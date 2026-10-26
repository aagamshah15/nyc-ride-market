"""Clean (lane L06): rows in = rows out = the manifest, files per mode, and replacing a month."""

from __future__ import annotations

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline import clean, common, schema_map
from tests.fixtures.raw.raw_trips import raw_table, set_manifest_rows, write_month, write_raw

MARCH = "2025-03"


def part(mode: str, month: str = MARCH):
    return common.clean_partition(mode, month) / "part-0.parquet"


def rows_in_file(mode: str, month: str = MARCH) -> int:
    return pq.ParquetFile(part(mode, month)).metadata.num_rows


def test_rows_out_equal_rows_in_flagged_rows_kept():
    write_month(MARCH,
                fhvhv=[{}, {"hvfhs_license_num": "HV0005"}, {"trip_time": 0}, {"PULocationID": None},
                       {"hvfhs_license_num": "HV0005", "trip_miles": 500.0}],
                yellow=[{}, {"fare_amount": 0.0}, {"DOLocationID": 264}, {"DOLocationID": 265}],
                green=[{}, {}, {"trip_distance": 0.0}, {}])
    counts = clean.clean_month(MARCH)
    # fhvhv 5 rows = uber 3 + lyft 2; yellow 4; green 4
    assert {mode: c["rows"] for mode, c in counts.items()} == {"uber": 3, "lyft": 2, "yellow": 4, "green": 4}
    assert {mode: rows_in_file(mode) for mode in counts} == {"uber": 3, "lyft": 2, "yellow": 4, "green": 4}
    # uber: trip_time 0 (f_time) and a NULL pickup zone (f_zone); lyft: 500 miles (f_miles)
    assert (counts["uber"]["valid"], counts["uber"]["f_time"], counts["uber"]["f_zone"]) == (1, 1, 1)
    assert (counts["lyft"]["valid"], counts["lyft"]["f_miles"]) == (1, 1)
    # yellow: a $0 fare (f_fare) and a drop-off in zone 264 (f_zone); zone 265 is valid (D26)
    assert (counts["yellow"]["valid"], counts["yellow"]["f_fare"], counts["yellow"]["f_zone"]) == (2, 1, 1)
    assert (counts["green"]["valid"], counts["green"]["f_miles"]) == (3, 1)
    # modes without rows get no file
    assert not part("other_hv").exists()


def test_rows_in_must_match_the_manifest():
    write_month(MARCH, yellow=[{}, {}])
    set_manifest_rows("yellow", MARCH, 3)
    with pytest.raises(clean.CleanError, match=r"raw/yellow/2025-03\.parquet: 2 rows, but manifest\.json says 3"):
        clean.clean_month(MARCH)
    assert not part("uber").exists()


def test_missing_raw_file_or_manifest_entry_stops_the_run():
    write_month(MARCH)
    common.raw_path("green", MARCH).unlink()
    with pytest.raises(clean.CleanError, match=r"raw/green/2025-03\.parquet: raw file missing"):
        clean.clean_month(MARCH)
    common.manifest_path().unlink()
    write_raw("green", MARCH)            # writes a manifest holding green only
    with pytest.raises(clean.CleanError, match=r"raw/fhvhv/2025-03\.parquet: no row count"):
        clean.clean_month(MARCH)


def test_missing_zone_lookup_stops_the_run():
    write_month(MARCH)
    (common.ref_dir() / "taxi_zone_lookup.csv").unlink()
    with pytest.raises(clean.CleanError, match="zone lookup missing; run make ref"):
        clean.clean_month(MARCH)


def test_rerun_replaces_the_month_and_drops_modes_now_empty():
    write_month(MARCH, fhvhv=[{}, {"hvfhs_license_num": "HV0004"}])
    write_month("2025-04")
    clean.clean_month(MARCH)
    clean.clean_month("2025-04")
    assert rows_in_file("other_hv") == 1

    write_month(MARCH, fhvhv=[{}, {}, {}])
    clean.clean_month(MARCH)
    assert rows_in_file("uber") == 3
    assert not part("other_hv").exists()
    assert not part("other_hv").parent.exists()
    # other months are untouched; no staging folder is left behind
    assert rows_in_file("uber", "2025-04") == 1
    assert [p.name for p in common.clean_dir().iterdir() if p.name.startswith(".")] == []


def test_a_failed_run_leaves_the_previous_files():
    write_month(MARCH, yellow=[{}, {}])
    clean.clean_month(MARCH)
    before = {mode: rows_in_file(mode) for mode in ("uber", "yellow", "green")}

    # fhvhv and yellow clean fine this time; green then fails on an unmapped column
    write_month(MARCH, fhvhv=[{}, {}, {}], yellow=[{}])
    write_raw("green", MARCH, table=raw_table("green", MARCH).append_column("new_fee", pa.array([0.5])))
    with pytest.raises(schema_map.UnmappedColumnError):
        clean.clean_month(MARCH)
    assert {mode: rows_in_file(mode) for mode in before} == before == {"uber": 1, "yellow": 2, "green": 1}
    assert [p.name for p in common.clean_dir().iterdir() if p.name.startswith(".")] == []


def test_cli_cleans_the_month(capsys):
    write_month(MARCH)
    clean.main(["--month", MARCH])
    out = capsys.readouterr().out
    assert "raw/fhvhv/2025-03.parquet: 1 rows in, 1 out" in out
    assert all(part(mode).exists() for mode in ("uber", "yellow", "green"))


def test_cli_reports_errors_and_exits_1(capsys):
    with pytest.raises(SystemExit) as stop:
        clean.main(["--month", MARCH])
    assert stop.value.code == 1
    assert "raw/fhvhv/2025-03.parquet: raw file missing" in capsys.readouterr().err
