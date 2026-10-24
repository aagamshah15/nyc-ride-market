"""price_volatility: the spread of fare per mile, p90 ÷ p10 (Q7)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_price_volatility(data_dir):
    write_agg("agg_zone_month_dist", agg_table("agg_zone_month_dist", [
        {"pu_zone": 161, "mode": "uber", "n": 3_000, "fpm_p10": 2.0, "fpm_p90": 7.0},
        {"pu_zone": 0, "mode": "ride_hail", "n": 50_000, "fpm_p10": 1.6, "fpm_p90": 4.0},
        {"pu_zone": 132, "mode": "green", "n": 120, "fpm_p10": 0.0, "fpm_p90": 3.0},
    ], month=MAR))
    table = metrics.run("price_volatility")
    assert table.column_names == ["month", "pu_zone", "mode", "n", "volatility"]
    # 4.0 / 1.6 = 2.5; 3.0 / 0 has no ratio (NULL); 7.0 / 2.0 = 3.5
    expected = [
        (MAR, 0, "ride_hail", 50_000, 2.5),
        (MAR, 132, "green", 120, None),
        (MAR, 161, "uber", 3_000, 3.5),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
