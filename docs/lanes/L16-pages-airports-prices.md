# L16 · Pages: Airports + Prices

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, §9.4 · **Decision** D10 · **Answers** Q9 (airports), Q7 (prices) · **Data** `airports.json`, `prices.json`

## Goal

Who wins the airport trip at JFK, LaGuardia and Newark, at what fare and when; and what riders pay per mile and per minute, and where pricing is most volatile.

## Owns

- `site/src/airports.md`, `site/src/prices.md`

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).

## Tasks

- [ ] Airports: tiles for trips per day, yellow-cab share, fare to Manhattan (mean or median as D10 settles) and busiest hour; bars per airport stacked to 100% by mode, split by direction; hour-of-day pattern; fares by mode
- [ ] Prices: tiles for median fare per mile, price volatility, and cheapest and dearest hour; fare-per-mile strip or box by mode; volatility map (p90 ÷ p10 by zone); fare per minute; borough view

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- Both routes build on mock and on real data; tile labels say mean or median correctly

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
