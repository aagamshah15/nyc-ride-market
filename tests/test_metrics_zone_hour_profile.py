"""zone_hour_profile: trips per week in each hour-of-week slot, and each mode's share of the zone (Q1)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

DEC, JAN, FEB, MAR = date(2024, 12, 1), date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)


def test_zone_hour_profile(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": JAN, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 30, "trips_valid": 1},
        {"month": FEB, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 30},
        {"month": MAR, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 30},
        {"month": MAR, "pu_zone": 161, "hour_of_week": 56, "mode": "yellow", "trips_all": 45},
        {"month": MAR, "pu_zone": 161, "hour_of_week": 8, "mode": "uber", "trips_all": 45},
        {"month": FEB, "pu_zone": 132, "hour_of_week": 10, "mode": "lyft", "trips_all": 18},
        {"month": DEC, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 1_000},   # outside
    ]))
    table = metrics.run("zone_hour_profile", to_month="2025-03", window=3)
    assert table.column_names == ["pu_zone", "hour_of_week", "mode", "trips_per_week", "mode_share_in_zone"]
    # Window Jan–Mar 2025 = 31 + 28 + 31 = 90 days = 90/7 weeks, so trips_per_week = trips × 7 / 90.
    # Zone 161 over the window: uber 30 + 30 + 30 + 45 = 135, yellow 45, total 180
    #   → uber 0.75 and yellow 0.25 of the zone, in every hour.
    expected = [
        (132, 10, "lyft", 18 * 7 / 90, 1.0),     # 1.4
        (161, 8, "uber", 45 * 7 / 90, 0.75),     # 3.5
        (161, 56, "uber", 90 * 7 / 90, 0.75),    # 7.0
        (161, 56, "yellow", 45 * 7 / 90, 0.25),  # 3.5
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]


def test_days_count_only_months_in_the_table(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": FEB, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 28},
        {"month": MAR, "pu_zone": 161, "hour_of_week": 56, "mode": "uber", "trips_all": 31},
    ]))
    # January is missing, so the 3-month window holds 28 + 31 = 59 days: 59 trips × 7 / 59 = 7 a week.
    (row,) = metrics.run("zone_hour_profile", to_month="2025-03").to_pylist()
    assert row["trips_per_week"] == pytest.approx(7.0)
