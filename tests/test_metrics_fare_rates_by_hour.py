"""fare_rates_by_hour: fare per mile and per minute by hour of week (Q7)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

JAN, FEB, MAR = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)


def test_fare_rates_by_hour(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": FEB, "hour_of_week": 56, "mode": "uber", "fare_base": 100.0, "miles": 40.0, "duration_s": 6_000},
        {"month": MAR, "hour_of_week": 56, "mode": "uber", "fare_base": 200.0, "miles": 60.0, "duration_s": 12_000},
        {"month": MAR, "hour_of_week": 56, "mode": "yellow", "fare_base": 150.0, "miles": 30.0, "duration_s": 9_000},
        {"month": MAR, "hour_of_week": 8, "mode": "lyft", "fare_base": 90.0, "miles": 30.0, "duration_s": 3_600},
        {"month": JAN, "hour_of_week": 56, "mode": "uber", "fare_base": 1_000.0, "miles": 1.0, "duration_s": 60},
    ]))
    table = metrics.run("fare_rates_by_hour", to_month="2025-03", window=2)
    assert table.column_names == ["hour_of_week", "mode", "fare_per_mile", "fare_per_min"]
    # Window Feb–Mar; January is left out.
    #   hour 56 uber: (100 + 200) / (40 + 60) mi = 3.0; 300 / (18,000 s ÷ 60) = 1.0
    #   hour 56 yellow: 150 / 30 = 5.0; 150 / 150 min = 1.0
    #   hour 56 all: 450 / 130 mi; 450 / 450 min = 1.0
    #   hour 8 lyft (and all): 90 / 30 = 3.0; 90 / 60 min = 1.5
    expected = [
        (8, "all", 3.0, 1.5),
        (8, "lyft", 3.0, 1.5),
        (56, "all", 450 / 130, 1.0),
        (56, "uber", 3.0, 1.0),
        (56, "yellow", 5.0, 1.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
