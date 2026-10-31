# L16 · Pages: Airports + Prices

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, §9.4 · **Decision** D10 · **Answers** Q9 (airports), Q7 (prices) · **Data** `airports.json`, `prices.json`

## Goal

Who wins the airport trip at JFK, LaGuardia and Newark, at what fare and when; and what riders pay per mile and per minute, and where pricing is most volatile.

## Owns

- `site/src/airports.md`, `site/src/prices.md`

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).

## Tasks

- [x] Airports: tiles for trips per day, yellow-cab share, fare to Manhattan (mean or median as D10 settles) and busiest hour; bars per airport stacked to 100% by mode, split by direction; hour-of-day pattern; fares by mode
- [x] Prices: tiles for median fare per mile, price volatility, and cheapest and dearest hour; fare-per-mile strip or box by mode; volatility map (p90 ÷ p10 by zone); fare per minute; borough view

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
| 31 Oct 2026 | done, synced | Merged `main` at `6a523c4` (merge `437609c`). The merge only brought L13's `company.js` and brief, nothing these pages use. `make test` still passes (490 passed, 13 skipped, site build renders both routes), and both pages re-checked in the browser with no console errors |
| 31 Oct 2026 | done | `airports.md` and `prices.md` built on the real data (as of 2026-08). `make test` passes: 490 passed, 13 skipped, and the site build renders both routes. The mock data also builds and renders, checked in a scratch copy. Both pages checked in the browser at 1280 px and 375 px, light and dark, with no console errors |

**Blocked:** nothing stops the pages. One data ask for L11: `prices.json` has no finding subtitle for fare per minute, so the page can't give it a chart of its own. For now it shows the median fare per minute by mode as tiles, and overall fare per minute by borough and mode in a table. If a chart is wanted, `publish.py` would add something like `subtitles.fpmin_by_mode`, and the page would draw it with `fareRange` or `lineChart`.

**Hand-off**
- Built:
  - **`/airports`**
    - Stat row: trips per day, yellow-cab share, mean fare to Manhattan (a mean, per D10), busiest hour. A note under it says the mean fare is before tip and covers trips from the airports in `fares[]` together, which answers the G4 point about blending JFK and LaGuardia.
    - `split`: bars stacked to 100% (`stackedBars100`), one panel each for pickups and drop-offs. Newark's pickup rows are left out (G4: they aren't TLC trips), so Newark shows as drop-offs only, with a note.
    - `share_trend`: the yellow-cab share at each airport over time (`lineChart`, a line per airport).
    - `by_hour`: trips per day by hour of day (`lineChart`), with a line per mode and one for all modes. The rows are summed as published, so the all-modes peak matches the subtitle (4,380 at 2 pm).
    - `fares`: the mean fare before tip from each airport to Manhattan, one panel per airport with a bar per mode. This uses a page-local `fareBars` (pinned Plot, `tableView`, `sourceCaption`) because `barChart` draws one panel only. Its table adds the mean base fare, base fare per mile (total ÷ total miles) and trips per day.
  - **`/prices`**
    - Stat row: median fare per mile, price volatility (p90 ÷ p10), cheapest hour, dearest hour. A note says which measure each tile uses.
    - `fpm_by_mode`: `fareRange` (median with the 10th–90th percentile) for the latest month and a year earlier.
    - Fare per minute: tiles for the median by mode.
    - `fpm_by_hour`: `hourHeatmap` of overall fare per mile, all modes.
    - `fpm_by_borough`: `barChart` of overall fare per mile, all modes, for the five boroughs, plus a table of every mode, per mile and per minute.
    - `volatility_by_zone`: a `choropleth` with an Uber / Lyft switch. Zones link to their pages.
  - Medians and overall ratios are named as such in every label and note.
- Checked:
  - `make test`.
  - The mock build, run from a scratch copy so the real `site/src/data/` was never touched.
  - In the browser at 1280 px and 375 px, light and dark:
    - no console errors;
    - no horizontal scroll at 375 px;
    - the hour chart's tooltip at 2 pm reads 4,380, matching its subtitle;
    - the Lyft switch redraws the map;
    - the borough table opens.
  - No digits in markdown prose.
  - Tile labels: "Mean fare to Manhattan" and "Median fare per mile" come from `tiles.json`, and both are correct.
- Known limits:
  - The airport tiles (trips per day, yellow-cab share) and `by_hour` include Newark's few pickup records (about 4 a day), while the split and the share-trend subtitle leave them out. The difference doesn't show at the published precision.
  - The volatility map shows Uber and Lyft only. Cab cells include junk-size spreads (zone 1 yellow 517×, several over 100×) that would wash out a linear scale.
    - Each mode's map has its own colour scale, and the page says so.
    - The subtitle names the widest cell across companies, whichever mode is picked.
  - `hourHeatmap` starts its colour scale at $0, so the hours differ only within the upper part of the ramp. They are still readable.
  - In `fpm_by_borough`, the "EWR" row (junk Newark pickups) and the "N/A" row (pickups outside the city) aren't shown.
- Follow-ups:
  - **L05:** in both schemes, Uber's grey is hard to tell from the `all` group's text colour. Both pages pass `colors: {all: "accent"}`; this could become the kit's default.
  - **L05:** on phones, `lineChart`'s x-axis label for `xType: "hour"` runs into the "6 pm" tick. The airports page shortens the label to "Hour" below 480 px. Zone pages using hour charts likely show the same overlap.
  - **L11 (optional):** leave Newark pickups out of the airport tiles and `by_hour` too, to match the split.
