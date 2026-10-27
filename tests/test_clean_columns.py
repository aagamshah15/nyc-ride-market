"""Clean (lane L06): the SPEC §4 unified columns, the §4.1 lookups and the schema-map checks.

Expected values are worked out by hand in the comments, from the raw defaults in
tests/fixtures/raw/raw_trips.py (pickup on the month's 4th at 08:10, dropoff 20 min later):

- fhvhv: fare 18.50, tolls 0, bcf 0.51, sales tax 1.64, congestion 2.75, airport fee 0, cbd 1.50, so
  other_fees = 0.51 + 1.64 = 2.15 and rider_total_ex_tip = 18.50 + 0 + 2.15 + 2.75 + 0 + 1.50 = 24.90
- yellow: total = 18.40 + 1.00 + 0.50 + 4.00 (tip) + 0 + 1.00 + 2.50 + 0 + 0.75 = 28.15, so
  rider_total_ex_tip = 28.15 − 4.00 = 24.15 and other_fees = 1.00 + 0.50 + 1.00 = 2.50
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline import clean, common, schema_map
from tests.factories import CLEAN_TRIPS_SCHEMA
from tests.fixtures.raw.raw_trips import pickup, raw_table, write_month, write_raw

MARCH = "2025-03"
P = pickup(MARCH)   # 2025-03-04 08:10


def part(mode: str, month: str = MARCH):
    return common.clean_partition(mode, month) / "part-0.parquet"


def read(mode: str, month: str = MARCH) -> list[dict]:
    return pq.read_table(part(mode, month)).to_pylist()


def one(mode: str, month: str = MARCH) -> dict:
    rows = read(mode, month)
    assert len(rows) == 1, rows
    return rows[0]


def test_each_mode_file_matches_the_clean_schema_exactly():
    write_month(MARCH, fhvhv=[{}, {"hvfhs_license_num": "HV0005"}, {"hvfhs_license_num": "HV0004"}])
    clean.clean_month(MARCH)
    for mode in common.MODES:
        schema = pq.read_schema(part(mode))
        assert schema.equals(CLEAN_TRIPS_SCHEMA), (mode, schema)
        # self-contained files (D18): mode and month are columns, read without hive partitioning
        assert {(r["mode"], r["month"]) for r in read(mode)} == {(mode, date(2025, 3, 1))}


def test_licence_codes_map_to_modes():
    write_month(MARCH, fhvhv=[{"hvfhs_license_num": code} for code in ("HV0003", "HV0005", "HV0002", "HV0004")])
    counts = clean.clean_month(MARCH)
    assert {mode: c["rows"] for mode, c in counts.items()} == {
        "uber": 1, "lyft": 1, "other_hv": 2, "yellow": 1, "green": 1}


def test_unknown_licence_code_stops_the_run():
    write_month(MARCH, fhvhv=[{}, {"hvfhs_license_num": "HV0009"}])
    with pytest.raises(clean.CleanError, match=r"raw/fhvhv/2025-03\.parquet: hvfhs_license_num 'HV0009'"):
        clean.clean_month(MARCH)
    assert not common.clean_dir().joinpath("mode=uber").exists()


def test_hvfhv_columns():
    write_month(MARCH, fhvhv=[{
        "trip_time": 1234,                         # duration comes from trip_time, not the timestamps
        "airport_fee": 2.50, "tolls": 6.94,
        "shared_request_flag": "Y", "shared_match_flag": "N", "wav_request_flag": "Y", "wav_match_flag": "Y",
    }])
    clean.clean_month(MARCH)
    trip = one("uber")
    assert trip["request_ts"] == P - timedelta(minutes=4)
    assert (trip["pu_zone"], trip["do_zone"], trip["miles"]) == (161, 236, 3.2)
    assert trip["duration_s"] == 1234
    assert (trip["fare_base"], trip["tips"], trip["driver_pay"]) == (18.50, 3.00, 14.20)
    assert trip["cbd_fee"] == 1.50
    assert trip["other_fees"] == pytest.approx(2.15)                 # 0.51 + 1.64
    # 18.50 + 6.94 tolls + 2.15 + 2.75 + 2.50 airport + 1.50 cbd
    assert trip["rider_total_ex_tip"] == pytest.approx(34.34)
    assert (trip["shared_request"], trip["shared_match"], trip["wav_request"], trip["wav_match"]) == (
        True, False, True, True)
    assert (trip["is_card"], trip["street_hail"], trip["vendor_id"]) == (None, None, None)
    assert trip["wait_s"] == 240                                     # 4 min


def test_rider_total_ex_tip_hvfhv_and_yellow():
    write_month(MARCH)
    clean.clean_month(MARCH)
    assert one("uber")["rider_total_ex_tip"] == pytest.approx(24.90)
    yellow = one("yellow")
    assert yellow["rider_total_ex_tip"] == pytest.approx(24.15)      # 28.15 − 4.00
    assert yellow["other_fees"] == pytest.approx(2.50)
    assert yellow["tips"] == 4.00


def test_month_is_the_files_month_not_the_pickup_month():
    # a pickup on 28 Feb inside the March file is still a March trip
    write_month(MARCH, yellow=[{"tpep_pickup_datetime": datetime(2025, 2, 28, 23, 50),
                                "tpep_dropoff_datetime": datetime(2025, 3, 1, 0, 10)}])
    clean.clean_month(MARCH)
    trip = one("yellow")
    assert trip["month"] == date(2025, 3, 1)
    assert trip["duration_s"] == 1200
    assert trip["f_time"] is False


def test_null_cbd_fee_becomes_zero():
    write_month(MARCH, fhvhv=[{"cbd_congestion_fee": None}], yellow=[{"cbd_congestion_fee": None}],
                green=[{"cbd_congestion_fee": None}])
    clean.clean_month(MARCH)
    assert [one(mode)["cbd_fee"] for mode in ("uber", "yellow", "green")] == [0.0, 0.0, 0.0]
    # 18.50 + 0 + 2.15 + 2.75 + 0 + 0
    assert one("uber")["rider_total_ex_tip"] == pytest.approx(23.40)


def test_2024_files_have_no_cbd_column_and_get_zero():
    write_month("2024-03")
    clean.clean_month("2024-03")
    for mode in ("uber", "yellow", "green"):
        trip = one(mode, "2024-03")
        assert trip["cbd_fee"] == 0.0
        assert trip["period"] == "pre_cp"
    assert one("uber", "2024-03")["rider_total_ex_tip"] == pytest.approx(23.40)    # 24.90 − 1.50
    assert one("yellow", "2024-03")["rider_total_ex_tip"] == pytest.approx(23.40)  # (28.15 − 0.75) − 4.00


def test_yellow_columns_and_the_airport_fee_spelling():
    end = P + timedelta(minutes=17, seconds=5)
    write_month(MARCH, yellow=[
        {"Airport_fee": 1.75, "tpep_dropoff_datetime": end},          # card, airport fee
        {"payment_type": 2, "tip_amount": 0.0},                       # cash
    ])
    clean.clean_month(MARCH)
    card, cash = sorted(read("yellow"), key=lambda r: r["duration_s"])
    assert card["duration_s"] == 1025                                 # 17 min 5 s, from the timestamps
    assert card["airport_fee"] == 1.75
    assert card["rider_total_ex_tip"] == pytest.approx(25.90)         # (28.15 + 1.75) − 4.00
    assert (card["is_card"], cash["is_card"]) == (True, False)
    assert cash["rider_total_ex_tip"] == pytest.approx(24.15)         # 24.15 − 0 tip
    for column in ("request_ts", "wait_s", "driver_pay", "shared_request", "wav_match", "street_hail"):
        assert card[column] is None, column
    assert card["f_wait"] is False


def test_cab_vendor_id_comes_through_and_ride_hail_has_none():
    # D25: the cab files' VendorID becomes vendor_id; HVFHV files have no vendor column
    write_month(MARCH, fhvhv=[{}, {"hvfhs_license_num": "HV0005"}],
                yellow=[{"tip_amount": 0.0}, {"VendorID": 6, "tip_amount": 1.0}, {"VendorID": 7, "tip_amount": 2.0}],
                green=[{"VendorID": 1}, {"VendorID": 6}])
    clean.clean_month(MARCH)
    assert {r["tips"]: r["vendor_id"] for r in read("yellow")} == {0.0: 2, 1.0: 6, 2.0: 7}
    assert sorted(r["vendor_id"] for r in read("green")) == [1, 6]
    assert [r["vendor_id"] for r in read("uber") + read("lyft")] == [None, None]
    # vendor 6 is kept like any other vendor: flags don't read vendor_id
    assert all(r["is_valid"] for r in read("yellow") + read("green"))


def test_lower_case_airport_fee_is_matched_too():
    table = raw_table("yellow", MARCH, [{"Airport_fee": 1.75}])
    table = table.rename_columns([("airport_fee" if n == "Airport_fee" else n) for n in table.column_names])
    write_month(MARCH)
    write_raw("yellow", MARCH, table=table)
    clean.clean_month(MARCH)
    assert one("yellow")["airport_fee"] == 1.75


def test_green_columns():
    write_month(MARCH, green=[{}, {"trip_type": 2, "payment_type": 2, "tip_amount": 0.0}])
    clean.clean_month(MARCH)
    hail, dispatch = sorted(read("green"), key=lambda r: not r["street_hail"])
    assert (hail["street_hail"], dispatch["street_hail"]) == (True, False)
    assert (hail["is_card"], dispatch["is_card"]) == (True, False)
    assert hail["airport_fee"] == 0.0                                 # green files have no airport fee
    # total 12.10 + 1.00 + 0.50 + 2.00 + 0 + 1.00 + 0 + 0 = 16.60; minus the 2.00 tip
    assert hail["rider_total_ex_tip"] == pytest.approx(14.60)
    assert (hail["pu_borough"], hail["do_borough"]) == ("Manhattan", "Manhattan")


def test_boroughs_airports_and_both_congestion_zone_lists():
    write_month(MARCH, fhvhv=[
        {"PULocationID": 132, "DOLocationID": 161},     # JFK → Midtown Center (core)
        {"PULocationID": 43, "DOLocationID": 138},      # Central Park (borderline, wide only) → LGA
        {"PULocationID": 1, "DOLocationID": 236},       # Newark → Upper East Side North (in neither)
        {"PULocationID": 264, "DOLocationID": None},    # unknown → NULL
    ])
    clean.clean_month(MARCH)
    trips = {r["pu_zone"]: r for r in read("uber")}
    jfk, park, ewr, unknown = trips[132], trips[43], trips[1], trips[264]

    assert (jfk["pu_borough"], jfk["do_borough"], jfk["airport_pu"], jfk["airport_do"]) == (
        "Queens", "Manhattan", "JFK", None)
    assert (jfk["cbd_pu"], jfk["cbd_do"], jfk["cbd_touch"]) == (False, True, True)
    assert (jfk["cbd_pu_wide"], jfk["cbd_do_wide"], jfk["cbd_touch_wide"]) == (False, True, True)

    assert park["airport_do"] == "LGA"
    assert (park["cbd_pu"], park["cbd_touch"]) == (False, False)
    assert (park["cbd_pu_wide"], park["cbd_touch_wide"]) == (True, True)

    assert (ewr["pu_borough"], ewr["airport_pu"]) == ("EWR", "EWR")
    assert (ewr["cbd_touch"], ewr["cbd_touch_wide"]) == (False, False)

    assert (unknown["pu_borough"], unknown["do_zone"], unknown["do_borough"]) == ("Unknown", None, None)
    assert (unknown["cbd_pu"], unknown["cbd_do"], unknown["cbd_touch_wide"]) == (False, False, False)


# --- schema map ------------------------------------------------------------------

def test_unmapped_column_stops_the_run_naming_file_and_column(capsys):
    table = raw_table("yellow", MARCH).append_column("surge_fee", pa.array([1.0]))
    write_month(MARCH)
    write_raw("yellow", MARCH, table=table)
    with pytest.raises(schema_map.UnmappedColumnError) as exc:
        clean.clean_month(MARCH)
    assert (exc.value.file, exc.value.column) == ("raw/yellow/2025-03.parquet", "surge_fee")

    with pytest.raises(SystemExit) as stop:
        clean.main(["--month", MARCH])
    assert stop.value.code == 1
    err = capsys.readouterr().err
    assert "raw/yellow/2025-03.parquet" in err and "'surge_fee'" in err
    assert not common.clean_dir().joinpath("mode=uber").exists()


def test_missing_mapped_column_stops_the_run():
    write_month(MARCH)
    write_raw("green", MARCH, table=raw_table("green", MARCH).drop_columns(["tolls_amount"]))
    with pytest.raises(schema_map.MissingColumnError) as exc:
        clean.clean_month(MARCH)
    assert (exc.value.file, exc.value.column) == ("raw/green/2025-03.parquet", "tolls_amount")


def test_changed_column_type_stops_the_run():
    table = raw_table("fhvhv", MARCH)
    i = table.column_names.index("PULocationID")
    table = table.set_column(i, "PULocationID", table["PULocationID"].cast(pa.int64()))
    write_month(MARCH)
    write_raw("fhvhv", MARCH, table=table)
    with pytest.raises(schema_map.ColumnTypeError) as exc:
        clean.clean_month(MARCH)
    assert (exc.value.column, exc.value.found, exc.value.expected) == ("PULocationID", "BIGINT", "INTEGER")


def test_2026_06_cab_files_ignore_request_source():
    write_month("2026-08", yellow=[{"request_source": "HV0005"}], green=[{"request_source": "A"}])
    counts = clean.clean_month("2026-08")
    assert (counts["yellow"]["rows"], counts["green"]["rows"]) == (1, 1)
    assert "request_source" not in pq.read_schema(part("yellow", "2026-08")).names
