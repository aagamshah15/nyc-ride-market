# L13 · Pages: Companies

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.3, D3 · **Answers** Q4, Q5, Q11, Q12, Q13 · **Data** `companies/{mode}.json`

## Goal

One template, `companies/[company].md`, rendering Uber, Lyft, yellow and green, each with a comparison block against the other three.

## Owns

- `site/src/companies/[company].md`, plus page-only helpers in `site/src/companies/` if needed

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).

## Tasks

- [x] Tiles as pinned in the contract: trips per day, share of NYC trips, median fare per mile, driver share of fare, tip rate
- [x] Charts: share trend; fare-per-mile distribution; tip rate (for taxis the chart says card-only); accessible (WAV) match rate and shared match rate, which are ride-hail only, with a plain "not reported for this mode" state on taxi pages
- [x] Comparison block from the `compare` rows
- [x] Q4 on the Uber and Lyft pages: where Lyft beats Uber on share and whether the gap is growing, from the contract fields
- [x] D29: the `wav` block is accessible *service*, not a match rate: chart `wav_share` (share of trips in a WAV) and show `wav_requests` (completed WAV-requested trips) from the company file's `wav` rows; caption that unfulfilled requests aren't in TLC's trip records. `compare` uses `wav_share`

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
| 30 Oct 2026 | done | `companies/[company].md` and its page-only helpers in `companies/company.js`, built on the real data (as of 2026-08) and on mock data in a scratch copy; `make test` green. One Blocked request for the integrator (thin flag on `by_zone`). Hand-off below |
| 30 Oct 2026 | started | Brief, SPEC §9, contracts, D24/D29 and the L05 kit read; real company files checked |

**Blocked:** none for this lane's work. One request for the integrator (L11's files and the companies contract):

1. **`lyft_vs_uber.by_zone` rows carry no thin flag.** `zones_lyft_ahead` (and the Q4 subtitle) count only zones with enough trips (`zone_counts()` in `publish.py`: not `thin`, i.e. at least `THIN_TRIPS` trips in the month and not a no-pickup zone), but `by_zone` lists every zone with no way to tell which ones were counted. On the real data three zones have Lyft ahead (Rikers Island +53.9 pts, Saint Michaels Cemetery/Woodside +52.6 pts, Governor's Island +33.3 pts) while the finding says one, so the Q4 chart can't match its subtitle. Suggest `publish.py` add `thin: true|false` to each `by_zone` row (the same rule as the count), with the mock generator and `companies.example.json` regenerated. The page already handles it: rows with `thin: true` draw hollow and unlabelled and the chart note changes to "Hollow dots are zones with too few trips in the month to count." Until then the chart draws every zone and its note says the count leaves out zones with too few trips. If you name the field differently, `counted()` in `site/src/companies/company.js` is the one line to change.

**Hand-off**
- Built:
  - `site/src/companies/[company].md`: one template for `/companies/{uber,lyft,yellow,green}`. Header and stat row (the five contract tiles, in the brief's order); share of NYC trips (`shareLine` with the three events); Q4 "Where Lyft beats Uber" on the Uber and Lyft pages only; fare per mile (`fareRange`, the same month a year earlier and the latest month, all four companies); tips (`lineChart`, cab series labelled "card-only"); wheelchair-accessible service (`wav_share` line per app, then one count tile per app for `wav_requests` in the latest month, then a note that unfilled requests aren't in TLC's records so a match rate can't be measured); shared rides (`match_rate` line per app, then a tile per app for `requests`); the comparison block (`compareTable` under the `compare` subtitle with the source caption); "How we measured this" linking to `/methods#tips`.
  - `site/src/companies/company.js` (page-only): `gapScatter` for Q4 (each zone's Lyft-minus-Uber share gap against its change on a year earlier, zero rules, zones where Lyft leads named and drawn larger, tooltip, table view, source caption), `countTiles` (built on `tile()` with `yoy: "none"`), `latestAndYearEarlier`, `tipSeriesLabel`. Pinned Plot and `html` from the components, colours from `palette.js`.
  - Taxi pages: driver share tile "Not reported for this mode" (statTiles); accessible service and shared rides show `notReported(...)` with the file's `wav` / `shared` subtitle as the explanation; a "card-only" note under the stat row when the company's `tip_rate` rows have `card_only`. Every state is driven by `not_reported` and the row flags, not by the company code.
  - A section with no rows or no subtitle shows an empty state instead of throwing. The browser tab reads "{name} | NYC Ride Market" once the data loads (front matter says "Company profile").
- Checked:
  - `make test`: 490 passed, 13 skipped (the existing smoke-test stubs), site build renders all four routes; budgets pass (the Lyft route's data is the largest at 80 KB of 1.5 MB). No digits in the page's markdown prose; no literal colours.
  - Mock data: `make_mock_site_data.py --out` into a scratch copy of `site/`, built and opened: all four routes, mock banner, no runtime errors, three not-reported states on the cab pages.
  - Real data in the browser (`observable preview`): all four pages at 1280 px and 375 px, light and dark; no console errors; no page-level horizontal scroll at 375 px (the compare table scrolls in its own box, as designed); Q4 tooltip and table view work.
- Known limits:
  - The Q4 chart draws thin zones as ordinary dots until the Blocked request lands, and their extreme changes (Governor's Island −66.7 pts) stretch its y axis.
  - The WAV and shared count tiles show the latest month only, with no change line: the file carries no year-earlier change for them and the page computes none.
  - With the real data the Lyft line on the shared chart starts in Jun 2025 (no Lyft shared requests before), and Lyft's match rate rests on a few thousand requests a month.
- Follow-ups:
  - L05 / integrator: at 375 px the share chart's second event label ("Per-minute minimum pay +3.9% (inflation)") runs off the right edge (`eventMarks` in `charts.js` anchors it at the start because it sits left of 55%). It affects every page that uses `shareLine`.
  - L05: the compare block reuses `.nrm-chart` to get a subtitle and caption around `compareTable`; a `subtitle`/`asOf` option on `compareTable` would make that a component concern.
