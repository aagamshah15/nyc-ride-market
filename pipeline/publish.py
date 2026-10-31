"""Metric outputs → site/src/data/ files, including generated titles and findings.

Refuses to write unless validation passed. ``--dev`` writes locally with
``"validated": false``, which deploy refuses.

Every value comes from ``pipeline.metrics.run`` (contracts/metrics.md), never from trips or
aggregate tables. Each file is shaped to its example in contracts/site/ (contracts/README.md),
and every sentence comes from ``pipeline.findings``. Changes "on a year earlier" compare the
latest month with the same month of the previous year.

Lane L11 · SPEC §9.2 · docs/lanes/L11-publish.md
"""

from __future__ import annotations

import argparse
import calendar
import json
import math
import shutil
import sys
from collections import defaultdict
from datetime import date, datetime, timezone
from itertools import product
from pathlib import Path

import yaml

from pipeline import common, findings, metrics, studies, validate, zones

CONTRACTS_SITE = common.REPO_ROOT / "contracts" / "site"
PAGES_PATH = CONTRACTS_SITE / "pages.yaml"
TILES_PATH = CONTRACTS_SITE / "tiles.yaml"
GEOJSON = "taxi_zones.geojson"

MODES = common.MODES
COMPANIES = ("uber", "lyft", "yellow", "green")
APPS = ("uber", "lyft")                  # the ride-hail apps with waits, accessible and shared rides
CABS = ("yellow", "green")
NAMES = {"uber": "Uber", "lyft": "Lyft", "yellow": "Yellow cab", "green": "Green cab"}   # contracts §2
ZONE_IDS = range(1, 264)                 # 264 and 265 are unknown zones and get no page (SPEC §3.3)
AIRPORT_ORDER = ("JFK", "LGA", "EWR")
DIRECTIONS = ("from", "to")
THIN_TRIPS = 100                         # contracts/README.md §4: a zone below this is thin
HEATMAP_MIN_SHARE = 0.10                 # contracts/README.md §1: heatmap modes
# Zone × company cells a "varies most" sentence may name. Smaller cells give unstable p90 ÷ p10
# (yellow-cab cells of a few hundred to 3,000 trips reach 130× to 740× in Aug 2026); the data
# rows keep every cell.
VOLATILITY_MIN_TRIPS = 5_000
TILE_DIGITS = {"count": 1, "share": 4, "usd": 2, "usd_per_mile": 3, "usd_per_minute": 3,   # contracts §2
               "usd_per_hour": 2, "seconds": 0, "trips_per_hour": 3, "ratio": 3, "effect": 4}
NYC_BOROUGHS = ("Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island")   # for sentences naming one
# Airports whose pickup records aren't TLC trips: TLC vehicles don't pick up at Newark, and its few
# records (480 in zone 1 in Aug 2026, 478 yellow, 88% ending at Newark) are an artifact. Pickup-share
# sentences, zone counts and maps leave its zone out (marked thin in the zone index, so maps grey it);
# drop-offs and the data rows keep it.
NO_PICKUP_SHARES = ("EWR",)
OUTSIDE_NYC = 265                        # "Outside of NYC": every out-of-city place in one zone (D26)
TLC_CLASSES = {"FHV - High Volume": "ride_hail", "Yellow": "yellow", "Green": "green"}
EVENT_LABELS = {"congestion_pricing_start": "Congestion pricing starts",            # D28; listed by date
                "driver_pay_inflation_step": "Per-minute minimum pay +3.9% (inflation)",
                "driver_pay_rise": "New driver minimum-pay rule"}
PAY_RULE_MEASURES = ("pay_per_min", "pay_per_mile", "fare_per_mile")   # pay_event columns
DOWNLOADS = {"share_monthly.json": "Monthly trips per day and share by mode",
             "zones/index.json": "Zone summary, one row per taxi zone",
             "congestion.json": "Congestion-pricing estimates, weekly series and fees",
             "drivers.json": "Driver share of fare, pay and hours",
             "prices.json": "Fare per mile and minute by mode, hour, borough and zone",
             "airports.json": "Airport trips, shares, hours and fares"}


class PublishError(RuntimeError):
    """Publishing can't go ahead: validation, inputs or the result failed a check."""


# --- small helpers -----------------------------------------------------------

def _r(x: float | None, digits: int) -> float | None:
    if x is None or (isinstance(x, float) and not math.isfinite(x)):
        return None
    return round(x, digits)


def _int(x: float | None) -> int | None:
    return None if x is None else int(round(x))


def _rel(now: float | None, before: float | None) -> float | None:
    """Relative change; None when the year-earlier value is missing or zero (contracts §4)."""
    if now is None or not before:
        return None
    return now / before - 1


def _pts(now: float | None, before: float | None) -> float | None:
    if now is None or before is None:
        return None
    return now - before


def _shift(month: str, months: int) -> str:
    """ "2026-08-01" moved by ``months`` → "2025-08-01" for −12."""
    index = int(month[:4]) * 12 + int(month[5:7]) - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}-01"


def _days(month: str) -> int:
    return calendar.monthrange(int(month[:4]), int(month[5:7]))[1]


def _plain(value):
    return value.isoformat() if isinstance(value, date) else value


def _mode_rank(mode: str) -> int:
    return MODES.index(mode) if mode in MODES else len(MODES)


def _airport_rank(airport: str) -> tuple:
    return (AIRPORT_ORDER.index(airport) if airport in AIRPORT_ORDER else len(AIRPORT_ORDER), airport)


def _direction_rank(direction: str) -> int:
    return DIRECTIONS.index(direction) if direction in DIRECTIONS else len(DIRECTIONS)


def _argmax(values: dict):
    known = {k: v for k, v in values.items() if v is not None}
    return max(known, key=known.get) if known else None


def _argmin(values: dict):
    known = {k: v for k, v in values.items() if v is not None}
    return min(known, key=known.get) if known else None


def dumps(obj) -> str:
    """Minified JSON, as published (contracts/README.md §1)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False)


# --- metric outputs ----------------------------------------------------------

class Outputs:
    """Metric results, each run once through ``metrics.run`` and kept as plain rows."""

    def __init__(self):
        self._results: dict[tuple, tuple[list[dict], dict]] = {}

    def _get(self, name: str, params: dict) -> tuple[list[dict], dict]:
        key = (name, tuple(sorted(params.items())))
        if key not in self._results:
            try:
                table = metrics.run(name, **params)
            except (KeyError, ValueError, RuntimeError) as exc:
                raise PublishError(f"metric {name}: {exc}") from exc
            rows = [{k: _plain(v) for k, v in row.items()} for row in table.to_pylist()]
            used = json.loads((table.schema.metadata or {}).get(b"params", b"{}"))
            self._results[key] = (rows, used)
        return self._results[key]

    def rows(self, name: str, **params) -> list[dict]:
        return self._get(name, params)[0]

    def params(self, name: str, **params) -> dict:
        """The parameters the run actually used, defaults filled in by the runner."""
        return self._get(name, params)[1]


# --- the site ----------------------------------------------------------------

class Site:
    """Every published file, built from metric outputs for the latest month in the data."""

    def __init__(self, outputs: Outputs, *, generated_at: str):
        self.out = outputs
        self.generated_at = generated_at
        self.validated = False
        self.summary: dict | None = None
        share_rows = outputs.rows("share_monthly")
        if not share_rows:
            raise PublishError("share_monthly has no rows: there are no aggregates to publish")
        self.months = sorted({r["month"] for r in share_rows})
        self.month = self.months[-1]
        self.as_of = self.month[:7]
        self.prior = _shift(self.month, -12)
        self.has_prior = self.prior in self.months
        self.share = {(r["month"], r["mode"]): r for r in share_rows}
        self.lookup = zones.read_lookup()
        self.cbd_rows = zones.load_cbd_zones()
        self.cbd_core = {r["LocationID"] for r in self.cbd_rows if not r["borderline"]}
        self.cbd_borderline = {r["LocationID"] for r in self.cbd_rows if r["borderline"]}
        self.airports = zones.airport_zones()
        self.no_pickup_zones = {z for z, code in self.airports.items() if code in NO_PICKUP_SHARES}
        self.pickup_zones = [z for z in ZONE_IDS if z not in self.no_pickup_zones]   # zones a sentence may name
        self.periods = common.load_yaml("periods.yaml")
        self.tile_registry = yaml.safe_load(TILES_PATH.read_text(encoding="utf-8"))
        self._zones: dict[int, dict] | None = None

    def env(self) -> dict:
        return {"as_of_month": self.as_of, "generated_at": self.generated_at, "validated": self.validated}

    def zone_name(self, zone: int) -> str:
        try:
            return self.lookup[zone]["Zone"]
        except KeyError:
            raise PublishError(f"zone lookup has no LocationID {zone}") from None

    def _tiles(self, now: dict, prior: dict) -> tuple[dict, dict]:
        """``(tiles, yoy)`` from unrounded values: each tile rounded for its unit, and its change
        versus ``prior`` (the same month a year earlier) by its kind in site/tiles.yaml."""
        tiles, yoy = {}, {}
        for key, value in now.items():
            meta = self.tile_registry[key]
            digits = TILE_DIGITS.get(meta["unit"])
            tiles[key] = value if digits is None or isinstance(value, int) else _r(value, digits)
            before, kind = prior.get(key), meta["yoy"]
            if kind == "relative":
                yoy[key] = _r(_rel(value, before), 4)
            elif kind == "pts":
                yoy[key] = _r(_pts(value, before), 4)
            elif kind == "diff":
                yoy[key] = None if value is None or before is None else value - before
            else:
                yoy[key] = None
        return tiles, yoy

    # --- shared values -------------------------------------------------------

    def trips_per_day(self, month: str) -> float | None:
        rows = [self.share[(month, mode)]["trips_per_day"] for mode in MODES if (month, mode) in self.share]
        return sum(rows) if rows else None

    def mode_share(self, month: str, mode: str) -> float | None:
        row = self.share.get((month, mode))
        return row["share"] if row else None

    def zone_info(self) -> dict[int, dict]:
        """Per-zone values used by the zone files, the index, and the company and home counts."""
        if self._zones is not None:
            return self._zones
        trips: dict[tuple, int] = defaultdict(int)
        shares: dict[tuple, dict] = defaultdict(dict)
        for r in self.out.rows("trip_share"):
            trips[(r["month"], r["pu_zone"])] += r["trips"]
            shares[(r["month"], r["pu_zone"])][r["mode"]] = r["share"]
        change = {(r["pu_zone"], r["mode"]): r for r in self.out.rows("zone_share_change")}
        lvu = {r["pu_zone"]: r for r in self.out.rows("lyft_vs_uber")}
        waits = {(r["month"], r["pu_zone"], r["mode"]): r for r in self.out.rows("wait_time")}
        result = {}
        for z in ZONE_IDS:
            now_trips = trips.get((self.month, z), 0)
            prior_trips = trips.get((self.prior, z), 0) if self.has_prior else None
            rh = change.get((z, "ride_hail"), {})
            yellow = change.get((z, "yellow"), {})
            app = _argmax({m: change.get((z, m), {}).get("trips_per_day") or None for m in APPS})
            no_pickups = z in self.no_pickup_zones      # counted as thin both years: out of every zone count
            result[z] = {
                "trips": now_trips, "prior_trips": prior_trips,
                "trips_per_day": now_trips / _days(self.month),
                "prior_trips_per_day": None if prior_trips is None else prior_trips / _days(self.prior),
                "no_pickups": no_pickups,
                "thin": no_pickups or now_trips < THIN_TRIPS,
                "thin_prior": None if prior_trips is None else no_pickups or prior_trips < THIN_TRIPS,
                "top_mode": _argmax({m: shares[(self.month, z)].get(m) for m in MODES}),
                "top_mode_prior": _argmax({m: shares[(self.prior, z)].get(m) for m in MODES}),
                "rh_share": rh.get("share"), "rh_change": rh.get("change"),
                "yellow_share": yellow.get("share"), "yellow_change": yellow.get("change"),
                "lvu": lvu.get(z),
                "app": app,
                "wait": waits.get((self.month, z, app), {}) if app else {},
                "wait_prior": waits.get((self.prior, z, app), {}) if app else {},
            }
        self._zones = result
        return result

    def zone_counts(self) -> dict:
        """Zone counts over zones with enough trips that month (the thin rule, both years)."""
        zs = self.zone_info()
        now = [z for z in zs.values() if not z["thin"]]
        prior = [z for z in zs.values() if z["thin_prior"] is False]
        both = [z for z in now if z["thin_prior"] is False and z["rh_change"] is not None]
        with_share = [z for z in now if z["rh_share"] is not None]
        return {
            "yellow_leads": sum(z["top_mode"] == "yellow" for z in now),
            "yellow_leads_prior": sum(z["top_mode_prior"] == "yellow" for z in prior) if self.has_prior else None,
            "lyft_ahead": sum(bool(z["lvu"]) and (z["lvu"]["gap"] or 0) > 0 for z in now),
            "lyft_ahead_prior": (sum(bool(z["lvu"]) and (z["lvu"]["gap_prior"] or 0) > 0 for z in prior)
                                 if self.has_prior else None),
            "rh_up": sum(z["rh_change"] > 0 for z in both),
            "rh_compared": len(both),
            "rh_majority": sum(z["rh_share"] >= 0.5 for z in with_share),
            "rh_measured": len(with_share),
        }

    # --- files ---------------------------------------------------------------

    def events(self) -> dict:
        keys = sorted(EVENT_LABELS, key=lambda key: str(self.periods[key]))
        return {**self.env(), "events": [{"id": key, "date": str(self.periods[key]), "label": EVENT_LABELS[key]}
                                         for key in keys]}

    def tiles(self) -> dict:
        return {**self.env(), "tiles": self.tile_registry}

    def share_monthly(self) -> dict:
        rows = [{"month": m, "mode": mode, "trips_per_day": _r(row["trips_per_day"], 1), "share": _r(row["share"], 4)}
                for m in self.months for mode in MODES if (row := self.share.get((m, mode)))]
        return {**self.env(), "rows": rows}

    def home(self) -> dict:
        m, p = self.month, self.prior
        ds = {(r["month"], r["mode"]): r for r in self.out.rows("driver_share")}
        fees = defaultdict(float)
        for r in self.out.rows("fee_revenue"):
            fees[r["month"]] += r["cbd_fee"] or 0.0

        def tiles_for(month: str) -> dict:
            return {"trips_per_day": self.trips_per_day(month),
                    "rh_share": self.mode_share(month, "ride_hail"),
                    "platform_share": ds.get((month, "ride_hail"), {}).get("platform_share"),
                    "cbd_fees_last_month": fees.get(month)}

        tiles, yoy = self._tiles(tiles_for(m), tiles_for(p))
        # the same calendar month at both ends, the earliest year in the data, so no season is mixed in
        same_month = [mo for mo in self.months if mo[5:7] == m[5:7]]
        first = same_month[0] if len(same_month) > 1 else None
        changes = {c: _pts(self.mode_share(m, c), self.mode_share(first, c)) if first else None for c in COMPANIES}
        mover = _argmax({c: None if v is None else abs(v) for c, v in changes.items()})
        turn = None
        if mover:
            ends = (self.mode_share(first, mover), self.mode_share(m, mover))
            between = [(mo, self.mode_share(mo, mover)) for mo in same_month[1:-1] if self.mode_share(mo, mover)]
            low = min(between, key=lambda t: t[1], default=None)
            high = max(between, key=lambda t: t[1], default=None)
            if low and low[1] < min(ends):
                turn = ("dipped", *low)
            elif high and high[1] > max(ends):
                turn = ("peaked", *high)
        return {**self.env(),
                "title": findings.home_title(rh_share=tiles["rh_share"], month=m),
                "subtitles": {"share_trend": findings.home_share_trend(
                    mode=mover, change=changes.get(mover), first_month=first, month=m, turn=turn)},
                "tiles": tiles, "yoy": yoy,
                "findings": [f for f in self.findings() if f]}

    def company(self, mode: str) -> dict:
        m, p = self.month, self.prior
        cab = mode in CABS
        fpm = {(r["month"], r["mode"]): r for r in self.out.rows("fare_dist") if r["pu_zone"] == 0}
        ds = {(r["month"], r["mode"]): r for r in self.out.rows("driver_share")}
        tips = {(r["month"], r["mode"]): r for r in self.out.rows("tip_rate") if r["pu_borough"] == "all"}
        wav = [r for r in self.out.rows("wav_service") if r["mode"] in APPS]
        shared = [r for r in self.out.rows("shared_match_rate") if r["pu_zone"] == 0 and r["mode"] in APPS]
        waits = {(r["month"], r["mode"]): r for r in self.out.rows("wait_time") if r["pu_zone"] == 0}
        rates = {(r["month"], r["mode"]): r for r in self.out.rows("fare_rates")}

        def tiles_for(month: str) -> dict:
            return {"trips_per_day": self.share.get((month, mode), {}).get("trips_per_day"),
                    "share": self.mode_share(month, mode),
                    "fpm_median": fpm.get((month, mode), {}).get("fpm_p50"),
                    "driver_share": None if cab else ds.get((month, mode), {}).get("driver_share"),
                    "tip_rate": tips.get((month, mode), {}).get("tip_rate")}

        tiles, yoy = self._tiles(tiles_for(m), tiles_for(p))
        wav_now = {r["mode"]: r for r in wav if r["month"] == m}
        shared_now = {r["mode"]: r for r in shared if r["month"] == m}

        def per_company(value) -> dict:
            return {c: value(c) for c in COMPANIES}

        compare_values = {
            "trips_per_day": ("count", lambda c: _r(self.share.get((m, c), {}).get("trips_per_day"), 1)),
            "share": ("share", lambda c: _r(self.mode_share(m, c), 4)),
            "fpm_median": ("usd_per_mile", lambda c: _r(fpm.get((m, c), {}).get("fpm_p50"), 3)),
            "fare_per_min": ("usd_per_minute", lambda c: _r(rates.get((m, c), {}).get("fare_per_min"), 3)),
            "driver_share": ("share", lambda c: _r(ds.get((m, c), {}).get("driver_share"), 4)),
            "tip_rate": ("share", lambda c: _r(tips.get((m, c), {}).get("tip_rate"), 4)),
            "wait_p50": ("seconds", lambda c: _r(waits.get((m, c), {}).get("wait_p50"), 0)),
            "wav_share": ("share", lambda c: _r(wav_now.get(c, {}).get("wav_share"), 4)),
            "shared_match_rate": ("share", lambda c: _r(shared_now.get(c, {}).get("match_rate"), 4)),
        }
        compare = [{"metric": metric, "unit": unit, **per_company(value)}
                   for metric, (unit, value) in compare_values.items()]

        lyft_vs_uber = None
        lvu_subtitle = None
        if not cab:
            counts = self.zone_counts()
            by_zone = [{"zone": z, "name": self.zone_name(z), "lyft_share": _r(row["lyft_share"], 4),
                        "uber_share": _r(row["uber_share"], 4), "gap": _r(row["gap"], 4),
                        "gap_change": _r(row["gap_change"], 4), "thin": info["thin"]}
                       for z, info in self.zone_info().items() if (row := info["lvu"])]
            lyft_vs_uber = {"zones_lyft_ahead": counts["lyft_ahead"],
                            "zones_lyft_ahead_prior_year": counts["lyft_ahead_prior"], "by_zone": by_zone}
            lvu_subtitle = findings.lyft_vs_uber(zones_now=counts["lyft_ahead"],
                                                 zones_prior=counts["lyft_ahead_prior"], month=m)

        dist_now = fpm.get((m, mode), {})
        subtitles = {
            "share_trend": findings.company_share_trend(mode=mode, change=yoy["share"], month=m, prior=p),
            "fpm_dist": findings.company_fpm_dist(mode=mode, fpm_median=tiles["fpm_median"],
                                                  change=yoy["fpm_median"], p10=dist_now.get("fpm_p10"),
                                                  p90=dist_now.get("fpm_p90"), month=m, prior=p),
            "tip_rate": findings.company_tip_rate(mode=mode, tip_rate=tiles["tip_rate"], change=yoy["tip_rate"],
                                                  card_only=cab, month=m),
            "wav": findings.company_wav(
                mode=mode, service={a: (wav_now.get(a, {}).get("wav_requests"), wav_now.get(a, {}).get("wav_share"))
                                    for a in APPS}, month=m),
            "shared": findings.company_shared(mode=mode,
                                              requests={a: shared_now.get(a, {}).get("requests") for a in APPS},
                                              matched_share=shared_now.get(mode, {}).get("match_rate"), month=m),
            "compare": findings.company_compare(
                mode=mode, fpm_medians={c: compare_values["fpm_median"][1](c) for c in COMPANIES}, month=m),
            "lyft_vs_uber": lvu_subtitle,
        }
        return {
            **self.env(), "mode": mode, "name": NAMES[mode],
            "title": findings.company_title(mode=mode, mode_share=tiles["share"], month=m),
            "subtitles": subtitles, "tiles": tiles, "yoy": yoy,
            "not_reported": ["driver_share", "wav", "shared"] if cab else [],
            "share_trend": [{"month": month, "mode": md, "share": _r(row["share"], 4),
                             "trips_per_day": _r(row["trips_per_day"], 1)}
                            for month in self.months for md in MODES if (row := self.share.get((month, md)))],
            "fpm_dist": [{"month": r["month"], "mode": r["mode"], "fpm_p10": _r(r["fpm_p10"], 3),
                          "fpm_p50": _r(r["fpm_p50"], 3), "fpm_p90": _r(r["fpm_p90"], 3),
                          "fpmin_p50": _r(r["fpmin_p50"], 3)}
                         for (_, md), r in sorted(fpm.items(), key=lambda kv: (kv[0][0], _mode_rank(kv[0][1])))
                         if md in COMPANIES],
            "tip_rate": [{"month": r["month"], "mode": r["mode"], "tip_rate": _r(r["tip_rate"], 4),
                          "card_only": r["card_only"]}
                         for (_, md), r in sorted(tips.items(), key=lambda kv: (kv[0][0], _mode_rank(kv[0][1])))
                         if md in COMPANIES],
            "wav": [{"month": r["month"], "mode": r["mode"], "trips": r["trips"], "wav_requests": r["wav_requests"],
                     "wav_trips": r["wav_trips"], "wav_share": _r(r["wav_share"], 4)} for r in wav],
            "shared": [self._match_row(r) for r in shared],
            "compare": compare,
            "lyft_vs_uber": lyft_vs_uber,
        }

    @staticmethod
    def _match_row(r: dict) -> dict:
        return {"month": r["month"], "mode": r["mode"], "requests": r["requests"], "matched": r["matched"],
                "match_rate": _r(r["match_rate"], 4)}

    def zones_index(self) -> dict:
        m, p = self.month, self.prior
        zs = self.zone_info()
        counts = self.zone_counts()
        rows = [{"zone": z, "name": self.zone_name(z), "borough": self.lookup[z]["Borough"],
                 "trips_per_day": _r(info["trips_per_day"], 1), "rh_share": _r(info["rh_share"], 4),
                 "yellow_share": _r(info["yellow_share"], 4),
                 "wait_p50": None if info["thin"] else _r(info["wait"].get("wait_p50"), 0),
                 "share_change_yoy": _r(info["rh_change"], 4),
                 "yellow_share_change_yoy": _r(info["yellow_change"], 4),
                 "top_mode": info["top_mode"], "cbd": z in self.cbd_core, "thin": info["thin"]}
                for z, info in zs.items()]
        busiest = max((r for r in rows if r["zone"] not in self.no_pickup_zones), key=lambda r: r["trips_per_day"] or 0)
        tiles, yoy = self._tiles({"zones_yellow_leads": counts["yellow_leads"],
                                  "zones_lyft_beats_uber": counts["lyft_ahead"], "zones_rh_share_up": counts["rh_up"]},
                                 {"zones_yellow_leads": counts["yellow_leads_prior"],
                                  "zones_lyft_beats_uber": counts["lyft_ahead_prior"]})
        return {**self.env(),
                "title": findings.zones_title(zones_now=counts["yellow_leads"],
                                              zones_prior=counts["yellow_leads_prior"], month=m),
                "subtitles": {
                    "level_map": findings.zones_level_map(majority=counts["rh_majority"],
                                                          total=counts["rh_measured"], month=m),
                    "change_map": findings.zones_change_map(rose=counts["rh_up"], total=counts["rh_compared"],
                                                            month=m, prior=p),
                    "yellow_map": findings.zones_yellow_map(zones_now=counts["yellow_leads"],
                                                            zones_prior=counts["yellow_leads_prior"], month=m),
                    "table": findings.zones_table(name=busiest["name"] if busiest["trips_per_day"] else None,
                                                  trips_per_day=busiest["trips_per_day"], month=m)},
                "tiles": tiles, "yoy": yoy, "rows": rows}

    def zone_files(self) -> dict[str, dict]:
        m, p = self.month, self.prior
        share_trend = defaultdict(list)
        for r in self.out.rows("trip_share"):
            if r["mode"] in COMPANIES:
                share_trend[r["pu_zone"]].append({"month": r["month"], "mode": r["mode"], "share": _r(r["share"], 4)})
        profile = defaultdict(list)
        for r in self.out.rows("zone_hour_profile"):
            profile[r["pu_zone"]].append(r)
        window = self.out.params("zone_hour_profile").get("window")
        monthly_waits = defaultdict(list)
        for r in self.out.rows("wait_time"):
            if r["wait_p50"] is not None or r["wait_p90"] is not None:
                monthly_waits[r["pu_zone"]].append({"month": r["month"], "mode": r["mode"],
                                                    "wait_p50": _r(r["wait_p50"], 0), "wait_p90": _r(r["wait_p90"], 0)})
        hourly_waits = defaultdict(list)
        for r in self.out.rows("wait_by_hour"):
            hourly_waits[r["pu_zone"]].append({"hour": r["hour"], "mode": r["mode"], "wait_mean": _r(r["wait_mean"], 0)})
        dropoffs: dict[str, float] = defaultdict(float)     # trips a day to each airport, latest month
        for r in self.out.rows("airport_share"):
            if r["month"] == m and r["direction"] == "to":
                dropoffs[r["airport"]] += r["trips_per_day"] or 0.0
        destinations = defaultdict(list)
        for r in sorted(self.out.rows("top_destinations"), key=lambda r: (r["pu_zone"], r["rank"])):
            destinations[r["pu_zone"]].append({"do_zone": r["do_zone"], "name": self.zone_name(r["do_zone"]),
                                               "trips": r["trips"], "share": _r(r["share"], 4)})

        files = {}
        for z, info in self.zone_info().items():
            name, thin = self.zone_name(z), info["thin"]
            hours: dict[int, float] = defaultdict(float)
            for r in profile[z]:
                hours[r["hour_of_week"]] += r["trips_per_week"] or 0.0
            peak = _argmax(dict(hours))
            heatmap = [{"hour_of_week": r["hour_of_week"], "mode": r["mode"], "trips": _r(r["trips_per_week"], 1)}
                       for r in sorted(profile[z], key=lambda r: (_mode_rank(r["mode"]), r["hour_of_week"]))
                       if (r["mode_share_in_zone"] or 0) >= HEATMAP_MIN_SHARE]
            dests = destinations[z]
            # name a mapped zone; "Outside of NYC" gets its own clause when it would have ranked first
            mapped = [d for d in dests if d["do_zone"] in ZONE_IDS]
            top = mapped[0] if mapped else None
            out = next((d for d in dests if d["do_zone"] == OUTSIDE_NYC), None)
            left_city = out["share"] if out and (top is None or dests.index(out) < dests.index(top)) else None
            wait, wait_prior = info["wait"], info["wait_prior"]
            tiles, yoy = self._tiles(
                {"trips_per_day": info["trips_per_day"], "rh_share": info["rh_share"],
                 "wait_p50": None if thin else wait.get("wait_p50"),
                 "wait_p90": None if thin else wait.get("wait_p90"),
                 "top_destination": top["name"] if top else None},
                {"trips_per_day": info["prior_trips_per_day"], "wait_p50": wait_prior.get("wait_p50"),
                 "wait_p90": wait_prior.get("wait_p90")})
            yoy["rh_share"] = _r(info["rh_change"], 4)     # zone_share_change's own change
            title = findings.zone_title(name=name, rh_share=info["rh_share"], trips=info["trips"], thin=thin, month=m)
            subtitles = {
                "share_trend": findings.zone_share_trend(rh_share=info["rh_share"], change=info["rh_change"],
                                                         month=m, prior=p),
                "hour_heatmap": findings.zone_hour_heatmap(peak_hour=peak, peak_trips=hours.get(peak),
                                                           window=window, month=m),
                "waits": findings.zone_waits(mode=info["app"], wait_p50=tiles["wait_p50"], thin=thin, month=m),
                "top_destinations": findings.zone_top_destinations(
                    name=top["name"] if top else None, dest_share=top["share"] if top else None,
                    left_city_share=left_city, month=m)}
            if info["no_pickups"]:      # pickup records here aren't TLC trips: no tile or sentence reads them
                airport = self.airports[z]
                title = findings.zone_not_tlc_title(name=name, dropoffs_per_day=dropoffs.get(airport), month=m)
                subtitles = {chart: findings.zone_not_tlc(name=name, chart=chart) for chart in subtitles}
                tiles = {key: None for key in tiles}
                yoy = {key: None for key in yoy}
            files[f"zones/{z}.json"] = {
                **self.env(), "zone": z, "name": name, "borough": self.lookup[z]["Borough"],
                "flags": {"cbd": z in self.cbd_core, "cbd_borderline": z in self.cbd_borderline,
                          "airport": self.airports.get(z), "thin": thin},
                "title": title, "subtitles": subtitles, "tiles": tiles, "yoy": yoy,
                "share_trend": share_trend[z],
                "hour_heatmap": heatmap,
                "waits": {"monthly": [] if thin else monthly_waits[z], "by_hour": [] if thin else hourly_waits[z]},
                "top_destinations": dests,
            }
        return files

    def airports_page(self) -> dict:
        m, p = self.month, self.prior

        def key(r: dict) -> tuple:
            return (_airport_rank(r["airport"]), _direction_rank(r["direction"]), _mode_rank(r["mode"]))

        share_rows = self.out.rows("airport_share")
        latest = sorted((r for r in share_rows if r["month"] == m), key=key)
        airports = sorted({r["airport"] for r in latest}, key=_airport_rank)

        def totals(month: str, rows: list[dict]) -> tuple[dict, int]:
            by_mode: dict[str, int] = defaultdict(int)
            for r in rows:
                if r["month"] == month:
                    by_mode[r["mode"]] += r["trips"]
            return by_mode, sum(by_mode.values())

        def yellow_share(month: str, rows: list[dict]) -> float | None:
            by_mode, total = totals(month, rows)
            return by_mode["yellow"] / total if total else None

        def fare_mean(month: str) -> float | None:
            rows = self.out.rows("airport_fares", to_month=month)
            trips = sum(r["trips"] for r in rows if r["fare_mean"] is not None)
            return sum(r["fare_mean"] * r["trips"] for r in rows if r["fare_mean"] is not None) / trips if trips else None

        # sentences count trips to every airport and pickups everywhere but NO_PICKUP_SHARES
        counted = [r for r in share_rows if not (r["direction"] == "from" and r["airport"] in NO_PICKUP_SHARES)]
        by_mode_now, total_now = totals(m, counted)
        top = _argmax(dict(by_mode_now))
        both_ways = sorted({r["airport"] for r in counted if r["month"] == m and r["direction"] == "from"},
                           key=_airport_rank)
        dropoff_only = [a for a in airports if a not in both_ways]

        by_hour = self.out.rows("airport_by_hour")
        window = self.out.params("airport_by_hour").get("window")
        hourly: dict[int, float] = defaultdict(float)
        for r in by_hour:
            hourly[r["hour"]] += r["trips_per_day"] or 0.0
        busiest = _argmax(dict(hourly))

        def trips_per_day(month: str) -> float | None:
            rows = [r["trips_per_day"] for r in share_rows if r["month"] == month]
            return sum(rows) if rows else None

        tiles, yoy = self._tiles(
            {"trips_per_day": trips_per_day(m), "yellow_share": yellow_share(m, share_rows),
             "fare_to_manhattan_mean": fare_mean(m), "busiest_hour": busiest},
            {"trips_per_day": trips_per_day(p), "yellow_share": yellow_share(p, share_rows),
             "fare_to_manhattan_mean": fare_mean(p) if self.has_prior else None})

        trend: dict[tuple, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for r in share_rows:
            trend[(r["month"], r["airport"])][r["mode"]] += r["trips"]
        share_trend = []
        for (month, airport), counts in sorted(trend.items(), key=lambda kv: (kv[0][0], _airport_rank(kv[0][1]))):
            total = sum(counts.values())
            share_trend += [{"month": month, "airport": airport, "mode": md, "share": _r(n / total, 4) if total else None}
                            for md, n in sorted(counts.items(), key=lambda kv: _mode_rank(kv[0]))]

        leaders = []
        for airport in both_ways:
            pickups = {r["mode"]: r["share"] for r in latest if r["airport"] == airport and r["direction"] == "from"}
            if (leader := _argmax(pickups)) is not None:
                leaders.append((airport, leader, pickups[leader]))

        fares = sorted(self.out.rows("airport_fares", to_month=m),
                       key=lambda r: (_airport_rank(r["airport"]), _mode_rank(r["mode"])))
        fares_out = [{"airport": r["airport"], "mode": r["mode"], "fare_mean": _r(r["fare_mean"], 2),
                      "fare_base_mean": _r(r["fare_base_mean"], 2), "fare_per_mile": _r(r["fare_per_mile"], 3),
                      "trips_per_day": _r(r["trips"] / _days(m), 1)} for r in fares]
        fares_by_airport: dict[str, list] = defaultdict(list)
        for r in fares:
            fares_by_airport[r["airport"]].append(r)
        focus = _argmax({a: sum(r["trips"] for r in rows) for a, rows in fares_by_airport.items()})
        focus_rows = [r for r in fares_by_airport.get(focus, []) if r["fare_mean"] is not None]
        focus_trips = sum(r["trips"] for r in focus_rows)
        focus_mean = sum(r["fare_mean"] * r["trips"] for r in focus_rows) / focus_trips if focus_trips else None
        cheapest = min(focus_rows, key=lambda r: r["fare_mean"]) if focus_rows else None
        dearest = max(focus_rows, key=lambda r: r["fare_mean"]) if focus_rows else None

        def mean_fare(rows: list[dict]) -> float | None:     # rider total ÷ trips, a ratio of sums
            rows = [r for r in rows if r["fare_mean"] is not None]
            trips = sum(r["trips"] for r in rows)
            return sum(r["fare_mean"] * r["trips"] for r in rows) / trips if trips else None

        airport_fares = [(a, mean_fare(fares_by_airport[a])) for a in sorted(fares_by_airport, key=_airport_rank)]

        self.airport_facts = {"top": top, "top_share": by_mode_now[top] / total_now if top else None,
                              "airports": both_ways, "dropoff_only": dropoff_only,
                              "fares": airport_fares, "busiest_hour": busiest}
        return {
            **self.env(),
            "title": findings.airports_title(mode=top, top_share=self.airport_facts["top_share"],
                                             airports=both_ways, dropoff_only=dropoff_only, month=m),
            "subtitles": {
                "split": findings.airports_split(leaders=leaders, month=m),
                "share_trend": findings.airports_share_trend(
                    yellow_change=_pts(yellow_share(m, counted), yellow_share(p, counted)), month=m, prior=p),
                "by_hour": findings.airports_by_hour(hour=busiest, trips_per_day=hourly.get(busiest),
                                                     window=window, month=m),
                "fares": findings.airports_fares(
                    airport=focus, fare_mean=focus_mean,
                    cheapest=(cheapest["mode"], cheapest["fare_mean"]) if cheapest else None,
                    dearest=(dearest["mode"], dearest["fare_mean"]) if dearest else None, month=m)},
            "tiles": tiles, "yoy": yoy,
            "split": [{"airport": r["airport"], "direction": r["direction"], "mode": r["mode"],
                       "trips_per_day": _r(r["trips_per_day"], 1), "share": _r(r["share"], 4)} for r in latest],
            "share_trend": share_trend,
            "by_hour": [{"airport": r["airport"], "direction": r["direction"], "hour": r["hour"], "mode": r["mode"],
                         "trips_per_day": _r(r["trips_per_day"], 1)}
                        for r in sorted(by_hour, key=lambda r: (_airport_rank(r["airport"]),
                                                                _direction_rank(r["direction"]), r["hour"],
                                                                _mode_rank(r["mode"])))],
            "fares": fares_out,
        }

    def congestion(self) -> dict:
        start = str(self.periods["congestion_pricing_start"])
        summary = self.out.rows("cp_effect_summary")
        weekly = self.out.rows("cp_effect")
        effect = {(r["metric"], r["mode"], r["zone_list"]): r for r in summary}
        trips_all = effect.get(("trips", "all", "core"), {})
        fpm_rh = effect.get(("fare_per_mile", "ride_hail", "core"), {})
        fees = [r for r in self.out.rows("fee_revenue") if r["month"] >= start[:7] + "-01"]
        total_fees = sum(r["cbd_fee"] or 0.0 for r in fees)
        by_mode: dict[str, float] = defaultdict(float)
        for r in fees:
            by_mode[r["mode"]] += r["cbd_fee"] or 0.0
        top_fee_mode = _argmax(dict(by_mode))

        mode_effects = {md: effect.get(("trips", md, "core"), {}).get("median") for md in ("ride_hail", "yellow", "green")}
        green_share = self.mode_share(self.month, "green")

        trips = [r for r in self.out.rows("cp_weekly_trips") if r["zone_list"] == "core"]
        years = sorted({r["iso_year"] for r in trips})
        growth = {}
        if len(years) >= 2:
            base, year = years[0], years[-1]
            series = {(r["cbd_group"], r["iso_year"], r["iso_week"]): r["trips_per_day"]
                      for r in trips if r["mode"] == "all" and r["trips_per_day"] is not None}
            # weeks with both groups in both years; every week has 7 days, so summing the weekly
            # rates is a ratio of sums
            weeks = set.intersection(*({w for (g, y, w) in series if (g, y) == key}
                                       for key in product(("treated", "control"), (base, year))))
            for group in ("treated", "control"):
                growth[group] = _rel(sum(series[(group, year, w)] for w in weeks),
                                     sum(series[(group, base, w)] for w in weeks))

        start_year = int(start[:4])
        change = [r for r in self.out.rows("cp_zone_change") if r["pu_zone"] in ZONE_IDS]
        measured = [r for r in change if r["change"] is not None and r["pu_zone"] in self.pickup_zones]
        in_zone = [r for r in measured if r["pu_zone"] in self.cbd_core]
        excluded = sorted({(r["iso_year"], r["iso_week"], r["exclusion_reason"]) for r in weekly if r["excluded"]},
                          key=lambda t: (t[0], t[1], t[2] or ""))

        tiles, yoy = self._tiles({"trips_effect": trips_all.get("median"), "fpm_effect": fpm_rh.get("median"),
                                  "fees_to_date": total_fees if fees else None}, {})
        self.congestion_facts = {"trips_all": trips_all, "mode_effects": mode_effects, "green_share": green_share,
                                 "fpm_rh": fpm_rh.get("median"),
                                 "ds_rh": effect.get(("driver_share", "ride_hail", "core"), {}).get("median")}
        return {
            **self.env(),
            "title": findings.congestion_title(trips_effect=tiles["trips_effect"]),
            "subtitles": {
                "effects": findings.congestion_effects(by_mode=mode_effects, green_share=green_share),
                "weekly_effect": findings.congestion_weekly_effect(p10=trips_all.get("p10"), p90=trips_all.get("p90")),
                "weekly_trips": findings.congestion_weekly_trips(
                    treated_change=growth.get("treated"), control_change=growth.get("control"),
                    year=years[-1] if years else None, base_year=years[0] if years else None),
                "fees": findings.congestion_fees(total=total_fees if fees else None, first_month=start, month=self.month,
                                                 top_mode=top_fee_mode,
                                                 top_share=by_mode[top_fee_mode] / total_fees
                                                 if top_fee_mode and total_fees else None),
                "zone_change": findings.congestion_zone_change(
                    fell=sum(r["change"] < 0 for r in measured), total=len(measured),
                    fell_cbd=sum(r["change"] < 0 for r in in_zone), total_cbd=len(in_zone),
                    year=start_year, base_year=start_year - 1)},
            "tiles": tiles, "yoy": yoy,
            "effects": [{"metric": r["metric"], "mode": r["mode"], "zone_list": r["zone_list"],
                         "median": _r(r["median"], 4), "p10": _r(r["p10"], 4), "p90": _r(r["p90"], 4),
                         "weeks": r["weeks"]} for r in summary],
            "weekly_effect": [{"week_start": r["week_start"], "iso_week": r["iso_week"], "metric": r["metric"],
                               "mode": r["mode"], "zone_list": r["zone_list"], "effect": _r(r["effect"], 4),
                               "excluded": r["excluded"]} for r in weekly],
            "weekly_trips": [{"week_start": r["week_start"], "iso_year": r["iso_year"], "iso_week": r["iso_week"],
                              "cbd_group": r["cbd_group"], "mode": r["mode"],
                              "trips_per_day": _r(r["trips_per_day"], 1)} for r in trips],
            "fees": [{"month": r["month"], "mode": r["mode"], "cbd_fee": _r(r["cbd_fee"], 2),
                      "trips_with_cbd_fee": r["trips_with_cbd_fee"]} for r in fees],
            "zone_change": [{"zone": r["pu_zone"], "change": _r(r["change"], 4)} for r in change],
            "excluded_weeks": [{"iso_year": y, "iso_week": w, "reason": reason} for y, w, reason in excluded],
        }

    def drivers(self) -> dict:
        m, p = self.month, self.prior
        ds = self.out.rows("driver_share")
        pph = self.out.rows("pay_per_hour")
        ds_at = {(r["month"], r["mode"]): r for r in ds}
        pph_at = {(r["month"], r["mode"]): r for r in pph}
        hours = [r for r in self.out.rows("trips_per_hour_worked")
                 if r["license_class"] in TLC_CLASSES and self.months[0] <= r["month"] <= m]
        hv = {r["month"]: r for r in hours if TLC_CLASSES[r["license_class"]] == "ride_hail"}
        tlc_month = max(hv) if hv else None
        tlc_now = hv.get(tlc_month, {})
        tlc_prior = hv.get(_shift(tlc_month, -12), {}) if tlc_month else {}

        def tiles_for(month: str, tlc: dict) -> dict:
            return {"pay_per_hour": pph_at.get((month, "ride_hail"), {}).get("pay_per_hour"),
                    "driver_share": ds_at.get((month, "ride_hail"), {}).get("driver_share"),
                    "trips_per_hour_worked": tlc.get("trips_per_hour_worked"),
                    "active_drivers": _int(tlc.get("unique_drivers"))}

        tiles, yoy = self._tiles(tiles_for(m, tlc_now), tiles_for(p, tlc_prior))

        event = self.out.rows("pay_event")
        rule = self.pay_rule()
        tph_by_class = {TLC_CLASSES[r["license_class"]]: r["trips_per_hour_worked"]
                        for r in hours if r["month"] == tlc_month}
        self.driver_facts = {"tlc_month": tlc_month, "tlc_now": tlc_now}
        return {
            **self.env(),
            "title": findings.drivers_title(driver_share=tiles["driver_share"], month=m),
            "subtitles": {
                "driver_share_trend": findings.drivers_share_trend(
                    changes={a: _pts(ds_at.get((m, a), {}).get("driver_share"),
                                     ds_at.get((p, a), {}).get("driver_share")) for a in APPS},
                    month=m, prior=p),
                "pay_per_hour_trend": findings.drivers_pay_per_hour(pay_per_hour=tiles["pay_per_hour"],
                                                                    change=yoy["pay_per_hour"], month=m),
                "event_study": findings.drivers_event_study(
                    pay_per_min=rule["net"].get("pay_per_min"), pay_per_mile=rule["net"].get("pay_per_mile"),
                    weeks=rule["weeks"], base_year=rule["base_year"]),
                "hours": findings.drivers_hours(tph={k: tph_by_class.get(k) for k in TLC_CLASSES.values()},
                                                tlc_month=tlc_month) if tlc_month else None},
            "tiles": tiles, "yoy": yoy,
            "tlc_as_of_month": tlc_month[:7] if tlc_month else None,
            "driver_share_trend": [{"month": r["month"], "mode": r["mode"], "driver_share": _r(r["driver_share"], 4),
                                    "platform_share": _r(r["platform_share"], 4)} for r in ds],
            "pay_per_hour_trend": [{"month": r["month"], "mode": r["mode"], "pay_per_hour": _r(r["pay_per_hour"], 2)}
                                   for r in pph],
            "event_study": [{"year": r["year"], "week_offset": r["week_offset"], "week_start": r["week_start"],
                             "mode": r["mode"], "pay_per_mile": _r(r["pay_per_mile"], 3),
                             "pay_per_min": _r(r["pay_per_min"], 3), "fare_per_mile": _r(r["fare_per_mile"], 3),
                             "transition": r["transition"]} for r in event],
            "hours": [{"month": r["month"], "license_class": r["license_class"],
                       "trips_per_hour_worked": _r(r["trips_per_hour_worked"], 3),
                       "active_drivers": _int(r["unique_drivers"]), "vehicles_per_day": _int(r["vehicles_per_day"]),
                       "hours_per_day_per_vehicle": _r(r["hours_per_day_per_vehicle"], 2)} for r in hours],
        }

    def prices(self) -> dict:
        m, p = self.month, self.prior
        modes = COMPANIES + ("all",)
        dist = [r for r in self.out.rows("fare_dist") if r["pu_zone"] == 0 and r["mode"] in COMPANIES + ("ride_hail", "all")]
        dist_at = {(r["month"], r["mode"]): r for r in dist}
        vol = self.out.rows("price_volatility")
        vol_at = {(r["month"], r["pu_zone"], r["mode"]): r for r in vol}
        fpm_zone = {(r["month"], r["pu_zone"], r["mode"]): r for r in self.out.rows("fare_dist")}
        by_hour = [r for r in self.out.rows("fare_rates_by_hour") if r["mode"] in modes]
        window = self.out.params("fare_rates_by_hour").get("window")
        by_borough = [r for r in self.out.rows("fare_rates_by_borough") if r["mode"] in modes]
        hour_fpm = {r["hour_of_week"]: r["fare_per_mile"] for r in by_hour if r["mode"] == "all"}
        cheapest, dearest = _argmin(hour_fpm), _argmax(hour_fpm)

        tiles, yoy = self._tiles(
            {"fpm_median": dist_at.get((m, "all"), {}).get("fpm_p50"),
             "volatility": vol_at.get((m, 0, "all"), {}).get("volatility"),
             "cheapest_hour": cheapest, "dearest_hour": dearest},
            {"fpm_median": dist_at.get((p, "all"), {}).get("fpm_p50"),
             "volatility": vol_at.get((p, 0, "all"), {}).get("volatility")})

        zone_vol = [r for r in vol if r["month"] == m and r["pu_zone"] in ZONE_IDS and r["mode"] in COMPANIES]
        widest = max((r for r in zone_vol if r["volatility"] is not None and r["n"] >= VOLATILITY_MIN_TRIPS
                      and r["pu_zone"] in self.pickup_zones),
                     key=lambda r: r["volatility"], default=None)
        company_fpm = {c: dist_at.get((m, c), {}).get("fpm_p50") for c in COMPANIES}
        low_mode, high_mode = _argmin(company_fpm), _argmax(company_fpm)
        borough_fpm = {r["pu_borough"]: r["fare_per_mile"] for r in by_borough
                       if r["mode"] == "all" and r["pu_borough"] in NYC_BOROUGHS}
        top_borough = _argmax(borough_fpm)

        self.price_facts = {"widest": widest}
        return {
            **self.env(),
            "title": findings.prices_title(fpm_median=tiles["fpm_median"], month=m),
            "subtitles": {
                "fpm_by_mode": findings.prices_by_mode(
                    cheapest=(low_mode, company_fpm[low_mode]) if low_mode else None,
                    dearest=(high_mode, company_fpm[high_mode]) if high_mode else None, month=m),
                "fpm_by_hour": findings.prices_by_hour(
                    cheapest=(cheapest, hour_fpm[cheapest]) if cheapest is not None else None,
                    dearest=(dearest, hour_fpm[dearest]) if dearest is not None else None, window=window, month=m),
                "fpm_by_borough": findings.prices_by_borough(borough=top_borough,
                                                             fare_per_mile=borough_fpm.get(top_borough),
                                                             window=window, month=m),
                "volatility_by_zone": findings.prices_volatility(
                    zone_name=self.zone_name(widest["pu_zone"]) if widest else None,
                    mode=widest["mode"] if widest else None, volatility=widest["volatility"] if widest else None,
                    month=m)},
            "tiles": tiles, "yoy": yoy,
            "fpm_by_mode": [{"month": r["month"], "mode": r["mode"], "fpm_p10": _r(r["fpm_p10"], 3),
                             "fpm_p50": _r(r["fpm_p50"], 3), "fpm_p90": _r(r["fpm_p90"], 3),
                             "fpmin_p50": _r(r["fpmin_p50"], 3)} for r in dist],
            "fpm_by_hour": [{"hour_of_week": r["hour_of_week"], "mode": r["mode"],
                             "fare_per_mile": _r(r["fare_per_mile"], 3), "fare_per_min": _r(r["fare_per_min"], 3)}
                            for r in by_hour],
            "fpm_by_borough": [{"borough": r["pu_borough"], "mode": r["mode"],
                                "fare_per_mile": _r(r["fare_per_mile"], 3), "fare_per_min": _r(r["fare_per_min"], 3)}
                               for r in by_borough],
            "volatility_by_zone": [{"zone": r["pu_zone"], "mode": r["mode"], "volatility": _r(r["volatility"], 3),
                                    "fpm_p50": _r(fpm_zone.get((m, r["pu_zone"], r["mode"]), {}).get("fpm_p50"), 3),
                                    "n": r["n"]} for r in zone_vol],
        }

    def quality(self, sizes: dict[str, int]) -> dict:
        validation = None
        if self.summary is not None:
            validation = {key: self.summary.get(key) for key in ("status", "checks", "tie_out", "cbd", "fees")}
        return {
            **self.env(),
            "quality": [{"month": r["month"], "mode": r["mode"], "rows": r["rows"], "valid_rows": r["valid_rows"],
                         "valid_share": _r(r["valid_share"], 4), "f_time": r["f_time"], "f_miles": r["f_miles"],
                         "f_fare": r["f_fare"], "f_zone": r["f_zone"], "f_wait": r["f_wait"]}
                        for r in self.out.rows("quality_month")],
            "validation": validation,
            "cbd_zones": [{"zone": r["LocationID"], "name": self.zone_name(r["LocationID"]),
                           "borderline": r["borderline"], "note": r["note"]} for r in self.cbd_rows],
            "downloads": [{"file": f, "description": d, "bytes": sizes[f]} for f, d in DOWNLOADS.items()],
        }

    def pay_rule(self) -> dict:
        """Ride-hail changes across the new minimum-pay rule (D28): the median week after against the
        median week before, net of the same weeks of the reference year, as L10's report computes
        them (``studies.before_after``; the transition week left out, D12)."""
        event = self.out.rows("pay_event")
        years = sorted({r["year"] for r in event})
        net = {}
        if len(years) >= 2:
            base, year = years[0], years[-1]
            for measure in PAY_RULE_MEASURES:
                before, after = studies.before_after(event, "ride_hail", measure, year)
                ref_before, ref_after = studies.before_after(event, "ride_hail", measure, base)
                change, ref_change = _rel(after, before), _rel(ref_after, ref_before)
                net[measure] = None if change is None or ref_change is None else (1 + change) / (1 + ref_change) - 1
        return {"net": net, "weeks": max((r["week_offset"] for r in event), default=None),
                "base_year": years[0] if len(years) >= 2 else None}

    # --- Q1–Q15 ----------------------------------------------------------------

    def findings(self) -> list[dict | None]:
        """One finding per question, in order; None where an input is missing."""
        m, p = self.month, self.prior
        counts = self.zone_counts()
        rh_share, rh_prior = self.mode_share(m, "ride_hail"), self.mode_share(p, "ride_hail")
        ds = {(r["month"], r["mode"]): r["driver_share"] for r in self.out.rows("driver_share")}
        rule = self.pay_rule()
        dist = {(r["month"], r["mode"]): r["fpm_p50"] for r in self.out.rows("fare_dist") if r["pu_zone"] == 0}
        waits = {(r["mode"]): r["wait_p50"] for r in self.out.rows("wait_time") if r["month"] == m and r["pu_zone"] == 0}
        zone_waits = [r for r in self.out.rows("wait_time")
                      if r["month"] == m and r["pu_zone"] in self.pickup_zones and r["wait_p50"] is not None]
        longest = max(zone_waits, key=lambda r: r["wait_p50"], default=None)
        wav = {r["mode"]: r for r in self.out.rows("wav_service") if r["month"] == m}
        shared = [r for r in self.out.rows("shared_match_rate") if r["mode"] in APPS]
        city = [r for r in shared if r["pu_zone"] == 0]
        requests_now = sum(r["requests"] or 0 for r in city if r["month"] == m)
        matched_now = sum(r["matched"] or 0 for r in city if r["month"] == m)
        requests_prior = sum(r["requests"] or 0 for r in city if r["month"] == p)
        by_zone: dict[int, int] = defaultdict(int)
        for r in shared:
            if r["month"] == m and r["pu_zone"] in self.pickup_zones:
                by_zone[r["pu_zone"]] += r["requests"] or 0
        top_shared = _argmax({z: n or None for z, n in by_zone.items()})
        tips = {r["mode"]: r["tip_rate"] for r in self.out.rows("tip_rate")
                if r["month"] == m and r["pu_borough"] == "all"}
        fees = defaultdict(float)
        fees_prior = 0.0
        for r in self.out.rows("fee_revenue"):
            if r["month"] == m:
                fees[r["mode"]] += r["cbd_fee"] or 0.0
            elif r["month"] == p:
                fees_prior += r["cbd_fee"] or 0.0
        fee_total = sum(fees.values()) if fees else None
        top_fee = _argmax({k: v or None for k, v in fees.items()})
        cp, ap, dv, pr = self.congestion_facts, self.airport_facts, self.driver_facts, self.price_facts
        trips_all = cp["trips_all"]
        widest = pr["widest"]
        return [
            findings.q1(rh_share=rh_share, change=_pts(rh_share, rh_prior), zones_up=counts["rh_up"],
                        zones_total=counts["rh_compared"], month=m),
            findings.q2(all_modes=(trips_all.get("median"), trips_all.get("p10"), trips_all.get("p90")),
                        by_mode=cp["mode_effects"], green_share=cp["green_share"]),
            findings.q3(fpm_effect=cp["fpm_rh"], driver_share_effect=cp["ds_rh"]),
            findings.q4(zones_now=counts["lyft_ahead"], zones_prior=counts["lyft_ahead_prior"], month=m),
            findings.q5(driver_share=ds.get((m, "ride_hail")),
                        change=_pts(ds.get((m, "ride_hail")), ds.get((p, "ride_hail"))),
                        by_company={a: ds.get((m, a)) for a in APPS}, month=m),
            findings.q6(pay_per_min=rule["net"].get("pay_per_min"), pay_per_mile=rule["net"].get("pay_per_mile"),
                        fare_per_mile=rule["net"].get("fare_per_mile"), weeks=rule["weeks"],
                        base_year=rule["base_year"], rule_month=str(self.periods["driver_pay_rise"])),
            findings.q7(fpm_median=dist.get((m, "all")), zone_name=self.zone_name(widest["pu_zone"]) if widest else None,
                        mode=widest["mode"] if widest else None, volatility=widest["volatility"] if widest else None,
                        month=m),
            findings.q8(waits={a: waits.get(a) for a in APPS},
                        longest=(self.zone_name(longest["pu_zone"]), longest["mode"], longest["wait_p50"])
                        if longest else None, month=m),
            findings.q9(mode=ap["top"], top_share=ap["top_share"], airports=ap["airports"],
                        dropoff_only=ap["dropoff_only"], fares=ap["fares"],
                        busiest_hour=ap["busiest_hour"], month=m),
            findings.q10(zones_now=counts["yellow_leads"], zones_prior=counts["yellow_leads_prior"], month=m),
            findings.q11(service={a: (wav.get(a, {}).get("wav_requests"), wav.get(a, {}).get("wav_share"))
                                  for a in APPS}, month=m),
            findings.q12(requests=requests_now if city else None, change=_rel(requests_now, requests_prior),
                         matched_share=matched_now / requests_now if requests_now else None,
                         top_zone=self.zone_name(top_shared) if top_shared else None, month=m),
            findings.q13(rates={c: tips.get(c) for c in COMPANIES}, month=m),
            findings.q14(total=fee_total, change=_rel(fee_total, fees_prior), top_mode=top_fee,
                         top_amount=fees.get(top_fee) if top_fee else None, month=m),
            findings.q15(tph=dv["tlc_now"].get("trips_per_hour_worked"), drivers=dv["tlc_now"].get("unique_drivers"),
                         hours_per_day=dv["tlc_now"].get("hours_per_day_per_vehicle"),
                         tlc_month=dv["tlc_month"]),
        ]

    # --- everything ----------------------------------------------------------

    def build(self, validated: bool, summary: dict | None) -> dict[str, dict]:
        """Every JSON file, keyed by its path under site/src/data/ (the zone map is copied apart)."""
        self.validated, self.summary = validated, summary
        files: dict[str, dict] = {
            "events.json": self.events(),
            "tiles.json": self.tiles(),
            "share_monthly.json": self.share_monthly(),
            "airports.json": self.airports_page(),
            "congestion.json": self.congestion(),
            "drivers.json": self.drivers(),
            "prices.json": self.prices(),
            "zones/index.json": self.zones_index(),
        }
        files["home.json"] = self.home()          # findings read the pages' values above
        for company in COMPANIES:
            files[f"companies/{company}.json"] = self.company(company)
        files.update(self.zone_files())
        sizes = {path: len(dumps(obj).encode()) for path, obj in files.items()}
        files["quality.json"] = self.quality(sizes)
        return files


# --- checks ------------------------------------------------------------------

def load_validation(as_of: str, dev: bool) -> tuple[bool, dict | None]:
    """``(validated, summary)``. Without ``dev``, refuses unless the summary passed and covers ``as_of``."""
    path = validate.summary_path()
    summary = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    if dev:
        return False, summary
    if summary is None:
        raise PublishError(f"{path} not found: run make validate first (or publish --dev for a local preview)")
    if summary.get("status") != "pass":
        raise PublishError(f"validation status is {summary.get('status')!r}, not 'pass': see reports/validation.md")
    if as_of not in summary.get("months_checked", []):
        raise PublishError(f"validation did not check {as_of}, the latest month in the aggregates: "
                           "run make validate again")
    return True, summary


def text_problems(files: dict[str, dict]) -> list[str]:
    """Pages without a title, and questions without a finding."""
    problems = [f"{path}: no title" for path, obj in files.items() if "title" in obj and not obj["title"]]
    found = {f["question"] for f in files["home.json"]["findings"] if f}
    problems += [f"home.json: no finding for {q}" for q in findings.QUESTIONS if q not in found]
    return problems


def budget_problems(sizes: dict[str, int]) -> list[str]:
    """Routes over budget and zone files over their cap (contracts/site/pages.yaml)."""
    pages = yaml.safe_load(PAGES_PATH.read_text(encoding="utf-8"))
    problems = []
    for name, route in pages["routes"].items():
        (key, values), = (route.get("params") or {"_": [None]}).items()
        if isinstance(values, str):
            first, last = (int(v) for v in values.split(".."))
            values = [str(v) for v in range(first, last + 1)]
        for value in values:
            files = [f.format(**{key: value}) for f in route["files"]]
            total = sum(sizes.get(f, 0) for f in files)
            if total > pages["budget_bytes"]:
                problems.append(f"{name} ({files[0]}): {total:,} bytes > {pages['budget_bytes']:,}")
    problems += [f"{path}: {size:,} bytes >= {pages['zone_file_max_bytes']:,}" for path, size in sizes.items()
                 if path.startswith("zones/") and path != "zones/index.json" and size >= pages["zone_file_max_bytes"]]
    return problems


# --- writing -----------------------------------------------------------------

def publish(out_dir: Path | None = None, dev: bool = False, now: datetime | None = None) -> list[Path]:
    """Build every contract file from metric outputs and write it to ``out_dir`` (default site/src/data/).

    Nothing is written unless every check passes; ``dev`` turns validation, text and budget
    failures into warnings and marks every file ``validated: false``."""
    out_dir = Path(out_dir or common.SITE_DATA_DIR)
    generated_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    geojson = zones.geojson_path()
    if map_problems := zones.geojson_problems(geojson):
        raise PublishError("zone map: " + "; ".join(map_problems[:5]))
    site = Site(Outputs(), generated_at=generated_at)
    validated, summary = load_validation(site.as_of, dev)
    files = site.build(validated, summary)

    texts = {path: dumps(obj) for path, obj in files.items()}
    sizes = {path: len(text.encode()) for path, text in texts.items()}
    sizes[GEOJSON] = geojson.stat().st_size
    problems = text_problems(files) + budget_problems(sizes)
    if problems and not dev:
        raise PublishError("; ".join(problems[:10]))
    for problem in problems:
        print(f"publish --dev: {problem}", file=sys.stderr)

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for path, text in texts.items():
        target = out_dir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        written.append(target)
    shutil.copyfile(geojson, out_dir / GEOJSON)
    written.append(out_dir / GEOJSON)
    keep = {path.resolve() for path in written}
    for stale in sorted(out_dir.rglob("*")):
        if stale.is_file() and stale.suffix in (".json", ".geojson") and stale.resolve() not in keep:
            stale.unlink()
    return written


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.publish", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dev", action="store_true",
                        help="write without a passing validation, marked validated: false")
    parser.add_argument("--out", type=Path, default=common.SITE_DATA_DIR,
                        help="output folder (default site/src/data/)")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        written = publish(args.out, dev=args.dev)
    except PublishError as exc:
        print(f"publish: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    note = " (dev: validated false, deploy will refuse it)" if args.dev else ""
    print(f"publish: wrote {len(written)} files to {args.out}{note}")


if __name__ == "__main__":
    main()
