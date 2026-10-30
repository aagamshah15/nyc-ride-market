"""Clean trips for one month → that month's rows in every aggregate table (runs sql/agg/*.sql).

Deletes and rewrites only that month's rows in data/agg/{table}.parquet.

Lane L07 · SPEC §5 · decisions D7–D10, D15–D18, D23–D25, D29 · docs/lanes/L07-aggregate.md

Each ``sql/agg/{table}.sql`` is a SELECT over the view ``trips``: the month's clean files,
``data/clean/mode=*/month={YYYY-MM}/part-0.parquet``, read with ``hive_partitioning = false``
(D18). Every table's new rows are computed first, so a failing query stops the run before
any file is touched. Then each table is rebuilt as its other months' rows plus the new rows,
sorted on every column, written to ``{table}.parquet.tmp`` beside it and renamed over the old
file. Other months' rows are copied unchanged and a re-run writes the same file. If a run
stops while writing, run the month again.

A table file whose columns differ from what its SQL now gives (written before a schema
change) is stale: it is moved to ``data/agg_stale/{table}.parquet``, the table restarts with
this month alone, and a warning lists the other months to aggregate again.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import date
from pathlib import Path

import duckdb

from pipeline.common import (
    SQL_DIR, agg_path, clean_dir, connect, data_dir, format_month, load_yaml, month_arg, parse_month,
    sql_literal,
)

TABLES = (
    "agg_zone_hour", "agg_zone_month_dist", "agg_od_month", "agg_airport", "agg_week_cbd",
    "agg_fees_month", "agg_quality_month", "agg_cbd_pairs", "agg_fee_values", "agg_vendor_month",
)

DIST_MIN_N = 100     # agg_zone_month_dist: percentiles only for groups with this many valid trips
OD_MIN_TRIPS = 20    # agg_od_month: zone pairs with at least this many valid trips that month


class AggregateError(Exception):
    """The month can't be aggregated. The message says why and what to run."""


def clean_files(month: str) -> list[Path]:
    """The month's clean partition files, one per mode present."""
    files = sorted(clean_dir().glob(f"mode=*/month={month}/part-0.parquet"))
    if not files:
        raise AggregateError(f"{month}: no clean files under {clean_dir()}; run make clean MONTH={month} first")
    return files


def stale_path(table: str) -> Path:
    """Where a table file with an older column layout is set aside (outside ``data/agg/``)."""
    return data_dir() / "agg_stale" / f"{table}.parquet"


def cbd_from_month() -> date:
    """First day of the month congestion pricing started (config/periods.yaml)."""
    start = load_yaml("periods.yaml")["congestion_pricing_start"]
    return date(start.year, start.month, 1)


def open_month(con: duckdb.DuckDBPyConnection, month: str) -> dict[str, int]:
    """Create the ``trips`` view and the SQL variables; return rows per mode."""
    files = ", ".join(sql_literal(str(f)) for f in clean_files(month))
    con.execute(f"CREATE OR REPLACE TEMP VIEW trips AS "
                f"SELECT * FROM read_parquet([{files}], hive_partitioning = false)")
    found = con.execute("SELECT month, mode, count(*) FROM trips GROUP BY ALL ORDER BY mode").fetchall()
    wrong = sorted({str(m) for m, _, _ in found if m != parse_month(month)})
    if wrong:
        raise AggregateError(f"{month}: clean files hold rows for other months ({', '.join(wrong)}); "
                             f"rebuild them with make clean MONTH={month}")
    con.execute(f"SET VARIABLE dist_min_n = {int(DIST_MIN_N)}")
    con.execute(f"SET VARIABLE od_min_trips = {int(OD_MIN_TRIPS)}")
    con.execute(f"SET VARIABLE cbd_from_month = DATE '{cbd_from_month().isoformat()}'")
    return {mode: n for _, mode, n in found}


def _columns(con: duckdb.DuckDBPyConnection, relation: str) -> list[tuple[str, str]]:
    return [(name, kind) for name, kind, *_ in con.execute(f"DESCRIBE {relation}").fetchall()]


def _layout_change(old: list[tuple[str, str]], new: list[tuple[str, str]]) -> str:
    old_types, new_types = dict(old), dict(new)
    parts = []
    if missing := [c for c in new_types if c not in old_types]:
        parts.append("without " + ", ".join(missing))
    if extra := [c for c in old_types if c not in new_types]:
        parts.append("with extra " + ", ".join(extra))
    if retyped := [c for c in new_types if c in old_types and old_types[c] != new_types[c]]:
        parts.append("with other types for " + ", ".join(retyped))
    return "; ".join(parts) or "with the columns in another order"


def stage(con: duckdb.DuckDBPyConnection, table: str, month: str) -> str | None:
    """Compute ``table``'s rows for the month into ``new_{table}``. Return how the existing file's
    layout differs from them when it is stale, else None."""
    query = (SQL_DIR / "agg" / f"{table}.sql").read_text(encoding="utf-8").strip().rstrip(";")
    try:
        con.execute(f"CREATE OR REPLACE TEMP TABLE new_{table} AS (\n{query}\n)")
    except duckdb.BinderException as exc:
        raise AggregateError(f"{table}: {exc}\nThe clean files may predate a schema change; "
                             f"rebuild them with make clean MONTH={month}") from None
    path = agg_path(table)
    if path.exists():
        old = _columns(con, f"SELECT * FROM read_parquet({sql_literal(str(path))})")
        new = _columns(con, f"new_{table}")
        if old != new:
            return _layout_change(old, new)
    return None


def rewrite(con: duckdb.DuckDBPyConnection, table: str, month: str, stale: str | None = None) -> tuple[int, int]:
    """Replace ``month``'s rows in ``data/agg/{table}.parquet`` with ``new_{table}``;
    return (month rows, all rows). A ``stale`` file is set aside and the table restarts."""
    path = agg_path(table)
    source = f"SELECT * FROM new_{table}"
    if path.exists() and not stale:
        source = (f"SELECT * FROM read_parquet({sql_literal(str(path))}) "
                  f"WHERE month <> DATE '{month}-01' UNION ALL {source}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    con.execute(f"COPY ({source} ORDER BY ALL) TO {sql_literal(str(tmp))} (FORMAT parquet)")
    if stale:
        others = [format_month(m) for (m,) in con.execute(
            f"SELECT DISTINCT month FROM read_parquet({sql_literal(str(path))}) "
            f"WHERE month <> DATE '{month}-01' ORDER BY month").fetchall()]
        aside = stale_path(table)
        aside.parent.mkdir(parents=True, exist_ok=True)
        os.replace(path, aside)
        todo = f"; aggregate its other {len(others)} months again ({others[0]} to {others[-1]})" if others else ""
        print(f"{table}: the file was written {stale}, an older layout. Moved it to {aside} and "
              f"restarted the table with {month}{todo}", file=sys.stderr)
    os.replace(tmp, path)
    month_rows = con.execute(f"SELECT count(*) FROM new_{table}").fetchone()[0]
    all_rows = con.execute(f"SELECT count(*) FROM read_parquet({sql_literal(str(path))})").fetchone()[0]
    return month_rows, all_rows


def aggregate_month(month: str, tables: tuple[str, ...] = TABLES) -> dict[str, int]:
    """Rebuild ``month``'s rows (``YYYY-MM``) in each table; return the month's row count per table."""
    parse_month(month)
    con = connect()
    try:
        modes = open_month(con, month)
        print(f"{month}: clean rows " + ", ".join(f"{mode} {n:,}" for mode, n in modes.items()))
        seconds, stale = {}, {}
        for table in tables:            # every query first: a failure leaves all files as they were
            started = time.monotonic()
            stale[table] = stage(con, table, month)
            seconds[table] = time.monotonic() - started
        written = {}
        for table in tables:
            started = time.monotonic()
            written[table], total = rewrite(con, table, month, stale[table])
            seconds[table] += time.monotonic() - started
            print(f"{table}: {written[table]:,} rows for {month}, {total:,} in all ({seconds[table]:.1f} s)")
        return written
    finally:
        con.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.aggregate", description=__doc__)
    parser.add_argument("--month", type=month_arg, metavar="YYYY-MM", required=True)
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        aggregate_month(args.month)
    except AggregateError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
