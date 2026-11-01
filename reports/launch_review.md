# Launch review (L18)

**Date:** 1 Nov 2026 · **Reviewed:** `main` at `83f2488` (G5 passed; every page merged) · **Data:** `site/src/data/`, `as_of_month` 2026-08, generated 2026-10-31T00:59:29Z · **Reviewer:** lane L18, which built none of the pages

## Verdict

- **No blockers.** The site builds and every page renders with the real, validated data. No page has a console or runtime error, and no route scrolls sideways at 375 px.
- **10 should-fix findings.** The main ones:
  - **Subtitles that the charts can't show:** the zone heatmaps on all 256 profiled zones, and the yellow-cab trend on `/airports`.
  - **Newark leftovers:** zone 1 still appears on the congestion map, and its zone page gives the wrong reason for having no charts.
  - **Policy-date labels** that run across each other's rules.
  - **Two dark-mode colour problems:** the diverging midpoint, and the rate heatmap.
  - **Raw QA text on `/methods`.**
  - **One ambiguous tile label.**
- **17 nits.**
- Every title, tile and subtitle checked matches the value in its JSON file. Where a finding fails, the chart doesn't show the number its subtitle states; the JSON value itself is right.

## How it was checked

- **Build:** `make site-build` in this worktree (symlinked `.venv` and `site/node_modules`): exit 0, 274 links validated. `site/dist` was served with `python -m http.server` and opened in the built-in browser with `.html` URLs.
- **Pages:** all 10 top-level routes were checked in light mode at 1280 px. Zones index, zones 1 and 132, congestion pricing, airports and prices were also checked in dark mode, at 1280 px or 375 px. The phone check covered 8 routes (home, Uber, congestion pricing, drivers, airports, prices, zones index, methods) plus zone 132 at 375 × 812 (the built-in browser's mobile preset). The other three company pages share Uber's template.
- **Zone pages:** 1 (Newark), 27 (Breezy Point, longest wait), 43 (Central Park: borderline, yellow leads), 105 (Governor's Island: thin, borderline), 132 (JFK), 138 (LaGuardia), 161 (Midtown Center, core congestion zone), 199 (Rikers Island, thin), 207 (Lyft beats Uber) and 237 (Upper East Side South: borderline, yellow leads). A script also checked all 263 zone files for the patterns found on those pages.
- **In-page audit:** a script run on each page listed:
  - every figure's subtitle and source caption;
  - any text, SVG or table that crosses the main column or the viewport;
  - the event labels that cross another event's rule;
  - the footer and any images.
  The script lived in `site/dist/__review/` during the review and has been deleted.
- **Scripted source checks:**
  - digits in page-markdown prose (outside code fences, comments, `<style>` and `${…}`);
  - hex, `rgb()` and `hsl()` colours in `site/src` outside `palette.js`;
  - banned words in all 4,608 generated strings in `site/src/data/` (1,276 unique);
  - every `/methods#…` anchor against the built `methods.html`;
  - `validated` and `as_of_month` in every file;
  - `pytest tests/test_site_budget.py tests/test_contracts.py`: 61 passed.
- **Numbers:** each page's tiles and subtitles were recomputed from the arrays in the same JSON file. For example, Aug 2026 fees sum to $11,532,539, which is the home tile. Uber's share of fees to date is 60.1%, and the hourly fare-per-mile minimum and maximum are hours 150 and 89.
- **Colour blindness:** two methods.
  1. **Numeric** (`cvd.py`, below): every `palette.js` mode colour and both map ramps, light and dark, simulated with the Machado, Oliveira & Fernandes (2009) matrices at severity 1.0, applied in linear RGB. Pairs were compared by CIEDE2000.
  2. **Visual:** the same matrices as an SVG `feColorMatrix` filter on `<html>`. Applied to `/zones` (level and change maps) under deuteranopia and tritanopia, and to `/companies/uber` (fare-range and tips charts) under protanopia.

## Findings

Owners: L05 components · L11 data and findings · L12 home and methods · L13 companies · L14 zones · L15 congestion and drivers · L16 airports and prices. Where two lanes are named, the first is where the fix most likely lands.

### Should-fix

**1. Policy-date labels cross each other's rules on every dated time chart**
- **Routes:** `/`, `/companies/*`, `/drivers` (3 charts), `/congestion-pricing` (weekly trips, fees) and every zone page's share chart.
- **Owner:** L05 (`eventMarks` in `components/charts.js`).
- **Evidence (1280 px):** on the `/companies/uber` share chart, the rules sit at x = 667 (5 Jan 2025), 711 (1 Mar 2025) and 834 (1 Aug 2025).
  - "Congestion pricing starts" spans x 672–802, across the 1 Mar rule.
  - "Per-minute minimum pay +3.9% (inflation)" spans x 716–936, across the 1 Aug rule.
  - "New driver minimum-pay rule" spans x 675–829, across the 1 Mar rule.
- **Evidence (375 px):** on the home share chart, "Congestion pricing starts" sits over the Aug 2025 rule, and "New driver minimum-pay rule" wraps to the left across the Jan 2025 rule.
- **Effect:** labels sit right of rules at or before 55% of the width and left of later rules, so all of them pile into the 7-month strip between Jan and Aug 2025, and readers can't tell which label marks which date.
- L13's earlier "label runs off the right edge" problem is fixed: no label passes the viewport now.

**2. Zone heatmap subtitles quote an all-modes total the chart never draws**
- **Routes:** all 256 non-thin zone pages.
- **Owners:** L11 (`subtitles.hour_heatmap`), L14.
- **Evidence:** `/zones/132` says "Pickups here peaked on Sun 11 pm, with 1,470 trips in that hour in an average week".
  - The heatmap is three per-mode grids whose largest cell is 732 (Uber). Its legend stops near 700.
  - 1,470 is Uber 732.2 + Lyft 337.5 + yellow 395.4 = 1,465 at `hour_of_week` 23.
  - A script over all zone files finds the subtitle value above every single cell on 256 of 256 non-thin zones.
- **Fix options:** word it per mode ("Uber pickups peaked…"), or draw an all-modes grid.

**3. The `/airports` yellow-cab trend subtitle states a figure the chart doesn't draw**
- **Route:** `/airports`, "Yellow cabs over time".
- **Owners:** L11, L16.
- **Evidence:** the subtitle says "Yellow cabs' share of airport trips fell 1.7 pts between Aug 2025 and Aug 2026".
  - The chart draws one line per airport: JFK 20.4% → 18.0% (−2.4 pts), LaGuardia 13.1% → 12.3% (−0.8), Newark 4.5% → 3.6% (−0.8).
  - `share_trend` has no all-airports row, so the −1.7 pts (the `yellow_share` tile's change) can't be seen on the chart.

**4. Newark (zone 1) is still coloured on the congestion-pricing map**
- **Route:** `/congestion-pricing`, "Where pickups moved".
- **Owners:** L11 (`congestion.json` `zone_change` keeps zone 1), L15.
- **Evidence:**
  - Hovering Newark shows "Newark Airport (EWR) +2.0%".
  - The subtitle counts "19 of 260 zones", which leaves zone 1 out, but `zone_change` has 261 rows, zone 1 included.
  - The G4 fix and `/methods` ("its stray pickup records are left out of every zone count and map") both say zone 1 is excluded.

**5. The congestion map doesn't show where the congestion zone is**
- **Route:** `/congestion-pricing`, "Where pickups moved".
- **Owners:** L15 (or L05, as a `choropleth` outline option).
- **Evidence:** the subtitle says "…including 11 of the 38 in the congestion zone". The map has no outline, hatching or label for the 38 core zones, so readers can't see which zones the claim is about. The count itself checks out: 11 of the 38 core zones in `zone_change` are negative.

**6. The Newark zone page gives the wrong reason for having no charts**
- **Route:** `/zones/1`.
- **Owner:** L14.
- **Evidence:**
  - The title is right: "TLC vehicles dropped off 4,980 trips a day at Newark Airport in Aug 2026; pickups there aren't TLC trips".
  - Below it, every tile reads "Too few trips", and the box says "Charts of pickups … need at least 100 trips in the month; this zone had fewer". Newark had 480 pickup records in Aug 2026 (G4 review), and that isn't why it has no charts.
  - `zones/1.json` carries Newark-specific subtitles that the page never shows, such as "Pickups at Newark Airport aren't TLC trips, so there are no waits to report".
  - The crumb shows "EWR" as the borough.
- **Promised but not shown:** G4 and `/methods` both say the page "shows drop-offs". The only drop-off figure is the one in the title. Linking to `/airports`, which has the drop-off split, would cover it.

**7. In dark mode, near-zero change zones look like "too few trips" zones**
- **Routes:** `/zones` change map and `/congestion-pricing` map, dark mode.
- **Owner:** L05 (`palette.js`; the colours were set by D20, so a change needs the integrator's sign-off).
- **Evidence:** the dark diverging ramp's midpoint is `muted.dark` (#4A4F55), which is also the `unknown` fill. In the CIEDE2000 check they are identical (ΔE 0.0) under every simulation.
  - On `/zones` in dark mode, Staten Island and most of the Bronx (near-zero change) are the same grey as Newark, Jamaica Bay and Rikers Island.
  - The note under the map says "Grey zones had too few trips".
- In light mode the gap is small but visible (ΔE about 8.5 between #F2F2F2 and #C9CDD2).
- L14 reported this to L05 at hand-off; it is still open.

**8. The hour-of-week heatmap's colour scale starts at $0, which hides the variation in fares**
- **Route:** `/prices`, "By hour of the week". Every `hourHeatmap` uses the same scale.
- **Owners:** L05 (`hourHeatmap` sets `domain: [0, max]`), L16.
- **Evidence:** hourly fare per mile runs from $4.22 to $6.99, which fills only the top 40% of a $0–$7 ramp.
  - Light mode: the grid is all mid-to-dark blue.
  - Dark mode (reversed ramp): it is almost uniformly white, so the subtitle's lowest hour (Sat 6 am) and highest (Wed 5 pm) can't be found.
- A zero start is right for the zone pages' trip counts, but not for a rate.

**9. `/methods` shows the validation gate's internal QA strings as public text**
- **Route:** `/methods`: subtitles of "Valid records by month" and "Tie-out with TLC's monthly indicators", and the validation-checks table.
- **Owners:** L11 (`quality.json` `validation.checks[].summary`), L12.
- **Evidence:** text shown verbatim includes:
  - "All 31 FHV - High Volume months with indicators within ±2%; reported, not gated (D27)…"
  - "…8 more than 3 points below the mode's median (listed): yellow 2025-05 (5.92 pts), … lyft 2025-08 (3.21 pts)…"
  - "core: 98.92% of both-in trips carry a fee, pass-through 3.28%…"
  - "uber 100.00%, lyft 100.00% … of trips with a CBD fee carry the configured fee (at least 95%)"
- **Problems:**
  - decision ids;
  - TLC licence-class names;
  - lower-case mode codes;
  - "both-in" and "CBD";
  - `YYYY-MM` months, against the `Jan 2025` rule in contracts §3.
- These need public sentences, generated like the page findings.

**10. The "Estimated effect on fare per mile" tile is ride-hail only but doesn't say so**
- **Routes:** `/` (congestion block) and `/congestion-pricing` stat row.
- **Owner:** L11 (the `fpm_effect` label lives in the tile registry, `contracts/site/tiles.yaml`, so the change goes through the integrator).
- **Evidence:** the tile shows +3.0%, which is `effects` ride_hail fare_per_mile 0.0298. The all-modes figure is +2.2%.
  - The tile sits beside "Estimated effect on zone trips −4.2%", which is all modes.
  - The label doesn't say "ride-hail", although the findings text under the home tiles does ("For ride-hail trips touching the zone…").

### Nits

**11. On `/prices`, switching the volatility map to Lyft leaves the Uber subtitle** (`/prices`, "Where prices vary most"; L16, L11). With Lyft selected, the map and its scale (2×–3.5×) change, but the subtitle still reads "Fares per mile varied most for Uber trips from Garment District…". `prices.json` has no Lyft subtitle.

**12. On the congestion effect dots, Uber and "All modes" share a colour** (`/congestion-pricing`, "Estimated effects by mode"; L15). Uber is #3A3A3A in light mode and #D4D4D4 in dark; "All modes" is `currentColor`. Both read as the same black or white dot. Row labels separate them, but `/airports` and `/prices` already pass `colors: {all: …}` for this.

**13. Zone share subtitles name a ride-hail total that isn't drawn** (all 256 non-thin zone pages; L14, L11). For example, `/zones/132` says "Ride-hail apps' share of pickups here rose 6.6 pts … to 72%", but the chart draws Uber (52.8%) and Lyft (18.7%) separately, so readers must add them. This is the same pattern as finding 3, but here the total can be worked out from the chart.

**14. Some trip counts show decimals or bad plurals** (zone pages, `/methods`; L11, L12).
- Heatmap subtitles give fractional counts on 236 zones, for example "with 283.2 trips" (zone 43), "813.1 trips" (zone 237) and "20.9 trips" (zone 207).
- The `/methods` fee table shows "$0.25 (1 trips)".

**15. Thin zones show share tiles built from a handful of trips** (`/zones/199`, `/zones/105` and the other thin zones; L14, L11).
- Rikers Island (13 pickups): "Trips per day 0.4, +160.0%", "Ride-hail share 54%, −26.1 pts".
- Governor's Island (3 pickups): "100%, 0.0 pts".
- `/zones` blanks the same zones' figures ("Thin zones show no figures"), so the index and the zone page disagree. Four thin zones carry an `rh_share` tile.

**16. Airport pickup figures differ between `/airports` and the airport zone pages** (L11).
- `/airports` uses valid trips only, through `agg_airport` (`airport_share.sql`: "agg_airport counts valid trips only"). The zone pages count every record.
- LaGuardia pickups: zone 138 shows ride-hail at 82%, while `/airports` shows Uber 59% + Lyft 24% = 83%.
- JFK pickups: 17,273 a day on zone 132, against 17,047 on `/airports`.
- `/methods` says "Trip counts and shares count all records".

**17. "Fare per minute" means different measures on different pages** (company pages vs `/prices`; L05 `COMPARE_LABELS`, L11). The company comparison row "Fare per minute" is an overall rate (total fares ÷ total minutes): Uber $1.39/min. `/prices` "Median fare per minute" gives Uber $1.29/min, and the comparison table's own neighbouring row is a median ("Median fare per mile").

**18. Static page titles are placeholders** (`/companies/*`, `/zones/*`; L13, L14).
- The built HTML has `<title>Company profile | NYC Ride Market</title>` and `<title>Zone profile | NYC Ride Market</title>`. JavaScript replaces them at run time, so link previews and crawlers see the placeholder.
- The yellow page's tab then reads "Yellow cab | …" while the sidebar says "Yellow cabs".

**19. The week-by-week effect line runs straight across the two left-out weeks** (`/congestion-pricing`, "Week by week"; L15). The weeks of 13 and 20 Jan 2025 are filtered out before drawing, so the line joins 6 Jan to 27 Jan with a segment where there is no data. The note under the chart says the weeks are "off the line".

**20. The airport fare subtitle covers only one of the two airports charted** (`/airports`; L11).
- The fares subtitle covers LaGuardia only ("A trip from LaGuardia to Manhattan cost a mean $75.52…"), but the chart leads with the JFK panel.
- The "Mean fare to Manhattan" tile ($87.96) is the JFK and LaGuardia blend that G4 asked the Q9 text to stop using. The page's note discloses it, but per-airport figures would match the chart.
- Under the formatting rule, JFK's bars mix "$124", "$106" and "$83.67".

**21. Airport zone titles say "pickups in JFK Airport"** (`/zones/132`, `/zones/138`; L11). They read "Ride-hail apps carried 72% of pickups in JFK Airport…"; "at" reads better for the two airport zones.

**22. "Congestion fees, last month" is the Aug 2026 figure** (`/`; L11, tile registry). The tile shows Aug 2026, the as-of month, which will be two to three months back at launch. Naming the month, or "latest month", avoids the confusion.

**23. The `/drivers` "Hours on the road" section shows no hours** (L15). It charts trips per hour worked only. `drivers.json` `hours` has `hours_per_day_per_vehicle` (6.4 for ride-hail), but it appears only in the home Q15 finding.

**24. The `/prices` per-minute tiles go two to a row on phones** (`/prices` at 375 px; L16). `.nrm-minute-tiles` overrides the grid to `repeat(2, …)` below 640 px, against SPEC §9.5's one column.

**25. The published files still hold Newark's stray pickup rows** (downloads on `/methods`; L11).
- `prices.json` `volatility_by_zone` has yellow zone 1 with `fpm_p50` 1500.0 and `volatility` 516.7.
- `zones/index.json` zone 1 has `trips_per_day` 15.5 and `yellow_share` 0.9958 (L14 reported this one).
- `zones/1.json` still carries `share_trend`, `hour_heatmap` and `top_destinations` from those records.
- The pages hide all of them, but `prices.json` and `zones/index.json` are listed as downloads.

**26. Borderline zones aren't marked on their zone pages** (`/zones/43`, `/zones/237`, `/zones/105`; L14). The crumb says "Inside the congestion zone" only for core zones. Borderline zones (`flags.cbd_borderline`) show nothing, although the methods list of borderline zones links to them.

**27. The green-cab page's share chart can't show its own finding** (`/companies/green`; L13). The green line (0.2%) lies on the 0% baseline of a 0–65% axis, so "held steady" can't be seen.

## Summary

| # | Route | Finding | Owner | Severity |
|---|---|---|---|---|
| 1 | `/`, companies, drivers, congestion, zone pages | Policy-date labels cross other rules | L05 | should-fix |
| 2 | 256 zone pages | Heatmap subtitle quotes an all-modes total not drawn | L11, L14 | should-fix |
| 3 | `/airports` | Yellow-share subtitle is all airports; chart is per airport | L11, L16 | should-fix |
| 4 | `/congestion-pricing` | Newark coloured +2.0% on the zone-change map | L11, L15 | should-fix |
| 5 | `/congestion-pricing` | Map doesn't mark the congestion zone its subtitle counts | L15 (L05) | should-fix |
| 6 | `/zones/1` | Wrong "too few trips" reason; Newark subtitles not shown | L14 | should-fix |
| 7 | `/zones`, `/congestion-pricing` (dark) | Diverging midpoint equals the no-data grey | L05 (D20) | should-fix |
| 8 | `/prices` | Rate heatmap scale starts at $0; dark grid near-uniform | L05, L16 | should-fix |
| 9 | `/methods` | Raw QA strings (D26, D27, `2025-05`, "both-in") as public text | L11, L12 | should-fix |
| 10 | `/`, `/congestion-pricing` | Fare-per-mile effect tile is ride-hail only; label doesn't say so | L11 | should-fix |
| 11 | `/prices` | Lyft map keeps the Uber subtitle | L16, L11 | nit |
| 12 | `/congestion-pricing` | Uber and All modes share a colour | L15 | nit |
| 13 | zone pages | Share subtitle's ride-hail total isn't a line | L14, L11 | nit |
| 14 | zone pages, `/methods` | Fractional trip counts; "(1 trips)" | L11, L12 | nit |
| 15 | thin zone pages | Share and change tiles from a handful of trips | L14, L11 | nit |
| 16 | `/airports` vs zones 132, 138 | Valid-only vs all-record airport pickups | L11 | nit |
| 17 | companies vs `/prices` | "Fare per minute" is two different measures | L05, L11 | nit |
| 18 | companies, zones | Static `<title>` placeholders | L13, L14 | nit |
| 19 | `/congestion-pricing` | Weekly line bridges the left-out weeks | L15 | nit |
| 20 | `/airports` | Fare subtitle names LaGuardia only; blended tile | L11 | nit |
| 21 | zones 132, 138 | "pickups in JFK Airport" | L11 | nit |
| 22 | `/` | "Congestion fees, last month" is Aug 2026 | L11 | nit |
| 23 | `/drivers` | "Hours on the road" shows no hours | L15 | nit |
| 24 | `/prices` | Two-up tiles below 640 px | L16 | nit |
| 25 | downloads | Newark junk rows in published files | L11 | nit |
| 26 | borderline zone pages | Borderline status not shown | L14 | nit |
| 27 | `/companies/green` | Green line flat on the axis | L13 | nit |

**Totals:** 0 blockers, 10 should-fix, 17 nits.

**By owner** (a finding with two owners counts for each):

| Owner | Findings | Count |
|---|---|---|
| L05 | 1, 5, 7, 8, 17 | 5 |
| L11 | 2, 3, 4, 9, 10, 11, 13, 14, 15, 16, 17, 20, 21, 22, 25 | 15 |
| L12 | 9, 14 | 2 |
| L13 | 18, 27 | 2 |
| L14 | 2, 6, 13, 15, 18, 26 | 6 |
| L15 | 4, 5, 12, 19, 23 | 5 |
| L16 | 3, 8, 11, 24 | 4 |

## Checklist

| Item | Result | Notes |
|---|---|---|
| Each title and subtitle finding matches its chart and the JSON value behind it | **Fail** | Every title and subtitle equals its JSON value, and the values recompute from the page's own arrays. Charts don't show the stated number in findings 2 and 3, and partly in 4, 5, 11 and 13 |
| No digits in page markdown prose; no hex or rgb colours in `site/src` outside `palette.js` | **Pass** | No prose digits; the only hits are CSS inside `<style>` blocks. No colour literals outside `palette.js` (excluding `site/src/dev/`) |
| Language: no "caused"; pay per hour "with a passenger"; taxi tips "card-only"; congestion "estimated effect" | **Pass** | Across 1,276 unique generated strings: 0 "caused", 0 "5%", 0 "pay rise", no WAV match rate. Every per-hour pay string says "with a passenger". Every cab tip figure (tiles, tip chart series, comparison table, Q13) says card-only. Every congestion result says "estimated effect". `/methods` says "not proof of cause", a negation |
| Every chart has a subtitle, units and a source caption; no pies, 3D, dual axes or "Average" labels | **Pass** | Every figure has a source caption. The figures without subtitles are tables: the accepted sensitivity table and the methods tables. The event study uses two panels, not two axes. "average day/week" appear only in axis labels naming the measure |
| No logos or wordmarks; the footer is on every page | **Pass** | No `<img>` on any page; `site/src/assets` holds only fonts. The footer is in all 274 built pages |
| Light and dark modes; colour-blindness simulation of the mode colours and both map scales | **Fail** | Findings 7 and 8 are dark-mode failures. The simulation itself passes; see below |
| Phone layout at 375 px, one column below 640 px | **Pass** | 8 routes plus zone 132: `scrollWidth` = 375 everywhere. Wide tables scroll inside their own boxes. Tiles and map pairs go to one column, except the `/prices` per-minute tiles (nit 24) |
| Every `/methods#…` link resolves; methods covers SPEC §12 limits and §7.3 | **Pass** | All 10 contract anchors exist in `methods.html`, including the 5 that pages link to (`cleaning`, `congestion-method`, `pay-rise-method`, `tips`, `waits`). Every SPEC §12 limit is under "Known limits". §7.3 is covered by the fee-check table and the effects table for both zone lists. Finding 4 contradicts one methods sentence |
| Published data has no `MOCK` and has `validated: true`; budgets pass | **Pass** | 277 JSON files: all `as_of_month` 2026-08 and `validated: true`, no `MOCK`. Budget and contract tests: 61 passed |
| Spot-check ten zone pages, including thin zones, the airports (1, 132, 138) and a congestion-zone zone | **Fail** | Zones 1, 27, 43, 105, 132, 138, 161, 199, 207 and 237 checked. Findings 2, 6, 13, 15, 21 and 26 |

### Colour-blindness results

**Mode colours.** Under protanopia and deuteranopia, no pair of the light-mode mode colours (including the ride-hail accent) falls below CIEDE2000 12. The near pairs:

| Scheme | Simulation | Pair | ΔE |
|---|---|---|---|
| Light | Tritanopia | Green vs ride-hail accent | 11.6 |
| Dark | Deuteranopia | Lyft vs other ride-hail | 10.0 |
| Dark | Protanopia | Lyft vs other ride-hail | 11.4 |
| Dark | Protanopia | Lyft vs ride-hail accent | 11.8 |
| Dark | Tritanopia | Green vs ride-hail accent | 10.3 |

Other ride-hail is rarely drawn. Charts that use these pairs carry row labels, line-end labels or legends. In the protanopia filter, the yellow-cab and green-cab tip lines get close in hue but stay apart by lightness and their end labels.

**Contrast on white.** Yellow is 2.45:1 and other ride-hail 2.64:1 (known: D20).

**Sequential ramp.** Lightness is monotonic in light and dark under every simulation, with an end-to-end ΔE of 63–69. In light mode, the lightest stop is ΔE 7–8.5 from the no-data grey.

**Diverging ramp.** The blue and orange poles stay ΔE 46–68 apart under every simulation, and the filter screenshots of `/zones` keep blue apart from khaki (deutan) and teal apart from pink (tritan). The one failure is finding 7, which doesn't depend on colour vision.

## Known and accepted (not reported)

- The core-vs-wide congestion result and fare per minute are shown as tables or tiles, not charts.
- `site/src/dev/` isn't in the build.
- The dark-mode sequential ramp puts low values in the most saturated blue, as D20 intends.

## Appendix: colour-blindness script

The simulation behind the numbers above. It was run from the session scratchpad and isn't part of the repo. Inputs are the `palette.js` tokens, d3's `interpolateBlues` stops on [0.12, 1] (reversed in dark mode), and the two diverging ramps from D20. Each ramp is sampled at nine stops.

```text
Simulation: v_sim = M · v (v in linear RGB), M from Machado et al. (2009), severity 1.0
  protan  [[0.152286, 1.052583, -0.204868], [0.114503, 0.786281, 0.099216], [-0.003882, -0.048116, 1.051998]]
  deutan  [[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]]
  tritan  [[1.255528, -0.076749, -0.178779], [-0.078411, 0.930809, 0.147602], [0.004733, 0.691367, 0.303900]]
Distance: CIEDE2000 on CIELAB (D65)
```

## Resolution (integrator, 1 Nov 2026)

Fixes were made in two sessions, merged to `main` as `930faec`, plus integrator follow-ups in the commit that adds this section. The re-published data (Aug 2026, 278 files) passes every contract and budget, and `make test` passes (546).

| # | Status | How |
|---|---|---|
| 1 | Fixed | Numbered badges on each rule, with the labels in a key above the plot; badges that would touch drop a row |
| 2 | Fixed | Per-mode wording, e.g. "Uber pickups here peaked on Sun 11 pm, with 732 trips…": the largest square drawn |
| 3 | Fixed | Per-airport subtitle ("fell 2.4 pts at JFK and 0.8 pts at LaGuardia"). Newark's line, the yellow-share tile and trips-per-day now leave out its stray pickups (integrator) |
| 4 | Fixed | Zone 1 dropped from `congestion.json` `zone_change` |
| 5 | Fixed | `choropleth` `outline` option; the map outlines the 38 core zones |
| 6 | Fixed | `/zones/1` shows Newark's own reasons, links to `/airports`, and the crumb reads "New Jersey" |
| 7 | Fixed | No-data zones are hatched on every map; D20's ramps unchanged |
| 8 | Fixed | `hourHeatmap` `zero` option, off on `/prices` |
| 9 | Fixed | `quality.json` `subtitles.valid_share`, `subtitles.tie_out` and each check's `text`, shown on `/methods` |
| 10 | Fixed | Tile label "Estimated effect on ride-hail fare per mile" |
| 11 | Fixed | `subtitles.volatility_by_zone_lyft` is used when Lyft is selected |
| 12 | Fixed | "All modes" uses a colour no other row on that chart uses |
| 13 | Fixed | Zone share subtitle names Uber's and Lyft's parts and the ride-hail total |
| 14 | Fixed | Whole trip counts and singular plurals ("1 trip") |
| 15 | Fixed | Thin zones' share and change tiles are null |
| 16 | Fixed | `/methods` says airport figures count valid trips, while zone pages count every record |
| 17 | Fixed | Comparison row reads "Overall fare per minute" |
| 18 | **Open: accept?** | Framework 1.13.4 takes `<title>` from front matter or the first heading, and a dynamic route has one source file. Per-route titles would need page loaders, which slow every build and go stale. JavaScript sets the right title at run time |
| 19 | Fixed | `lineChart` `gaps` option; the weekly line breaks at the left-out weeks |
| 20 | Fixed | Fares subtitle covers both airports. The tile reads "Mean fare to Manhattan, JFK and LaGuardia", and JFK's bars show whole dollars ($124 · $106 · $84) via `format.usdGroup` (integrator) |
| 21 | Fixed | "pickups at JFK Airport" / "at LaGuardia Airport" |
| 22 | Fixed | Tile label "Congestion fees, latest month" |
| 23 | Fixed | `/drivers` charts hours on the road per vehicle per day |
| 24 | Fixed | Per-minute tiles go to one column below 640 px |
| 25 | Fixed | Newark's pickup rows are gone from `prices.json`, `zones/index.json`, `zones/1.json` and the companies `lyft_vs_uber` lists (integrator) |
| 26 | Fixed | Borderline zones say so in the crumb, linked to `/methods#cbd-zones` |
| 27 | Fixed | The green-cab page adds a zoomed panel for its own line |

`contracts/site/pages.yaml` now also lists `quality.json` for `/congestion-pricing` and `home.json` for `/drivers`.
