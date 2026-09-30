import pytest

import analytics


def test_summary_totals(df):
    s = analytics.compute_summary(df)
    assert s["total_revenue"] == 46500.0
    assert s["total_units_sold"] == 1245
    assert s["average_revenue_per_sale"] == 9300.0
    assert s["number_of_sales_records"] == 5


def test_summary_on_empty_table_is_valid_json_safe():
    s = analytics.compute_summary(analytics.to_frame([]))
    assert s == {"total_revenue": 0.0, "total_units_sold": 0,
                 "average_revenue_per_sale": 0.0, "number_of_sales_records": 0}


def test_summary_with_filters(df):
    s = analytics.compute_summary(df, region="Maribor", month="2026-08")
    assert s["total_revenue"] == 5400.0
    assert s["number_of_sales_records"] == 1


def test_group_by_region(df):
    rows = analytics.group_totals(df, "region")
    assert rows == [
        {"region": "Ljubljana", "revenue": 35000.0, "units_sold": 940},
        {"region": "Maribor", "revenue": 11500.0, "units_sold": 305},
    ]


def test_group_by_month_is_chronological(df):
    months = [r["month"] for r in analytics.group_totals(df, "month")]
    assert months == ["2026-07", "2026-08"]


def test_group_by_empty_table_returns_empty_list():
    assert analytics.group_totals(analytics.to_frame([]), "region") == []


def test_group_by_rejects_unknown_dimension(df):
    with pytest.raises(ValueError):
        analytics.group_totals(df, "revenue")


def test_top_n_orders_and_limits(df):
    top = analytics.top_n(df, "product", "revenue", n=1)
    assert [r["product"] for r in top] == ["Widget A"]
    worst = analytics.top_n(df, "region", "units_sold", ascending=True, n=1)
    assert worst[0]["region"] == "Maribor"


def test_compare_values_does_the_subtraction(df):
    c = analytics.compare_values(df, "month", "2026-07", "2026-08")
    assert c["a"]["total_revenue"] == 26800.0
    assert c["b"]["total_revenue"] == 19700.0
    assert c["revenue_change_b_minus_a"] == -7100.0
    assert c["revenue_change_percent"] == -26.49


def test_compare_values_unknown_value_raises(df):
    with pytest.raises(ValueError):
        analytics.compare_values(df, "month", "2026-07", "1999-01")


def test_run_tool_reports_no_match_with_valid_values(df):
    out = analytics.run_tool(df, "get_summary", {"region": "Atlantis"})
    assert "error" in out
    assert "Ljubljana" in out["valid_values"]["region"]


def test_run_tool_never_raises(df):
    assert "error" in analytics.run_tool(df, "does_not_exist", {})
    assert "error" in analytics.run_tool(df, "get_totals_by", {"group_by": "nonsense"})
    assert "error" in analytics.run_tool(df, "get_summary", {"bogus_arg": 1})
