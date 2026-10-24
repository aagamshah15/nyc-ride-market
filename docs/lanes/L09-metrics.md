# L09 · Metrics library

**Wave** 2 · **Phase** 2–3 · **Spec** §6 · **Feeds** L10, L11

## Goal

Every SPEC §6 metric defined once, as SQL over the aggregate tables, each with a test whose expected value was worked out by hand.

## Owns

- `sql/metrics/*.sql`, except the files `contracts/metrics.md` assigns to L10
- `pipeline/metrics.py`: registers `data/agg/*.parquet` as views, runs a named metric with parameters, returns an Arrow table; CLI `python -m pipeline.metrics <name>` and `--all`
- `tests/test_metrics_<name>.py`

## Tasks

- [x] One file per metric listed in `contracts/metrics.md`, each with a header comment: question(s), params, grain, output columns
- [x] Ratios of sums only; divide with `NULLIF(denominator, 0)`
- [x] Filter modes as SPEC says (driver share: `uber`, `lyft`); taxi tip rate uses card trips only
- [x] `trips_per_hour_worked` reads `ref_indicators` and is marked TLC-reported in its output
- [x] Output columns match `contracts/metrics.md` exactly (tested)

## Tests

- One per metric: a factory fixture, with the expected value worked out by hand in a comment

## Done when

- `python -m pipeline.metrics --all` runs on the G2 aggregates without error
- Tests green

## Not this lane

- The congestion and pay-rise studies (L10); shaping site files or writing findings (L11)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct | done on fixtures | All 24 L09 metrics, the runner and 25 test files. `make test` green (211 passed, 7 skipped). Not yet run on real aggregates (none exist); the integrator runs `--all` at G2 |
| 24 Oct | started | |

**Blocked:** none. Five contract points below are worth pinning, but none stopped the work.

**Hand-off**
- Built:
  - `sql/metrics/*.sql`: the 24 L09 metrics in `contracts/metrics.md`. Each header has `Metric`, `Questions`, `Params`, `Grain`, `Columns` and `Source` lines plus notes.
  - `pipeline/metrics.py`:
    - `run(name, **params)` returns an Arrow table. `run_all(**params)` runs every metric, passing each only the params its SQL uses.
    - `available()`, `parameters(name)`, `header(name)`, `contract_schema(name)` and `check_contract(name, table)` are public too.
    - CLI: `python -m pipeline.metrics <name>` prints CSV; `--all` prints `name: N rows` per metric and exits 1 if any fails; `--param KEY=VALUE` works with both.
    - `STUB_LANE` is removed.
  - Views:
    - every `data/agg/*.parquet` under its file name, including L08's `ref_indicators`
    - `ref_zones` (LocationID SMALLINT, Borough, Zone, service_zone)
    - **`ref_airports`** (LocationID SMALLINT, airport), read from `config/airports.csv` for `airport_fares`
  - Params:
    - `$to_month` defaults to `max(month)` in agg_zone_hour. It accepts `YYYY-MM`, `YYYY-MM-01` or a date, and is normalised to the 1st.
    - `$window` defaults to 3 and `$top_n` to 10; both must be positive integers.
    - Unknown params raise an error.
  - Contract enforcement: `run()` checks every output against `contracts/metrics.md` (names, order, types) and raises `ContractError` on a mismatch. This also covers L10's metrics.
  - Output metadata: `metric`, `params` (JSON of the resolved values; L11 can read `to_month` from it) and `source` (`TLC trip records`, or `TLC-reported` for `trips_per_hour_worked`).
- Checked:
  - One `tests/test_metrics_<name>.py` per metric, each with a factory fixture and its expected values worked out by hand in comments.
  - `tests/test_metrics_runner.py` covers:
    - the views
    - param defaults, coercion and errors
    - contract parsing (29 rows) and the type rules
    - each header's `Columns` and `Params` lines against the contract and the SQL
    - `run_all` and the CLI on a full fixture set of every aggregate table, several months, all modes and zones 132/161/264
  - Mutation spot check: switching `trip_share` to `trips_valid` and `tip_rate` to all-payment tips both fail their tests.
- Known limits:
  - Days in a window (`zone_hour_profile`, `airport_by_hour`) count only the window's months that are in the table, so a missing month doesn't drag per-day and per-week numbers down. This matters at G2, when only one month exists.
  - `agg_od_month` keeps pairs with at least 20 trips per mode, so `top_destinations` and `airport_fares` miss smaller pairs.
  - `agg_airport` has no `trips_all`, so `airport_share` counts valid trips.
  - `tip_rate` and `fare_rates_by_borough` drop boroughs with no valid trips: "Unknown" and "N/A" (zones 264 and 265).
  - `shared_match_rate` keeps zone rows with 0 requests (match_rate NULL).
  - `fare_dist` and `price_volatility` pass `agg_zone_month_dist` through as stored.
- Follow-ups for the integrator (contract wording; none of these blocked the work):
  1. **Types the contract leaves out.** `contracts/metrics.md` types some columns only. The runner applies a type given anywhere in the table to every column of that name, and uses these rules for the rest:
     - VARCHAR: mode, pu_borough, airport, direction, license_class, metric, zone_list, cbd_group, exclusion_reason
     - SMALLINT: do_zone, iso_year, iso_week, year
     - BIGINT: n, requests, matched, rows, valid_rows, f_*, trips_with_cbd_fee
     - DOUBLE: everything else, including `unique_drivers` as TLC reports it

     Please pin these in the contract. L10 needs to know them, because `run()` enforces them on `cp_*` and `pay_event`.
  2. **`top_destinations.share`.** Its denominator is the zone's valid trips from `agg_zone_hour`, as contracts/README.md §7 defines it. The Reads column should add `agg_zone_hour`.
  3. **`zone_hour_profile.mode_share_in_zone`.** This is read as the mode's share of the zone's trips across the whole window and all hours, which is the ≥10% heatmap filter in contracts/README.md §1.
  4. **`ref_airports`.** This view is an addition to the views the contract lists.
  5. **"Prior".** "Prior" and "change" in `zone_share_change` and `lyft_vs_uber` compare with the same month a year earlier, as L11's brief says.
  - The runner parses `contracts/metrics.md` at run time, so a reformat of that table needs `tests/test_metrics_runner.py` to stay green.
