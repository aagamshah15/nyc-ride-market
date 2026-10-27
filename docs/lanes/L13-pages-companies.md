# L13 · Pages: Companies

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, D3 · **Answers** Q4, Q5, Q11, Q12, Q13 · **Data** `companies/{mode}.json`

## Goal

One template, `companies/[company].md`, rendering Uber, Lyft, yellow and green, each with a comparison block against the other three.

## Owns

- `site/src/companies/[company].md`, plus page-only helpers in `site/src/companies/` if needed

## Starts when

- L05 is done. Build on `make site-mock` data; switch to real data once L11 publishes

## Tasks

- [ ] Tiles as pinned in the contract: trips per day, share of NYC trips, median fare per mile, driver share of fare, tip rate
- [ ] Charts: share trend; fare-per-mile distribution; tip rate (for taxis the chart says card-only); accessible (WAV) match rate and shared match rate, which are ride-hail only, with a plain "not reported for this mode" state on taxi pages
- [ ] Comparison block from the `compare` rows
- [ ] Q4 on the Uber and Lyft pages: where Lyft beats Uber on share and whether the gap is growing, from the contract fields
- [ ] D29: the `wav` block is accessible *service*, not a match rate: chart `wav_share` (share of trips in a WAV) and show `wav_requests` (completed WAV-requested trips) from the company file's `wav` rows; caption that unfulfilled requests aren't in TLC's trip records. `compare` uses `wav_share`

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- All four routes build on mock and on real data; nulls render as states, never as zeros

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
