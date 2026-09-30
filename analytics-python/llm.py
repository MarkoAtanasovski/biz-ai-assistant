"""
Gemini integration: retry with backoff + a small function-calling loop.

The model is given the DECLARATIONS below and nothing else about the
data except which regions/products/months exist. It asks for a function,
we run it with pandas (analytics.run_tool) and send the aggregate back.
Raw sales rows are never put in a prompt.
"""

import os
import random
import time
from typing import Any, Callable, List, Tuple

import pandas as pd
from fastapi import HTTPException
from google.genai import types

import analytics

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

# 429 = rate limited, 500/503/504 = Google-side trouble or overload.
# These usually pass within seconds, so waiting and retrying is right.
# Errors like 404 (wrong model) or 401/403 (bad key) will NOT fix
# themselves, so we fail immediately on those.
RETRYABLE_CODES = {429, 500, 503, 504}
MAX_ATTEMPTS = 4          # 1 first try + 3 retries
BASE_DELAY_SECONDS = 1.0  # waits ~1s, ~2s, ~4s between attempts
MAX_TOOL_ROUNDS = 5       # stop a model that keeps calling functions forever

T = types.Type
_STR = lambda d: types.Schema(type=T.STRING, description=d)  # noqa: E731
_FILTERS = {
    "region": _STR("Only include this region (exact name)."),
    "product": _STR("Only include this product (exact name)."),
    "month": _STR("Only include this month, formatted YYYY-MM."),
}
_DIM = types.Schema(type=T.STRING, enum=list(analytics.DIMENSIONS))
_METRIC = types.Schema(type=T.STRING, enum=list(analytics.METRICS))

DECLARATIONS = [
    types.FunctionDeclaration(
        name="get_summary",
        description="Overall KPIs: total revenue, total units, average revenue per sale, "
                    "number of records. Optionally filtered by region, product and/or month.",
        parameters=types.Schema(type=T.OBJECT, properties=dict(_FILTERS)),
    ),
    types.FunctionDeclaration(
        name="get_totals_by",
        description="Revenue and units summed per region, per product, or per month "
                    "(months are returned in chronological order). Optionally filtered.",
        parameters=types.Schema(
            type=T.OBJECT,
            properties={"group_by": _DIM, **_FILTERS},
            required=["group_by"],
        ),
    ),
    types.FunctionDeclaration(
        name="get_top_n",
        description="Rank regions, products or months by revenue or units sold. "
                    "Use ascending=true for the worst performers.",
        parameters=types.Schema(
            type=T.OBJECT,
            properties={
                "dimension": _DIM,
                "metric": _METRIC,
                "n": types.Schema(type=T.INTEGER, description="How many to return (default 3)."),
                "ascending": types.Schema(type=T.BOOLEAN, description="true = lowest first."),
                **_FILTERS,
            },
            required=["dimension"],
        ),
    ),
    types.FunctionDeclaration(
        name="compare_values",
        description="Compare two values of one dimension, e.g. two months or two regions. "
                    "Returns both sides plus the absolute and percent change (B minus A).",
        parameters=types.Schema(
            type=T.OBJECT,
            properties={
                "dimension": _DIM,
                "value_a": _STR("The baseline value, e.g. 2026-07 or Maribor."),
                "value_b": _STR("The value to compare against the baseline."),
            },
            required=["dimension", "value_a", "value_b"],
        ),
    ),
]


def build_system_prompt(df: pd.DataFrame) -> str:
    return (
        "You are a business analytics assistant for a sales dataset. You cannot see the "
        "raw data and you are unreliable at arithmetic, so ALWAYS get figures by calling "
        "the provided functions, and never estimate or calculate numbers yourself. "
        "Answer using ONLY what the functions return. Format money as euros with thousands "
        "separators and no decimals (for example EUR 26,800). Keep the answer to at most "
        "5 sentences. If the functions cannot answer the question (for example forecasts "
        "or data that is not in the dataset), say so plainly instead of guessing.\n\n"
        f"The dataset contains these values: {analytics.available_values(df)}"
    )


def call_with_retry(fn: Callable[[], Any], sleep: Callable[[float], None] = time.sleep) -> Tuple[Any, int]:
    """Run fn(); retry temporary Gemini errors with exponential backoff and
    jitter. Returns (result, number_of_retries)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(), attempt - 1
        except Exception as e:  # noqa: BLE001 - SDK raises several error types
            code = getattr(e, "code", None)
            if code not in RETRYABLE_CODES or attempt == MAX_ATTEMPTS:
                # 502 = "our upstream dependency (Gemini) failed"
                raise HTTPException(
                    status_code=502,
                    detail=f"Gemini API call failed after {attempt} attempt(s): {e}",
                )
            delay = BASE_DELAY_SECONDS * (2 ** (attempt - 1))
            sleep(delay * (0.75 + random.random() * 0.5))
    raise AssertionError("unreachable")


def answer_question(question: str, df: pd.DataFrame,
                    generate: Callable[[List[types.Content]], Any],
                    sleep: Callable[[float], None] = time.sleep) -> dict:
    """The function-calling loop. `generate(contents)` performs one model call
    (injected so tests can fake Gemini)."""
    contents: List[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=question)])
    ]
    tool_calls: List[dict] = []
    retries = 0

    for round_no in range(1, MAX_TOOL_ROUNDS + 2):
        response, r = call_with_retry(lambda: generate(contents), sleep)
        retries += r
        calls = response.function_calls or []
        if not calls:
            return {"answer": response.text or "", "tool_calls": tool_calls,
                    "llm_calls": round_no, "retries": retries}
        if round_no > MAX_TOOL_ROUNDS:
            break

        # Send the model's own turn back untouched (Gemini 3 needs its
        # thought signatures), then one response per call, in order.
        contents.append(response.candidates[0].content)
        parts = []
        for fc in calls:
            args = dict(fc.args or {})
            result = analytics.run_tool(df, fc.name, args)
            tool_calls.append({"name": fc.name, "args": args, "result": result})
            parts.append(types.Part(function_response=types.FunctionResponse(
                id=fc.id, name=fc.name, response={"result": result})))
        contents.append(types.Content(role="user", parts=parts))

    raise HTTPException(status_code=502,
                        detail=f"The model kept calling functions after {MAX_TOOL_ROUNDS} rounds.")


def gemini_generate(api_key: str, system_prompt: str) -> Callable[[List[types.Content]], Any]:
    from google import genai

    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(
        system_instruction=system_prompt,
        tools=[types.Tool(function_declarations=DECLARATIONS)],
        # We run the loop ourselves so we can report which functions were used.
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
    )
    return lambda contents: client.models.generate_content(
        model=GEMINI_MODEL, contents=contents, config=config)
