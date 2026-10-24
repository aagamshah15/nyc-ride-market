"""pay_per_hour: driver pay per hour with a passenger (Q6)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_pay_per_hour(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "driver_pay": 300.0, "duration_s": 21_600},
        {"mode": "uber", "pu_zone": 132, "driver_pay": 150.0, "duration_s": 14_400},
        {"mode": "lyft", "driver_pay": 280.0, "duration_s": 25_200},
        {"mode": "other_hv", "driver_pay": 1_000.0, "duration_s": 3_600},   # not in ride_hail here
        {"mode": "yellow"},
    ], month=MAR))
    table = metrics.run("pay_per_hour")
    assert table.column_names == ["month", "mode", "driver_pay", "on_trip_hours", "pay_per_hour"]
    # uber: 450 over (21,600 + 14,400) s = 10 h → $45/h; lyft: 280 over 25,200 s = 7 h → $40/h;
    # ride_hail = uber + lyft: 730 / 17 h.
    expected = [
        (MAR, "lyft", 280.0, 7.0, 40.0),
        (MAR, "ride_hail", 730.0, 17.0, 730 / 17),
        (MAR, "uber", 450.0, 10.0, 45.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
