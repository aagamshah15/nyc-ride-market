"""Run metrics defined in sql/metrics/ over the aggregate tables.

Each metric is one SQL file; this module registers data/agg/*.parquet as views and runs
a named metric with parameters. Pages and publish.py read these outputs and never
recompute from trips.

Views: every ``data/agg/{table}.parquet`` as ``{table}`` (this includes L08's
``ref_indicators``), ``ref_zones`` from ``data/ref/taxi_zone_lookup.csv`` and
``ref_airports`` from ``config/airports.csv``.

Every output is checked against ``contracts/metrics.md`` (names, order and types) before
it is returned. Its schema metadata carries ``metric``, ``params`` (JSON) and ``source``
(the file's ``-- Source:`` header line, e.g. ``TLC-reported``).

Lane L09 · SPEC §6 · docs/lanes/L09-metrics.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from functools import cache

import duckdb
import pyarrow as pa
import pyarrow.csv as pacsv

from pipeline import common

METRICS_DIR = common.SQL_DIR / "metrics"
CONTRACT_PATH = common.REPO_ROOT / "contracts" / "metrics.md"

DEFAULTS = {"window": 3, "top_n": 10}     # to_month defaults to the latest month in agg_zone_hour

_PARAM_RE = re.compile(r"\$([A-Za-z_]\w*)")
_COMMENT_RE = re.compile(r"--[^\n]*")
_HEADER_RE = re.compile(r"^--\s*([A-Za-z ]+):\s*(.*?)\s*$")

# contracts/metrics.md types a column at some uses only. A type given anywhere applies to
# every column of that name; the rest follow these rules (counts BIGINT, money DOUBLE).
_TYPES = {
    "DATE": pa.date32(), "VARCHAR": pa.string(), "SMALLINT": pa.int16(), "INT": pa.int32(),
    "INTEGER": pa.int32(), "BIGINT": pa.int64(), "DOUBLE": pa.float64(), "BOOLEAN": pa.bool_(),
}
_DEFAULT_TYPES = {
    "VARCHAR": ("mode", "pu_borough", "airport", "direction", "license_class", "metric",
                "zone_list", "cbd_group", "exclusion_reason"),
    "SMALLINT": ("do_zone", "iso_year", "iso_week", "year"),
    "BIGINT": ("n", "requests", "matched", "rows", "valid_rows", "f_time", "f_miles", "f_fare",
               "f_zone", "f_wait", "trips_with_cbd_fee"),
}


class ContractError(ValueError):
    """A metric's output doesn't match contracts/metrics.md."""


# --- metric files ------------------------------------------------------------

def available() -> list[str]:
    """Metric names: the ``.sql`` files in ``sql/metrics/``."""
    return sorted(path.stem for path in METRICS_DIR.glob("*.sql"))


def sql_text(name: str) -> str:
    path = METRICS_DIR / f"{name}.sql"
    if not path.is_file():
        raise KeyError(f"no metric {name!r}; expected one of {available()}")
    return path.read_text(encoding="utf-8")


def header(name: str) -> dict[str, str]:
    """The ``-- Key: value`` lines at the top of a metric file."""
    fields = {}
    for line in sql_text(name).splitlines():
        if not line.startswith("--"):
            break
        if match := _HEADER_RE.match(line):
            fields[match[1].strip().lower()] = match[2]
    return fields


def parameters(name: str) -> set[str]:
    """Named parameters (``$name``) the metric's SQL uses, comments ignored."""
    return set(_PARAM_RE.findall(_COMMENT_RE.sub("", sql_text(name))))


# --- contract ----------------------------------------------------------------

@cache
def _contract_rows() -> dict[str, list[tuple[str, str | None]]]:
    rows = {}
    for line in CONTRACT_PATH.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 7 or not cells[0].startswith("`"):
            continue
        name = cells[0].split("`")[1]
        columns = cells[5].split("`")[1]
        rows[name] = [(part.split()[0], part.split()[1] if len(part.split()) > 1 else None)
                      for part in (p.strip() for p in columns.split(","))]
    return rows


def contract_schema(name: str) -> pa.Schema:
    """The output schema ``contracts/metrics.md`` gives ``name``."""
    rows = _contract_rows()
    if name not in rows:
        raise ContractError(f"metric {name!r} is not in {CONTRACT_PATH.name}")
    declared = {}
    for columns in rows.values():
        for column, kind in columns:
            if kind:
                declared.setdefault(column, kind)
    defaults = {column: kind for kind, columns in _DEFAULT_TYPES.items() for column in columns}
    return pa.schema([(column, _TYPES[kind or declared.get(column) or defaults.get(column, "DOUBLE")])
                      for column, kind in rows[name]])


def check_contract(name: str, table: pa.Table) -> None:
    """Raise ``ContractError`` unless ``table``'s columns match the contract exactly."""
    expected = contract_schema(name)
    if not table.schema.equals(expected):
        got = [f"{field.name} {field.type}" for field in table.schema]
        want = [f"{field.name} {field.type}" for field in expected]
        raise ContractError(f"{name}: columns {got} don't match contract {want}")


# --- running -----------------------------------------------------------------

def connect() -> duckdb.DuckDBPyConnection:
    """A connection with every aggregate table, ``ref_zones`` and ``ref_airports`` as views."""
    con = common.connect()
    for path in sorted(common.agg_dir().glob("*.parquet")):
        con.execute(f'CREATE VIEW "{path.stem}" AS SELECT * FROM read_parquet({common.sql_literal(str(path))})')
    zones = common.ref_dir() / "taxi_zone_lookup.csv"
    if zones.is_file():
        con.execute(f"""CREATE VIEW ref_zones AS SELECT * FROM read_csv({common.sql_literal(str(zones))},
            header = true, columns = {{'LocationID': 'SMALLINT', 'Borough': 'VARCHAR',
                                       'Zone': 'VARCHAR', 'service_zone': 'VARCHAR'}})""")
    airports = common.CONFIG_DIR / "airports.csv"
    con.execute(f"""CREATE VIEW ref_airports AS SELECT * FROM read_csv({common.sql_literal(str(airports))},
        header = true, columns = {{'LocationID': 'SMALLINT', 'airport': 'VARCHAR'}})""")
    return con


def _month(value: object) -> date:
    if isinstance(value, datetime):
        value = value.date()
    if isinstance(value, str):
        value = common.parse_month(value[:7]) if re.fullmatch(r"\d{4}-\d{2}(-01)?", value) else None
    if not isinstance(value, date):
        raise ValueError("to_month must be a date or YYYY-MM")
    return date(value.year, value.month, 1)


def _positive_int(key: str, value: object) -> int:
    if isinstance(value, str) and value.strip().isdigit():
        value = int(value)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise ValueError(f"{key} must be a positive integer, got {value!r}")
    return value


def _latest_month(con: duckdb.DuckDBPyConnection) -> date:
    try:
        latest = con.execute("SELECT max(month) FROM agg_zone_hour").fetchone()[0]
    except duckdb.CatalogException:
        latest = None
    if latest is None:
        raise ValueError("to_month has no default: agg_zone_hour is missing or empty")
    return latest


def resolve_params(name: str, con: duckdb.DuckDBPyConnection, given: dict[str, object]) -> dict[str, object]:
    """The metric's parameters: ``given`` values, typed, plus defaults for the rest."""
    used = parameters(name)
    if unknown := sorted(given.keys() - used):
        raise ValueError(f"{name} takes no parameter {', '.join(unknown)}; it uses {sorted(used) or 'none'}")
    params = {}
    for key in sorted(used):
        if key == "to_month":
            params[key] = _month(given[key]) if key in given else _latest_month(con)
        elif key in DEFAULTS:
            params[key] = _positive_int(key, given.get(key, DEFAULTS[key]))
        elif key in given:
            params[key] = given[key]
        else:
            raise ValueError(f"{name} needs parameter {key}")
    return params


def run(name: str, **params: object) -> pa.Table:
    """Run ``sql/metrics/{name}.sql`` with named parameters."""
    with connect() as con:
        return _run(con, name, params)


def _run(con: duckdb.DuckDBPyConnection, name: str, given: dict[str, object]) -> pa.Table:
    sql = sql_text(name)
    params = resolve_params(name, con, given)
    try:
        table = con.execute(sql, params).to_arrow_table()
    except duckdb.CatalogException as exc:
        views = [row[0] for row in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()]
        raise RuntimeError(f"{name}: {exc} (registered views: {sorted(views)})") from exc
    check_contract(name, table)
    return table.replace_schema_metadata({
        "metric": name,
        "params": json.dumps(params, default=str, sort_keys=True),
        "source": header(name).get("source", ""),
    })


def run_all(**params: object) -> dict[str, pa.Table | Exception]:
    """Run every metric, passing each only the parameters it uses. Failures are returned, not raised."""
    results: dict[str, pa.Table | Exception] = {}
    with connect() as con:
        for name in available():
            try:
                used = parameters(name)
                results[name] = _run(con, name, {k: v for k, v in params.items() if k in used})
            except Exception as exc:  # noqa: BLE001 — report every failing metric, not just the first
                results[name] = exc
    return results


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.metrics", description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("name", nargs="?", help="metric file name without .sql")
    target.add_argument("--all", action="store_true", help="run every metric")
    parser.add_argument("--param", action="append", default=[], metavar="KEY=VALUE",
                        help="named parameter; repeatable")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    params = {}
    for item in args.param:
        key, sep, value = item.partition("=")
        if not sep or not key:
            parser.error(f"--param must look like KEY=VALUE, got {item!r}")
        params[key] = value
    if args.all:
        failed = 0
        for name, result in run_all(**params).items():
            if isinstance(result, Exception):
                failed += 1
                print(f"{name}: FAILED: {result}", file=sys.stderr)
            else:
                print(f"{name}: {result.num_rows} rows")
        if failed:
            print(f"{failed} metric(s) failed", file=sys.stderr)
            raise SystemExit(1)
        return
    try:
        table = run(args.name, **params)
    except (KeyError, ValueError, RuntimeError) as exc:
        print(f"{args.name}: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    pacsv.write_csv(table, sys.stdout.buffer)


if __name__ == "__main__":
    main()
