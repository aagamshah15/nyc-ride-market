"""fare_rates: city-wide fare per mile, per minute and rider total per trip (Q3, Q7)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_fare_rates(data_dir):
    sums = {  # fare_base, miles, duration_s, rider_total_ex_tip, trips_valid
        "uber": (300.0, 100.0, 18_000, 400.0, 20),
        "lyft": (200.0, 80.0, 12_000, 250.0, 10),
        "other_hv": (100.0, 50.0, 6_000, 150.0, 10),
        "yellow": (400.0, 100.0, 30_000, 500.0, 25),
        "green": (100.0, 50.0, 6_000, 125.0, 5),
    }
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": mode, "fare_base": f, "miles": mi, "duration_s": s, "rider_total_ex_tip": r, "trips_valid": n}
        for mode, (f, mi, s, r, n) in sums.items()
    ], month=MAR))
    table = metrics.run("fare_rates")
    assert table.column_names == ["month", "mode", "fare_per_mile", "fare_per_min", "rider_total_per_trip"]
    # fare ÷ miles, fare ÷ (seconds ÷ 60), rider total ÷ valid trips; groups are sums of sums:
    #   ride_hail 600 / 230 mi, 600 / 600 min, 800 / 40 trips
    #   taxi 500 / 150 mi, 500 / 600 min, 625 / 30 trips
    #   all 1,100 / 380 mi, 1,100 / 1,200 min, 1,425 / 70 trips
    expected = [
        (MAR, "all", 1_100 / 380, 1_100 / 1_200, 1_425 / 70),
        (MAR, "green", 2.0, 1.0, 25.0),
        (MAR, "lyft", 2.5, 1.0, 25.0),
        (MAR, "other_hv", 2.0, 1.0, 15.0),
        (MAR, "ride_hail", 600 / 230, 1.0, 20.0),
        (MAR, "taxi", 500 / 150, 500 / 600, 625 / 30),
        (MAR, "uber", 3.0, 1.0, 20.0),
        (MAR, "yellow", 4.0, 0.8, 20.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
