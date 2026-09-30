"""
Business AI Assistant - Python Analytics Microservice

Stateless: the Spring Boot backend owns the sales data and sends it on
every request. pandas does the math (analytics.py); Gemini only explains
aggregates it fetches through function calls (llm.py).

Run locally with:  uvicorn main:app --reload --port 8000
"""

import os
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field

import analytics
import llm

app = FastAPI(title="Biz AI Analytics Service")

# Kept in case this service is ever called directly from a browser.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class SaleRow(BaseModel):
    """One sale as sent by the Java backend. Java's JSON uses
    camelCase (unitsSold); the alias lets us keep snake_case here."""
    model_config = ConfigDict(populate_by_name=True)

    region: str
    product: str
    revenue: float
    units_sold: int = Field(alias="unitsSold")
    month: str


class Question(BaseModel):
    """Body for /ai/ask: {"question": "...", "sales": [...]}."""
    question: str = Field(max_length=500)
    sales: List[SaleRow]


def frame(rows: List[SaleRow]):
    return analytics.to_frame(r.model_dump() for r in rows)


@app.get("/health")
def health():
    return {"status": "ok", "service": "biz-ai-analytics"}


@app.post("/analytics/summary")
def summary(rows: List[SaleRow]):
    return analytics.compute_summary(frame(rows))


@app.post("/analytics/by-region")
def by_region(rows: List[SaleRow]):
    return analytics.group_totals(frame(rows), "region")


@app.post("/analytics/by-product")
def by_product(rows: List[SaleRow]):
    return analytics.group_totals(frame(rows), "product")


@app.post("/analytics/by-month")
def by_month(rows: List[SaleRow]):
    return analytics.group_totals(frame(rows), "month")


@app.post("/ai/ask")
def ask(body: Question):
    """Answer a plain-English question. Gemini picks which analytics
    functions to run; only their aggregate results reach the model."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")
    if not body.sales:
        raise HTTPException(status_code=400, detail="There is no sales data yet. Upload a CSV first.")

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set. Set it in the environment that runs "
                   "the service, then restart it.",
        )

    df = frame(body.sales)
    generate = llm.gemini_generate(api_key, llm.build_system_prompt(df))
    result = llm.answer_question(question, df, generate)
    return {"question": question, "model": llm.GEMINI_MODEL, **result}
