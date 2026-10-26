"""The metrics runner: views, parameters, contract checks, headers and the CLI (L09)."""

import json
import subprocess
import sys
from datetime import date

import pyarrow as pa
import pytest
from factories import AGG_SCHEMAS, HV_MODES, TAXI_MODES, agg_table, write_agg

from pipeline import common, metrics

MODES = HV_MODES + TAXI_MODES
MONTHS = (date(2024, 3, 1), date(2025, 2, 1), date(2025, 3, 1))
L10_METRICS = {"cp_effect", "cp_effect_summary", "cp_weekly_trips", "cp_zone_change", "pay_event"}
ZONES = [(1, "EWR", "Newark Airport", "EWR"), (132, "Queens", "JFK Airport", "Airports"),
         (161, "Manhattan", "Midtown Center", "Yellow Zone"),
         (236, "Manhattan", "Upper East Side North", "Yellow Zone"),
         (264, "Unknown", "N/A", "N/A"), (265, "N/A", "Outside of NYC", "N/A")]


def write_zone_lookup(data_dir, zones=ZONES):
    (data_dir / "ref").mkdir(exist_ok=True)
    lines = ['"LocationID","Borough","Zone","service_zone"']
    lines += [f'{zone},"{borough}","{name}","{service}"' for zone, borough, name, service in zones]
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text("\n".join(lines) + "\n")


def write_full_fixture(data_dir):
    """Every aggregate table, several months, modes and zones; factory defaults elsewhere."""
    cells = [{"month": m, "mode": md, "pu_zone": z, "hour_of_week": h}
             for m in MONTHS for md in MODES for z in (132, 161, 264) for h in (8, 56)]
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", cells))
    dist = [{"month": m, "mode": md, "pu_zone": z} for m in MONTHS for md in MODES for z in (0, 161)]
    dist += [{"month": m, "mode": group, "pu_zone": 0, "wait_p50": None, "wait_p90": None}
             for m in MONTHS for group in ("ride_hail", "all")]
    write_agg("agg_zone_month_dist", agg_table("agg_zone_month_dist", dist))
    write_agg("agg_od_month", agg_table("agg_od_month", [
        {"month": m, "mode": md, "pu_zone": pu, "do_zone": do}
        for m in MONTHS for md in MODES for pu, do in ((161, 236), (132, 161), (1, 161), (132, 236))]))
    write_agg("agg_airport", agg_table("agg_airport", [
        {"month": m, "mode": md, "airport": ap, "direction": d, "hour_of_day": h}
        for m in MONTHS for md in MODES for ap in ("JFK", "LGA", "EWR") for d in ("from", "to") for h in (7, 15)]))
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [
        {"mode": md, "zone_list": zl, "cbd_group": g} for md in MODES for zl in ("core", "wide")
        for g in ("treated", "control")]))
    for name in ("agg_fees_month", "agg_quality_month", "agg_fee_values", "agg_vendor_month"):   # last: D25
        write_agg(name, agg_table(name, [{"month": m, "mode": md} for m in MONTHS for md in MODES]))
    write_agg("agg_cbd_pairs", agg_table("agg_cbd_pairs", [{"mode": md} for md in MODES]))
    write_agg("ref_indicators", agg_table("ref_indicators", [
        {"month": m, "Year/Month": common.format_month(m), "License Class": lc}
        for m in MONTHS for lc in ("FHV - High Volume", "Yellow", "Green")]))
    write_zone_lookup(data_dir)


@pytest.fixture
def full(data_dir):
    write_full_fixture(data_dir)
    return data_dir


# --- metric files and contract ------------------------------------------------

def test_every_l09_metric_has_a_file_and_a_test():
    contract = set(metrics._contract_rows())
    assert len(contract) == 29
    assert contract - L10_METRICS == set(metrics.available()) - L10_METRICS
    assert len(contract - L10_METRICS) == 24
    for name in contract - L10_METRICS:
        assert (common.REPO_ROOT / "tests" / f"test_metrics_{name}.py").is_file(), name


@pytest.mark.parametrize("name", sorted(set(metrics.available()) - L10_METRICS))
def test_header_names_questions_params_grain_columns_source(name):
    head = metrics.header(name)
    assert head["metric"] == name
    assert {"questions", "params", "grain", "columns", "source"} <= head.keys()
    columns = [part.split()[0] for part in head["columns"].split(",")]
    assert columns == metrics.contract_schema(name).names
    used = metrics.parameters(name)
    assert head["params"] == (", ".join(f"${p}" for p in sorted(used, key=["to_month", "window", "top_n"].index))
                              if used else "none")


def test_contract_types_follow_first_typed_use_and_defaults():
    schema = metrics.contract_schema("airport_share")
    assert schema.field("month").type == pa.date32()       # typed in share_monthly
    assert schema.field("trips").type == pa.int64()        # typed in share_monthly
    assert schema.field("airport").type == pa.string()     # default text column
    assert schema.field("share").type == pa.float64()
    assert metrics.contract_schema("quality_month").field("rows").type == pa.int64()
    with pytest.raises(metrics.ContractError):
        metrics.contract_schema("no_such_metric")


def test_check_contract_rejects_wrong_order_and_type():
    good = pa.table({"month": pa.array([date(2025, 3, 1)]), "mode": ["uber"],
                     "requests": pa.array([1], pa.int64()), "matched": pa.array([1], pa.int64()),
                     "match_rate": [1.0]})
    metrics.check_contract("wav_match_rate", good)
    with pytest.raises(metrics.ContractError, match="match_rate"):
        metrics.check_contract("wav_match_rate", good.select(["month", "mode", "matched", "requests", "match_rate"]))
    with pytest.raises(metrics.ContractError):
        metrics.check_contract("wav_match_rate", good.set_column(2, "requests", pa.array([1.0])))


# --- views and parameters ------------------------------------------------------

def test_views_cover_every_agg_file_and_refs(full):
    with metrics.connect() as con:
        views = {row[0] for row in con.execute("SELECT view_name FROM duckdb_views() WHERE NOT internal").fetchall()}
        assert views == set(AGG_SCHEMAS) | {"ref_zones", "ref_airports"}
        assert con.execute("SELECT typeof(LocationID), Borough FROM ref_zones WHERE LocationID = 132").fetchone() \
            == ("SMALLINT", "Queens")
        assert con.execute("SELECT airport FROM ref_airports ORDER BY LocationID").fetchall() \
            == [("EWR",), ("JFK",), ("LGA",)]


def test_to_month_defaults_to_latest_agg_zone_hour_month(full):
    table = metrics.run("zone_share_change")
    assert json.loads(table.schema.metadata[b"params"]) == {"to_month": "2025-03-01"}
    assert table.schema.metadata[b"metric"] == b"zone_share_change"


def test_window_and_top_n_defaults(full):
    params = json.loads(metrics.run("top_destinations").schema.metadata[b"params"])
    assert params == {"to_month": "2025-03-01", "top_n": 10}
    params = json.loads(metrics.run("zone_hour_profile").schema.metadata[b"params"])
    assert params == {"to_month": "2025-03-01", "window": 3}


@pytest.mark.parametrize("value", ["2024-03", "2024-03-01", date(2024, 3, 1), date(2024, 3, 17)])
def test_to_month_accepts_month_strings_and_dates(full, value):
    table = metrics.run("airport_fares", to_month=value)
    assert json.loads(table.schema.metadata[b"params"]) == {"to_month": "2024-03-01"}


@pytest.mark.parametrize("params, message", [
    ({"top_n": 5}, "takes no parameter top_n"),
    ({"to_month": "March"}, "to_month"),
    ({"to_month": "2025-03", "window": 0}, "window must be a positive integer"),
    ({"to_month": "2025-03", "window": "two"}, "window"),
])
def test_bad_params_raise(full, params, message):
    with pytest.raises(ValueError, match=message):
        metrics.run("zone_hour_profile", **params)


def test_unknown_metric(full):
    with pytest.raises(KeyError, match="no metric"):
        metrics.run("no_such_metric")


def test_to_month_needs_agg_zone_hour(data_dir):
    write_agg("agg_od_month", agg_table("agg_od_month"))
    with pytest.raises(ValueError, match="agg_zone_hour is missing or empty"):
        metrics.run("top_destinations")


def test_missing_table_names_the_registered_views(data_dir):
    with pytest.raises(RuntimeError, match="registered views"):
        metrics.run("fee_revenue")


def test_source_metadata(full):
    assert metrics.run("trips_per_hour_worked").schema.metadata[b"source"] == b"TLC-reported"
    assert metrics.run("fee_revenue").schema.metadata[b"source"] == b"TLC trip records"


# --- every metric on a full fixture set -----------------------------------------

def test_run_all_on_full_fixture(full):
    results = metrics.run_all()
    failures = {name: result for name, result in results.items() if isinstance(result, Exception)}
    assert not failures
    assert set(results) == set(metrics.available())
    for name, table in results.items():
        assert table.schema.equals(metrics.contract_schema(name)), name
        assert table.num_rows > 0, name


def test_run_all_passes_each_metric_only_its_params(full):
    results = metrics.run_all(to_month="2024-03", top_n=1)
    assert json.loads(results["top_destinations"].schema.metadata[b"params"]) == {"to_month": "2024-03-01", "top_n": 1}
    assert json.loads(results["fare_rates"].schema.metadata[b"params"]) == {}


def _cli(*args):
    return subprocess.run([sys.executable, "-m", "pipeline.metrics", *args],
                          cwd=common.REPO_ROOT, capture_output=True, text=True)


def test_cli_all(full):
    result = _cli("--all", "--param", "to_month=2025-03")
    assert result.returncode == 0, result.stderr
    assert "share_monthly: " in result.stdout and "rows" in result.stdout


def test_cli_one_metric_prints_csv(full):
    result = _cli("wav_match_rate")
    assert result.returncode == 0, result.stderr
    assert result.stdout.splitlines()[0] == '"month","mode","requests","matched","match_rate"'
    assert len(result.stdout.splitlines()) == 1 + len(MONTHS) * 2


def test_cli_reports_failures(data_dir):
    result = _cli("--all")
    assert result.returncode == 1
    assert "FAILED" in result.stderr
    result = _cli("zone_hour_profile", "--param", "nope=1")
    assert result.returncode == 1
    assert "takes no parameter nope" in result.stderr
    assert _cli("share_monthly", "--param", "bad").returncode == 2
