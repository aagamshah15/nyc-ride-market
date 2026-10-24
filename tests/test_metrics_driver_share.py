"""driver_share: the share of the base fare paid to drivers, by company (Q3, Q5, Q6)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_driver_share(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "driver_pay": 600.0, "fare_base": 800.0},
        {"mode": "uber", "pu_zone": 132, "driver_pay": 120.0, "fare_base": 200.0},
        {"mode": "lyft", "driver_pay": 330.0, "fare_base": 600.0},
        {"mode": "other_hv", "driver_pay": 90.0, "fare_base": 100.0},   # not in ride_hail here
        {"mode": "yellow"},
    ], month=MAR))
    table = metrics.run("driver_share")
    assert table.column_names == ["month", "mode", "driver_pay", "fare_base", "driver_share", "platform_share"]
    # uber (600 + 120) / (800 + 200) = 0.72; lyft 330 / 600 = 0.55;
    # ride_hail = uber + lyft only: 1,050 / 1,600 = 0.65625. platform_share = 1 − driver_share.
    expected = [
        (MAR, "lyft", 330.0, 600.0, 0.55, 0.45),
        (MAR, "ride_hail", 1_050.0, 1_600.0, 0.65625, 0.34375),
        (MAR, "uber", 720.0, 1_000.0, 0.72, 0.28),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
