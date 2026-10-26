"""Month-scoped rewrite of the aggregate tables (lane L07): other months untouched, re-runs
identical, ISO weeks across month ends, and the errors that stop a run."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from datetime import date, datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline import aggregate, common
from tests.factories import agg_table, clean_trips, write_agg, write_clean

MAR, APR = date(2025, 3, 1), date(2025, 4, 1)

# ISO week 2025-W14 runs Monday 31 Mar to Sunday 6 Apr, across the March and April files.
MARCH = clean_trips([
    {"pickup_ts": datetime(2025, 3, 30, 9, 0)},                       # Sun → W13
    {"pickup_ts": datetime(2025, 3, 31, 9, 0)},                       # Mon → W14
    {"pickup_ts": datetime(2025, 3, 31, 18, 0), "mode": "yellow"},    # Mon → W14
])
APRIL = clean_trips([
    {"pickup_ts": datetime(2025, 3, 31, 23, 30), "month": APR},       # April file, picked up the day before → W14
    {"pickup_ts": datetime(2025, 4, 1, 9, 0)},                        # Tue → W14
    {"pickup_ts": datetime(2025, 4, 6, 22, 0)},                       # Sun → W14
    {"pickup_ts": datetime(2025, 4, 7, 9, 0), "mode": "lyft"},        # Mon → W15
])


def month_rows(table: str, month: date) -> list[dict]:
    return [r for r in pq.read_table(common.agg_path(table)).to_pylist() if r["month"] == month]


def file_bytes() -> dict[str, bytes]:
    return {table: common.agg_path(table).read_bytes() for table in aggregate.TABLES}


def drop_clean(month: str) -> None:
    for folder in common.clean_dir().glob(f"mode=*/month={month}"):
        shutil.rmtree(folder)


def week_trips(zone_list: str = "core") -> dict[tuple, int]:
    table = pq.read_table(common.agg_path("agg_week_cbd")).to_pylist()
    return {(r["month"], r["iso_year"], r["iso_week"], r["mode"]): r["trips_all"]
            for r in table if r["zone_list"] == zone_list}


def test_iso_week_spanning_two_months():
    write_clean(MARCH)
    write_clean(APRIL)
    aggregate.aggregate_month("2025-03")
    aggregate.aggregate_month("2025-04")
    # every trip touches the zone by default, so each count is its treated row (core list shown)
    assert week_trips() == {
        (MAR, 2025, 13, "uber"): 1,
        (MAR, 2025, 14, "uber"): 1,
        (MAR, 2025, 14, "yellow"): 1,
        (APR, 2025, 14, "uber"): 3,     # incl. the 31 Mar 23:30 pickup in the April file (D7)
        (APR, 2025, 15, "lyft"): 1,
    }
    # summing over month gives the whole week: uber W14 = 1 (March file) + 3 (April file)
    whole = sum(n for (m, y, w, mode), n in week_trips().items() if (y, w, mode) == (2025, 14, "uber"))
    assert whole == 4


def test_iso_year_differs_from_calendar_year():
    write_clean(clean_trips([
        {"pickup_ts": datetime(2024, 12, 29, 12, 0)},   # Sun → 2024-W52
        {"pickup_ts": datetime(2024, 12, 30, 12, 0)},   # Mon → 2025-W01
    ]))
    write_clean(clean_trips([{"pickup_ts": datetime(2025, 1, 2, 12, 0)}]))   # Thu → 2025-W01
    aggregate.aggregate_month("2024-12")
    aggregate.aggregate_month("2025-01")
    assert week_trips() == {
        (date(2024, 12, 1), 2024, 52, "uber"): 1,
        (date(2024, 12, 1), 2025, 1, "uber"): 1,
        (date(2025, 1, 1), 2025, 1, "uber"): 1,
    }


def test_rewriting_one_month_leaves_the_other_identical():
    write_clean(MARCH)
    write_clean(APRIL)
    aggregate.aggregate_month("2025-03")
    march = {table: month_rows(table, MAR) for table in aggregate.TABLES}

    aggregate.aggregate_month("2025-04")
    assert {table: month_rows(table, MAR) for table in aggregate.TABLES} == march
    assert month_rows("agg_quality_month", APR) != []

    # April changes upstream (TLC revises it): one uber trip left
    drop_clean("2025-04")
    write_clean(clean_trips([{"pickup_ts": datetime(2025, 4, 2, 9, 0)}]))
    aggregate.aggregate_month("2025-04")
    assert {table: month_rows(table, MAR) for table in aggregate.TABLES} == march
    assert [(r["mode"], r["rows"]) for r in month_rows("agg_quality_month", APR)] == [("uber", 1)]
    assert {(r["mode"], r["trips_all"]) for r in month_rows("agg_zone_hour", APR)} == {("uber", 1)}
    assert {(r["iso_week"], r["trips_all"]) for r in month_rows("agg_week_cbd", APR)} == {(14, 1)}


def test_rerun_writes_identical_files():
    write_clean(MARCH)
    write_clean(APRIL)
    aggregate.aggregate_month("2025-03")
    aggregate.aggregate_month("2025-04")
    first = file_bytes()

    aggregate.aggregate_month("2025-04")          # same month again
    assert file_bytes() == first
    aggregate.aggregate_month("2025-03")          # an earlier month again: April's rows stay put
    assert file_bytes() == first
    assert not list(common.agg_dir().glob("*.tmp"))


def test_sums_are_exact_whatever_the_row_order():
    # ten tips of 0.10: a DOUBLE running sum gives 0.9999999999999999; DECIMAL sums give 1.0
    write_clean(clean_trips([{"tips": 0.1} for _ in range(10)]))
    aggregate.aggregate_month("2025-03")
    assert month_rows("agg_zone_hour", MAR)[0]["tips"] == 1.0


def test_missing_clean_month_stops_before_writing():
    write_clean(MARCH)
    aggregate.aggregate_month("2025-03")
    before = file_bytes()
    with pytest.raises(aggregate.AggregateError, match="2025-04: no clean files"):
        aggregate.aggregate_month("2025-04")
    assert file_bytes() == before


def test_clean_rows_for_another_month_stop_the_run():
    write_clean(APRIL.slice(1, 1))                     # a 2025-04 file …
    common.clean_partition("uber", "2025-04").rename(common.clean_partition("uber", "2025-05"))  # … filed under May
    with pytest.raises(aggregate.AggregateError, match="rows for other months"):
        aggregate.aggregate_month("2025-05")
    assert not common.agg_dir().exists()


def test_changed_table_layout_stops_the_run():
    stale = agg_table("agg_zone_hour").drop_columns(["wav_match"])   # an older layout
    path = write_agg("agg_zone_hour", stale)
    before = path.read_bytes()
    write_clean(MARCH)
    with pytest.raises(aggregate.AggregateError, match="agg_zone_hour: .* back-fill"):
        aggregate.aggregate_month("2025-03")
    assert path.read_bytes() == before


def test_clean_files_missing_a_column_stop_the_run_before_any_write():
    write_clean(MARCH)
    aggregate.aggregate_month("2025-03")
    before = file_bytes()
    # March cleaned again by an older clean.py, before vendor_id (D25): every query runs before any
    # file is written, so agg_zone_hour and the rest stay as they were
    drop_clean("2025-03")
    write_clean(MARCH.drop_columns(["vendor_id"]))
    with pytest.raises(aggregate.AggregateError, match=r"agg_vendor_month: .*vendor_id(.|\n)*make clean MONTH=2025-03"):
        aggregate.aggregate_month("2025-03")
    assert file_bytes() == before


def test_existing_rows_from_the_factory_are_kept():
    # a table written by another month's run (here: the factory's February row) survives
    feb = agg_table("agg_fees_month", [{"month": date(2025, 2, 1), "mode": "lyft"}])
    write_agg("agg_fees_month", feb)
    write_clean(MARCH)
    aggregate.aggregate_month("2025-03")
    table = pq.read_table(common.agg_path("agg_fees_month"))
    assert table.slice(0, 1).equals(feb)                       # sorted by month, February first
    assert [r["month"] for r in table.to_pylist()] == [date(2025, 2, 1), MAR, MAR]


def test_cli(data_dir):
    write_clean(MARCH)
    env = {**os.environ, "NYC_DATA_DIR": str(data_dir)}
    run = subprocess.run([sys.executable, "-m", "pipeline.aggregate", "--month", "2025-03"],
                         cwd=common.REPO_ROOT, env=env, capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    # hours of week: uber Sun 09:00 → 9, uber Mon 09:00 → 33, yellow Mon 18:00 → 42
    assert "agg_zone_hour: 3 rows for 2025-03" in run.stdout
    assert all(common.agg_path(table).exists() for table in aggregate.TABLES)

    missing = subprocess.run([sys.executable, "-m", "pipeline.aggregate", "--month", "2025-04"],
                             cwd=common.REPO_ROOT, env=env, capture_output=True, text=True)
    assert missing.returncode == 1
    assert "make clean MONTH=2025-04" in missing.stderr


def test_cli_rejects_bad_month():
    run = subprocess.run([sys.executable, "-m", "pipeline.aggregate", "--month", "2025-3"],
                         cwd=common.REPO_ROOT, capture_output=True, text=True)
    assert run.returncode == 2
    assert "YYYY-MM" in run.stderr
