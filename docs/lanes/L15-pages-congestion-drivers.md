# L15 · Pages: Congestion pricing + Drivers

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, §9.4, §6 · **Answers** Q2, Q3, Q14 (congestion); Q5, Q6, Q15 (drivers) · **Data** `congestion.json`, `drivers.json`

## Goal

The lead case-study page on congestion pricing, and the drivers page on pay, platform share and hours.

## Owns

- `site/src/congestion-pricing.md`, `site/src/drivers.md`

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).

## Tasks

- [x] Congestion: tiles for the change in zone trips vs control, the change in fare per mile and fees collected to date; effect dots with p10–p90 ranges per metric and mode; weekly series; fee revenue by month and mode; results with and without borderline zones; a limits note linking `/methods#congestion-method`
- [x] Drivers: tiles for pay per hour with a passenger, driver share of fare, trips per hour worked (marked TLC-reported) and active drivers; driver-share trend; the pay-rise event study with the 2024 reference
- [x] The event study shows fare per mile with driver pay per mile on one shared $/mile axis; pay per minute goes in its own panel (no dual axes)
- [x] D28: time charts on the drivers page draw all events from `events.json` (three since D28: 1 Mar 2025 per-minute inflation step, 1 Aug 2025 "New driver minimum-pay rule"); never write "5% rise" in page text

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
| 31 Oct 2026 | ready for hand-off | Both pages built on the real data (as of 2026-08) and on mock data; `make test` green. Two Blocked notes for the integrator (fee chart events, sensitivity subtitle) |
| | not started | |

**Blocked:**
- **L05 · `monthlyColumns` has no `events` option.** The fee chart (`congestion.json` `fees`, by month and mode) is a time chart but can't draw the `events.json` rules, so the congestion page misses "every time chart draws every event" on that one chart. Ask: give `monthlyColumns` an `events` option that works like `lineChart`'s. The page will then pass `events: events.events`. Every other time chart on both pages draws all three events.
- **L11 · No subtitle for the core-vs-wide comparison.** `congestion.json` has a finding subtitle for `effects` (core list) but none for the borderline-zone result. So the page shows "with and without borderline zones" as a table (core and wide medians and ranges, by measure and mode), not a chart, since every chart needs a finding from JSON. Ask: `publish.py` adds `subtitles.effects_wide` (for example, the yellow-cab estimate's move between the lists). The page can then draw it as a second `effectDots` chart.

**Hand-off**
- Built:
  - `site/src/congestion-pricing.md`:
    - the three tiles (`trips_effect`, `fpm_effect`, `fees_to_date`);
    - `effectDots` on the core list, one panel per measure (trips, base fare per mile, driver share);
    - the weekly estimated effect (trips, all modes, core list), with the left-out holiday weeks named from `excluded_weeks`;
    - weekly trips per day, touching the zone against elsewhere;
    - the core-vs-wide sensitivity table;
    - fee revenue by month and mode (`monthlyColumns`);
    - the pickups-change map (`zone_change`), linking each zone to its page, with a note that it is not an estimated effect;
    - a no-digit limits list, and "How we measured this" linking to `/methods#congestion-method`.
  - `site/src/drivers.md`:
    - the four tiles (pay per hour with a passenger, driver share, trips per hour worked and active drivers, both TLC-reported);
    - the driver-share trend and the pay-per-hour trend, each drawing all three events;
    - the event study;
    - trips per hour worked by licence class (monthly-indicators caption, `tlc_as_of_month`);
    - "How we measured this" linking to `/methods#pay-rise-method`.
  - The event study is one figure with one subtitle and two panels on a shared week axis:
    - base fare per mile and driver pay per mile on one $/mile axis;
    - pay per minute in its own panel, so no dual axes;
    - solid lines for 2025 and dashed lines for the same weeks of 2024 (the seasonal reference);
    - the transition week (W31, `transition: true`) shaded and labelled.
  - `lineChart` has no panels or dashed reference lines, so the event study is built in the page from the kit's pinned `Plot`, `sourceCaption`, `tableView`, `palette` and `format`, as L13's `gapScatter` is. It keeps the same frame: subtitle, units on both axes, source caption and a table view.
  - Nothing shared was edited.
  - The event label and the rule's month come from `events.json`, so the page never names the rule's size.
- Checked:
  - `make test`: 490 passed, 13 skipped. The site build renders both routes with the real data. Data per route: congestion 783 kB, drivers 154 kB, under the 1.5 MB budget.
  - Mock data: the same pages build in a scratch copy with `make_mock_site_data.py --out <scratch>`, and render with no errors. The real `site/src/data/` was never touched.
  - Browser: both pages at 1280 px and 375 px, in light and dark. No horizontal page scroll at 375 px; the sensitivity table scrolls inside its own box. Tooltips and the table views work.
  - Console: no errors on visible loads of both the dev preview and the built pages. The first load in a hidden browser pane logs `<rect> attribute width: A negative value` errors (Plot drawing at zero width). They don't recur at any real width.
  - Prose has no digits. No "caused", "pay rise" or "5% rise" anywhere in either page. Pay is "per hour with a passenger" throughout.
- Known limits:
  - At 375 px, `lineChart`'s three stacked event labels wrap, but the rules still cross their text on the weekly and monthly charts (shared component; L05).
  - In dark mode the map's diverging midpoint is the same grey as "no data" (L14 noted this too).
  - The weekly charts draw the two pay-rule events as well, as the page rules ask; they're context there, not part of the congestion estimate.
- Follow-ups:
  - The map can't outline the congestion zone: neither `congestion.json` nor `taxi_zones.geojson` says which zones are in the core or wide list. A `cbd` field on `zone_change` rows (`core`, `wide` or null) would let the map mark them.
  - If L05 gives `lineChart` panels and a dashed reference series, the page-side event study can move onto it.
