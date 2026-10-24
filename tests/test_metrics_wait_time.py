"""wait_time: seconds from request to pickup, by zone and city-wide (Q8)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_wait_time(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "hour_of_week": 8, "wait_s_sum": 24_000, "wait_n": 100},
        {"mode": "uber", "pu_zone": 161, "hour_of_week": 56, "wait_s_sum": 6_000, "wait_n": 50},
        {"mode": "uber", "pu_zone": 132, "wait_s_sum": 9_000, "wait_n": 30},
        {"mode": "lyft", "pu_zone": 161, "wait_s_sum": 12_000, "wait_n": 40},
        {"mode": "yellow", "pu_zone": 161},
    ], month=MAR))
    write_agg("agg_zone_month_dist", agg_table("agg_zone_month_dist", [
        {"mode": "uber", "pu_zone": 161, "wait_p50": 180.0, "wait_p90": 420.0},
        {"mode": "uber", "pu_zone": 0, "wait_p50": 190.0, "wait_p90": 450.0},
        {"mode": "lyft", "pu_zone": 0, "wait_p50": 280.0, "wait_p90": 600.0},
        {"mode": "all", "pu_zone": 0, "wait_p50": None, "wait_p90": None},
        {"mode": "yellow", "pu_zone": 161},
    ], month=MAR))
    table = metrics.run("wait_time")
    assert table.column_names == ["month", "pu_zone", "mode", "wait_p50", "wait_p90", "wait_mean"]
    # Means are wait_s_sum ÷ wait_n: uber 161 (24,000 + 6,000) / 150 = 200; uber 132 9,000 / 30 = 300;
    # lyft 161 12,000 / 40 = 300; city-wide uber 39,000 / 180, lyft 300.
    # Percentiles are NULL where the distribution table has no row (n < 100).
    expected = [
        (MAR, 0, "lyft", 280.0, 600.0, 300.0),
        (MAR, 0, "uber", 190.0, 450.0, 39_000 / 180),
        (MAR, 132, "uber", None, None, 300.0),
        (MAR, 161, "lyft", None, None, 300.0),
        (MAR, 161, "uber", 180.0, 420.0, 200.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
