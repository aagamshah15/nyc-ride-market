"""trips_per_hour_worked: TLC-reported trips per vehicle-hour on the road (Q15)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_trips_per_hour_worked(data_dir):
    write_agg("ref_indicators", agg_table("ref_indicators", [
        {"License Class": "FHV - High Volume", "Trips Per Day": 600_000.0, "Vehicles Per Day": 50_000.0,
         "Avg Hours Per Day Per Vehicle": 8.0, "Unique Drivers": 70_000.0},
        {"License Class": "Yellow", "Trips Per Day": 120_000.0, "Vehicles Per Day": 7_500.0,
         "Avg Hours Per Day Per Vehicle": 10.0, "Unique Drivers": 9_000.0},
        {"License Class": "Green", "Trips Per Day": 1_500.0, "Vehicles Per Day": 0.0,
         "Avg Hours Per Day Per Vehicle": 5.0, "Unique Drivers": 400.0},
    ], month=MAR))
    table = metrics.run("trips_per_hour_worked")
    assert table.column_names == ["month", "license_class", "trips_per_day", "vehicles_per_day",
                                  "hours_per_day_per_vehicle", "trips_per_hour_worked", "unique_drivers"]
    # FHV: 600,000 / (50,000 × 8) = 1.5; Yellow: 120,000 / (7,500 × 10) = 1.6; Green: no vehicles → NULL.
    expected = [
        (MAR, "FHV - High Volume", 600_000.0, 50_000.0, 8.0, 1.5, 70_000.0),
        (MAR, "Green", 1_500.0, 0.0, 5.0, None, 400.0),
        (MAR, "Yellow", 120_000.0, 7_500.0, 10.0, 1.6, 9_000.0),
    ]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
    assert table.schema.metadata[b"source"] == b"TLC-reported"
