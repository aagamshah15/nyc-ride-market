"""airport_by_hour: airport trips per day by hour of day (Q9)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

JAN, FEB, MAR = date(2025, 1, 1), date(2025, 2, 1), date(2025, 3, 1)


def test_airport_by_hour(data_dir):
    write_agg("agg_airport", agg_table("agg_airport", [
        {"month": FEB, "airport": "JFK", "direction": "from", "hour_of_day": 15, "mode": "uber", "trips_valid": 59},
        {"month": MAR, "airport": "JFK", "direction": "from", "hour_of_day": 15, "mode": "uber", "trips_valid": 59},
        {"month": MAR, "airport": "JFK", "direction": "from", "hour_of_day": 15, "mode": "yellow", "trips_valid": 59},
        {"month": MAR, "airport": "JFK", "direction": "to", "hour_of_day": 7, "mode": "lyft", "trips_valid": 295},
        {"month": JAN, "airport": "JFK", "direction": "from", "hour_of_day": 15, "mode": "uber", "trips_valid": 999},
    ]))
    table = metrics.run("airport_by_hour", to_month="2025-03", window=2)
    assert table.column_names == ["airport", "direction", "hour", "mode", "trips_per_day"]
    # Window Feb–Mar 2025 = 28 + 31 = 59 days; January is outside.
    # JFK from, 3 pm: uber (59 + 59) / 59 = 2.0, yellow 59 / 59 = 1.0. JFK to, 7 am: lyft 295 / 59 = 5.0.
    expected = [
        ("JFK", "from", 15, "uber", 2.0),
        ("JFK", "from", 15, "yellow", 1.0),
        ("JFK", "to", 7, "lyft", 5.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
