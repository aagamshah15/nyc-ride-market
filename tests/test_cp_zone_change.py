"""cp_zone_change: pickups per day by zone in 2025 against 2024, all modes (Q2)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics


@pytest.fixture
def zone_hour(data_dir):
    def cell(month, zone, trips, mode="uber", hour=56):
        return {"month": month, "pu_zone": zone, "mode": mode, "hour_of_week": hour,
                "trips_all": trips, "trips_valid": 1}

    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        # zone 161, Feb + Mar 2024: 1,000 + 900 + 1,000 + 3,100 = 6,000 over 29 + 31 = 60 days → 100
        cell(date(2024, 2, 1), 161, 1000, hour=8), cell(date(2024, 2, 1), 161, 900),
        cell(date(2024, 2, 1), 161, 1000, mode="yellow"), cell(date(2024, 3, 1), 161, 3100),
        # zone 161, Feb + Mar 2025: 2,240 + 2,480 = 4,720 over 28 + 31 = 59 days → 80
        cell(date(2025, 2, 1), 161, 2240), cell(date(2025, 3, 1), 161, 2480, mode="yellow"),
        # zone 132: March 2024 only → 600 ÷ 60 = 10 a day, then 0
        cell(date(2024, 3, 1), 132, 600),
        # zone 236: March 2025 only → 0, then 590 ÷ 59 = 10 a day
        cell(date(2025, 3, 1), 236, 590),
        # left out: April 2025 has no April 2024; 2023 isn't a study year
        cell(date(2025, 4, 1), 161, 9999), cell(date(2023, 3, 1), 161, 5555),
    ]))


EXPECTED = [   # pu_zone, trips_per_day_2024, trips_per_day_2025, change
    (132, 10.0, 0.0, -1.0),
    (161, 100.0, 80.0, -0.2),        # 80 ÷ 100 − 1
    (236, 0.0, 10.0, None),          # no 2024 pickups: change undefined
]


def test_cp_zone_change(zone_hour):
    table = metrics.run("cp_zone_change")
    assert table.column_names == ["pu_zone", "trips_per_day_2024", "trips_per_day_2025", "change"]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, r))) for r in EXPECTED]


def test_no_matched_months(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [{"month": date(2025, 3, 1)}]))
    assert metrics.run("cp_zone_change").num_rows == 0
