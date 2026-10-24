"""share_monthly: each mode's share of all trips, by month (Q1)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR, FEB24 = date(2025, 3, 1), date(2024, 2, 1)


def test_share_monthly(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": MAR, "mode": "uber", "pu_zone": 161, "trips_all": 1_000, "trips_valid": 1},
        {"month": MAR, "mode": "uber", "pu_zone": 132, "trips_all": 550, "trips_valid": 1},
        {"month": MAR, "mode": "lyft", "trips_all": 620},
        {"month": MAR, "mode": "other_hv", "trips_all": 31},
        {"month": MAR, "mode": "yellow", "trips_all": 868},
        {"month": MAR, "mode": "green", "trips_all": 31},
        {"month": FEB24, "mode": "uber", "trips_all": 290},
    ]))
    table = metrics.run("share_monthly")
    assert table.column_names == ["month", "mode", "trips", "days", "trips_per_day", "share"]
    # March 2025 has 31 days and 3,100 trips in all (trips_all, not trips_valid):
    #   uber 1,000 + 550 = 1,550 → 50/day, 1,550 / 3,100 = 0.50
    #   lyft 620 → 20/day, 0.20 · other_hv 31 → 1/day, 0.01
    #   yellow 868 → 28/day, 0.28 · green 31 → 1/day, 0.01
    #   ride_hail 1,550 + 620 + 31 = 2,201 → 71/day, 0.71 · taxi 899 → 29/day, 0.29
    # February 2024 has 29 days: uber 290 → 10/day, the whole month; no taxi row.
    expected = [
        (FEB24, "ride_hail", 290, 29, 10.0, 1.0),
        (FEB24, "uber", 290, 29, 10.0, 1.0),
        (MAR, "green", 31, 31, 1.0, 0.01),
        (MAR, "lyft", 620, 31, 20.0, 0.20),
        (MAR, "other_hv", 31, 31, 1.0, 0.01),
        (MAR, "ride_hail", 2_201, 31, 71.0, 0.71),
        (MAR, "taxi", 899, 31, 29.0, 0.29),
        (MAR, "uber", 1_550, 31, 50.0, 0.50),
        (MAR, "yellow", 868, 31, 28.0, 0.28),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
