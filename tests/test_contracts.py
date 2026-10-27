"""Contracts (L01): examples, mocks, budgets, tile registry, factories and the checker."""

import importlib.util
import json
import re
import subprocess
from datetime import date, datetime

import duckdb
import pytest
import yaml
from contract_check import assert_matches_contract, contract_errors
from factories import (AGG_SCHEMAS, CLEAN_TRIPS_SCHEMA, agg_row, agg_table, clean_trips, make_trip,
                       write_agg, write_clean)

from pipeline import common

REPO_ROOT = common.REPO_ROOT
CONTRACTS = REPO_ROOT / "contracts"
SITE_CONTRACTS = CONTRACTS / "site"


def _load_mock_module():
    spec = importlib.util.spec_from_file_location("make_mock_site_data", REPO_ROOT / "scripts" / "make_mock_site_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mock = _load_mock_module()
PAGES = yaml.safe_load((SITE_CONTRACTS / "pages.yaml").read_text())
TILES = yaml.safe_load((SITE_CONTRACTS / "tiles.yaml").read_text())


def _example(name: str):
    return json.loads((SITE_CONTRACTS / name).read_text())


def _route_files(route: dict) -> list[list[str]]:
    """Every concrete file list for a route (one per parameter value)."""
    params = route.get("params") or {}
    if not params:
        return [route["files"]]
    (key, values), = params.items()
    if isinstance(values, str):
        first, last = (int(v) for v in values.split(".."))
        values = [str(v) for v in range(first, last + 1)]
    return [[f.format(**{key: v}) for f in route["files"]] for v in values]


@pytest.fixture(scope="module")
def mock_dir(tmp_path_factory):
    out = tmp_path_factory.mktemp("site_data")
    mock.write_data(out)
    return out


# --- examples and mocks ------------------------------------------------------

def test_examples_are_up_to_date():
    for name, obj in mock.build_examples().items():
        assert _example(name) == obj, f"{name} is stale: run python scripts/make_mock_site_data.py --examples"


def test_every_route_file_has_an_example():
    for route in PAGES["routes"].values():
        for files in _route_files(route)[:2]:
            for path in files:
                assert (SITE_CONTRACTS / mock.example_name(path)).exists(), path


def test_mocks_match_their_examples(mock_dir):
    paths = sorted(p for p in mock_dir.rglob("*") if p.is_file())
    assert len(paths) == len(mock.EXAMPLES) - 2 + 4 + 263   # companies and zones patterns expand
    for path in paths:
        rel = path.relative_to(mock_dir).as_posix()
        assert_matches_contract(json.loads(path.read_text()), _example(mock.example_name(rel)), rel)


def test_mocks_carry_the_envelope(mock_dir):
    for path in mock_dir.rglob("*.json"):
        data = json.loads(path.read_text())
        assert data["as_of_month"] == "MOCK"
        assert data["validated"] is False
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["generated_at"])


def test_mock_routes_fit_their_budgets(mock_dir):
    for name, route in PAGES["routes"].items():
        for files in _route_files(route):
            size = sum((mock_dir / f).stat().st_size for f in files)
            assert size <= PAGES["budget_bytes"], f"{name} {files[0]}: {size} bytes"
    for path in (mock_dir / "zones").glob("[0-9]*.json"):
        assert path.stat().st_size < PAGES["zone_file_max_bytes"], path.name


def test_pages_yaml_routes():
    anchors = set(PAGES["methods_anchors"])
    for name, route in PAGES["routes"].items():
        assert route["source"].endswith(".md"), name
        assert route["methods"] is None or route["methods"] in anchors, name
    assert {"/", "/zones", "/methods"} <= PAGES["routes"].keys()


def test_mock_refuses_to_overwrite_real_data(tmp_path):
    (tmp_path / "home.json").write_text(json.dumps({"as_of_month": "2026-08"}))
    with pytest.raises(SystemExit, match="real data"):
        mock.write_data(tmp_path)


def test_no_mock_data_is_tracked():
    try:
        tracked = subprocess.run(["git", "ls-files", "site/src/data"], cwd=REPO_ROOT,
                                 capture_output=True, text=True, check=True).stdout.split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("not a git checkout")
    for rel in tracked:
        path = REPO_ROOT / rel
        if path.suffix == ".json" and path.exists():
            assert json.loads(path.read_text()).get("as_of_month") != "MOCK", f"mock data tracked: {rel}"


# --- tile registry -----------------------------------------------------------

UNITS = {"count", "share", "usd", "usd_per_mile", "usd_per_minute", "usd_per_hour", "seconds",
         "trips_per_hour", "ratio", "effect", "hour_of_day", "hour_of_week", "text"}


def test_tile_registry_is_well_formed():
    for key, meta in TILES.items():
        assert set(meta) == {"label", "unit", "yoy"}, key
        assert meta["unit"] in UNITS, key
        assert meta["yoy"] in {"relative", "pts", "diff", "none"}, key


def test_every_tile_is_registered(mock_dir):
    for path in mock_dir.rglob("*.json"):
        data = json.loads(path.read_text())
        if "tiles" in data and path.name != "tiles.json":
            assert data["tiles"].keys() <= TILES.keys(), path.name
            assert data["yoy"].keys() == data["tiles"].keys(), path.name
            for key, change in data["yoy"].items():
                if TILES[key]["yoy"] == "none":
                    assert change is None, f"{path.name}: {key}"


# --- metrics contract --------------------------------------------------------

def test_metric_names_are_unique_and_snake_case():
    names = re.findall(r"^\| `([a-z0-9_]+)`", (CONTRACTS / "metrics.md").read_text(), flags=re.M)
    assert len(names) == len(set(names)) > 20
    assert {"trip_share", "driver_share", "cp_effect", "pay_event"} <= set(names)


# --- factories ---------------------------------------------------------------

SPEC_CLEAN_COLUMNS = {   # SPEC §4, §4.1, §4.2 (+ D9 wide-list flags, D25 vendor_id)
    "mode", "month", "request_ts", "pickup_ts", "dropoff_ts", "pu_zone", "do_zone", "miles",
    "duration_s", "fare_base", "tips", "tolls", "airport_fee", "congestion_surcharge", "cbd_fee",
    "other_fees", "rider_total_ex_tip", "driver_pay", "is_card", "shared_request", "shared_match",
    "wav_request", "wav_match", "street_hail", "wait_s", "hour_of_week", "pu_borough", "do_borough",
    "airport_pu", "airport_do", "cbd_pu", "cbd_do", "cbd_touch", "period", "f_time", "f_miles",
    "f_fare", "f_zone", "f_wait", "is_valid", "cbd_pu_wide", "cbd_do_wide", "cbd_touch_wide",
    "vendor_id",                                               # D25
}

SPEC_AGG_COLUMNS = {     # SPEC §5 (+ D7–D10, D15, D25)
    "agg_zone_hour": "month mode pu_zone hour_of_week trips_all trips_valid miles duration_s fare_base "
                     "rider_total_ex_tip driver_pay tips card_trips card_tips card_fare_base wait_s_sum "
                     "wait_n cbd_fee shared_req shared_match wav_req wav_match",
    "agg_zone_month_dist": "month mode pu_zone n fpm_p10 fpm_p50 fpm_p90 fpmin_p50 wait_p50 wait_p90",
    "agg_od_month": "month mode pu_zone do_zone trips_valid miles duration_s fare_base driver_pay "
                    "rider_total_ex_tip",
    "agg_airport": "month mode airport direction hour_of_day trips_valid miles duration_s fare_base "
                   "rider_total_ex_tip tips",
    "agg_week_cbd": "month iso_year iso_week mode zone_list cbd_group trips_all trips_valid miles "
                    "duration_s fare_base driver_pay rider_total_ex_tip",
    "agg_fees_month": "month mode cbd_fee congestion_surcharge airport_fee trips_with_cbd_fee",
    "agg_quality_month": "month mode rows valid_rows f_time f_miles f_fare f_zone f_wait",
    "agg_cbd_pairs": "month mode pu_zone do_zone trips_all trips_cbd_fee",
    "agg_fee_values": "month mode cbd_fee trips",
    "agg_vendor_month": "month mode vendor_id rows",          # D25
    "ref_indicators": "month",
}


def test_clean_schema_covers_spec():
    assert set(CLEAN_TRIPS_SCHEMA.names) == SPEC_CLEAN_COLUMNS


def test_agg_schemas_cover_spec():
    assert AGG_SCHEMAS.keys() == SPEC_AGG_COLUMNS.keys()
    for name, columns in SPEC_AGG_COLUMNS.items():
        assert set(columns.split()) <= set(AGG_SCHEMAS[name].names), name
        if name != "ref_indicators":
            assert len(columns.split()) == len(AGG_SCHEMAS[name].names), name


def test_default_trip_derivations():
    trip = make_trip()
    assert trip["month"] == date(2025, 3, 1)
    assert trip["duration_s"] == 1200 and trip["wait_s"] == 240
    assert trip["hour_of_week"] == 2 * 24 + 8          # Tuesday 08:xx, Sunday = 0
    assert trip["period"] == "post_cp"
    assert trip["rider_total_ex_tip"] == pytest.approx(18.50 + 0 + 2.10 + 2.75 + 0 + 1.50)
    assert trip["cbd_touch"] and trip["is_valid"]


@pytest.mark.parametrize("pickup, expected", [
    (datetime(2025, 1, 4, 23, 59, 59), "pre_cp"),
    (datetime(2025, 1, 5, 0, 0), "post_cp"),
    (datetime(2025, 8, 1, 0, 0), "post_pay"),
])
def test_trip_period_boundaries(pickup, expected):
    assert make_trip(pickup_ts=pickup)["period"] == expected


def test_hour_of_week_ends():
    assert make_trip(pickup_ts=datetime(2025, 3, 2, 0, 30))["hour_of_week"] == 0      # Sunday
    assert make_trip(pickup_ts=datetime(2025, 3, 8, 23, 30))["hour_of_week"] == 167   # Saturday


def test_taxi_trip_defaults():
    trip = make_trip(mode="yellow")
    assert trip["request_ts"] is None and trip["wait_s"] is None and trip["driver_pay"] is None
    assert trip["is_card"] is True and trip["cbd_fee"] == 0.75
    assert make_trip(mode="green")["street_hail"] is True


def test_flags_drive_is_valid():
    assert make_trip(f_miles=True)["is_valid"] is False
    assert make_trip(f_wait=True)["is_valid"] is True       # f_wait isn't part of is_valid (SPEC §4.2)


def test_unknown_columns_are_rejected():
    with pytest.raises(KeyError):
        make_trip(fare=1.0)
    with pytest.raises(KeyError):
        agg_row("agg_zone_hour", trips=1)


def test_clean_trips_round_trip_through_duckdb(data_dir):
    trips = clean_trips([{}, {"mode": "yellow"}, {"pickup_ts": datetime(2025, 4, 1, 9, 0)}])
    assert trips.schema == CLEAN_TRIPS_SCHEMA
    written = write_clean(trips)
    assert len(written) == 3
    glob = common.sql_literal(str(common.clean_dir() / "**" / "*.parquet"))
    con = duckdb.connect()
    rows = con.execute(f"SELECT mode, month, count(*) FROM read_parquet({glob}, hive_partitioning = false) "
                       "GROUP BY ALL ORDER BY ALL").fetchall()
    assert rows == [("uber", date(2025, 3, 1), 1), ("uber", date(2025, 4, 1), 1), ("yellow", date(2025, 3, 1), 1)]


@pytest.mark.parametrize("name", sorted(AGG_SCHEMAS))
def test_agg_tables_round_trip_through_duckdb(name, data_dir):
    second = {"mode": "yellow"} if "mode" in AGG_SCHEMAS[name].names else {"License Class": "Yellow"}
    table = agg_table(name, [{}, second])
    path = write_agg(name, table)
    con = duckdb.connect()
    columns = [row[0] for row in con.execute(
        f"DESCRIBE SELECT * FROM read_parquet({common.sql_literal(str(path))})").fetchall()]
    assert columns == AGG_SCHEMAS[name].names
    assert con.execute(f"SELECT count(*) FROM read_parquet({common.sql_literal(str(path))})").fetchone()[0] == 2


def test_taxi_agg_defaults_are_null_where_not_reported():
    row = agg_row("agg_zone_hour", mode="yellow")
    assert row["driver_pay"] is None and row["wait_n"] is None and row["wav_req"] is None
    assert row["card_trips"] == 80


# --- the checker itself ------------------------------------------------------

EXAMPLE = {"a": 1, "b": "x", "c": [{"d": 1.5, "e": None}, {"d": 2, "e": "y"}], "f": {"g": True}}


def test_checker_accepts_a_match_and_nulls():
    assert contract_errors({"a": 2, "b": "z", "c": [{"d": 3, "e": "w"}], "f": {"g": False}}, EXAMPLE) == []
    assert contract_errors({"a": None, "b": "z", "c": [], "f": None}, EXAMPLE) == []


@pytest.mark.parametrize("actual, problem", [
    ({"b": "x", "c": [], "f": {"g": True}}, "$.a: missing"),
    ({**EXAMPLE, "z": 1}, "$.z: not in contract"),
    ({**EXAMPLE, "a": "1"}, "$.a: expected number, got string"),
    ({**EXAMPLE, "c": [{"d": 1, "e": 5}]}, "$.c[0].e: expected string, got number"),
    ({**EXAMPLE, "c": [{"d": 1}]}, "$.c[0].e: missing"),
    ({**EXAMPLE, "f": {"g": 1}}, "$.f.g: expected boolean, got number"),
])
def test_checker_reports_departures(actual, problem):
    assert problem in contract_errors(actual, EXAMPLE)


def test_assert_matches_contract_raises():
    with pytest.raises(AssertionError, match="missing"):
        assert_matches_contract({}, {"a": 1})
