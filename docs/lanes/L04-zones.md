# L04 · Zones, congestion-zone list, airports, map geometry

**Wave** 1 · **Phase** 1 (draft), refined in 2 · **Spec** §3.3, §7, §9.2 (`taxi_zones.geojson`) · **Decision** D9 · **Feeds** L06, L07, L08, L10, L11, L14

## Goal

A defensible list of taxi zones inside the Congestion Relief Zone, confirmed airport zones, and a simplified zone map under 1 MB.

## Owns

- `pipeline/zones.py`, `config/cbd_zones.csv`, `config/airports.csv`, `reports/cbd_zones.md`, `tests/test_zones.py`
- Generated, not committed: `data/ref/taxi_zones.simplified.geojson`

## Tasks

- [x] Load `taxi_zones.zip` with DuckDB `spatial`; check its CRS and reproject to WGS84 for the GeoJSON
- [x] Compare the lookup CSV with the shapefile: IDs 1–263 present, duplicates, name or borough mismatches; record findings in the report
- [x] Draft `cbd_zones.csv` with columns `LocationID, zone, borderline, note`: Manhattan zones mostly south of 60th St. Write up every borderline call, with its reason, in `reports/cbd_zones.md`
- [x] Helper `cbd_zone_ids(zone_list="core" | "wide")`: core excludes borderline zones, wide includes them (used by L06 and L07)
- [x] Exploratory fee check on one 2025 HVFHV month, run on raw data in `data/scratch/L04/`: share of trips with `cbd_congestion_fee > 0` by pickup and by drop-off zone. Use it to refine the borderline list; record the results
- [x] Confirm `1,EWR`, `132,JFK`, `138,LGA` against the lookup
- [x] Simplify with mapshaper to under 1 MB, keeping `LocationID`, `zone`, `borough`

## Tests

- Helper returns the expected IDs for both lists
- GeoJSON is under 1 MB and has 263 distinct LocationIDs (or the documented exceptions)
- Airports file matches the lookup

## Done when

- Draft list and report merged for G1; refined after the exploratory fee check
- GeoJSON generated and under budget

## Not this lane

- The formal SPEC §7.2 threshold check (L08)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct 2026 | done | Draft list refined by the fee check on 2026-08 HVFHV (a post-pricing month, in place of a 2025 one); GeoJSON 388 KB; airports confirmed. Branch `claude/elegant-benz-06b02b` |

**Blocked:** none

**Hand-off**
- Built:
  - `pipeline/zones.py`: `cbd_zone_ids("core" | "wide")`, `airport_zones()` and `load_cbd_zones()` (typed rows, for L11's methods page). `python -m pipeline.zones` builds `data/ref/taxi_zones.simplified.geojson` and runs every check; `--check` only checks; `--explore YYYY-MM` reruns the fee check into `data/scratch/L04/`.
  - `config/cbd_zones.csv`: 47 rows. `core` is 38 zones (`borderline=false`). The 9 borderline zones are 43, 140, 141, 142, 143, 237 (straddle 60th St) and 103, 104, 105 (islands with no road access). `borderline` is the literal `true` / `false`. `note` is short public text; the full reasons are in `reports/cbd_zones.md`.
  - `config/airports.csv`: unchanged (`1,EWR` · `132,JFK` · `138,LGA`); confirmed against the lookup.
  - `reports/cbd_zones.md`: lookup vs shapefile findings, method, each borderline call with its reason, and the fee-check tables.
  - `tests/test_zones.py`: 24 tests.
- Checked:
  - The shapefile (18 Feb 2026) has 263 polygons and LocationIDs 1–263 once each. Names and boroughs match the lookup exactly; every geometry is valid. Its CRS is EPSG:2263, reprojected to EPSG:4326 (lon/lat).
  - GeoJSON: 388,275 bytes, 263 distinct IDs, properties `LocationID`, `zone`, `borough`, exterior rings clockwise, every vertex inside the NYC lon/lat box. A rendered preview looked right.
  - Fee check, 2026-08 HVFHV: both-in fee share is 99.70% for `core` and 97.91% for `wide`. Pickup fee share is 96.2–99.8% for core zones, 54–70% for borderline ones and at most 43% for Manhattan zones wholly north.
  - `make test` green.
- Known limits:
  - The 60th St line is approximate (about half a block). The calls don't depend on it, because the fee data separate the groups.
  - Mapshaper 0.7.98 writes RFC 7946 (counter-clockwise) winding by default, so the build passes `gj2008` to get clockwise exteriors as the contract requires. The kickoff note's "clockwise is mapshaper's default" is out of date for this version.
  - The test that runs the real build is skipped when DuckDB `spatial` isn't installed locally, so tests stay offline; in CI it skips. The checks themselves are pure Python and always run.
  - About 96 small overlaps between neighbouring zones come from the TLC source and survive simplification; they don't show at site scale.
- Follow-ups:
  - **L08 / integrator:** `wide` fails SPEC §7.2's 98% both-in threshold by construction (97.91% on 2026-08), because its borderline zones are mostly north of 60th St. Decide whether the gate applies to `core` only, with `wide` reported. Per SPEC §7.2 this needs a written reason, and the decision is the integrator's.
  - **Integrator:** no make target builds the GeoJSON yet. Consider `make zones` (`$(PY) -m pipeline.zones`), or calling it after `make ref`. The first run installs DuckDB `spatial` if it's missing (network).
  - **L06:** read the lists with `zones.cbd_zone_ids("core")` and `("wide")`, or in SQL with `read_csv('config/cbd_zones.csv')` and `WHERE NOT borderline` for core.
