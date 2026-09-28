"""
Business AI Assistant - Python Analytics Microservice

This service is the "number-crunching" layer of our project. The Spring
Boot backend (or later, our AI layer) will call these endpoints over
HTTP to get real analytics on the sales data - things Java/SQL alone
would be more awkward to compute, but pandas makes trivial.

Run locally with:  uvicorn main:app --reload --port 8000
"""

import os
import random
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd

app = FastAPI(title="Biz AI Analytics Service")

# CORS: browsers block a web page from calling an API on a different
# origin (here: React on :5173 calling FastAPI on :8000) unless the API
# says it is allowed. Only our own dev frontend is whitelisted.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

# In Phase 2 this same data lived in the Java/H2 database. For now we
# duplicate a copy here as a pandas DataFrame so this service can be
# developed and tested independently. Later (Phase 4/6) we can have
# Java call this service and pass real data instead of using this
# hardcoded copy.
sales_data = pd.DataFrame([
    {"region": "Ljubljana", "product": "Widget A", "revenue": 12500.0, "units_sold": 340, "month": "2026-07"},
    {"region": "Ljubljana", "product": "Widget B", "revenue": 8200.0,  "units_sold": 210, "month": "2026-07"},
    {"region": "Maribor",   "product": "Widget A", "revenue": 6100.0,  "units_sold": 165, "month": "2026-07"},
    {"region": "Ljubljana", "product": "Widget A", "revenue": 14300.0, "units_sold": 390, "month": "2026-08"},
    {"region": "Maribor",   "product": "Widget B", "revenue": 5400.0,  "units_sold": 140, "month": "2026-08"},
])


@app.get("/health")
def health():
    """Simple check that the service is alive - same idea as the Java
    /api/health endpoint from Phase 1."""
    return {"status": "ok", "service": "biz-ai-analytics"}


@app.get("/analytics/summary")
def summary():
    """
    Returns high-level KPIs across all sales data:
    total revenue, total units sold, and average revenue per sale.

    pandas makes this a one-liner instead of writing manual loops -
    this is the whole point of using Python/pandas for this layer
    rather than doing it in Java.
    """
    return {
        "total_revenue": float(sales_data["revenue"].sum()),
        "total_units_sold": int(sales_data["units_sold"].sum()),
        "average_revenue_per_sale": round(float(sales_data["revenue"].mean()), 2),
        "number_of_sales_records": len(sales_data),
    }


@app.get("/analytics/by-region")
def by_region():
    """
    Groups the data by region and sums revenue + units sold per region.
    This is the pandas equivalent of a SQL "GROUP BY region" query.
    """
    grouped = (
        sales_data
        .groupby("region")[["revenue", "units_sold"]]
        .sum()
        .reset_index()
    )
    # .to_dict(orient="records") turns the table into a list of plain
    # dictionaries, which FastAPI automatically converts to JSON.
    return grouped.to_dict(orient="records")


@app.get("/analytics/by-product")
def by_product():
    """Same idea, grouped by product instead of region."""
    grouped = (
        sales_data
        .groupby("product")[["revenue", "units_sold"]]
        .sum()
        .reset_index()
    )
    return grouped.to_dict(orient="records")


# ---------------------------------------------------------------------
# PHASE 4: AI layer
# ---------------------------------------------------------------------
# Design principle (worth remembering for interviews):
#   pandas does the MATH, the LLM does the EXPLAINING.
# LLMs are unreliable at arithmetic and will happily invent numbers, so
# we compute the real figures ourselves first and hand them to the model
# as context. This is called "grounding" - it keeps answers tied to real
# data instead of the model's imagination.
#
# The model name lives in an environment variable because Google
# renames/retires models often. If you get a "model not found" error,
# set GEMINI_MODEL to a current Flash model listed in Google AI Studio.

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Retry settings for temporary Gemini failures.
# 429 = rate limited, 500/503/504 = Google-side trouble or overload.
# These usually pass within seconds, so waiting and retrying is right.
# Errors like 404 (wrong model) or 401/403 (bad key) will NOT fix
# themselves, so we fail immediately on those instead of wasting time.
RETRYABLE_CODES = {429, 500, 503, 504}
MAX_ATTEMPTS = 4          # 1 first try + 3 retries
BASE_DELAY_SECONDS = 1.0  # waits ~1s, ~2s, ~4s between attempts


class Question(BaseModel):
    """The JSON body clients must send to /ai/ask: {"question": "..."}"""
    question: str


def build_context() -> str:
    """Turn our analytics into plain text the LLM can read."""
    return (
        f"Summary KPIs: {summary()}\n"
        f"Totals by region: {by_region()}\n"
        f"Totals by product: {by_product()}\n"
        f"Raw sales rows (CSV):\n{sales_data.to_csv(index=False)}"
    )


@app.post("/ai/ask")
def ask(body: Question):
    """Answer a plain-English question about the sales data using Gemini."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    # Never hardcode API keys in source code - read from the environment.
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="GEMINI_API_KEY is not set. Set it in the same terminal "
                   "that runs uvicorn, then restart the server.",
        )

    try:
        from google import genai  # imported here so the rest of the
        # service still works even if the package is not installed
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="google-genai is not installed. Run: pip install google-genai",
        )

    prompt = (
        "You are a business analytics assistant. Answer the question using "
        "ONLY the data below. Quote the relevant numbers, formatting money as "
        "euros with thousands separators and no decimals (for example "
        "EUR 26,800), keep the answer "
        "short (max 5 sentences), and if the data cannot answer the "
        "question, say so instead of guessing.\n\n"
        f"DATA:\n{build_context()}\n\n"
        f"QUESTION: {question}"
    )

    client = genai.Client(api_key=api_key)

    # Retry with exponential backoff: wait 1s, then 2s, then 4s, so a
    # busy moment on Google's side does not become an error for our user.
    # A little random "jitter" stops many clients retrying in lockstep.
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
            return {
                "question": question,
                "answer": response.text,
                "model": GEMINI_MODEL,
                "attempts": attempt,
            }
        except Exception as e:
            code = getattr(e, "code", None)
            is_temporary = code in RETRYABLE_CODES
            out_of_attempts = attempt == MAX_ATTEMPTS
            if not is_temporary or out_of_attempts:
                # 502 = "our upstream dependency (Gemini) failed"
                raise HTTPException(
                    status_code=502,
                    detail=f"Gemini API call failed after {attempt} attempt(s): {e}",
                )
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            time.sleep(delay * (0.75 + random.random() * 0.5))
