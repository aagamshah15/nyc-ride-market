"""top_destinations: each pickup zone's busiest drop-off zones, all modes summed (Q1)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR, FEB = date(2025, 3, 1), date(2025, 2, 1)


@pytest.fixture
def od(data_dir):
    write_agg("agg_od_month", agg_table("agg_od_month", [
        {"month": MAR, "pu_zone": 161, "do_zone": 236, "mode": "uber", "trips_valid": 40},
        {"month": MAR, "pu_zone": 161, "do_zone": 236, "mode": "yellow", "trips_valid": 20},
        {"month": MAR, "pu_zone": 161, "do_zone": 237, "mode": "uber", "trips_valid": 30},
        {"month": MAR, "pu_zone": 161, "do_zone": 162, "mode": "lyft", "trips_valid": 30},
        {"month": MAR, "pu_zone": 161, "do_zone": 100, "mode": "uber", "trips_valid": 25},
        {"month": MAR, "pu_zone": 132, "do_zone": 161, "mode": "uber", "trips_valid": 50},
        {"month": FEB, "pu_zone": 161, "do_zone": 999, "mode": "uber", "trips_valid": 500},
    ]))
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": MAR, "pu_zone": 161, "mode": "uber", "trips_valid": 200, "trips_all": 260},
        {"month": MAR, "pu_zone": 161, "mode": "yellow", "trips_valid": 100, "trips_all": 140},
        {"month": MAR, "pu_zone": 132, "mode": "uber", "trips_valid": 200},
    ]))


def test_top_destinations(od):
    table = metrics.run("top_destinations", to_month="2025-03", top_n=2)
    assert table.column_names == ["pu_zone", "do_zone", "rank", "trips", "share"]
    # Zone 161 has 200 + 100 = 300 valid trips (agg_zone_hour). Pairs: 236 = 40 + 20 = 60,
    # 162 = 30, 237 = 30, 100 = 25. The 30s tie and rank by do_zone, so 162 comes second.
    # Zone 132 has 200 valid trips; 132 → 161 = 50.
    expected = [
        (132, 161, 1, 50, 50 / 200),
        (161, 236, 1, 60, 60 / 300),
        (161, 162, 2, 30, 30 / 300),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]


def test_top_n_defaults_to_ten(od):
    table = metrics.run("top_destinations", to_month="2025-03")
    assert [(r["pu_zone"], r["do_zone"], r["rank"]) for r in table.to_pylist()] == [
        (132, 161, 1), (161, 236, 1), (161, 162, 2), (161, 237, 3), (161, 100, 4)]
