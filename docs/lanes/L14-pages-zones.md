# L14 · Pages: Zones

**Wave** 4 · **Phase** 4 · **Spec** §9.1, §9.2 · **Decision** D13 · **Answers** Q1, Q8, Q10 · **Data** `zones/index.json`, `zones/{zone}.json`, `taxi_zones.geojson`

## Goal

263 zone pages from one template, plus the `/zones` index with the city-wide maps (if D13 is agreed).

## Owns

- `site/src/zones/[zone].md`, `site/src/zones/index.md`

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).
- Zone 1 (Newark Airport) is marked `thin` in both years since G4: TLC vehicles don't pick up at Newark, so its page leads with drop-offs and its pickup tiles are null. Grey it out on the maps like other thin zones. 12 zones are MultiPolygons (`contracts/README.md`), so map code must handle both geometry types

## Tasks

- [x] Zone page: tiles for trips per day, ride-hail share, median and 90th-percentile wait, top destination; share trend; 24 × 7 heatmap by mode; waits; top destinations linking to their zone pages
- [x] Thin zones (islands, very few trips): null percentiles and short series show a clear "too few trips" state
- [x] Index: level map (ride-hail share, sequential blues) and change map (share change vs a year earlier, diverging, centred on 0); a searchable table linking to zone pages; a Q10 view of where yellow cabs still win
- [x] Zones 264 and 265 never get pages
- [x] Check build time and output size for all 263 pages

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- All 264 routes build (263 zones + the index); every zone file is under 50 KB and every route within budget

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 30 Oct 2026 | done | Merged main (acbf13f fixes the `/zones/` nav path, Blocked 1). `make test` green on this branch with no local changes: 490 passed, 13 skipped; 263 links validated |
| 30 Oct 2026 | built | `zones/index.md` and `zones/[zone].md` built against the real data (as of 2026-08). The build needed a one-character config fix outside L14's files (Blocked 1). Hand-off below |
| 30 Oct 2026 | started | Read SPEC §9, contracts, components, G4 review; profiled every zone file (7 thin, all non-thin files complete) |

**Blocked** (for the integrator; all are shared files outside L14's Owns):

1. **Resolved by the integrator in acbf13f.** **The `/zones` nav entry broke the build.** `observablehq.config.js` listed `{name: "Zones", path: "/zones", source: "zones/index.md"}`. In Framework 1.13.4, `"/zones"` resolves to `src/zones.md`: see `normalizePath` in `config.js` and `findPage` in `loader.js`. So once `zones/index.md` existed, the build failed with `Not found: /zones`. The fix is `path: "/zones/"`, which Framework normalises to `/zones/index`. The integrator made that change on main, and this branch has merged it.
2. **The pinned Inputs ships without its stylesheet.** `page.js` exports Inputs from `npm:@observablehq/inputs@0.12.0`. Framework adds `inputs.css` only when a page imports the bare specifier `npm:@observablehq/inputs` (`getImplicitStylesheets` in `libraries.js`). Tables and inputs from `page.js` therefore render unstyled: `Inputs.table` loses its scroll box and spills over the caption and footer. The zones table works around this with a plain table and L05's `.nrm-table-scroll`. Other page lanes (L12, L13, L15, L16) will hit the same problem. A fix for L05: have `page.js` also load `observablehq:stdlib/inputs.css`, or add an import that Framework recognises.
3. **Finding links to `/zones` (no slash) 404 in the preview.** Three findings in `home.json` have `"page": "/zones"`, and `page.js` `siteUrl()` turns that into `<root>/zones`. Checked 30 Oct on this branch, with acbf13f merged:
   - **Framework preview** (`make site-dev`, Framework 1.13.4): `GET /zones` returns `404` with the plain-text body `Not found: /zones`. `/zones/` returns 200 (the index), and `/zones/index` returns `302` to `/zones/`.
   - **Built site:** `dist/` has `zones/index.html` and no `zones.html`. Served by a plain static server (`python3 -m http.server`), `GET /zones` returns `301` to `/zones/`, which returns 200.
   - **GitHub Pages:** not tested here, since there's no deploy. Its documented behaviour is the same directory-to-slash redirect, so the link should work once deployed (under the `/nyc-ride-market/` base too). Only the preview breaks.
   - **Link check:** Framework's build doesn't catch these, because the links are built from JSON at runtime. Its link check covers only static links in the markdown.
   - L14 changed neither `page.js` nor the data; the fix is for the shared code.

**Hand-off**
- Built:
  - **`/zones`** (`zones/index.md`): the title and three tiles from `zones/index.json`, then three choropleths from `charts.js` `choropleth`:
    - ride-hail share (sequential);
    - change vs a year earlier (diverging, centred on 0);
    - Q10: yellow-cab share (sequential). The six zones where yellow leads are the six darkest. A table beside the map lists them, from rows with `top_mode = "yellow"` and not thin, each with yellow share, its change and ride-hail share, linking to the zone pages.
  - Every map links each zone to its page. Thin zones are left out of the map data, so they draw in the muted grey. A note under the maps names them from the data.
  - "Every zone" is a searchable, sortable table of all 263 zones linking to their pages. Thin rows show "Too few trips" and no figures, so Newark's junk pickup values never appear.
  - No new map component was needed (`choropleth` covers all three maps), so there's no Blocked note for one.
  - **`/zones/{1..263}`** (`zones/[zone].md`): a crumb (All zones · zone number · borough · congestion-zone flag), the title and five tiles (trips per day, ride-hail share, median and 90th-percentile wait, top destination), then four charts:
    - share trend (`shareLine` with the `events.json` rules);
    - 24 × 7 heatmap by mode;
    - monthly median wait by mode (`lineChart`, ride-hail only, says so);
    - top destinations (`barChart`, zones 1–263 only; zone 265 is left out because the subtitle already gives the share leaving the city), then a line of links to each destination's page.
  - Every chart has its JSON subtitle, a source caption and a table view. The page title comes from JSON; the browser tab shows the zone name.
  - **Thin zones** (`flags.thin`: zones 1, 2, 103, 104, 105, 110 and 199) show the title, the tiles (null tiles read "Too few trips") and one `tooFewTrips` state in place of the four charts. This follows the titles L11 generates for them ("too few to profile", "No pickups were recorded", Newark's drop-off title). Defensive empty states cover a non-thin zone with an empty section, though none has one in the 2026-08 data.
  - Zones 264 and 265 get no pages; the build has none.
- Checked:
  - `make test` on this branch after merging main: 490 passed, 13 skipped (smoke-test stubs, as on main); the site build validated 263 links.
  - Build: `npm run build` takes about 6.2 s for all 265 pages (home, the zones index and 263 zone pages).
  - Output: `dist` is 13.1 MB in total. Each zone page is 13 kB of HTML plus 97–136 kB of files, of which about 94 kB is the shared stylesheet with the inlined Inter font, so the zone data itself is at most about 42 KB. The index is 18 kB of HTML plus 549 kB of files: `zones/index.json` 64 KB and `taxi_zones.geojson` 388 KB. All pages share 662 kB of cached JS.
  - Data files: the largest zone file is 39,681 bytes (zone 132), under 50 KB, and every route is within its 1.5 MB budget (`test_site_data_within_budget`).
  - In the browser, at 1280 px and 375 px, in light and dark: JFK Airport (132, busy), Jamaica Bay (2, thin), Newark Airport (1), Governor's Island (103, no pickups) and the index, including search, sort and thin rows. No horizontal page scroll at 375 px; the wide tables scroll inside their own boxes.
  - The markdown has no digits outside code, CSS and tag names.
- Known limits:
  - The Q10 view is a yellow-share map plus a list of the leading zones, not a categorical "leading mode" map. It matches the subtitle and uses the component as it is.
  - Thin zones show no charts, even where the file has a share trend and heatmap. With under 100 trips a month those charts are noise, and for Newark they're junk. Ask if the share trend should come back for thin zones.
  - The thin note reuses `tooFewTrips` ("this zone had fewer"). For Newark, the title explains the real reason: pickups there aren't TLC trips.
  - `waits.by_hour` isn't drawn because the file has no subtitle for it.
  - Destination names longer than the bar chart's label margin are shortened with "…" on phones; the link line under the chart keeps the full names.
- Follow-ups:
  - L05, `lineChart` event labels: at 375 px, "Per-minute minimum pay +3.9% (inflation)" is cut off at the right edge of every share chart on the site.
  - L05, dark diverging ramp: the dark midpoint is the same muted token as the "no data" fill, so in dark mode thin zones look the same as zones with about zero change. Light mode separates them, though only just (`#F2F2F2` midpoint against `#C9CDD2`).
  - L05, `barChart`: its label margin caps at 40% of the width, so long labels spill into the page gutter on phones. This page shortens them itself.
  - L11, `zones/index.json` row for zone 1: it still carries pickup values (trips per day 15.5, ride-hail share 0.21%, yellow share 99.6%, `top_mode` yellow), while `zones/1.json` has those tiles null. The pages don't show them, but the two files disagree.
