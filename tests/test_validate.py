"""Validation gate (lane L08): each check passes and fails at its boundary, months missing from
the indicators are skipped, the summary matches contracts/README.md §5, and the report and CLI.

Aggregates come from tests/factories.py; the indicators CSV is written in the real file's shape
(NYC Open Data copy, D19). Trip-file footers are faked unless a test writes local raw files, so
nothing touches the network.
"""

import calendar
import json
import re
from datetime import date, datetime, timezone

import pyarrow.parquet as pq
import pytest
from contract_check import assert_matches_contract
from factories import AGG_SCHEMAS, agg_table, write_agg
from test_discover import write_real

from pipeline import common, discover, validate, zones
from pipeline.discover import FileSchema

NOW = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
SCOPE = ["2025-02", "2025-03", "2025-04"]
MODES = ("uber", "lyft", "other_hv", "yellow", "green")
CORE = {161, 162, 163}
WIDE = CORE | {142}                      # 142 stands in for a borderline zone

# Trips per day: the HV modes sum to TLC's FHV - High Volume figure; 1 yellow trip a day is 0.01%.
PER_DAY = {"uber": 7_000, "lyft": 2_900, "other_hv": 100, "yellow": 10_000, "green": 100}
TLC = {"FHV - High Volume": 10_000, "Yellow": 10_000, "Green": 100}

REAL_HEADER = ("Year/Month,License Class,Trips Per Day,Farebox Per Day,Unique Drivers,Unique Vehicles,"
               "Vehicles Per Day,Avg Days Vehicles on Road,Avg Hours Per Day Per Vehicle,Avg Days Drivers on Road,"
               "Avg Hours Per Day Per Driver,Avg Minutes Per Trip,Percent of Trips Paid with Credit Card,"
               "Trips Per Day Shared")

REAL_DISCOVER, REAL_CHECK = discover.discover, discover.check


# --- fixtures and builders -----------------------------------------------------

@pytest.fixture(autouse=True)
def report_path(monkeypatch, tmp_path):
    path = tmp_path / "reports" / "validation.md"
    monkeypatch.setattr(validate, "REPORT_PATH", path)
    return path


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    """Scope, zone lists and trip-file footers for every test; tests override as needed."""
    monkeypatch.setattr(common, "months_in_scope", lambda: list(SCOPE))
    monkeypatch.setattr(zones, "cbd_zone_ids", lambda zone_list="core": set(CORE if zone_list == "core" else WIDE))
    calls = []

    def fake_discover(datasets, months, con=None, **_):
        calls.append(list(months))
        return [FileSchema(d, m, "remote", columns=[("x", "VARCHAR")], rows=1) for d in datasets for m in months]

    monkeypatch.setattr(discover, "discover", fake_discover)
    monkeypatch.setattr(discover, "check", lambda files, schema_map: [])
    return calls


def d(month: str) -> date:
    return common.parse_month(month)


def days(month: str) -> int:
    first = d(month)
    return calendar.monthrange(first.year, first.month)[1]


def indicator_line(month: str, license_class: str, trips_per_day) -> str:
    """A row as the real file has it: plain numbers, empty FHV farebox and card share."""
    if license_class.startswith("FHV"):
        return f"{month},{license_class},{trips_per_day},,85794,83544,59457,22.1,6.4,21.9,6.3,19,,5315"
    return f"{month},{license_class},{trips_per_day},30727,517,497,289,18.1,3.6,17.5,3.6,16,79,"


def write_indicators(rows=None, header=REAL_HEADER, lines=None):
    """``rows`` of (month, license class, trips per day); default: every class for SCOPE."""
    rows = [(m, cls, tpd) for m in SCOPE for cls, tpd in TLC.items()] if rows is None else rows
    body = lines if lines is not None else [indicator_line(*row) for row in rows]
    path = common.ref_dir() / validate.INDICATORS_CSV
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([header, *body]) + "\n", encoding="utf-8")
    return path


def write_zone_hour(months=SCOPE, totals=None):
    """Each month × mode's trips (PER_DAY × days unless ``totals`` overrides), split over two zones."""
    totals = totals or {}
    rows = []
    for m in months:
        for mode in MODES:
            total = totals.get((m, mode), PER_DAY[mode] * days(m))
            half = total // 2
            rows += [{"month": d(m), "mode": mode, "pu_zone": 161, "trips_all": half},
                     {"month": d(m), "mode": mode, "pu_zone": 236, "trips_all": total - half}]
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", rows))


def write_quality(months=SCOPE, valid=None):
    valid = valid or {}
    write_agg("agg_quality_month", agg_table("agg_quality_month", [
        {"month": d(m), "mode": mode, "rows": 10_000, "valid_rows": valid.get((m, mode), 9_900)}
        for m in months for mode in MODES]))


def write_cbd_pairs(rows=None, months=SCOPE):
    """Default per month: core both-in 99.0% with a fee, borderline pair 99%, pass-through 0.4%."""
    if rows is None:
        rows = []
        for m in months:
            rows += [{"month": d(m), "pu_zone": 161, "do_zone": 162, "trips_all": 1_000, "trips_cbd_fee": 990},
                     {"month": d(m), "pu_zone": 142, "do_zone": 161, "trips_all": 100, "trips_cbd_fee": 99},
                     {"month": d(m), "pu_zone": 1, "do_zone": 2, "trips_all": 1_000, "trips_cbd_fee": 4}]
    write_agg("agg_cbd_pairs", agg_table("agg_cbd_pairs", rows))


def write_fee_values(rows=None, months=SCOPE):
    """Default: every mode at its configured fee, plus no-fee trips (ignored by the check)."""
    if rows is None:
        rows = [{"month": d(m), "mode": mode} for m in months for mode in MODES]
        rows += [{"month": d(m), "mode": mode, "cbd_fee": 0.0, "trips": 5_000} for m in months for mode in MODES]
    write_agg("agg_fee_values", agg_table("agg_fee_values", rows))


def write_vendor_month(rows=None, months=SCOPE):
    """Records per vendor (D25). Default: one vendor per month × mode (NULL for HVFHV, vendor 2 for
    cabs), so nothing is excluded from the tie-out."""
    if rows is None:
        rows = [{"month": d(m), "mode": mode, "rows": PER_DAY[mode] * days(m)} for m in months for mode in MODES]
    write_agg("agg_vendor_month", agg_table("agg_vendor_month", rows))


def write_world():
    write_indicators()
    write_zone_hour()
    write_vendor_month()
    write_quality()
    write_cbd_pairs()
    write_fee_values()


def run() -> dict:
    return validate.run(now=NOW)


def check(summary: dict, check_id: str) -> dict:
    return next(c for c in summary["checks"] if c["id"] == check_id)


def contract_example() -> dict:
    """The validation_summary.json example in contracts/README.md §5."""
    text = (common.REPO_ROOT / "contracts" / "README.md").read_text()
    section = text.split("## 5.", 1)[1]
    return json.loads(re.search(r"```json\n(.*?)\n```", section, re.S).group(1))


# --- the whole gate ------------------------------------------------------------

def test_all_checks_pass_on_a_consistent_world(report_path):
    write_world()
    summary = run()
    assert summary["status"] == "pass"
    assert [(c["id"], c["status"]) for c in summary["checks"]] == [
        ("tie_out", "pass"), ("quality_drift", "pass"), ("cbd_list", "pass"), ("schema", "pass"), ("fees", "pass")]
    assert summary["months_checked"] == SCOPE
    assert summary["generated_at"] == "2026-11-15T10:00:00Z"
    assert json.loads(validate.summary_path().read_text()) == summary
    assert report_path.exists()


def test_summary_matches_contract():
    write_world()
    write_fee_values([{"month": d("2025-03"), "mode": "uber", "cbd_fee": 1.5, "trips": 990},
                      {"month": d("2025-03"), "mode": "uber", "cbd_fee": 0.75, "trips": 10}])
    summary = run()
    assert_matches_contract(summary, contract_example())
    assert summary["fees"][0]["other_values"] == [{"cbd_fee": 0.75, "trips": 10}]
    assert summary["tie_out"][0] == {"month": "2025-02-01", "license_class": "FHV - High Volume",
                                     "pipeline_trips_per_day": 10_000.0, "tlc_trips_per_day": 10_000.0,
                                     "diff": 0.0, "status": "pass"}
    assert summary["quality"][0] == {"month": "2025-02-01", "mode": "uber", "valid_share": 0.99, "status": "pass"}
    assert summary["cbd"] == [
        # core: 3 × 990 / 3 × 1,000; pass-through 3 × 4 / 3 × 1,000
        {"zone_list": "core", "both_in_fee_share": 0.99, "neither_in_fee_share": 0.004, "status": "pass"},
        # wide adds the 142 → 161 pair: (2,970 + 297) / (3,000 + 300) = 0.99
        {"zone_list": "wide", "both_in_fee_share": 0.99, "neither_in_fee_share": 0.004, "status": "pass"}]


def test_report_has_the_table_first_then_every_section(report_path):
    write_world()
    run()
    report = report_path.read_text()
    headings = ["## Tie-out", "## Quality drift", "## CBD list", "## Schema", "## Fees"]
    positions = [report.index(h) for h in headings]
    assert positions == sorted(positions)
    table = report.index("| Check | Status | Summary |")
    assert report.index("**Status: PASS**") < table < positions[0]
    assert "months checked: 2025-02 → 2025-04 (3 months)" in report
    assert "| Tie-out | PASS | All 3 months with indicators within ±2% |" in report


def test_any_failure_fails_the_gate():
    write_world()
    write_quality(valid={("2025-03", "green"): 8_000})       # 80%, below D26's 85%
    summary = run()
    assert summary["status"] == "fail"
    assert check(summary, "quality_drift")["status"] == "fail"
    assert check(summary, "tie_out")["status"] == "pass"


def test_missing_table_fails_its_check_only():
    write_world()
    common.agg_path("agg_quality_month").unlink()
    summary = run()
    assert check(summary, "quality_drift") == {
        "id": "quality_drift", "status": "fail",
        "summary": "could not run: missing data/agg/agg_quality_month.parquet"}
    assert check(summary, "tie_out")["status"] == "pass"
    assert summary["quality"] == []
    assert summary["status"] == "fail"


def test_months_checked_adds_months_found_in_the_aggregates():
    write_world()
    write_zone_hour(months=[*SCOPE, "2025-05"])
    summary = run()
    assert summary["months_checked"] == [*SCOPE, "2025-05"]
    may = [r for r in summary["tie_out"] if r["month"] == "2025-05-01"]
    assert {r["status"] for r in may} == {"skipped"}        # not in the indicators written here


# --- tie-out -------------------------------------------------------------------

@pytest.mark.parametrize("per_day, status", [
    (10_200, "pass"),    # +2.00%
    (10_201, "fail"),    # +2.01%
    (9_800, "pass"),     # −2.00%
    (9_799, "fail"),     # −2.01%
])
def test_tie_out_boundary(per_day, status):
    write_world()
    write_zone_hour(totals={("2025-03", "yellow"): per_day * 31})
    summary = run()
    row = next(r for r in summary["tie_out"] if r["month"] == "2025-03-01" and r["license_class"] == "Yellow")
    assert row["pipeline_trips_per_day"] == per_day
    assert row["diff"] == pytest.approx(per_day / 10_000 - 1)
    assert row["status"] == status
    assert check(summary, "tie_out")["status"] == status


def test_tie_out_sums_the_hv_modes():
    write_world()
    # 2025-04 (30 days): uber + lyft + other_hv = 300,000 + 0 + 6,000 = 306,000 → 10,200 a day, +2.00%
    write_zone_hour(totals={("2025-04", "uber"): 300_000, ("2025-04", "lyft"): 0, ("2025-04", "other_hv"): 6_000})
    row = next(r for r in run()["tie_out"] if r["month"] == "2025-04-01" and r["license_class"] == "FHV - High Volume")
    assert (row["pipeline_trips_per_day"], row["status"]) == (10_200.0, "pass")


def test_tie_out_divides_by_days_in_the_month(monkeypatch):
    monkeypatch.setattr(common, "months_in_scope", lambda: ["2024-02"])    # leap year: 29 days
    write_indicators([("2024-02", cls, tpd) for cls, tpd in TLC.items()])
    write_zone_hour(months=["2024-02"])
    write_vendor_month(months=["2024-02"])
    summary = run()
    assert [(r["pipeline_trips_per_day"], r["status"]) for r in summary["tie_out"]] == [
        (10_000.0, "pass"), (100.0, "pass"), (10_000.0, "pass")]


def test_month_missing_from_indicators_is_skipped_and_listed():
    write_world()
    write_indicators([(m, cls, tpd) for m in SCOPE[:2] for cls, tpd in TLC.items()])
    summary = run()
    april = [r for r in summary["tie_out"] if r["month"] == "2025-04-01"]
    assert [(r["status"], r["tlc_trips_per_day"], r["diff"]) for r in april] == [("skipped", None, None)] * 3
    assert check(summary, "tie_out") == {
        "id": "tie_out", "status": "pass",
        "summary": "All 2 months with indicators within ±2%; 2025-04 skipped (not yet in indicators)"}


def test_one_class_missing_from_indicators_is_named():
    write_world()
    write_indicators([(m, cls, tpd) for m in SCOPE for cls, tpd in TLC.items() if (m, cls) != ("2025-04", "Green")])
    summary = run()
    assert check(summary, "tie_out")["summary"].endswith("2025-04 (Green) skipped (not yet in indicators)")
    assert check(summary, "tie_out")["status"] == "pass"


def test_month_in_scope_without_pipeline_trips_fails():
    write_world()
    write_zone_hour(months=SCOPE[:2])
    summary = run()
    april = [r for r in summary["tie_out"] if r["month"] == "2025-04-01"]
    assert {(r["pipeline_trips_per_day"], r["diff"], r["status"]) for r in april} == {(0.0, -1.0, "fail")}
    assert check(summary, "tie_out")["summary"].startswith(
        "3 of 9 month × class rows outside ±2%: FHV - High Volume 2025-04 (no pipeline trips)")


def test_tie_out_fails_without_the_indicators_csv():
    write_world()
    (common.ref_dir() / validate.INDICATORS_CSV).unlink()
    summary = run()
    assert check(summary, "tie_out")["status"] == "fail"
    assert "indicators not loaded" in check(summary, "tie_out")["summary"]
    assert "run `make ref`" in check(summary, "tie_out")["summary"]


def test_tie_out_never_uses_a_stale_indicators_copy():
    write_world()
    validate.load_ref_indicators()                        # a good copy from an earlier run
    write_indicators(header=REAL_HEADER.replace("Year/Month", "Month/Year"))
    summary = run()
    assert check(summary, "tie_out")["status"] == "fail"
    assert "missing ['Year/Month'], unexpected ['Month/Year']" in check(summary, "tie_out")["summary"]


# D25: TLC's indicators don't count vendor 6's cab records, so the tie-out leaves them out.

def tie_out_row(summary: dict, month: str, license_class: str) -> dict:
    return next(r for r in summary["tie_out"] if r["month"] == f"{month}-01" and r["license_class"] == license_class)


@pytest.mark.parametrize("exclusions, per_day, diff, status, excluded_cell", [
    # config/sources.yaml (vendor 6): 51,539 − 1,222 = 50,317 records; 50,317 / 31 = 1,623.1 a day;
    # 50,317 / (1,624 × 31 = 50,344) − 1 = −0.05%
    (None, 1_623.1, -0.0005, "pass", "1,222 (vendor 6)"),
    # nothing excluded: 51,539 / 31 = 1,662.5 a day; 51,539 / 50,344 − 1 = +2.37%
    ({}, 1_662.5, 0.0237, "fail", "—"),
])
def test_tie_out_leaves_out_excluded_vendors(monkeypatch, report_path, exclusions, per_day, diff, status,
                                              excluded_cell):
    if exclusions is not None:
        monkeypatch.setattr(validate, "tie_out_exclusions", lambda: exclusions)
    write_world()
    # green 2025-03 as found at G2: 51,539 records, 1,222 of them vendor 6; TLC 1,624 trips a day
    write_indicators([(m, cls, 1_624 if (m, cls) == ("2025-03", "Green") else tpd)
                      for m in SCOPE for cls, tpd in TLC.items()])
    write_zone_hour(totals={("2025-03", "green"): 51_539})
    write_vendor_month([{"month": d("2025-03"), "mode": "green", "vendor_id": 2, "rows": 50_317},
                        {"month": d("2025-03"), "mode": "green", "vendor_id": 6, "rows": 1_222}])
    summary = run()
    row = tie_out_row(summary, "2025-03", "Green")
    assert (row["pipeline_trips_per_day"], row["tlc_trips_per_day"], row["diff"], row["status"]) == (
        per_day, 1_624.0, diff, status)
    assert check(summary, "tie_out")["status"] == status
    assert (f"| 2025-03 | Green | 51,539 | {excluded_cell} | {per_day:,.1f} | 1,624.0 | {diff * 100:+.2f}% | "
            f"{status} |") in report_path.read_text()


def test_tie_out_counts_vendors_not_in_the_list():
    write_world()
    # yellow 2025-03: vendor 2 309,500 + vendor 7 500 + vendor 6 310 = 310,310 records. Only vendor 6
    # leaves: 310,000 / 31 = 10,000.0 a day, TLC's figure exactly (without vendor 7 too: 9,983.9)
    write_zone_hour(totals={("2025-03", "yellow"): 310_310})
    write_vendor_month([{"month": d("2025-03"), "mode": "yellow", "vendor_id": 2, "rows": 309_500},
                        {"month": d("2025-03"), "mode": "yellow", "vendor_id": 7, "rows": 500},
                        {"month": d("2025-03"), "mode": "yellow", "vendor_id": 6, "rows": 310}])
    row = tie_out_row(run(), "2025-03", "Yellow")
    assert (row["pipeline_trips_per_day"], row["diff"], row["status"]) == (10_000.0, 0.0, "pass")


def test_tie_out_leaves_hvfhv_untouched(report_path):
    write_world()
    # HVFHV records have no vendor; even a stray uber row with vendor_id 6 isn't a cab vendor's.
    # 2025-03 HV records stay 310,000 = 10,000.0 a day (subtracting it would give 9,838.7)
    write_vendor_month([{"month": d("2025-03"), "mode": "uber", "vendor_id": None, "rows": 212_000},
                        {"month": d("2025-03"), "mode": "uber", "vendor_id": 6, "rows": 5_000}])
    row = tie_out_row(run(), "2025-03", "FHV - High Volume")
    assert (row["pipeline_trips_per_day"], row["status"]) == (10_000.0, "pass")
    assert "| 2025-03 | FHV - High Volume | 310,000 | — | 10,000.0 |" in report_path.read_text()


def test_tie_out_needs_agg_vendor_month():
    write_world()
    common.agg_path("agg_vendor_month").unlink()
    assert check(run(), "tie_out") == {"id": "tie_out", "status": "fail",
                                       "summary": "could not run: missing data/agg/agg_vendor_month.parquet"}


def test_tie_out_exclusions_come_from_config():
    assert validate.tie_out_exclusions() == {"yellow": [6], "green": [6]}


def test_tie_out_rejects_an_unknown_dataset_in_the_exclusions(monkeypatch):
    load_yaml = common.load_yaml
    monkeypatch.setattr(common, "load_yaml", lambda name: {**load_yaml(name), "tie_out_exclude_vendors": {"fhv": [6]}}
                        if name == "sources.yaml" else load_yaml(name))
    write_world()
    result = check(run(), "tie_out")
    assert result["status"] == "fail"
    assert "names unknown datasets ['fhv']" in result["summary"]


# --- quality drift -------------------------------------------------------------

@pytest.mark.parametrize("valid_rows, status", [(8_500, "pass"), (8_499, "fail")])   # 85.00% vs 84.99% (D26)
def test_quality_boundary(valid_rows, status):
    write_world()
    write_quality(valid={("2025-03", "yellow"): valid_rows})
    summary = run()
    row = next(r for r in summary["quality"] if r["month"] == "2025-03-01" and r["mode"] == "yellow")
    assert (row["valid_share"], row["status"]) == (valid_rows / 10_000, status)
    assert check(summary, "quality_drift")["status"] == status
    if status == "fail":
        assert check(summary, "quality_drift")["summary"].startswith(
            "1 of 15 month × mode rows below 85% valid (D26): yellow 2025-03 (84.99%)")


@pytest.mark.parametrize("valid_rows, points", [
    (9_600, None),       # 3.00 points below: not listed
    (9_599, "3.01"),     # 3.01 points below: listed
    (9_000, "9.00"),     # 90%: below SPEC's old 95% floor, above D26's 85%, so listed but not failed
])
def test_quality_drift_is_listed_not_failed(valid_rows, points, report_path):
    write_world()
    # uber: 99.00%, 99.00% and 96.00% (or 95.99%, or 90.00%); median 99.00%
    write_quality(valid={("2025-04", "uber"): valid_rows})
    summary = run()
    result = check(summary, "quality_drift")
    assert result["status"] == "pass"
    if points:
        assert result["summary"] == ("All 15 month × mode rows at least 85% valid (D26); 1 more than 3 points "
                                     f"below the mode's median (listed): uber 2025-04 ({points} pts)")
        assert f"{valid_rows / 100:.2f}% *drift −{points} pts*" in report_path.read_text()
    else:
        assert result["summary"].endswith("none more than 3 points below its mode's median")


# --- CBD list ------------------------------------------------------------------

@pytest.mark.parametrize("fee_trips, status", [(9_800, "pass"), (9_799, "fail")])   # 98.00% vs 97.99%
def test_cbd_boundary(fee_trips, status):
    write_world()
    write_cbd_pairs([{"month": d("2025-03"), "pu_zone": 161, "do_zone": 162,
                      "trips_all": 10_000, "trips_cbd_fee": fee_trips}])
    summary = run()
    assert [(r["zone_list"], r["both_in_fee_share"], r["status"]) for r in summary["cbd"]] == [
        ("core", fee_trips / 10_000, status), ("wide", fee_trips / 10_000, status)]
    assert check(summary, "cbd_list")["status"] == status


def test_cbd_pass_through_is_reported_not_failed():
    write_world()
    write_cbd_pairs([{"month": d("2025-03"), "pu_zone": 161, "do_zone": 162, "trips_all": 100, "trips_cbd_fee": 100},
                     {"month": d("2025-03"), "pu_zone": 1, "do_zone": 2, "trips_all": 100, "trips_cbd_fee": 60},
                     # one end in the zone: neither both-in nor pass-through
                     {"month": d("2025-03"), "pu_zone": 161, "do_zone": 2, "trips_all": 100, "trips_cbd_fee": 0}])
    summary = run()
    assert summary["cbd"][0] == {"zone_list": "core", "both_in_fee_share": 1.0, "neither_in_fee_share": 0.6,
                                 "status": "pass"}
    assert check(summary, "cbd_list")["status"] == "pass"


def test_cbd_wide_list_counts_borderline_zones():
    write_world()
    # 142 → 161 is both-in only on the wide list: core 100%, wide (100 + 0) / (100 + 100) = 50%
    write_cbd_pairs([{"month": d("2025-03"), "pu_zone": 161, "do_zone": 162, "trips_all": 100, "trips_cbd_fee": 100},
                     {"month": d("2025-03"), "pu_zone": 142, "do_zone": 161, "trips_all": 100, "trips_cbd_fee": 0}])
    summary = run()
    assert [(r["zone_list"], r["both_in_fee_share"], r["status"]) for r in summary["cbd"]] == [
        ("core", 1.0, "pass"), ("wide", 0.5, "fail")]
    # D21: only core gates the check; wide's failing result is reported, not gated
    assert check(summary, "cbd_list")["status"] == "pass"
    assert "wide (reported, not gated): 50.00% of both-in trips carry a fee (below 98%)" in check(
        summary, "cbd_list")["summary"]


def test_cbd_core_below_threshold_fails_even_when_wide_passes():
    write_world()
    # core 161 → 162: 9,700 / 10,000 = 97%; wide adds 142 → 161 at 100%: (9,700 + 10,000) / 20,000 = 98.5%
    write_cbd_pairs([{"month": d("2025-03"), "pu_zone": 161, "do_zone": 162, "trips_all": 10_000, "trips_cbd_fee": 9_700},
                     {"month": d("2025-03"), "pu_zone": 142, "do_zone": 161, "trips_all": 10_000, "trips_cbd_fee": 10_000}])
    summary = run()
    assert [(r["zone_list"], r["status"]) for r in summary["cbd"]] == [("core", "fail"), ("wide", "pass")]
    assert check(summary, "cbd_list")["status"] == "fail"


def test_cbd_leaves_out_the_month_pricing_began(monkeypatch, report_path):
    monkeypatch.setattr(common, "months_in_scope", lambda: ["2025-01", *SCOPE])
    write_world()
    # 1–4 Jan 2025 trips carry no fee; the month can't be split, so it's left out
    write_cbd_pairs([{"month": d("2025-01"), "pu_zone": 161, "do_zone": 162, "trips_all": 10_000, "trips_cbd_fee": 8_700},
                     {"month": d("2025-03"), "pu_zone": 161, "do_zone": 162, "trips_all": 100, "trips_cbd_fee": 99}])
    summary = run()
    assert check(summary, "cbd_list")["status"] == "pass"
    assert summary["cbd"][0]["both_in_fee_share"] == 0.99
    assert "2025-01 left out: congestion pricing began on 2025-01-05" in report_path.read_text()


def test_cbd_without_zone_lists_fails(monkeypatch):
    write_world()

    def stub(zone_list="core"):
        raise NotImplementedError("zones.cbd_zone_ids (lane L04)")

    monkeypatch.setattr(zones, "cbd_zone_ids", stub)
    summary = run()
    assert check(summary, "cbd_list") == {"id": "cbd_list", "status": "fail",
                                          "summary": "could not run: zones.cbd_zone_ids (lane L04)"}


def test_cbd_with_no_trips_after_pricing_is_skipped_and_gate_fails():
    write_world()
    write_cbd_pairs([])
    summary = run()
    assert check(summary, "cbd_list")["status"] == "skipped"
    assert [r["status"] for r in summary["cbd"]] == ["skipped", "skipped"]
    assert summary["status"] == "skipped"            # only an all-pass gate passes


# --- schema --------------------------------------------------------------------

def test_schema_reads_every_file_for_the_months_checked(setup):
    write_world()
    summary = run()
    assert setup == [SCOPE]
    assert check(summary, "schema")["summary"] == "9 files, no unmapped, missing or mistyped columns"


def test_schema_fails_on_an_unreadable_file(monkeypatch):
    write_world()
    monkeypatch.setattr(discover, "check", REAL_CHECK)
    monkeypatch.setattr(discover, "discover", lambda datasets, months, **_: [
        FileSchema("green", "2025-04", "remote", error="HTTP 403: no such file")])
    result = check(run(), "schema")
    assert result == {"id": "schema", "status": "fail", "summary": (
        "1 problems in 1 files: green_tripdata_2025-04.parquet: could not read the footer: HTTP 403: no such file")}


def test_schema_uses_local_footers(monkeypatch):
    monkeypatch.setattr(discover, "discover", REAL_DISCOVER)
    monkeypatch.setattr(discover, "check", REAL_CHECK)
    write_real()                                       # real-shaped 2024-12 and 2025-01 files (L03's helper)
    result = validate.check_schema(["2024-12", "2025-01"])
    assert (result.status, result.summary) == ("pass", "6 files, no unmapped, missing or mistyped columns")
    assert "(6 local, 0 read over HTTP, D11)" in result.details[0]


# --- fees ----------------------------------------------------------------------

@pytest.mark.parametrize("exact, status", [(9_500, "pass"), (9_499, "fail")])   # 95.00% vs 94.99%
def test_fees_boundary(exact, status):
    write_world()
    write_fee_values([{"month": d("2025-03"), "mode": "uber", "cbd_fee": 1.5, "trips": exact},
                      {"month": d("2025-03"), "mode": "uber", "cbd_fee": 0.75, "trips": 10_000 - exact}])
    summary = run()
    assert summary["fees"] == [{"mode": "uber", "configured_fee": 1.5, "exact_share": exact / 10_000,
                                "other_values": [{"cbd_fee": 0.75, "trips": 10_000 - exact}], "status": status}]
    assert check(summary, "fees")["status"] == status


def test_fees_use_each_modes_configured_fee_and_list_other_values():
    write_world()
    write_fee_values([
        {"month": d("2025-03"), "mode": "yellow", "cbd_fee": 0.75, "trips": 1_000},
        {"month": d("2025-03"), "mode": "yellow", "cbd_fee": 1.5, "trips": 3},
        {"month": d("2025-04"), "mode": "yellow", "cbd_fee": 2.5, "trips": 7},
        {"month": d("2025-03"), "mode": "yellow", "cbd_fee": 0.0, "trips": 50_000},     # no fee: not counted
        {"month": d("2025-03"), "mode": "yellow", "cbd_fee": -0.75, "trips": 40},       # refund: not counted
        {"month": d("2025-03"), "mode": "green", "cbd_fee": 0.75, "trips": 100},
    ])
    summary = run()
    assert summary["fees"] == [
        {"mode": "yellow", "configured_fee": 0.75, "exact_share": round(1_000 / 1_010, 4),
         "other_values": [{"cbd_fee": 2.5, "trips": 7}, {"cbd_fee": 1.5, "trips": 3}], "status": "pass"},
        {"mode": "green", "configured_fee": 0.75, "exact_share": 1.0, "other_values": [], "status": "pass"}]


def test_fees_ignore_months_before_pricing(monkeypatch):
    monkeypatch.setattr(common, "months_in_scope", lambda: ["2024-12", *SCOPE])
    write_world()
    write_fee_values([{"month": d("2024-12"), "mode": "uber", "cbd_fee": 2.0, "trips": 1_000},
                      {"month": d("2025-01"), "mode": "uber", "cbd_fee": 1.5, "trips": 100}])
    summary = run()
    assert summary["fees"] == [{"mode": "uber", "configured_fee": 1.5, "exact_share": 1.0,
                                "other_values": [], "status": "pass"}]


# --- ref_indicators ------------------------------------------------------------

def test_ref_indicators_keeps_names_and_values():
    write_indicators(lines=[
        "2026-08,FHV - High Volume,661076,,85794,83544,59457,22.1,6.4,21.9,6.3,19,,5315",
        "2026-08,Green,1291,30727,517,497,289,18.1,3.6,17.5,3.6,16,79,",
    ])
    path = validate.load_ref_indicators()
    assert path == common.agg_path("ref_indicators")
    table = pq.read_table(path)
    assert table.schema.names == AGG_SCHEMAS["ref_indicators"].names
    assert table.schema.types == AGG_SCHEMAS["ref_indicators"].types
    hv, green = table.to_pylist()
    assert hv["month"] == date(2026, 8, 1)
    assert (hv["Year/Month"], hv["License Class"], hv["Trips Per Day"]) == ("2026-08", "FHV - High Volume", 661_076.0)
    assert (hv["Farebox Per Day"], hv["Percent of Trips Paid with Credit Card"], hv["Trips Per Day Shared"]) == (
        None, None, 5_315.0)
    assert (green["Avg Hours Per Day Per Vehicle"], green["Percent of Trips Paid with Credit Card"]) == (3.6, 79.0)
    assert green["Trips Per Day Shared"] is None


def test_ref_indicators_rejects_another_header():
    write_indicators(header=REAL_HEADER.replace("Year/Month", "Month/Year"))
    with pytest.raises(ValueError, match=r"missing \['Year/Month'\], unexpected \['Month/Year'\]"):
        validate.load_ref_indicators()


def test_ref_indicators_rejects_repeated_rows():
    write_indicators([("2026-08", "Green", 1291), ("2026-08", "Green", 1290)])
    with pytest.raises(ValueError, match="repeated month × license class rows"):
        validate.load_ref_indicators()


def test_ref_indicators_never_turns_a_bad_value_into_null():
    write_indicators(lines=['2026-08,Yellow,"107,510",2950326,12675,9923,8332,26,7.9,23.1,7,17.1,89,'])
    with pytest.raises(Exception, match="107,510"):
        validate.load_ref_indicators()
    assert not common.agg_path("ref_indicators").exists()


# --- CLI -----------------------------------------------------------------------

def test_cli_exit_codes(capsys):
    write_world()
    with pytest.raises(SystemExit) as exit_:
        validate.main([])
    assert exit_.value.code == 0
    out = capsys.readouterr().out
    assert "pass    tie_out: All 3 months with indicators within ±2%" in out
    assert "validation pass" in out

    write_zone_hour(totals={("2025-03", "yellow"): 10_201 * 31})
    with pytest.raises(SystemExit) as exit_:
        validate.main([])
    assert exit_.value.code == 1
    assert "validation fail" in capsys.readouterr().out


def test_cli_indicators_only(capsys):
    write_indicators()
    validate.main(["--indicators-only"])
    assert "9 rows, 2025-02 → 2025-04" in capsys.readouterr().out
    assert common.agg_path("ref_indicators").exists()
    assert not validate.summary_path().exists()


def test_cli_indicators_only_without_the_csv(capsys):
    with pytest.raises(SystemExit) as exit_:
        validate.main(["--indicators-only"])
    assert exit_.value.code == 1
    assert "run `make ref`" in capsys.readouterr().err


@pytest.mark.parametrize("start, months", [
    (date(2025, 1, 5), (date(2025, 1, 1), date(2025, 2, 1))),
    (date(2025, 12, 5), (date(2025, 12, 1), date(2026, 1, 1))),
    (date(2025, 3, 1), (date(2025, 3, 1), date(2025, 3, 1))),
])
def test_pricing_months(start, months):
    assert validate._pricing_months({"congestion_pricing_start": start}) == months
