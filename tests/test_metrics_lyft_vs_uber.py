"""lyft_vs_uber: Lyft's share minus Uber's share of a zone's pickups, and its change (Q4)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

NOW, PRIOR = date(2025, 3, 1), date(2024, 3, 1)


def test_lyft_vs_uber(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": NOW, "pu_zone": 161, "mode": "lyft", "trips_all": 300, "trips_valid": 1},
        {"month": NOW, "pu_zone": 161, "mode": "uber", "trips_all": 500},
        {"month": NOW, "pu_zone": 161, "mode": "yellow", "trips_all": 200},
        {"month": PRIOR, "pu_zone": 161, "mode": "lyft", "trips_all": 100},
        {"month": PRIOR, "pu_zone": 161, "mode": "uber", "trips_all": 700},
        {"month": PRIOR, "pu_zone": 161, "mode": "yellow", "trips_all": 200},
        {"month": NOW, "pu_zone": 7, "mode": "lyft", "trips_all": 60},
        {"month": NOW, "pu_zone": 7, "mode": "uber", "trips_all": 40},
        {"month": NOW, "pu_zone": 132, "mode": "yellow", "trips_all": 100},
        {"month": PRIOR, "pu_zone": 132, "mode": "yellow", "trips_all": 50},
        {"month": PRIOR, "pu_zone": 236, "mode": "uber", "trips_all": 50},
    ]))
    table = metrics.run("lyft_vs_uber", to_month="2025-03")
    assert table.column_names == ["pu_zone", "lyft_share", "uber_share", "gap", "gap_prior", "gap_change"]
    expected = [
        # zone 7: 60 / 100 and 40 / 100, gap 0.2; no trips a year earlier
        (7, 0.6, 0.4, 0.2, None, None),
        # zone 132: cabs only, now and then
        (132, 0.0, 0.0, 0.0, 0.0, 0.0),
        # zone 161: 300 / 1,000 and 500 / 1,000 → gap −0.2; then (100 − 700) / 1,000 = −0.6;
        # change −0.2 − (−0.6) = +0.4
        (161, 0.3, 0.5, -0.2, -0.6, 0.4),
        # zone 236 had trips only a year earlier: no row
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
