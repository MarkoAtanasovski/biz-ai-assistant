import pytest
from fastapi.testclient import TestClient

import llm
import main

client = TestClient(main.app)


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_summary_endpoint_accepts_java_camel_case(api_rows):
    r = client.post("/analytics/summary", json=api_rows)
    assert r.status_code == 200
    assert r.json()["total_revenue"] == 46500.0


def test_by_region_by_product_by_month(api_rows):
    assert len(client.post("/analytics/by-region", json=api_rows).json()) == 2
    assert len(client.post("/analytics/by-product", json=api_rows).json()) == 2
    months = client.post("/analytics/by-month", json=api_rows).json()
    assert [m["month"] for m in months] == ["2026-07", "2026-08"]


def test_empty_list_is_fine():
    assert client.post("/analytics/by-region", json=[]).json() == []
    assert client.post("/analytics/summary", json=[]).json()["number_of_sales_records"] == 0


def test_ask_rejects_empty_question(api_rows):
    r = client.post("/ai/ask", json={"question": "   ", "sales": api_rows})
    assert r.status_code == 400


def test_ask_rejects_missing_data():
    r = client.post("/ai/ask", json={"question": "hi", "sales": []})
    assert r.status_code == 400 and "Upload" in r.json()["detail"]


def test_ask_without_api_key_is_503(api_rows, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = client.post("/ai/ask", json={"question": "hi", "sales": api_rows})
    assert r.status_code == 503


def test_ask_end_to_end_with_fake_gemini(api_rows, monkeypatch):
    from tests.test_llm import call_response, scripted, text_response

    gen = scripted(call_response("get_summary", {}), text_response("Total was EUR 46,500."))
    monkeypatch.setenv("GEMINI_API_KEY", "test")
    monkeypatch.setattr(llm, "gemini_generate", lambda key, prompt: gen)

    r = client.post("/ai/ask", json={"question": "total?", "sales": api_rows})
    body = r.json()
    assert r.status_code == 200
    assert body["answer"] == "Total was EUR 46,500."
    assert body["tool_calls"][0]["name"] == "get_summary"
    assert body["model"] == llm.GEMINI_MODEL
