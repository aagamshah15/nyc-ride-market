"""config/schema_map.yaml and its resolver (lane L03)."""

import copy

import pytest
import yaml

from pipeline import common
from pipeline.schema_map import (
    UNIFIED_COLUMNS, ColumnTypeError, MissingColumnError, SchemaError, UnmappedColumnError,
    find_problems, load_schema_map, resolve, select_range,
)
from tests.factories import CLEAN_TRIPS_SCHEMA

# Column lists as the real files spell them (reports/schema_discovery.md).
FHVHV_2024 = [
    "hvfhs_license_num", "dispatching_base_num", "originating_base_num", "request_datetime",
    "on_scene_datetime", "pickup_datetime", "dropoff_datetime", "PULocationID", "DOLocationID",
    "trip_miles", "trip_time", "base_passenger_fare", "tolls", "bcf", "sales_tax",
    "congestion_surcharge", "airport_fee", "tips", "driver_pay", "shared_request_flag",
    "shared_match_flag", "access_a_ride_flag", "wav_request_flag", "wav_match_flag",
]
FHVHV_2025 = FHVHV_2024 + ["cbd_congestion_fee"]
YELLOW_2025 = [
    "VendorID", "tpep_pickup_datetime", "tpep_dropoff_datetime", "passenger_count", "trip_distance",
    "RatecodeID", "store_and_fwd_flag", "PULocationID", "DOLocationID", "payment_type", "fare_amount",
    "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge", "total_amount",
    "congestion_surcharge", "Airport_fee", "cbd_congestion_fee",
]


def test_unified_columns_match_the_clean_schema():
    assert list(UNIFIED_COLUMNS) == CLEAN_TRIPS_SCHEMA.names[:len(UNIFIED_COLUMNS)]
    assert CLEAN_TRIPS_SCHEMA.names[len(UNIFIED_COLUMNS)] == "wait_s"   # first §4.1 derived column


def test_every_unified_column_has_one_source_in_every_range():
    schema_map = load_schema_map()
    assert set(schema_map) == set(common.DATASETS)
    for dataset, ranges in schema_map.items():
        for rng in ranges:
            covered = [spec["unified"] for spec in rng["columns"].values()]
            covered += [*(rng.get("constant") or {}), *(rng.get("nulls") or []), *(rng.get("derived") or {})]
            assert set(covered) == set(UNIFIED_COLUMNS), (dataset, rng["valid_from"])


def test_ranges_cover_every_month_in_scope_and_stay_open():
    schema_map = load_schema_map()
    for dataset in common.DATASETS:
        for month in common.months_in_scope():
            select_range(dataset, month, schema_map)
        assert schema_map[dataset][-1]["valid_to"] is None
        select_range(dataset, "2027-01", schema_map)   # a new TLC month resolves against the latest range


def test_resolve_maps_raw_columns_as_spelled():
    mapping = resolve("yellow", "2025-03", YELLOW_2025, "yellow_tripdata_2025-03.parquet")
    assert mapping["Airport_fee"] == "airport_fee"
    assert mapping["cbd_congestion_fee"] == "cbd_fee"
    assert mapping["total_amount"] == "rider_total_ex_tip"
    assert [c for c, u in mapping.items() if u == "other_fees"] == ["extra", "mta_tax", "improvement_surcharge"]
    assert "VendorID" not in mapping                                      # ignored
    assert list(mapping) == [c for c in YELLOW_2025 if c in mapping]      # file order


@pytest.mark.parametrize("spelling", ["Airport_fee", "airport_fee", "AIRPORT_FEE"])
def test_airport_fee_resolves_in_any_case(spelling):
    columns = [spelling if c == "Airport_fee" else c for c in YELLOW_2025]
    assert resolve("yellow", "2025-03", columns, "f.parquet")[spelling] == "airport_fee"


def test_unmapped_column_names_file_and_column():
    with pytest.raises(UnmappedColumnError) as info:
        resolve("yellow", "2025-03", YELLOW_2025 + ["surge_fee"], "yellow_tripdata_2025-03.parquet")
    assert info.value.file == "yellow_tripdata_2025-03.parquet"
    assert info.value.column == "surge_fee"
    assert "yellow_tripdata_2025-03.parquet" in str(info.value) and "'surge_fee'" in str(info.value)


def test_unmapped_is_reported_before_missing():
    # A rename shows as the new name unmapped, not as the old name missing.
    columns = [("trip_mileage" if c == "trip_miles" else c) for c in FHVHV_2025]
    with pytest.raises(UnmappedColumnError, match="trip_mileage"):
        resolve("fhvhv", "2025-03", columns, "f.parquet")
    problems = find_problems("fhvhv", "2025-03", [(c, None) for c in columns], "f.parquet")
    assert [type(p) for p in problems] == [UnmappedColumnError, MissingColumnError]


def test_missing_required_column_raises():
    columns = [c for c in FHVHV_2025 if c != "driver_pay"]
    with pytest.raises(MissingColumnError) as info:
        resolve("fhvhv", "2025-03", columns, "fhvhv_tripdata_2025-03.parquet")
    assert info.value.column == "driver_pay"
    assert "fhvhv_tripdata_2025-03.parquet" in str(info.value)


def test_ignored_column_passes_and_is_optional():
    without_ignored = [c for c in FHVHV_2025 if c not in ("access_a_ride_flag", "on_scene_datetime")]
    assert resolve("fhvhv", "2025-03", FHVHV_2025, "f") == resolve("fhvhv", "2025-03", without_ignored, "f")


def test_range_boundary_for_cbd_congestion_fee():
    # 2024-12 is the last month without the column, 2025-01 the first with it.
    assert "cbd_congestion_fee" not in resolve("fhvhv", "2024-12", FHVHV_2024, "f")
    assert resolve("fhvhv", "2025-01", FHVHV_2025, "f")["cbd_congestion_fee"] == "cbd_fee"
    with pytest.raises(UnmappedColumnError, match="cbd_congestion_fee"):
        resolve("fhvhv", "2024-12", FHVHV_2025, "f")
    with pytest.raises(MissingColumnError, match="cbd_congestion_fee"):
        resolve("fhvhv", "2025-01", FHVHV_2024, "f")
    assert select_range("fhvhv", "2024-12")["constant"] == {"cbd_fee": 0}
    assert "constant" not in select_range("fhvhv", "2025-01")


def test_range_boundary_for_request_source():
    with pytest.raises(UnmappedColumnError, match="request_source"):
        resolve("yellow", "2026-05", YELLOW_2025 + ["request_source"], "f")
    assert "request_source" not in resolve("yellow", "2026-06", YELLOW_2025 + ["request_source"], "f")


def test_type_mismatch_is_a_problem():
    columns = [(c, "VARCHAR" if c == "PULocationID" else None) for c in FHVHV_2025]
    [problem] = find_problems("fhvhv", "2025-03", columns, "f.parquet")
    assert isinstance(problem, ColumnTypeError)
    assert (problem.column, problem.expected, problem.found) == ("PULocationID", "INTEGER", "VARCHAR")


def test_columns_differing_only_in_case_are_a_problem():
    with pytest.raises(SchemaError, match="differ only in case"):
        resolve("yellow", "2025-03", YELLOW_2025 + ["airport_fee"], "f")


def test_month_without_a_range():
    with pytest.raises(SchemaError, match="no range"):
        resolve("fhvhv", "2019-02", FHVHV_2024, "fhvhv_tripdata_2019-02.parquet")


def test_unknown_dataset():
    with pytest.raises(ValueError):
        resolve("fhv", "2025-03", [], "f")


# --- map consistency ------------------------------------------------------------

def _write_map(tmp_path, schema_map):
    path = tmp_path / "schema_map.yaml"
    path.write_text(yaml.safe_dump(schema_map))
    return path


def _two_range_map():
    return copy.deepcopy({"fhvhv": load_schema_map()["fhvhv"]})


def test_copied_map_is_valid(tmp_path):
    load_schema_map(_write_map(tmp_path, _two_range_map()))


@pytest.mark.parametrize("break_it, message", [
    (lambda m: m["fhvhv"][1].update(valid_from="2025-02"), "not the month after"),
    (lambda m: m["fhvhv"][0].update(valid_to=None), "only the last range"),
    (lambda m: m["fhvhv"][0].update(valid_to="2023-12"), "valid_to is before valid_from"),
    (lambda m: m["fhvhv"][0]["columns"]["bcf"].update(unified="black_car_fund"), "not a SPEC §4 unified column"),
    (lambda m: m["fhvhv"][0]["columns"].pop("driver_pay"), "'driver_pay' is covered by nothing"),
    (lambda m: m["fhvhv"][0]["nulls"].append("tips"), "'tips' is covered by columns and nulls"),
    (lambda m: m["fhvhv"][0]["ignore"].update(TIPS="duplicate"), "listed twice"),
    (lambda m: m["fhvhv"][0]["ignore"].update(extra_col=""), "needs a one-line reason"),
    (lambda m: m["fhvhv"][0]["columns"]["bcf"].pop("type"), "needs unified and type"),
    (lambda m: m["fhvhv"][0].update(columnz={}), "unknown keys"),
    (lambda m: m.update(fhv=m["fhvhv"]), "unknown dataset"),
])
def test_inconsistent_map_is_rejected(tmp_path, break_it, message):
    schema_map = _two_range_map()
    break_it(schema_map)
    with pytest.raises(SchemaError, match=message):
        load_schema_map(_write_map(tmp_path, schema_map))
