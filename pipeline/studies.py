"""Tables for the congestion-pricing and pay-rise write-ups in reports/.

``python -m pipeline.studies`` runs the five policy metrics (cp_effect, cp_effect_summary,
cp_weekly_trips, cp_zone_change, pay_event) over the aggregates and rewrites the generated
blocks of reports/congestion_pricing.md and reports/pay_rise.md: everything between
``<!-- BEGIN generated: NAME -->`` and ``<!-- END generated: NAME -->``. The narrative around
the blocks is written by hand and left alone. The same aggregates give the same reports.

``--holidays`` recomputes the US federal holidays that fall in different ISO weeks in 2024 and
2025 and writes them to config/periods.yaml (``excluded_holiday_weeks``). cp_effect.sql and
cp_effect_summary.sql mirror that list (metrics read only the aggregate tables), and
tests/test_cp_effect.py checks the three agree. A report run stops if periods.yaml is stale.

Lane L10 · SPEC §6, §12 · decisions D7, D9, D12, D21 · docs/lanes/L10-policy-studies.md
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import statistics
import sys
from datetime import date, timedelta
from pathlib import Path

import pyarrow as pa

from pipeline import common, metrics

BASE_YEAR, STUDY_YEAR = 2024, 2025   # the congestion effect: 2025 ISO weeks against 2024's (SPEC §6)
HOLIDAYS_KEY = "excluded_holiday_weeks"
HOLIDAYS_BEGIN = (f"# BEGIN {HOLIDAYS_KEY}: written by `python -m pipeline.studies --holidays` (lane L10). "
                  "Don't edit by hand.")
HOLIDAYS_END = f"# END {HOLIDAYS_KEY}"

METRICS = ("cp_effect", "cp_effect_summary", "cp_weekly_trips", "cp_zone_change", "pay_event")
CP_REPORT, PAY_REPORT = "congestion_pricing.md", "pay_rise.md"
HEADLINE_LIST, SENSITIVITY_LIST = "core", "wide"     # D21: core is the headline; wide is the sensitivity result
ZONE_MIN_TRIPS_PER_DAY = 100                         # zone-change tables skip zones smaller than this in 2024

MODE_LABELS = {"all": "All modes", "ride_hail": "Ride-hail", "taxi": "Cabs", "uber": "Uber", "lyft": "Lyft",
               "other_hv": "Other ride-hail", "yellow": "Yellow cab", "green": "Green cab"}
CP_METRICS = {"trips": "Trips", "fare_per_mile": "Base fare per mile",
              "driver_share": "Driver share of base fare"}
PAY_MEASURES = {"pay_per_mile": "Driver pay per mile", "pay_per_min": "Driver pay per minute with a passenger",
                "fare_per_mile": "Base fare per mile"}

_BLOCK_RE = re.compile(r"(<!-- BEGIN generated: (?P<name>[\w-]+) -->\n).*?(<!-- END generated: (?P=name) -->)",
                       re.S)


# --- holiday weeks -----------------------------------------------------------

def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The ``n``-th ``weekday`` (Monday = 0) of the month; ``n = -1`` is the last."""
    if n > 0:
        first = date(year, month, 1)
        return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))
    last = date(year + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """A holiday on a Saturday is observed on the Friday before; on a Sunday, the Monday after."""
    return day + timedelta(days={5: -1, 6: 1}.get(day.weekday(), 0))


def federal_holidays(year: int) -> list[tuple[str, date]]:
    """The eleven US federal holidays (5 U.S.C. § 6103) as observed in ``year``, in calendar order."""
    mon, thu = 0, 3
    return [
        ("New Year's Day", _observed(date(year, 1, 1))),
        ("Martin Luther King Jr. Day", _nth_weekday(year, 1, mon, 3)),
        ("Washington's Birthday", _nth_weekday(year, 2, mon, 3)),
        ("Memorial Day", _nth_weekday(year, 5, mon, -1)),
        ("Juneteenth", _observed(date(year, 6, 19))),
        ("Independence Day", _observed(date(year, 7, 4))),
        ("Labor Day", _nth_weekday(year, 9, mon, 1)),
        ("Columbus Day", _nth_weekday(year, 10, mon, 2)),
        ("Veterans Day", _observed(date(year, 11, 11))),
        ("Thanksgiving Day", _nth_weekday(year, 11, thu, 4)),
        ("Christmas Day", _observed(date(year, 12, 25))),
    ]


def _day_label(day: date) -> str:
    return f"{day:%a} {day.day} {day:%b}"


def holiday_weeks(base_year: int = BASE_YEAR, study_year: int = STUDY_YEAR) -> list[dict]:
    """ISO weeks to leave out of the year-over-year comparison (SPEC §6).

    A holiday in ISO week ``a`` of ``base_year`` and week ``b`` of ``study_year`` (a ≠ b) spoils
    both weeks: week ``a`` compares a holiday week with an ordinary one, week ``b`` the reverse.
    Returns one ``{iso_week, holiday, reason}`` per week and holiday, sorted by week."""
    weeks = []
    for (name, base_day), (_, study_day) in zip(federal_holidays(base_year), federal_holidays(study_year)):
        base_iso, study_iso = base_day.isocalendar(), study_day.isocalendar()
        if (base_iso.year, study_iso.year) != (base_year, study_year):
            raise ValueError(f"{name} falls outside its ISO year ({base_day}, {study_day}); "
                             "holiday_weeks only handles holidays inside the two ISO years")
        if base_iso.week == study_iso.week:
            continue
        reason = (f"{name} is in ISO week {base_iso.week} in {base_year} ({_day_label(base_day)}) "
                  f"and week {study_iso.week} in {study_year} ({_day_label(study_day)})")
        weeks += [{"iso_week": week, "holiday": name, "reason": reason} for week in (base_iso.week, study_iso.week)]
    return sorted(weeks, key=lambda w: (w["iso_week"], w["holiday"]))


def holidays_block(weeks: list[dict]) -> str:
    """The ``excluded_holiday_weeks`` key as YAML text, between its BEGIN and END marker lines."""
    lines = [
        HOLIDAYS_BEGIN,
        f"# {STUDY_YEAR} ISO weeks left out of the congestion effect (SPEC §6): each US federal holiday that",
        f"# falls in different ISO weeks in {BASE_YEAR} and {STUDY_YEAR} removes both weeks. sql/metrics/cp_effect.sql",
        "# and cp_effect_summary.sql mirror this list; tests/test_cp_effect.py checks they match.",
        f"{HOLIDAYS_KEY}:",
    ]
    for week in weeks:   # JSON strings are valid YAML scalars
        lines += [f"  - iso_week: {week['iso_week']}",
                  f"    holiday: {json.dumps(week['holiday'])}",
                  f"    reason: {json.dumps(week['reason'], ensure_ascii=False)}"]
    if not weeks:
        lines[-1] += " []"
    return "\n".join([*lines, HOLIDAYS_END]) + "\n"


def write_holidays(path: Path | None = None) -> list[dict]:
    """Recompute the holiday weeks and write them to ``periods.yaml``, leaving its other keys alone."""
    path = path or common.CONFIG_DIR / "periods.yaml"
    weeks = holiday_weeks()
    text = path.read_text(encoding="utf-8")
    block = holidays_block(weeks)
    if HOLIDAYS_BEGIN in text:
        start = text.index(HOLIDAYS_BEGIN)
        end = text.index(HOLIDAYS_END, start) + len(HOLIDAYS_END)
        text = text[:start] + block.rstrip("\n") + text[end:]
    else:
        text = text.rstrip("\n") + "\n\n" + block
    path.write_text(text, encoding="utf-8")
    return weeks


def configured_holiday_weeks() -> list[dict]:
    """``excluded_holiday_weeks`` as config/periods.yaml holds it now."""
    return common.load_yaml("periods.yaml").get(HOLIDAYS_KEY) or []


# --- formatting --------------------------------------------------------------

def _minus(text: str) -> str:
    return text.replace("-", "−")


def _pct(value: float | None) -> str:
    """A relative change or effect: signed percent, 1 decimal (contracts/README.md §3)."""
    return "—" if value is None else _minus(f"{value * 100:+.1f}%")


def _pts(value: float | None) -> str:
    return "—" if value is None else _minus(f"{value * 100:+.1f} pts")


def _share(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def _usd(value: float | None) -> str:
    """Dollars per mile or minute, 3 decimals: a 5% pay rise moves pay per minute by about 3 cents."""
    return "—" if value is None else f"${value:.3f}"


def _count(value: float | None) -> str:
    return "—" if value is None else f"{value:,.0f}"


def _day(value: date) -> str:
    return f"{value.day} {value:%b %Y}"


def _week(iso_week: int) -> str:
    return f"W{iso_week:02d}"


def _iso_monday(iso_year: int, iso_week: int) -> date:
    return date.fromisocalendar(iso_year, iso_week, 1)


def _table(headers: list[str], rows: list[list[str]], right: set[int] = frozenset()) -> str:
    """A Markdown table; columns listed in ``right`` are right-aligned."""
    if not rows:
        return "_No rows._"
    rule = ["---:" if i in right else "---" for i in range(len(headers))]
    return "\n".join("| " + " | ".join(cells) + " |" for cells in [headers, rule, *rows])


def _details(summary: str, body: str) -> str:
    return f"<details>\n<summary>{summary}</summary>\n\n{body}\n\n</details>"


def _modes_in(rows: list[dict]) -> list[str]:
    present = {row["mode"] for row in rows}
    return [mode for mode in MODE_LABELS if mode in present]


# --- inputs ------------------------------------------------------------------

def run_metrics() -> dict[str, pa.Table]:
    """The five policy metrics over the aggregates in ``NYC_DATA_DIR``."""
    return {name: metrics.run(name) for name in METRICS}


def provenance() -> str:
    """Which aggregates the tables come from, and whether the validation gate passed on them."""
    with metrics.connect() as con:
        spans = {table: con.execute(f"SELECT min(month), max(month) FROM {table}").fetchone()
                 for table in ("agg_week_cbd", "agg_zone_hour")}
    summary = common.agg_dir() / "validation_summary.json"
    status = json.loads(summary.read_text(encoding="utf-8")).get("status", "unknown") if summary.is_file() else "not run"
    parts = [f"`{table}` {common.format_month(first)} to {common.format_month(last)}"
             for table, (first, last) in spans.items() if first is not None]
    return (f"Generated by `python -m pipeline.studies` from {' and '.join(parts) or 'empty aggregates'}. "
            f"Validation gate (`make validate`): **{status}**.")


def _zone_names() -> dict[int, str]:
    lookup = common.ref_dir() / "taxi_zone_lookup.csv"
    if not lookup.is_file():
        return {}
    with open(lookup, encoding="utf-8", newline="") as f:
        return {int(row["LocationID"]): row["Zone"] for row in csv.DictReader(f)}


def _zone_lists() -> dict[int, str]:
    """``core`` for zones in the core list, ``wide`` for borderline zones (D9)."""
    return {int(row["LocationID"]): "wide" if row["borderline"].strip().lower() == "true" else "core"
            for row in common.load_csv("cbd_zones.csv")}


# --- congestion-pricing report -----------------------------------------------

def _effects_core(summary: list[dict]) -> str:
    rows = [[CP_METRICS[metric], MODE_LABELS[row["mode"]], _pct(row["median"]), _pct(row["p10"]),
             _pct(row["p90"]), str(row["weeks"])]
            for metric in CP_METRICS for row in summary
            if row["metric"] == metric and row["zone_list"] == HEADLINE_LIST]
    order = list(MODE_LABELS.values())
    rows.sort(key=lambda r: (list(CP_METRICS.values()).index(r[0]), order.index(r[1])))
    return _table(["Metric", "Mode", "Median weekly effect", "p10", "p90", "Weeks"], rows, {2, 3, 4, 5})


def _effects_wide(summary: list[dict]) -> str:
    core = {(r["metric"], r["mode"]): r for r in summary if r["zone_list"] == HEADLINE_LIST}
    rows = []
    for metric in CP_METRICS:
        wide = {r["mode"]: r for r in summary if r["metric"] == metric and r["zone_list"] == SENSITIVITY_LIST}
        for mode in [m for m in MODE_LABELS if m in wide]:
            w, c = wide[mode], core.get((metric, mode), {})
            gap = None if w["median"] is None or c.get("median") is None else w["median"] - c["median"]
            rows.append([CP_METRICS[metric], MODE_LABELS[mode], _pct(c.get("median")), _pct(w["median"]),
                         _pct(w["p10"]), _pct(w["p90"]), str(w["weeks"]), _pts(gap)])
    return _table(["Metric", "Mode", "Core median", "Wide median", "Wide p10", "Wide p90", "Wide weeks",
                   "Wide − core"], rows, {2, 3, 4, 5, 6, 7})


def _weekly_effects(effects: list[dict]) -> str:
    core = [r for r in effects if r["zone_list"] == HEADLINE_LIST]
    parts = []
    for metric, label in CP_METRICS.items():
        rows = [r for r in core if r["metric"] == metric]
        modes = _modes_in(rows)
        cells = {(r["iso_week"], r["mode"]): r for r in rows}
        weeks = sorted({(r["iso_week"], r["week_start"], r["exclusion_reason"]) for r in rows})
        body = [[_week(week), _day(start), *[_pct(cells[(week, m)]["effect"]) if (week, m) in cells else "—"
                                             for m in modes], "excluded" if reason else ""]
                for week, start, reason in weeks]
        table = _table(["ISO week", "Week of", *[MODE_LABELS[m] for m in modes], ""], body,
                       set(range(2, 2 + len(modes))))
        parts.append(_details(f"{label}: estimated effect by week, core list", table))
    return "\n\n".join(parts)


def _weekly_trips(weekly: list[dict]) -> str:
    core = [r for r in weekly if r["zone_list"] == HEADLINE_LIST]
    parts = []
    for mode in _modes_in(core):
        cells = {(r["iso_year"], r["iso_week"], r["cbd_group"]): r["trips_per_day"]
                 for r in core if r["mode"] == mode}
        weeks = sorted({week for _, week, _ in cells})
        body = [[_week(w), *[_count(cells.get((year, w, group))) for group in ("treated", "control")
                             for year in (BASE_YEAR, STUDY_YEAR)]] for w in weeks]
        table = _table(["ISO week", f"Treated {BASE_YEAR}", f"Treated {STUDY_YEAR}", f"Control {BASE_YEAR}",
                        f"Control {STUDY_YEAR}"], body, {1, 2, 3, 4})
        parts.append(_details(f"{MODE_LABELS[mode]}: trips per day, core list", table))
    return "\n\n".join(parts) or "_No rows._"


def _excluded_weeks(effects: list[dict]) -> str:
    start = common.load_yaml("periods.yaml")["congestion_pricing_start"]
    rows = [[_week(1), _day(_iso_monday(STUDY_YEAR, 1)),
             f"Left out by design (D12): pricing began on its last day ({_day_label(start)})"]]
    excluded = sorted({(r["iso_week"], r["week_start"], r["exclusion_reason"]) for r in effects if r["excluded"]})
    rows += [[_week(week), _day(start), reason] for week, start, reason in excluded]
    return _table(["ISO week", f"Week of ({STUDY_YEAR})", "Why"], rows)


def _holidays() -> str:
    excluded = {w["holiday"] for w in holiday_weeks()}
    rows = []
    for (name, base_day), (_, study_day) in zip(federal_holidays(BASE_YEAR), federal_holidays(STUDY_YEAR)):
        rows.append([name, f"{_day_label(base_day)} ({_week(base_day.isocalendar().week)})",
                     f"{_day_label(study_day)} ({_week(study_day.isocalendar().week)})",
                     "both weeks excluded" if name in excluded else "same week: kept"])
    return _table(["Federal holiday", str(BASE_YEAR), str(STUDY_YEAR), "Effect on the study"], rows)


def _zone_change(zones: list[dict]) -> str:
    names, lists = _zone_names(), _zone_lists()
    big = [z for z in zones if z["change"] is not None and z["trips_per_day_2024"] >= ZONE_MIN_TRIPS_PER_DAY]

    def rows(selected: list[dict]) -> list[list[str]]:
        return [[str(z["pu_zone"]), names.get(z["pu_zone"], "—"), lists.get(z["pu_zone"], "—"),
                 _count(z["trips_per_day_2024"]), _count(z["trips_per_day_2025"]), _pct(z["change"])]
                for z in selected]

    headers = ["Zone", "Name", "Zone list", f"Pickups/day {BASE_YEAR}", f"Pickups/day {STUDY_YEAR}", "Change"]
    falls = sorted(big, key=lambda z: (z["change"], z["pu_zone"]))[:10]
    rises = sorted(big, key=lambda z: (-z["change"], z["pu_zone"]))[:10]
    return (f"{len(big)} zones had at least {ZONE_MIN_TRIPS_PER_DAY} pickups a day in {BASE_YEAR}.\n\n"
            f"**Largest falls**\n\n{_table(headers, rows(falls), {3, 4, 5})}\n\n"
            f"**Largest rises**\n\n{_table(headers, rows(rises), {3, 4, 5})}")


def congestion_blocks(results: dict[str, pa.Table], source: str) -> dict[str, str]:
    effects = results["cp_effect"].to_pylist()
    summary = results["cp_effect_summary"].to_pylist()
    return {
        "provenance": source,
        "effects_core": _effects_core(summary),
        "effects_wide": _effects_wide(summary),
        "weekly_effects": _weekly_effects(effects),
        "weekly_trips": _weekly_trips(results["cp_weekly_trips"].to_pylist()),
        "excluded_weeks": _excluded_weeks(effects),
        "holidays": _holidays(),
        "zone_change": _zone_change(results["cp_zone_change"].to_pylist()),
    }


# --- pay-rise report ---------------------------------------------------------

def before_after(rows: list[dict], mode: str, measure: str, year: int) -> tuple[float | None, float | None]:
    """Median weekly value in the 12 weeks before and the 12 weeks after the transition week (D12)."""
    def median(after: bool) -> float | None:
        values = [r[measure] for r in rows if r["mode"] == mode and r["year"] == year and not r["transition"]
                  and r[measure] is not None and (r["week_offset"] > 0) == after]
        return statistics.median(values) if values else None
    return median(False), median(True)


def _ratio(after: float | None, before: float | None) -> float | None:
    return None if after is None or not before else after / before - 1


def _pay_summary(event: list[dict]) -> str:
    rows = []
    for mode in [m for m in ("ride_hail", "uber", "lyft") if any(r["mode"] == m for r in event)]:
        for measure, label in PAY_MEASURES.items():
            before_now, after_now = before_after(event, mode, measure, STUDY_YEAR)
            before_ref, after_ref = before_after(event, mode, measure, BASE_YEAR)
            change_now, change_ref = _ratio(after_now, before_now), _ratio(after_ref, before_ref)
            adjusted = None if change_now is None or change_ref is None else (1 + change_now) / (1 + change_ref) - 1
            rows.append([MODE_LABELS[mode], label, _usd(before_now), _usd(after_now), _pct(change_now),
                         _usd(before_ref), _usd(after_ref), _pct(change_ref), _pct(adjusted)])
    return _table(["Mode", "Measure", f"{STUDY_YEAR} before", f"{STUDY_YEAR} after", f"{STUDY_YEAR} change",
                   f"{BASE_YEAR} before", f"{BASE_YEAR} after", f"{BASE_YEAR} change",
                   f"Change net of {BASE_YEAR}"], rows, set(range(2, 9)))


def _pay_weekly(event: list[dict]) -> str:
    def table(mode: str) -> str:
        cells = {(r["year"], r["week_offset"]): r for r in event if r["mode"] == mode}
        body = []
        for offset in sorted({o for _, o in cells}):
            now, ref = cells.get((STUDY_YEAR, offset), {}), cells.get((BASE_YEAR, offset), {})
            start = now.get("week_start")
            body.append([_minus(f"{offset:+d}") if offset else "0",
                         _week(start.isocalendar().week) if start else "—", _day(start) if start else "—",
                         *[_usd(row.get(m)) for m in PAY_MEASURES for row in (now, ref)],
                         "transition" if now.get("transition") else ""])
        headers = ["Offset", "ISO week", f"Week of ({STUDY_YEAR})"]
        headers += [f"{short} {year}" for short in ("Pay/mile", "Pay/min", "Fare/mile") for year in (STUDY_YEAR, BASE_YEAR)]
        return _table([*headers, ""], body, set(range(3, 9)))

    modes = [m for m in ("ride_hail", "uber", "lyft") if any(r["mode"] == m for r in event)]
    if not modes:
        return "_No rows._"
    parts = [f"**{MODE_LABELS[modes[0]]}**\n\n{table(modes[0])}"]
    parts += [_details(f"{MODE_LABELS[m]}", table(m)) for m in modes[1:]]
    return "\n\n".join(parts)


def _pay_weeks(event: list[dict]) -> str:
    rows = []
    for year in (STUDY_YEAR, BASE_YEAR):
        offsets = sorted({r["week_offset"] for r in event if r["year"] == year})
        if not offsets:
            continue
        first = min(r["week_start"] for r in event if r["year"] == year)
        last = max(r["week_start"] for r in event if r["year"] == year)
        missing = sorted({r["week_offset"] for r in event if r["year"] == year
                          and r["mode"] == "ride_hail" and r["pay_per_mile"] is None})
        transition = next(r["week_start"] for r in event if r["year"] == year and r["transition"])
        rows.append([str(year), f"{_week(first.isocalendar().week)} to {_week(last.isocalendar().week)}",
                     f"{_day(first)} to {_day(last + timedelta(days=6))}",
                     f"{_week(transition.isocalendar().week)} (week of {_day(transition)})",
                     ", ".join(_minus(f"{o:+d}") for o in missing) or "none"])
    return _table(["Year", "ISO weeks", "Dates", "Left out of before/after (transition)",
                   "Offsets with no ride-hail data"], rows)


def pay_blocks(results: dict[str, pa.Table], source: str) -> dict[str, str]:
    event = results["pay_event"].to_pylist()
    return {
        "provenance": source,
        "summary": _pay_summary(event),
        "weekly": _pay_weekly(event),
        "weeks": _pay_weeks(event),
    }


# --- report files ------------------------------------------------------------

def fill_blocks(text: str, blocks: dict[str, str]) -> str:
    """Replace each generated block's body; every block in ``blocks`` must appear exactly once."""
    seen = []

    def replace(match: re.Match) -> str:
        name = match["name"]
        if name not in blocks:
            raise ValueError(f"report has a generated block {name!r} that studies.py doesn't write")
        seen.append(name)
        return match[1] + blocks[name].rstrip("\n") + "\n" + match[3]

    text = _BLOCK_RE.sub(replace, text)
    if sorted(seen) != sorted(blocks):
        missing = sorted(set(blocks) - set(seen))
        repeated = sorted({name for name in seen if seen.count(name) > 1})
        raise ValueError(f"generated blocks missing {missing} or repeated {repeated}")
    return text


def write_reports(reports_dir: Path, results: dict[str, pa.Table], source: str) -> list[Path]:
    written = []
    for name, blocks in ((CP_REPORT, congestion_blocks(results, source)), (PAY_REPORT, pay_blocks(results, source))):
        path = reports_dir / name
        try:
            text = fill_blocks(path.read_text(encoding="utf-8"), blocks)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from None
        path.write_text(text, encoding="utf-8")
        written.append(path)
    return written


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.studies", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--holidays", action="store_true",
                        help="recompute the excluded holiday weeks into config/periods.yaml, then stop")
    parser.add_argument("--reports-dir", type=Path, default=common.REPORTS_DIR,
                        help="folder holding the two reports (default: reports/)")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.holidays:
        weeks = write_holidays()
        print(f"config/periods.yaml: {HOLIDAYS_KEY} = {[w['iso_week'] for w in weeks]}")
        return
    if configured_holiday_weeks() != holiday_weeks():
        print(f"studies: config/periods.yaml {HOLIDAYS_KEY} is stale; run `python -m pipeline.studies --holidays`",
              file=sys.stderr)
        raise SystemExit(1)
    try:
        results = run_metrics()
        written = write_reports(args.reports_dir, results, provenance())
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"studies: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    for path in written:
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
