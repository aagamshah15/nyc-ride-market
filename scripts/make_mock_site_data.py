"""Write contract-shaped mock files to site/src/data/, marked ``as_of_month: "MOCK"``.

Run by ``make site-mock``. Mocks let the site lanes build pages before real data
exists. They must never be committed or deployed: tests/test_contracts.py fails on a
tracked mock file, and deploy refuses ``validated: false``.

``--examples`` rewrites contracts/site/*.example.json instead: the same files, pretty
printed, with every list trimmed to three items. Those examples are the site-data
contracts (contracts/README.md), so a contract change is a change here plus a
regenerate.

Lane L01 · docs/lanes/L01-contracts.md
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import yaml  # noqa: E402

from pipeline import common  # noqa: E402

CONTRACTS_SITE = REPO_ROOT / "contracts" / "site"
MOCK = "MOCK"
SEED = 20261024
EXAMPLE_LIST_LEN = 3
EXAMPLE_GENERATED_AT = "2026-10-24T00:00:00Z"
MOCK_FROM, MOCK_TO = "2024-01", "2026-08"   # fixed, so examples don't move with config

MODES = ("uber", "lyft", "other_hv", "yellow", "green")
COMPANIES = ("uber", "lyft", "yellow", "green")
RIDE_HAIL = ("uber", "lyft")
NAMES = {"uber": "Uber", "lyft": "Lyft", "other_hv": "Other ride-hail",
         "yellow": "Yellow cab", "green": "Green cab"}
BOROUGHS = ("Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island")
AIRPORTS = {1: "EWR", 132: "JFK", 138: "LGA"}
ZONES = range(1, 264)
EFFECT_MODES = ("uber", "lyft", "yellow", "green", "ride_hail", "all")
HEATMAP_MIN_SHARE = 0.10   # contracts/README.md §1 Size
MULTIPOLYGON_ZONE = 2      # Jamaica Bay: one of the 12 real zones that are MultiPolygons

# Published data file → its example in contracts/site/.
EXAMPLES = {
    "home.json": "home.example.json",
    "share_monthly.json": "share_monthly.example.json",
    "events.json": "events.example.json",
    "tiles.json": "tiles.example.json",
    "companies/{company}.json": "companies.example.json",
    "zones/index.json": "zones_index.example.json",
    "zones/{zone}.json": "zone.example.json",
    "airports.json": "airports.example.json",
    "congestion.json": "congestion.example.json",
    "drivers.json": "drivers.example.json",
    "prices.json": "prices.example.json",
    "quality.json": "quality.example.json",
    "taxi_zones.geojson": "taxi_zones.example.geojson",
}
EXAMPLE_PARAMS = {"company": "uber", "zone": "230"}


def example_name(data_path: str) -> str:
    """Example file for a published path, e.g. ``zones/17.json`` → ``zone.example.json``."""
    if data_path.startswith("companies/"):
        return EXAMPLES["companies/{company}.json"]
    if data_path.startswith("zones/") and data_path != "zones/index.json":
        return EXAMPLES["zones/{zone}.json"]
    return EXAMPLES[data_path]


# --- small helpers -----------------------------------------------------------

def _r(x: float | None, n: int) -> float | None:
    return None if x is None else round(x, n)


def _month_iso(m: str) -> str:
    return f"{m}-01"


def _days(m: str) -> int:
    d = common.parse_month(m)
    following = date(d.year + (d.month == 12), d.month % 12 + 1, 1)
    return (following - d).days


def _prior_year(m: str) -> str:
    year, month = m.split("-")
    return f"{int(year) - 1}-{month}"


def _label(m: str) -> str:
    return common.parse_month(m).strftime("%b %Y")


def _pct(x: float) -> str:
    return f"{x * 100:.0f}%" if abs(x) >= 0.1 else f"{x * 100:.1f}%"


def _week_start(year: int, week: int) -> str:
    return date.fromisocalendar(year, week, 1).isoformat()


def _rel(now: float | None, before: float | None) -> float | None:
    if now is None or not before:
        return None
    return _r(now / before - 1, 4)


def _pts(now: float | None, before: float | None) -> float | None:
    if now is None or before is None:
        return None
    return _r(now - before, 4)


def _normalise(shares: dict[str, float]) -> dict[str, float]:
    total = sum(shares.values())
    return {k: v / total for k, v in shares.items()}


def trim(obj, n: int = EXAMPLE_LIST_LEN):
    """Copy of ``obj`` with every list cut to its first ``n`` items."""
    if isinstance(obj, dict):
        return {k: trim(v, n) for k, v in obj.items()}
    if isinstance(obj, list):
        return [trim(v, n) for v in obj[:n]]
    return obj


def dumps_min(obj) -> str:
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


def dumps_pretty(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


# --- the mock market ---------------------------------------------------------

class MockSite:
    def __init__(self, seed: int = SEED, generated_at: str | None = None):
        self.rng = random.Random(seed)
        self.months = common.month_range(MOCK_FROM, MOCK_TO)
        self.latest = self.months[-1]
        self.prior = _prior_year(self.latest)
        self.generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.periods = common.load_yaml("periods.yaml")
        self.tile_registry = yaml.safe_load((CONTRACTS_SITE / "tiles.yaml").read_text())
        self.zones = {z: self._zone(z) for z in ZONES}
        self.share = {m: self._mode_shares(i) for i, m in enumerate(self.months)}
        self.tpd = {m: 780_000 * (1 + 0.06 * math.sin(i / 12 * 2 * math.pi)) * (1 + 0.002 * i)
                    for i, m in enumerate(self.months)}

    def jitter(self, x: float, spread: float = 0.04) -> float:
        return x * (1 + self.rng.uniform(-spread, spread))

    def env(self) -> dict:
        return {"as_of_month": MOCK, "generated_at": self.generated_at, "validated": False}

    def _mode_shares(self, i: int) -> dict[str, float]:
        base = {"uber": 0.57 - 0.0006 * i, "lyft": 0.20 + 0.0008 * i, "other_hv": 0.002,
                "yellow": 0.21 - 0.0003 * i, "green": 0.018}
        return _normalise({k: self.jitter(v, 0.01) for k, v in base.items()})

    def _zone(self, z: int) -> dict:
        airport = AIRPORTS.get(z)
        borough = "EWR" if z == 1 else "Queens" if airport else BOROUGHS[z % 5]
        manhattan = borough == "Manhattan"
        thin = z % 37 == 0
        if manhattan:
            base = {"uber": 0.45, "lyft": 0.17, "other_hv": 0.002, "yellow": 0.36, "green": 0.018}
        elif airport:
            base = {"uber": 0.40, "lyft": 0.15, "other_hv": 0.002, "yellow": 0.40, "green": 0.048}
        else:   # outer zones: four modes above 5%, the zone-file size worst case
            base = {"uber": 0.58, "lyft": 0.24, "other_hv": 0.002, "yellow": 0.07, "green": 0.108}
        tpd = 12 if thin else 9_000 if airport else 7_000 if manhattan else 1_600
        return {
            "zone": z,
            "name": f"{airport} Airport" if airport else f"Mock zone {z}",
            "borough": borough,
            "cbd": manhattan and z < 150,
            "borderline": z in (140, 145),
            "airport": airport,
            "thin": thin,
            "tpd": self.jitter(tpd, 0.2),
            "shares": _normalise({k: self.jitter(v, 0.15) for k, v in base.items()}),
        }

    def fees(self, m: str, mode: str) -> float:
        if m < "2025-01":
            return 0.0
        fee = self.periods["fees"]["cbd_fee_taxi" if mode in ("yellow", "green") else "cbd_fee_hvfhv"]
        cbd_fraction = 0.6 if mode in ("yellow", "green") else 0.28
        return self.tpd[m] * self.share[m][mode] * _days(m) * cbd_fraction * fee

    def rh_share(self, m: str) -> float:
        return sum(self.share[m][k] for k in ("uber", "lyft", "other_hv"))

    def driver_share(self, mode: str, i: int) -> float:
        base = {"uber": 0.71, "lyft": 0.73, "ride_hail": 0.715}[mode]
        return base + 0.0005 * i + self.rng.uniform(-0.005, 0.005)

    def fpm(self, mode: str, i: int = 0) -> float:
        base = {"uber": 2.95, "lyft": 2.80, "other_hv": 2.7, "yellow": 3.40, "green": 3.05,
                "ride_hail": 2.90, "taxi": 3.35, "all": 3.02}[mode]
        return self.jitter(base * (1 + 0.003 * i), 0.02)

    # --- files ---------------------------------------------------------------

    def events(self) -> dict:
        return {**self.env(), "events": [
            {"id": "congestion_pricing_start", "date": str(self.periods["congestion_pricing_start"]),
             "label": "Congestion pricing starts"},
            {"id": "driver_pay_rise", "date": str(self.periods["driver_pay_rise"]),
             "label": "Driver minimum pay rises 5%"},
        ]}

    def tiles(self) -> dict:
        return {**self.env(), "tiles": self.tile_registry}

    def share_monthly(self) -> dict:
        rows = [{"month": _month_iso(m), "mode": mode,
                 "trips_per_day": _r(self.tpd[m] * self.share[m][mode], 1),
                 "share": _r(self.share[m][mode], 4)}
                for m in self.months for mode in MODES]
        return {**self.env(), "rows": rows}

    def home(self) -> dict:
        m, p = self.latest, self.prior
        n = len(self.months)
        fees_now = sum(self.fees(m, mode) for mode in MODES)
        fees_before = sum(self.fees(p, mode) for mode in MODES)
        platform_now = 1 - self.driver_share("ride_hail", n - 1)
        platform_before = 1 - self.driver_share("ride_hail", n - 13)
        tiles = {"trips_per_day": _r(self.tpd[m], 1), "rh_share": _r(self.rh_share(m), 4),
                 "platform_share": _r(platform_now, 4), "cbd_fees_last_month": _r(fees_now, 2)}
        yoy = {"trips_per_day": _rel(self.tpd[m], self.tpd[p]),
               "rh_share": _pts(self.rh_share(m), self.rh_share(p)),
               "platform_share": _pts(platform_now, platform_before),
               "cbd_fees_last_month": _rel(fees_now, fees_before)}
        pages = {"Q1": "/zones", "Q2": "/congestion-pricing", "Q3": "/congestion-pricing",
                 "Q4": "/companies/lyft", "Q5": "/drivers", "Q6": "/drivers", "Q7": "/prices",
                 "Q8": "/zones", "Q9": "/airports", "Q10": "/zones", "Q11": "/companies/uber",
                 "Q12": "/companies/uber", "Q13": "/companies/yellow",
                 "Q14": "/congestion-pricing", "Q15": "/drivers"}
        findings = [{"question": q, "text": f"MOCK finding for {q}, {_label(m)}",
                     "value": _r(self.rng.uniform(0.05, 0.9), 4), "unit": "share", "page": page,
                     "featured": q in ("Q1", "Q2", "Q5", "Q9")}
                    for q, page in pages.items()]
        return {**self.env(),
                "title": f"MOCK: ride-hail apps carried {_pct(self.rh_share(m))} of NYC trips in {_label(m)}",
                "subtitles": {"share_trend": "MOCK: Lyft's share has edged up since Jan 2024"},
                "tiles": tiles, "yoy": yoy, "findings": findings}

    def company(self, mode: str) -> dict:
        m, p, n = self.latest, self.prior, len(self.months)
        taxi = mode in ("yellow", "green")
        tip = {"uber": 0.07, "lyft": 0.09, "yellow": 0.18, "green": 0.12}
        fpm_now = self.fpm(mode, n - 1)
        fpm_before = self.fpm(mode, n - 13)
        ds_now = None if taxi else self.driver_share(mode, n - 1)
        ds_before = None if taxi else self.driver_share(mode, n - 13)
        tiles = {"trips_per_day": _r(self.tpd[m] * self.share[m][mode], 1),
                 "share": _r(self.share[m][mode], 4), "fpm_median": _r(fpm_now, 3),
                 "driver_share": _r(ds_now, 4), "tip_rate": _r(tip[mode], 4)}
        yoy = {"trips_per_day": _rel(self.tpd[m] * self.share[m][mode], self.tpd[p] * self.share[p][mode]),
               "share": _pts(self.share[m][mode], self.share[p][mode]),
               "fpm_median": _rel(fpm_now, fpm_before), "driver_share": _pts(ds_now, ds_before),
               "tip_rate": _r(self.rng.uniform(-0.01, 0.01), 4)}

        def match_rows(base_rate: float, volume: int) -> list[dict]:
            rows = []
            for i, month in enumerate(self.months):
                for rh in RIDE_HAIL:
                    requests = int(self.jitter(volume * (1 + 0.01 * i), 0.1))
                    matched = int(requests * min(0.99, self.jitter(base_rate, 0.05)))
                    rows.append({"month": _month_iso(month), "mode": rh, "requests": requests,
                                 "matched": matched, "match_rate": _r(matched / requests, 4)})
            return rows

        compare_values = {
            "trips_per_day": ("count", lambda c: _r(self.tpd[m] * self.share[m][c], 1)),
            "share": ("share", lambda c: _r(self.share[m][c], 4)),
            "fpm_median": ("usd_per_mile", lambda c: _r(self.fpm(c, n - 1), 3)),
            "fare_per_min": ("usd_per_minute", lambda c: _r(self.jitter(1.10), 3)),
            "driver_share": ("share", lambda c: None if c in ("yellow", "green") else _r(self.driver_share(c, n - 1), 4)),
            "tip_rate": ("share", lambda c: _r(tip[c], 4)),
            "wait_p50": ("seconds", lambda c: None if c in ("yellow", "green") else _r(self.jitter(290), 0)),
            "wav_match_rate": ("share", lambda c: None if c in ("yellow", "green") else _r(self.jitter(0.86), 4)),
            "shared_match_rate": ("share", lambda c: None if c in ("yellow", "green") else _r(self.jitter(0.41), 4)),
        }
        compare = [{"metric": metric, "unit": unit, **{c: value(c) for c in COMPANIES}}
                   for metric, (unit, value) in compare_values.items()]

        lyft_vs_uber = None
        if not taxi:
            by_zone = []
            for z, info in self.zones.items():
                lyft, uber = info["shares"]["lyft"], info["shares"]["uber"]
                if z % 11 == 0:
                    lyft, uber = uber, lyft   # a few zones where Lyft leads
                gap_prior = lyft - uber + self.rng.uniform(-0.02, 0.01)
                by_zone.append({"zone": z, "name": info["name"], "lyft_share": _r(lyft, 4),
                                "uber_share": _r(uber, 4), "gap": _r(lyft - uber, 4),
                                "gap_change": _r((lyft - uber) - gap_prior, 4)})
            ahead = sum(1 for row in by_zone if row["gap"] > 0)
            lyft_vs_uber = {"zones_lyft_ahead": ahead, "zones_lyft_ahead_prior_year": max(0, ahead - 4),
                            "by_zone": by_zone}

        return {
            **self.env(), "mode": mode, "name": NAMES[mode],
            "title": f"MOCK: {NAMES[mode]} carried {_pct(self.share[m][mode])} of NYC trips in {_label(m)}",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in
                          ("share_trend", "fpm_dist", "tip_rate", "wav", "shared", "compare", "lyft_vs_uber")},
            "tiles": tiles, "yoy": yoy,
            "not_reported": ["driver_share", "wav", "shared"] if taxi else [],
            "share_trend": [{"month": _month_iso(month), "mode": md, "share": _r(self.share[month][md], 4),
                             "trips_per_day": _r(self.tpd[month] * self.share[month][md], 1)}
                            for month in self.months for md in MODES],
            "fpm_dist": [{"month": _month_iso(month), "mode": c,
                          **(lambda mid: {"fpm_p10": _r(mid * 0.62, 3), "fpm_p50": _r(mid, 3),
                                          "fpm_p90": _r(mid * 1.75, 3), "fpmin_p50": _r(mid * 0.38, 3)})(self.fpm(c, i))}
                         for i, month in enumerate(self.months) for c in COMPANIES],
            "tip_rate": [{"month": _month_iso(month), "mode": c, "tip_rate": _r(self.jitter(tip[c], 0.05), 4),
                          "card_only": c in ("yellow", "green")}
                         for month in self.months for c in COMPANIES],
            "wav": match_rows(0.86, 30_000),
            "shared": match_rows(0.41, 120_000),
            "compare": compare,
            "lyft_vs_uber": lyft_vs_uber,
        }

    def zones_index(self) -> dict:
        rows = []
        for z, info in self.zones.items():
            rh = sum(info["shares"][k] for k in ("uber", "lyft", "other_hv"))
            rows.append({
                "zone": z, "name": info["name"], "borough": info["borough"],
                "trips_per_day": _r(info["tpd"], 1), "rh_share": _r(rh, 4),
                "yellow_share": _r(info["shares"]["yellow"], 4),
                "wait_p50": None if info["thin"] else _r(self.jitter(300, 0.3), 0),
                "share_change_yoy": _r(self.rng.uniform(-0.03, 0.04), 4),
                "yellow_share_change_yoy": _r(self.rng.uniform(-0.04, 0.01), 4),
                "top_mode": max(info["shares"], key=info["shares"].get),
                "cbd": info["cbd"], "thin": info["thin"],
            })
        yellow_leads = sum(1 for row in rows if row["top_mode"] == "yellow")
        return {**self.env(),
                "title": f"MOCK: yellow cabs still lead in {yellow_leads} zones",
                "subtitles": {"level_map": "MOCK subtitle for level_map",
                              "change_map": "MOCK subtitle for change_map",
                              "yellow_map": "MOCK subtitle for yellow_map",
                              "table": "MOCK subtitle for table"},
                "tiles": {"zones_yellow_leads": yellow_leads, "zones_lyft_beats_uber": 24,
                          "zones_rh_share_up": sum(1 for row in rows if row["share_change_yoy"] > 0)},
                "yoy": {"zones_yellow_leads": -3, "zones_lyft_beats_uber": 4, "zones_rh_share_up": None},
                "rows": rows}

    def zone(self, z: int) -> dict:
        info = self.zones[z]
        thin = info["thin"]
        shares = info["shares"]
        rh = sum(shares[k] for k in ("uber", "lyft", "other_hv"))
        heat_modes = [md for md in MODES if shares[md] >= HEATMAP_MIN_SHARE]
        weekly = info["tpd"] * 7

        def hour_weight(h: int) -> float:
            hour = h % 24
            return 0.2 + math.exp(-((hour - 8) ** 2) / 8) + 1.2 * math.exp(-((hour - 18) ** 2) / 10)

        weights = [hour_weight(h) for h in range(168)]
        total_weight = sum(weights)
        destinations = self.rng.sample([d for d in ZONES if d != z], 10)
        dest_shares = sorted((self.rng.uniform(0.01, 0.08) for _ in destinations), reverse=True)
        top_dest = [{"do_zone": d, "name": self.zones[d]["name"],
                     "trips": int(info["tpd"] * _days(self.latest) * s), "share": _r(s, 4)}
                    for d, s in zip(destinations, dest_shares)]
        wait50 = None if thin else self.jitter(300, 0.3)
        wait90 = None if thin else wait50 * 2.1
        return {
            **self.env(), "zone": z, "name": info["name"], "borough": info["borough"],
            "flags": {"cbd": info["cbd"], "cbd_borderline": info["borderline"],
                      "airport": info["airport"], "thin": thin},
            "title": f"MOCK: ride-hail apps carried {_pct(rh)} of pickups in {info['name']}",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in
                          ("share_trend", "hour_heatmap", "waits", "top_destinations")},
            "tiles": {"trips_per_day": _r(info["tpd"], 1), "rh_share": _r(rh, 4),
                      "wait_p50": _r(wait50, 0), "wait_p90": _r(wait90, 0),
                      "top_destination": top_dest[0]["name"]},
            "yoy": {"trips_per_day": _r(self.rng.uniform(-0.08, 0.08), 4),
                    "rh_share": _r(self.rng.uniform(-0.03, 0.03), 4),
                    "wait_p50": None if thin else _r(self.rng.uniform(-0.1, 0.1), 4),
                    "wait_p90": None if thin else _r(self.rng.uniform(-0.1, 0.1), 4),
                    "top_destination": None},
            "share_trend": [{"month": _month_iso(m), "mode": md, "share": _r(self.jitter(shares[md], 0.05), 4)}
                            for m in self.months for md in COMPANIES],
            "hour_heatmap": [{"hour_of_week": h, "mode": md,
                              "trips": _r(weekly * shares[md] * weights[h] / total_weight, 1)}
                             for md in heat_modes for h in range(168)],
            "waits": {
                "monthly": [] if thin else [
                    {"month": _month_iso(m), "mode": md, "wait_p50": _r(self.jitter(wait50, 0.1), 0),
                     "wait_p90": _r(self.jitter(wait90, 0.1), 0)}
                    for m in self.months for md in RIDE_HAIL],
                "by_hour": [] if thin else [
                    {"hour": h, "mode": md, "wait_mean": _r(self.jitter(wait50 * (1 + 0.3 * math.sin(h / 4)), 0.05), 0)}
                    for h in range(24) for md in RIDE_HAIL],
            },
            "top_destinations": top_dest,
        }

    def airports(self) -> dict:
        m = self.latest
        mix = {"uber": 0.40, "lyft": 0.15, "other_hv": 0.002, "yellow": 0.40, "green": 0.048}
        size = {"JFK": 26_000, "LGA": 19_000, "EWR": 4_000}
        split = []
        for code in ("JFK", "LGA", "EWR"):
            for direction in ("from", "to"):
                shares = _normalise({k: self.jitter(v, 0.2) for k, v in mix.items()})
                for md in MODES:
                    split.append({"airport": code, "direction": direction, "mode": md,
                                  "trips_per_day": _r(size[code] / 2 * shares[md], 1),
                                  "share": _r(shares[md], 4)})
        yellow = sum(r["trips_per_day"] for r in split if r["mode"] == "yellow")
        total = sum(r["trips_per_day"] for r in split)
        return {
            **self.env(),
            "title": f"MOCK: yellow cabs carried {_pct(yellow / total)} of airport trips in {_label(m)}",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in ("split", "share_trend", "by_hour", "fares")},
            "tiles": {"trips_per_day": _r(total, 1), "yellow_share": _r(yellow / total, 4),
                      "fare_to_manhattan_mean": _r(self.jitter(78.0), 2), "busiest_hour": 15},
            "yoy": {"trips_per_day": 0.0412, "yellow_share": -0.0123, "fare_to_manhattan_mean": 0.031,
                    "busiest_hour": None},
            "split": split,
            "share_trend": [{"month": _month_iso(mo), "airport": code, "mode": md,
                             "share": _r(self.jitter(mix[md], 0.1), 4)}
                            for mo in self.months for code in ("JFK", "LGA", "EWR") for md in MODES],
            "by_hour": [{"airport": code, "direction": direction, "hour": h, "mode": md,
                         "trips_per_day": _r(size[code] / 48 * mix[md] * (1 + 0.6 * math.sin((h - 6) / 24 * 2 * math.pi)), 1)}
                        for code in ("JFK", "LGA", "EWR") for direction in ("from", "to")
                        for h in range(24) for md in MODES],
            "fares": [{"airport": code, "mode": md, "fare_mean": _r(self.jitter(75.0, 0.15), 2),
                       "fare_base_mean": _r(self.jitter(58.0, 0.15), 2),
                       "fare_per_mile": _r(self.jitter(3.6, 0.1), 3),
                       "trips_per_day": _r(size[code] / 4 * mix[md], 1)}
                      for code in ("JFK", "LGA", "EWR") for md in MODES],
        }

    def congestion(self) -> dict:
        excluded = {3: "MLK Day is in ISO week 3 in 2024 and week 4 in 2025",
                    4: "MLK Day is in ISO week 3 in 2024 and week 4 in 2025"}
        base_effect = {"trips": -0.06, "fare_per_mile": 0.025, "driver_share": -0.004}
        metrics_for = {md: ("trips", "fare_per_mile") + (("driver_share",) if md in ("uber", "lyft", "ride_hail") else ())
                       for md in EFFECT_MODES}
        weekly_effect = []
        for zone_list in ("core", "wide"):
            shrink = 0.85 if zone_list == "wide" else 1.0
            for week in range(2, 53):
                for md in EFFECT_MODES:
                    for metric in metrics_for[md]:
                        weekly_effect.append({
                            "week_start": _week_start(2025, week), "iso_week": week, "metric": metric,
                            "mode": md, "zone_list": zone_list,
                            "effect": _r(base_effect[metric] * shrink + self.rng.gauss(0, 0.015), 4),
                            "excluded": week in excluded})
        effects = []
        for zone_list in ("core", "wide"):
            for md in EFFECT_MODES:
                for metric in metrics_for[md]:
                    values = sorted(r["effect"] for r in weekly_effect
                                    if r["zone_list"] == zone_list and r["mode"] == md
                                    and r["metric"] == metric and not r["excluded"])
                    k = len(values)
                    effects.append({"metric": metric, "mode": md, "zone_list": zone_list,
                                    "median": values[k // 2], "p10": values[k // 10],
                                    "p90": values[(9 * k) // 10], "weeks": k})
        weekly_trips = []
        for year in (2024, 2025):
            for week in range(1, 53):
                for group in ("treated", "control"):
                    for md, size in (("ride_hail", 600_000), ("taxi", 130_000), ("all", 730_000)):
                        level = size * (0.3 if group == "treated" else 0.7)
                        if year == 2025 and group == "treated" and week >= 2:
                            level *= 0.94
                        weekly_trips.append({"week_start": _week_start(year, week), "iso_year": year,
                                             "iso_week": week, "cbd_group": group, "mode": md,
                                             "trips_per_day": _r(self.jitter(level, 0.03), 1)})
        fee_months = [m for m in self.months if m >= "2025-01"]
        fees = [{"month": _month_iso(m), "mode": md, "cbd_fee": _r(self.fees(m, md), 2),
                 "trips_with_cbd_fee": int(self.fees(m, md) / self.periods["fees"][
                     "cbd_fee_taxi" if md in ("yellow", "green") else "cbd_fee_hvfhv"])}
                for m in fee_months for md in MODES]
        trips_core = next(e for e in effects if e["metric"] == "trips" and e["mode"] == "all" and e["zone_list"] == "core")
        fpm_core = next(e for e in effects if e["metric"] == "fare_per_mile" and e["mode"] == "ride_hail" and e["zone_list"] == "core")
        return {
            **self.env(),
            "title": f"MOCK: estimated effect of congestion pricing on zone trips, {trips_core['median'] * 100:+.1f}%",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in
                          ("effects", "weekly_effect", "weekly_trips", "fees", "zone_change")},
            "tiles": {"trips_effect": trips_core["median"], "fpm_effect": fpm_core["median"],
                      "fees_to_date": _r(sum(r["cbd_fee"] for r in fees), 2)},
            "yoy": {"trips_effect": None, "fpm_effect": None, "fees_to_date": None},
            "effects": effects,
            "weekly_effect": weekly_effect,
            "weekly_trips": weekly_trips,
            "fees": fees,
            "zone_change": [{"zone": z, "change": _r((-0.07 if info["cbd"] else 0.01) + self.rng.gauss(0, 0.02), 4)}
                            for z, info in self.zones.items()],
            "excluded_weeks": [{"iso_year": 2025, "iso_week": w, "reason": reason} for w, reason in excluded.items()],
        }

    def drivers(self) -> dict:
        n = len(self.months)
        tlc_months = self.months[:-1]   # the indicators file runs a month behind the trip files
        tlc_latest = tlc_months[-1]
        classes = {"FHV - High Volume": (1.55, 70_000, 64_000, 7.1), "Yellow": (1.85, 9_200, 6_900, 9.4),
                   "Green": (1.05, 900, 700, 6.0)}
        hours = [{"month": _month_iso(m), "license_class": lc,
                  "trips_per_hour_worked": _r(self.jitter(tph, 0.03), 3),
                  "active_drivers": int(self.jitter(drivers, 0.03)),
                  "vehicles_per_day": int(self.jitter(vehicles, 0.03)),
                  "hours_per_day_per_vehicle": _r(self.jitter(hrs, 0.03), 2)}
                 for m in tlc_months for lc, (tph, drivers, vehicles, hrs) in classes.items()]
        hv_now = next(r for r in hours if r["month"] == _month_iso(tlc_latest) and r["license_class"] == "FHV - High Volume")
        hv_before = next(r for r in hours if r["month"] == _month_iso(_prior_year(tlc_latest))
                         and r["license_class"] == "FHV - High Volume")
        event = []
        for year in (2024, 2025):
            for offset in range(-12, 13):
                bump = 1.05 if year == 2025 and offset > 0 else 1.0
                for md in ("uber", "lyft", "ride_hail"):
                    event.append({"year": year, "week_offset": offset,
                                  "week_start": _week_start(year, 31 + offset), "mode": md,
                                  "pay_per_mile": _r(self.jitter(1.95 * bump, 0.02), 3),
                                  "pay_per_min": _r(self.jitter(0.62 * bump, 0.02), 3),
                                  "fare_per_mile": _r(self.jitter(2.90 * (1.01 if bump > 1 else 1), 0.02), 3),
                                  "transition": offset == 0})
        pph_now, pph_before = self.jitter(38.5), self.jitter(36.9)
        ds_now = self.driver_share("ride_hail", n - 1)
        ds_before = self.driver_share("ride_hail", n - 13)
        return {
            **self.env(),
            "title": f"MOCK: drivers kept {_pct(ds_now)} of ride-hail fares in {_label(self.latest)}",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in
                          ("driver_share_trend", "pay_per_hour_trend", "event_study", "hours")},
            "tiles": {"pay_per_hour": _r(pph_now, 2), "driver_share": _r(ds_now, 4),
                      "trips_per_hour_worked": hv_now["trips_per_hour_worked"],
                      "active_drivers": hv_now["active_drivers"]},
            "yoy": {"pay_per_hour": _rel(pph_now, pph_before), "driver_share": _pts(ds_now, ds_before),
                    "trips_per_hour_worked": _rel(hv_now["trips_per_hour_worked"], hv_before["trips_per_hour_worked"]),
                    "active_drivers": _rel(hv_now["active_drivers"], hv_before["active_drivers"])},
            "tlc_as_of_month": tlc_latest,
            "driver_share_trend": [{"month": _month_iso(m), "mode": md,
                                    "driver_share": _r(ds, 4), "platform_share": _r(1 - ds, 4)}
                                   for i, m in enumerate(self.months) for md in ("uber", "lyft", "ride_hail")
                                   for ds in [self.driver_share(md, i)]],
            "pay_per_hour_trend": [{"month": _month_iso(m), "mode": md,
                                    "pay_per_hour": _r(self.jitter(35 + 0.12 * i, 0.02), 2)}
                                   for i, m in enumerate(self.months) for md in ("uber", "lyft", "ride_hail")],
            "event_study": event,
            "hours": hours,
        }

    def prices(self) -> dict:
        n = len(self.months)
        modes = COMPANIES + ("all",)

        def hour_factor(h: int) -> float:
            hour = h % 24
            return 1 + 0.12 * math.exp(-((hour - 18) ** 2) / 6) + 0.08 * math.exp(-((hour - 8) ** 2) / 4) - 0.06 * (2 <= hour <= 5)

        by_hour = [{"hour_of_week": h, "mode": md, "fare_per_mile": _r(self.fpm(md) * hour_factor(h), 3),
                    "fare_per_min": _r(self.fpm(md) * 0.38 * hour_factor(h), 3)}
                   for h in range(168) for md in modes]
        all_rows = [r for r in by_hour if r["mode"] == "all"]
        cheapest = min(all_rows, key=lambda r: r["fare_per_mile"])["hour_of_week"]
        dearest = max(all_rows, key=lambda r: r["fare_per_mile"])["hour_of_week"]
        volatility = []
        for z, info in self.zones.items():
            if info["thin"]:
                continue
            for md in COMPANIES:
                trips = int(info["tpd"] * info["shares"][md] * _days(self.latest))
                if trips >= 100:
                    volatility.append({"zone": z, "mode": md, "volatility": _r(self.jitter(2.6, 0.25), 3),
                                       "fpm_p50": _r(self.fpm(md), 3), "n": trips})
        fpm_now, fpm_before = self.fpm("all", n - 1), self.fpm("all", n - 13)
        return {
            **self.env(),
            "title": f"MOCK: riders paid a median ${fpm_now:.2f} a mile in {_label(self.latest)}",
            "subtitles": {key: f"MOCK subtitle for {key}" for key in
                          ("fpm_by_mode", "fpm_by_hour", "fpm_by_borough", "volatility_by_zone")},
            "tiles": {"fpm_median": _r(fpm_now, 3), "volatility": _r(self.jitter(2.5), 3),
                      "cheapest_hour": cheapest, "dearest_hour": dearest},
            "yoy": {"fpm_median": _rel(fpm_now, fpm_before), "volatility": _r(self.rng.uniform(-0.05, 0.05), 4),
                    "cheapest_hour": None, "dearest_hour": None},
            "fpm_by_mode": [{"month": _month_iso(m), "mode": md,
                             **(lambda mid: {"fpm_p10": _r(mid * 0.62, 3), "fpm_p50": _r(mid, 3),
                                             "fpm_p90": _r(mid * 1.75, 3), "fpmin_p50": _r(mid * 0.38, 3)})(self.fpm(md, i))}
                            for i, m in enumerate(self.months) for md in COMPANIES + ("ride_hail", "all")],
            "fpm_by_hour": by_hour,
            "fpm_by_borough": [{"borough": b, "mode": md, "fare_per_mile": _r(self.fpm(md), 3),
                                "fare_per_min": _r(self.fpm(md) * 0.38, 3)}
                               for b in BOROUGHS + ("EWR",) for md in modes],
            "volatility_by_zone": volatility,
        }

    def quality(self, sizes: dict[str, int]) -> dict:
        quality = []
        for m in self.months:
            for md in MODES:
                rows = int(self.tpd[m] * self.share[m][md] * _days(m))
                valid = int(rows * self.jitter(0.985, 0.005))
                bad = rows - valid
                quality.append({"month": _month_iso(m), "mode": md, "rows": rows, "valid_rows": valid,
                                "valid_share": _r(valid / rows, 4), "f_time": bad // 3, "f_miles": bad // 3,
                                "f_fare": bad // 4, "f_zone": bad // 5,
                                "f_wait": bad // 6 if md in ("uber", "lyft", "other_hv") else None})
        classes = {"FHV - High Volume": ("uber", "lyft", "other_hv"), "Yellow": ("yellow",), "Green": ("green",)}
        tie_out = []
        for m in self.months[:-1]:
            for lc, members in classes.items():
                ours = sum(self.tpd[m] * self.share[m][md] for md in members)
                theirs = self.jitter(ours, 0.01)
                tie_out.append({"month": _month_iso(m), "license_class": lc,
                                "pipeline_trips_per_day": _r(ours, 1), "tlc_trips_per_day": _r(theirs, 1),
                                "diff": _r(ours / theirs - 1, 4), "status": "pass"})
        descriptions = {"share_monthly.json": "Monthly trips per day and share by mode",
                        "zones/index.json": "Zone summary, one row per taxi zone",
                        "congestion.json": "Congestion-pricing estimates, weekly series and fees",
                        "drivers.json": "Driver share of fare, pay and hours",
                        "prices.json": "Fare per mile and minute by mode, hour, borough and zone",
                        "airports.json": "Airport trips, shares, hours and fares"}
        return {
            **self.env(),
            "quality": quality,
            "validation": {
                "status": "pass",
                "checks": [{"id": check, "status": "pass", "summary": f"MOCK summary for {check}"}
                           for check in ("tie_out", "quality_drift", "cbd_list", "schema", "fees")],
                "tie_out": tie_out,
                "cbd": [{"zone_list": zl, "both_in_fee_share": _r(self.jitter(0.993, 0.003), 4),
                         "neither_in_fee_share": _r(self.jitter(0.004, 0.3), 4), "status": "pass"}
                        for zl in ("core", "wide")],
                "fees": [{"mode": md, "configured_fee": self.periods["fees"][
                              "cbd_fee_taxi" if md in ("yellow", "green") else "cbd_fee_hvfhv"],
                          "exact_share": _r(self.jitter(0.997, 0.002), 4),
                          "other_values": [{"cbd_fee": 0.75 if md not in ("yellow", "green") else 1.5, "trips": 120}],
                          "status": "pass"} for md in MODES],
            },
            "cbd_zones": [{"zone": z, "name": info["name"], "borderline": info["borderline"],
                           "note": "MOCK note" if info["borderline"] else ""}
                          for z, info in self.zones.items() if info["cbd"]],
            "downloads": [{"file": f, "description": d, "bytes": sizes[f]} for f, d in descriptions.items()],
        }

    def geojson(self) -> dict:
        """A 17 × 16 grid over the NYC bounding box. Exterior rings run clockwise, as d3-geo
        expects (mapshaper's default output); RFC 7946 order would fill the whole globe.
        Zone MULTIPOLYGON_ZONE is split in two, as 12 real zones are MultiPolygons."""
        west, east, south, north = -74.26, -73.70, 40.49, 40.92
        cols, rows = 17, 16
        dx, dy = (east - west) / cols, (north - south) / rows

        def ring(x0: float, x1: float, y0: float, y1: float) -> list:
            return [[x0, y1], [x1, y1], [x1, y0], [x0, y0], [x0, y1]]

        features = []
        for z, info in self.zones.items():
            col, row = (z - 1) % cols, (z - 1) // cols
            x0, x1 = round(west + col * dx, 5), round(west + (col + 1) * dx, 5)
            y1, y0 = round(north - row * dy, 5), round(north - (row + 1) * dy, 5)
            if z == MULTIPOLYGON_ZONE:
                left, right = round(x0 + 0.4 * (x1 - x0), 5), round(x0 + 0.6 * (x1 - x0), 5)
                geometry = {"type": "MultiPolygon",
                            "coordinates": [[ring(x0, left, y0, y1)], [ring(right, x1, y0, y1)]]}
            else:
                geometry = {"type": "Polygon", "coordinates": [ring(x0, x1, y0, y1)]}
            features.append({"type": "Feature",
                             "properties": {"LocationID": z, "zone": info["name"], "borough": info["borough"]},
                             "geometry": geometry})
        return {"type": "FeatureCollection", "features": features}

    def build(self) -> dict[str, dict]:
        """Every published file, keyed by its path under site/src/data/."""
        files: dict[str, dict] = {
            "events.json": self.events(),
            "tiles.json": self.tiles(),
            "share_monthly.json": self.share_monthly(),
            "home.json": self.home(),
            "zones/index.json": self.zones_index(),
            "airports.json": self.airports(),
            "congestion.json": self.congestion(),
            "drivers.json": self.drivers(),
            "prices.json": self.prices(),
            "taxi_zones.geojson": self.geojson(),
        }
        for company in COMPANIES:
            files[f"companies/{company}.json"] = self.company(company)
        for z in ZONES:
            files[f"zones/{z}.json"] = self.zone(z)
        sizes = {path: len(dumps_min(obj).encode()) for path, obj in files.items()}
        files["quality.json"] = self.quality(sizes)
        return files


def build_examples() -> dict[str, dict]:
    """Example file name → trimmed example, deterministic."""
    files = MockSite(generated_at=EXAMPLE_GENERATED_AT).build()
    examples = {}
    for pattern, name in EXAMPLES.items():
        path = pattern.format(**EXAMPLE_PARAMS)
        examples[name] = trim(files[path])
    return examples


def write_data(out_dir: Path, force: bool = False) -> list[Path]:
    """Write every mock file under ``out_dir``. Refuses to overwrite real (non-MOCK) data."""
    files = MockSite().build()
    written = []
    for path, obj in files.items():
        target = out_dir / path
        if target.exists() and not force and target.suffix == ".json":
            try:
                existing = json.loads(target.read_text()).get("as_of_month")
            except (ValueError, AttributeError):
                existing = None
            if existing != MOCK:
                raise SystemExit(f"{target} holds real data (as_of_month={existing!r}); "
                                 "refusing to overwrite it with mocks (use --force)")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(dumps_min(obj), encoding="utf-8")
        written.append(target)
    return written


def write_examples(out_dir: Path = CONTRACTS_SITE) -> list[Path]:
    written = []
    for name, obj in build_examples().items():
        target = out_dir / name
        target.write_text(dumps_pretty(obj), encoding="utf-8")
        written.append(target)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python scripts/make_mock_site_data.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=common.SITE_DATA_DIR,
                        help="output folder (default site/src/data/)")
    parser.add_argument("--examples", action="store_true",
                        help="rewrite contracts/site/*.example.json instead of writing mocks")
    parser.add_argument("--force", action="store_true", help="overwrite files that hold real data")
    args = parser.parse_args(argv)
    if args.examples:
        written = write_examples()
        print(f"wrote {len(written)} examples to {CONTRACTS_SITE.relative_to(REPO_ROOT)}/")
    else:
        written = write_data(args.out, force=args.force)
        print(f"wrote {len(written)} mock files to {args.out}")


if __name__ == "__main__":
    main()
