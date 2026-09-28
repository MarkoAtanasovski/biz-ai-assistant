"""
Business AI Assistant - Python Analytics Microservice

This service is the "number-crunching" layer of our project. The Spring
Boot backend is the only caller: it owns the sales data (in H2) and
sends it to us on every request. pandas does the math here because it
is more awkward to do the same aggregations directly in Java/SQL.

Run locally with:  uvicorn main:app --reload --port 8000
"""

import os
import random
import time

from typing import List
from pydantic import BaseModel, ConfigDict, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import pandas as pd

app = FastAPI(title="Biz AI Analytics Service")

# CORS: browsers block a web page from calling an API on a different
# origin. Kept even though the React dashboard now goes through Java
# (localhost:8080), in case this service is ever called directly again.
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


SALE_COLUMNS = ["region", "product", "revenue", "units_sold", "month"]


def to_frame(rows: List[SaleRow]) -> pd.DataFrame:
    # Passing columns= means an EMPTY list still gives a valid (empty)
    # table with the right column names, instead of one with no columns.
    return pd.DataFrame([r.model_dump() for r in rows], columns=SALE_COLUMNS)


def compute_summary(df: pd.DataFrame) -> dict:
    return {
        "total_revenue": float(df["revenue"].sum()),
        "total_units_sold": int(df["units_sold"].sum()),
        # mean() of an empty column is NaN, which is not valid JSON
        "average_revenue_per_sale": round(float(df["revenue"].mean()), 2) if len(df) else 0.0,
        "number_of_sales_records": len(df),
    }


def group_totals(df: pd.DataFrame, column: str) -> list:
    """SQL-style GROUP BY: sum revenue and units per value of `column`.
    .to_dict(orient="records") turns the table into a list of plain
    dictionaries, which FastAPI automatically converts to JSON."""
    return (
        df.groupby(column)[["revenue", "units_sold"]]
        .sum()
        .reset_index()
        .to_dict(orient="records")
    )


@app.get("/health")
def health():
    """Simple check that the service is alive - same idea as the Java
    /api/health endpoint from Phase 1."""
    return {"status": "ok", "service": "biz-ai-analytics"}


@app.post("/analytics/summary")
def summary_from_rows(rows: List[SaleRow]):
    """KPIs (total revenue, total units sold, average revenue per
    sale) for the rows the caller (Java) supplies."""
    return compute_summary(to_frame(rows))


@app.post("/analytics/by-region")
def by_region_from_rows(rows: List[SaleRow]):
    """Totals per region for the rows the caller (Java) supplies."""
    return group_totals(to_frame(rows), "region")


@app.post("/analytics/by-product")
def by_product_from_rows(rows: List[SaleRow]):
    """Totals per product for the rows the caller (Java) supplies."""
    return group_totals(to_frame(rows), "product")


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
    """The JSON body for /ai/ask: {"question": "...", "sales": [...]}.
    Java always supplies `sales` from its own database - there is no
    hardcoded fallback anymore, so it is required."""
    question: str
    sales: List[SaleRow]


def build_context(df: pd.DataFrame) -> str:
    """Turn the analytics for the given rows into plain text the LLM can read."""
    return (
        f"Summary KPIs: {compute_summary(df)}\n"
        f"Totals by region: {group_totals(df, 'region')}\n"
        f"Totals by product: {group_totals(df, 'product')}\n"
        f"Raw sales rows (CSV):\n{df.to_csv(index=False)}"
    )


@app.post("/ai/ask")
def ask(body: Question):
    """Answer a plain-English question about the sales data using Gemini."""
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question must not be empty.")

    df = to_frame(body.sales)

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
        f"DATA:\n{build_context(df)}\n\n"
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
