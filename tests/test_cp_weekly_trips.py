"""cp_weekly_trips: trips per day inside and outside the congestion zone, by ISO week (Q2)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics

JAN24, FEB24, JAN25, FEB25, DEC25 = (date(2024, 1, 1), date(2024, 2, 1), date(2025, 1, 1), date(2025, 2, 1),
                                     date(2025, 12, 1))


def row(month, year, week, mode, trips, group="treated", zone_list="core"):
    return {"month": month, "iso_year": year, "iso_week": week, "mode": mode, "zone_list": zone_list,
            "cbd_group": group, "trips_all": trips, "trips_valid": 1}


@pytest.fixture
def weekly(data_dir):
    # Months in the table: 2024-01, 2024-02, 2025-01, 2025-02, 2025-12 (no 2025-03).
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [
        # 2025-W05 (27 Jan – 2 Feb) straddles January and February: rows under both months (D7)
        row(JAN25, 2025, 5, "uber", 400), row(FEB25, 2025, 5, "uber", 300),
        row(JAN25, 2025, 5, "lyft", 210), row(FEB25, 2025, 5, "other_hv", 14),
        row(JAN25, 2025, 5, "yellow", 70), row(FEB25, 2025, 5, "green", 7),
        # 2025-W06 (3–9 Feb): control under core, treated under wide
        row(FEB25, 2025, 6, "uber", 1400, group="control"),
        row(FEB25, 2025, 6, "uber", 2100, zone_list="wide"),
        # 2025-W09 (24 Feb – 2 Mar): March isn't in the table, so 5 of its days are covered
        row(FEB25, 2025, 9, "uber", 500, group="control"),
        # 2024-W05 (29 Jan – 4 Feb)
        row(JAN24, 2024, 5, "uber", 420), row(FEB24, 2024, 5, "uber", 280),
        # ISO year 2026 is outside the study
        row(DEC25, 2026, 1, "uber", 9999),
    ]))


EXPECTED = [   # iso_year, iso_week, week_start, cbd_group, mode, zone_list, trips_per_day
    (2024, 5, date(2024, 1, 29), "treated", "all", "core", 100.0),           # (420 + 280) ÷ 7
    (2024, 5, date(2024, 1, 29), "treated", "ride_hail", "core", 100.0),
    (2025, 5, date(2025, 1, 27), "treated", "all", "core", 143.0),           # 1,001 ÷ 7
    (2025, 5, date(2025, 1, 27), "treated", "ride_hail", "core", 132.0),     # (400 + 300 + 210 + 14) ÷ 7
    (2025, 5, date(2025, 1, 27), "treated", "taxi", "core", 11.0),           # (70 + 7) ÷ 7
    (2025, 6, date(2025, 2, 3), "control", "all", "core", 200.0),            # 1,400 ÷ 7; no cab rows
    (2025, 6, date(2025, 2, 3), "control", "ride_hail", "core", 200.0),
    (2025, 6, date(2025, 2, 3), "treated", "all", "wide", 300.0),            # 2,100 ÷ 7
    (2025, 6, date(2025, 2, 3), "treated", "ride_hail", "wide", 300.0),
    (2025, 9, date(2025, 2, 24), "control", "all", "core", 100.0),           # 500 ÷ 5 days (24–28 Feb)
    (2025, 9, date(2025, 2, 24), "control", "ride_hail", "core", 100.0),
]


def test_cp_weekly_trips(weekly):
    table = metrics.run("cp_weekly_trips")
    assert table.column_names == ["iso_year", "iso_week", "week_start", "cbd_group", "mode", "zone_list",
                                  "trips_per_day"]
    assert table.to_pylist() == [pytest.approx(dict(zip(table.column_names, r))) for r in EXPECTED]
