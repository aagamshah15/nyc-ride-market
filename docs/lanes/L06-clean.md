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

- [x] Map raw columns only through the resolver; stop on an unmapped column, naming file and column
- [x] Unified columns per the SPEC §4 table:
  - `mode` from the license code (HV0003 uber, HV0005 lyft, HV0002 and HV0004 other_hv; an unknown code is an error)
  - `month` = the file's month, not the pickup month
  - taxi `duration_s` from timestamps; green `airport_fee` = 0; `cbd_fee` coalesced to 0
  - `other_fees`, `rider_total_ex_tip`, `is_card`; Y/N flags to BOOLEAN
- [x] Derived columns (§4.1): `wait_s` (NULL when `request_ts` is NULL), `hour_of_week` (Sunday = 0), boroughs, airports, `cbd_pu` / `cbd_do` / `cbd_touch` for the core list and `cbd_pu_wide` / `cbd_do_wide` / `cbd_touch_wide` for the wide list (D9), `period`. `tests/factories.py` (`CLEAN_TRIPS_SCHEMA`) is the exact output schema
- [x] Flags (§4.2), including pickup outside the file's month ± 1 day; `is_valid`
- [x] Write one file per mode to `data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet`, keeping every column including `mode` and `month` (D18: readers use `hive_partitioning = false`, so plain `COPY … TO` per mode rather than `PARTITION_BY`); replace the month atomically
- [x] Log rows in, rows out and flag counts per mode
- [x] One month in memory at a time; the SQL does the work

- [ ] D25: carry `vendor_id`, the cab files' `VendorID` (SMALLINT, NULL for HVFHV), as the last unified column after `street_hail` (`schema_map.UNIFIED_COLUMNS`, `config/schema_map.yaml`); output still equals `CLEAN_TRIPS_SCHEMA`

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
| 24 Oct 2026 | done | Built and tested; 38 clean tests and `make test` green. Real runs on 2024-01 and 2026-08 (the integrator's substitute for the brief's 2024-03 and 2025-03, since those two months are already downloaded and fall before and after pricing). Rows out = rows in = manifest for every dataset. Flag shares are under Hand-off. **Gate risk:** green (both months) and yellow 2026-08 are below SPEC §8's 95% valid share |
| 24 Oct 2026 | started | |

**Blocked:** none

**Hand-off**
- Built:
  - `pipeline/clean.py`: `make clean MONTH=YYYY-MM` / `python -m pipeline.clean --month YYYY-MM` (exits 1 with a message naming the file when the month can't be cleaned); `clean_month(month)` for scripts returns rows, valid rows and flag counts per mode. `STUB_LANE` removed.
  - Per raw file: DESCRIBE → `schema_map.find_problems` with types (unmapped column first, then missing column or changed type; the error names the file, e.g. `raw/yellow/2025-03.parquet`, and the column) → `schema_map.resolve` and `select_range` build the view `src`. A raw column that alone feeds a unified column takes the unified name and keeps its raw value (`Airport_fee` → `airport_fee`, `payment_type` → `is_card`, `total_amount` → `rider_total_ex_tip`). Columns that share one (`bcf`, `sales_tax`; `extra`, `mta_tax`, `improvement_surcharge`) keep their map names. The range's `constant` and `nulls` are added under the unified name. So `sql/clean/*.sql` reads the same names in every month range (the 2024 `cbd_fee` constant and the 2025+ `cbd_congestion_fee` column both arrive as `src.cbd_fee`).
  - `sql/clean/{hvfhv,yellow,green}.sql`: `src` → the 24 SPEC §4 columns in order, with the map's rules. `clean.py` checks the column list against `schema_map.UNIFIED_COLUMNS`. Licence codes come from `hv_license` in `config/sources.yaml`; any other code, or a NULL, stops the run, listing the codes and their row counts.
  - `sql/clean/derive.sql`: the §4.1 derived columns and §4.2 flags, cast to `CLEAN_TRIPS_SCHEMA`'s exact order and types. Boroughs come from `data/ref/taxi_zone_lookup.csv` (`zones.read_lookup`); airports from `zones.airport_zones()`; `cbd_*` from `zones.cbd_zone_ids("core")` and `cbd_*_wide` from `("wide")` (D9); periods from `config/periods.yaml`. Python loads these into a 265-row `ref_zone` table, joined twice (pickup and drop-off).
  - Output: one `COPY` per mode with rows (zstd), each file self-contained with `mode` and `month` (D18), written first to `data/clean/.staging-{month}-{pid}/`. Only after all three datasets pass (rows in = the manifest's `rows`, rows out = rows in, per mode and in total) are the files renamed into `mode={mode}/month={YYYY-MM}/part-0.parquet`, one `os.replace` each. A mode with no rows this time loses its old file. The staging folder is always removed.
  - `tests/fixtures/raw/raw_trips.py`: raw files built in code with the real files' column names, order and types (yellow's `Airport_fee`, `cbd_congestion_fee` from 2025-01, cab `request_source` from 2026-06), a manifest entry per file and a small zone lookup.
- Checked:
  - `tests/test_clean_columns.py` (16), `tests/test_clean_flags.py` (14), `tests/test_clean_run.py` (8), with expected values worked out by hand in comments:
    - every flag at its boundary: duration 0 / 1 / 10800 / 10801 / −60 s from `trip_time`, and 0 / 10800 / 10801 / −814 s from cab timestamps; miles 0 / 0.01 / 100 / 100.01 / −1; fare 0 / 0.01 / −3; zones 264, 265 and NULL at either end; wait −1 / 0 / 3600 / 3601 s; pickups at 28 Feb 00:00 (inside), 27 Feb 23:59:59 and 27 Feb 00:00 (outside), 1 Apr 23:59:59 (inside), 2 Apr 00:00 (outside) for the March file;
    - `is_valid` ignoring `f_wait`; NULL measures setting their flags; a NULL request giving NULL `wait_s` and no `f_wait`; a duration beyond INTEGER (NULL and flagged);
    - `hour_of_week` Sunday 00:30 → 0, Saturday 23:10 → 167, Tuesday 08:10 → 56;
    - `period` at 2025-01-04 23:59:59 (pre_cp), 2025-01-05 00:00 (post_cp), 2025-07-31 23:59:59 (post_cp) and 2025-08-01 00:00 (post_pay);
    - `rider_total_ex_tip` 24.90 (HVFHV) and 24.15 (yellow); `cbd_fee` NULL → 0 for all three; 2024 files with no cbd column → 0; `Airport_fee` and `airport_fee` spellings; green `airport_fee` 0, `street_hail`, `is_card`; licence codes to modes, and an unknown code;
    - boroughs, airports and the core and wide CBD flags (Central Park is wide only);
    - an unmapped, a missing and a retyped column, each naming file and column; `month` = the file's month for a 28 Feb pickup in the March file; exact schema per mode file;
    - rows out = rows in with flagged rows kept; a manifest mismatch; a missing raw file, manifest entry or zone lookup; a re-run replacing the month and dropping an emptied mode; a failed run (green fails after fhvhv and yellow staged) leaving the previous files intact; the CLI.
  - `make test` green: 338 passed, 12 skipped, site build OK.
  - Real runs (`NYC_DATA_DIR` = the shared data folder), about 2.8 s per month on this Mac, peak RSS 1.4–1.5 GB; both months together take 1.1 GB on disk. Every file's schema equals `CLEAN_TRIPS_SCHEMA`. Totals: 22,685,105 rows for 2024-01 and 23,870,883 for 2026-08, equal to the manifest's rows. Every flag count was recounted with a separate query straight on the raw files and matched exactly.
  - Flag shares (share of the mode's rows; `other_hv` has no rows in either month):

    | Month | Mode | Rows | Valid | f_time | f_miles | f_fare | f_zone | f_wait |
    |---|---|---:|---:|---:|---:|---:|---:|---:|
    | 2024-01 | uber | 14,432,755 | 96.18% | 0.00% (556) | 0.03% | 0.00% (253) | 3.80% | 0.66% |
    | 2024-01 | lyft | 5,231,175 | 96.16% | 0.00% (237) | 0.02% | 0.14% | 3.69% | 1.80% |
    | 2024-01 | yellow | 2,964,624 | 95.78% | 0.10% | 2.04% | 1.29% | 1.06% | — |
    | 2024-01 | green | 56,551 | **93.57%** | 0.53% | 5.16% | 0.41% | 1.14% | — |
    | 2026-08 | uber | 14,800,058 | 95.32% | 0.01% | 0.03% | 0.01% | 4.66% | 1.12% |
    | 2026-08 | lyft | 5,693,422 | 95.12% | 0.01% | 0.02% | 0.00% (26) | 4.88% | 1.21% |
    | 2026-08 | yellow | 3,336,716 | **94.12%** | 1.32% | 3.57% | 0.52% | 0.80% | — |
    | 2026-08 | green | 40,687 | **92.55%** | 0.36% | 4.43% | 1.69% | 1.80% | — |

- Known limits (choices made inside the brief):
  1. **Flags are never NULL.** A NULL duration, pickup, miles or fare fails its test and sets the flag. A NULL wait sets no `f_wait`, since wait metrics already drop NULL waits (L07). The real files have no such NULLs.
  2. **INTEGER overflow.** `duration_s` and `wait_s` are INTEGER (`CLEAN_TRIPS_SCHEMA`). A value outside that range (about 68 years, possible only with a garbled cab timestamp) is stored as NULL, and its flag is worked out on the full value. None in either month: cab durations run −18,031,051 to 567,324 s.
  3. **Raw NULLs stay NULL.** SPEC coalesces only `cbd_fee`. Yellow `Airport_fee` and `congestion_surcharge` are NULL in 140,162 rows (4.7%) in 2024-01 and 921,181 (27.6%) in 2026-08, and stay NULL. Green `payment_type` and `trip_type` NULL (3,415 and 6,313 rows) give NULL `is_card` and `street_hail`. A NULL Y/N flag would stay NULL (none seen).
  4. **Zones** are cast to SMALLINT with a plain CAST, so a value outside its range stops the run rather than being lost; every zone in both months is in 1–265. Zones 264 and 265 get the lookup's boroughs (`Unknown`, `N/A`). Every HVFHV `f_zone` row in both months is zone 265 (outside NYC); none are 264.
  5. **Replacing the month** is one rename per file after everything passes, not one atomic step across five folders. If a run stops during the renames (a few milliseconds), re-run the month. There is no lock against two cleans of one month at once.
  6. **No file for an empty mode.** `other_hv` (HV0002, HV0004) has no trips in 2024-01 or 2026-08, so it has no folder. L07 reads whatever files exist.
  7. `period` is set by `pickup_ts`, so garbled old pickups in a 2026 file (e.g. 2009) read `pre_cp`. They always carry `f_time`.
- Follow-ups:
  - **Integrator (gate risk, G3):** under SPEC §4.2's flag rules, the quality-drift check (`valid_rows / rows` ≥ 95%, SPEC §8) would fail for green 2024-01 (93.57%), yellow 2026-08 (94.12%) and green 2026-08 (92.55%). Uber and Lyft 2026-08 pass narrowly (95.32%, 95.12%). The causes are in the data: zero-distance trips (yellow 119,059 = 3.6% in 2026-08; green 4.4–5.1%), yellow durations ≤ 0 (43,185 in 2026-08, against 870 in 2024-01) and HVFHV trips to or from zone 265 (3.7–4.9%). The independent recount rules out a clean bug. Changing a flag or the threshold is the user's call (CLAUDE.md), so nothing was changed here.
  - **L07 / L09:** yellow `airport_fee` is NULL in 27.6% of 2026-08 rows; `SUM` skips them, so airport-fee totals count only rows that report the fee.
  - **Integrator, G2:** `make clean MONTH=2025-03` needs the 2025-03 raw files, which aren't downloaded yet.
