"""zone_share_change: each mode's pickup share in a zone vs a year earlier (Q1, Q4, Q10)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR25, FEB25, MAR24 = date(2025, 3, 1), date(2025, 2, 1), date(2024, 3, 1)


@pytest.fixture
def zone_hour(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        # zone 161, March 2025: 1,240 trips
        {"month": MAR25, "pu_zone": 161, "mode": "uber", "trips_all": 620, "trips_valid": 1},
        {"month": MAR25, "pu_zone": 161, "mode": "lyft", "trips_all": 310},
        {"month": MAR25, "pu_zone": 161, "mode": "yellow", "trips_all": 310},
        # zone 161, March 2024: 1,000 trips
        {"month": MAR24, "pu_zone": 161, "mode": "uber", "trips_all": 400},
        {"month": MAR24, "pu_zone": 161, "mode": "yellow", "trips_all": 500},
        {"month": MAR24, "pu_zone": 161, "mode": "green", "trips_all": 100},
        # zone 132: March 2025 only
        {"month": MAR25, "pu_zone": 132, "mode": "uber", "trips_all": 31},
        # outside both months
        {"month": FEB25, "pu_zone": 161, "mode": "uber", "trips_all": 9_999},
    ]))


EXPECTED = [
    # zone 132 had no trips in March 2024, so share_prior and change are NULL
    (132, "ride_hail", 1.0, 1.0, None, None),
    (132, "uber", 1.0, 1.0, None, None),
    # zone 161; March 2025 has 31 days
    (161, "green", 0.0, 0.0, 0.1, -0.1),            # 0 of 1,240 now; 100 of 1,000 then
    (161, "lyft", 10.0, 0.25, 0.0, 0.25),           # 310 / 31; 310 / 1,240; none then
    (161, "ride_hail", 30.0, 0.75, 0.4, 0.35),      # uber + lyft 930 / 31; 930 / 1,240; 400 / 1,000
    (161, "uber", 20.0, 0.5, 0.4, 0.1),             # 620 / 31; 620 / 1,240; 400 / 1,000
    (161, "yellow", 10.0, 0.25, 0.5, -0.25),        # 310 / 31; 310 / 1,240; 500 / 1,000
]


def test_zone_share_change(zone_hour):
    table = metrics.run("zone_share_change", to_month="2025-03")
    assert table.column_names == ["pu_zone", "mode", "trips_per_day", "share", "share_prior", "change"]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in EXPECTED]


def test_to_month_defaults_to_latest(zone_hour):
    assert metrics.run("zone_share_change").to_pylist() == metrics.run("zone_share_change", to_month="2025-03").to_pylist()
