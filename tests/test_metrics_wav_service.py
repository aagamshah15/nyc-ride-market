"""wav_service: trips in wheelchair-accessible vehicles, by company (Q11, D29)."""

from datetime import date

import pyarrow as pa
import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_wav_service(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "trips_all": 700, "trips_valid": 600, "wav_req": 4, "wav_trips": 50},
        {"mode": "uber", "pu_zone": 132, "trips_all": 450, "trips_valid": 400, "wav_req": 2, "wav_trips": 30},
        {"mode": "lyft", "trips_valid": 0, "wav_req": 0, "wav_trips": 0},
        {"mode": "other_hv", "trips_valid": 100, "wav_req": 5, "wav_trips": 100},
        {"mode": "yellow"},
    ], month=MAR))
    table = metrics.run("wav_service")
    assert table.column_names == ["month", "mode", "trips", "wav_requests", "wav_trips", "wav_share"]
    # uber: 600 + 400 = 1,000 valid trips (not trips_all); 4 + 2 = 6 asked for a WAV;
    # 50 + 30 = 80 ran in one → 80 / 1,000 = 0.08.
    # lyft has no valid trips, so the share is NULL rather than a division by zero.
    # Only uber and lyft report; other_hv and cabs have no rows.
    expected = [(MAR, "lyft", 0, 0, 0, None), (MAR, "uber", 1_000, 6, 80, 0.08)]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
    assert table.schema.field("wav_trips").type == pa.int64()
