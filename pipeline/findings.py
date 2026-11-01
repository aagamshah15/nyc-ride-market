"""Page titles, chart subtitles and the Q1–Q15 finding sentences, built from computed values.

Every sentence on the site comes from here: findings are generated, not typed (SPEC §9.2).
Numbers follow contracts/README.md §3 with the same rules as site/src/components/format.js,
and the wording follows CLAUDE.md: congestion results are "estimated effects", pay per
hour is "per hour with a passenger", and cab tips are "card-only".

Builders take plain values and return a sentence, or ``None`` when a value the sentence
rests on is missing (contracts/README.md §4). Optional clauses drop out on their own.

Lane L11 · SPEC §9.2, §9.3 · docs/lanes/L11-publish.md
"""

from __future__ import annotations

import math
from decimal import ROUND_HALF_UP, Decimal

MINUS = "−"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DAYS = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")   # hour_of_week: Sunday 00:00 = 0

# Mode names inside a sentence (contracts/README.md §2 gives the display names).
NOUNS = {"uber": "Uber", "lyft": "Lyft", "other_hv": "other ride-hail apps", "yellow": "yellow cabs",
         "green": "green cabs", "ride_hail": "ride-hail apps", "taxi": "cabs", "all": "all modes"}
FARE_NOUNS = {"uber": "Uber", "lyft": "Lyft", "other_hv": "other ride-hail", "yellow": "yellow-cab",
              "green": "green-cab"}
AIRPORT_NAMES = {"JFK": "JFK", "LGA": "LaGuardia", "EWR": "Newark"}

# Question → (page it links to, featured on the home page). SPEC App. A: Q1, Q2, Q5, Q9 lead.
QUESTIONS = {
    "Q1": ("/zones", True), "Q2": ("/congestion-pricing", True), "Q3": ("/congestion-pricing", False),
    "Q4": ("/companies/lyft", False), "Q5": ("/drivers", True), "Q6": ("/drivers", False),
    "Q7": ("/prices", False), "Q8": ("/zones", False), "Q9": ("/airports", True),
    "Q10": ("/zones", False), "Q11": ("/companies/uber", False), "Q12": ("/companies/uber", False),
    "Q13": ("/companies/yellow", False), "Q14": ("/congestion-pricing", False), "Q15": ("/drivers", False),
}
# Stored precision of a finding's value, by unit (contracts/README.md §2).
VALUE_DIGITS = {"count": 0, "share": 4, "effect": 4, "usd": 2, "usd_per_mile": 3, "usd_per_minute": 3,
                "usd_per_hour": 2, "seconds": 0, "trips_per_hour": 3, "ratio": 3}


# --- numbers (contracts/README.md §3, as format.js) ---------------------------

def _fixed(x: float, digits: int) -> str:
    """JavaScript ``x.toFixed(digits)`` for ``x >= 0``: the exact binary value, ties rounded up."""
    return str(Decimal(x).quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP))


def _js_round(x: float) -> int:
    """JavaScript ``Math.round``: halves go towards +∞."""
    return math.floor(x + 0.5)


def _sign(v: float) -> str:
    return MINUS if v < 0 else ""


def _signed(v: float, text: str) -> str:
    return ("+" if v > 0 else MINUS if v < 0 else "") + text


def count(n: float) -> str:
    """Exact below 1,000; 3 significant figures with commas; "x.y million" from 10 million."""
    a = abs(n)
    if a < 1000:   # toLocaleString rounds the shortest decimal form of the number, not its binary value
        text = f"{Decimal(repr(a)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP):,f}"
        return _sign(n) + (text[:-2] if text.endswith(".0") else text)
    exact = Decimal(a)
    rounded = exact.quantize(Decimal(1).scaleb(exact.adjusted() - 2), rounding=ROUND_HALF_UP)
    if rounded >= 10_000_000:
        return f"{_sign(n)}{_fixed(a / 1e6, 1)} million"
    return f"{_sign(n)}{int(rounded):,}"


def share(x: float) -> str:
    """A fraction as a percent: 0 decimals at 10% and above, 1 decimal below."""
    p = abs(x * 100)
    return f"{_sign(x)}{_fixed(p, 0 if p >= 9.95 else 1)}%"


def share_change(d: float) -> str:
    """A change in a share as signed percentage points: "+2.1 pts"."""
    v = _js_round(d * 1000) / 10
    return _signed(v, _fixed(abs(v), 1)) + " pts"


def rel_change(x: float) -> str:
    """A relative change or estimated effect as a signed percent: "−7.4%"."""
    v = _js_round(x * 1000) / 10
    return _signed(v, _fixed(abs(v), 1)) + "%"


effect = rel_change


def usd(x: float) -> str:
    """Under $100 with cents; whole dollars to $1 million; "$x.y million" above."""
    a = abs(x)
    if _js_round(a * 100) / 100 < 100:
        return f"{_sign(x)}${_fixed(a, 2)}"
    if a <= 1_000_000:
        return f"{_sign(x)}${_js_round(a):,}"
    return f"{_sign(x)}${_fixed(a / 1e6, 1)} million"


def usd_group(values: list[float]) -> list[str]:
    """Dollars compared side by side: whole dollars for all when any shows as $100 or more, so a
    group never mixes "$124" with "$83.67" (contracts/README.md §3)."""
    if any(_js_round(abs(x) * 100) / 100 >= 100 for x in values) and all(abs(x) <= 1_000_000 for x in values):
        return [f"{_sign(x)}${_js_round(abs(x)):,}" for x in values]
    return [usd(x) for x in values]


def _usd_per(unit: str):
    return lambda x: f"{_sign(x)}${_fixed(abs(x), 2)}/{unit}"


usd_per_mile = _usd_per("mile")
usd_per_minute = _usd_per("min")
usd_per_hour = _usd_per("hour")


def seconds(s: float) -> str:
    """Waits in minutes, 1 decimal."""
    minutes = s / 60
    return f"{'-' if minutes < 0 else ''}{_fixed(abs(minutes), 1)} min"   # format.js uses toFixed here


def trips_per_hour(x: float) -> str:
    return f"{_fixed(x, 2)} trips/hour"


def ratio(x: float) -> str:
    return f"{_fixed(x, 1)}×"


def month_label(value: str) -> str:
    """ "Aug 2026" from "2026-08" or "2026-08-01"."""
    return f"{MONTHS[int(value[5:7]) - 1]} {value[:4]}"


def week_label(value: str) -> str:
    """ "week of 6 Jan 2025" from the week's Monday, "2025-01-06"."""
    return f"week of {int(value[8:10])} {MONTHS[int(value[5:7]) - 1]} {value[:4]}"


def hour_of_day(h: int) -> str:
    return f"{12 if h % 12 == 0 else h % 12} {'am' if h < 12 else 'pm'}"


def hour_of_week(h: int) -> str:
    return f"{DAYS[h // 24]} {hour_of_day(h % 24)}"


BY_UNIT = {"count": count, "share": share, "effect": effect, "usd": usd, "usd_per_mile": usd_per_mile,
           "usd_per_minute": usd_per_minute, "usd_per_hour": usd_per_hour, "seconds": seconds,
           "trips_per_hour": trips_per_hour, "ratio": ratio, "hour_of_day": hour_of_day,
           "hour_of_week": hour_of_week}


# --- words -------------------------------------------------------------------

def _missing(*values) -> bool:
    return any(v is None or (isinstance(v, float) and not math.isfinite(v)) for v in values)


def cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def noun(mode: str) -> str:
    return NOUNS.get(mode, mode)


def possessive(name: str) -> str:
    return name + ("'" if name.endswith("s") else "'s")


def join_and(items: list[str]) -> str:
    items = list(items)
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def zones_count(n: int) -> str:
    return f"{count(n)} zone" + ("" if n == 1 else "s")


def months_count(n: int) -> str:
    return f"{count(n)} month" + ("" if n == 1 else "s")


def whole_trips(n: float) -> str:
    """A trip count as a whole number with its plural: "1 trip", "732 trips", "1,470 trips"."""
    whole = _js_round(n)
    if whole < 1:
        return "fewer than 1 trip"
    return f"{count(whole)} trip" + ("" if whole == 1 else "s")


def _pct_size(x: float) -> str:
    """The size of a relative difference, unsigned: "4.1%"."""
    return rel_change(abs(x)).lstrip("+")


def moved(change: float, kind: str = "pts") -> str:
    """ "rose 2.1 pts", "fell 7.4%" or "held steady", as the change rounds for display."""
    text = share_change(change) if kind == "pts" else rel_change(change)
    if text.startswith("+"):
        return "rose " + text[1:]
    if text.startswith(MINUS):
        return "fell " + text[1:]
    return "held steady"


def against_prior(now: int, prior: int | None) -> str:
    """ ", up from 19 a year earlier" (or down from, or the same as), or "" without a prior."""
    if prior is None:
        return ""
    if now == prior:
        return ", the same as a year earlier"
    return f", {'up' if now > prior else 'down'} from {count(prior)} a year earlier"


def _on_year_earlier(change: float | None, kind: str) -> str:
    if change is None:
        return ""
    return f" ({share_change(change) if kind == 'pts' else rel_change(change)} on a year earlier)"


def rank_words(rank: int, total: int) -> str:
    """ "the lowest", "the second lowest", …, "the highest" for a 0-based rank among ``total``."""
    if rank == 0:
        return "the lowest"
    if rank == total - 1:
        return "the highest"
    if rank < total / 2:
        return f"the {_ordinal(rank + 1)} lowest"
    return f"the {_ordinal(total - rank)} highest"


def _ordinal(n: int) -> str:
    return {2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(n, f"{n}th")


def finding(question: str, text: str | None, value: float | None, unit: str) -> dict | None:
    """A home-page finding (contracts/site/home.example.json), or None without its text."""
    if text is None:
        return None
    page, featured = QUESTIONS[question]
    if value is not None:
        digits = VALUE_DIGITS[unit]
        value = round(value) if digits == 0 else round(value, digits)
    return {"question": question, "text": text, "value": value, "unit": unit, "page": page,
            "featured": featured}


# --- home --------------------------------------------------------------------

def home_title(*, rh_share, month):
    if _missing(rh_share):
        return None
    return f"Ride-hail apps carried {share(rh_share)} of NYC trips in {month_label(month)}"


def home_share_trend(*, mode, change, first_month, month, turn=None):
    """The company whose share moved most between the same month of two years (no season mixed in).
    ``turn``: (verb, month, share) when a year between went beyond both ends, e.g. ("dipped", …)."""
    if _missing(mode, change):
        return None
    text = (f"{possessive(cap(noun(mode)))} share {moved(change)} between {month_label(first_month)} "
            f"and {month_label(month)}, the biggest shift of any company")
    if turn and not _missing(*turn):
        text += f"; it {turn[0]} to {share(turn[2])} in {month_label(turn[1])}"
    return text


# --- companies ---------------------------------------------------------------

def company_title(*, mode, mode_share, month):
    if _missing(mode_share):
        return None
    return f"{cap(noun(mode))} carried {share(mode_share)} of NYC trips in {month_label(month)}"


def company_share_trend(*, mode, change, month, prior):
    if _missing(change):
        return None
    return (f"{possessive(cap(noun(mode)))} share of NYC trips {moved(change)} between "
            f"{month_label(prior)} and {month_label(month)}")


def company_fpm_dist(*, mode, fpm_median, change, p10, p90, month, prior):
    if _missing(fpm_median):
        return None
    if change is None:
        text = f"The median {FARE_NOUNS[mode]} fare per mile was {usd_per_mile(fpm_median)} in {month_label(month)}"
    else:
        text = (f"The median {FARE_NOUNS[mode]} fare per mile {moved(change, 'relative')} between "
                f"{month_label(prior)} and {month_label(month)}, to {usd_per_mile(fpm_median)}")
    if not _missing(p10, p90):
        text += f"; most trips paid {usd_per_mile(p10)} to {usd_per_mile(p90)} (10th to 90th percentile)"
    return text


def company_tip_rate(*, mode, tip_rate, change, card_only, month):
    if _missing(tip_rate):
        return None
    if card_only:
        return (f"Card-only tips on {noun(mode)} came to {share(tip_rate)} of the fare in "
                f"{month_label(month)}{_on_year_earlier(change, 'pts')}; cash tips aren't recorded")
    return (f"{cap(noun(mode))} riders tipped {share(tip_rate)} of the base fare in "
            f"{month_label(month)}{_on_year_earlier(change, 'pts')}")


UNFILLED_WAV = "requests that went unfilled aren't in TLC's records"   # D29: trip records are completed trips


def company_wav(*, mode, service, month):
    """``service``: {"uber": (completed WAV-requested trips, share of trips in a WAV), "lyft": …},
    latest month (D29). There is no match rate: unfilled requests have no trip record."""
    if mode in service:
        requests, wav_share = service[mode]
        if _missing(requests, wav_share):
            return None
        return (f"{cap(noun(mode))} completed {count(requests)} trips that requested a wheelchair-accessible "
                f"vehicle in {month_label(month)}, and {share(wav_share)} of all its trips ran in one; {UNFILLED_WAV}")
    known = [(m, s) for m, (_, s) in service.items() if not _missing(s)]
    if not known:
        return None
    return (f"Wheelchair-accessible service isn't reported for {noun(mode)}; in {month_label(month)}, "
            + join_and([f"{share(s)} of {noun(m)} trips" for m, s in known])
            + f" ran in a wheelchair-accessible vehicle; {UNFILLED_WAV}")


def company_shared(*, mode, requests, matched_share, month):
    """``requests``: {"uber": n, "lyft": n}; ``matched_share`` the page mode's match rate."""
    if mode in requests:
        if _missing(requests[mode]):
            return None
        text = f"{cap(noun(mode))} riders made {count(requests[mode])} shared-ride requests in {month_label(month)}"
        if not _missing(matched_share):
            text += f", and {share(matched_share)} were matched"
        return text
    known = [v for v in requests.values() if not _missing(v)]
    if not known:
        return None
    return (f"Shared rides aren't reported for {noun(mode)}; Uber and Lyft riders made {count(sum(known))} "
            f"shared-ride requests in {month_label(month)}")


def company_compare(*, mode, fpm_medians, month):
    """``fpm_medians``: {company: median fare per mile} for the latest month."""
    known = sorted((v, m) for m, v in fpm_medians.items() if not _missing(v))
    if _missing(fpm_medians.get(mode)) or len(known) < 2:
        return None
    rank = [m for _, m in known].index(mode)
    return (f"The median {FARE_NOUNS[mode]} fare per mile, {usd_per_mile(fpm_medians[mode])} in "
            f"{month_label(month)}, was {rank_words(rank, len(known))} of {count(len(known))} companies")


def lyft_vs_uber(*, zones_now, zones_prior, month):
    if _missing(zones_now):
        return None
    return (f"Lyft had a bigger share of pickups than Uber in {zones_count(zones_now)} in "
            f"{month_label(month)}{against_prior(zones_now, zones_prior)}")


# --- zones index -------------------------------------------------------------

def zones_title(*, zones_now, zones_prior, month):
    if _missing(zones_now):
        return None
    return (f"Yellow cabs led pickups in {zones_count(zones_now)} in {month_label(month)}"
            f"{against_prior(zones_now, zones_prior)}")


def zones_level_map(*, majority, total, month):
    if _missing(majority, total) or total == 0:
        return None
    return (f"Ride-hail apps carried at least half of pickups in {count(majority)} of "
            f"{zones_count(total)} in {month_label(month)}")


def zones_change_map(*, rose, total, month, prior):
    if _missing(rose, total) or total == 0:
        return None
    return (f"Ride-hail share of pickups rose in {count(rose)} of {zones_count(total)} between "
            f"{month_label(prior)} and {month_label(month)}")


def zones_yellow_map(*, zones_now, zones_prior, month):
    if _missing(zones_now):
        return None
    return (f"Yellow cabs carried more pickups than any other mode in {zones_count(zones_now)} in "
            f"{month_label(month)}{against_prior(zones_now, zones_prior)}")


def zones_table(*, name, trips_per_day, month):
    if _missing(name, trips_per_day):
        return None
    return f"{name} was the busiest pickup zone in {month_label(month)}, with {count(trips_per_day)} trips a day"


# --- one zone ----------------------------------------------------------------

def zone_title(*, name, rh_share, trips, thin, month, airport=False):
    """``airport``: pickups are "at" an airport zone and "in" any other."""
    where = f"{'at' if airport else 'in'} {name}"
    if thin:
        if not trips:
            return f"No pickups were recorded {where} in {month_label(month)}"
        return f"{name} had {count(trips)} pickups in {month_label(month)}, too few to profile"
    if _missing(rh_share):
        return None
    return f"Ride-hail apps carried {share(rh_share)} of pickups {where} in {month_label(month)}"


def zone_share_trend(*, apps, rh_share, change, month):
    """``apps``: [(mode, share of the zone's pickups)] in the latest month for the apps the chart
    draws as lines, one clause each; the ride-hail total, which isn't a line, comes after them."""
    known = [(m, s) for m, s in apps if not _missing(s)]
    if not known:
        if _missing(rh_share):
            return None
        return (f"Ride-hail apps carried {share(rh_share)} of pickups here in {month_label(month)}"
                f"{_on_year_earlier(change, 'pts')}")
    (first, first_share), *rest = known
    text = (f"{possessive(cap(noun(first)))} share of pickups here was {share(first_share)}"
            + "".join(f"{',' if i < len(rest) - 1 else ' and'} {possessive(noun(m))} {share(s)}"
                      for i, (m, s) in enumerate(rest))
            + f" in {month_label(month)}")
    if _missing(rh_share):
        return text
    total = f"ride-hail apps together {share(rh_share)}"
    if change is not None:
        total += f", {share_change(change)} on a year earlier"
    return f"{text} ({total})"


def zone_hour_heatmap(*, mode, peak_hour, peak_trips, window, month):
    """``mode``, ``peak_hour``, ``peak_trips``: the single largest cell of the per-mode grids, as
    drawn (average trips a week in that hour of the week)."""
    if _missing(mode, peak_hour, peak_trips):
        return None
    return (f"{cap(FARE_NOUNS.get(mode, noun(mode)))} pickups here peaked on {hour_of_week(peak_hour)}, with "
            f"{whole_trips(peak_trips)} in that hour in an average week over the {count(window)} months to "
            f"{month_label(month)}")


def zone_waits(*, mode, wait_p50, thin, month):
    if thin or _missing(mode, wait_p50):
        return f"Too few ride-hail trips here in {month_label(month)} to report waits"
    return (f"{noun(mode)} riders here waited a median {seconds(wait_p50)} from request to pickup in "
            f"{month_label(month)}")


# Pickup charts on a zone whose pickups aren't TLC trips (Newark Airport): what each chart can't show.
NOT_TLC_PICKUPS = {"share_trend": "these shares don't show who serves the airport",
                   "hour_heatmap": "these hours don't show when TLC vehicles serve it",
                   "waits": "there are no waits to report",
                   "top_destinations": "these destinations don't describe trips from the airport"}


def zone_not_tlc_title(*, name, dropoffs_per_day, month):
    """Title for a zone whose pickup records aren't TLC trips: what TLC vehicles do there is drop off."""
    if _missing(dropoffs_per_day):
        return f"Pickups at {name} aren't TLC trips"
    return (f"TLC vehicles dropped off {count(dropoffs_per_day)} trips a day at {name} in {month_label(month)}; "
            f"pickups there aren't TLC trips")


def zone_not_tlc(*, name, chart):
    return f"Pickups at {name} aren't TLC trips, so {NOT_TLC_PICKUPS[chart]}"


def zone_top_destinations(*, name, dest_share, left_city_share, month):
    """``name``: the top destination among the mapped zones. ``left_city_share``: the share of trips
    to "Outside of NYC" when it outranks every mapped zone, else None."""
    left = "" if _missing(left_city_share) else f"; {share(left_city_share)} of trips left the city"
    if _missing(name):
        where = "in the city " if left else ""
        return f"No destination {where}had enough trips from here in {month_label(month)} to list{left}"
    text = f"{name} was the top destination from here in {month_label(month)}"
    if not _missing(dest_share):
        text += f", with {share(dest_share)} of trips"
    return text + left


# --- airports ----------------------------------------------------------------

def airports_list(codes: list[str]) -> str:
    return join_and([AIRPORT_NAMES.get(code, code) for code in codes])


def airports_title(*, mode, top_share, airports, dropoff_only, month):
    """``airports``: counted both ways; ``dropoff_only``: counted for trips to the airport only."""
    places = ([f"to and from {airports_list(airports)}"] if airports else []) + \
             ([f"to {airports_list(dropoff_only)}"] if dropoff_only else [])
    if _missing(mode, top_share) or not places:
        return None
    return f"{cap(noun(mode))} carried {share(top_share)} of trips {' and '.join(places)} in {month_label(month)}"


def airports_split(*, leaders, month):
    """``leaders``: [(airport, mode, share)] for pickups at each airport, latest month."""
    if not leaders:
        return None
    groups: dict[str, list[str]] = {}
    for airport, mode, mode_share in leaders:
        groups.setdefault(mode, []).append(f"{AIRPORT_NAMES.get(airport, airport)} ({share(mode_share)})")
    parts = [f"{noun(mode)} led pickups at {join_and(places)}" for mode, places in groups.items()]
    return f"In {month_label(month)}, " + "; ".join(parts)


def airports_share_trend(*, changes, month, prior):
    """``changes``: [(airport, change in yellow cabs' share of its trips)], one per line the chart draws."""
    known = [(a, c) for a, c in changes if not _missing(c)]
    if not known:
        return None
    parts, last_verb = [], None
    for airport, change in known:
        verb, _, size = moved(change).partition(" ")   # "fell", "2.4 pts"; "held", "steady"
        text = moved(change) if verb != last_verb or verb == "held" else size
        parts.append(f"{text} at {AIRPORT_NAMES.get(airport, airport)}")
        last_verb = verb
    return (f"Yellow cabs' share of trips {join_and(parts)} between {month_label(prior)} and "
            f"{month_label(month)}")


def airports_by_hour(*, hour, trips_per_day, window, month):
    if _missing(hour, trips_per_day):
        return None
    return (f"Airport trips peaked at {hour_of_day(hour)}, with {count(trips_per_day)} trips in that hour on "
            f"an average day over the {count(window)} months to {month_label(month)}")


def airports_fares(*, ranges, month):
    """``ranges``: [(airport, (cheapest mode, mean fare), (dearest mode, mean fare))] to Manhattan,
    one per panel the chart draws; each airport's two fares share a format (usd_group)."""
    clauses = []
    for airport, cheapest, dearest in ranges:
        if not cheapest or not dearest or _missing(cheapest[1], dearest[1]):
            continue
        place = f"for trips from {AIRPORT_NAMES.get(airport, airport)}"
        if cheapest[0] == dearest[0]:
            clauses.append(f"at {usd(cheapest[1])} by {noun(cheapest[0])} {place}")
            continue
        low, high = usd_group([cheapest[1], dearest[1]])
        clauses.append(f"from {low} by {noun(cheapest[0])} to {high} by {noun(dearest[0])} {place}")
    if not clauses:
        return None
    joined = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + ", and " + clauses[-1]
    return f"Mean fares to Manhattan before tip in {month_label(month)} ran {joined}"


# --- congestion pricing ------------------------------------------------------

def congestion_title(*, trips_effect):
    if _missing(trips_effect):
        return None
    return f"Congestion pricing had an estimated effect of {effect(trips_effect)} on trips touching the zone"


def _main_effects(by_mode: dict) -> list[tuple[str, float]]:
    """Ride-hail and yellow cabs, the modes Q2 reads by (combined ride-hail, as L10's report does)."""
    return [(m, by_mode[m]) for m in ("ride_hail", "yellow") if not _missing(by_mode.get(m))]


def _green_effect(by_mode: dict, green_share) -> str:
    """Green cabs apart, with their share of NYC trips so the reader sees how small they are."""
    if _missing(by_mode.get("green")):
        return ""
    size = "" if _missing(green_share) else f", {share(green_share)} of NYC trips,"
    return f"green cabs{size} came out at {effect(by_mode['green'])}"


def congestion_effects(*, by_mode, green_share):
    """``by_mode``: median weekly estimated effect on trips, core list, for ride_hail, yellow and green."""
    main = _main_effects(by_mode)
    if not main:
        return None
    text = ("By mode, the estimated effect on trips touching the zone was "
            + join_and([f"{effect(v)} for {noun(m)}" for m, v in main]))
    green = _green_effect(by_mode, green_share)
    return text + (f"; {green}" if green else "")


def congestion_weekly_effect(*, p10, p90):
    if _missing(p10, p90):
        return None
    return (f"Weekly estimated effects on trips touching the zone ran from {effect(p10)} to {effect(p90)} "
            f"(10th to 90th percentile of weeks)")


def congestion_weekly_trips(*, treated_change, control_change, year, base_year):
    if _missing(treated_change, control_change):
        return None
    return (f"In {year}, trips touching the zone {moved(treated_change, 'relative')} on the same weeks of "
            f"{base_year}, while trips elsewhere {moved(control_change, 'relative')}")


def congestion_fees(*, total, first_month, month, top_mode, top_share):
    if _missing(total) or total == 0:
        return None
    text = (f"Trips were charged {usd(total)} in congestion fees from {month_label(first_month)} to "
            f"{month_label(month)}")
    if not _missing(top_mode, top_share):
        text += f"; {noun(top_mode)} trips paid the most, {share(top_share)} of it"
    return text


def congestion_zone_change(*, fell, total, fell_cbd, total_cbd, year, base_year):
    if _missing(fell, total) or total == 0:
        return None
    text = f"Pickups per day fell in {count(fell)} of {zones_count(total)} from {base_year} to {year}"
    if total_cbd:
        text += f", including {count(fell_cbd)} of the {count(total_cbd)} in the congestion zone"
    return text


# --- drivers -----------------------------------------------------------------

def drivers_title(*, driver_share, month):
    if _missing(driver_share):
        return None
    return f"Drivers received {share(driver_share)} of ride-hail base fares in {month_label(month)}"


def drivers_share_trend(*, changes, month, prior):
    """``changes``: {"uber": change in driver share, "lyft": …} vs a year earlier."""
    parts = [f"{moved(change)} on {noun(mode)}" for mode, change in changes.items() if change is not None]
    if not parts:
        return None
    return (f"Drivers' share of the base fare {join_and(parts)} between {month_label(prior)} and "
            f"{month_label(month)}")


def drivers_pay_per_hour(*, pay_per_hour, change, month):
    if _missing(pay_per_hour):
        return None
    return (f"Ride-hail drivers earned {usd(pay_per_hour)} per hour with a passenger in "
            f"{month_label(month)}{_on_year_earlier(change, 'relative')}")


def drivers_event_study(*, pay_per_min, pay_per_mile, weeks, base_year):
    """Ride-hail changes across the new minimum-pay rule (D28): median week after against median
    week before, net of the same weeks of ``base_year`` (as L10's report)."""
    if _missing(pay_per_min, weeks, base_year):
        return None
    text = f"Net of the same weeks of {base_year}, ride-hail driver pay per minute with a passenger "
    text += moved(pay_per_min, "relative")
    if not _missing(pay_per_mile):
        text += f" and pay per mile {moved(pay_per_mile, 'relative')}"
    return text + (f" in the {count(weeks)} weeks after the new minimum-pay rule, against the "
                   f"{count(weeks)} weeks before")


def drivers_hours(*, tph, tlc_month):
    """``tph``: {"ride_hail": trips per hour worked, "yellow": …, "green": …}, TLC-reported."""
    if _missing(tph.get("ride_hail")):
        return None
    text = f"Ride-hail vehicles made {trips_per_hour(tph['ride_hail'])} worked in {month_label(tlc_month)}"
    others = [f"{trips_per_hour(v)} for {noun(mode)}" for mode, v in tph.items()
              if mode != "ride_hail" and not _missing(v)]
    if others:
        text += ", against " + join_and(others)
    return text + " (TLC-reported)"


# --- prices ------------------------------------------------------------------

def prices_title(*, fpm_median, month):
    if _missing(fpm_median):
        return None
    return f"Riders paid a median {usd_per_mile(fpm_median)} in {month_label(month)}"


def prices_by_mode(*, cheapest, dearest, month):
    """``cheapest`` and ``dearest``: (mode, median fare per mile), latest month."""
    if not cheapest or not dearest or cheapest[0] == dearest[0]:
        return None
    return (f"{cap(noun(cheapest[0]))} had the lowest median fare per mile in {month_label(month)}, "
            f"{usd_per_mile(cheapest[1])}, and {noun(dearest[0])} the highest, {usd_per_mile(dearest[1])}")


def prices_by_hour(*, cheapest, dearest, window, month):
    """``cheapest`` and ``dearest``: (hour of week, fare per mile), all modes."""
    if not cheapest or not dearest:
        return None
    return (f"Fares per mile were lowest on {hour_of_week(cheapest[0])} ({usd_per_mile(cheapest[1])}) and "
            f"highest on {hour_of_week(dearest[0])} ({usd_per_mile(dearest[1])}) over the {count(window)} "
            f"months to {month_label(month)}")


def prices_by_borough(*, borough, fare_per_mile, window, month):
    if _missing(borough, fare_per_mile):
        return None
    return (f"{borough} had the highest overall fare per mile (total fares ÷ total miles), "
            f"{usd_per_mile(fare_per_mile)} across all modes, over the {count(window)} months to {month_label(month)}")


def prices_volatility(*, zone_name, mode, volatility, month):
    if _missing(zone_name, mode, volatility):
        return None
    return (f"Fares per mile varied most for {FARE_NOUNS.get(mode, mode)} trips from {zone_name} in "
            f"{month_label(month)}, where the 90th-percentile fare per mile was {ratio(volatility)} the 10th")


# --- methods: data quality and the validation gate ------------------------------
# Public sentences for the gate's checks. The gate's own one-line summaries are QA text (decision
# ids, licence classes, "YYYY-MM"); these say the same in the site's words.

CHECK_STATUS = {"fail": "This check failed in the latest run", "skipped": "This check was skipped in the latest run"}


def check_fallback(status: str) -> str:
    return CHECK_STATUS.get(status, "This check passed in the latest run")


def _month_span(months: list[str]) -> str:
    """ "in Aug 2025", or "in 7 months from May 2025 to Nov 2025"."""
    months = sorted(months)
    if len(months) == 1:
        return f"in {month_label(months[0])}"
    return f"in {months_count(len(months))} from {month_label(months[0])} to {month_label(months[-1])}"


def quality_valid_share(*, lowest, below, total, floor_pct):
    """``lowest``: (mode, month, valid share), the lowest point on the chart; ``below``: month and
    mode rows under the gate's floor, of ``total``."""
    if not lowest or _missing(*lowest):
        return None
    mode, month, value = lowest
    text = f"{cap(noun(mode))} had the lowest share of valid records, {share(value)} in {month_label(month)}"
    if below:
        return text + f"; {count(below)} of {count(total)} month and mode results were below the {floor_pct}% floor"
    return text + f"; every month and mode was at least {floor_pct}% valid"


def _ride_hail_tie_out(*, within, checked, exceptions, skipped, tolerance_pct):
    """The head of both tie-out sentences: the gated ride-hail rows."""
    if not checked:
        text = "No month of ride-hail trips could be checked against TLC's monthly figures"
    elif within == checked:
        text = (f"Ride-hail trips per day were within {tolerance_pct}% of TLC's monthly figures in "
                f"{'the' if checked == 1 else 'all'} {months_count(checked)} checked")
    else:
        text = (f"Ride-hail trips per day were within {tolerance_pct}% of TLC's monthly figures in {count(within)} "
                f"of {months_count(checked)} checked")
    if exceptions:
        listed = join_and([f"{month_label(m)} ({rel_change(d)})" for m, d in exceptions])
        text += f", and {listed} {'is a documented exception' if len(exceptions) == 1 else 'are documented exceptions'}"
    if skipped:
        text += (f"; {join_and([month_label(m) for m in skipped])} "
                 f"{'isn' if len(skipped) == 1 else 'aren'}'t in TLC's figures yet")
    return text


def quality_tie_out(*, within, checked, exceptions, skipped, cab_gaps, tolerance_pct):
    """Chart subtitle. ``exceptions``: [(month, diff)]; ``skipped``: months not yet in TLC's figures;
    ``cab_gaps``: [(mode, the diff furthest from zero)] for the cab lines, which don't gate."""
    text = _ride_hail_tie_out(within=within, checked=checked, exceptions=exceptions, skipped=skipped,
                              tolerance_pct=tolerance_pct)
    gaps = [(m, d) for m, d in cab_gaps if not _missing(d)]
    clauses = []
    for i, (m, d) in enumerate(gaps):
        side = ("above" if d >= 0 else "below") + (" TLC's" if i == 0 else "")
        clauses.append(f"{_pct_size(d)} {side} for {noun(m)}")
    if clauses:
        text += "; cab figures, which don't gate, ran up to " + join_and(clauses)
    return text


def check_tie_out_text(*, status, within, checked, exceptions, skipped, cabs, tolerance_pct):
    """``cabs``: [(mode, months more than the tolerance off, months checked)], reported, not gated."""
    if checked is None:
        return check_fallback(status)
    text = _ride_hail_tie_out(within=within, checked=checked, exceptions=exceptions, skipped=skipped,
                              tolerance_pct=tolerance_pct)
    parts, said_off = [], False
    for m, off, n in cabs:
        if not n:
            continue
        if not off:
            parts.append(f"{noun(m)} were within {tolerance_pct}% in every month")
        else:      # the second "more than 2% off" goes without saying
            parts.append(f"{noun(m)} {'' if said_off else f'were more than {tolerance_pct}% off '}in {count(off)} "
                         f"of {months_count(n) if not said_off else count(n)}")
            said_off = True
    if parts:
        text += (". Cab figures follow TLC counting rules the trip files can't reproduce, so they're reported but "
                 f"don't gate: {join_and(parts)}")
    return text


def check_quality_text(*, status, total, below, floor_pct, drift, drift_points):
    """``drift``: [(mode, [months])] more than ``drift_points`` points below the mode's median."""
    if not total:
        return check_fallback(status)
    if below:
        text = f"{count(below)} of {count(total)} month and mode results had less than {floor_pct}% valid records"
    else:
        text = (f"{'The' if total == 1 else 'All'} {count(total)} month and mode "
                f"{'result' if total == 1 else 'results'} had at least {floor_pct}% valid records")
    listed = [(m, months) for m, months in drift if months]
    if listed:
        n = sum(len(months) for _, months in listed)
        text += (f"; {count(n)} {'was' if n == 1 else 'were'} more than {drift_points} points below their mode's "
                 f"median share: " + join_and([f"{noun(m)} {_month_span(months)}" for m, months in listed]))
    else:
        text += f"; none was more than {drift_points} points below its mode's median share"
    return text


def check_cbd_text(*, status, core, wide, min_pct, first_month, last_month):
    """``core``, ``wide``: (share of trips with both ends in the zone list that carry a fee, share of
    trips with neither end in it that carry one), or None. Only the core list gates, so ``status``
    is its result."""
    if not core or _missing(core[0]):
        return check_fallback(status)
    both, neither = core
    text = (f"From {month_label(first_month)} to {month_label(last_month)}, {share(both)} of trips with both ends "
            f"in the congestion zone carried a congestion fee, {'against' if status == 'pass' else 'below'} the "
            f"{min_pct}% needed")
    if not _missing(neither):
        text += f"; {share(neither)} of trips with neither end in it did too, by passing through"
    if wide and not _missing(wide[0]):
        text += f". Counting the borderline zones as in the zone, {share(wide[0])} did (reported, not gated)"
    return text


def check_schema_text(*, status, first_month, last_month):
    span = f"{month_label(first_month)} to {month_label(last_month)}"
    if status == "pass":
        return (f"Every column in every monthly trip file, {span}, maps to the site's unified table, with none "
                "missing or of the wrong type")
    if status == "fail":
        return f"Some monthly trip files, {span}, have columns that are unmapped, missing or of the wrong type"
    return check_fallback(status)


def check_fees_text(*, status, rows, min_pct):
    """``rows``: [(mode, fee set for the mode, share of fee-paying trips charged exactly it, status)]."""
    known = [r for r in rows if not _missing(r[1], r[2])]
    if not known:
        return check_fallback(status)
    failed = [r for r in known if r[3] == "fail"]
    if failed:
        return (f"Fewer than {min_pct}% of fee-paying trips were charged exactly the fee set for "
                + join_and([f"{noun(m)} ({share(s)})" for m, _, s, _ in failed]))
    fees: dict[float, list[str]] = {}
    for m, fee, _, _ in known:
        fees.setdefault(fee, []).append(noun(m))
    low, high = share(min(r[2] for r in known)), share(max(r[2] for r in known))
    size = low if low == high else f"{low} to {high}"
    return (f"{size} of each mode's trips with a congestion fee were charged exactly the fee set for it ("
            + "; ".join(f"{usd(fee)} for {join_and(names)}" for fee, names in fees.items())
            + f"), against the {min_pct}% needed")


# --- Q1–Q15 (home findings) ----------------------------------------------------

def q1(*, rh_share, change, zones_up, zones_total, month):
    if _missing(rh_share):
        return finding("Q1", None, None, "share")
    text = f"Ride-hail apps carried {share(rh_share)} of NYC trips in {month_label(month)}"
    text += _on_year_earlier(change, "pts")
    if not _missing(zones_up, zones_total) and zones_total:
        text += f", and their share of pickups rose in {count(zones_up)} of {zones_count(zones_total)}"
    return finding("Q1", text, rh_share, "share")


def q2(*, all_modes, by_mode, green_share):
    """``all_modes``: (median, p10, p90) estimated effect on trips, all modes, core zone list;
    ``by_mode``: {mode: median} for ride_hail, yellow and green; ``green_share``: green's share of trips."""
    if not all_modes or _missing(all_modes[0]):
        return finding("Q2", None, None, "effect")
    median, p10, p90 = all_modes
    text = f"Congestion pricing had an estimated effect of {effect(median)} on trips touching the zone"
    if not _missing(p10, p90):
        text += f" (weekly range {effect(p10)} to {effect(p90)})"
    if main := _main_effects(by_mode):
        text += "; by mode, " + join_and([f"{noun(m)} {effect(v)}" for m, v in main])
        if green := _green_effect(by_mode, green_share):
            text += f", while {green}"
    return finding("Q2", text, median, "effect")


def q3(*, fpm_effect, driver_share_effect):
    if _missing(fpm_effect):
        return finding("Q3", None, None, "effect")
    text = (f"For ride-hail trips touching the zone, congestion pricing had an estimated effect of "
            f"{effect(fpm_effect)} on fare per mile")
    if not _missing(driver_share_effect):
        text += f" and {effect(driver_share_effect)} on the driver share of the base fare"
    return finding("Q3", text, fpm_effect, "effect")


def q4(*, zones_now, zones_prior, month):
    return finding("Q4", lyft_vs_uber(zones_now=zones_now, zones_prior=zones_prior, month=month),
                   zones_now, "count")


def q5(*, driver_share, change, by_company, month):
    if _missing(driver_share):
        return finding("Q5", None, None, "share")
    text = (f"Drivers received {share(driver_share)} of ride-hail base fares in {month_label(month)}"
            f"{_on_year_earlier(change, 'pts')}")
    parts = [f"{noun(m)} {share(v)}" for m, v in by_company.items() if not _missing(v)]
    if parts:
        text += ": " + join_and(parts)
    return finding("Q5", text, driver_share, "share")


def q6(*, pay_per_min, pay_per_mile, fare_per_mile, weeks, base_year, rule_month):
    """Each a change net of the same weeks of ``base_year``: the median week in the ``weeks`` after
    the new minimum-pay rule against the median week before (D28; L10's pay-rule report)."""
    if _missing(pay_per_min, weeks, base_year):
        return finding("Q6", None, None, "effect")
    text = (f"Over the {count(weeks)} weeks after the new minimum-pay rule of {month_label(rule_month)}, which "
            f"lowered the per-mile floor and raised the per-minute floor, ride-hail driver pay per minute with "
            f"a passenger {moved(pay_per_min, 'relative')}")
    if not _missing(pay_per_mile):
        text += f" and pay per mile {moved(pay_per_mile, 'relative')}"
    text += f" against the {count(weeks)} weeks before, net of the same weeks of {base_year}"
    if not _missing(fare_per_mile):
        text += f"; base fare per mile {moved(fare_per_mile, 'relative')}"
    return finding("Q6", text, pay_per_min, "effect")


def q7(*, fpm_median, zone_name, mode, volatility, month):
    text = prices_title(fpm_median=fpm_median, month=month)
    if text and not _missing(zone_name, mode, volatility):
        text += (f"; fares per mile varied most for {FARE_NOUNS.get(mode, mode)} trips from {zone_name}, where the "
                 f"90th percentile was {ratio(volatility)} the 10th")
    return finding("Q7", text, fpm_median, "usd_per_mile")


def q8(*, waits, longest, month):
    """``waits``: {"uber": city-wide median wait, "lyft": …}; ``longest``: (zone name, mode, wait)."""
    known = [(m, w) for m, w in waits.items() if not _missing(w)]
    if not known:
        return finding("Q8", None, None, "seconds")
    first_mode, first_wait = known[0]
    text = (f"{noun(first_mode)} riders waited a median {seconds(first_wait)} from request to pickup in "
            f"{month_label(month)}")
    text += "".join(f", {noun(m)} riders {seconds(w)}" for m, w in known[1:])
    if longest and not _missing(*longest):
        text += f"; the longest median wait was {seconds(longest[2])}, for {noun(longest[1])} riders in {longest[0]}"
    return finding("Q8", text, first_wait, "seconds")


def q9(*, mode, top_share, airports, dropoff_only, fares, busiest_hour, month):
    """``fares``: [(airport, mean fare to Manhattan)], each airport on its own (a blend would hide the gap)."""
    text = airports_title(mode=mode, top_share=top_share, airports=airports, dropoff_only=dropoff_only, month=month)
    if text:
        known = [(a, f) for a, f in fares if not _missing(f)]
        if known:
            text += ("; the mean fare to Manhattan before tip was "
                     + join_and([f"{usd(f)} from {AIRPORT_NAMES.get(a, a)}" for a, f in known]))
        if not _missing(busiest_hour):
            text += f", and trips peaked at {hour_of_day(busiest_hour)}"
    return finding("Q9", text, top_share, "share")


def q10(*, zones_now, zones_prior, month):
    return finding("Q10", zones_yellow_map(zones_now=zones_now, zones_prior=zones_prior, month=month),
                   zones_now, "count")


def q11(*, service, month):
    """``service``: {"uber": (completed WAV-requested trips, share of trips in a WAV), "lyft": …} (D29)."""
    known = [(m, n, s) for m, (n, s) in service.items() if not _missing(n, s)]
    if not known:
        return finding("Q11", None, None, "count")
    first, requests, _ = known[0]
    text = (f"{noun(first)} completed {count(requests)} trips that requested a wheelchair-accessible vehicle in "
            f"{month_label(month)}" + "".join(f" and {noun(m)} {count(n)}" for m, n, _ in known[1:])
            + ", and " + join_and([f"{share(s)} of {possessive(noun(m))} trips" for m, _, s in known])
            + f" ran in one; {UNFILLED_WAV}")
    return finding("Q11", text, requests, "count")


def q12(*, requests, change, matched_share, top_zone, month):
    if _missing(requests):
        return finding("Q12", None, None, "count")
    text = (f"Uber and Lyft riders made {count(requests)} shared-ride requests in {month_label(month)}"
            f"{_on_year_earlier(change, 'relative')}")
    if not _missing(matched_share):
        text += f", and {share(matched_share)} were matched"
    if not _missing(top_zone):
        text += f"; the most came from {top_zone}"
    return finding("Q12", text, requests, "count")


def q13(*, rates, month):
    """``rates``: {company: tip rate}; cab rates are card-only (SPEC §6)."""
    hv = [(m, r) for m, r in rates.items() if m not in ("yellow", "green") and not _missing(r)]
    cabs = [(m, r) for m, r in rates.items() if m in ("yellow", "green") and not _missing(r)]
    if not hv and not cabs:
        return finding("Q13", None, None, "share")
    parts = []
    if hv:
        parts.append(f"riders tipped {share(hv[0][1])} of the base fare on {noun(hv[0][0])}"
                     + "".join(f" and {share(r)} on {noun(m)}" for m, r in hv[1:]) + f" in {month_label(month)}")
    if cabs:
        parts.append(f"card-only tips came to {share(cabs[0][1])} of the fare on {noun(cabs[0][0])}"
                     + "".join(f" and {share(r)} on {noun(m)}" for m, r in cabs[1:])
                     + ("" if hv else f" in {month_label(month)}"))
    value = (hv or cabs)[0][1]
    return finding("Q13", cap("; ".join(parts)), value, "share")


def q14(*, total, change, top_mode, top_amount, month):
    if _missing(total):
        return finding("Q14", None, None, "usd")
    text = (f"Trips were charged {usd(total)} in congestion fees in {month_label(month)}"
            f"{_on_year_earlier(change, 'relative')}")
    if not _missing(top_mode, top_amount):
        text += f"; {noun(top_mode)} trips paid the most, {usd(top_amount)}"
    return finding("Q14", text, total, "usd")


def q15(*, tph, drivers, hours_per_day, tlc_month):
    if _missing(tph):
        return finding("Q15", None, None, "trips_per_hour")
    text = f"TLC reports that ride-hail vehicles made {trips_per_hour(tph)} worked in {month_label(tlc_month)}"
    if not _missing(hours_per_day):
        text += f", on the road {_fixed(hours_per_day, 1)} hours a day"
    if not _missing(drivers):
        text += f", with {count(drivers)} drivers active"
    return finding("Q15", text, tph, "trips_per_hour")
