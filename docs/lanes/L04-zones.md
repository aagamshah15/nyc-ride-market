# L04 · Zones, congestion-zone list, airports, map geometry

**Wave** 1 · **Phase** 1 (draft), refined in 2 · **Spec** §3.3, §7, §9.2 (`taxi_zones.geojson`) · **Decision** D9 · **Feeds** L06, L07, L08, L10, L11, L14

## Goal

A defensible list of taxi zones inside the Congestion Relief Zone, confirmed airport zones, and a simplified zone map under 1 MB.

## Owns

- `pipeline/zones.py`, `config/cbd_zones.csv`, `config/airports.csv`, `reports/cbd_zones.md`, `tests/test_zones.py`
- Generated, not committed: `data/ref/taxi_zones.simplified.geojson`

## Tasks

- [ ] Load `taxi_zones.zip` with DuckDB `spatial`; check its CRS and reproject to WGS84 for the GeoJSON
- [ ] Compare the lookup CSV with the shapefile: IDs 1–263 present, duplicates, name or borough mismatches; record findings in the report
- [ ] Draft `cbd_zones.csv` with columns `LocationID, zone, borderline, note`: Manhattan zones mostly south of 60th St. Write up every borderline call, with its reason, in `reports/cbd_zones.md`
- [ ] Helper `cbd_zone_ids(zone_list="core" | "wide")`: core excludes borderline zones, wide includes them (used by L06 and L07)
- [ ] Exploratory fee check on one 2025 HVFHV month, run on raw data in `data/scratch/L04/`: share of trips with `cbd_congestion_fee > 0` by pickup and by drop-off zone. Use it to refine the borderline list; record the results
- [ ] Confirm `1,EWR`, `132,JFK`, `138,LGA` against the lookup
- [ ] Simplify with mapshaper to under 1 MB, keeping `LocationID`, `zone`, `borough`

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
