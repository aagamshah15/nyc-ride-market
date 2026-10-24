"""wait_by_hour: mean wait by hour of day, by zone and city-wide (Q8)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

FEB, MAR = date(2025, 2, 1), date(2025, 3, 1)


def test_wait_by_hour(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": MAR, "mode": "uber", "pu_zone": 161, "hour_of_week": 8, "wait_s_sum": 3_000, "wait_n": 10},
        {"month": MAR, "mode": "uber", "pu_zone": 161, "hour_of_week": 56, "wait_s_sum": 9_000, "wait_n": 20},
        {"month": MAR, "mode": "uber", "pu_zone": 161, "hour_of_week": 57, "wait_s_sum": 1_500, "wait_n": 5},
        {"month": MAR, "mode": "lyft", "pu_zone": 132, "hour_of_week": 32, "wait_s_sum": 2_000, "wait_n": 10},
        {"month": MAR, "mode": "yellow", "pu_zone": 161, "hour_of_week": 8},
        {"month": FEB, "mode": "uber", "pu_zone": 161, "hour_of_week": 8, "wait_s_sum": 100_000, "wait_n": 1},
    ]))
    table = metrics.run("wait_by_hour", to_month="2025-03", window=1)
    assert table.column_names == ["pu_zone", "hour", "mode", "wait_mean"]
    # Hour of day = hour_of_week mod 24: 8 (Sun) and 56 (Tue) are both 8 am, 57 is 9 am, 32 (Mon) is 8 am.
    # uber 161 at 8 am: (3,000 + 9,000) / (10 + 20) = 400; at 9 am: 1,500 / 5 = 300.
    # lyft 132 at 8 am: 2,000 / 10 = 200. City-wide rows (pu_zone 0) repeat these; February is outside.
    expected = [
        (0, 8, "lyft", 200.0),
        (0, 8, "uber", 400.0),
        (0, 9, "uber", 300.0),
        (132, 8, "lyft", 200.0),
        (161, 8, "uber", 400.0),
        (161, 9, "uber", 300.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
