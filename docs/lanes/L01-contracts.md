# L01 · Contracts

**Wave** 0 · **Run in** integrator space (recommended) or its own agent · **Spec** §4, §5, §6, §9.2–§9.3 · **Decisions** D7–D10, D13 · **Unblocks** L05, L07–L16

## Goal

Pin every interface two lanes share, with executable examples, so downstream lanes build in parallel against fixtures and mock data instead of waiting.

## Owns

- `contracts/README.md`: index; number and date formatting rules shared by `findings.py` and `format.js`; shape of `validation_summary.json`; how nulls are represented
- `contracts/metrics.md`: one row per metric file (name, params, grain, output columns and types, source tables, questions)
- `contracts/site/*.example.json`: one per SPEC §9.2 file (a single example zone file)
- `contracts/site/pages.yaml`: route → data files it loads; methods-page anchors
- `tests/factories.py`: builders for unified clean trips (SPEC §4, §4.1, §4.2) and every aggregate table (SPEC §5 plus agreed D7–D10), with defaults and per-row overrides
- `tests/contract_check.py`: `assert_matches_contract(actual, example)` checking keys, types and array element shape (no new dependency)
- `tests/test_contracts.py`
- `scripts/make_mock_site_data.py`: writes contract-shaped mocks (all 263 zones) to `site/src/data/` with `as_of_month: "MOCK"`; run by `make site-mock`

## Tasks

- [ ] Keep every key SPEC §9.2 names. Add keys; never rename them
- [ ] Pin what SPEC leaves open:
  - tile keys per page, from the brief's "Headline stats per page" table
  - the keys of `airports.json`, `congestion.json`, `drivers.json` and `prices.json` (one key per chart)
  - per page, a generated `title` and a `subtitles` map (one finding per chart), so page markdown carries no numbers
- [ ] Chart data as tidy long rows with explicit unit fields; months as `YYYY-MM-01`
- [ ] Null rules: taxi waits, percentiles below n = 100, modes with no WAV or shared data
- [ ] Metric list covering SPEC §6 and every tile and chart in the examples, for example: `trip_share`, `driver_share`, `fare_rates`, `fare_dist`, `price_volatility`, `wait_time`, `pay_per_hour`, `trips_per_hour_worked`, `tip_rate`, `wav_match_rate`, `shared_match_rate`, `fee_revenue`, `airport_share`, `airport_fares`, `zone_share_change`, `cp_effect`, `pay_event`
- [ ] Methods anchors: `#cleaning`, `#flags`, `#cbd-zones`, `#validation`, `#congestion-method`, `#pay-rise-method`, `#tips`, `#waits`, `#limits`, `#downloads`
- [ ] Mocks for every route fit the 1.5 MB budget (largest zone page counted)
- [ ] User approves the site contracts before L05 and the page lanes start, since they fix what the site shows

## Done when

- An example exists for every SPEC §9.2 file; `make site-mock` fills `site/src/data/`
- Factories build every aggregate table; `tests/test_contracts.py` green
- Contracts approved; later changes go through the integrator

## Not this lane

- Implementing metrics, publish or pages

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 2026-10-24 | done | User approved the site contracts and D15–D18; decisions marked accepted |
| 2026-10-24 | built, awaiting approval | Built in the integrator space; proposed D15–D18 in `docs/decisions.md` |

**Blocked:** none

**Hand-off**
- Built: `contracts/README.md` (envelope, page keys, units and precision, mode codes and groups, formatting rules, null rules, `validation_summary.json`, schema pins, field notes); `contracts/metrics.md` (29 metrics, 5 of them L10's, with params, grain and exact output columns); `contracts/site/tiles.yaml` (26 tiles), `contracts/site/pages.yaml` (9 routes, budgets, 10 methods anchors); 13 generated examples in `contracts/site/`; `tests/factories.py` (`CLEAN_TRIPS_SCHEMA`, `AGG_SCHEMAS` for 10 tables, `make_trip` / `clean_trips` / `write_clean`, `agg_row` / `agg_table` / `write_agg`); `tests/contract_check.py`; `tests/test_contracts.py` (41 tests); `scripts/make_mock_site_data.py` (`make site-mock`, `--examples`)
- Checked: `make test` green (69 passed, 1 skipped); mocks match every example; every route's mock files fit 1.5 MB (largest is `/congestion-pricing`); largest mock zone file 39 KB; examples regenerate identically; `make site-mock && make site-build` works and the mock files were removed afterwards; mocks refuse to overwrite non-MOCK files; a test fails if a tracked file in `site/src/data/` is MOCK
- Known limits: the checker allows `null` anywhere and can't type-check positions whose example is `null` or an empty list (e.g. `flags.airport`, `not_reported` in the Uber example); the mock geojson is a grid, not real zones; zone-file size needs revisiting for the Phase 6 back-fill
- Follow-ups: L08 should replace the `ref_indicators` percent column type once it sees the real CSV; later contract changes go through the integrator
