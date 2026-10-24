"""airport_share: each mode's share of trips to and from each airport (Q9)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_airport_share(data_dir):
    write_agg("agg_airport", agg_table("agg_airport", [
        {"airport": "JFK", "direction": "from", "mode": "uber", "hour_of_day": 7, "trips_valid": 155},
        {"airport": "JFK", "direction": "from", "mode": "uber", "hour_of_day": 15, "trips_valid": 155},
        {"airport": "JFK", "direction": "from", "mode": "yellow", "trips_valid": 620},
        {"airport": "JFK", "direction": "to", "mode": "uber", "trips_valid": 62},
        {"airport": "LGA", "direction": "from", "mode": "lyft", "trips_valid": 31},
    ], month=MAR))
    table = metrics.run("airport_share")
    assert table.column_names == ["month", "airport", "direction", "mode", "trips", "trips_per_day", "share"]
    # March has 31 days. JFK from: uber 155 + 155 = 310 (10/day), yellow 620 (20/day), of 930
    # → 1/3 and 2/3. JFK to: uber 62 (2/day), all of it. LGA from: lyft 31 (1/day), all of it.
    expected = [
        (MAR, "JFK", "from", "uber", 310, 10.0, 1 / 3),
        (MAR, "JFK", "from", "yellow", 620, 20.0, 2 / 3),
        (MAR, "JFK", "to", "uber", 62, 2.0, 1.0),
        (MAR, "LGA", "from", "lyft", 31, 1.0, 1.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
