"""Shared paths, config loading, month helpers and the DuckDB connection.

Owned by the integrator. Lanes ask before changing it (docs/development-plan.md §1).

All data paths resolve under ``data_dir()``, which honours ``NYC_DATA_DIR`` so several
git worktrees can share one copy of the raw files.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

import duckdb
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = REPO_ROOT / "config"
SQL_DIR = REPO_ROOT / "sql"
REPORTS_DIR = REPO_ROOT / "reports"
SITE_DATA_DIR = REPO_ROOT / "site" / "src" / "data"

DATASETS = ("fhvhv", "yellow", "green")
MODES = ("uber", "lyft", "other_hv", "yellow", "green")

_MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


# --- paths -------------------------------------------------------------------

def data_dir() -> Path:
    """Root of all pipeline data: ``$NYC_DATA_DIR`` or ``<repo>/data``."""
    override = os.environ.get("NYC_DATA_DIR")
    return Path(override).expanduser().resolve() if override else REPO_ROOT / "data"


def raw_path(dataset: str, month: str) -> Path:
    """``data/raw/{dataset}/{YYYY-MM}.parquet``."""
    _check_dataset(dataset)
    return data_dir() / "raw" / dataset / f"{format_month(parse_month(month))}.parquet"


def clean_dir() -> Path:
    return data_dir() / "clean"


def clean_partition(mode: str, month: str) -> Path:
    """``data/clean/mode={mode}/month={YYYY-MM}/``."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    return clean_dir() / f"mode={mode}" / f"month={format_month(parse_month(month))}"


def agg_dir() -> Path:
    return data_dir() / "agg"


def agg_path(table: str) -> Path:
    """``data/agg/{table}.parquet``."""
    return agg_dir() / f"{table}.parquet"


def ref_dir() -> Path:
    """Lookup and context files: zone lookup, shapefile, indicators CSV."""
    return data_dir() / "ref"


def manifest_path() -> Path:
    return data_dir() / "manifest.json"


def scratch_dir(lane: str) -> Path:
    """Per-lane experiment space, ``data/scratch/{lane}/``. Created on first use."""
    path = data_dir() / "scratch" / lane
    path.mkdir(parents=True, exist_ok=True)
    return path


def _check_dataset(dataset: str) -> None:
    if dataset not in DATASETS:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {DATASETS}")


# --- config ------------------------------------------------------------------

def load_yaml(name: str) -> Any:
    """Load ``config/{name}`` (e.g. ``"sources.yaml"``)."""
    with open(CONFIG_DIR / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_csv(name: str) -> list[dict[str, str]]:
    """Load ``config/{name}`` as a list of row dicts keyed by header."""
    with open(CONFIG_DIR / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


# --- months ------------------------------------------------------------------

def parse_month(value: str) -> date:
    """``"2026-08"`` → ``date(2026, 8, 1)``. Anything else raises ``ValueError``."""
    match = _MONTH_RE.match(value)
    if not match:
        raise ValueError(f"month must look like YYYY-MM, got {value!r}")
    return date(int(match[1]), int(match[2]), 1)


def format_month(value: date) -> str:
    return f"{value.year:04d}-{value.month:02d}"


def month_arg(value: str) -> str:
    """argparse ``type=`` for ``YYYY-MM`` arguments."""
    try:
        return format_month(parse_month(value))
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from None


def month_range(start: str, end: str) -> list[str]:
    """Inclusive list of ``YYYY-MM`` strings from ``start`` to ``end``."""
    first, last = parse_month(start), parse_month(end)
    if first > last:
        raise ValueError(f"start month {start} is after end month {end}")
    months = []
    year, month = first.year, first.month
    while (year, month) <= (last.year, last.month):
        months.append(f"{year:04d}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def months_in_scope() -> list[str]:
    """Months listed in ``config/sources.yaml`` (``months.from`` → ``months.to``)."""
    months = load_yaml("sources.yaml")["months"]
    return month_range(str(months["from"]), str(months["to"]))


# --- DuckDB ------------------------------------------------------------------

def connect(database: str = ":memory:") -> duckdb.DuckDBPyConnection:
    """DuckDB connection with project defaults.

    ``NYC_DUCKDB_THREADS`` and ``NYC_DUCKDB_MEMORY`` (e.g. ``"8GB"``) override DuckDB's
    own defaults. Spill files go under ``data/tmp/duckdb``.
    """
    con = duckdb.connect(database)
    spill = data_dir() / "tmp" / "duckdb"
    spill.mkdir(parents=True, exist_ok=True)
    con.execute(f"SET temp_directory = {sql_literal(str(spill))}")
    con.execute("SET preserve_insertion_order = false")
    if threads := os.environ.get("NYC_DUCKDB_THREADS"):
        con.execute(f"SET threads = {int(threads)}")
    if memory := os.environ.get("NYC_DUCKDB_MEMORY"):
        con.execute(f"SET memory_limit = {sql_literal(memory)}")
    return con


def sql_literal(value: str) -> str:
    """Quote a string as a SQL literal (for paths in COPY / read_parquet / SET)."""
    return "'" + value.replace("'", "''") + "'"


# --- stubs -------------------------------------------------------------------

def not_implemented(lane: str, step: str) -> None:
    """Exit non-zero naming the lane that owns an unbuilt step."""
    print(f"{step}: not implemented (lane {lane})", file=sys.stderr)
    raise SystemExit(3)


# --- CLI ---------------------------------------------------------------------

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m pipeline.common")
    sub = parser.add_subparsers(dest="command", required=True)
    months = sub.add_parser("months", help="print months from START to END, one per line")
    months.add_argument("start", metavar="START")
    months.add_argument("end", metavar="END")
    args = parser.parse_args(argv)
    if args.command == "months":
        try:
            print("\n".join(month_range(args.start, args.end)))
        except ValueError as exc:
            parser.error(str(exc))


if __name__ == "__main__":
    main()
