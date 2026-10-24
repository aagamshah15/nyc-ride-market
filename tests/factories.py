"""Builders for contract-shaped test data: unified clean trips and every aggregate table.

These schemas are the executable form of SPEC §4 and §5 plus decisions D7–D10 and
D15–D16 (contracts/README.md §6). Build fixtures from them instead of hand-writing
Parquet, so a schema change reaches every lane's tests at once.

    trips = clean_trips([{"mode": "yellow", "fare_base": 12.0}, {}])
    write_clean(trips)                              # $NYC_DATA_DIR/clean/mode=…/month=…/
    zone_hour = agg_table("agg_zone_hour", [{"trips_all": 10}, {"mode": "yellow"}])
    write_agg("agg_zone_hour", zone_hour)           # $NYC_DATA_DIR/agg/agg_zone_hour.parquet

A trip's derived columns (month, duration_s, wait_s, hour_of_week, period, cbd_touch*,
rider_total_ex_tip, is_valid) follow from the row unless overridden. The factory does
not apply the cleaning rules themselves: set flags explicitly.

Owned by L01; changed through the integrator.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from pipeline import common

HV_MODES = ("uber", "lyft", "other_hv")
TAXI_MODES = ("yellow", "green")

TS, D, S = pa.timestamp("us"), pa.date32(), pa.string()
I16, I32, I64, F64, B = pa.int16(), pa.int32(), pa.int64(), pa.float64(), pa.bool_()

CLEAN_TRIPS_SCHEMA = pa.schema([
    # unified columns (SPEC §4)
    ("mode", S), ("month", D), ("request_ts", TS), ("pickup_ts", TS), ("dropoff_ts", TS),
    ("pu_zone", I16), ("do_zone", I16), ("miles", F64), ("duration_s", I32),
    ("fare_base", F64), ("tips", F64), ("tolls", F64), ("airport_fee", F64),
    ("congestion_surcharge", F64), ("cbd_fee", F64), ("other_fees", F64),
    ("rider_total_ex_tip", F64), ("driver_pay", F64), ("is_card", B),
    ("shared_request", B), ("shared_match", B), ("wav_request", B), ("wav_match", B),
    ("street_hail", B),
    # derived columns (SPEC §4.1; *_wide per D9)
    ("wait_s", I32), ("hour_of_week", I16), ("pu_borough", S), ("do_borough", S),
    ("airport_pu", S), ("airport_do", S),
    ("cbd_pu", B), ("cbd_do", B), ("cbd_touch", B),
    ("cbd_pu_wide", B), ("cbd_do_wide", B), ("cbd_touch_wide", B),
    ("period", S),
    # quality flags (SPEC §4.2)
    ("f_time", B), ("f_miles", B), ("f_fare", B), ("f_zone", B), ("f_wait", B), ("is_valid", B),
])

AGG_SCHEMAS = {
    "agg_zone_hour": pa.schema([
        ("month", D), ("mode", S), ("pu_zone", I16), ("hour_of_week", I16),
        ("trips_all", I64), ("trips_valid", I64), ("miles", F64), ("duration_s", I64),
        ("fare_base", F64), ("rider_total_ex_tip", F64), ("driver_pay", F64), ("tips", F64),
        ("card_trips", I64), ("card_tips", F64), ("card_fare_base", F64),
        ("wait_s_sum", I64), ("wait_n", I64), ("cbd_fee", F64),
        ("shared_req", I64), ("shared_match", I64), ("wav_req", I64), ("wav_match", I64),
    ]),
    "agg_zone_month_dist": pa.schema([   # pu_zone = 0: city-wide, incl. ride_hail / all (D10, D16)
        ("month", D), ("mode", S), ("pu_zone", I16), ("n", I64),
        ("fpm_p10", F64), ("fpm_p50", F64), ("fpm_p90", F64), ("fpmin_p50", F64),
        ("wait_p50", F64), ("wait_p90", F64),
    ]),
    "agg_od_month": pa.schema([          # rider_total_ex_tip per D15
        ("month", D), ("mode", S), ("pu_zone", I16), ("do_zone", I16), ("trips_valid", I64),
        ("miles", F64), ("duration_s", I64), ("fare_base", F64), ("driver_pay", F64),
        ("rider_total_ex_tip", F64),
    ]),
    "agg_airport": pa.schema([
        ("month", D), ("mode", S), ("airport", S), ("direction", S), ("hour_of_day", I16),
        ("trips_valid", I64), ("miles", F64), ("duration_s", I64), ("fare_base", F64),
        ("rider_total_ex_tip", F64), ("tips", F64),
    ]),
    "agg_week_cbd": pa.schema([          # month per D7, zone_list per D9
        ("month", D), ("iso_year", I16), ("iso_week", I16), ("mode", S), ("zone_list", S),
        ("cbd_group", S), ("trips_all", I64), ("trips_valid", I64), ("miles", F64),
        ("duration_s", I64), ("fare_base", F64), ("driver_pay", F64), ("rider_total_ex_tip", F64),
    ]),
    "agg_fees_month": pa.schema([
        ("month", D), ("mode", S), ("cbd_fee", F64), ("congestion_surcharge", F64),
        ("airport_fee", F64), ("trips_with_cbd_fee", I64),
    ]),
    "agg_quality_month": pa.schema([
        ("month", D), ("mode", S), ("rows", I64), ("valid_rows", I64), ("f_time", I64),
        ("f_miles", I64), ("f_fare", I64), ("f_zone", I64), ("f_wait", I64),
    ]),
    "agg_cbd_pairs": pa.schema([         # D8
        ("month", D), ("mode", S), ("pu_zone", I16), ("do_zone", I16),
        ("trips_all", I64), ("trips_cbd_fee", I64),
    ]),
    "agg_fee_values": pa.schema([        # D8
        ("month", D), ("mode", S), ("cbd_fee", F64), ("trips", I64),
    ]),
    "ref_indicators": pa.schema([        # CSV columns unchanged (Open Data copy, D19), plus a parsed month
        ("month", D), ("Year/Month", S), ("License Class", S), ("Trips Per Day", F64),
        ("Farebox Per Day", F64), ("Unique Drivers", F64), ("Unique Vehicles", F64),
        ("Vehicles Per Day", F64), ("Avg Days Vehicles on Road", F64),
        ("Avg Hours Per Day Per Vehicle", F64), ("Avg Days Drivers on Road", F64),
        ("Avg Hours Per Day Per Driver", F64), ("Avg Minutes Per Trip", F64),
        ("Percent of Trips Paid with Credit Card", F64), ("Trips Per Day Shared", F64),
    ]),
}


# --- clean trips -------------------------------------------------------------

def _period(pickup: datetime) -> str:
    periods = common.load_yaml("periods.yaml")
    if pickup.date() < periods["congestion_pricing_start"]:
        return "pre_cp"
    if pickup.date() < periods["driver_pay_rise"]:
        return "post_cp"
    return "post_pay"


def make_trip(**overrides) -> dict:
    """One clean-trip row: a valid Tuesday-morning Midtown trip in March 2025 by default."""
    unknown = overrides.keys() - set(CLEAN_TRIPS_SCHEMA.names)
    if unknown:
        raise KeyError(f"not clean-trip columns: {sorted(unknown)}")
    mode = overrides.get("mode", "uber")
    hv = mode in HV_MODES
    pickup = overrides.get("pickup_ts", datetime(2025, 3, 4, 8, 10))
    row = {
        "mode": mode,
        "pickup_ts": pickup,
        "dropoff_ts": pickup + timedelta(minutes=20),
        "request_ts": pickup - timedelta(minutes=4) if hv else None,
        "pu_zone": 161, "do_zone": 236,
        "miles": 3.2, "fare_base": 18.50, "tips": 3.00, "tolls": 0.0,
        "airport_fee": 0.0, "congestion_surcharge": 2.75 if hv else 2.50,
        "cbd_fee": 1.50 if hv else 0.75, "other_fees": 2.10 if hv else 2.00,
        "driver_pay": 14.20 if hv else None,
        "is_card": None if hv else True,
        "shared_request": False if hv else None, "shared_match": False if hv else None,
        "wav_request": False if hv else None, "wav_match": False if hv else None,
        "street_hail": True if mode == "green" else None,
        "pu_borough": "Manhattan", "do_borough": "Manhattan",
        "airport_pu": None, "airport_do": None,
        "cbd_pu": True, "cbd_do": False, "cbd_pu_wide": True, "cbd_do_wide": False,
        "f_time": False, "f_miles": False, "f_fare": False, "f_zone": False, "f_wait": False,
    }
    row.update(overrides)
    pickup, dropoff, request = row["pickup_ts"], row["dropoff_ts"], row["request_ts"]
    derived = {
        "month": date(pickup.year, pickup.month, 1),
        "duration_s": int((dropoff - pickup).total_seconds()),
        "wait_s": int((pickup - request).total_seconds()) if request else None,
        "hour_of_week": (pickup.isoweekday() % 7) * 24 + pickup.hour,   # Sunday = 0
        "period": _period(pickup),
        "cbd_touch": row["cbd_pu"] or row["cbd_do"],
        "cbd_touch_wide": row["cbd_pu_wide"] or row["cbd_do_wide"],
        "rider_total_ex_tip": round(row["fare_base"] + row["tolls"] + row["other_fees"]
                                    + row["congestion_surcharge"] + row["airport_fee"] + row["cbd_fee"], 2),
        "is_valid": not (row["f_time"] or row["f_miles"] or row["f_fare"] or row["f_zone"]),
    }
    for key, value in derived.items():
        row.setdefault(key, value)
    return row


def clean_trips(rows: list[dict] | None = None, **shared) -> pa.Table:
    """Clean trips: one row per override dict (``[{}]`` gives one default trip).
    ``shared`` overrides apply to every row."""
    return pa.Table.from_pylist([make_trip(**{**shared, **row}) for row in rows or [{}]],
                                schema=CLEAN_TRIPS_SCHEMA)


def write_clean(trips: pa.Table) -> list:
    """Write trips to ``data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet``.

    Files keep every column, including ``mode`` and ``month``; folder names are layout
    only, so read them with ``hive_partitioning = false`` (contracts/README.md §6)."""
    written = []
    keys = sorted({(r["mode"], r["month"]) for r in trips.select(["mode", "month"]).to_pylist()})
    for mode, month in keys:
        part = trips.filter(pc.and_(pc.equal(trips["mode"], mode), pc.equal(trips["month"], month)))
        folder = common.clean_partition(mode, common.format_month(month))
        folder.mkdir(parents=True, exist_ok=True)
        pq.write_table(part, folder / "part-0.parquet")
        written.append(folder / "part-0.parquet")
    return written


# --- aggregate tables --------------------------------------------------------

def _agg_defaults(name: str, mode: str) -> dict:
    hv = mode in HV_MODES
    month = date(2025, 3, 1)
    if name == "agg_zone_hour":
        return {
            "month": month, "mode": mode, "pu_zone": 161, "hour_of_week": 56,
            "trips_all": 100, "trips_valid": 98, "miles": 313.6, "duration_s": 117_600,
            "fare_base": 1_813.0, "rider_total_ex_tip": 2_435.3,
            "driver_pay": 1_391.6 if hv else None, "tips": 294.0,
            "card_trips": None if hv else 80, "card_tips": None if hv else 296.0,
            "card_fare_base": None if hv else 1_480.0,
            "wait_s_sum": 23_520 if hv else None, "wait_n": 98 if hv else None,
            "cbd_fee": 147.0 if hv else 73.5,
            "shared_req": 2 if hv else None, "shared_match": 1 if hv else None,
            "wav_req": 1 if hv else None, "wav_match": 1 if hv else None,
        }
    if name == "agg_zone_month_dist":
        return {"month": month, "mode": mode, "pu_zone": 161, "n": 3_000,
                "fpm_p10": 3.10, "fpm_p50": 5.40, "fpm_p90": 9.80, "fpmin_p50": 0.95,
                "wait_p50": 240.0 if hv else None, "wait_p90": 510.0 if hv else None}
    if name == "agg_od_month":
        return {"month": month, "mode": mode, "pu_zone": 161, "do_zone": 236, "trips_valid": 40,
                "miles": 128.0, "duration_s": 48_000, "fare_base": 740.0,
                "driver_pay": 568.0 if hv else None, "rider_total_ex_tip": 994.0}
    if name == "agg_airport":
        return {"month": month, "mode": mode, "airport": "JFK", "direction": "from", "hour_of_day": 15,
                "trips_valid": 50, "miles": 875.0, "duration_s": 135_000, "fare_base": 3_400.0,
                "rider_total_ex_tip": 4_100.0, "tips": 600.0}
    if name == "agg_week_cbd":
        return {"month": month, "iso_year": 2025, "iso_week": 10, "mode": mode, "zone_list": "core",
                "cbd_group": "treated", "trips_all": 1_000, "trips_valid": 985, "miles": 2_955.0,
                "duration_s": 1_182_000, "fare_base": 17_730.0,
                "driver_pay": 13_120.0 if hv else None, "rider_total_ex_tip": 24_400.0}
    if name == "agg_fees_month":
        return {"month": month, "mode": mode, "cbd_fee": 1_500.0 if hv else 750.0,
                "congestion_surcharge": 2_750.0, "airport_fee": 0.0, "trips_with_cbd_fee": 1_000}
    if name == "agg_quality_month":
        return {"month": month, "mode": mode, "rows": 1_000, "valid_rows": 985, "f_time": 5,
                "f_miles": 6, "f_fare": 2, "f_zone": 3, "f_wait": 1 if hv else None}
    if name == "agg_cbd_pairs":
        return {"month": month, "mode": mode, "pu_zone": 161, "do_zone": 236,
                "trips_all": 100, "trips_cbd_fee": 99}
    if name == "agg_fee_values":
        return {"month": month, "mode": mode, "cbd_fee": 1.50 if hv else 0.75, "trips": 1_000}
    if name == "ref_indicators":
        return {"month": month, "Year/Month": "2025-03", "License Class": "FHV - High Volume",
                "Trips Per Day": 650_000.0, "Farebox Per Day": 17_500_000.0, "Unique Drivers": 70_000.0,
                "Unique Vehicles": 66_000.0, "Vehicles Per Day": 58_000.0,
                "Avg Days Vehicles on Road": 24.0, "Avg Hours Per Day Per Vehicle": 7.2,
                "Avg Days Drivers on Road": 23.0, "Avg Hours Per Day Per Driver": 6.9,
                "Avg Minutes Per Trip": 19.5, "Percent of Trips Paid with Credit Card": None,
                "Trips Per Day Shared": 0.0}
    raise KeyError(f"unknown aggregate table {name!r}; expected one of {sorted(AGG_SCHEMAS)}")


def agg_row(name: str, **overrides) -> dict:
    """One aggregate row with defaults that suit ``overrides.get("mode", "uber")``."""
    schema = AGG_SCHEMAS[name]
    unknown = overrides.keys() - set(schema.names)
    if unknown:
        raise KeyError(f"not {name} columns: {sorted(unknown)}")
    return {**_agg_defaults(name, overrides.get("mode", "uber")), **overrides}


def agg_table(name: str, rows: list[dict] | None = None, **shared) -> pa.Table:
    """An aggregate table: one row per override dict (``[{}]`` gives one default row)."""
    return pa.Table.from_pylist([agg_row(name, **{**shared, **row}) for row in rows or [{}]],
                                schema=AGG_SCHEMAS[name])


def write_agg(name: str, table: pa.Table) -> object:
    """Write ``table`` to ``data/agg/{name}.parquet`` under ``NYC_DATA_DIR``."""
    path = common.agg_path(name)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path
