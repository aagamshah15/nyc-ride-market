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


def test_q2_congestion_effect():
    # all modes: median −0.06, p10 −0.0826, p90 −0.0402; the largest company effect by size is
    # yellow's −0.071 (Uber −0.0584, Lyft −0.03, green +0.01).
    result = findings.q2(all_modes=(-0.06, -0.0826, -0.0402),
                         by_company={"uber": -0.0584, "lyft": -0.03, "yellow": -0.071, "green": 0.01})
    assert result["text"] == ("Congestion pricing had an estimated effect of −6.0% on trips touching the zone "
                              "(weekly range −8.3% to −4.0%); among companies it was largest for yellow cabs, "
                              "at −7.1%")
    assert (result["value"], result["unit"], result["featured"]) == (-0.06, "effect", True)


def test_q14_fee_money():
    # $10,627,132.13 is above $1 million → "$10.6 million"; +2.29% → "+2.3%".
    result = findings.q14(total=10_627_132.13, change=0.0229, top_mode="uber", top_amount=5_820_800.67,
                          month=AUG26)
    assert result["text"] == ("Trips were charged $10.6 million in congestion fees in Aug 2026 "
                              "(+2.3% on a year earlier); Uber trips paid the most, $5.8 million")
    assert result["value"] == 10_627_132.13


def test_q6_pay_rise():
    # $44.73 against $42.60 is +5.0%; fare per mile unchanged reads "held steady".
    result = findings.q6(pay_after=44.73, pay_before=42.60, fpm_change=0.0, rise_month="2025-08-01",
                         before_month="2025-07-01")
    assert result["text"] == ("Ride-hail drivers earned $44.73 per hour with a passenger in Aug 2025, the month "
                              "the minimum-pay rise began, +5.0% on Jul 2025; fare per mile held steady over "
                              "the same months")


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
                 findings.congestion_effects(lowest=("uber", -0.09), highest=("green", 0.01)),
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
