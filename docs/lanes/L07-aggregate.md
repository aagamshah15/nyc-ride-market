# L07 · Aggregate

**Wave** 2 · **Phase** 2 · **Spec** §5 · **Decisions** D7, D8, D9, D10 · **Feeds** L08, L09, L10

## Goal

`make aggregate MONTH=` rebuilds that month's rows in every aggregate table, storing sums so any roll-up stays correct.

## Owns

- `pipeline/aggregate.py`, `sql/agg/<table>.sql` (one file per table), `tests/test_aggregate_*.py`

## Reads

- Clean partitions in the SPEC §4 schema. While L06 is in progress, build from `tests/factories.py`, not real data

## Tasks

- [ ] One SQL file per table: `agg_zone_hour`, `agg_zone_month_dist`, `agg_od_month`, `agg_airport`, `agg_week_cbd`, `agg_fees_month`, `agg_quality_month`, plus the D8 tables and the D10 city-wide row if agreed
- [ ] Month rewrite: existing table minus that month, plus the new rows, written to a temp file, then renamed over `data/agg/{table}.parquet`. Other months untouched; a re-run gives identical output
- [ ] Rules:
  - `trips_all` counts all rows; other sums use `is_valid` rows
  - wait sums exclude `f_wait` and NULL waits
  - `card_*` columns for taxis only
  - percentiles via `quantile_cont` on valid rows; distribution rows only where n ≥ 100
  - OD pairs only with ≥ 20 valid trips that month
- [ ] `agg_airport`: `from` = pickup at the airport, `to` = drop-off at the airport; an airport-to-airport trip counts in both (document this); hour of day from pickup
- [ ] `agg_week_cbd`: ISO year and week from `pickup_ts`; treated = `cbd_touch`; with `month` (D7) and `zone_list` (D9) if agreed
- [ ] A column comment block at the top of each SQL file

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
