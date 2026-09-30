"""
Pure analytics functions: no web framework, no LLM, easy to test.

Every function takes a pandas DataFrame with the columns in SALE_COLUMNS.
The LLM never sees raw rows - it can only call the functions in TOOLS
below and read the aggregates they return.
"""

from typing import Any, Callable, Dict, Iterable, List, Optional

import pandas as pd

SALE_COLUMNS = ["region", "product", "revenue", "units_sold", "month"]
DIMENSIONS = ("region", "product", "month")
METRICS = ("revenue", "units_sold")


def to_frame(rows: Iterable[dict]) -> pd.DataFrame:
    # Passing columns= means an EMPTY list still gives a valid (empty)
    # table with the right column names, instead of one with no columns.
    return pd.DataFrame(list(rows), columns=SALE_COLUMNS)


def _filter(df: pd.DataFrame, region=None, product=None, month=None) -> pd.DataFrame:
    for column, value in (("region", region), ("product", product), ("month", month)):
        if value is not None:
            df = df[df[column] == value]
    return df


def compute_summary(df: pd.DataFrame, region=None, product=None, month=None) -> dict:
    df = _filter(df, region, product, month)
    return {
        "total_revenue": round(float(df["revenue"].sum()), 2),
        "total_units_sold": int(df["units_sold"].sum()),
        # mean() of an empty column is NaN, which is not valid JSON
        "average_revenue_per_sale": round(float(df["revenue"].mean()), 2) if len(df) else 0.0,
        "number_of_sales_records": len(df),
    }


def group_totals(df: pd.DataFrame, column: str, region=None, product=None, month=None) -> List[dict]:
    """SQL-style GROUP BY: sum revenue and units per value of `column`,
    sorted by that value (so months come out in chronological order)."""
    _check_choice("dimension", column, DIMENSIONS)
    df = _filter(df, region, product, month)
    if df.empty:
        return []
    out = df.groupby(column)[["revenue", "units_sold"]].sum().reset_index()
    out["revenue"] = out["revenue"].round(2)
    return out.to_dict(orient="records")


def top_n(df: pd.DataFrame, dimension: str, metric: str = "revenue", n: int = 3,
          ascending: bool = False, region=None, product=None, month=None) -> List[dict]:
    _check_choice("metric", metric, METRICS)
    n = max(1, min(int(n), 20))
    rows = group_totals(df, dimension, region, product, month)
    return sorted(rows, key=lambda r: r[metric], reverse=not ascending)[:n]


def compare_values(df: pd.DataFrame, dimension: str, value_a: str, value_b: str) -> dict:
    """Compare two values of one dimension (e.g. two months, two regions).
    Changes are B minus A, so the model never has to do the subtraction."""
    _check_choice("dimension", dimension, DIMENSIONS)
    a = compute_summary(df, **{dimension: value_a})
    b = compute_summary(df, **{dimension: value_b})
    if a["number_of_sales_records"] == 0 or b["number_of_sales_records"] == 0:
        raise ValueError(f"No sales found for {dimension} = {value_a!r} and/or {value_b!r}.")

    def change(key):
        diff = round(b[key] - a[key], 2)
        pct = round(diff / a[key] * 100, 2) if a[key] else None
        return diff, pct

    rev_change, rev_pct = change("total_revenue")
    unit_change, unit_pct = change("total_units_sold")
    return {
        "dimension": dimension,
        "a": {"value": value_a, **a},
        "b": {"value": value_b, **b},
        "revenue_change_b_minus_a": rev_change,
        "revenue_change_percent": rev_pct,
        "units_change_b_minus_a": unit_change,
        "units_change_percent": unit_pct,
    }


def available_values(df: pd.DataFrame) -> Dict[str, List[str]]:
    return {d: sorted(df[d].dropna().unique().tolist()) for d in DIMENSIONS}


def _check_choice(name: str, value: Any, allowed: tuple) -> None:
    if value not in allowed:
        raise ValueError(f"{name} must be one of {list(allowed)}, got {value!r}.")


# ---------------------------------------------------------------------
# Tool registry: name -> function(df, **args). llm.py declares the same
# names to Gemini; tests check the two stay in sync.
# ---------------------------------------------------------------------
def _tool_get_summary(df, region=None, product=None, month=None):
    return _non_empty(df, region, product, month) or compute_summary(df, region, product, month)


def _tool_totals_by(df, group_by, region=None, product=None, month=None):
    return _non_empty(df, region, product, month) or group_totals(df, group_by, region, product, month)


def _tool_top_n(df, dimension, metric="revenue", n=3, ascending=False, region=None, product=None, month=None):
    return _non_empty(df, region, product, month) or top_n(df, dimension, metric, n, ascending, region, product, month)


def _tool_compare(df, dimension, value_a, value_b):
    return compare_values(df, dimension, value_a, value_b)


def _non_empty(df, region, product, month) -> Optional[dict]:
    """Return an error dict (with the valid values) if the filters match
    nothing, so the model can say so instead of reporting zeros."""
    if len(_filter(df, region, product, month)) > 0:
        return None
    return {
        "error": "No sales match those filters.",
        "filters": {"region": region, "product": product, "month": month},
        "valid_values": available_values(df),
    }


TOOLS: Dict[str, Callable[..., Any]] = {
    "get_summary": _tool_get_summary,
    "get_totals_by": _tool_totals_by,
    "get_top_n": _tool_top_n,
    "compare_values": _tool_compare,
}


def run_tool(df: pd.DataFrame, name: str, args: Optional[dict]) -> Any:
    """Execute one tool call. Never raises: problems come back as
    {"error": ...} so the model can recover or explain."""
    fn = TOOLS.get(name)
    if fn is None:
        return {"error": f"Unknown function {name!r}. Available: {sorted(TOOLS)}"}
    try:
        return fn(df, **(args or {}))
    except (ValueError, TypeError) as e:
        return {"error": str(e)}
