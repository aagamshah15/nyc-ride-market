"""fare_dist: fare-per-mile and fare-per-minute percentiles by zone (Q3, Q7)."""

from datetime import date

from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_fare_dist(data_dir):
    write_agg("agg_zone_month_dist", agg_table("agg_zone_month_dist", [
        {"pu_zone": 161, "mode": "yellow", "n": 400, "fpm_p10": 2.5, "fpm_p50": 4.0, "fpm_p90": 7.5, "fpmin_p50": 1.2},
        {"pu_zone": 0, "mode": "all", "n": 9_000, "fpm_p10": 2.0, "fpm_p50": 3.5, "fpm_p90": 6.0, "fpmin_p50": 1.1,
         "wait_p50": None, "wait_p90": None},
        {"pu_zone": 0, "mode": "uber", "n": 5_000, "fpm_p10": 1.9, "fpm_p50": 3.2, "fpm_p90": 5.8, "fpmin_p50": 1.0},
    ], month=MAR))
    table = metrics.run("fare_dist")
    assert table.column_names == ["month", "pu_zone", "mode", "n", "fpm_p10", "fpm_p50", "fpm_p90", "fpmin_p50"]
    # Percentiles can't be combined, so the rows pass through as stored, city-wide rows
    # (pu_zone 0, including the "all" group) first.
    assert table.to_pylist() == [
        {"month": MAR, "pu_zone": 0, "mode": "all", "n": 9_000,
         "fpm_p10": 2.0, "fpm_p50": 3.5, "fpm_p90": 6.0, "fpmin_p50": 1.1},
        {"month": MAR, "pu_zone": 0, "mode": "uber", "n": 5_000,
         "fpm_p10": 1.9, "fpm_p50": 3.2, "fpm_p90": 5.8, "fpmin_p50": 1.0},
        {"month": MAR, "pu_zone": 161, "mode": "yellow", "n": 400,
         "fpm_p10": 2.5, "fpm_p50": 4.0, "fpm_p90": 7.5, "fpmin_p50": 1.2},
    ]
