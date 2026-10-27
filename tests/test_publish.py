"""publish.py: every contract file from metric outputs, the validation gate, budgets, stale files,
and findings checked against values worked out by hand, on factory aggregates (L11)."""

import importlib.util
import json
import re
from datetime import date
from pathlib import Path

import pytest
import yaml
from contract_check import assert_matches_contract
from factories import HV_MODES, agg_table, write_agg
from test_site_budget import budget_problems

from pipeline import common, findings, metrics, publish

SITE_CONTRACTS = common.REPO_ROOT / "contracts" / "site"
L10_METRICS = {"cp_effect", "cp_effect_summary", "cp_weekly_trips", "cp_zone_change", "pay_event"}


def _load_mock_module():
    spec = importlib.util.spec_from_file_location("make_mock_site_data",
                                                  common.REPO_ROOT / "scripts" / "make_mock_site_data.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mock = _load_mock_module()

AUG24, JUL25, AUG25, AUG26 = date(2024, 8, 1), date(2025, 7, 1), date(2025, 8, 1), date(2026, 8, 1)

# Pickups (trips_all = trips_valid) by zone and mode, one hour-of-week cell each. Aug 2026 against
# the same three earlier months (Aug 2024, Jul 2025, Aug 2025). Zone 2 is thin in Aug 2026 (50 < 100)
# but not a year earlier (100); 264 is the unknown zone and gets no page.
TRIPS_NOW = {161: {"uber": 500, "lyft": 200, "yellow": 300}, 236: {"uber": 300, "lyft": 400, "yellow": 100},
             132: {"uber": 200, "lyft": 100, "yellow": 500}, 7: {"uber": 300, "lyft": 100, "green": 200},
             2: {"uber": 30, "yellow": 20}, 264: {"uber": 100}}
TRIPS_BEFORE = {161: {"uber": 450, "lyft": 250, "yellow": 300}, 236: {"uber": 400, "lyft": 300, "yellow": 100},
                132: {"uber": 300, "lyft": 100, "yellow": 400}, 7: {"uber": 200, "lyft": 100, "green": 300},
                2: {"uber": 30, "yellow": 70}, 264: {"uber": 100}}
BUSY_ZONE = 230   # every mode in every hour of the week: the zone-file size worst case

NAMED_ZONES = {1: ("EWR", "Newark Airport", "EWR"), 2: ("Queens", "Jamaica Bay", "Boro Zone"),
               7: ("Queens", "Astoria", "Boro Zone"), 132: ("Queens", "JFK Airport", "Airports"),
               138: ("Queens", "LaGuardia Airport", "Airports"),
               161: ("Manhattan", "Midtown Center", "Yellow Zone"),
               230: ("Manhattan", "Times Sq/Theatre District", "Yellow Zone"),
               236: ("Manhattan", "Upper East Side North", "Yellow Zone"),
               264: ("Unknown", "N/A", "N/A"), 265: ("N/A", "Outside of NYC", "N/A")}
BOROUGHS = ("Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island")


# --- the factory set -----------------------------------------------------------

def write_zone_lookup(data_dir: Path) -> None:
    lines = ['"LocationID","Borough","Zone","service_zone"']
    for z in range(1, 266):
        borough, name, service = NAMED_ZONES.get(z, (BOROUGHS[z % 5], f"Zone {z}", "Boro Zone"))
        lines.append(f'{z},"{borough}","{name}","{service}"')
    (data_dir / "ref").mkdir(exist_ok=True)
    (data_dir / "ref" / "taxi_zone_lookup.csv").write_text("\n".join(lines) + "\n")


def write_zone_map(data_dir: Path) -> None:
    """A 263-zone grid with clockwise rings, as L04's map has (the mock generator's)."""
    (data_dir / "ref").mkdir(exist_ok=True)
    geojson = mock.MockSite(generated_at="2026-10-27T00:00:00Z").geojson()
    (data_dir / "ref" / "taxi_zones.simplified.geojson").write_text(json.dumps(geojson))


def zone_hour_rows(busy: bool) -> list[dict]:
    rows = []
    for month in (AUG24, JUL25, AUG25, AUG26):
        for zone, by_mode in (TRIPS_NOW if month == AUG26 else TRIPS_BEFORE).items():
            for mode, n in by_mode.items():
                row = {"month": month, "mode": mode, "pu_zone": zone, "trips_all": n, "trips_valid": n}
                if month == AUG25 and mode in HV_MODES:
                    row["driver_pay"] = 1_461.18          # the pay rise: +5% on the default 1,391.60
                rows.append(row)
    if busy:
        rows += [{"month": AUG26, "mode": mode, "pu_zone": BUSY_ZONE, "hour_of_week": h, "trips_all": 1000 + h,
                  "trips_valid": 1000 + h} for mode in common.MODES for h in range(168)]
    return rows


def dist_rows() -> list[dict]:
    rows = []
    for month in (AUG25, AUG26):
        city = {"uber": 3.10, "lyft": 3.20, "yellow": 3.60, "green": 3.30, "ride_hail": 3.15,
                "all": 3.35 if month == AUG26 else 3.20}
        waits = {"uber": 240.0, "lyft": 270.0}   # city-wide median waits; cabs and groups have none
        for mode, p50 in city.items():
            rows.append({"month": month, "mode": mode, "pu_zone": 0, "n": 50_000, "fpm_p50": p50,
                         "wait_p50": waits.get(mode), "wait_p90": 600.0 if mode in waits else None})
        rows += [
            {"month": month, "mode": "uber", "pu_zone": 161, "n": 6_000, "fpm_p10": 2.0, "fpm_p90": 9.0},
            {"month": month, "mode": "yellow", "pu_zone": 161},
            {"month": month, "mode": "uber", "pu_zone": 236},
            {"month": month, "mode": "lyft", "pu_zone": 236, "wait_p50": 600.0, "wait_p90": 1_200.0},
            {"month": month, "mode": "yellow", "pu_zone": 132},
            {"month": month, "mode": "uber", "pu_zone": 132},
            {"month": month, "mode": "uber", "pu_zone": 7},
        ]
    return rows


def od_rows() -> list[dict]:
    rows = []
    for month, uber_total in ((AUG25, 3_000.0), (AUG26, 3_200.0)):
        rows += [
            {"month": month, "mode": "uber", "pu_zone": 161, "do_zone": 236},
            {"month": month, "mode": "yellow", "pu_zone": 161, "do_zone": 132, "trips_valid": 30},
            {"month": month, "mode": "uber", "pu_zone": 132, "do_zone": 161, "rider_total_ex_tip": uber_total},
            {"month": month, "mode": "yellow", "pu_zone": 132, "do_zone": 161, "trips_valid": 20,
             "rider_total_ex_tip": 1_400.0},
            {"month": month, "mode": "lyft", "pu_zone": 236, "do_zone": 161, "trips_valid": 25},
        ]
    return rows


def airport_rows() -> list[dict]:
    cells = {AUG26: [("JFK", "from", "uber", 15, 60), ("JFK", "from", "yellow", 15, 40), ("JFK", "to", "uber", 7, 50),
                     ("LGA", "from", "uber", 15, 30), ("LGA", "from", "yellow", 15, 20)],
             AUG25: [("JFK", "from", "uber", 15, 50), ("JFK", "from", "yellow", 15, 50), ("JFK", "to", "uber", 7, 50),
                     ("LGA", "from", "uber", 15, 30), ("LGA", "from", "yellow", 15, 20)]}
    return [{"month": month, "airport": airport, "direction": direction, "mode": mode, "hour_of_day": hour,
             "trips_valid": n} for month, rows in cells.items() for airport, direction, mode, hour, n in rows]


def week_rows() -> list[dict]:
    """Congestion weeks 2025-W10…W12 against 2024 (all in March), core list. Treated trips: 1,000 a
    mode in 2024; Uber 900, 800, 1,000 and yellow 980 in 2025. Control: 2,000 both years. Uber's
    treated 2025 fare is +10% (19,503 against the default 17,730). Pay weeks W30 and W32 have
    control rows only, so they feed pay_event and give the congestion effect no week."""
    rows = []
    for week, uber_2025 in ((10, 900), (11, 800), (12, 1000)):
        for year in (2024, 2025):
            month = date(year, 3, 1)
            for mode, treated in (("uber", uber_2025 if year == 2025 else 1000), ("yellow", 980 if year == 2025 else 1000)):
                extra = {"fare_base": 19_503.0} if (mode, year) == ("uber", 2025) else {}
                rows.append({"month": month, "iso_year": year, "iso_week": week, "mode": mode,
                             "cbd_group": "treated", "trips_all": treated, **extra})
                rows.append({"month": month, "iso_year": year, "iso_week": week, "mode": mode,
                             "cbd_group": "control", "trips_all": 2000})
    for year in (2024, 2025):
        for week in (30, 32):
            monday = date.fromisocalendar(year, week, 1)
            rows.append({"month": date(year, monday.month, 1), "iso_year": year, "iso_week": week, "mode": "uber",
                         "cbd_group": "control",
                         "driver_pay": 13_776.0 if (year, week) == (2025, 32) else 13_120.0})
    return rows


FEES = {AUG24: {"uber": 0.0, "lyft": 0.0, "yellow": 0.0, "green": 0.0},
        JUL25: {"uber": 1_200.0, "lyft": 500.0, "yellow": 600.0, "green": 50.0},
        AUG25: {"uber": 1_300.0, "lyft": 500.0, "yellow": 650.0, "green": 50.0},
        AUG26: {"uber": 1_500.0, "lyft": 600.0, "yellow": 750.0, "green": 75.0}}


def write_fixture(data_dir: Path, busy: bool = False) -> None:
    """Every aggregate table the metrics read, the zone lookup and the zone map."""
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", zone_hour_rows(busy)))
    write_agg("agg_zone_month_dist", agg_table("agg_zone_month_dist", dist_rows()))
    write_agg("agg_od_month", agg_table("agg_od_month", od_rows()))
    write_agg("agg_airport", agg_table("agg_airport", airport_rows()))
    write_agg("agg_week_cbd", agg_table("agg_week_cbd", week_rows()))
    write_agg("agg_fees_month", agg_table("agg_fees_month", [
        {"month": month, "mode": mode, "cbd_fee": fee} for month, by_mode in FEES.items() for mode, fee in by_mode.items()]))
    write_agg("agg_quality_month", agg_table("agg_quality_month", [
        {"month": month, "mode": mode} for month in (AUG25, AUG26) for mode in common.MODES]))
    write_agg("ref_indicators", agg_table("ref_indicators", [
        {"month": month, "Year/Month": common.format_month(month), "License Class": lc}
        for month in (AUG25, AUG26) for lc in ("FHV - High Volume", "Yellow", "Green", "FHV - Black Car")]))
    write_zone_lookup(data_dir)
    write_zone_map(data_dir)


def write_summary(data_dir: Path, status: str = "pass", months: tuple = ("2025-08", "2026-08")) -> None:
    """validation_summary.json in the shape of contracts/README.md §5."""
    summary = {
        "generated_at": "2026-10-27T10:00:00Z", "status": status, "months_checked": list(months),
        "checks": [{"id": check, "status": status, "summary": f"{check} summary"}
                   for check in ("tie_out", "quality_drift", "cbd_list", "schema", "fees")],
        "tie_out": [{"month": "2026-08-01", "license_class": "FHV - High Volume", "pipeline_trips_per_day": 108.1,
                     "tlc_trips_per_day": 108.0, "diff": 0.0009, "status": "pass"}],
        "quality": [{"month": "2026-08-01", "mode": "uber", "valid_share": 0.985, "status": "pass"}],
        "cbd": [{"zone_list": "core", "both_in_fee_share": 0.993, "neither_in_fee_share": 0.004, "status": "pass"}],
        "fees": [{"mode": "uber", "configured_fee": 1.5, "exact_share": 0.998,
                  "other_values": [{"cbd_fee": 0.75, "trips": 1}], "status": "pass"}],
    }
    path = data_dir / "agg" / "validation_summary.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary))


def example(rel: str):
    return json.loads((SITE_CONTRACTS / mock.example_name(rel)).read_text())


def load_all(out: Path) -> dict[str, object]:
    return {path.relative_to(out).as_posix(): json.loads(path.read_text())
            for path in sorted(out.rglob("*")) if path.is_file()}


@pytest.fixture(scope="module")
def site(tmp_path_factory):
    """``python -m pipeline.publish --dev`` once on the factory set; every file loaded, and the
    metrics it ran."""
    data = tmp_path_factory.mktemp("data")
    out = tmp_path_factory.mktemp("site_data")
    calls = []
    with pytest.MonkeyPatch.context() as mp:
        mp.setenv("NYC_DATA_DIR", str(data))
        run = metrics.run
        mp.setattr(metrics, "run", lambda name, **params: calls.append(name) or run(name, **params))
        write_fixture(data)
        publish.main(["--dev", "--out", str(out)])
    return {"out": out, "files": load_all(out), "calls": calls}


# --- contract and budgets --------------------------------------------------------

def test_writes_every_contract_file(site):
    files = site["files"]
    assert len(files) == len(mock.EXAMPLES) - 2 + 4 + 263      # companies and zones patterns expand
    for rel, data in files.items():
        assert_matches_contract(data, example(rel), rel)
    assert not (site["out"] / "zones" / "264.json").exists()
    assert not (site["out"] / "zones" / "0.json").exists()


def test_every_file_carries_the_envelope(site):
    for rel, data in site["files"].items():
        if rel == "taxi_zones.geojson":
            continue
        assert data["as_of_month"] == "2026-08", rel
        assert data["validated"] is False, rel
        assert re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", data["generated_at"]), rel


def test_routes_fit_their_budgets(site):
    assert budget_problems(site["out"]) == []


def test_busiest_zone_file_fits_its_cap(data_dir, tmp_path):
    """Five modes above 10% in all 168 hours: the heatmap's worst case still fits 50 KB."""
    write_fixture(data_dir, busy=True)
    publish.publish(tmp_path, dev=True)
    zone = json.loads((tmp_path / "zones" / f"{BUSY_ZONE}.json").read_text())
    assert len(zone["hour_heatmap"]) == 5 * 168
    assert (tmp_path / "zones" / f"{BUSY_ZONE}.json").stat().st_size < 50_000
    assert budget_problems(tmp_path) == []


def test_tiles_and_events_come_from_config(site):
    files = site["files"]
    assert files["tiles.json"]["tiles"] == yaml.safe_load((SITE_CONTRACTS / "tiles.yaml").read_text())
    periods = common.load_yaml("periods.yaml")
    assert [(e["id"], e["date"]) for e in files["events.json"]["events"]] == [
        ("congestion_pricing_start", str(periods["congestion_pricing_start"])),
        ("driver_pay_rise", str(periods["driver_pay_rise"]))]


def test_zone_map_is_copied(site, tmp_path):
    copied = site["files"]["taxi_zones.geojson"]
    assert copied["type"] == "FeatureCollection" and len(copied["features"]) == 263


def test_metrics_run_through_the_runner(site):
    """Every value comes from metrics.run, L10's five metrics included."""
    assert L10_METRICS <= set(site["calls"])
    assert set(site["calls"]) <= set(metrics.available())


def test_downloads_list_the_published_sizes(site):
    for row in site["files"]["quality.json"]["downloads"]:
        assert row["bytes"] == (site["out"] / row["file"]).stat().st_size


# --- values and findings worked out by hand ----------------------------------------

def test_every_question_has_a_finding(site):
    found = site["files"]["home.json"]["findings"]
    assert [f["question"] for f in found] == [f"Q{n}" for n in range(1, 16)]
    assert {f["question"] for f in found if f["featured"]} == {"Q1", "Q2", "Q5", "Q9"}
    for f in found:
        assert f["text"] and f["page"] == findings.QUESTIONS[f["question"]][0]


HAND_WORKED = {
    # Pickups in Aug 2026: 3,350, of which ride-hail 2,230 → 66.6% ("67%"). Aug 2025: 2,230 of 3,400 →
    # 65.6%, so +0.98 pts ("+1.0 pts"). Zones with 100+ trips both years: 7, 132, 161, 236; ride-hail
    # share rose only in zone 7 (300 of 600 → 400 of 600).
    "Q1": "Ride-hail apps carried 67% of NYC trips in Aug 2026 (+1.0 pts on a year earlier), and their share of "
          "pickups rose in 1 of 4 zones",
    # All modes, core list. Weekly treated growth ÷ control growth − 1: W10 (900 + 980) ÷ 2,000 − 1 =
    # −0.06, W11 −0.11, W12 −0.01. Median −0.06; p10 −0.11 + 0.2 × 0.05 = −0.10; p90 −0.06 + 0.8 × 0.05
    # = −0.02. Uber's weeks −0.10, −0.20, 0 (median −0.10) outweigh yellow's −0.02.
    "Q2": "Congestion pricing had an estimated effect of −6.0% on trips touching the zone (weekly range −10.0% to "
          "−2.0%); among companies it was largest for Uber, at −10.0%",
    # Ride-hail is Uber alone here. Fare per mile: treated 19,503 ÷ 17,730 = 1.10 against control 1.00 → +10%.
    # Driver share: 13,120 ÷ 19,503 against 13,120 ÷ 17,730 → 17,730 ÷ 19,503 − 1 = −9.09% ("−9.1%").
    "Q3": "For ride-hail trips touching the zone, congestion pricing had an estimated effect of +10.0% on fare per "
          "mile and −9.1% on the driver share of the base fare",
    # Lyft beats Uber only in zone 236 (400 against 300); a year earlier in no zone.
    "Q4": "Lyft had a bigger share of pickups than Uber in 1 zone in Aug 2026, up from 0 a year earlier",
    # Pay per hour with a passenger: 1,461.18 ÷ (117,600 s ÷ 3,600) = $44.73 in Aug 2025, against
    # 1,391.60 ÷ 32.67 h = $42.60 in Jul 2025: +5.0%. Fare per mile is the default in both months.
    "Q6": "Ride-hail drivers earned $44.73 per hour with a passenger in Aug 2025, the month the minimum-pay rise "
          "began, +5.0% on Jul 2025; fare per mile held steady over the same months",
    # City-wide median $3.35/mile. The only zone × company cell with 5,000+ trips is Uber in zone 161:
    # 9.0 ÷ 2.0 = 4.5.
    "Q7": "Riders paid a median $3.35/mile in Aug 2026; fares per mile varied most for Uber trips from Midtown "
          "Center, where the 90th percentile was 4.5× the 10th",
    # City-wide medians 240 s and 270 s; the longest zone median is Lyft's 600 s in zone 236.
    "Q8": "Uber riders waited a median 4.0 min from request to pickup in Aug 2026, Lyft riders 4.5 min; the "
          "longest median wait was 10.0 min, for Lyft riders in Upper East Side North",
    # Airport trips in Aug 2026: Uber 60 + 50 + 30 = 140 of 200 (70%). To Manhattan from JFK: rider
    # totals 3,200 + 1,400 over 40 + 20 trips = $76.67. Hour 15 has 150 trips, hour 7 has 50.
    "Q9": "Uber carried 70% of trips to and from JFK and LaGuardia in Aug 2026; the mean fare to Manhattan was "
          "$76.67 before tip, and trips peaked at 3 pm",
    # Yellow leads zone 132 (500 of 800). A year earlier: 132 (400 of 800) and zone 2 (70 of 100).
    "Q10": "Yellow cabs carried more pickups than any other mode in 1 zone in Aug 2026, down from 2 a year earlier",
    # Fees: 1,500 + 600 + 750 + 75 = $2,925 against 2,500 a year earlier (+17.0%); Uber the most.
    "Q14": "Trips were charged $2,925 in congestion fees in Aug 2026 (+17.0% on a year earlier); Uber trips paid "
           "the most, $1,500",
    # TLC-reported, defaults: 650,000 ÷ (58,000 × 7.2) = 1.5565 trips per hour worked.
    "Q15": "TLC reports that ride-hail vehicles made 1.56 trips/hour worked in Aug 2026, on the road 7.2 hours a "
           "day, with 70,000 drivers active",
}


@pytest.mark.parametrize("question", sorted(HAND_WORKED, key=lambda q: int(q[1:])))
def test_findings_worked_by_hand(site, question):
    found = {f["question"]: f["text"] for f in site["files"]["home.json"]["findings"]}
    assert found[question] == HAND_WORKED[question]


def test_home_tiles_worked_by_hand(site):
    home = site["files"]["home.json"]
    # 3,350 trips ÷ 31 days = 108.06 a day; 3,400 ÷ 31 a year earlier → 3,350 ÷ 3,400 − 1 = −1.47%.
    # Driver share is 1,391.60 ÷ 1,813 in Aug 2026 and 1,461.18 ÷ 1,813 in Aug 2025, so the platform
    # keeps 0.2324 against 0.1941.
    assert home["tiles"] == {"trips_per_day": 108.1, "rh_share": 0.6657, "platform_share": 0.2324,
                             "cbd_fees_last_month": 2925.0}
    assert home["yoy"] == {"trips_per_day": -0.0147, "rh_share": 0.0098, "platform_share": 0.0384,
                           "cbd_fees_last_month": 0.17}
    assert home["title"] == "Ride-hail apps carried 67% of NYC trips in Aug 2026"


def test_zone_counts(site):
    index = site["files"]["zones/index.json"]
    assert index["tiles"] == {"zones_yellow_leads": 1, "zones_lyft_beats_uber": 1, "zones_rh_share_up": 1}
    assert index["yoy"] == {"zones_yellow_leads": -1, "zones_lyft_beats_uber": 1, "zones_rh_share_up": None}
    assert [row["zone"] for row in index["rows"]] == list(range(1, 264))
    uber, yellow = site["files"]["companies/uber.json"], site["files"]["companies/yellow.json"]
    assert (uber["lyft_vs_uber"]["zones_lyft_ahead"], uber["lyft_vs_uber"]["zones_lyft_ahead_prior_year"]) == (1, 0)
    assert yellow["lyft_vs_uber"] is None
    assert yellow["not_reported"] == ["driver_share", "wav", "shared"] and uber["not_reported"] == []
    assert yellow["tiles"]["driver_share"] is None


def test_thin_and_empty_zones_give_nulls(site):
    thin = site["files"]["zones/2.json"]
    assert thin["flags"]["thin"] is True
    assert thin["title"] == "Jamaica Bay had 50 pickups in Aug 2026, too few to profile"
    assert (thin["tiles"]["wait_p50"], thin["tiles"]["wait_p90"]) == (None, None)
    assert thin["waits"] == {"monthly": [], "by_hour": []}
    empty = site["files"]["zones/50.json"]
    assert empty["tiles"]["trips_per_day"] == 0.0 and empty["tiles"]["rh_share"] is None
    assert empty["title"] == "No pickups were recorded in Zone 50 in Aug 2026"
    assert empty["hour_heatmap"] == [] and empty["top_destinations"] == []
    busy = site["files"]["zones/161.json"]
    assert busy["flags"] == {"cbd": True, "cbd_borderline": False, "airport": None, "thin": False}
    assert busy["tiles"]["top_destination"] == "Upper East Side North"
    assert site["files"]["zones/132.json"]["flags"]["airport"] == "JFK"


# --- language rules (CLAUDE.md) -------------------------------------------------

def generated_text(files: dict) -> list[tuple[str, str]]:
    texts = []
    for rel, data in files.items():
        if not isinstance(data, dict):
            continue
        if data.get("title"):
            texts.append((rel, data["title"]))
        texts += [(f"{rel} {key}", text) for key, text in (data.get("subtitles") or {}).items() if text]
        texts += [(f"{rel} {f['question']}", f["text"]) for f in data.get("findings", [])]
    return texts


def test_language_rules(site):
    texts = generated_text(site["files"])
    assert len(texts) > 263 * 3          # a title and subtitles on every zone page, and more
    for where, text in texts:
        lower = text.lower()
        assert not re.search(r"\bcaus", lower), where
        if re.search(r"\btip(s|ped)\b", lower) and re.search(r"\bcabs?\b", lower):   # tipping, not "before tip"
            assert "card-only" in lower, where
        if "per hour" in lower:
            assert "per hour with a passenger" in lower, where
        if re.search(r"\beffects?\b", lower):
            assert not re.search(r"(?<!estimated )\beffects?\b", lower), where


# --- the gate, the CLI and stale files ----------------------------------------------

def test_refuses_without_a_validation_summary(data_dir, tmp_path, capsys):
    write_fixture(data_dir)
    with pytest.raises(SystemExit) as exit_info:
        publish.main(["--out", str(tmp_path / "out")])
    assert exit_info.value.code == 1
    assert "validation_summary.json not found" in capsys.readouterr().err
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("status, months, problem", [
    ("fail", ("2025-08", "2026-08"), "not 'pass'"),
    ("pass", ("2025-08",), "did not check 2026-08"),
])
def test_refuses_a_failed_or_stale_validation(data_dir, tmp_path, status, months, problem):
    write_fixture(data_dir)
    write_summary(data_dir, status, months)
    with pytest.raises(publish.PublishError, match=problem):
        publish.publish(tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_publishes_validated_data_after_a_passing_gate(data_dir, tmp_path):
    write_fixture(data_dir)
    write_summary(data_dir)
    publish.publish(tmp_path)
    home = json.loads((tmp_path / "home.json").read_text())
    quality = json.loads((tmp_path / "quality.json").read_text())
    assert home["validated"] is True
    assert quality["validation"]["status"] == "pass"
    assert_matches_contract(quality, example("quality.json"), "quality.json")


def test_refuses_without_the_zone_map(data_dir, tmp_path):
    write_fixture(data_dir)
    (data_dir / "ref" / "taxi_zones.simplified.geojson").unlink()
    with pytest.raises(publish.PublishError, match="zone map"):
        publish.publish(tmp_path, dev=True)


def test_removes_files_the_contract_no_longer_lists(data_dir, tmp_path):
    write_fixture(data_dir)
    for stale in ("zones/264.json", "old.json", "companies/other_hv.json"):
        (tmp_path / stale).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / stale).write_text("{}")
    (tmp_path / "README.md").write_text("not ours")
    publish.publish(tmp_path, dev=True)
    assert not (tmp_path / "zones" / "264.json").exists()
    assert not (tmp_path / "old.json").exists() and not (tmp_path / "companies" / "other_hv.json").exists()
    assert (tmp_path / "README.md").exists()
    assert (tmp_path / "zones" / "263.json").exists()
