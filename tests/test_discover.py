"""Schema discovery, the report and the SPEC §8 schema check (lane L03).

Footers come from tiny Parquet files written to the temp data folder, so nothing touches
the network: discover reads a local raw file whenever one exists.
"""

from datetime import date

import duckdb
import pytest

from pipeline import common, discover
from pipeline.discover import FileSchema
from pipeline.schema_map import load_schema_map

FHVHV_2024 = [
    ("hvfhs_license_num", "VARCHAR"), ("dispatching_base_num", "VARCHAR"), ("originating_base_num", "VARCHAR"),
    ("request_datetime", "TIMESTAMP"), ("on_scene_datetime", "TIMESTAMP"), ("pickup_datetime", "TIMESTAMP"),
    ("dropoff_datetime", "TIMESTAMP"), ("PULocationID", "INTEGER"), ("DOLocationID", "INTEGER"),
    ("trip_miles", "DOUBLE"), ("trip_time", "BIGINT"), ("base_passenger_fare", "DOUBLE"), ("tolls", "DOUBLE"),
    ("bcf", "DOUBLE"), ("sales_tax", "DOUBLE"), ("congestion_surcharge", "DOUBLE"), ("airport_fee", "DOUBLE"),
    ("tips", "DOUBLE"), ("driver_pay", "DOUBLE"), ("shared_request_flag", "VARCHAR"),
    ("shared_match_flag", "VARCHAR"), ("access_a_ride_flag", "VARCHAR"), ("wav_request_flag", "VARCHAR"),
    ("wav_match_flag", "VARCHAR"),
]
YELLOW_2024 = [
    ("VendorID", "INTEGER"), ("tpep_pickup_datetime", "TIMESTAMP"), ("tpep_dropoff_datetime", "TIMESTAMP"),
    ("passenger_count", "BIGINT"), ("trip_distance", "DOUBLE"), ("RatecodeID", "BIGINT"),
    ("store_and_fwd_flag", "VARCHAR"), ("PULocationID", "INTEGER"), ("DOLocationID", "INTEGER"),
    ("payment_type", "BIGINT"), ("fare_amount", "DOUBLE"), ("extra", "DOUBLE"), ("mta_tax", "DOUBLE"),
    ("tip_amount", "DOUBLE"), ("tolls_amount", "DOUBLE"), ("improvement_surcharge", "DOUBLE"),
    ("total_amount", "DOUBLE"), ("congestion_surcharge", "DOUBLE"), ("Airport_fee", "DOUBLE"),
]
GREEN_2024 = [
    ("VendorID", "INTEGER"), ("lpep_pickup_datetime", "TIMESTAMP"), ("lpep_dropoff_datetime", "TIMESTAMP"),
    ("store_and_fwd_flag", "VARCHAR"), ("RatecodeID", "BIGINT"), ("PULocationID", "INTEGER"),
    ("DOLocationID", "INTEGER"), ("passenger_count", "BIGINT"), ("trip_distance", "DOUBLE"),
    ("fare_amount", "DOUBLE"), ("extra", "DOUBLE"), ("mta_tax", "DOUBLE"), ("tip_amount", "DOUBLE"),
    ("tolls_amount", "DOUBLE"), ("ehail_fee", "DOUBLE"), ("improvement_surcharge", "DOUBLE"),
    ("total_amount", "DOUBLE"), ("payment_type", "BIGINT"), ("trip_type", "BIGINT"),
    ("congestion_surcharge", "DOUBLE"),
]
CBD = [("cbd_congestion_fee", "DOUBLE")]
REAL = {
    ("fhvhv", "2024-12"): FHVHV_2024, ("fhvhv", "2025-01"): FHVHV_2024 + CBD,
    ("yellow", "2024-12"): YELLOW_2024, ("yellow", "2025-01"): YELLOW_2024 + CBD,
    ("green", "2024-12"): GREEN_2024, ("green", "2025-01"): GREEN_2024 + CBD,
}


def write_raw(dataset, month, columns, rows=3):
    """A ``rows``-row raw file with exactly ``columns`` (name, DuckDB type), all NULL."""
    path = common.raw_path(dataset, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    select = ", ".join(f'NULL::{type_} AS "{name}"' for name, type_ in columns)
    duckdb.execute(f"COPY (SELECT {select} FROM range({rows})) TO {common.sql_literal(str(path))} (FORMAT parquet)")
    return path


def write_real(months=("2024-12", "2025-01")):
    for (dataset, month), columns in REAL.items():
        if month in months:
            write_raw(dataset, month, columns)


@pytest.fixture
def no_sleep():
    slept = []
    return slept, slept.append


# --- reading footers -------------------------------------------------------------

def test_read_footer_uses_local_file():
    write_raw("yellow", "2025-01", YELLOW_2024 + CBD, rows=5)
    schema = discover.read_footer(common.connect(), "yellow", "2025-01")
    assert (schema.source, schema.rows, schema.error) == ("local", 5, None)
    assert schema.columns == YELLOW_2024 + CBD          # Airport_fee keeps its spelling
    assert schema.name == "yellow_tripdata_2025-01.parquet"


def test_trip_url_follows_sources_yaml():
    assert discover.trip_url("fhvhv", "2026-08") == \
        "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2026-08.parquet"


def test_unreadable_remote_file_is_an_error_not_a_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(discover, "trip_url", lambda d, m: str(tmp_path / f"{d}_{m}.parquet"))
    schema = discover.read_footer(common.connect(), "green", "2031-01")
    assert schema.source == "remote" and schema.error and schema.columns == []


def _http_error(status, body):
    exc = duckdb.HTTPException(f"HTTP Error: HTTP GET error (HTTP {status})")
    exc.status_code, exc.body = status, body
    return exc


BLOCKED = _http_error(403, "<H1>403 ERROR</H1> Request blocked. We can't connect to the server")
NOT_FOUND = _http_error(403, "<Error><Code>AccessDenied</Code></Error>")


def _fake_describe(monkeypatch, outcomes):
    """``describe`` raising or returning each of ``outcomes`` in turn."""
    def fake(con, location):
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome
    monkeypatch.setattr(discover, "describe", fake)
    monkeypatch.setattr(discover, "trip_url", lambda d, m: f"/nowhere/{d}_{m}.parquet")


def test_rate_block_is_waited_out(monkeypatch, no_sleep):
    slept, sleep = no_sleep
    _fake_describe(monkeypatch, [BLOCKED, BLOCKED, ([("a", "VARCHAR")], 7)])
    schema = discover.read_footer(common.connect(), "fhvhv", "2025-01", sleep=sleep)
    assert schema.error is None and schema.rows == 7
    assert slept == list(discover.BLOCK_WAITS_S[:2])


def test_missing_file_is_not_retried(monkeypatch, no_sleep):
    slept, sleep = no_sleep
    _fake_describe(monkeypatch, [NOT_FOUND])
    schema = discover.read_footer(common.connect(), "fhvhv", "2031-01", sleep=sleep)
    assert slept == [] and "no such file" in schema.error


def test_block_budget_is_shared_across_files(monkeypatch, no_sleep):
    # A block that never lifts costs one round of waits, not one per file.
    slept, sleep = no_sleep
    _fake_describe(monkeypatch, [BLOCKED] * (len(discover.BLOCK_WAITS_S) + 3))
    files = discover.discover(["fhvhv", "yellow", "green"], ["2025-01"], pause=0.5, sleep=sleep)
    assert all("blocking" in f.error for f in files)
    assert [s for s in slept if s != 0.5] == list(discover.BLOCK_WAITS_S)


def test_remote_reads_are_paced_and_local_reads_are_not(monkeypatch, no_sleep):
    slept, sleep = no_sleep
    write_raw("yellow", "2025-01", YELLOW_2024 + CBD)
    _fake_describe(monkeypatch, [([("a", "VARCHAR")], 1)] * 3)
    files = discover.discover(list(common.DATASETS), ["2025-01"], pause=0.5, sleep=sleep)
    assert [f.source for f in files] == ["remote", "local", "remote"]
    assert slept == [0.5]


# --- check -----------------------------------------------------------------------

def test_check_passes_on_real_shaped_files():
    write_real()
    files = discover.discover(list(common.DATASETS), ["2024-12", "2025-01"])
    assert [f.source for f in files] == ["local"] * 6
    assert discover.check(files, load_schema_map()) == []


def test_check_names_file_and_column():
    write_raw("fhvhv", "2025-01", FHVHV_2024 + CBD + [("surge_fee", "DOUBLE")])
    write_raw("yellow", "2025-01", [c for c in YELLOW_2024 if c[0] != "fare_amount"] + CBD)
    write_raw("green", "2025-01", [(n, "VARCHAR" if n == "trip_type" else t) for n, t in GREEN_2024 + CBD])
    problems = discover.check(discover.discover(list(common.DATASETS), ["2025-01"]), load_schema_map())
    assert problems == [
        "fhvhv_tripdata_2025-01.parquet: column 'surge_fee' is not in config/schema_map.yaml",
        "yellow_tripdata_2025-01.parquet: column 'fare_amount' is mapped in config/schema_map.yaml but missing",
        "green_tripdata_2025-01.parquet: column 'trip_type' is VARCHAR, config/schema_map.yaml expects BIGINT",
    ]


def test_check_fails_on_unreadable_file():
    files = [FileSchema("green", "2031-01", "remote", error="HTTP 403: no such file")]
    assert discover.check(files, load_schema_map()) == [
        "green_tripdata_2031-01.parquet: could not read the footer: HTTP 403: no such file"]


def test_cli_check_exit_codes(capsys):
    write_real(months=("2025-01",))
    with pytest.raises(SystemExit) as exit_:
        discover.main(["--check", "--month", "2025-01"])
    assert exit_.value.code == 0
    assert "3 files, 0 problems" in capsys.readouterr().out

    write_raw("green", "2025-01", GREEN_2024 + CBD + [("tip_type", "VARCHAR")])
    with pytest.raises(SystemExit) as exit_:
        discover.main(["--check", "--month", "2025-01"])
    assert exit_.value.code == 1
    assert "green_tripdata_2025-01.parquet: column 'tip_type'" in capsys.readouterr().err


# --- report ----------------------------------------------------------------------

def test_report_from_cli(monkeypatch, tmp_path):
    write_real()
    report_path = tmp_path / "reports" / "schema_discovery.md"
    monkeypatch.setattr(discover, "REPORT_PATH", report_path)
    monkeypatch.setattr(common, "months_in_scope", lambda: ["2024-12", "2025-01"])
    discover.main([])
    report = report_path.read_text()
    assert "2024-12 → 2025-01: 6 files (fhvhv, yellow, green)" in report
    assert "**Pass.**" in report
    assert "| fhvhv | 2 | 6 | 24–25 | 2025-01 adds `cbd_congestion_fee` |" in report
    assert "| 2025-01 | added | `cbd_congestion_fee` | DOUBLE |" in report
    assert "| `Airport_fee` | airport_fee | D | D |" in report
    assert "| `cbd_congestion_fee` | cbd_fee | · | D |" in report
    assert "| `cbd_fee` | = 0 | `cbd_congestion_fee` (COALESCE(cbd_congestion_fee, 0)) |" in report
    assert "| `airport_fee` | = 0 | = 0 | = 0 |" in report                     # green
    assert "| 2024-12 | 3 | 3 | 3 |" in report


def test_report_not_written_when_a_file_is_unreadable(monkeypatch, tmp_path, capsys):
    write_real(months=("2025-01",))
    common.raw_path("green", "2025-01").unlink()
    monkeypatch.setattr(discover, "trip_url", lambda d, m: str(tmp_path / "missing.parquet"))
    monkeypatch.setattr(discover, "REPORT_PATH", tmp_path / "report.md")
    monkeypatch.setattr(common, "months_in_scope", lambda: ["2025-01"])
    with pytest.raises(SystemExit) as exit_:
        discover.main([])
    assert exit_.value.code == 1
    assert not (tmp_path / "report.md").exists()
    assert "report not written" in capsys.readouterr().err


def test_report_highlights_changes_and_unmapped_columns():
    months = ["2026-04", "2026-05", "2026-06"]
    base = YELLOW_2024 + CBD
    files = [
        FileSchema("yellow", months[0], "local", base, 10),
        FileSchema("yellow", months[1], "local",                       # respelled, retyped, renamed
                   [("airport_fee" if n == "Airport_fee" else n, "VARCHAR" if n == "payment_type" else t)
                    for n, t in base if n != "extra"] + [("extra_charge", "DOUBLE")], 11),
        FileSchema("yellow", months[2], "local", base + [("request_source", "VARCHAR")], 12),
    ]
    report = discover.render_report(files, {"yellow": load_schema_map()["yellow"]}, date(2026, 10, 24))
    assert "**Fail: 3 problems.**" in report
    for row in [
        "| 2026-05 | added | `extra_charge` | DOUBLE; same type as dropped `extra`: renamed? |",
        "| 2026-05 | removed | `extra` | DOUBLE |",
        "| 2026-05 | type changed | `payment_type` | BIGINT → VARCHAR |",
        "| 2026-05 | case changed | `airport_fee` | was `Airport_fee` |",
        "| 2026-06 | case changed | `Airport_fee` | was `airport_fee` |",
        "| 2026-06 | added | `request_source` | VARCHAR |",
        "| `Airport_fee` | airport_fee | D | D* | D |",
        "| `payment_type` | is_card | B | V! | B |",
        "| `extra_charge` | **unmapped** | · | D | · |",
        "| `request_source` | ignored | · | · | V |",
        "_Generated by `make discover` (`python -m pipeline.discover`, lane L03) on 2026-10-24.",
    ]:
        assert row in report, row
