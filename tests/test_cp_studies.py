"""pipeline.studies: the report tables for both policy studies, end to end on a full factory
fixture set, plus the L10 metric headers (SPEC §6, D12, D21)."""

import calendar
import json
import re
import shutil
import subprocess
import sys
from datetime import date

import pytest
from factories import HV_MODES, TAXI_MODES, agg_table, write_agg

from pipeline import common, metrics, studies

L10_METRICS = ("cp_effect", "cp_effect_summary", "cp_weekly_trips", "cp_zone_change", "pay_event")
BLOCK_RE = re.compile(r"(<!-- BEGIN generated: [\w-]+ -->\n).*?(<!-- END generated: [\w-]+ -->)", re.S)


def write_full_fixture(data_dir):
    """Every ISO week of 2024 and 2025 for every mode, list and group, and two years of zone pickups.

    agg_week_cbd: each week's rows sit under the month of its Monday, so every month from 2024-01
    to 2025-12 is in the table and every week is fully covered.
      trips: treated 1,000 (core) / 1,100 (wide), control 3,000 / 2,900. From 2025-W02, treated is
             940 (core) and 1,045 (wide): growth 0.94 and 0.95 against 1.0 → effects −6.0% and −5.0%.
      pay: 1,000 miles per row and driver pay 2,000 → $2.000 a mile; from W32 (after the transition
             week) 2,100 in 2025 (+5.0%) and 2,020 in 2024 (+1.0%). Net of 2024: 1.05 ÷ 1.01 − 1 = +4.0%.
    agg_zone_hour: pickups per day zone 161 100 → 90 (−10.0%), zone 236 200 → 220 (+10.0%), zone 132
    50 → 50 (under the 100-a-day floor for the zone tables), zone 264 300 → 100 (unknown zone: kept by
    the metric, left out of the report's zone tables). Default sums elsewhere: driver pay 1,391.6 over
    117,600 seconds in every row → pay per hour with a passenger 1,391.6 ÷ 32.67 h = $42.60."""
    rows = []
    for year in (2024, 2025):
        for week in range(1, 53):
            monday = date.fromisocalendar(year, week, 1)
            pay = 2000.0 if week < 32 else {2024: 2020.0, 2025: 2100.0}[year]
            for mode in HV_MODES + TAXI_MODES:
                for zone_list, treated, control, treated_now in (("core", 1000, 3000, 940), ("wide", 1100, 2900, 1045)):
                    for group, trips in (("treated", treated_now if year == 2025 and week >= 2 else treated),
                                         ("control", control)):
                        rows.append({"month": date(monday.year, monday.month, 1), "iso_year": year, "iso_week": week,
                                     "mode": mode, "zone_list": zone_list, "cbd_group": group, "trips_all": trips,
                                     "miles": 1000.0, "driver_pay": pay if mode in HV_MODES else None})
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", rows))
    per_day = {161: (100, 90), 236: (200, 220), 132: (50, 50), 264: (300, 100)}
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [
        {"month": date(year, month, 1), "pu_zone": zone, "trips_all": per_day[zone][year - 2024]
         * calendar.monthrange(year, month)[1]}
        for year in (2024, 2025) for month in range(1, 13) for zone in per_day]))
    (data_dir / "ref").mkdir(exist_ok=True)
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text(
        '"LocationID","Borough","Zone","service_zone"\n132,"Queens","JFK Airport","Airports"\n'
        '161,"Manhattan","Midtown Center","Yellow Zone"\n236,"Manhattan","Upper East Side North","Yellow Zone"\n')


@pytest.fixture
def full(data_dir):
    write_full_fixture(data_dir)
    return data_dir


@pytest.fixture
def reports(tmp_path):
    folder = tmp_path / "reports"
    folder.mkdir()
    for name in (studies.CP_REPORT, studies.PAY_REPORT):
        shutil.copy(common.REPORTS_DIR / name, folder / name)
    return folder


def narrative(text):
    """A report with every generated block emptied: the hand-written part."""
    return BLOCK_RE.sub(r"\1\2", text)


# --- metrics on the full fixture -----------------------------------------------

def test_all_five_metrics_run_on_the_full_fixture(full):
    for name in L10_METRICS:
        table = metrics.run(name)
        assert table.schema.equals(metrics.contract_schema(name)), name
        assert table.num_rows > 0, name


@pytest.mark.parametrize("name", L10_METRICS)
def test_header_names_questions_params_grain_columns_source(name):
    head = metrics.header(name)
    assert head["metric"] == name
    assert {"questions", "params", "grain", "columns", "source"} <= head.keys()
    assert [part.split()[0] for part in head["columns"].split(",")] == metrics.contract_schema(name).names
    assert metrics.parameters(name) == set() and head["params"] == "none"
    assert head["source"] == "TLC trip records"


def test_sql_dates_match_periods_yaml():
    periods = common.load_yaml("periods.yaml")
    for name in ("cp_effect", "cp_effect_summary"):
        assert f"DATE '{periods['congestion_pricing_start']}' AS cp_start" in metrics.sql_text(name)
    assert f"isoyear(DATE '{periods['driver_pay_rise']}')" in metrics.sql_text("pay_event")


# --- the reports ---------------------------------------------------------------

def test_reports_are_filled_from_the_metrics(full, reports):
    templates = {name: (reports / name).read_text() for name in (studies.CP_REPORT, studies.PAY_REPORT)}
    studies.main(["--reports-dir", str(reports)])
    cp, pay = (reports / studies.CP_REPORT).read_text(), (reports / studies.PAY_REPORT).read_text()
    for name, text in ((studies.CP_REPORT, cp), (studies.PAY_REPORT, pay)):
        assert "Not generated yet" not in text
        assert narrative(text) == narrative(templates[name])      # hand-written text untouched
        assert "`agg_week_cbd` 2024-01 to 2025-12 and `agg_zone_hour` 2024-01 to 2025-12" in text
        assert "Validation gate (`make validate`): **not run**." in text
    # headline (core) and sensitivity (wide), W02–W52 less the two MLK weeks = 49 weeks
    assert "| Trips | All modes | −6.0% | −6.0% | −6.0% | 49 |" in cp
    assert "| Base fare per mile | Yellow cab | +0.0% | +0.0% | +0.0% | 49 |" in cp
    assert "| Driver share of base fare | Ride-hail | +0.0% | +0.0% | +0.0% | 49 |" in cp
    assert "| Driver share of base fare | Green cab |" not in cp
    assert "| Trips | All modes | −6.0% | −5.0% | −5.0% | −5.0% | 49 | +1.0 pts |" in cp
    # weekly series: 2,143 = 15,000 control trips (5 modes × 3,000) ÷ 7; treated 4,700 ÷ 7 = 671
    assert "| W02 | 714 | 671 | 2,143 | 2,143 |" in cp
    assert "| W01 | 30 Dec 2024 | Left out by design (D12): pricing began on its last day (Sun 5 Jan) |" in cp
    for week in ("W03 | 13 Jan 2025", "W04 | 20 Jan 2025"):
        assert f"| {week} | Martin Luther King Jr. Day is in ISO week 3 in 2024" in cp
    assert "| Martin Luther King Jr. Day | Mon 15 Jan (W03) | Mon 20 Jan (W04) | both weeks excluded |" in cp
    assert "2 map zones (1 to 263) had at least 100 pickups a day in 2024; 1 of them had fewer pickups a day in 2025." in cp
    assert "| 161 | Midtown Center | core | 100 | 90 | −10.0% |" in cp
    assert "| 236 | Upper East Side North | — | 200 | 220 | +10.0% |" in cp
    assert "| 132 |" not in cp and "| 264 |" not in cp
    # group growth: core treated 5,000 → 4,700 (−6.0%), wide 5,500 → 5,225 (−5.0%); controls flat
    assert "| All modes | −6.0% | +0.0% | −5.0% | +0.0% |" in cp
    assert "| Yellow cab | −6.0% | +0.0% | −5.0% | +0.0% |" in cp
    # pay rise: medians of 12 weeks either side of W31
    assert "| Ride-hail | Driver pay per mile | $2.000 | $2.100 | +5.0% | $2.000 | $2.020 | +1.0% | +4.0% |" in pay
    assert "| 0 | W31 | 28 Jul 2025 | $2.000 | $2.000 |" in pay and "| transition |" in pay
    assert "| 2025 | W19 to W43 | 5 May 2025 to 26 Oct 2025 | W31 (week of 28 Jul 2025) | none |" in pay
    assert "| 2024 | W19 to W43 | 6 May 2024 to 27 Oct 2024 | W31 (week of 29 Jul 2024) | none |" in pay
    # monthly context: L09's pay_per_hour, ride_hail (uber only here)
    assert "| Jan 2024 | $42.60 | — | — | — |" in pay
    assert "| Mar 2025 | $42.60 | +0.0% | $42.60 | +0.0% |" in pay


def test_reports_are_reproducible(full, reports):
    studies.main(["--reports-dir", str(reports)])
    first = {p.name: p.read_text() for p in reports.iterdir()}
    studies.main(["--reports-dir", str(reports)])
    assert {p.name: p.read_text() for p in reports.iterdir()} == first


def test_validation_status_comes_from_the_summary(full, reports):
    (full / "agg" / "validation_summary.json").write_text(json.dumps({"status": "pass"}))
    studies.main(["--reports-dir", str(reports)])
    assert "Validation gate (`make validate`): **pass**." in (reports / studies.PAY_REPORT).read_text()


def test_committed_reports_have_every_block(full):
    results = studies.run_metrics()
    for name, blocks in ((studies.CP_REPORT, studies.congestion_blocks(results, "")),
                         (studies.PAY_REPORT, studies.pay_blocks(results, ""))):
        text = (common.REPORTS_DIR / name).read_text()
        studies.fill_blocks(text, blocks)                 # raises if a block is missing or unknown
        assert "Not generated yet" not in text
        assert "caused" not in text


# --- CLI and errors ------------------------------------------------------------

def test_cli(full, reports):
    result = subprocess.run([sys.executable, "-m", "pipeline.studies", "--reports-dir", str(reports)],
                            cwd=common.REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.count("wrote ") == 2


def test_missing_aggregates_fail_cleanly(data_dir, reports, capsys):
    with pytest.raises(SystemExit) as exit_info:
        studies.main(["--reports-dir", str(reports)])
    assert exit_info.value.code == 1
    assert capsys.readouterr().err.startswith("studies: ")
    assert (reports / studies.CP_REPORT).read_text() == (common.REPORTS_DIR / studies.CP_REPORT).read_text()


def test_stale_holiday_weeks_stop_the_run(full, reports, monkeypatch, capsys):
    monkeypatch.setattr(studies, "configured_holiday_weeks", lambda: [])
    with pytest.raises(SystemExit) as exit_info:
        studies.main(["--reports-dir", str(reports)])
    assert exit_info.value.code == 1
    assert "--holidays" in capsys.readouterr().err


def test_fill_blocks_needs_every_block_once():
    text = "a\n<!-- BEGIN generated: x -->\nold\n<!-- END generated: x -->\nb\n"
    assert studies.fill_blocks(text, {"x": "new"}) == "a\n<!-- BEGIN generated: x -->\nnew\n<!-- END generated: x -->\nb\n"
    with pytest.raises(ValueError, match=r"missing \['y'\]"):
        studies.fill_blocks(text, {"x": "new", "y": "more"})
    with pytest.raises(ValueError, match="doesn't write"):
        studies.fill_blocks(text, {})


def test_before_after_uses_medians_and_skips_the_transition_week():
    rows = [{"mode": "uber", "year": 2025, "week_offset": o, "transition": o == 0, "pay_per_mile": v}
            for o, v in ((-3, 1.0), (-2, 2.0), (-1, 9.0), (0, 100.0), (1, 3.0), (2, None), (3, 5.0))]
    # before: median(1, 2, 9) = 2; after: median(3, 5) = 4 (the NULL week and the transition week drop)
    assert studies.before_after(rows, "uber", "pay_per_mile", 2025) == (2.0, 4.0)
    assert studies.before_after(rows, "lyft", "pay_per_mile", 2025) == (None, None)
