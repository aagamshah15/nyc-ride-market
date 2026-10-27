"""cp_effect and cp_effect_summary: the weekly congestion-pricing estimate (Q2, Q3), and the
holiday weeks it leaves out (SPEC §6, D12)."""

import statistics
from datetime import date

import pytest
from factories import HV_MODES, TAXI_MODES, agg_table, write_agg

from pipeline import common, metrics, studies

MLK = "Martin Luther King Jr. Day is in ISO week 3 in 2024 (Mon 15 Jan) and week 4 in 2025 (Mon 20 Jan)"


def week_row(year, week, group, month=None, **values):
    """An agg_week_cbd row; month defaults to the month of the week's Monday."""
    monday = date.fromisocalendar(year, week, 1)
    return {"month": month or date(monday.year, monday.month, 1), "iso_year": year, "iso_week": week,
            "mode": "uber", "zone_list": "core", "cbd_group": group, **values}


def four(week, t24, t25, c24, c25, **values):
    """Treated and control rows for one ISO week in 2024 and 2025."""
    return [week_row(2024, week, "treated", trips_all=t24, **values),
            week_row(2025, week, "treated", trips_all=t25, **values),
            week_row(2024, week, "control", trips_all=c24, **values),
            week_row(2025, week, "control", trips_all=c25, **values)]


def by_key(rows, *keys):
    return {tuple(row[k] for k in keys): row for row in rows}


# --- trips: effect, exclusions and the summary --------------------------------

JAN24, FEB24, JAN25, FEB25 = date(2024, 1, 1), date(2024, 2, 1), date(2025, 1, 1), date(2025, 2, 1)


@pytest.fixture
def weeks(data_dir):
    """Uber, core list, ISO weeks 1–8. Months 2024-01/02 and 2024-12, 2025-01/02 are in the
    table, so 2025-W02…W08 and their 2024 weeks are fully covered."""
    rows = []
    rows += four(1, 1000, 100, 1000, 1000)      # 2025-W01 starts 30 Dec 2024: left out (D12)
    rows += four(2, 1000, 900, 2000, 2000)      # growth 0.9 vs 1.0 → effect −0.10
    rows += four(3, 1000, 1000, 1000, 1000)     # MLK week in 2024 only → excluded, effect 0
    rows += four(4, 1000, 500, 1000, 1000)      # MLK week in 2025 only → excluded, effect −0.50
    # 2025-W05 (27 Jan – 2 Feb) and 2024-W05 (29 Jan – 4 Feb) straddle January and February: each
    # group has a row under both months (D7), summed to whole weeks.
    #   treated 2024 600 + 400 = 1,000; 2025 500 + 300 = 800 → growth 0.8
    #   control 2024 1,000 + 1,000 = 2,000; 2025 1,200 + 800 = 2,000 → growth 1.0 → effect −0.20
    # Fare per mile is a ratio of sums over the week: treated 2025 (600 + 1,200) ÷ (100 + 300) = 4.5
    # and 2024 (1,000 + 800) ÷ (200 + 200) = 4.5, growth 1.0; control rows keep the default 6.0, so
    # the effect is 0. Averaging the two months' ratios would give 2025 (6 + 4) ÷ 2 = 5.0 instead.
    rows += [
        week_row(2024, 5, "treated", JAN24, trips_all=600, miles=200.0, fare_base=1000.0),
        week_row(2024, 5, "treated", FEB24, trips_all=400, miles=200.0, fare_base=800.0),
        week_row(2025, 5, "treated", JAN25, trips_all=500, miles=100.0, fare_base=600.0),
        week_row(2025, 5, "treated", FEB25, trips_all=300, miles=300.0, fare_base=1200.0),
        week_row(2024, 5, "control", JAN24, trips_all=1000),
        week_row(2024, 5, "control", FEB24, trips_all=1000),
        week_row(2025, 5, "control", JAN25, trips_all=1200),
        week_row(2025, 5, "control", FEB25, trips_all=800),
    ]
    rows += four(6, 1000, 950, 1000, 1000)      # → −0.05
    rows += four(7, 1000, 1100, 1000, 1250)     # 1.1 ÷ 1.25 − 1 → −0.12
    rows += four(8, 2000, 1700, 1000, 1000)     # 0.85 ÷ 1.0 − 1 → −0.15
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", rows))


EXPECTED_TRIPS = {   # iso_week: (week_start, growth_treated, growth_control, effect, exclusion_reason)
    2: (date(2025, 1, 6), 0.9, 1.0, -0.10, None),
    3: (date(2025, 1, 13), 1.0, 1.0, 0.0, MLK),
    4: (date(2025, 1, 20), 0.5, 1.0, -0.50, MLK),
    5: (date(2025, 1, 27), 0.8, 1.0, -0.20, None),
    6: (date(2025, 2, 3), 0.95, 1.0, -0.05, None),
    7: (date(2025, 2, 10), 1.1, 1.25, -0.12, None),
    8: (date(2025, 2, 17), 0.85, 1.0, -0.15, None),
}


def test_trips_effect_by_week(weeks):
    table = metrics.run("cp_effect")
    assert table.column_names == ["iso_year", "iso_week", "week_start", "mode", "metric", "zone_list",
                                  "growth_treated", "growth_control", "effect", "excluded", "exclusion_reason"]
    rows = [r for r in table.to_pylist() if r["metric"] == "trips"]
    for mode in ("uber", "ride_hail", "all"):   # uber is the only mode, so the groups equal it
        got = {r["iso_week"]: r for r in rows if r["mode"] == mode}
        assert sorted(got) == list(range(2, 9))                 # W01 left out
        for week, (start, g_t, g_c, effect, reason) in EXPECTED_TRIPS.items():
            row = got[week]
            assert (row["iso_year"], row["week_start"], row["zone_list"]) == (2025, start, "core")
            assert (row["growth_treated"], row["growth_control"], row["effect"]) == \
                pytest.approx((g_t, g_c, effect)), week
            assert row["excluded"] is (reason is not None)
            assert row["exclusion_reason"] == reason


def test_ratio_of_sums_across_months(weeks):
    rows = by_key(metrics.run("cp_effect").to_pylist(), "iso_week", "mode", "metric")
    assert rows[(5, "uber", "fare_per_mile")]["growth_treated"] == pytest.approx(1.0)
    assert rows[(5, "uber", "fare_per_mile")]["effect"] == pytest.approx(0.0)
    # factory default sums elsewhere: driver_share 13,120 ÷ 17,730 in every cell → effect 0
    assert rows[(2, "uber", "driver_share")]["effect"] == pytest.approx(0.0)
    assert (2, "all", "driver_share") not in rows


def test_summary_median_and_percentiles(weeks):
    # Weeks not excluded: W02 −0.10, W05 −0.20, W06 −0.05, W07 −0.12, W08 −0.15.
    # Sorted: −0.20, −0.15, −0.12, −0.10, −0.05 (n = 5); quantile_cont interpolates at (n − 1)·q:
    #   median: position 2   → −0.12
    #   p10:    position 0.4 → −0.20 + 0.4 × 0.05 = −0.18
    #   p90:    position 3.6 → −0.10 + 0.6 × 0.05 = −0.07
    table = metrics.run("cp_effect_summary")
    assert table.column_names == ["mode", "metric", "zone_list", "weeks", "median", "p10", "p90"]
    rows = by_key(table.to_pylist(), "mode", "metric", "zone_list")
    for mode in ("uber", "ride_hail", "all"):
        row = rows[(mode, "trips", "core")]
        assert row["weeks"] == 5
        assert (row["median"], row["p10"], row["p90"]) == pytest.approx((-0.12, -0.18, -0.07))
    assert rows[("uber", "fare_per_mile", "core")]["weeks"] == 5
    assert rows[("uber", "fare_per_mile", "core")]["median"] == pytest.approx(0.0)
    assert set(rows) == {(m, metric, "core") for m in ("uber", "ride_hail", "all")
                         for metric in ("trips", "fare_per_mile")} | \
        {(m, "driver_share", "core") for m in ("uber", "ride_hail")}


# --- fare per mile, driver share and the mode groups --------------------------

@pytest.fixture
def ratios(data_dir):
    """ISO week 2 of both years, core list; 100 trips in every row, so trips effects are 0."""
    cells = {   # mode: {(year, group): (miles, fare_base, driver_pay)}
        "uber": {(2024, "treated"): (1000, 5000, 3500), (2025, "treated"): (1000, 5500, 3850),
                 (2024, "control"): (2000, 8000, 6000), (2025, "control"): (2000, 8400, 6300)},
        "lyft": {(2024, "treated"): (1000, 5000, 4000), (2025, "treated"): (1000, 5000, 3600),
                 (2024, "control"): (1000, 4000, 3000), (2025, "control"): (1000, 4000, 3000)},
        "other_hv": {key: (1000, 2000, 99) for key in [(y, g) for y in (2024, 2025) for g in ("treated", "control")]},
        "yellow": {(2024, "treated"): (1000, 3000, None), (2025, "treated"): (1000, 3300, None),
                   (2024, "control"): (1000, 3000, None), (2025, "control"): (1000, 3000, None)},
    }
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [
        week_row(year, 2, group, mode=mode, trips_all=100, miles=float(m), fare_base=float(f),
                 driver_pay=None if p is None else float(p))
        for mode, groups in cells.items() for (year, group), (m, f, p) in groups.items()]))


EXPECTED_RATIOS = {   # (mode, metric): (growth_treated, growth_control, effect)
    # fare per mile = fare_base ÷ miles
    ("uber", "fare_per_mile"): (1.1, 1.05, 1.1 / 1.05 - 1),          # 5.0 → 5.5; 4.0 → 4.2
    ("lyft", "fare_per_mile"): (1.0, 1.0, 0.0),
    ("other_hv", "fare_per_mile"): (1.0, 1.0, 0.0),
    ("yellow", "fare_per_mile"): (1.1, 1.0, 0.1),                    # 3.0 → 3.3; 3.0 → 3.0
    # ride_hail = uber + lyft + other_hv: treated 12,000 ÷ 3,000 → 12,500 ÷ 3,000; control
    # 14,000 ÷ 4,000 → 14,400 ÷ 4,000. effect = (12,500 × 14,000) ÷ (12,000 × 14,400) − 1
    ("ride_hail", "fare_per_mile"): (12500 / 12000, 14400 / 14000, 175 / 172.8 - 1),
    # all adds yellow: treated 15,000 → 15,800 over 4,000 miles; control 17,000 → 17,400 over 5,000
    ("all", "fare_per_mile"): (15800 / 15000, 17400 / 17000, (15800 * 17000) / (15000 * 17400) - 1),
    # driver share = driver_pay ÷ fare_base
    ("uber", "driver_share"): (1.0, 1.0, 0.0),                       # 0.70 → 0.70; 0.75 → 0.75
    ("lyft", "driver_share"): (0.9, 1.0, -0.1),                      # 0.80 → 0.72; 0.75 → 0.75
    # ride_hail = uber + lyft only (contracts/README.md §2): treated 7,500 ÷ 10,000 → 7,450 ÷ 10,500;
    # control 9,000 ÷ 12,000 → 9,300 ÷ 12,400 (0.75 both years)
    ("ride_hail", "driver_share"): (7450 * 10000 / (10500 * 7500), 1.0, 7450 * 10000 / (10500 * 7500) - 1),
}


def test_fare_per_mile_driver_share_and_groups(ratios):
    rows = metrics.run("cp_effect").to_pylist()
    assert {r["iso_week"] for r in rows} == {2}
    got = by_key([r for r in rows if r["metric"] != "trips"], "mode", "metric")
    assert set(got) == set(EXPECTED_RATIOS)          # no driver_share for other_hv, yellow or all
    for key, expected in EXPECTED_RATIOS.items():
        row = got[key]
        assert (row["growth_treated"], row["growth_control"], row["effect"]) == pytest.approx(expected), key
        assert row["excluded"] is False and row["exclusion_reason"] is None
    trips = by_key([r for r in rows if r["metric"] == "trips"], "mode")
    assert sorted(trips) == [("all",), ("lyft",), ("other_hv",), ("ride_hail",), ("uber",), ("yellow",)]
    assert all(r["effect"] == pytest.approx(0.0) for r in trips.values())


def test_zone_lists_are_not_summed_together(data_dir):
    # core: growth 0.9 vs 1.0 → −0.10. wide: 150 ÷ 200 = 0.75 vs 1.0 → −0.25.
    # Summing the lists would give (90 + 150) ÷ (100 + 200) = 0.8 → −0.20 for both.
    rows = four(2, 100, 90, 100, 100) + [dict(r, zone_list="wide") for r in four(2, 200, 150, 100, 100)]
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", rows))
    got = by_key(metrics.run("cp_effect").to_pylist(), "mode", "metric", "zone_list")
    assert got[("uber", "trips", "core")]["effect"] == pytest.approx(-0.10)
    assert got[("uber", "trips", "wide")]["effect"] == pytest.approx(-0.25)
    summary = by_key(metrics.run("cp_effect_summary").to_pylist(), "mode", "metric", "zone_list")
    assert summary[("all", "trips", "wide")]["median"] == pytest.approx(-0.25)


# --- weeks the aggregates don't fully cover -----------------------------------

def test_incomplete_weeks_are_excluded(data_dir):
    # Only February 2024 and February 2025 are in the table.
    #   2025-W05 (27 Jan – 2 Feb): 2 days covered; 2024-W05 (29 Jan – 4 Feb): 4 days
    #   2025-W06 (3–9 Feb) and 2024-W06 (5–11 Feb): all 7 → kept
    #   2025-W09 (24 Feb – 2 Mar): 5 days (24–28 Feb); 2024-W09 (26 Feb – 3 Mar): 4 days (26–29 Feb)
    rows = []
    for week in (5, 6, 9):
        rows += [dict(r, month=date(r["iso_year"], 2, 1)) for r in four(week, 100, 90, 100, 100)]
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", rows))
    got = {r["iso_week"]: r for r in metrics.run("cp_effect").to_pylist()
           if r["mode"] == "uber" and r["metric"] == "trips"}
    assert got[5]["exclusion_reason"] == ("the aggregates cover 4 of the 7 days of 2024-W05; "
                                          "the aggregates cover 2 of the 7 days of 2025-W05")
    assert got[9]["exclusion_reason"] == ("the aggregates cover 4 of the 7 days of 2024-W09; "
                                          "the aggregates cover 5 of the 7 days of 2025-W09")
    assert [got[w]["excluded"] for w in (5, 6, 9)] == [True, False, True]
    assert got[5]["effect"] == pytest.approx(-0.10)    # still computed, just left out of the summary
    summary = by_key(metrics.run("cp_effect_summary").to_pylist(), "mode", "metric", "zone_list")
    assert summary[("uber", "trips", "core")]["weeks"] == 1
    assert summary[("uber", "trips", "core")]["median"] == pytest.approx(-0.10)


def test_no_base_year_data(data_dir):
    # 2025 only: every week lacks its 2024 week, so growth and effect are NULL and the week is
    # excluded; the summary still has a row, with 0 weeks.
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [week_row(2025, 10, g) for g in ("treated", "control")]))
    rows = metrics.run("cp_effect").to_pylist()
    assert rows and all(r["effect"] is None and r["excluded"] for r in rows)
    assert rows[0]["exclusion_reason"] == "the aggregates cover 0 of the 7 days of 2024-W10"
    summary = metrics.run("cp_effect_summary").to_pylist()
    assert summary and all(r["weeks"] == 0 and r["median"] is None for r in summary)


# --- the excluded holiday weeks: computed, configured and mirrored -------------

def test_federal_holidays_as_observed():
    assert [d for _, d in studies.federal_holidays(2024)] == [
        date(2024, 1, 1), date(2024, 1, 15), date(2024, 2, 19), date(2024, 5, 27), date(2024, 6, 19),
        date(2024, 7, 4), date(2024, 9, 2), date(2024, 10, 14), date(2024, 11, 11), date(2024, 11, 28),
        date(2024, 12, 25)]
    assert [d for _, d in studies.federal_holidays(2025)] == [
        date(2025, 1, 1), date(2025, 1, 20), date(2025, 2, 17), date(2025, 5, 26), date(2025, 6, 19),
        date(2025, 7, 4), date(2025, 9, 1), date(2025, 10, 13), date(2025, 11, 11), date(2025, 11, 27),
        date(2025, 12, 25)]
    observed = dict(studies.federal_holidays(2021))
    assert observed["Independence Day"] == date(2021, 7, 5)      # Sunday → Monday
    assert observed["Christmas Day"] == date(2021, 12, 24)       # Saturday → Friday
    assert dict(studies.federal_holidays(2022))["New Year's Day"] == date(2021, 12, 31)


def test_holiday_weeks_2024_vs_2025():
    # Only MLK Day moves: Mon 15 Jan 2024 is in W03, Mon 20 Jan 2025 in W04. Every other holiday
    # keeps its ISO week (e.g. Thanksgiving W48 both years).
    assert studies.holiday_weeks() == [
        {"iso_week": 3, "holiday": "Martin Luther King Jr. Day", "reason": MLK},
        {"iso_week": 4, "holiday": "Martin Luther King Jr. Day", "reason": MLK},
    ]
    with pytest.raises(ValueError, match="outside its ISO year"):
        studies.holiday_weeks(2020, 2021)      # 1 Jan 2021 is in 2020-W53


def test_periods_yaml_holds_the_computed_weeks():
    assert studies.configured_holiday_weeks() == studies.holiday_weeks()


def test_write_holidays_keeps_other_keys_and_is_idempotent(tmp_path):
    path = tmp_path / "periods.yaml"
    path.write_text("congestion_pricing_start: 2025-01-05   # comment kept\n")
    studies.write_holidays(path)
    once = path.read_text()
    studies.write_holidays(path)
    assert path.read_text() == once
    assert once.startswith("congestion_pricing_start: 2025-01-05   # comment kept\n\n# BEGIN excluded_holiday_weeks")
    assert (common.CONFIG_DIR / "periods.yaml").read_text().endswith(once.split("\n\n", 1)[1])


@pytest.fixture
def every_week(data_dir):
    """Uber, core list, every ISO week of 2024 and 2025, fully covered; varied effects."""
    rows = []
    for week in range(1, 53):
        rows += four(week, 1000, 900 + 7 * (week % 11), 2000, 1900 + 13 * (week % 7))
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", rows))


def test_sql_mirrors_periods_yaml(every_week):
    expected = {}
    for entry in studies.configured_holiday_weeks():
        expected.setdefault(entry["iso_week"], []).append(entry["reason"])
    expected = {week: "; ".join(sorted(reasons)) for week, reasons in expected.items()}
    rows = metrics.run("cp_effect").to_pylist()
    assert {r["iso_week"] for r in rows} == set(range(2, 53))
    assert {r["iso_week"]: r["exclusion_reason"] for r in rows if r["excluded"]} == expected


def test_summary_agrees_with_weekly_effects(every_week):
    effects = metrics.run("cp_effect").to_pylist()
    for row in metrics.run("cp_effect_summary").to_pylist():
        values = [r["effect"] for r in effects if (r["mode"], r["metric"], r["zone_list"]) ==
                  (row["mode"], row["metric"], row["zone_list"]) and not r["excluded"] and r["effect"] is not None]
        assert row["weeks"] == len(values) == 49           # W02–W52 less the two MLK weeks
        deciles = statistics.quantiles(values, n=10, method="inclusive")
        assert (row["median"], row["p10"], row["p90"]) == \
            pytest.approx((statistics.median(values), deciles[0], deciles[8]))


def test_summary_and_weekly_files_share_the_effect_sql():
    def block(name):
        text = metrics.sql_text(name)
        return text[text.index("-- BEGIN weekly effects"):text.index("-- END weekly effects")]
    assert block("cp_effect") == block("cp_effect_summary")


def test_every_mode_appears(data_dir):
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", [
        week_row(y, 2, g, mode=mode) for mode in HV_MODES + TAXI_MODES for y in (2024, 2025)
        for g in ("treated", "control")]))
    rows = metrics.run("cp_effect").to_pylist()
    assert {(r["mode"], r["metric"]) for r in rows} == \
        {(m, metric) for m in HV_MODES + TAXI_MODES + ("ride_hail", "all") for metric in ("trips", "fare_per_mile")} | \
        {(m, "driver_share") for m in ("uber", "lyft", "ride_hail")}
