"""findings.py: number formats (contracts/README.md §3, as format.js), sentences worked out by
hand, the language rules in CLAUDE.md, and missing values (L11)."""

import json
import shutil
import subprocess

import pytest

from pipeline import common, findings

COMPONENTS = common.REPO_ROOT / "site" / "src" / "components"
AUG26 = "2026-08-01"

FORMAT_CASES = [   # contracts/README.md §3 examples, then the edges L05 pinned in format.js
    (findings.count, 842, "842"),
    (findings.count, 1280, "1,280"),
    (findings.count, 675432, "675,000"),
    (findings.count, 20100000, "20.1 million"),
    (findings.count, 842.3, "842.3"),
    (findings.count, 9999999, "10.0 million"),
    (findings.share, 0.84, "84%"),
    (findings.share, 0.032, "3.2%"),
    (findings.share, 0.0996, "10%"),
    (findings.share_change, 0.021, "+2.1 pts"),
    (findings.share_change, -0.004, "−0.4 pts"),
    (findings.share_change, -0.0004, "0.0 pts"),
    (findings.rel_change, 0.031, "+3.1%"),
    (findings.rel_change, -0.074, "−7.4%"),
    (findings.usd, 18.4, "$18.40"),
    (findings.usd, 4812, "$4,812"),
    (findings.usd, 48200000, "$48.2 million"),
    (findings.usd, 99.999, "$100"),
    (findings.usd, 1000000, "$1,000,000"),
    (findings.usd_per_mile, 2.87, "$2.87/mile"),
    (findings.usd_per_minute, 1.12, "$1.12/min"),
    (findings.usd_per_hour, 38.5, "$38.50/hour"),
    (findings.seconds, 252, "4.2 min"),
    (findings.trips_per_hour, 1.5376, "1.54 trips/hour"),
    (findings.ratio, 2.57, "2.6×"),
    (findings.month_label, "2025-01-01", "Jan 2025"),
    (findings.month_label, "2026-08", "Aug 2026"),
    (findings.week_label, "2025-01-06", "week of 6 Jan 2025"),
    (findings.hour_of_day, 0, "12 am"),
    (findings.hour_of_day, 6, "6 am"),
    (findings.hour_of_day, 12, "12 pm"),
    (findings.hour_of_day, 18, "6 pm"),
    (findings.hour_of_week, 0, "Sun 12 am"),
    (findings.hour_of_week, 2 * 24 + 18, "Tue 6 pm"),
]


@pytest.mark.parametrize("fn, value, expected", FORMAT_CASES)
def test_formats_follow_the_contract(fn, value, expected):
    assert fn(value) == expected


# Values chosen to hit rounding edges: halves, binary near-halves, unit boundaries, negatives.
PARITY_VALUES = [0, 0.5, 1.005, 2.675, 9.95, 99.995, 999.5, 999.95, 1000, 1285, 12345.6, 99950, 999500,
                 9_995_000, 10_050_000, -3.25, -0.0125, 0.0995, 0.125, 0.0425, 0.00049, 0.1049999]
PARITY_FUNCTIONS = {"count": "count", "share": "share", "share_change": "shareChange",
                    "rel_change": "relChange", "usd": "usd", "usd_per_mile": "usdPerMile", "seconds": "seconds",
                    "ratio": "ratio", "trips_per_hour": "tripsPerHour"}


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_formats_match_format_js():
    """Every sentence number reads as the site prints it: findings.py against format.js itself."""
    calls = [(py, js, v) for py, js in PARITY_FUNCTIONS.items() for v in PARITY_VALUES
             if not (py in ("ratio", "trips_per_hour") and v < 0)]
    script = (f"const m = await import({json.dumps((COMPONENTS / 'format.js').as_uri())});\n"
              f"console.log(JSON.stringify([{', '.join(f'm.{js}({v!r})' for _, js, v in calls)}]));")
    result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    expected = json.loads(result.stdout)
    got = [getattr(findings, py)(v) for py, _, v in calls]
    assert {f"{py}({v})": g for (py, _, v), g in zip(calls, got)} == \
           {f"{py}({v})": e for (py, _, v), e in zip(calls, expected)}


# --- words -------------------------------------------------------------------

def test_moved_follows_the_displayed_rounding():
    assert findings.moved(0.021) == "rose 2.1 pts"
    assert findings.moved(-0.074, "relative") == "fell 7.4%"
    assert findings.moved(0.0004) == "held steady"            # shows as 0.0 pts


def test_against_prior_and_counts():
    assert findings.against_prior(23, 19) == ", up from 19 a year earlier"
    assert findings.against_prior(1, 2) == ", down from 2 a year earlier"
    assert findings.against_prior(4, 4) == ", the same as a year earlier"
    assert findings.against_prior(4, None) == ""
    assert findings.zones_count(1) == "1 zone"
    assert findings.zones_count(1280) == "1,280 zones"


def test_rank_words():
    assert [findings.rank_words(i, 4) for i in range(4)] == [
        "the lowest", "the second lowest", "the second highest", "the highest"]


# --- sentences worked out by hand ----------------------------------------------

def test_q4_lyft_against_uber():
    assert findings.q4(zones_now=23, zones_prior=19, month=AUG26) == {
        "question": "Q4", "text": "Lyft had a bigger share of pickups than Uber in 23 zones in Aug 2026, "
                                  "up from 19 a year earlier",
        "value": 23, "unit": "count", "page": "/companies/lyft", "featured": False}


def test_q2_congestion_effect_by_mode():
    # all modes: median −0.06, p10 −0.0826, p90 −0.0402; by mode ride-hail −0.0813 and yellow −0.0777;
    # green, 0.17% of NYC trips, comes apart with its share.
    result = findings.q2(all_modes=(-0.06, -0.0826, -0.0402),
                         by_mode={"ride_hail": -0.0813, "yellow": -0.0777, "green": 0.0411}, green_share=0.0017)
    assert result["text"] == ("Congestion pricing had an estimated effect of −6.0% on trips touching the zone "
                              "(weekly range −8.3% to −4.0%); by mode, ride-hail apps −8.1% and yellow cabs −7.8%, "
                              "while green cabs, 0.2% of NYC trips, came out at +4.1%")
    assert (result["value"], result["unit"], result["featured"]) == (-0.06, "effect", True)
    assert findings.congestion_effects(by_mode={"ride_hail": -0.0813, "yellow": -0.0777, "green": 0.0411},
                                       green_share=0.0017) == (
        "By mode, the estimated effect on trips touching the zone was −8.1% for ride-hail apps and −7.8% for "
        "yellow cabs; green cabs, 0.2% of NYC trips, came out at +4.1%")


def test_destination_sentences():
    assert findings.zone_top_destinations(name="Park Slope", dest_share=0.041, left_city_share=0.071,
                                          month=AUG26) == (
        "Park Slope was the top destination from here in Aug 2026, with 4.1% of trips; 7.1% of trips left the city")
    assert findings.zone_top_destinations(name=None, dest_share=None, left_city_share=0.25, month=AUG26) == \
        "No destination in the city had enough trips from here in Aug 2026 to list; 25% of trips left the city"
    assert findings.zone_top_destinations(name=None, dest_share=None, left_city_share=None, month=AUG26) == \
        "No destination had enough trips from here in Aug 2026 to list"


def test_airports_named_by_direction():
    assert findings.airports_title(mode="uber", top_share=0.63, airports=["JFK", "LGA"], dropoff_only=["EWR"],
                                   month=AUG26) == \
        "Uber carried 63% of trips to and from JFK and LaGuardia and to Newark in Aug 2026"


def test_q14_fee_money():
    # $10,627,132.13 is above $1 million → "$10.6 million"; +2.29% → "+2.3%".
    result = findings.q14(total=10_627_132.13, change=0.0229, top_mode="uber", top_amount=5_820_800.67,
                          month=AUG26)
    assert result["text"] == ("Trips were charged $10.6 million in congestion fees in Aug 2026 "
                              "(+2.3% on a year earlier); Uber trips paid the most, $5.8 million")
    assert result["value"] == 10_627_132.13


def test_q6_new_pay_rule():
    # Net of the same weeks of 2024: pay per minute −0.9%, pay per mile −1.2%, base fare per mile −2.2%.
    result = findings.q6(pay_per_min=-0.0091, pay_per_mile=-0.0121, fare_per_mile=-0.0218, weeks=12,
                         base_year=2024, rule_month="2025-08-01")
    assert result["text"] == ("Over the 12 weeks after the new minimum-pay rule of Aug 2025, which lowered the "
                              "per-mile floor and raised the per-minute floor, ride-hail driver pay per minute with "
                              "a passenger fell 0.9% and pay per mile fell 1.2% against the 12 weeks before, net of "
                              "the same weeks of 2024; base fare per mile fell 2.2%")
    assert (result["value"], result["unit"]) == (-0.0091, "effect")
    assert findings.drivers_event_study(pay_per_min=-0.0091, pay_per_mile=-0.0121, weeks=12, base_year=2024) == (
        "Net of the same weeks of 2024, ride-hail driver pay per minute with a passenger fell 0.9% and pay per mile "
        "fell 1.2% in the 12 weeks after the new minimum-pay rule, against the 12 weeks before")


def test_q11_accessible_service():
    # D29: completed WAV-requested trips and the share of trips in a WAV; no match rate.
    service = {"uber": (39_879, 0.0937), "lyft": (16_612, 0.0851)}
    result = findings.q11(service=service, month=AUG26)
    assert result["text"] == ("Uber completed 39,900 trips that requested a wheelchair-accessible vehicle in Aug 2026 "
                              "and Lyft 16,600, and 9.4% of Uber's trips and 8.5% of Lyft's trips ran in one; "
                              "requests that went unfilled aren't in TLC's records")
    assert (result["value"], result["unit"]) == (39_879, "count")
    assert findings.company_wav(mode="uber", service=service, month=AUG26) == (
        "Uber completed 39,900 trips that requested a wheelchair-accessible vehicle in Aug 2026, and 9.4% of all its "
        "trips ran in one; requests that went unfilled aren't in TLC's records")
    assert findings.company_wav(mode="yellow", service=service, month=AUG26) == (
        "Wheelchair-accessible service isn't reported for yellow cabs; in Aug 2026, 9.4% of Uber trips and 8.5% of "
        "Lyft trips ran in a wheelchair-accessible vehicle; requests that went unfilled aren't in TLC's records")


def test_share_trend_over_the_same_month():
    assert findings.home_share_trend(mode="uber", change=-0.0169, first_month="2024-08-01", month=AUG26,
                                     turn=("dipped", "2025-08-01", 0.592)) == (
        "Uber's share fell 1.7 pts between Aug 2024 and Aug 2026, the biggest shift of any company; it dipped to "
        "59% in Aug 2025")
    assert findings.home_share_trend(mode="uber", change=None, first_month=None, month=AUG26) is None


def test_q9_names_each_airport_fare():
    result = findings.q9(mode="uber", top_share=0.6333, airports=["JFK", "LGA"], dropoff_only=["EWR"],
                         fares=[("JFK", 106.38), ("LGA", 75.52)], busiest_hour=14, month=AUG26)
    assert result["text"] == ("Uber carried 63% of trips to and from JFK and LaGuardia and to Newark in Aug 2026; "
                              "the mean fare to Manhattan before tip was $106 from JFK and $75.52 from LaGuardia, "
                              "and trips peaked at 2 pm")


def test_borough_sentence_names_its_measure():
    assert findings.prices_by_borough(borough="Manhattan", fare_per_mile=6.41, window=3, month=AUG26) == (
        "Manhattan had the highest overall fare per mile (total fares ÷ total miles), $6.41/mile across all modes, "
        "over the 3 months to Aug 2026")


def test_newark_page_sentences():
    assert findings.zone_not_tlc_title(name="Newark Airport", dropoffs_per_day=4982.3, month=AUG26) == \
        "TLC vehicles dropped off 4,980 trips a day at Newark Airport in Aug 2026; pickups there aren't TLC trips"
    assert findings.zone_not_tlc(name="Newark Airport", chart="waits") == \
        "Pickups at Newark Airport aren't TLC trips, so there are no waits to report"


def test_thin_and_empty_zone_titles():
    assert findings.zone_title(name="Jamaica Bay", rh_share=0.6, trips=50, thin=True, month=AUG26) == \
        "Jamaica Bay had 50 pickups in Aug 2026, too few to profile"
    assert findings.zone_title(name="Zone 50", rh_share=None, trips=0, thin=True, month=AUG26) == \
        "No pickups were recorded in Zone 50 in Aug 2026"
    assert findings.zone_share_trend(rh_share=1.0, change=0.0, month=AUG26, prior="2025-08-01") == \
        "Ride-hail apps' share of pickups here held steady between Aug 2025 and Aug 2026, at 100%"


# --- language rules (CLAUDE.md) ---------------------------------------------

def test_cab_tips_are_card_only():
    text = findings.company_tip_rate(mode="yellow", tip_rate=0.18, change=0.004, card_only=True, month=AUG26)
    assert text.startswith("Card-only tips on yellow cabs came to 18% of the fare")
    q13 = findings.q13(rates={"uber": 0.07, "lyft": 0.09, "yellow": 0.18, "green": 0.12}, month=AUG26)["text"]
    assert q13 == ("Riders tipped 7.0% of the base fare on Uber and 9.0% on Lyft in Aug 2026; card-only tips "
                   "came to 18% of the fare on yellow cabs and 12% on green cabs")


def test_pay_per_hour_is_with_a_passenger():
    text = findings.drivers_pay_per_hour(pay_per_hour=38.5, change=-0.0213, month=AUG26)
    assert text == "Ride-hail drivers earned $38.50 per hour with a passenger in Aug 2026 (−2.1% on a year earlier)"


def test_congestion_results_are_estimated_effects():
    sentences = [findings.congestion_title(trips_effect=-0.06),
                 findings.congestion_effects(by_mode={"ride_hail": -0.08, "yellow": -0.07}, green_share=None),
                 findings.congestion_weekly_effect(p10=-0.08, p90=-0.04),
                 findings.q3(fpm_effect=0.025, driver_share_effect=-0.004)["text"]]
    for text in sentences:
        assert "estimated effect" in text.lower()
        assert "caus" not in text.lower()


# --- missing values ----------------------------------------------------------

def test_missing_values_give_no_sentence():
    assert findings.home_title(rh_share=None, month=AUG26) is None
    assert findings.prices_title(fpm_median=float("nan"), month=AUG26) is None
    assert findings.q1(rh_share=None, change=None, zones_up=None, zones_total=None, month=AUG26) is None
    assert findings.q15(tph=None, drivers=1, hours_per_day=7.0, tlc_month=AUG26) is None


def test_optional_clauses_drop_out():
    result = findings.q1(rh_share=0.78, change=None, zones_up=None, zones_total=None, month=AUG26)
    assert result["text"] == "Ride-hail apps carried 78% of NYC trips in Aug 2026"
    assert findings.q14(total=2925.0, change=None, top_mode=None, top_amount=None, month=AUG26)["text"] == \
        "Trips were charged $2,925 in congestion fees in Aug 2026"
