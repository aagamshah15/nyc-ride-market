"""Clean (lane L06): SPEC §4.2 quality flags at their boundaries, hour of week and period.

Rows are told apart by their tip (``tips`` / ``tip_amount``), which no flag reads. Raw defaults are
in tests/fixtures/raw/raw_trips.py: a valid trip on the month's 4th at 08:10, 20 minutes, 3.2 miles,
ride-hail requested 4 minutes before pickup.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pyarrow.parquet as pq

from pipeline import clean, common
from tests.fixtures.raw.raw_trips import pickup, write_month

MARCH = "2025-03"
P = pickup(MARCH)   # Tuesday 2025-03-04 08:10
FLAGS = ("f_time", "f_miles", "f_fare", "f_zone", "f_wait", "is_valid")


def by_tip(mode: str, month: str = MARCH) -> dict[float, dict]:
    rows = pq.read_table(common.clean_partition(mode, month) / "part-0.parquet").to_pylist()
    return {r["tips"]: r for r in rows}


def flags(row: dict) -> tuple:
    return tuple(row[f] for f in FLAGS)


def hv_at(ts: datetime, tip: float, **extra) -> dict:
    """A ride-hail row picked up at ``ts`` (request 4 min before, dropoff 20 min after)."""
    return {"pickup_datetime": ts, "request_datetime": ts - timedelta(minutes=4),
            "dropoff_datetime": ts + timedelta(minutes=20), "tips": tip, **extra}


def test_duration_boundaries_ride_hail():
    write_month(MARCH, fhvhv=[{"trip_time": s, "tips": float(i)} for i, s in enumerate([0, 1, 10800, 10801, -60])])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    # duration_s <= 0 or > 10800 → f_time
    assert [trips[float(i)]["f_time"] for i in range(5)] == [True, False, False, True, True]
    assert [trips[float(i)]["duration_s"] for i in range(5)] == [0, 1, 10800, 10801, -60]
    assert [trips[float(i)]["is_valid"] for i in range(5)] == [False, True, True, False, False]


def test_duration_boundaries_cabs_from_timestamps():
    seconds = [0, 10800, 10801, -814]
    write_month(MARCH, yellow=[{"tpep_dropoff_datetime": P + timedelta(seconds=s), "tip_amount": float(i)}
                               for i, s in enumerate(seconds)])
    clean.clean_month(MARCH)
    trips = by_tip("yellow")
    assert [trips[float(i)]["duration_s"] for i in range(4)] == seconds
    assert [trips[float(i)]["f_time"] for i in range(4)] == [True, False, True, True]


def test_duration_beyond_integer_range_is_null_and_flagged():
    # a dropoff 80 years after pickup is about 2.5 billion seconds, more than INTEGER holds
    write_month(MARCH, yellow=[{"tpep_dropoff_datetime": P + timedelta(days=80 * 365)}])
    clean.clean_month(MARCH)
    (trip,) = by_tip("yellow").values()
    assert trip["duration_s"] is None
    assert (trip["f_time"], trip["is_valid"]) == (True, False)


def test_miles_boundaries():
    miles = [0.0, 0.01, 100.0, 100.01, -1.0]
    write_month(MARCH, fhvhv=[{"trip_miles": m, "tips": float(i)} for i, m in enumerate(miles)])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    # miles <= 0 or > 100 → f_miles
    assert [trips[float(i)]["f_miles"] for i in range(5)] == [True, False, False, True, True]
    assert [trips[float(i)]["is_valid"] for i in range(5)] == [False, True, True, False, False]


def test_fare_boundary():
    write_month(MARCH, yellow=[{"fare_amount": f, "tip_amount": float(i)} for i, f in enumerate([0.0, 0.01, -3.0])])
    clean.clean_month(MARCH)
    trips = by_tip("yellow")
    # fare_base <= 0 → f_fare
    assert [trips[float(i)]["f_fare"] for i in range(3)] == [True, False, True]
    assert [trips[float(i)]["is_valid"] for i in range(3)] == [False, True, False]


def test_zone_flags():
    zones = [(161, 236), (264, 236), (161, 264), (None, 236), (161, None),
             (265, 236), (161, 265), (265, 265), (265, 264), (None, 265)]
    write_month(MARCH, green=[{"PULocationID": pu, "DOLocationID": do, "tip_amount": float(i)}
                              for i, (pu, do) in enumerate(zones)])
    clean.clean_month(MARCH)
    trips = by_tip("green")
    # either zone 264 or NULL → f_zone; 265 ("Outside of NYC") at either end or both is a real place (D26)
    expected = [False, True, True, True, True, False, False, False, True, True]
    assert [trips[float(i)]["f_zone"] for i in range(10)] == expected
    assert [trips[float(i)]["is_valid"] for i in range(10)] == [not f for f in expected]


def test_wait_boundaries():
    waits = [-1, 0, 3600, 3601]
    write_month(MARCH, fhvhv=[{"request_datetime": P - timedelta(seconds=w), "tips": float(i)}
                              for i, w in enumerate(waits)])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    assert [trips[float(i)]["wait_s"] for i in range(4)] == waits
    # ride-hail and (wait_s < 0 or > 3600) → f_wait; it doesn't affect is_valid
    assert [trips[float(i)]["f_wait"] for i in range(4)] == [True, False, False, True]
    assert all(trips[float(i)]["is_valid"] for i in range(4))


def test_null_request_gives_null_wait_and_no_wait_flag():
    write_month(MARCH, fhvhv=[{"request_datetime": None}])
    clean.clean_month(MARCH)
    (trip,) = by_tip("uber").values()
    assert (trip["wait_s"], trip["f_wait"], trip["is_valid"]) == (None, False, True)


def test_pickup_window_is_the_files_month_plus_or_minus_one_day():
    pickups = [
        datetime(2025, 2, 28, 0, 0, 0),      # one day before 1 March: inside
        datetime(2025, 2, 27, 23, 59, 59),   # a second earlier: outside
        datetime(2025, 2, 27, 0, 0, 0),      # two days before: outside
        datetime(2025, 4, 1, 23, 59, 59),    # last second of the day after the month: inside
        datetime(2025, 4, 2, 0, 0, 0),       # two days after the month's end: outside
        datetime(2024, 3, 4, 8, 10),         # a year early: outside
    ]
    write_month(MARCH, fhvhv=[hv_at(ts, float(i)) for i, ts in enumerate(pickups)])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    # trip_time is the default 1200 s in every row, so only the window sets f_time
    assert [trips[float(i)]["f_time"] for i in range(6)] == [False, True, True, False, True, True]


def test_is_valid_combines_four_flags_and_ignores_the_wait_flag():
    write_month(MARCH, fhvhv=[
        {"tips": 0.0},                                                    # valid
        {"tips": 1.0, "request_datetime": P - timedelta(hours=2)},       # f_wait only: still valid
        {"tips": 2.0, "trip_time": 0, "trip_miles": 0.0, "base_passenger_fare": 0.0,
         "PULocationID": 264},                                            # every flag but f_wait
    ])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    assert flags(trips[0.0]) == (False, False, False, False, False, True)
    assert flags(trips[1.0]) == (False, False, False, False, True, True)
    assert flags(trips[2.0]) == (True, True, True, True, False, False)


def test_null_measures_set_their_flags():
    write_month(MARCH, fhvhv=[{"trip_time": None, "trip_miles": None, "base_passenger_fare": None}])
    clean.clean_month(MARCH)
    (trip,) = by_tip("uber").values()
    assert flags(trip) == (True, True, True, False, False, False)


def test_cab_rows_never_carry_the_wait_flag():
    write_month(MARCH)
    clean.clean_month(MARCH)
    for mode in ("yellow", "green"):
        (trip,) = by_tip(mode).values()
        assert (trip["wait_s"], trip["f_wait"]) == (None, False)


def test_hour_of_week():
    write_month(MARCH, fhvhv=[
        hv_at(datetime(2025, 3, 2, 0, 30), 0.0),    # Sunday 00:30 → 0
        hv_at(datetime(2025, 3, 8, 23, 10), 1.0),   # Saturday 23:10 → 6 × 24 + 23 = 167
        hv_at(P, 2.0),                              # Tuesday 08:10 → 2 × 24 + 8 = 56
    ])
    clean.clean_month(MARCH)
    trips = by_tip("uber")
    assert [trips[t]["hour_of_week"] for t in (0.0, 1.0, 2.0)] == [0, 167, 56]


def test_period_boundaries():
    write_month("2025-01", fhvhv=[hv_at(datetime(2025, 1, 4, 23, 59, 59), 0.0),
                                  hv_at(datetime(2025, 1, 5, 0, 0, 0), 1.0)])
    write_month("2025-08", fhvhv=[hv_at(datetime(2025, 7, 31, 23, 59, 59), 0.0),
                                  hv_at(datetime(2025, 8, 1, 0, 0, 0), 1.0)])
    clean.clean_month("2025-01")
    clean.clean_month("2025-08")
    january, august = by_tip("uber", "2025-01"), by_tip("uber", "2025-08")
    assert (january[0.0]["period"], january[1.0]["period"]) == ("pre_cp", "post_cp")
    assert (august[0.0]["period"], august[1.0]["period"]) == ("post_cp", "post_pay")
