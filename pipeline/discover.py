"""DESCRIBE every trip file in scope and write reports/schema_discovery.md.

Only each file's Parquet footer is read: from the local raw file when ingest has already
fetched it, otherwise from the remote file over HTTP with DuckDB httpfs (decision D11).
Whole files are never downloaded.

``--check`` is the SPEC §8 schema check: exit non-zero if any file has a column that
``config/schema_map.yaml`` neither maps nor ignores, lacks a column the map requires, has a
mapped column of another type, or can't be read.

Lane L03 · SPEC §4, §8 · decision D11 · docs/lanes/L03-schema.md
"""

from __future__ import annotations

import argparse
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import duckdb

from pipeline import common
from pipeline.schema_map import UNIFIED_COLUMNS, SchemaError, find_problems, load_schema_map, select_range

REPORT_PATH = common.REPORTS_DIR / "schema_discovery.md"

# CloudFront answers a burst of requests with HTTP 403 "Request blocked" for every file on the
# host, so remote reads are paced and a block is waited out before giving up.
REMOTE_PAUSE_S = 1.0
BLOCK_WAITS_S = (60, 120, 240)

TYPE_CODES = {"VARCHAR": "V", "TIMESTAMP": "T", "INTEGER": "I", "BIGINT": "B", "DOUBLE": "D"}


@dataclass
class FileSchema:
    """One trip file's footer: columns as ``(name, DuckDB type)`` in file order, and rows."""

    dataset: str
    month: str
    source: str                                   # "local" or "remote"
    columns: list[tuple[str, str]] = field(default_factory=list)
    rows: int | None = None
    error: str | None = None

    @property
    def name(self) -> str:
        return f"{self.dataset}_tripdata_{self.month}.parquet"


# --- reading footers -------------------------------------------------------------

def trip_url(dataset: str, month: str) -> str:
    """Remote URL of a trip file, from ``trip_url`` in config/sources.yaml."""
    return common.load_yaml("sources.yaml")["trip_url"].format(dataset=dataset, month=month)


def describe(con: duckdb.DuckDBPyConnection, location: str) -> tuple[list[tuple[str, str]], int]:
    """Columns and row count of one Parquet file, from its footer only."""
    path = common.sql_literal(location)
    columns = con.execute(f"DESCRIBE SELECT * FROM read_parquet({path})").fetchall()
    rows = con.execute(f"SELECT SUM(num_rows) FROM parquet_file_metadata({path})").fetchone()[0]
    return [(name, type_) for name, type_, *_ in columns], int(rows)


def read_footer(con: duckdb.DuckDBPyConnection, dataset: str, month: str, waits: list[float] | None = None,
                sleep: Callable[[float], None] = time.sleep) -> FileSchema:
    """Describe one trip file, local if present, else remote. Errors are returned, not raised.

    While CloudFront blocks requests, waits for each of ``waits`` in turn (popping them, so a
    caller can share one budget across files) before giving up.
    """
    local = common.raw_path(dataset, month)
    if local.exists():
        location, source = str(local), "local"
    else:
        location, source = trip_url(dataset, month), "remote"
        if location.startswith(("http://", "https://")):
            con.execute("INSTALL httpfs")
            con.execute("LOAD httpfs")
    waits = list(BLOCK_WAITS_S) if waits is None else waits
    while True:
        try:
            columns, rows = describe(con, location)
            return FileSchema(dataset, month, source, columns, rows)
        except duckdb.Error as exc:
            if _rate_blocked(exc) and waits:
                wait = waits.pop(0)
                _log(f"{dataset} {month}: CloudFront is blocking requests; retrying in {wait} s")
                sleep(wait)
                continue
            return FileSchema(dataset, month, source, error=_error_text(exc))


def discover(datasets: list[str], months: list[str], con: duckdb.DuckDBPyConnection | None = None,
             pause: float = REMOTE_PAUSE_S, sleep: Callable[[float], None] = time.sleep) -> list[FileSchema]:
    """Read the footer of every ``dataset × month`` file, dataset by dataset.

    Remote reads are ``pause`` seconds apart. The back-off for a CloudFront block is one
    budget for the run, refilled after each successful read, so a block that never lifts
    costs one round of waits rather than one per file.
    """
    con = con or common.connect()
    con.execute("SET enable_http_metadata_cache = true")
    con.execute("SET parquet_metadata_cache = true")
    files, remote_reads, waits = [], 0, list(BLOCK_WAITS_S)
    for dataset in datasets:
        for month in months:
            if not common.raw_path(dataset, month).exists():
                if remote_reads:
                    sleep(pause)
                remote_reads += 1
            schema = read_footer(con, dataset, month, waits, sleep)
            if schema.error:
                _log(f"{dataset} {month}: {schema.error}")
            else:
                waits[:] = BLOCK_WAITS_S
                _log(f"{dataset} {month}: {len(schema.columns)} columns, {schema.rows:,} rows ({schema.source})")
            files.append(schema)
    return files


def _rate_blocked(exc: Exception) -> bool:
    if not isinstance(exc, duckdb.HTTPException):
        return False
    status = getattr(exc, "status_code", None)
    body = getattr(exc, "body", None) or ""
    return status in (429, 503) or (status == 403 and "Request blocked" in body)


def _error_text(exc: Exception) -> str:
    if _rate_blocked(exc):
        return f"CloudFront kept blocking requests (HTTP {exc.status_code}); try again later"
    if isinstance(exc, duckdb.HTTPException) and getattr(exc, "status_code", None) in (403, 404):
        return f"HTTP {exc.status_code}: no such file (has TLC posted this month?)"
    return str(exc).strip().splitlines()[0]


def _log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


# --- check -----------------------------------------------------------------------

def check(files: list[FileSchema], schema_map: dict) -> list[str]:
    """SPEC §8 schema check: one message per problem, empty when every file passes."""
    problems = []
    for f in files:
        if f.error:
            problems.append(f"{f.name}: could not read the footer: {f.error}")
            continue
        problems.extend(str(p) for p in find_problems(f.dataset, f.month, f.columns, f.name, schema_map))
    return problems


# --- report ----------------------------------------------------------------------

def render_report(files: list[FileSchema], schema_map: dict, generated: date) -> str:
    """reports/schema_discovery.md for ``files`` (all readable)."""
    datasets = list(dict.fromkeys(f.dataset for f in files))
    months = sorted({f.month for f in files})
    sources = Counter(f.source for f in files)
    problems = check(files, schema_map)
    changes = {ds: _changes([f for f in files if f.dataset == ds]) for ds in datasets}

    out = [
        "# Schema discovery",
        "",
        f"_Generated by `make discover` (`python -m pipeline.discover`, lane L03) on {generated.isoformat()}. "
        "Don't edit by hand._",
        "",
        f"Every trip file in scope, {months[0]} → {months[-1]}: {len(files)} files ({', '.join(datasets)}), "
        f"read from {sources['remote']} remote Parquet footers (decision D11) and {sources['local']} local raw files. "
        "Types are DuckDB's, as `DESCRIBE` reports them. Column names are matched case-insensitively against "
        "`config/schema_map.yaml`.",
        "",
        "## Check",
        "",
    ]
    if problems:
        out += [f"**Fail: {len(problems)} problems.**", ""] + [f"- {p}" for p in problems]
    else:
        out.append("**Pass.** Every column of every file is mapped or ignored in `config/schema_map.yaml`, "
                   "every mapped column is present, and each has the type the map expects "
                   "(`python -m pipeline.discover --check`).")

    out += ["", "## Summary", "",
            "| Dataset | Files | Rows | Columns | Schema changes |", "|---|--:|--:|--:|---|"]
    for ds in datasets:
        ds_files = [f for f in files if f.dataset == ds]
        widths = sorted({len(f.columns) for f in ds_files})
        width = str(widths[0]) if len(widths) == 1 else f"{widths[0]}–{widths[-1]}"
        summary = "; ".join(f"{m} {_VERBS[kind]} `{col}`" for m, kind, col, _ in changes[ds]) or "none"
        rows = sum(f.rows or 0 for f in ds_files)
        out.append(f"| {ds} | {len(ds_files)} | {rows:,} | {width} | {summary} |")

    for ds in datasets:
        ds_files = sorted((f for f in files if f.dataset == ds), key=lambda f: f.month)
        out += ["", f"## {ds}", "", "### Changes between months", ""]
        if changes[ds]:
            out += ["| Month | Change | Column | Detail |", "|---|---|---|---|"]
            out += [f"| {m} | {kind} | `{col}` | {detail} |" for m, kind, col, detail in changes[ds]]
        else:
            out.append(f"None: every file from {ds_files[0].month} to {ds_files[-1].month} has the same columns.")
        out += ["", "### Columns by month", ""] + _matrix(ds, ds_files, schema_map)
        out += ["", "### Where each unified column comes from", ""] + _sources_table(schema_map[ds])

    out += ["", "## Ignored columns", "", "| Dataset | Column | Reason |", "|---|---|---|"]
    for ds in datasets:
        reasons: dict[str, tuple[str, str]] = {}
        for rng in schema_map[ds]:
            reasons |= {name.lower(): (name, reason) for name, reason in rng["ignore"].items()}
        out += [f"| {ds} | `{name}` | {reason} |" for name, reason in reasons.values()]

    out += ["", "## Rows per file", "", "| Month | " + " | ".join(datasets) + " |",
            "|---|" + "--:|" * len(datasets)]
    rows = {(f.dataset, f.month): f.rows for f in files}
    for m in months:
        cells = [f"{rows[ds, m]:,}" if rows.get((ds, m)) is not None else "" for ds in datasets]
        out.append(f"| {m} | " + " | ".join(cells) + " |")
    return "\n".join(out) + "\n"


_VERBS = {"added": "adds", "removed": "drops", "type changed": "retypes", "case changed": "respells"}


def _changes(files: list[FileSchema]) -> list[tuple[str, str, str, str]]:
    """``(month, kind, column, detail)`` for each difference from the previous month's file."""
    changes = []
    previous: dict[str, tuple[str, str]] | None = None
    for f in sorted(files, key=lambda f: f.month):
        current = {name.lower(): (name, type_) for name, type_ in f.columns}
        if previous is not None:
            added = [k for k in current if k not in previous]
            removed = [k for k in previous if k not in current]
            for k in added:
                name, type_ = current[k]
                renamed = [previous[r][0] for r in removed if previous[r][1] == type_]
                hint = f"; same type as dropped `{renamed[0]}`: renamed?" if renamed else ""
                changes.append((f.month, "added", name, type_ + hint))
            changes += [(f.month, "removed", previous[k][0], previous[k][1]) for k in removed]
            for k in (k for k in current if k in previous):
                (old_name, old_type), (name, type_) = previous[k], current[k]
                if type_ != old_type:
                    changes.append((f.month, "type changed", name, f"{old_type} → {type_}"))
                if name != old_name:
                    changes.append((f.month, "case changed", name, f"was `{old_name}`"))
        previous = current
    return changes


def _matrix(dataset: str, files: list[FileSchema], schema_map: dict) -> list[str]:
    """Column × month table: one row per column (case-insensitive), cells give the type."""
    labels: dict[str, str] = {}
    for f in [files[-1], *files]:                 # latest file's order, then columns since dropped
        for name, _ in f.columns:
            labels.setdefault(name.lower(), name)
    ranges = {f.month: _range_or_none(dataset, f.month, schema_map) for f in files}

    def map_cell(key: str) -> str:
        targets = []
        for rng in schema_map[dataset]:
            for name, spec in rng["columns"].items():
                if name.lower() == key:
                    targets.append(spec["unified"])
            if any(name.lower() == key for name in rng["ignore"]):
                targets.append("ignored")
        return ", ".join(dict.fromkeys(targets)) or "**unmapped**"

    def cell(f: FileSchema, key: str) -> str:
        found = {name.lower(): (name, type_) for name, type_ in f.columns}.get(key)
        if found is None:
            return "·"
        name, type_ = found
        text = TYPE_CODES.get(type_, type_)
        rng = ranges[f.month] or {"columns": {}}
        expected = {n.lower(): spec["type"] for n, spec in rng["columns"].items()}.get(key)
        if name != labels[key]:
            text += "*"
        if expected is not None and type_ != expected:
            text += "!"
        return text

    legend = ", ".join(f"{code} {type_}" for type_, code in TYPE_CODES.items())
    out = [f"Cells give the type ({legend}); · means absent, * a spelling that differs from the row's "
           "only in case, ! a type the map doesn't expect.", "",
           "| Column | Map | " + " | ".join(f.month[2:] for f in files) + " |",
           "|---|---|" + ":-:|" * len(files)]
    for key, label in labels.items():
        out.append(f"| `{label}` | {map_cell(key)} | " + " | ".join(cell(f, key) for f in files) + " |")
    return out


def _range_or_none(dataset: str, month: str, schema_map: dict) -> dict | None:
    try:
        return select_range(dataset, month, schema_map)
    except SchemaError:
        return None


def _sources_table(ranges: list[dict]) -> list[str]:
    """Unified column × range: the raw columns, constant, NULL or rule each range uses."""
    heads = [f"{r['valid_from']} → {r['valid_to'] or 'latest'}" for r in ranges]
    out = ["| Unified column | " + " | ".join(heads) + " |", "|---|" + "---|" * len(ranges)]
    cells = [_unified_sources(r) for r in ranges]
    for unified in UNIFIED_COLUMNS:
        out.append(f"| `{unified}` | " + " | ".join(c[unified] for c in cells) + " |")
    return out


def _unified_sources(rng: dict) -> dict[str, str]:
    sources: dict[str, list[tuple[str, dict]]] = {}
    for name, spec in rng["columns"].items():
        sources.setdefault(spec["unified"], []).append((name, spec))
    described = {}
    for unified, specs in sources.items():
        text = " + ".join(f"`{name}`" for name, _ in specs)
        if len(specs) == 1 and specs[0][1].get("rule"):
            text += f" ({specs[0][1]['rule']})"
        described[unified] = text
    described |= {unified: f"= {value!r}" for unified, value in (rng.get("constant") or {}).items()}
    described |= {unified: "NULL" for unified in rng.get("nulls") or []}
    described |= {unified: f"derived: {rule}" for unified, rule in (rng.get("derived") or {}).items()}
    return described


# --- CLI -------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.discover", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--month", type=common.month_arg, metavar="YYYY-MM",
                        help="limit to one month (default: every month in config/sources.yaml); "
                             "without --check, prints the report instead of writing it")
    parser.add_argument("--check", action="store_true",
                        help="run the schema check instead of writing the report")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    months = [args.month] if args.month else common.months_in_scope()
    datasets = list(common.load_yaml("sources.yaml")["datasets"])
    schema_map = load_schema_map()
    files = discover(datasets, months)

    if args.check:
        problems = check(files, schema_map)
        for problem in problems:
            print(problem, file=sys.stderr)
        print(f"schema check: {len(files)} files, {len(problems)} problems")
        raise SystemExit(1 if problems else 0)

    unreadable = [f for f in files if f.error]
    if unreadable:
        for f in unreadable:
            print(f"{f.name}: {f.error}", file=sys.stderr)
        print(f"{len(unreadable)} of {len(files)} files unreadable; report not written", file=sys.stderr)
        raise SystemExit(1)
    report = render_report(files, schema_map, date.today())
    if args.month:
        print(report, end="")
        return
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    problems = check(files, schema_map)
    print(f"wrote {REPORT_PATH}: {len(files)} files, {len(problems)} schema problems")


if __name__ == "__main__":
    main()
