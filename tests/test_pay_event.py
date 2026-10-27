"""pay_event: weekly ride-hail pay and fares around the 1 Aug 2025 minimum-pay rise (Q6, D12)."""

from datetime import date

import pytest
from factories import agg_table, write_agg

from pipeline import metrics


def row(month, year, week, mode, pay, miles, duration_s, fare, group="control", zone_list="core"):
    return {"month": month, "iso_year": year, "iso_week": week, "mode": mode, "zone_list": zone_list,
            "cbd_group": group, "driver_pay": pay, "miles": float(miles), "duration_s": duration_s,
            "fare_base": float(fare)}


@pytest.fixture
def event(data_dir):
    jul25, aug25, may25, oct25, jul24 = (date(2025, 7, 1), date(2025, 8, 1), date(2025, 5, 1),
                                         date(2025, 10, 1), date(2024, 7, 1))
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [
        # 2025-W31 (28 Jul – 3 Aug), offset 0: uber has a treated row under July and a control row
        # under August, summed (D7): pay 1,000, miles 500, 1,500 minutes, fare 1,400
        row(jul25, 2025, 31, "uber", 300.0, 100, 36_000, 400, group="treated"),
        row(aug25, 2025, 31, "uber", 700.0, 400, 54_000, 1000),
        row(aug25, 2025, 31, "lyft", 500.0, 250, 30_000, 750),        # 500 minutes
        # not counted: other ride-hail, cabs, and the wide list (every trip appears once per list)
        row(aug25, 2025, 31, "other_hv", 99_999.0, 1, 60, 1),
        row(aug25, 2025, 31, "yellow", None, 1000, 60_000, 99_999),
        row(aug25, 2025, 31, "uber", 50_000.0, 1, 60, 1, zone_list="wide"),
        # offsets −12 (W19) and +12 (W43); W18 and W44 fall outside the window
        row(may25, 2025, 19, "uber", 1000.0, 500, 60_000, 1400, group="treated"),
        row(oct25, 2025, 43, "uber", 1050.0, 500, 60_000, 1500),
        row(may25, 2025, 18, "uber", 1.0, 1, 60, 1),
        row(oct25, 2025, 44, "uber", 1.0, 1, 60, 1),
        # 2024-W31 (29 Jul – 4 Aug), the seasonal reference for offset 0
        row(jul24, 2024, 31, "uber", 950.0, 500, 57_000, 1400),
    ]))


EXPECTED = {   # (year, week_offset, mode): (week_start, pay_per_mile, pay_per_min, fare_per_mile)
    (2025, 0, "uber"): (date(2025, 7, 28), 1000 / 500, 1000 / 1500, 1400 / 500),
    (2025, 0, "lyft"): (date(2025, 7, 28), 500 / 250, 500 / 500, 750 / 250),
    # ride_hail = uber + lyft: pay 1,500, miles 750, 2,000 minutes, fare 2,150
    (2025, 0, "ride_hail"): (date(2025, 7, 28), 1500 / 750, 1500 / 2000, 2150 / 750),
    (2025, -12, "uber"): (date(2025, 5, 5), 2.0, 1.0, 2.8),
    (2025, -12, "ride_hail"): (date(2025, 5, 5), 2.0, 1.0, 2.8),
    (2025, -12, "lyft"): (date(2025, 5, 5), None, None, None),           # no data: NULLs, row kept
    (2025, 12, "uber"): (date(2025, 10, 20), 2.1, 1.05, 3.0),             # 1,050 ÷ 500; 1,050 ÷ 1,000
    (2024, 0, "uber"): (date(2024, 7, 29), 1.9, 1.0, 2.8),                # 950 ÷ 500; 950 ÷ 950
    (2024, 0, "ride_hail"): (date(2024, 7, 29), 1.9, 1.0, 2.8),
    (2024, -12, "uber"): (date(2024, 5, 6), None, None, None),
    (2024, 12, "uber"): (date(2024, 10, 21), None, None, None),
}


def test_pay_event(event):
    table = metrics.run("pay_event")
    assert table.column_names == ["year", "week_offset", "week_start", "mode", "pay_per_mile", "pay_per_min",
                                  "fare_per_mile", "transition"]
    rows = {(r["year"], r["week_offset"], r["mode"]): r for r in table.to_pylist()}
    # 2 years × 25 weeks (offsets −12…+12) × 3 modes, whatever data exist
    assert table.num_rows == len(rows) == 150
    assert set(rows) == {(y, o, m) for y in (2024, 2025) for o in range(-12, 13) for m in ("uber", "lyft", "ride_hail")}
    for key, (start, ppm, ppmin, fpm) in EXPECTED.items():
        got = rows[key]
        assert got["week_start"] == start, key
        assert (got["pay_per_mile"], got["pay_per_min"], got["fare_per_mile"]) == pytest.approx((ppm, ppmin, fpm)), key


def test_transition_week_is_offset_zero_in_both_years(event):
    rows = metrics.run("pay_event").to_pylist()
    assert {(r["year"], r["week_offset"]) for r in rows if r["transition"]} == {(2024, 0), (2025, 0)}
    assert [r["year"] for r in rows][:75] == [2024] * 75          # ordered by year, offset, mode
    assert [r["mode"] for r in rows][:3] == ["lyft", "ride_hail", "uber"]
