# L05 · Site foundation

**Wave** 1 (after L01) · **Phase** 4 groundwork · **Spec** §9.1, §9.3–§9.5 · **Decision** D13 · **Feeds** L12–L16

## Goal

The Framework project, design tokens and a small component kit, so page lanes assemble pages without writing styles, colours or chart boilerplate.

## Owns

- `site/observablehq.config.js` (after the L00 seed), `site/src/style.css`
- `site/src/components/{palette,format,statTiles,charts,page}.js`
- Self-hosted Inter under `site/src/assets/`
- A component gallery page `site/src/dev/components.md`, kept out of the nav and removed or excluded before launch
- `tests/test_site_budget.py`

## Tasks

- [x] Confirm in the pinned 1.13.4 docs: `[param]` routes, `dynamicPaths`, and `observable.params` inside `FileAttachment` template literals. Record what works in the status log
- [x] Pin every `npm:` import to an exact version (for example `npm:@observablehq/plot@0.6.17`); otherwise Framework resolves `@latest` from the network at each build
- [x] Config: nav; footer text exactly as SPEC §9.5; `dynamicPaths` for the four companies and zones 1–263; the `/zones` index if D13 is agreed
- [x] `palette.js` exactly as SPEC §9.5; light and dark via `prefers-color-scheme`; the diverging interpolator
- [x] `format.js`: counts, percentages, dollars, durations, dates as `Jan 2025`, following `contracts/README.md`
- [x] `statTiles.js`: 3–4 tiles, value plus change vs a year earlier, tabular figures, a null state
- [x] `charts.js`: one helper per SPEC §9.4 row (share line with labelled rules at 2025-01-05 and 2025-08-01; sequential and diverging choropleths; 24 × 7 heatmap; effect dot with p10–p90 rule; fare strip or box; 100% stacked bars). Each helper requires a subtitle, axis labels with units and a source caption, and takes colours only from `palette.js`
- [x] `page.js`: the SPEC §9.3 template (title from JSON, stat row, chart blocks, "How we measured this" link to `/methods#anchor`)
- [x] One column below 640 px
- [x] Check the mode palette in a colour-blindness simulator and in dark mode; record results
- [x] Budget test: sum each route's files from `contracts/site/pages.yaml`; fail above 1.5 MB

## Done when

- `make site-mock && make site-build` green
- The gallery shows every helper in light and dark, at 375 px and desktop width
- The budget test runs as part of `make test`

## Not this lane

- Page content (L12–L16); producing data (L11)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct 2026 | done | Config, styles, Inter, palette, format, tiles, charts, page template, gallery and budget test built; `make site-mock && make site-build` and `make test` green. Hand-off below |
| 24 Oct 2026 | started | Framework 1.13.4 routing checked in the docs and in a scratch build |

**Blocked:** none for this lane's work. Requests for the integrator, outside L05's files:

1. **CI needs site data once pages read it.** `make test` runs `make site-build` on a checkout with no `site/src/data/` (nothing is committed until L11 publishes). Any page that loads a data file then fails the build with `Not found: /data/tiles.json` (checked in a scratch build). Suggest the Makefile's `test` target, or `ci.yml`, run `make site-mock` before `make site-build` when `site/src/data/home.json` is absent (`site-mock` already refuses to overwrite real data). L12–L16 hit this with their first page; L05 doesn't, because the gallery is a draft.
2. **Dark-mode ramps.** SPEC §9.5 gives only the light diverging ramp. `palette.js` adds a dark one (accent dark → muted dark → `#E07B39`) and flips the sequential blues in dark mode. Record in `docs/decisions.md` if you treat that as a decision.
3. **Labels for comparison metrics that aren't tiles.** `compare[]` rows include `fare_per_min`, `wav_match_rate` and `shared_match_rate`, which have no label in `tiles.yaml`; `page.js` labels them itself. Moving those labels into the contract (L01) would keep them in one place.

**Framework 1.13.4 checks** (docs at tag v1.13.4: `docs/params.md`, `docs/config.md`, `docs/imports.md`; plus the installed source and scratch builds)

- `[param]` routes and `dynamicPaths`: both work and were added in 1.11.0 (SPEC §9.1 says 1.12). A scratch build of `companies/[company].md` and `zones/[zone].md` built 4 + 263 pages in about 10 s.
- `observable.params` in a `FileAttachment` template literal works, e.g. ``FileAttachment(`../data/zones/${observable.params.zone}.json`)``. It's the documented exception to the static-literal rule, and each page registers only its own file (the Uber page ships `uber.json` only), so per-route budgets match what is shipped.
- A nav entry or dynamic path whose page doesn't exist fails the build (ENOENT). The config therefore lists only the page files present in `src/`; the nav and the 4 + 263 dynamic paths fill in as L12–L16 land.
- npm pins: an exact `x.y.z` skips the registry lookup; anything else resolves from the local cache, or else `@latest`. Pinned: `@observablehq/plot@0.6.17`, `@observablehq/inputs@0.12.0`, `htl@0.3.1` (htl 1.0.0 exists, but Inputs 0.12 is built on 0.3). Framework's own client bundle still resolves its recommended libraries (react-dom, lodash, arquero, echarts, leaflet and others) to `@latest` version numbers at every build. Nothing is downloaded unless a page uses one. Pages must import `Plot`, `Inputs` and `html` from the components, never the implicit globals.
- Fonts: 1.13.4 can't bundle a `.woff2` referenced from `style.css` (open issue observablehq/framework#786). Inter is therefore inlined as a data URL in `assets/fonts/inter.css` (about 65 KB, cached with the stylesheet), with the `.woff2` and its licence beside it. `globalStylesheets: []` drops Framework's default Google Fonts request.

**Colour-blindness check** (dataviz `validate_palette.js`: Machado 2009 at severity 1.0, ΔE in OKLab × 100, target 8 and floor 6; light surface `#FFFFFF` from the air theme, dark `#161616` from near-midnight)

| Check | Light | Dark |
|---|---|---|
| Mode colours, neighbours in SPEC order (stacks, legends) | worst 11.8, green ↔ yellow (protan): pass | worst 9.1, green ↔ yellow (protan): pass |
| Mode colours, all pairs (lines) | green ↔ Lyft 5.9 (deutan): below floor | other ride-hail ↔ Lyft 5.7 (protan): below floor; yellow ↔ Uber 14.5 for normal vision (floor 15) |
| Contrast against the page | yellow 2.45:1 and other ride-hail 2.64:1, below 3:1 | all ≥ 3:1 |
| Diverging poles | 27.5: pass | 25.1: pass |
| Ride-hail accent beside Uber and Lyft | worst 15.1: pass | worst 9.7: pass |

The validator also flags Uber and other ride-hail as grey, and the dark tones as brighter than its band. SPEC chose those on purpose, so they aren't CVD problems. The palette is locked, so the components compensate:

- legends and stacks use SPEC's order, so Lyft never touches green or other ride-hail;
- every multi-series chart has a legend, and line charts label their line ends from 480 px wide;
- stacked segments carry share labels, every mark has a tooltip, and every chart has a table view.

If yellow's light-mode contrast should pass on its own, that's a SPEC §9.5 change for the user.

**Hand-off**

- Built:
  - `observablehq.config.js`:
    - nav limited to existing pages: Congestion pricing, Companies (4), Zones (D13), Airports, Drivers, Prices, Methods;
    - `dynamicPaths` for the 4 companies and zones 1–263 (no 264 or 265), added once their page file exists;
    - footer exactly as SPEC §9.5;
    - no TOC, pager or search.
  - `style.css`: Framework default plus air (light) and near-midnight (dark), Inter, tiles, chart frames, null states, the comparison table, and one column below 640 px. It has no literal colours, only theme variables.
  - `components/palette.js`: SPEC §9.5 tokens exactly, plus:
    - the fixed `modeOrder`;
    - group colours (ride-hail = accent, cabs = yellow, all modes = text colour);
    - dark ramps and `inkOn`;
    - Plot scale helpers.
  - `components/format.js`: contracts §3 rules, mode names, tile-unit and change dispatch, and axis ticks. Choices outside §3:
    - trips per hour shows 2 decimals ("1.54 trips/hour");
    - ratios show 1 decimal ("2.6×");
    - counts below 1,000 keep their stored decimal ("842.3");
    - axis ticks are compact (200K, $10M);
    - waits are drawn in minutes;
    - dates are always parsed as UTC.
  - `components/statTiles.js`: `statTiles(page, tilesJson, {keys, yoyLabel})`. Labels and units come from `tiles.json`. Null states: "Not reported for this mode" (`not_reported`), "Too few trips" (`flags.thin`), "Not available", and "No year-earlier value" for a null `yoy`.
  - `components/charts.js`: every helper needs `subtitle` and `asOf` (`dataset: "monthly indicators"` for TLC-reported data), takes `width` and `dark`, and adds the source caption and a table view. Each helper throws if a required label is missing. Helpers:
    - `shareLine`, which needs `events`;
    - `lineChart` (month, week, hour or numeric x; `events` or `rules`; series colours by mode, group or token);
    - `choropleth` (sequential or diverging, with an optional `href` per zone);
    - `hourHeatmap` (24 × 7, one grid per mode on a shared scale);
    - `effectDots`, `fareRange` and `rangeDots`;
    - `fareStrip`;
    - `stackedBars100`;
    - `barChart`;
    - `monthlyColumns`;
    - `tableView`;
    - a pinned `Plot` re-export.
  - `components/page.js`:
    - `pageHeader` (mock banner + h1 from JSON + tiles), `pageTitle` and `mockBanner`;
    - `howWeMeasured(anchor)`;
    - `notReported`, `tooFewTrips` and `emptyState`;
    - `compareTable`, which adds the card-only note for cab tips;
    - `findingsList`;
    - `siteUrl(path)`, for links that survive the GitHub Pages base path;
    - pinned `Inputs` and `html`.
  - `assets/fonts/`: Inter variable font (Latin subset, `@fontsource-variable/inter@5.3.0`, OFL).
  - `dev/components.md`: the gallery. It is `draft: true`, so it only shows in `make site-dev` at `/dev/components` and never ships; there's nothing to remove at launch.
  - `tests/test_site_budget.py`:
    - each route's files from `pages.yaml` ≤ 1.5 MB, and each zone file < 50 KB, on whatever is in `site/src/data/`;
    - checker unit tests;
    - `format.js` against the contracts §3 examples;
    - `palette.js` against SPEC;
    - no hex, `rgb()` or `hsl()` colours anywhere in `site/src` outside `palette.js`;
    - every component parses (Node).
- Checked:
  - `make site-mock && make site-build` and `make test` are green (83 passed, 1 skipped).
  - The gallery was viewed in the browser in light and dark, at 375 px and at desktop width: 16 charts and 18 tiles, no errors, and no horizontal page scroll at 375 px (the comparison table scrolls in its own box).
  - The table view opens. The methods and findings links resolve from the site root in preview and in a static build.
  - Inter loads.
  - A scratch build with stand-in `[company].md`, `[zone].md` and `methods.md` produced 4 + 263 + 1 pages with the right nav and footer.
  - A build with no site data passes with the draft gallery.
- Known limits:
  - The mock zone map is a grid, so the real map's shape and height haven't been seen. `choropleth` fits a Mercator projection to whatever geometry it gets.
  - Line end labels are off below 480 px; the legend carries identity there.
  - Faceted charts (heatmap, effects, airport split) are stacked small multiples with headings, not Plot facets, so each panel is full width on a phone.
  - Building the gallery on desktop needs mock data (`make site-mock`).
- Follow-ups:
  - The three integrator requests above.
  - L14: check the real zone map's height once L04's geometry lands.
  - L12–L16: page markdown imports from `../components/*.js` (`./components/` at the top level); give each page a plain front-matter `title` for the browser tab (the h1 comes from JSON); and pass `width` and `dark` to every chart.
