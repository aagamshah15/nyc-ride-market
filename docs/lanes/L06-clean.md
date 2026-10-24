# L06 · Clean

**Wave** 2 · **Phase** 2 (2 – 15 Nov) · **Spec** §4, §4.1, §4.2 · **Decision** D9 · **Feeds** L07

## Goal

`make clean MONTH=` turns one month of raw files into unified, enriched, flagged trips, keeping every raw row.

## Owns

- `pipeline/clean.py`
- `sql/clean/{hvfhv,yellow,green}.sql` and `sql/clean/derive.sql` (derived columns and flags shared by all three)
- `tests/test_clean_*.py`; raw fixtures built in code under `tests/fixtures/raw/`

## Reads

- `pipeline/schema_map.py` resolver (L03); `config/cbd_zones.csv` and the `pipeline/zones.py` helper (L04); `config/airports.csv`; `config/periods.yaml`; `data/ref/taxi_zone_lookup.csv`

## Starts when

- L03's map covers the target month and L04's draft list exists (a placeholder list is fine for tests)

## Tasks

- [ ] Map raw columns only through the resolver; stop on an unmapped column, naming file and column
- [ ] Unified columns per the SPEC §4 table:
  - `mode` from the license code (HV0003 uber, HV0005 lyft, HV0002 and HV0004 other_hv; an unknown code is an error)
  - `month` = the file's month, not the pickup month
  - taxi `duration_s` from timestamps; green `airport_fee` = 0; `cbd_fee` coalesced to 0
  - `other_fees`, `rider_total_ex_tip`, `is_card`; Y/N flags to BOOLEAN
- [ ] Derived columns (§4.1): `wait_s` (NULL when `request_ts` is NULL), `hour_of_week` (Sunday = 0), boroughs, airports, `cbd_pu` / `cbd_do` / `cbd_touch` (for both zone lists if D9 is agreed), `period`
- [ ] Flags (§4.2), including pickup outside the file's month ± 1 day; `is_valid`
- [ ] Write `data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet` with DuckDB `COPY … PARTITION_BY`, replacing the month atomically
- [ ] Log rows in, rows out and flag counts per mode
- [ ] One month in memory at a time; the SQL does the work

## Tests (expected values worked out by hand)

- Each flag at its boundary: duration 0 / 10800 / 10801 s; miles 0 / 100 / 100.01; fare 0; zones 264, 265 and NULL; wait −1 / 3600 / 3601 s; pickup one day vs two days before the month starts
- `hour_of_week`: Sunday 00:xx → 0, Saturday 23:xx → 167
- `period` at 2025-01-04 23:59:59, 2025-01-05 00:00 and 2025-08-01 00:00
- `rider_total_ex_tip` for an HVFHV row and a yellow row; `cbd_fee` NULL → 0; the `Airport_fee` spelling
- Rows out equal rows in

## Done when

- Real runs on 2024-03 and 2025-03 for all three datasets: row counts match the manifest; flag shares recorded in the status log
- Tests green

## Not this lane

- Aggregation (L07); deciding the zone list (L04)

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
