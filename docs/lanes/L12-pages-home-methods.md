# L12 · Pages: Home + Methods

**Wave** 4 · **Phase** 4–5 · **Spec** §9.1, §9.3, §7.3, §12 · **Data** `home.json`, `share_monthly.json`, `quality.json`

## Goal

The home page (the market at a glance and the top findings) and the methods page every other page links to.

## Owns

- `site/src/index.md`, `site/src/methods.md`

## Starts when

- L05 is done. Build on `make site-mock` data; switch to real data once L11 publishes

## Tasks

- [ ] Home: title from JSON; tiles for trips per day, ride-hail share, platform share and congestion fees last month, each with its change vs a year earlier; share-trend line with the 2025-01-05 and 2025-08-01 rules; top findings linking to their pages; a congestion-pricing slot
- [ ] Methods: sources; cleaning rules and the SPEC §4.2 flag table with flag shares from `quality.json`; the CBD zone list with borderline zones and results with and without them (SPEC §7.3); validation results; congestion and pay-rise methods; tips are card-only for taxis; waits are ride-hail only; known limits (SPEC §12); downloads of the published files
- [ ] Every anchor in `contracts/site/pages.yaml` exists on the methods page

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- Builds on mock and on real data; every anchor resolves; budget test green

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
