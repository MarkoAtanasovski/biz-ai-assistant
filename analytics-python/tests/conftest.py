import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest

import analytics

ROWS = [
    {"region": "Ljubljana", "product": "Widget A", "revenue": 12500.0, "units_sold": 340, "month": "2026-07"},
    {"region": "Ljubljana", "product": "Widget B", "revenue": 8200.0, "units_sold": 210, "month": "2026-07"},
    {"region": "Maribor", "product": "Widget A", "revenue": 6100.0, "units_sold": 165, "month": "2026-07"},
    {"region": "Ljubljana", "product": "Widget A", "revenue": 14300.0, "units_sold": 390, "month": "2026-08"},
    {"region": "Maribor", "product": "Widget B", "revenue": 5400.0, "units_sold": 140, "month": "2026-08"},
]


@pytest.fixture
def df():
    return analytics.to_frame(ROWS)


@pytest.fixture
def api_rows():
    """The same rows as Java sends them (camelCase unitsSold)."""
    out = []
    for r in ROWS:
        row = dict(r)
        row["unitsSold"] = row.pop("units_sold")
        out.append(row)
    return out
