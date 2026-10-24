"""shared_match_rate: shared-ride requests matched, by zone and city-wide (Q12)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_shared_match_rate(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "hour_of_week": 8, "shared_req": 6, "shared_match": 1},
        {"mode": "uber", "pu_zone": 161, "hour_of_week": 56, "shared_req": 2, "shared_match": 1},
        {"mode": "uber", "pu_zone": 132, "shared_req": 0, "shared_match": 0},
        {"mode": "lyft", "pu_zone": 161, "shared_req": 10, "shared_match": 5},
        {"mode": "green", "pu_zone": 161},
    ], month=MAR))
    table = metrics.run("shared_match_rate")
    assert table.column_names == ["month", "pu_zone", "mode", "requests", "matched", "match_rate"]
    # uber 161: (1 + 1) / (6 + 2) = 0.25; uber 132: no requests → NULL; city-wide uber 2 / 8.
    # lyft 161 and city-wide: 5 / 10 = 0.5.
    expected = [
        (MAR, 0, "lyft", 10, 5, 0.5),
        (MAR, 0, "uber", 8, 2, 0.25),
        (MAR, 132, "uber", 0, 0, None),
        (MAR, 161, "lyft", 10, 5, 0.5),
        (MAR, 161, "uber", 8, 2, 0.25),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
