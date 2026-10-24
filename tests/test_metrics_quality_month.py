"""quality_month: rows, valid rows and flag counts by month and mode (methods page)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_quality_month(data_dir):
    write_agg("agg_quality_month", agg_table("agg_quality_month", [
        {"mode": "uber", "rows": 1_000, "valid_rows": 985, "f_time": 5, "f_miles": 6, "f_fare": 2,
         "f_zone": 3, "f_wait": 1},
        {"mode": "yellow", "rows": 200, "valid_rows": 150, "f_time": 10, "f_miles": 30, "f_fare": 5,
         "f_zone": 8, "f_wait": None},
    ], month=MAR))
    table = metrics.run("quality_month")
    assert table.column_names == ["month", "mode", "rows", "valid_rows", "valid_share", "f_time", "f_miles",
                                  "f_fare", "f_zone", "f_wait"]
    # uber 985 / 1,000 = 0.985; yellow 150 / 200 = 0.75, and f_wait stays NULL for cabs.
    expected = [
        (MAR, "uber", 1_000, 985, 0.985, 5, 6, 2, 3, 1),
        (MAR, "yellow", 200, 150, 0.75, 10, 30, 5, 8, None),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
