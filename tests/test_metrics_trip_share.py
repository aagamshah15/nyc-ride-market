"""trip_share: each mode's share of pickups by month and zone (Q1, Q4, Q9, Q10)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR, APR = date(2025, 3, 1), date(2025, 4, 1)


def test_trip_share(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": MAR, "pu_zone": 161, "mode": "uber", "hour_of_week": 8, "trips_all": 40, "trips_valid": 1},
        {"month": MAR, "pu_zone": 161, "mode": "uber", "hour_of_week": 56, "trips_all": 20, "trips_valid": 1},
        {"month": MAR, "pu_zone": 161, "mode": "yellow", "trips_all": 40, "trips_valid": 39},
        {"month": MAR, "pu_zone": 132, "mode": "lyft", "trips_all": 25},
        {"month": MAR, "pu_zone": 132, "mode": "uber", "trips_all": 75},
        {"month": APR, "pu_zone": 161, "mode": "uber", "trips_all": 10},
    ]))
    table = metrics.run("trip_share")
    assert table.column_names == ["month", "pu_zone", "mode", "trips", "share"]
    # Zone 161, March: uber 40 + 20 = 60 of 100 trips (trips_all) → 0.6; yellow 40 → 0.4.
    # Zone 132, March: lyft 25 of 100 → 0.25; uber 75 → 0.75.
    # Zone 161, April is its own partition: uber 10 of 10 → 1.0.
    expected = [
        (MAR, 132, "lyft", 25, 0.25),
        (MAR, 132, "uber", 75, 0.75),
        (MAR, 161, "uber", 60, 0.6),
        (MAR, 161, "yellow", 40, 0.4),
        (APR, 161, "uber", 10, 1.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
