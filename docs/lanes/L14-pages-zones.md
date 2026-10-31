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

- [ ] Zone page: tiles for trips per day, ride-hail share, median and 90th-percentile wait, top destination; share trend; 24 × 7 heatmap by mode; waits; top destinations linking to their zone pages
- [ ] Thin zones (islands, very few trips): null percentiles and short series show a clear "too few trips" state
- [ ] Index: level map (ride-hail share, sequential blues) and change map (share change vs a year earlier, diverging, centred on 0); a searchable table linking to zone pages; a Q10 view of where yellow cabs still win
- [ ] Zones 264 and 265 never get pages
- [ ] Check build time and output size for all 263 pages

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
