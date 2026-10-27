"""Raw TLC trip files for the clean tests (lane L06), built in code and written under ``NYC_DATA_DIR``.

Each dataset's columns, names and types are those of the real files (reports/schema_discovery.md):
yellow spells ``Airport_fee`` with a capital A, ``cbd_congestion_fee`` starts in 2025-01 and cab files
gain ``request_source`` in 2026-06. ``write_raw`` also records the file's row count in
``data/manifest.json``, as ingest does, and ``write_lookup`` writes a small zone lookup.

    write_month("2025-03", fhvhv=[{}, {"trip_time": 0}], yellow=[{"Airport_fee": 1.75}])
    clean.clean_month("2025-03")

Default rows (pickup on the month's 4th at 08:10, dropoff 20 min later):

- fhvhv: Uber (HV0003), zone 161 → 236, 3.2 miles, trip_time 1200, request 4 min before pickup;
  fare 18.50, tolls 0, bcf 0.51, sales tax 1.64, congestion surcharge 2.75, airport fee 0, tips 3.00,
  driver pay 14.20, every Y/N flag 'N', cbd_congestion_fee 1.50 (from 2025-01)
- yellow: VendorID 2, zone 161 → 236, 3.2 miles, card (payment_type 1); fare 18.40, extra 1.00,
  MTA tax 0.50, tip 4.00, tolls 0, improvement surcharge 1.00, congestion surcharge 2.50,
  Airport_fee 0, cbd_congestion_fee 0.75 (from 2025-01)
- green: VendorID 2, zone 74 → 75, 2.0 miles, card, street hail (trip_type 1); fare 12.10,
  extra 1.00, MTA tax 0.50, tip 2.00, tolls 0, improvement surcharge 1.00, congestion surcharge 0,
  cbd_congestion_fee 0

A cab's ``total_amount`` is the sum of its money columns unless a row sets it.
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timedelta

import pyarrow as pa
import pyarrow.parquet as pq

from pipeline import common

TS, S, I32, I64, F64 = pa.timestamp("us"), pa.string(), pa.int32(), pa.int64(), pa.float64()

COLUMNS = {
    "fhvhv": [
        ("hvfhs_license_num", S), ("dispatching_base_num", S), ("originating_base_num", S),
        ("request_datetime", TS), ("on_scene_datetime", TS), ("pickup_datetime", TS),
        ("dropoff_datetime", TS), ("PULocationID", I32), ("DOLocationID", I32), ("trip_miles", F64),
        ("trip_time", I64), ("base_passenger_fare", F64), ("tolls", F64), ("bcf", F64),
        ("sales_tax", F64), ("congestion_surcharge", F64), ("airport_fee", F64), ("tips", F64),
        ("driver_pay", F64), ("shared_request_flag", S), ("shared_match_flag", S),
        ("access_a_ride_flag", S), ("wav_request_flag", S), ("wav_match_flag", S),
    ],
    "yellow": [
        ("VendorID", I32), ("tpep_pickup_datetime", TS), ("tpep_dropoff_datetime", TS),
        ("passenger_count", I64), ("trip_distance", F64), ("RatecodeID", I64),
        ("store_and_fwd_flag", S), ("PULocationID", I32), ("DOLocationID", I32),
        ("payment_type", I64), ("fare_amount", F64), ("extra", F64), ("mta_tax", F64),
        ("tip_amount", F64), ("tolls_amount", F64), ("improvement_surcharge", F64),
        ("total_amount", F64), ("congestion_surcharge", F64), ("Airport_fee", F64),
    ],
    "green": [
        ("VendorID", I32), ("lpep_pickup_datetime", TS), ("lpep_dropoff_datetime", TS),
        ("store_and_fwd_flag", S), ("RatecodeID", I64), ("PULocationID", I32), ("DOLocationID", I32),
        ("passenger_count", I64), ("trip_distance", F64), ("fare_amount", F64), ("extra", F64),
        ("mta_tax", F64), ("tip_amount", F64), ("tolls_amount", F64), ("ehail_fee", F64),
        ("improvement_surcharge", F64), ("total_amount", F64), ("payment_type", I64),
        ("trip_type", I64), ("congestion_surcharge", F64),
    ],
}
CAB_MONEY = ("fare_amount", "extra", "mta_tax", "tip_amount", "tolls_amount", "improvement_surcharge",
             "congestion_surcharge", "Airport_fee", "cbd_congestion_fee")

# LocationID, Borough, Zone, service_zone: the rows of data/ref/taxi_zone_lookup.csv the tests use
LOOKUP = [
    (1, "EWR", "Newark Airport", "EWR"),
    (43, "Manhattan", "Central Park", "Yellow Zone"),
    (74, "Manhattan", "East Harlem North", "Boro Zone"),
    (75, "Manhattan", "East Harlem South", "Boro Zone"),
    (132, "Queens", "JFK Airport", "Airports"),
    (138, "Queens", "LaGuardia Airport", "Airports"),
    (161, "Manhattan", "Midtown Center", "Yellow Zone"),
    (236, "Manhattan", "Upper East Side North", "Yellow Zone"),
    (264, "Unknown", "N/A", "N/A"),
    (265, "N/A", "Outside of NYC", "N/A"),
]


def schema(dataset: str, month: str) -> pa.Schema:
    """The raw file schema for ``dataset`` in ``month`` (``YYYY-MM``)."""
    columns = list(COLUMNS[dataset])
    if month >= "2025-01":
        columns.append(("cbd_congestion_fee", F64))
    if dataset != "fhvhv" and month >= "2026-06":
        columns.append(("request_source", S))
    return pa.schema(columns)


def pickup(month: str) -> datetime:
    """The default pickup: the month's 4th at 08:10."""
    first = common.parse_month(month)
    return datetime(first.year, first.month, 4, 8, 10)


def raw_row(dataset: str, month: str, **overrides) -> dict:
    """One raw row with real column names; ``overrides`` replace any column."""
    names = schema(dataset, month).names
    unknown = overrides.keys() - set(names)
    if unknown:
        raise KeyError(f"not {dataset} {month} columns: {sorted(unknown)}")
    p = pickup(month)
    if dataset == "fhvhv":
        row = {
            "hvfhs_license_num": "HV0003", "dispatching_base_num": "B03404", "originating_base_num": "B03404",
            "request_datetime": p - timedelta(minutes=4), "on_scene_datetime": p - timedelta(minutes=1),
            "pickup_datetime": p, "dropoff_datetime": p + timedelta(minutes=20),
            "PULocationID": 161, "DOLocationID": 236, "trip_miles": 3.2, "trip_time": 1200,
            "base_passenger_fare": 18.50, "tolls": 0.0, "bcf": 0.51, "sales_tax": 1.64,
            "congestion_surcharge": 2.75, "airport_fee": 0.0, "tips": 3.00, "driver_pay": 14.20,
            "shared_request_flag": "N", "shared_match_flag": "N", "access_a_ride_flag": "N",
            "wav_request_flag": "N", "wav_match_flag": "N", "cbd_congestion_fee": 1.50,
        }
    else:
        prefix = "tpep" if dataset == "yellow" else "lpep"
        row = {
            "VendorID": 2, f"{prefix}_pickup_datetime": p, f"{prefix}_dropoff_datetime": p + timedelta(minutes=20),
            "passenger_count": 1, "RatecodeID": 1, "store_and_fwd_flag": "N", "payment_type": 1,
            "extra": 1.00, "mta_tax": 0.50, "tolls_amount": 0.0, "improvement_surcharge": 1.00,
            "request_source": None,
        }
        if dataset == "yellow":
            row |= {"PULocationID": 161, "DOLocationID": 236, "trip_distance": 3.2, "fare_amount": 18.40,
                    "tip_amount": 4.00, "congestion_surcharge": 2.50, "Airport_fee": 0.0,
                    "cbd_congestion_fee": 0.75}
        else:
            row |= {"PULocationID": 74, "DOLocationID": 75, "trip_distance": 2.0, "fare_amount": 12.10,
                    "tip_amount": 2.00, "congestion_surcharge": 0.0, "ehail_fee": None, "trip_type": 1,
                    "cbd_congestion_fee": 0.0}
    row = {name: value for name, value in row.items() if name in names}
    row.update(overrides)
    if dataset != "fhvhv" and "total_amount" not in overrides:
        row["total_amount"] = round(sum(row.get(name) or 0.0 for name in CAB_MONEY if name in names), 2)
    return row


def raw_table(dataset: str, month: str, rows: list[dict] | None = None) -> pa.Table:
    """A raw file's contents: one row per override dict (``[{}]`` gives one default row)."""
    return pa.Table.from_pylist([raw_row(dataset, month, **row) for row in rows or [{}]],
                                schema=schema(dataset, month))


def set_manifest_rows(dataset: str, month: str, rows: int) -> None:
    """Record ``rows`` for the raw file in data/manifest.json, as ingest does."""
    path = common.manifest_path()
    files = json.loads(path.read_text(encoding="utf-8"))["files"] if path.exists() else {}
    key = common.raw_path(dataset, month).relative_to(common.data_dir()).as_posix()
    files[key] = {"file": key, "dataset": dataset, "month": month, "rows": rows}
    path.write_text(json.dumps({"files": files}, indent=2), encoding="utf-8")


def write_raw(dataset: str, month: str, rows: list[dict] | None = None, table: pa.Table | None = None):
    """Write ``data/raw/{dataset}/{month}.parquet`` from ``rows`` (or a ready ``table``)."""
    table = table if table is not None else raw_table(dataset, month, rows)
    path = common.raw_path(dataset, month)
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    set_manifest_rows(dataset, month, table.num_rows)
    return path


def write_lookup() -> None:
    """A small ``data/ref/taxi_zone_lookup.csv`` (the zones in ``LOOKUP``)."""
    path = common.ref_dir() / "taxi_zone_lookup.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_NONNUMERIC)
        writer.writerow(["LocationID", "Borough", "Zone", "service_zone"])
        writer.writerows(LOOKUP)


def write_month(month: str, fhvhv: list[dict] | None = None, yellow: list[dict] | None = None,
                green: list[dict] | None = None) -> None:
    """All three raw files of a month plus the zone lookup; a dataset left out gets one default row."""
    write_lookup()
    for dataset, rows in (("fhvhv", fhvhv), ("yellow", yellow), ("green", green)):
        write_raw(dataset, month, rows)
