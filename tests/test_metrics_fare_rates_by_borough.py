"""fare_rates_by_borough: fare per mile and per minute by pickup borough (Q7)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

FEB, MAR = date(2025, 2, 1), date(2025, 3, 1)


def write_zone_lookup(data_dir):
    (data_dir / "ref").mkdir()
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text(
        '"LocationID","Borough","Zone","service_zone"\n'
        '7,"Queens","Astoria","Boro Zone"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n'
        '236,"Manhattan","Upper East Side North","Yellow Zone"\n'
        '264,"Unknown","N/A","N/A"\n')


def test_fare_rates_by_borough(data_dir):
    write_zone_lookup(data_dir)
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": MAR, "pu_zone": 161, "mode": "uber", "fare_base": 100.0, "miles": 40.0, "duration_s": 3_000},
        {"month": MAR, "pu_zone": 236, "mode": "uber", "fare_base": 50.0, "miles": 10.0, "duration_s": 1_500},
        {"month": MAR, "pu_zone": 161, "mode": "yellow", "fare_base": 120.0, "miles": 30.0, "duration_s": 3_600},
        {"month": MAR, "pu_zone": 7, "mode": "uber", "fare_base": 60.0, "miles": 30.0, "duration_s": 3_600},
        {"month": MAR, "pu_zone": 264, "mode": "uber", "trips_valid": 0, "fare_base": None, "miles": None,
         "duration_s": None},
        {"month": FEB, "pu_zone": 161, "mode": "uber", "fare_base": 999.0, "miles": 1.0, "duration_s": 60},
    ]))
    table = metrics.run("fare_rates_by_borough", to_month="2025-03", window=1)
    assert table.column_names == ["pu_borough", "mode", "fare_per_mile", "fare_per_min"]
    # Manhattan uber: (100 + 50) / (40 + 10) mi = 3.0; 150 / (4,500 s ÷ 60 = 75 min) = 2.0
    # Manhattan yellow: 120 / 30 = 4.0; 120 / 60 min = 2.0
    # Manhattan all: 270 / 80 mi; 270 / 135 min = 2.0
    # Queens uber (and all): 60 / 30 = 2.0; 60 / 60 min = 1.0
    # Zone 264 has no valid trips, so "Unknown" has no row; February is outside the window.
    expected = [
        ("Manhattan", "all", 270 / 80, 2.0),
        ("Manhattan", "uber", 3.0, 2.0),
        ("Manhattan", "yellow", 4.0, 2.0),
        ("Queens", "all", 2.0, 1.0),
        ("Queens", "uber", 2.0, 1.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
