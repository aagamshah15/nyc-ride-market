"""Validation gate: tie-out, quality drift, CBD list, schema and fee checks.

Writes reports/validation.md (pass/fail table first, then details) and
data/agg/validation_summary.json (contracts/README.md §5), and exits non-zero unless every
check passes. The thresholds are SPEC's and are not options: never widen a tolerance to make
a check pass (CLAUDE.md).

Each run first reloads data/ref/data_reports_monthly.csv into data/agg/ref_indicators.parquet,
values unchanged; ``--indicators-only`` does just that. The months checked are
config/sources.yaml's scope plus any month found in the aggregates, so a month missing from
the aggregates fails the tie-out and an extra one is still checked.

The checks are SQL in sql/validate/ over the aggregate tables; the schema check reads trip-file
footers through pipeline.discover (the same check as ``python -m pipeline.discover --check``).

Lane L08 · SPEC §8, §7.2 · decisions D8, D21, D22, D25, D26, D27 · docs/lanes/L08-validate.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

import duckdb

from pipeline import common, discover, zones
from pipeline.schema_map import SchemaError, load_schema_map

# SPEC thresholds, as whole percentages so the SQL compares integers and each boundary is exact.
TIE_OUT_TOLERANCE_PCT = 2    # SPEC §8: pipeline trips per day within ±2% of TLC's
MIN_VALID_PCT = 85           # D26 (replaces SPEC §8's 95%): valid_rows / rows per month × mode
DRIFT_POINTS = 3             # SPEC §8: list a month more than 3 points below its mode's median
CBD_BOTH_IN_MIN_PCT = 98     # SPEC §7.2: both-in trips carrying a fee
FEE_EXACT_MIN_PCT = 95       # SPEC §8: fee-paying trips at exactly the configured fee

CHECKS = {   # id → report heading, in contract order
    "tie_out": "Tie-out",
    "quality_drift": "Quality drift",
    "cbd_list": "CBD list",
    "schema": "Schema",
    "fees": "Fees",
}
ROWS_KEY = {"tie_out": "tie_out", "quality_drift": "quality", "cbd_list": "cbd", "fees": "fees"}
ZONE_LISTS = ("core", "wide")                       # D9
GATED_ZONE_LIST = "core"                            # D21: only core gates the CBD check; wide is reported
LICENSE_CLASSES = ("FHV - High Volume", "Yellow", "Green")
GATED_LICENSE_CLASS = "FHV - High Volume"           # D27: only ride-hail gates the tie-out; cabs are reported
AGG_INPUTS = ("agg_zone_hour", "agg_quality_month", "agg_cbd_pairs", "agg_fee_values", "agg_vendor_month")
HV_MODES = ("uber", "lyft", "other_hv")
DATASET_MODES = {"fhvhv": HV_MODES, "yellow": ("yellow",), "green": ("green",)}

INDICATORS_CSV = "data_reports_monthly.csv"
INDICATOR_COLUMNS = (   # NYC Open Data copy (D19): first header is Year/Month
    "Year/Month", "License Class", "Trips Per Day", "Farebox Per Day", "Unique Drivers",
    "Unique Vehicles", "Vehicles Per Day", "Avg Days Vehicles on Road",
    "Avg Hours Per Day Per Vehicle", "Avg Days Drivers on Road", "Avg Hours Per Day Per Driver",
    "Avg Minutes Per Trip", "Percent of Trips Paid with Credit Card", "Trips Per Day Shared",
)

MAX_LISTED = 5           # problems named in a one-line summary before "and N more"
MAX_OTHER_VALUES = 20    # other fee values kept per mode

SQL_DIR = common.SQL_DIR / "validate"
REPORT_PATH = common.REPORTS_DIR / "validation.md"


class MissingInput(Exception):
    """An input table or file a check needs isn't there."""


@dataclass
class Check:
    """One check's outcome: status, a one-line summary, contract rows and report lines."""

    id: str
    status: str                                     # pass | fail | skipped
    summary: str
    rows: list[dict] = field(default_factory=list)  # this check's array in the summary JSON
    details: list[str] = field(default_factory=list)


def indicators_csv_path() -> Path:
    return common.ref_dir() / INDICATORS_CSV


def summary_path() -> Path:
    return common.agg_dir() / "validation_summary.json"


# --- ref_indicators ----------------------------------------------------------

def load_ref_indicators(con: duckdb.DuckDBPyConnection | None = None) -> Path:
    """Load the indicators CSV into ``data/agg/ref_indicators.parquet`` with its column names
    and values unchanged (sql/validate/ref_indicators.sql). Raises if the CSV is missing, its
    header differs from :data:`INDICATOR_COLUMNS`, a month × class repeats, or a value doesn't parse."""
    csv_path = indicators_csv_path()
    if not csv_path.exists():
        raise FileNotFoundError(f"{csv_path} is missing; run `make ref`")
    con = con or common.connect()
    con.execute("CREATE OR REPLACE TEMP VIEW indicators_csv AS SELECT * FROM read_csv("
                f"{common.sql_literal(str(csv_path))}, header = true, all_varchar = true, delim = ',')")
    header = [row[0] for row in con.execute("DESCRIBE indicators_csv").fetchall()]
    if sorted(header) != sorted(INDICATOR_COLUMNS):
        missing = [c for c in INDICATOR_COLUMNS if c not in header]
        extra = [c for c in header if c not in INDICATOR_COLUMNS]
        raise ValueError(f"{csv_path}: header differs from the expected indicators columns; "
                         f"missing {missing}, unexpected {extra}")
    repeated = con.execute('SELECT "Year/Month", "License Class" FROM indicators_csv '
                           "GROUP BY ALL HAVING COUNT(*) > 1 ORDER BY ALL").fetchall()
    if repeated:
        raise ValueError(f"{csv_path}: repeated month × license class rows: {repeated[:MAX_LISTED]}")
    path = common.agg_path("ref_indicators")
    _write_parquet(con, _sql("ref_indicators"), path)
    return path


def _write_parquet(con: duckdb.DuckDBPyConnection, select: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    con.execute(f"COPY ({select.strip().rstrip(';')}) TO {common.sql_literal(str(tmp))} (FORMAT parquet)")
    os.replace(tmp, path)


# --- running the checks ------------------------------------------------------

def run(con: duckdb.DuckDBPyConnection | None = None, now: datetime | None = None) -> dict:
    """Run every check, write the report and the summary JSON, and return the summary."""
    con = con or common.connect()
    now = now or datetime.now(timezone.utc)
    try:
        load_ref_indicators(con)
        indicators_error = None
    except (OSError, ValueError, duckdb.Error) as exc:
        indicators_error = _first_line(exc)
    present = _register_inputs(con)
    if indicators_error:
        present.discard("ref_indicators")   # never tie out against a stale copy
    months = months_checked(con, present)
    con.execute("CREATE OR REPLACE TABLE months_checked (month DATE)")
    con.executemany("INSERT INTO months_checked VALUES (?)", [[common.parse_month(m)] for m in months])
    periods = common.load_yaml("periods.yaml")

    checks = [
        _guarded("tie_out", check_tie_out, con, present, indicators_error),
        _guarded("quality_drift", check_quality, con, present),
        _guarded("cbd_list", check_cbd, con, present, periods, months),
        _guarded("schema", check_schema, months),
        _guarded("fees", check_fees, con, present, periods),
    ]
    summary = build_summary(checks, months, now)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(render_report(summary, checks, now), encoding="utf-8")
    _write_json_atomic(summary_path(), summary)
    return summary


def _register_inputs(con: duckdb.DuckDBPyConnection) -> set[str]:
    """A view per aggregate table that exists; returns their names."""
    present = set()
    for name in (*AGG_INPUTS, "ref_indicators"):
        path = common.agg_path(name)
        if path.exists():
            con.execute(f"CREATE OR REPLACE VIEW {name} AS "
                        f"SELECT * FROM read_parquet({common.sql_literal(str(path))})")
            present.add(name)
    return present


def months_checked(con: duckdb.DuckDBPyConnection, present: set[str]) -> list[str]:
    """``YYYY-MM`` months in config/sources.yaml's scope or in any input aggregate, sorted."""
    months = set(common.months_in_scope())
    for name in AGG_INPUTS:
        if name in present:
            found = con.execute(f"SELECT DISTINCT month FROM {name} WHERE month IS NOT NULL").fetchall()
            months |= {common.format_month(month) for (month,) in found}
    return sorted(months)


def _guarded(check_id: str, fn: Callable[..., Check], *args: Any) -> Check:
    """Run one check; one that can't run fails with the reason instead of stopping the gate."""
    try:
        return fn(*args)
    except (MissingInput, SchemaError, NotImplementedError, OSError, ValueError, duckdb.Error) as exc:
        reason = _first_line(exc)
        return Check(check_id, "fail", f"could not run: {reason}", details=[f"Could not run: {reason}"])


def _require(present: set[str], *names: str) -> None:
    missing = [name for name in names if name not in present]
    if missing:
        raise MissingInput("missing " + ", ".join(f"data/agg/{name}.parquet" for name in missing))


def _query(con: duckdb.DuckDBPyConnection, name: str, **params: Any) -> list[dict]:
    result = con.execute(_sql(name), params)
    columns = [d[0] for d in result.description]
    return [dict(zip(columns, row)) for row in result.fetchall()]


def _sql(name: str) -> str:
    return (SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")


# --- tie-out -----------------------------------------------------------------

def check_tie_out(con: duckdb.DuckDBPyConnection, present: set[str], indicators_error: str | None) -> Check:
    if indicators_error:
        raise MissingInput(f"indicators not loaded: {indicators_error}")
    _require(present, "agg_zone_hour", "agg_vendor_month", "ref_indicators")
    exclusions = tie_out_exclusions()
    con.execute("CREATE OR REPLACE TABLE excluded_vendors (mode VARCHAR, vendor_id SMALLINT)")
    excluded = [[mode, vendor] for dataset, vendors in exclusions.items()
                for mode in DATASET_MODES[dataset] for vendor in vendors]
    if excluded:
        con.executemany("INSERT INTO excluded_vendors VALUES (?, ?)", excluded)
    exceptions = tie_out_exceptions()
    rows = _query(con, "tie_out", tolerance_pct=TIE_OUT_TOLERANCE_PCT)
    for r in rows:   # D27: a listed row is shown with its reason and doesn't gate; skipped stays skipped
        r["computed_status"] = r["status"]
        r["reason"] = exceptions.get((r["month"], r["license_class"]))
        if r["reason"] is not None and r["status"] != "skipped":
            r["status"] = "excepted"
    gated = [r for r in rows if r["license_class"] == GATED_LICENSE_CLASS]
    checked = [r for r in gated if r["status"] in ("pass", "fail")]
    failed = [r for r in gated if r["status"] == "fail"]
    if failed:
        head = (f"{len(failed)} of {len(checked)} {GATED_LICENSE_CLASS} months outside ±{TIE_OUT_TOLERANCE_PCT}%: "
                + _listing(f"{_m(r['month'])} ({_diff_label(r)})" for r in failed))
    elif checked:
        head = f"All {len(checked)} {GATED_LICENSE_CLASS} months with indicators within ±{TIE_OUT_TOLERANCE_PCT}%"
    else:
        head = f"No {GATED_LICENSE_CLASS} month to check"
    parts = [head]
    reported = [_reported_label(cls, [r for r in rows if r["license_class"] == cls])
                for cls in LICENSE_CLASSES if cls != GATED_LICENSE_CLASS]
    if any(reported):
        parts.append("reported, not gated (D27): " + ", ".join(label for label in reported if label))
    excepted = [r for r in rows if r["status"] == "excepted"]
    if excepted:
        parts.append("excepted (D27): " + _listing(f"{r['license_class']} {_m(r['month'])}" for r in excepted))
    skipped = _skipped_label(rows)
    if skipped:
        parts.append(skipped)
    summary = "; ".join(parts)

    rule = "; ".join(f"{dataset} vendor {', '.join(str(v) for v in vendors)}"
                     for dataset, vendors in exclusions.items() if vendors) or "none"
    details = [
        f"Pipeline trips per day against TLC's \"Trips Per Day\" in `ref_indicators`; a row passes within "
        f"±{TIE_OUT_TOLERANCE_PCT}%. Only {GATED_LICENSE_CLASS} (uber + lyft + other_hv) gates the check (D27). "
        "Yellow and Green rows carry their own pass/fail as information, reported, not gated, because TLC's cab "
        "figures follow counting rules the pipeline can't reproduce. A row listed in `tie_out_exceptions` "
        "(`config/sources.yaml`) is `excepted`: shown with its reason below, not gating.",
        "",
        "Records are `SUM(trips_all)` from `agg_zone_hour` (every row). The records of vendors listed in "
        "`tie_out_exclude_vendors` (`config/sources.yaml`, from `agg_vendor_month`) are taken out before dividing "
        f"by the days in the month (D25 mechanism, emptied by D27; now: {rule}); every metric keeps them. "
        "A month the indicators file doesn't have yet is skipped; a month with no pipeline trips fails.",
        "",
        "| Month | License class | Records | Excluded | Pipeline trips/day | TLC trips/day | Diff | Status |",
        "|---|---|---:|---:|---:|---:|---:|---|",
    ]
    details += [f"| {_m(r['month'])} | {r['license_class']} | {_num(r['records'])} | {_excluded_cell(r)} | "
                f"{_num(r['pipeline_trips_per_day'], 1)} | {_num(r['tlc_trips_per_day'], 1)} | "
                f"{_signed_pct(r['diff'])} | {_tie_out_status_cell(r)} |" for r in rows]
    if excepted:
        details += ["", "Exceptions (D27):", ""]
        for r in excepted:
            within = r["computed_status"] == "pass"
            result = (f"within ±{TIE_OUT_TOLERANCE_PCT}%, so the exception is no longer needed: remove it"
                      if within else f"outside ±{TIE_OUT_TOLERANCE_PCT}%")
            details.append(f"- {r['license_class']} {_m(r['month'])}: {_signed_pct(r['diff'])}, {result}. "
                           f"Reason: {r['reason']}.")
    matched = {(r["month"], r["license_class"]) for r in rows if r["reason"] is not None}
    unmatched = sorted(set(exceptions) - matched)
    if unmatched:
        details += ["", "Exceptions listed but not among the months checked: "
                    + ", ".join(f"{cls} {_m(month)}" for month, cls in unmatched) + "."]
    contract_rows = [{
        "month": r["month"].isoformat(),
        "license_class": r["license_class"],
        "pipeline_trips_per_day": _round(r["pipeline_trips_per_day"], 1),
        "tlc_trips_per_day": _round(r["tlc_trips_per_day"], 1),
        "diff": _round(r["diff"], 4),
        "status": r["status"],
    } for r in rows]
    return Check("tie_out", _rollup(r["status"] for r in gated if r["status"] != "excepted"),
                 summary, contract_rows, details)


def tie_out_exceptions() -> dict[tuple[date, str], str]:
    """Month × license class rows reported with their reason but not gating: ``tie_out_exceptions``
    in config/sources.yaml (D27), as ``{(month, license_class): reason}``. An entry without a
    ``YYYY-MM`` month, a known license class and a reason raises ``ValueError``."""
    exceptions = {}
    for entry in common.load_yaml("sources.yaml").get("tie_out_exceptions") or []:
        entry = entry if isinstance(entry, dict) else {}
        license_class, reason = entry.get("license_class"), entry.get("reason")
        if license_class not in LICENSE_CLASSES or not reason:
            raise ValueError(f"tie_out_exceptions in config/sources.yaml: {entry!r} needs month (YYYY-MM), "
                             f"license_class (one of {list(LICENSE_CLASSES)}) and reason")
        exceptions[(common.parse_month(str(entry.get("month"))), license_class)] = str(reason)
    return exceptions


def _reported_label(license_class: str, rows: list[dict]) -> str:
    """``Green 20 of 32 months outside ±2%`` or ``Yellow within ±2%``, for a class that doesn't gate."""
    checked = [r for r in rows if r["status"] in ("pass", "fail")]
    if not checked:
        return ""
    outside = sum(r["status"] == "fail" for r in checked)
    if not outside:
        return f"{license_class} within ±{TIE_OUT_TOLERANCE_PCT}%"
    return f"{license_class} {outside} of {len(checked)} months outside ±{TIE_OUT_TOLERANCE_PCT}%"


def _tie_out_status_cell(row: dict) -> str:
    if row["status"] == "fail" and row["license_class"] != GATED_LICENSE_CLASS:
        return "fail (reported, not gated)"
    return row["status"]


def tie_out_exclusions() -> dict[str, list[int]]:
    """Vendors whose records TLC's indicators don't count, by dataset: ``tie_out_exclude_vendors``
    in config/sources.yaml (D25). An unknown dataset or a non-integer vendor raises ``ValueError``."""
    exclusions = common.load_yaml("sources.yaml").get("tie_out_exclude_vendors") or {}
    unknown = sorted(set(exclusions) - set(DATASET_MODES))
    if unknown:
        raise ValueError(f"tie_out_exclude_vendors in config/sources.yaml names unknown datasets {unknown}")
    return {dataset: [int(vendor) for vendor in vendors or []] for dataset, vendors in exclusions.items()}


def _excluded_cell(row: dict) -> str:
    """Excluded records, naming the vendors; a dash for a class with none excluded."""
    vendors = row["excluded_vendor_ids"]
    if not vendors:
        return "—"
    return f"{row['excluded_records']:,} (vendor {', '.join(str(v) for v in vendors)})"


def _diff_label(row: dict) -> str:
    return "no pipeline trips" if row["records"] == 0 else _signed_pct(row["diff"])


def _skipped_label(rows: list[dict]) -> str:
    """``2026-08 skipped (not yet in indicators)``; names the classes when only some are missing."""
    classes = {r["license_class"] for r in rows}
    by_month: dict[date, list[str]] = {}
    for r in rows:
        if r["status"] == "skipped":
            by_month.setdefault(r["month"], []).append(r["license_class"])
    labels = [_m(month) if set(missing) == classes else f"{_m(month)} ({', '.join(missing)})"
              for month, missing in sorted(by_month.items())]
    return f"{_listing(labels)} skipped (not yet in indicators)" if labels else ""


# --- quality drift -----------------------------------------------------------

def check_quality(con: duckdb.DuckDBPyConnection, present: set[str]) -> Check:
    _require(present, "agg_quality_month")
    rows = sorted(_query(con, "quality", min_valid_pct=MIN_VALID_PCT, drift_points=DRIFT_POINTS),
                  key=lambda r: (r["month"], _mode_rank(r["mode"])))
    failed = [r for r in rows if r["status"] == "fail"]
    drifted = [r for r in rows if r["drift"]]
    if failed:
        head = (f"{len(failed)} of {len(rows)} month × mode rows below {MIN_VALID_PCT}% valid (D26): "
                + _listing(f"{r['mode']} {_m(r['month'])} ({_pct(r['valid_share'])})" for r in failed))
    elif rows:
        head = f"All {len(rows)} month × mode rows at least {MIN_VALID_PCT}% valid (D26)"
    else:
        head = "No rows in agg_quality_month for the months checked"
    if drifted:
        drift = (f"{len(drifted)} more than {DRIFT_POINTS} points below the mode's median (listed): "
                 + _listing(f"{r['mode']} {_m(r['month'])} ({r['points_below_median']:.2f} pts)" for r in drifted))
    else:
        drift = f"none more than {DRIFT_POINTS} points below its mode's median"
    summary = f"{head}; {drift}" if rows else head

    modes = _ordered_modes({r["mode"] for r in rows})
    cells = {(r["month"], r["mode"]): r for r in rows}
    medians = {r["mode"]: r["mode_median"] for r in rows}
    details = [
        f"`valid_rows / rows` per month × mode from `agg_quality_month`; a row fails below {MIN_VALID_PCT}% "
        "(D26, replacing SPEC §8's 95%: green's zero-mile records and yellow's fares of $0 or less are data "
        "quality, not pipeline faults). "
        f"A month more than {DRIFT_POINTS} percentage points below its mode's median over the months checked "
        "is listed (marked *drift*), not failed.",
        "",
        "| Month | " + " | ".join(modes) + " |",
        "|---|" + "---:|" * len(modes),
    ]
    for month in sorted({r["month"] for r in rows}):
        details.append(f"| {_m(month)} | " + " | ".join(_quality_cell(cells.get((month, mode))) for mode in modes) + " |")
    if rows:
        details.append("| median | " + " | ".join(_pct(medians[mode]) for mode in modes) + " |")
    contract_rows = [{"month": r["month"].isoformat(), "mode": r["mode"],
                      "valid_share": _round(r["valid_share"], 4), "status": r["status"]} for r in rows]
    return Check("quality_drift", _rollup(r["status"] for r in rows), summary, contract_rows, details)


def _quality_cell(row: dict | None) -> str:
    if row is None:
        return ""
    cell = _pct(row["valid_share"])
    if row["status"] == "fail":
        cell += " **fail**"
    if row["drift"]:
        cell += f" *drift −{row['points_below_median']:.2f} pts*"
    return cell


# --- CBD list ----------------------------------------------------------------

def check_cbd(con: duckdb.DuckDBPyConnection, present: set[str], periods: dict, months: list[str]) -> Check:
    _require(present, "agg_cbd_pairs")
    fee_from, cbd_from = _pricing_months(periods)
    lists = {name: sorted(zones.cbd_zone_ids(name)) for name in ZONE_LISTS}
    empty = [name for name, ids in lists.items() if not ids]
    if empty:
        raise ValueError(f"CBD zone list {', '.join(empty)} is empty")
    con.execute("CREATE OR REPLACE TABLE cbd_zones (zone_list VARCHAR, zone INTEGER)")
    con.executemany("INSERT INTO cbd_zones VALUES (?, ?)", [[name, z] for name, ids in lists.items() for z in ids])
    rows = _query(con, "cbd_list", cbd_from=cbd_from, min_both_in_pct=CBD_BOTH_IN_MIN_PCT)

    totals = {r["zone_list"]: r for r in rows if r["level"] == "total"}
    by_month = [r for r in rows if r["level"] == "month"]
    window = sorted({r["month"] for r in by_month})
    left_out = [m for m in months if fee_from <= common.parse_month(m) < cbd_from]
    total_rows = [totals.get(name) or _no_cbd_trips(name) for name in ZONE_LISTS]

    if not window:
        summary = f"No trips in agg_cbd_pairs from {_m(cbd_from)} on"
    else:
        parts = []
        for r in total_rows:
            if r["status"] == "skipped":
                parts.append(f"{r['zone_list']}: no both-in trips")
                continue
            below = f" (below {CBD_BOTH_IN_MIN_PCT}%)" if r["status"] == "fail" else ""
            gate = "" if r["zone_list"] == GATED_ZONE_LIST else " (reported, not gated)"
            parts.append(f"{r['zone_list']}{gate}: {_pct(r['both_in_fee_share'])} of both-in trips carry a fee{below}, "
                         f"pass-through {_pct(r['neither_in_fee_share'])}")
        summary = "; ".join(parts) + f" ({_m(window[0])} → {_m(window[-1])})"

    lead = (f"From `agg_cbd_pairs`, months {_m(window[0])} → {_m(window[-1])}." if window
            else f"No rows in `agg_cbd_pairs` from {_m(cbd_from)} on.")
    if left_out:
        lead += (f" {', '.join(left_out)} left out: congestion pricing began on {periods['congestion_pricing_start']}, "
                 "and the table has no day grain to drop the trips before it.")
    details = [
        lead + f" Both-in: pickup and drop-off zones both in the list; passes when at least "
        f"{CBD_BOTH_IN_MIN_PCT}% carry a fee (`cbd_fee > 0`). Only the {GATED_ZONE_LIST} list gates the check "
        "(D21); the other list's result is reported, since its borderline zones lie mostly outside the "
        "charge zone. Pass-through: neither zone in the list; reported, not failed. "
        "Zone lists from `pipeline.zones.cbd_zone_ids`: "
        + ", ".join(f"{name} {len(ids)} zones" for name, ids in lists.items()) + ".",
        "",
        "| Zone list | Both-in trips | With fee | Share | Pass-through trips | With fee | Share | Status |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    details += [f"| {r['zone_list']} | {_num(r['both_in_trips'])} | {_num(r['both_in_fee_trips'])} | "
                f"{_pct(r['both_in_fee_share'])} | {_num(r['neither_in_trips'])} | {_num(r['neither_in_fee_trips'])} | "
                f"{_pct(r['neither_in_fee_share'])} | {r['status']} |" for r in total_rows]
    by_mode = sorted((r for r in rows if r["level"] == "mode"),
                     key=lambda r: (r["zone_list"], _mode_rank(r["mode"])))
    if by_mode:
        details += ["", "By mode:", "",
                    "| Zone list | Mode | Both-in trips | Share with fee | Pass-through trips | Share with fee |",
                    "|---|---|---:|---:|---:|---:|"]
        details += [f"| {r['zone_list']} | {r['mode']} | {_num(r['both_in_trips'])} | {_pct(r['both_in_fee_share'])} | "
                    f"{_num(r['neither_in_trips'])} | {_pct(r['neither_in_fee_share'])} |" for r in by_mode]
    low = [r for r in by_month if r["status"] == "fail"]
    details += ["", (f"Months below {CBD_BOTH_IN_MIN_PCT}% (listed; the check is on the totals): "
                     + ", ".join(f"{r['zone_list']} {_m(r['month'])} ({_pct(r['both_in_fee_share'])})" for r in low))
                if low else f"No single month below {CBD_BOTH_IN_MIN_PCT}% on either list."]
    contract_rows = [{"zone_list": r["zone_list"], "both_in_fee_share": _round(r["both_in_fee_share"], 4),
                      "neither_in_fee_share": _round(r["neither_in_fee_share"], 4), "status": r["status"]}
                     for r in total_rows]
    gated = (r["status"] for r in total_rows if r["zone_list"] == GATED_ZONE_LIST)
    return Check("cbd_list", _rollup(gated), summary, contract_rows, details)


def _no_cbd_trips(zone_list: str) -> dict:
    return {"zone_list": zone_list, "both_in_trips": 0, "both_in_fee_trips": 0, "both_in_fee_share": None,
            "neither_in_trips": 0, "neither_in_fee_trips": 0, "neither_in_fee_share": None, "status": "skipped"}


def _pricing_months(periods: dict) -> tuple[date, date]:
    """(month containing congestion_pricing_start, first month wholly after it)."""
    start = periods["congestion_pricing_start"]
    first = date(start.year, start.month, 1)
    if start.day == 1:
        return first, first
    return first, date(first.year + first.month // 12, first.month % 12 + 1, 1)


# --- schema ------------------------------------------------------------------

def check_schema(months: list[str]) -> Check:
    datasets = list(common.load_yaml("sources.yaml")["datasets"])
    schema_map = load_schema_map()
    files = discover.discover(datasets, months)
    problems = discover.check(files, schema_map)
    local = sum(f.source == "local" for f in files)
    lead = (f"Footers of {len(files)} trip files ({local} local, {len(files) - local} read over HTTP, D11) "
            "checked against `config/schema_map.yaml` by `pipeline.discover`, the same check as "
            "`python -m pipeline.discover --check`.")
    if problems:
        summary = f"{len(problems)} problems in {len(files)} files: " + _listing(problems)
        details = [lead, ""] + [f"- {p}" for p in problems]
    else:
        summary = f"{len(files)} files, no unmapped, missing or mistyped columns"
        details = [lead, "", "No problems."]
    return Check("schema", "fail" if problems else "pass", summary, [], details)


# --- fees --------------------------------------------------------------------

def check_fees(con: duckdb.DuckDBPyConnection, present: set[str], periods: dict) -> Check:
    _require(present, "agg_fee_values")
    fee_from, _ = _pricing_months(periods)
    fees = periods["fees"]
    rows = _query(con, "fees", fee_from=fee_from, fee_hvfhv=fees["cbd_fee_hvfhv"], fee_taxi=fees["cbd_fee_taxi"],
                  min_exact_pct=FEE_EXACT_MIN_PCT)
    per_mode = sorted((r for r in rows if r["level"] == "mode"), key=lambda r: _mode_rank(r["mode"]))
    others = {r["mode"]: [] for r in per_mode}
    for r in rows:   # value rows come largest first; status 'fail' means not the configured fee
        if r["level"] == "value" and r["exact_trips"] == 0:
            others[r["mode"]].append(r)

    failed = [r for r in per_mode if r["status"] == "fail"]
    if failed:
        summary = (f"{len(failed)} of {len(per_mode)} modes below {FEE_EXACT_MIN_PCT}% at the configured fee: "
                   + _listing(f"{r['mode']} {_pct(r['exact_share'])} at {_money(r['configured_fee'])}" for r in failed))
    elif per_mode:
        summary = (", ".join(f"{r['mode']} {_pct(r['exact_share'])}" for r in per_mode)
                   + f" of trips with a CBD fee carry the configured fee (at least {FEE_EXACT_MIN_PCT}%)")
    else:
        summary = f"No trips with a CBD fee in agg_fee_values from {_m(fee_from)} on"

    details = [
        f"From `agg_fee_values`, months from {_m(fee_from)} (congestion pricing began on "
        f"{periods['congestion_pricing_start']}). Of trips with `cbd_fee > 0`, the share carrying exactly the "
        f"configured fee for the mode ({_money(fees['cbd_fee_hvfhv'])} ride-hail, {_money(fees['cbd_fee_taxi'])} "
        f"cabs, `config/periods.yaml`); passes at {FEE_EXACT_MIN_PCT}% or more.",
        "",
        "| Mode | Configured fee | Trips with a fee | At configured fee | Share | Status |",
        "|---|---:|---:|---:|---:|---|",
    ]
    details += [f"| {r['mode']} | {_money(r['configured_fee'])} | {_num(r['fee_trips'])} | {_num(r['exact_trips'])} | "
                f"{_pct(r['exact_share'])} | {r['status']} |" for r in per_mode]
    if any(others.values()):
        details += ["", "Other values found:", "", "| Mode | cbd_fee | Trips |", "|---|---:|---:|"]
        for mode, values in others.items():
            details += [f"| {mode} | {v['cbd_fee']} | {_num(v['fee_trips'])} |" for v in values[:MAX_OTHER_VALUES]]
            if len(values) > MAX_OTHER_VALUES:
                details.append(f"| {mode} | and {len(values) - MAX_OTHER_VALUES} more values | |")
    else:
        details += ["", "No other values found."]
    low = [r for r in rows if r["level"] == "month" and r["status"] == "fail"]
    details += ["", (f"Months below {FEE_EXACT_MIN_PCT}% (listed; the check is on each mode's total): "
                     + ", ".join(f"{r['mode']} {_m(r['month'])} ({_pct(r['exact_share'])})" for r in low))
                if low else f"No single month below {FEE_EXACT_MIN_PCT}% for any mode."]
    contract_rows = [{
        "mode": r["mode"],
        "configured_fee": r["configured_fee"],
        "exact_share": _round(r["exact_share"], 4),
        "other_values": [{"cbd_fee": v["cbd_fee"], "trips": v["fee_trips"]} for v in others[r["mode"]][:MAX_OTHER_VALUES]],
        "status": r["status"],
    } for r in per_mode]
    return Check("fees", _rollup(r["status"] for r in per_mode), summary, contract_rows, details)


# --- summary and report ------------------------------------------------------

def build_summary(checks: list[Check], months: list[str], now: datetime) -> dict:
    """``validation_summary.json`` (contracts/README.md §5): ``pass`` only when every check passes."""
    statuses = [c.status for c in checks]
    status = "fail" if "fail" in statuses else "pass" if set(statuses) == {"pass"} else "skipped"
    summary = {
        "generated_at": _utc(now),
        "status": status,
        "months_checked": months,
        "checks": [{"id": c.id, "status": c.status, "summary": c.summary} for c in checks],
    }
    by_id = {c.id: c for c in checks}
    for check_id, key in ROWS_KEY.items():
        summary[key] = by_id[check_id].rows
    return summary


def render_report(summary: dict, checks: list[Check], now: datetime) -> str:
    lines = [
        "# Validation report",
        "",
        f"Generated {now.astimezone(timezone.utc):%Y-%m-%d %H:%M} UTC by `make validate` (`pipeline/validate.py`). "
        "Don't edit by hand. SPEC §8 and §7.2 set the checks; the thresholds are never widened to pass.",
        "",
        f"**Status: {summary['status'].upper()}** · months checked: {_months_label(summary['months_checked'])}",
        "",
        "| Check | Status | Summary |",
        "|---|---|---|",
    ]
    lines += [f"| {CHECKS[c.id]} | {c.status.upper()} | {c.summary} |" for c in checks]
    for c in checks:
        lines += ["", f"## {CHECKS[c.id]}", "", f"**{c.status.upper()}**: {c.summary}", "", *c.details]
    return "\n".join(lines) + "\n"


def _write_json_atomic(path: Path, doc: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(doc, indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


# --- helpers -----------------------------------------------------------------

def _rollup(statuses: Iterable[str]) -> str:
    """A check's status from its rows: any fail fails; else pass if any row passed; else skipped."""
    statuses = set(statuses)
    if "fail" in statuses:
        return "fail"
    return "pass" if "pass" in statuses else "skipped"


def _mode_rank(mode: str) -> tuple[int, str]:
    return (common.MODES.index(mode), "") if mode in common.MODES else (len(common.MODES), mode)


def _ordered_modes(modes: set[str]) -> list[str]:
    return sorted(modes, key=_mode_rank)


def _listing(items: Iterable[str]) -> str:
    items = list(items)
    shown = ", ".join(items[:MAX_LISTED])
    return shown + (f" and {len(items) - MAX_LISTED} more" if len(items) > MAX_LISTED else "")


def _months_label(months: list[str]) -> str:
    if not months:
        return "none"
    if months == common.month_range(months[0], months[-1]):
        return f"{months[0]} → {months[-1]} ({len(months)} months)"
    return ", ".join(months)


def _m(month: date) -> str:
    return common.format_month(month)


def _round(value: Any, digits: int) -> float | None:
    return None if value is None else round(float(value), digits)


def _num(value: Any, digits: int = 0) -> str:
    return "" if value is None else f"{float(value):,.{digits}f}"


def _pct(value: Any) -> str:
    return "" if value is None else f"{float(value) * 100:.2f}%"


def _signed_pct(value: Any) -> str:
    return "" if value is None else f"{float(value) * 100:+.2f}%"


def _money(value: Any) -> str:
    return "" if value is None else f"${float(value):.2f}"


def _utc(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _first_line(exc: BaseException) -> str:
    text = str(exc).strip()
    return text.splitlines()[0] if text else type(exc).__name__


def _display(path: Path) -> str:
    try:
        return str(path.relative_to(common.REPO_ROOT))
    except ValueError:
        return str(path)


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.validate", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--indicators-only", action="store_true",
                        help="load data/ref/data_reports_monthly.csv into data/agg/ref_indicators.parquet and stop")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.indicators_only:
        con = common.connect()
        try:
            path = load_ref_indicators(con)
        except (OSError, ValueError, duckdb.Error) as exc:
            print(f"ref_indicators: {_first_line(exc)}", file=sys.stderr)
            raise SystemExit(1)
        rows, first, last = con.execute(f"SELECT COUNT(*), MIN(\"Year/Month\"), MAX(\"Year/Month\") "
                                        f"FROM read_parquet({common.sql_literal(str(path))})").fetchone()
        print(f"wrote {path}: {rows} rows, {first} → {last}")
        return

    summary = run()
    for check in summary["checks"]:
        print(f"{check['status']:<7} {check['id']}: {check['summary']}")
    print(f"validation {summary['status']}: wrote {_display(REPORT_PATH)} and {summary_path()}")
    raise SystemExit(0 if summary["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
