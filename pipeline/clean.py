"""Raw trips for one month → unified, enriched, flagged trips (runs sql/clean/*.sql).

Writes data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet. Flags rows; never drops them.

Lane L06 · SPEC §4, §4.1, §4.2 · decisions D9, D18 · docs/lanes/L06-clean.md

Each dataset of the month (fhvhv, yellow, green) goes through, one file at a time:

1. The raw file's columns are checked against config/schema_map.yaml (``pipeline.schema_map``). A
   column the map neither maps nor ignores, a mapped column that is missing, or a changed type stops
   the run, naming the file and the column.
2. The view ``src`` selects the mapped columns from the file. A raw column that alone feeds a unified
   column takes the unified name and keeps its raw value (``Airport_fee`` → ``airport_fee``,
   ``payment_type`` → ``is_card``); columns that share a unified column keep their map names
   (``bcf``, ``sales_tax``); the range's constants and NULL columns are added under the unified name.
   So the SQL files below read the same names whatever the month's range.
3. ``sql/clean/{hvfhv,yellow,green}.sql`` turns ``src`` into the 25 unified columns, SPEC §4's
   plus ``vendor_id`` (D25) (view ``unified``); ``sql/clean/derive.sql`` adds the derived columns
   and flags (view ``clean``) in the order and types of ``CLEAN_TRIPS_SCHEMA`` (tests/factories.py).
4. One ``COPY`` per mode writes a self-contained file, ``mode`` and ``month`` included (D18), into a
   staging folder under data/clean/.

Rows out must equal rows in, and rows in must equal the file's ``rows`` in data/manifest.json. Only
when all three datasets pass are the staged files renamed over the month's old ones, one rename per
file; a mode with no rows this time loses its old file. If a run stops part-way, the old files stay
as they were: run the month again.
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import time
from collections import Counter
from pathlib import Path

import duckdb

from pipeline import schema_map, zones
from pipeline.common import (
    DATASETS, MODES, SQL_DIR, clean_dir, clean_partition, connect, data_dir, format_month, load_yaml,
    manifest_path, month_arg, parse_month, raw_path, sql_literal,
)
from pipeline.ingest import load_manifest

HV_MODES = ("uber", "lyft", "other_hv")
SQL_FILES = {"fhvhv": "hvfhv.sql", "yellow": "yellow.sql", "green": "green.sql"}
FLAGS = ("f_time", "f_miles", "f_fare", "f_zone", "f_wait")


class CleanError(Exception):
    """The month can't be cleaned. The message names the file and says why."""


def _label(path: Path) -> str:
    """A data file as the manifest keys it, e.g. ``raw/yellow/2025-03.parquet``."""
    return path.relative_to(data_dir()).as_posix()


def _ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _value(value) -> str:
    """A schema_map.yaml constant as a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        return repr(value)
    return sql_literal(str(value))


def _sql(name: str) -> str:
    return (SQL_DIR / "clean" / name).read_text(encoding="utf-8").strip().rstrip(";")


# --- reference tables ----------------------------------------------------------

def load_refs(con: duckdb.DuckDBPyConnection) -> None:
    """Tables ``ref_zone`` and ``hv_license`` and the period variables that the SQL reads."""
    try:
        lookup = zones.read_lookup()
    except FileNotFoundError:
        raise CleanError(f"{_label(zones.lookup_path())}: zone lookup missing; run make ref") from None
    airports = zones.airport_zones()
    core, wide = zones.cbd_zone_ids("core"), zones.cbd_zone_ids("wide")
    con.execute("CREATE OR REPLACE TEMP TABLE ref_zone "
                "(zone SMALLINT, borough VARCHAR, airport VARCHAR, cbd BOOLEAN, cbd_wide BOOLEAN)")
    con.executemany("INSERT INTO ref_zone VALUES (?, ?, ?, ?, ?)", [
        (zone, lookup[zone]["Borough"] if zone in lookup else None, airports.get(zone), zone in core, zone in wide)
        for zone in sorted(set(lookup) | set(airports) | wide)
    ])

    licenses = load_yaml("sources.yaml")["hv_license"]
    if wrong := {code: mode for code, mode in licenses.items() if mode not in HV_MODES}:
        raise CleanError(f"config/sources.yaml: hv_license maps {wrong}; modes must be one of {HV_MODES}")
    con.execute("CREATE OR REPLACE TEMP TABLE hv_license (code VARCHAR, mode VARCHAR)")
    con.executemany("INSERT INTO hv_license VALUES (?, ?)", list(licenses.items()))

    periods = load_yaml("periods.yaml")
    con.execute(f"SET VARIABLE cp_start = DATE '{periods['congestion_pricing_start'].isoformat()}'")
    con.execute(f"SET VARIABLE pay_rise = DATE '{periods['driver_pay_rise'].isoformat()}'")


# --- one raw file --------------------------------------------------------------

def source_query(con: duckdb.DuckDBPyConnection, dataset: str, month: str, path: Path,
                 smap: dict) -> tuple[str, dict[str, str]]:
    """The SELECT behind ``src`` for one raw file, and the file's raw → unified column mapping.

    Raises ``schema_map.SchemaError`` (unmapped columns first) when the file breaks the map.
    """
    label = _label(path)
    columns = [(name, kind) for name, kind, *_ in
               con.execute(f"DESCRIBE SELECT * FROM read_parquet({sql_literal(str(path))})").fetchall()]
    problems = schema_map.find_problems(dataset, month, columns, label, smap)
    if problems:
        raise problems[0]
    mapping = schema_map.resolve(dataset, month, [name for name, _ in columns], label, smap)
    rng = schema_map.select_range(dataset, month, smap)
    map_names = {name.lower(): name for name in rng["columns"]}
    sources = Counter(mapping.values())
    select = [f"{_ident(raw)} AS {_ident(unified if sources[unified] == 1 else map_names[raw.lower()])}"
              for raw, unified in mapping.items()]
    select += [f"{_value(value)} AS {_ident(unified)}" for unified, value in (rng.get("constant") or {}).items()]
    select += [f"NULL AS {_ident(unified)}" for unified in rng.get("nulls") or []]
    query = (f"SELECT {', '.join(select)} "
             f"FROM read_parquet({sql_literal(str(path))}, hive_partitioning = false)")
    return query, mapping


def check_licenses(con: duckdb.DuckDBPyConnection, label: str) -> None:
    """Every licence code in ``src.mode`` must be in config/sources.yaml (SPEC §3.3)."""
    unknown = con.execute("""
        SELECT src.mode, count(*) FROM src LEFT JOIN hv_license AS lic ON lic.code = src.mode
        WHERE lic.code IS NULL GROUP BY 1 ORDER BY 1 NULLS FIRST""").fetchall()
    if unknown:
        found = ", ".join(f"{code!r} ({n:,} rows)" for code, n in unknown)
        raise CleanError(f"{label}: hvfhs_license_num {found} not in hv_license in config/sources.yaml")


def flag_counts(con: duckdb.DuckDBPyConnection, path: Path) -> dict[str, int]:
    """Rows, valid rows and each flag's count in a written clean file."""
    counts = ", ".join(f"count(*) FILTER (WHERE {flag})" for flag in ("is_valid", *FLAGS))
    values = con.execute(f"SELECT count(*), {counts} FROM read_parquet({sql_literal(str(path))})").fetchone()
    return dict(zip(("rows", "valid", *FLAGS), values))


def clean_file(con: duckdb.DuckDBPyConnection, dataset: str, month: str, staging: Path,
               smap: dict, expected_rows: int) -> dict[str, dict[str, int]]:
    """Clean one raw file into ``staging``; return the counts per mode written."""
    path = raw_path(dataset, month)
    label = _label(path)
    query, mapping = source_query(con, dataset, month, path, smap)
    con.execute(f"CREATE OR REPLACE TEMP VIEW src AS {query}")
    if "mode" in mapping.values():
        check_licenses(con, label)

    sql_file = SQL_FILES[dataset]
    con.execute(f"CREATE OR REPLACE TEMP VIEW unified AS (\n{_sql(sql_file)}\n)")
    names = tuple(name for name, *_ in con.execute("DESCRIBE unified").fetchall())
    if names != schema_map.UNIFIED_COLUMNS:
        raise CleanError(f"sql/clean/{sql_file} gives columns {list(names)}, "
                         f"not SPEC §4's {list(schema_map.UNIFIED_COLUMNS)}")
    con.execute(f"CREATE OR REPLACE TEMP VIEW clean AS (\n{_sql('derive.sql')}\n)")

    rows_in = con.execute(f"SELECT count(*) FROM read_parquet({sql_literal(str(path))})").fetchone()[0]
    if rows_in != expected_rows:
        raise CleanError(f"{label}: {rows_in:,} rows, but {manifest_path().name} says {expected_rows:,}; "
                         f"run make ingest MONTH={month} again")
    modes_in = dict(con.execute("SELECT mode, count(*) FROM unified GROUP BY mode").fetchall())

    counts = {}
    for mode in sorted(modes_in, key=MODES.index):
        out = staging / clean_partition(mode, month).relative_to(clean_dir()) / "part-0.parquet"
        out.parent.mkdir(parents=True)
        con.execute(f"COPY (SELECT * FROM clean WHERE mode = {sql_literal(mode)}) "
                    f"TO {sql_literal(str(out))} (FORMAT parquet, COMPRESSION zstd)")
        counts[mode] = flag_counts(con, out)
        if counts[mode]["rows"] != modes_in[mode]:
            raise CleanError(f"{label}: {modes_in[mode]:,} {mode} rows in, {counts[mode]['rows']:,} out")
    rows_out = sum(c["rows"] for c in counts.values())
    if rows_out != rows_in:
        raise CleanError(f"{label}: {rows_in:,} rows in, {rows_out:,} out")
    return counts


# --- one month -----------------------------------------------------------------

def expected_rows(month: str) -> dict[str, int]:
    """Each dataset's row count from the manifest, checking that its raw file is there."""
    manifest = load_manifest()
    rows = {}
    for dataset in DATASETS:
        path = raw_path(dataset, month)
        label = _label(path)
        if not path.exists():
            raise CleanError(f"{label}: raw file missing; run make ingest MONTH={month}")
        entry = manifest.get(label) or {}
        if entry.get("rows") is None:
            raise CleanError(f"{label}: no row count in {manifest_path().name}; run make ingest MONTH={month}")
        rows[dataset] = entry["rows"]
    return rows


def replace_month(staging: Path, month: str) -> None:
    """Rename the staged files over the month's old ones; drop old files of modes now empty."""
    for mode in MODES:
        final = clean_partition(mode, month) / "part-0.parquet"
        staged = staging / final.relative_to(clean_dir())
        if staged.exists():
            final.parent.mkdir(parents=True, exist_ok=True)
            os.replace(staged, final)
        elif final.exists():
            final.unlink()
            try:
                final.parent.rmdir()
            except OSError:
                pass   # something else lives there; leave it


def _report(label: str, rows_in: int, counts: dict[str, dict[str, int]], seconds: float) -> None:
    print(f"{label}: {rows_in:,} rows in, {sum(c['rows'] for c in counts.values()):,} out ({seconds:.1f} s)")
    for mode, c in counts.items():
        shares = " · ".join(f"{name} {c[name]:,} ({c[name] / c['rows']:.2%})" for name in ("valid", *FLAGS))
        print(f"  {mode:<8} {c['rows']:>12,} rows · {shares}")


def clean_month(month: str) -> dict[str, dict[str, int]]:
    """Clean the month (``YYYY-MM``) of all three datasets; return counts per mode written."""
    month = format_month(parse_month(month))
    smap = schema_map.load_schema_map()
    rows = expected_rows(month)
    staging = clean_dir() / f".staging-{month}-{os.getpid()}"
    con = connect()
    try:
        load_refs(con)
        con.execute(f"SET VARIABLE file_month = DATE '{month}-01'")
        shutil.rmtree(staging, ignore_errors=True)
        staging.mkdir(parents=True)
        counts = {}
        for dataset in DATASETS:
            started = time.monotonic()
            written = clean_file(con, dataset, month, staging, smap, rows[dataset])
            _report(_label(raw_path(dataset, month)), rows[dataset], written, time.monotonic() - started)
            counts |= written
        replace_month(staging, month)
        print(f"{month}: wrote {', '.join(counts)} under {clean_dir()}")
        return counts
    finally:
        con.close()
        shutil.rmtree(staging, ignore_errors=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.clean", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", type=month_arg, metavar="YYYY-MM", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        clean_month(args.month)
    except (CleanError, schema_map.SchemaError) as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
