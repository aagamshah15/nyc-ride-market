"""wav_match_rate: wheelchair-accessible requests matched, by company (Q11)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

MAR = date(2025, 3, 1)


def test_wav_match_rate(data_dir):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"mode": "uber", "pu_zone": 161, "wav_req": 10, "wav_match": 9},
        {"mode": "uber", "pu_zone": 132, "wav_req": 10, "wav_match": 7},
        {"mode": "lyft", "wav_req": 0, "wav_match": 0},
        {"mode": "other_hv", "wav_req": 5, "wav_match": 5},
        {"mode": "yellow"},
    ], month=MAR))
    table = metrics.run("wav_match_rate")
    assert table.column_names == ["month", "mode", "requests", "matched", "match_rate"]
    # uber (9 + 7) / (10 + 10) = 0.8; lyft had no requests, so no rate. Only uber and lyft report.
    expected = [(MAR, "lyft", 0, 0, None), (MAR, "uber", 20, 16, 0.8)]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, row))) for row in expected]
