"""tip_rate: tips as a share of the base fare, by borough; cab tips are card-only (Q13)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def write_zone_lookup(data_dir):
    (data_dir / "ref").mkdir()
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text(
        '"LocationID","Borough","Zone","service_zone"\n'
        '7,"Queens","Astoria","Boro Zone"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n'
        '264,"Unknown","N/A","N/A"\n')


def test_tip_rate(data_dir):
    write_zone_lookup(data_dir)
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "tips": 30.0, "fare_base": 300.0},
        {"mode": "uber", "pu_zone": 7, "tips": 10.0, "fare_base": 200.0},
        {"mode": "yellow", "pu_zone": 161, "tips": 999.0, "fare_base": 1_000.0,
         "card_tips": 150.0, "card_fare_base": 750.0},
        {"mode": "uber", "pu_zone": 264, "trips_valid": 0, "tips": None, "fare_base": None},
    ], month=MAR))
    table = metrics.run("tip_rate")
    assert table.column_names == ["month", "pu_borough", "mode", "tips", "fare_base", "tip_rate", "card_only"]
    # uber Manhattan 30 / 300 = 0.10, Queens 10 / 200 = 0.05, city-wide 40 / 500 = 0.08.
    # yellow uses card trips only: 150 / 750 = 0.20 (its all-payment tips and fare are ignored).
    # Zone 264 ("Unknown") has no valid trips, so no row.
    expected = [
        (MAR, "Manhattan", "uber", 30.0, 300.0, 0.10, False),
        (MAR, "Manhattan", "yellow", 150.0, 750.0, 0.20, True),
        (MAR, "Queens", "uber", 10.0, 200.0, 0.05, False),
        (MAR, "all", "uber", 40.0, 500.0, 0.08, False),
        (MAR, "all", "yellow", 150.0, 750.0, 0.20, True),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
