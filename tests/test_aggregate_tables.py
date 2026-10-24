"""Aggregate tables (lane L07): sums, percentiles, thresholds and airport direction on factory trips.

Expected values are worked out by hand in the comments. Factory defaults (tests/factories.py):
a valid Tuesday 2025-03-04 08:10 trip (hour_of_week 2 × 24 + 8 = 56), zone 161 → 236, 3.2 miles,
20 min (1200 s), fare_base 18.50, tips 3.00, no tolls or airport fee. Ride-hail: congestion
surcharge 2.75, cbd_fee 1.50, other_fees 2.10, driver_pay 14.20, request 4 min before pickup
(wait 240 s), so rider_total_ex_tip = 18.50 + 2.10 + 2.75 + 1.50 = 24.85. Cabs: surcharge 2.50,
cbd_fee 0.75, other_fees 2.00, card, so rider_total_ex_tip = 18.50 + 2.00 + 2.50 + 0.75 = 23.75.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pyarrow.parquet as pq
import pytest

from pipeline import aggregate, common
from tests.factories import AGG_SCHEMAS, clean_trips, write_clean

MARCH = "2025-03"
P = datetime(2025, 3, 4, 8, 10)   # the factory's default pickup


def build(trips, month: str = MARCH) -> None:
    write_clean(trips)
    aggregate.aggregate_month(month)


def rows(table: str, **match) -> list[dict]:
    out = pq.read_table(common.agg_path(table)).to_pylist()
    return [r for r in out if all(r[k] == v for k, v in match.items())]


def one(table: str, **match) -> dict:
    found = rows(table, **match)
    assert len(found) == 1, found
    return found[0]


def test_tables_cover_every_aggregate_schema():
    assert set(aggregate.TABLES) == set(AGG_SCHEMAS) - {"ref_indicators"}


def test_every_table_matches_its_schema_exactly():
    build(clean_trips([{}, {"mode": "yellow"}, {"mode": "lyft", "pu_zone": 132, "airport_pu": "JFK"}]))
    for table in aggregate.TABLES:
        schema = pq.read_schema(common.agg_path(table))
        assert schema.equals(AGG_SCHEMAS[table]), (table, schema)
    # agg_zone_month_dist and agg_od_month are empty here (n < 100, pairs < 20): the file and its
    # schema are written anyway
    assert rows("agg_zone_month_dist") == []
    assert rows("agg_od_month") == []


def test_zone_hour_sums():
    build(clean_trips([
        {},                                                                        # uber A
        {"fare_base": 20.0, "miles": 4.0, "driver_pay": 15.0, "tips": 0.0,         # uber B
         "request_ts": P - timedelta(minutes=6),
         "shared_request": True, "shared_match": True, "wav_request": True},
        {"miles": 0.0, "f_miles": True},                                           # uber C: invalid
        {"request_ts": P - timedelta(seconds=4000), "f_wait": True},               # uber D: wait flagged
        {"pu_zone": 264, "f_zone": True},                                          # uber E: unknown zone
        {"mode": "yellow"},                                                        # yellow F: card
        {"mode": "yellow", "fare_base": 10.0, "tips": 0.0, "is_card": False},      # yellow G: cash
        {"mode": "yellow", "fare_base": 0.0, "f_fare": True},                      # yellow H: invalid
    ]))
    uber = one("agg_zone_hour", mode="uber", pu_zone=161)
    # A, B, C, D share zone 161 and hour 56; C is invalid, so valid = A, B, D
    assert uber["hour_of_week"] == 56
    assert (uber["trips_all"], uber["trips_valid"]) == (4, 3)
    assert uber["miles"] == pytest.approx(10.4)                  # 3.2 + 4.0 + 3.2
    assert uber["duration_s"] == 3600                            # 3 × 1200
    assert uber["fare_base"] == pytest.approx(57.0)              # 18.5 + 20 + 18.5
    assert uber["rider_total_ex_tip"] == pytest.approx(76.05)    # 24.85 + (20 + 2.10 + 2.75 + 1.50) + 24.85
    assert uber["driver_pay"] == pytest.approx(43.4)             # 14.2 + 15.0 + 14.2
    assert uber["tips"] == pytest.approx(6.0)                    # 3 + 0 + 3
    assert uber["wait_s_sum"] == 600                             # A 240 + B 360; D has f_wait, C is invalid
    assert uber["wait_n"] == 2
    assert uber["cbd_fee"] == pytest.approx(4.5)                 # 3 × 1.50
    assert (uber["shared_req"], uber["shared_match"], uber["wav_req"], uber["wav_match"]) == (1, 1, 1, 0)
    assert (uber["card_trips"], uber["card_tips"], uber["card_fare_base"]) == (None, None, None)

    # E is alone in zone 264 with no valid row: counted in trips_all, every sum 0
    unknown = one("agg_zone_hour", mode="uber", pu_zone=264)
    assert (unknown["trips_all"], unknown["trips_valid"]) == (1, 0)
    assert (unknown["miles"], unknown["fare_base"], unknown["driver_pay"]) == (0.0, 0.0, 0.0)
    assert (unknown["wait_s_sum"], unknown["wait_n"], unknown["shared_req"]) == (0, 0, 0)

    yellow = one("agg_zone_hour", mode="yellow")
    # F and G valid, H invalid
    assert (yellow["trips_all"], yellow["trips_valid"]) == (3, 2)
    assert yellow["miles"] == pytest.approx(6.4)
    assert yellow["duration_s"] == 2400
    assert yellow["fare_base"] == pytest.approx(28.5)            # 18.5 + 10
    assert yellow["rider_total_ex_tip"] == pytest.approx(39.0)   # 23.75 + (10 + 2.00 + 2.50 + 0.75)
    assert yellow["tips"] == pytest.approx(3.0)
    assert yellow["card_trips"] == 1                             # F
    assert yellow["card_tips"] == pytest.approx(3.0)
    assert yellow["card_fare_base"] == pytest.approx(18.5)
    assert yellow["cbd_fee"] == pytest.approx(1.5)               # 2 × 0.75
    for column in ("driver_pay", "wait_s_sum", "wait_n", "shared_req", "shared_match", "wav_req", "wav_match"):
        assert yellow[column] is None, column

    # every row of the month is in exactly one group (tie-out)
    assert sum(r["trips_all"] for r in rows("agg_zone_hour")) == 8


def test_zone_hour_groups_by_hour_of_week():
    build(clean_trips([
        {"pickup_ts": datetime(2025, 3, 2, 0, 30)},     # Sunday 00:30 → 0
        {"pickup_ts": datetime(2025, 3, 8, 23, 10)},    # Saturday 23:10 → 6 × 24 + 23 = 167
        {"pickup_ts": datetime(2025, 3, 15, 23, 50)},   # another Saturday 23:xx → 167
    ]))
    assert {r["hour_of_week"]: r["trips_all"] for r in rows("agg_zone_hour")} == {0: 1, 167: 2}


def test_percentiles_on_five_trips(monkeypatch):
    monkeypatch.setattr(aggregate, "DIST_MIN_N", 5)
    # (fare_base, wait seconds); 2 miles and 10 minutes each, listed out of order
    trips = [(12.0, 300), (4.0, 60), (20.0, 180), (8.0, 240), (16.0, 120)]
    build(clean_trips([
        {"fare_base": fare, "miles": 2.0, "dropoff_ts": P + timedelta(minutes=10),
         "request_ts": P - timedelta(seconds=wait)}
        for fare, wait in trips
    ]))
    # fare per mile 2, 4, 6, 8, 10. quantile_cont at position (n − 1) · p:
    #   p10 → 0.4 → 2 + 0.4 × 2 = 2.8;  p50 → 2 → 6;  p90 → 3.6 → 8 + 0.6 × 2 = 9.2
    # fare per minute = fare / 10 → 0.4 … 2.0, median 1.2
    # waits 60 … 300: median 180; p90 → 3.6 → 240 + 0.6 × 60 = 276
    expected_keys = {("uber", 161), ("uber", 0), ("ride_hail", 0), ("all", 0)}
    assert {(r["mode"], r["pu_zone"]) for r in rows("agg_zone_month_dist")} == expected_keys
    for mode, zone in expected_keys:
        row = one("agg_zone_month_dist", mode=mode, pu_zone=zone)
        assert row["n"] == 5
        assert row["fpm_p10"] == pytest.approx(2.8)
        assert row["fpm_p50"] == pytest.approx(6.0)
        assert row["fpm_p90"] == pytest.approx(9.2)
        assert row["fpmin_p50"] == pytest.approx(1.2)
        if mode == "all":          # cabs have no waits; an all-modes wait would be ride-hail only
            assert (row["wait_p50"], row["wait_p90"]) == (None, None)
        else:
            assert row["wait_p50"] == pytest.approx(180.0)
            assert row["wait_p90"] == pytest.approx(276.0)


def test_distribution_rows_need_100_valid_trips():
    one_minute = {"miles": 1.0, "dropoff_ts": P + timedelta(seconds=60)}
    build(clean_trips(
        # uber zone 161: 100 valid trips with fare = 1 … 100, so fare per mile = fare per minute = i
        [{"fare_base": float(i), **one_minute} for i in range(1, 101)]
        # uber zone 162: 99 valid trips and one invalid one → n = 99
        + [{"pu_zone": 162} for _ in range(99)] + [{"pu_zone": 162, "fare_base": 0.0, "f_fare": True}]
        # yellow zone 161: 99 valid trips
        + [{"mode": "yellow"} for _ in range(99)]
    ))
    kept = {(r["mode"], r["pu_zone"]): r["n"] for r in rows("agg_zone_month_dist")}
    # uber 0 = 100 + 99; ride_hail = uber; all = 199 + 99 yellow. Dropped: uber 162 (99),
    # yellow 161 and yellow city-wide (99 each)
    assert kept == {("uber", 161): 100, ("uber", 0): 199, ("ride_hail", 0): 199, ("all", 0): 298}
    zone = one("agg_zone_month_dist", mode="uber", pu_zone=161)
    # 1 … 100: p10 at 99 × 0.1 = 9.9 → 10 + 0.9 = 10.9; p50 at 49.5 → 50.5; p90 at 89.1 → 90.1
    assert zone["fpm_p10"] == pytest.approx(10.9)
    assert zone["fpm_p50"] == pytest.approx(50.5)
    assert zone["fpm_p90"] == pytest.approx(90.1)
    assert zone["fpmin_p50"] == pytest.approx(50.5)
    assert (zone["wait_p50"], zone["wait_p90"]) == (240.0, 240.0)   # every wait is the default 240 s
    assert one("agg_zone_month_dist", mode="all", pu_zone=0)["wait_p50"] is None


def test_od_pairs_need_20_valid_trips():
    build(clean_trips(
        [{} for _ in range(20)]                                       # uber 161 → 236: 20, kept
        + [{"do_zone": 237} for _ in range(19)]                       # uber 161 → 237: 19 valid …
        + [{"do_zone": 237, "dropoff_ts": P, "f_time": True}]         # … + 1 invalid → dropped
        + [{"mode": "yellow"} for _ in range(20)]                     # yellow 161 → 236: 20, kept
    ))
    assert {(r["mode"], r["pu_zone"], r["do_zone"]) for r in rows("agg_od_month")} == {
        ("uber", 161, 236), ("yellow", 161, 236)}
    uber = one("agg_od_month", mode="uber")
    assert uber["trips_valid"] == 20
    assert uber["miles"] == pytest.approx(64.0)                  # 20 × 3.2
    assert uber["duration_s"] == 24_000                          # 20 × 1200
    assert uber["fare_base"] == pytest.approx(370.0)             # 20 × 18.5
    assert uber["driver_pay"] == pytest.approx(284.0)            # 20 × 14.2
    assert uber["rider_total_ex_tip"] == pytest.approx(497.0)    # 20 × 24.85
    yellow = one("agg_od_month", mode="yellow")
    assert yellow["driver_pay"] is None
    assert yellow["rider_total_ex_tip"] == pytest.approx(475.0)  # 20 × 23.75


def test_airport_direction():
    jfk, lga = {"pu_zone": 132, "airport_pu": "JFK"}, {"do_zone": 138, "airport_do": "LGA"}
    build(clean_trips([
        {**jfk, "pickup_ts": datetime(2025, 3, 4, 15, 20),            # JFK → Midtown
         "miles": 17.0, "fare_base": 70.0, "rider_total_ex_tip": 80.0, "tips": 10.0},
        {**jfk, **lga, "pickup_ts": datetime(2025, 3, 4, 15, 40),     # JFK → LGA: both directions
         "miles": 11.0, "fare_base": 40.0, "rider_total_ex_tip": 50.0, "tips": 5.0},
        {**lga, "pickup_ts": datetime(2025, 3, 5, 6, 5),              # Midtown → LGA
         "miles": 9.0, "fare_base": 30.0, "rider_total_ex_tip": 36.0, "tips": 4.0},
        {**jfk, "pickup_ts": datetime(2025, 3, 4, 15, 50), "miles": 0.0, "f_miles": True},   # invalid
        {**jfk, "mode": "yellow", "pickup_ts": datetime(2025, 3, 6, 23, 10),
         "miles": 18.0, "fare_base": 70.0, "rider_total_ex_tip": 90.0, "tips": 12.0},
        {},                                                            # not an airport trip
    ]))
    got = {(r["mode"], r["airport"], r["direction"], r["hour_of_day"]):
           (r["trips_valid"], r["miles"], r["duration_s"], r["fare_base"], r["rider_total_ex_tip"], r["tips"])
           for r in rows("agg_airport")}
    assert got == {
        # JFK → Midtown + JFK → LGA, both picked up at 15:xx; the invalid 15:50 trip is left out
        ("uber", "JFK", "from", 15): (2, 28.0, 2400, 110.0, 130.0, 15.0),
        # drop-offs at LGA, by pickup hour
        ("uber", "LGA", "to", 6): (1, 9.0, 1200, 30.0, 36.0, 4.0),
        ("uber", "LGA", "to", 15): (1, 11.0, 1200, 40.0, 50.0, 5.0),
        ("yellow", "JFK", "from", 23): (1, 18.0, 1200, 70.0, 90.0, 12.0),
    }
    # 4 valid airport trips, 5 trip-directions: the JFK → LGA trip counts once each way
    assert sum(r["trips_valid"] for r in rows("agg_airport")) == 5


def test_airport_round_trip_to_the_same_airport():
    build(clean_trips([{"pu_zone": 132, "do_zone": 132, "airport_pu": "JFK", "airport_do": "JFK"}]))
    assert {(r["airport"], r["direction"], r["trips_valid"]) for r in rows("agg_airport")} == {
        ("JFK", "from", 1), ("JFK", "to", 1)}


def test_week_cbd_groups_under_both_zone_lists():
    build(clean_trips([
        {},                                                                     # core treated, wide treated
        {"cbd_pu": False, "cbd_pu_wide": True},                                 # borderline zone
        {"cbd_pu": False, "cbd_pu_wide": False, "fare_base": 10.0},             # control in both
        {"cbd_pu": False, "cbd_pu_wide": False, "miles": 0.0, "f_miles": True},  # control, invalid
        {"mode": "yellow"},                                                     # cab, treated
    ]))
    got = {(r["mode"], r["zone_list"], r["cbd_group"]):
           (r["trips_all"], r["trips_valid"], r["miles"], r["duration_s"], r["fare_base"],
            r["driver_pay"], r["rider_total_ex_tip"])
           for r in rows("agg_week_cbd")}
    # the 10.00 fare trip: rider_total_ex_tip = 10 + 2.10 + 2.75 + 1.50 = 16.35. Sums are exact
    # (DECIMAL), so plain equality holds
    assert got == {
        ("uber", "core", "treated"): (1, 1, 3.2, 1200, 18.5, 14.2, 24.85),
        ("uber", "core", "control"): (3, 2, 6.4, 2400, 28.5, 28.4, 41.2),     # borderline + 10.00 + invalid
        ("uber", "wide", "treated"): (2, 2, 6.4, 2400, 37.0, 28.4, 49.7),     # default + borderline
        ("uber", "wide", "control"): (2, 1, 3.2, 1200, 10.0, 14.2, 16.35),    # 10.00 + invalid
        ("yellow", "core", "treated"): (1, 1, 3.2, 1200, 18.5, None, 23.75),
        ("yellow", "wide", "treated"): (1, 1, 3.2, 1200, 18.5, None, 23.75),
    }
    # 2025-03-04 is in ISO week 10; every trip is counted once per list
    assert {(r["month"], r["iso_year"], r["iso_week"]) for r in rows("agg_week_cbd")} == {(date(2025, 3, 1), 2025, 10)}
    for zone_list in ("core", "wide"):
        assert sum(r["trips_all"] for r in rows("agg_week_cbd", zone_list=zone_list)) == 5


def test_quality_fees_and_qa_tables():
    build(clean_trips([
        {},                                                                     # uber A: valid, fee
        {"pu_zone": 132, "cbd_pu": False, "cbd_pu_wide": False,                 # uber B: valid, no fee
         "cbd_fee": 0.0, "airport_fee": 2.50},
        {"miles": 0.0, "f_miles": True, "fare_base": 0.0, "f_fare": True},      # uber C: two flags
        {"dropoff_ts": P, "f_time": True},                                      # uber D: 0 s trip
        {"pu_zone": 264, "f_zone": True},                                       # uber E: unknown zone
        {"request_ts": P - timedelta(seconds=4000), "f_wait": True},            # uber F: valid, wait flag
        {"mode": "yellow", "airport_fee": 1.75},                                # yellow G
        {"mode": "yellow"},                                                     # yellow H
        {"mode": "yellow", "do_zone": 265, "f_zone": True, "cbd_fee": 0.70},    # yellow I: invalid, odd fee
    ]))
    quality = {r["mode"]: r for r in rows("agg_quality_month")}
    assert {k: quality["uber"][k] for k in ("rows", "valid_rows", "f_time", "f_miles", "f_fare", "f_zone", "f_wait")} == {
        "rows": 6, "valid_rows": 3, "f_time": 1, "f_miles": 1, "f_fare": 1, "f_zone": 1, "f_wait": 1}   # valid: A B F
    assert {k: quality["yellow"][k] for k in ("rows", "valid_rows", "f_zone", "f_wait")} == {
        "rows": 3, "valid_rows": 2, "f_zone": 1, "f_wait": None}

    # fees over valid rows: uber A, B, F; yellow G, H
    fees = {r["mode"]: r for r in rows("agg_fees_month")}
    assert fees["uber"]["cbd_fee"] == pytest.approx(3.0)                  # 1.50 + 0 + 1.50
    assert fees["uber"]["congestion_surcharge"] == pytest.approx(8.25)    # 3 × 2.75
    assert fees["uber"]["airport_fee"] == pytest.approx(2.5)
    assert fees["uber"]["trips_with_cbd_fee"] == 2                        # A, F
    assert fees["yellow"]["cbd_fee"] == pytest.approx(1.5)                # 2 × 0.75
    assert fees["yellow"]["congestion_surcharge"] == pytest.approx(5.0)   # 2 × 2.50
    assert fees["yellow"]["airport_fee"] == pytest.approx(1.75)
    assert fees["yellow"]["trips_with_cbd_fee"] == 2

    # fee values over all rows
    assert {(r["mode"], r["cbd_fee"]): r["trips"] for r in rows("agg_fee_values")} == {
        ("uber", 0.0): 1,             # B
        ("uber", 1.5): 5,             # A C D E F
        ("yellow", 0.7): 1,           # I
        ("yellow", 0.75): 2,          # G H
    }

    # zone pairs over all rows
    assert {(r["mode"], r["pu_zone"], r["do_zone"]): (r["trips_all"], r["trips_cbd_fee"])
            for r in rows("agg_cbd_pairs")} == {
        ("uber", 161, 236): (4, 4),   # A C D F
        ("uber", 132, 236): (1, 0),   # B
        ("uber", 264, 236): (1, 1),   # E
        ("yellow", 161, 236): (2, 2),  # G H
        ("yellow", 161, 265): (1, 1),  # I: 0.70 > 0
    }


def test_cbd_pairs_start_with_congestion_pricing():
    # December 2024: before the 2025-01 start month, so no CBD pairs; fee values still recorded
    build(clean_trips([{"pickup_ts": datetime(2024, 12, 10, 9, 0), "cbd_fee": 0.0}]), month="2024-12")
    assert rows("agg_cbd_pairs") == []
    assert pq.read_schema(common.agg_path("agg_cbd_pairs")).equals(AGG_SCHEMAS["agg_cbd_pairs"])
    assert [(r["month"], r["cbd_fee"], r["trips"]) for r in rows("agg_fee_values")] == [(date(2024, 12, 1), 0.0, 1)]

    build(clean_trips([{"pickup_ts": datetime(2025, 1, 2, 9, 0)}]), month="2025-01")
    assert [r["month"] for r in rows("agg_cbd_pairs")] == [date(2025, 1, 1)]
