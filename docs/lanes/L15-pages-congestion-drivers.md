# L15 · Pages: Congestion pricing + Drivers

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, §9.4, §6 · **Answers** Q2, Q3, Q14 (congestion); Q5, Q6, Q15 (drivers) · **Data** `congestion.json`, `drivers.json`

## Goal

The lead case-study page on congestion pricing, and the drivers page on pay, platform share and hours.

## Owns

- `site/src/congestion-pricing.md`, `site/src/drivers.md`

## Starts when

- L05 is done. Build on `make site-mock` data; switch to real data once L11 publishes

## Tasks

- [ ] Congestion: tiles for the change in zone trips vs control, the change in fare per mile and fees collected to date; effect dots with p10–p90 ranges per metric and mode; weekly series; fee revenue by month and mode; results with and without borderline zones; a limits note linking `/methods#congestion-method`
- [ ] Drivers: tiles for pay per hour with a passenger, driver share of fare, trips per hour worked (marked TLC-reported) and active drivers; driver-share trend; the pay-rise event study with the 2024 reference
- [ ] The event study shows fare per mile with driver pay per mile on one shared $/mile axis; pay per minute goes in its own panel (no dual axes)

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- Both routes build on mock and on real data; "estimated effect" wording throughout the congestion page

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
