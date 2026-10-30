# L07 · Aggregate

**Wave** 2 · **Phase** 2 · **Spec** §5 · **Decisions** D7, D8, D9, D10 · **Feeds** L08, L09, L10

## Goal

`make aggregate MONTH=` rebuilds that month's rows in every aggregate table, storing sums so any roll-up stays correct.

## Owns

- `pipeline/aggregate.py`, `sql/agg/<table>.sql` (one file per table), `tests/test_aggregate_*.py`

## Reads

- Clean partitions in the SPEC §4 schema. While L06 is in progress, build from `tests/factories.py`, not real data

## Tasks

- [x] One SQL file per table: `agg_zone_hour`, `agg_zone_month_dist`, `agg_od_month`, `agg_airport`, `agg_week_cbd`, `agg_fees_month`, `agg_quality_month`, plus the D8 tables (`agg_cbd_pairs`, `agg_fee_values`), the D10/D16 city-wide rows (`pu_zone = 0`, each mode plus `ride_hail` and `all`) and D15's `rider_total_ex_tip` in `agg_od_month`. `AGG_SCHEMAS` in `tests/factories.py` is the exact output schema; read clean files with `hive_partitioning = false` (D18)
- [x] Month rewrite: existing table minus that month, plus the new rows, written to a temp file, then renamed over `data/agg/{table}.parquet`. Other months untouched; a re-run gives identical output
- [x] Rules:
  - `trips_all` counts all rows; other sums use `is_valid` rows, except `agg_fees_month`, which sums every row (D23)
  - wait sums exclude `f_wait` and NULL waits
  - `card_*` columns for taxis only
  - percentiles via `quantile_cont` on valid rows; distribution rows only where n ≥ 100
  - OD pairs only with ≥ 20 valid trips that month
- [x] `agg_airport`: `from` = pickup at the airport, `to` = drop-off at the airport; an airport-to-airport trip counts in both (document this); hour of day from pickup
- [x] `agg_week_cbd`: ISO year and week from `pickup_ts`; treated = `cbd_touch`; with `month` (D7) and `zone_list` (D9) if agreed
- [x] A column comment block at the top of each SQL file

- [x] D24: in `agg_zone_hour`, `wav_match` counts trips with `wav_request AND wav_match`, and `shared_match` counts `shared_request AND shared_match`
- [x] D25: new table `agg_vendor_month` (month × mode × vendor_id: `rows`, over all rows), with the same month-scoped rewrite; schema in `AGG_SCHEMAS`
- [ ] D29: `agg_zone_hour` gains `wav_trips` (BIGINT, last column): valid rows with `wav_match`, requested or not; NULL for cabs. `wav_req` and `wav_match` unchanged

## Tests (expected values worked out by hand)

- Sums per table from a factory fixture
- A percentile on a five-row fixture
- The n ≥ 100 and ≥ 20 thresholds at the boundary
- Rewriting month B leaves month A identical; a re-run is idempotent
- Airport direction, including an airport-to-airport trip
- An ISO week spanning two months (with D7)

## Done when

- `make aggregate MONTH=2025-03` on real clean data builds every table (G2)
- Tests green

## Not this lane

- Metric formulas (L09, L10); validation thresholds (L08)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 27 Oct 2026 | D29 applied | Merged `main` and `integrator/d28-d29` (ccf8df7). `agg_zone_hour` gains `wav_trips` (last column): valid rows with `wav_match`, requested or not; NULL for cabs. `wav_req` and D24's `wav_match` unchanged. A table file in an older layout (e.g. without `wav_trips`) is no longer an error: it moves to `data/agg_stale/` and the table restarts with the month being run, with a warning naming the other months to re-aggregate. Aggregate tests pass; the only `make test` failures are L09's `wav_match_rate` → `wav_service` swap and `test_publish.py` behind it |
| 25 Oct 2026 | D24, D25 applied | Merged `integrator/d24-d25` (e92d1c0). D24: `agg_zone_hour` counts a WAV or shared match only on a trip that requested it. D25: new table `agg_vendor_month` (all rows, one NULL-vendor row per ride-hail mode). Every table's query now runs before any file is written, so clean files from before D25 (no `vendor_id`) stop the run with nothing touched. All tests pass except L06's `tests/test_clean_*` (33), which wait on L06's `vendor_id`. Real runs wait on L06 + integrator |
| 24 Oct 2026 | D23 applied | `agg_fees_month` now sums all rows, flagged ones included (D23); fee tests recomputed and a flagged-trip fee test added; `make test` green. Real run still waits on L06 + integrator |
| 24 Oct 2026 | done on fixtures; real run waiting on L06 + integrator | All nine tables built and tested on factory fixtures; `make test` green. `make aggregate MONTH=2025-03` on real clean data (G2) waits for L06 to land and for the integrator to run it |
| 24 Oct 2026 | started | |

**Blocked:** none

**Hand-off**
- Built:
  - `pipeline/aggregate.py`: `make aggregate MONTH=YYYY-MM` / `python -m pipeline.aggregate --month YYYY-MM` (exit 1 with a message when the month can't be aggregated); `aggregate_month(month, tables=TABLES)` for scripts. `STUB_LANE` removed.
  - `sql/agg/{agg_zone_hour, agg_zone_month_dist, agg_od_month, agg_airport, agg_week_cbd, agg_fees_month, agg_quality_month, agg_cbd_pairs, agg_fee_values, agg_vendor_month}.sql`: one SELECT each over the view `trips`, with a column comment block. Output types are cast in the SQL and equal `AGG_SCHEMAS` exactly (names, order, types).
  - Input: `data/clean/mode=*/month={YYYY-MM}/part-0.parquet`, read with `hive_partitioning = false` (D18). The run stops if the files hold rows for another month or if none exist.
  - Month rewrite: first every table's rows for the month are computed; a failing query stops the run with every file untouched. A file in an older layout is set aside (limit 9). Then each table becomes its other months' rows plus the new month, sorted on every column (`ORDER BY ALL`), written to `{table}.parquet.tmp` beside it and renamed over it. A table is always written, even with no rows (for example `agg_cbd_pairs` before 2025), so readers find every file.
  - Thresholds: `DIST_MIN_N = 100`, `OD_MIN_TRIPS = 20` in `aggregate.py`, passed to the SQL as DuckDB variables. The `agg_cbd_pairs` start month comes from `congestion_pricing_start` in `config/periods.yaml` (2025-01).
- Checked:
  - `tests/test_aggregate_tables.py` (15) and `tests/test_aggregate_rewrite.py` (12, after D29), expected values worked out by hand in comments. They cover: exact schemas for all ten tables, empty ones included; `agg_zone_hour` sums with valid and invalid rows, f_wait, card and cash cabs, shared and WAV, an unknown-zone group, and the tie-out property (SUM(trips_all) = rows); WAV and shared matches counted only on requesting trips, so an accessible-vehicle trip nobody asked for isn't a match (D24; the test fails on the old SQL), while `wav_trips` counts it (D29: trips A and C of A–G, not B without a WAV, not invalid G; 0 where no trip ran in one; NULL for cabs); `agg_vendor_month` with vendors 1, 2, 6 and a missing VendorID, an invalid row still counted, one NULL row per ride-hail mode even with a stray value, and per-mode totals equal to `agg_quality_month.rows` (D25); hour of week 0 and 167; percentiles on five trips (p10 2.8, p50 6, p90 9.2, wait p90 276); the n ≥ 100 boundary (100 kept, 99 dropped, an invalid trip not counted) with city-wide `pu_zone = 0` rows for each mode plus `ride_hail` and `all`; OD pairs at 20 vs 19 valid trips; airport direction, including JFK → LGA and a JFK round trip; both zone lists in `agg_week_cbd`; quality, fees, fee values and CBD pairs on one fixture; a flagged trip's fees counted in `agg_fees_month` but not in `agg_zone_hour` (D23); CBD pairs starting in 2025-01; an ISO week (2025-W14) split across the March and April files; ISO year ≠ calendar year (2024-12-30 → 2025-W01); rewriting April twice (once with revised data) leaving March's rows identical; a re-run writing byte-identical files; exact sums (ten 0.10 tips = 1.0); errors for a missing month, rows from another month and clean files without `vendor_id`, each leaving every file untouched; a table file in an older layout (without `wav_trips`) set aside to `data/agg_stale/` with a warning naming its other months, the table restarting with the current month and the next month merging as usual; the CLI.
  - After D24/D25 on the merged branch: everything outside `tests/test_clean_*` passes (304 passed, 12 skipped) and the site builds. `make test` stops on the 33 `tests/test_clean_*` failures, all from `sql/clean/*.sql` not yet giving `vendor_id` (L06's part of D25), as the integrator expected.
  - After D29 on `integrator/d28-d29`: aggregate, contract and smoke tests pass (90 passed, 13 skipped); everything outside `test_publish.py`, `test_metrics_runner.py` and `test_metrics_wav_match_rate.py` passes (400 passed, 14 skipped); the site builds. `make test` has 10 failures and 23 errors, all from `wav_match_rate` no longer being in `contracts/metrics.md` (L09's `wav_service`, D29) and `test_publish.py` failing behind it; none touch aggregate.
  - Scale check on a synthetic 22.35M-row month (generated, not TLC data; uber 14M, lyft 5M, yellow 3.3M, green 50k): about 4 s on this 12-core Mac, byte-identical re-run, peak RSS about 5 GB (3.1 GB without `agg_zone_month_dist`).
- Known limits (choices made inside the brief; the integrator may want to confirm the first four):
  1. **Exact sums.** Money and miles are summed as `DECIMAL(18, 4)`, then stored as DOUBLE. Plain DOUBLE sums came out different in the last bits on each of five runs of the same 20M-row query (parallel aggregation changes the order), so "a re-run gives identical output" needs this. It is exact for TLC values (cents, hundredths of a mile). A value with more than four decimals would be rounded at the fourth; a value ≥ 10^14 or NaN would stop the run with a cast error rather than pass silently.
  2. **Zero vs NULL.** A sum over a group with no valid rows (e.g. a zone-hour holding only flagged trips) is 0. Columns that don't apply to a mode are NULL (`driver_pay`, waits, shared and WAV for cabs; `card_*` for ride-hail).
  3. **Waits in `agg_zone_month_dist`.** NULL for cab modes and for the `all` group (an all-modes wait would really be ride-hail only); `ride_hail` includes `other_hv`. The n ≥ 100 rule counts valid trips, not trips with a usable wait.
  4. **`agg_week_cbd`.** A NULL `cbd_touch` (only possible with a NULL zone) counts as control, the same as zones 264 and 265.
  5. **`agg_fees_month` sums all rows** (D23, decided by the user): a fee was charged whether or not the trip's distance, duration or fare looks odd. Every other money sum keeps the `is_valid` rule. The QA tables `agg_cbd_pairs` and `agg_fee_values` also use all rows, like the tie-out. `agg_fee_values` keeps the 0 value and every month.
  6. Airport-to-airport trips count once in each direction, so never sum `from` and `to` together (stated in the SQL).
  7. Memory: `agg_zone_month_dist` holds every valid trip's ratios about four times (zone, city-wide mode, `ride_hail`, `all`). Peak RSS was about 5 GB for 22M rows and did not drop with `NYC_DUCKDB_MEMORY=1GB`, since quantile state sits outside DuckDB's limit. This fits the 24 GB laptop and a 16 GB GitHub runner. If it ever doesn't, run the four levels as separate queries.
  8. Every table's query runs before any file is written, so a query error or a layout change leaves all files as they were. Files are then replaced one at a time: if the process dies while writing, some tables hold the new month and some the old, and re-running the month fixes it. There is no lock, so don't run two aggregates on one data folder at once.
  9. A table file whose columns differ from what its SQL now gives (written before a schema change, e.g. without D29's `wav_trips`) is stale. The run moves it to `data/agg_stale/{table}.parquet` (outside `data/agg/`, so metrics and release don't pick it up; a later stale file of the same table replaces it), restarts the table with the month being run, and prints a warning naming the other months it held. Until those months are aggregated again, that table holds fewer months than the rest.
- Follow-ups:
  - **Integrator, after L06 lands:** `make clean MONTH=2025-03`, then `make aggregate MONTH=2025-03` (G2). Check that SUM(`trips_all`) in `agg_zone_hour` per mode equals `rows` in `agg_quality_month` and the clean row count (and so the manifest), and that all ten files exist in `data/agg/`.
  - **Integrator, for D24/D25:** every month already aggregated (2025-03 at G2) needs `make clean` with L06's `vendor_id` and then `make aggregate` again. D24 changes `wav_match` and `shared_match` in `agg_zone_hour`, and `agg_vendor_month` only gets rows for months aggregated from clean files that carry `vendor_id`. Aggregating an old clean file now stops with "rebuild them with make clean MONTH=…" and touches nothing.
  - **Integrator, for D29:** `make aggregate` for every month. The first run sets the old `agg_zone_hour` aside to `data/agg_stale/` and restarts it; the remaining months fill it back in. When all months are back, delete `data/agg_stale/`.
  - L08: `agg_vendor_month` has one row per month × mode × vendor_id over all rows (NULL vendor for ride-hail), so the D25 tie-out subtracts the excluded vendors' `rows` from `trips_all`. `agg_fee_values` includes `cbd_fee = 0`, so filter `cbd_fee > 0`. `agg_cbd_pairs` keeps NULL and unknown zones and starts at 2025-01.
  - L09 / L10: `agg_zone_month_dist` waits are NULL for `all`. `agg_week_cbd` sums over `month` give whole ISO weeks.
