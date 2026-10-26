# L08 · Validation gate

**Wave** 2 · **Phase** 2 · **Spec** §8, §7.2, §3.2 (indicators) · **Decision** D8 · **Feeds** G3, L09, L11, L17

## Goal

`make validate` decides whether the data may be published: it writes `reports/validation.md` and exits non-zero on any failure.

## Owns

- `pipeline/validate.py`, `sql/validate/*.sql`, `tests/test_validate.py`
- Generated: `reports/validation.md` (committed), `data/agg/ref_indicators.parquet`, `data/agg/validation_summary.json`

## Tasks

- [x] Load the indicators CSV into `ref_indicators` without changing values. It's the NYC Open Data copy (D19): the month column is `Year/Month` (`2026-08`), and numbers are plain (no thousands separators). The percent column holds whole numbers such as `79`, and some cells are empty, for example HVFHV `Farebox Per Day`. Confirm against the real file, then set the percent column's type in `tests/factories.py` through the integrator
- [x] Tie-out: trips per day = `SUM(trips_all)` ÷ days in month, against `"Trips Per Day"`, within ±2%, for HVFHV (uber + lyft + other_hv vs `FHV - High Volume`), Yellow and Green. Months the indicators file doesn't have yet are skipped and listed
- [x] Quality drift: `valid_rows / rows` ≥ 95% per month × mode; list any month more than 3 points below its mode's median
- [x] CBD list: share of both-in trips with a fee ≥ 98%; share of neither-in (pass-through) trips with a fee reported, not failed. From `agg_cbd_pairs` (D8), for both zone lists
- [x] Schema: run `python -m pipeline.discover --check`. How it covers months with no local files depends on D11
- [x] Fees: since 2025-01-05, ≥ 95% of trips with `cbd_fee > 0` carry exactly the configured fee for their mode (from `agg_fee_values`, D8); list the other values found
- [x] Report: pass/fail table first, then details. The summary JSON feeds `quality.json`
- [x] Never widen a tolerance. A failure goes to the integrator with the evidence

- [x] D25: the tie-out subtracts the `agg_vendor_month` rows of vendors in `tie_out_exclude_vendors` (`config/sources.yaml`) from the pipeline count before comparing with TLC; the report shows the excluded records per month and class. The tolerance stays ±2%

- [ ] D26: the quality check fails a month × mode below 85% `valid_rows / rows` (was 95%); months more than 3 points below the mode's median stay listed, not failed
- [ ] D27: the tie-out gates on `FHV - High Volume` only; `Yellow` and `Green` keep their own ±2% pass/fail, reported, not gating. `tie_out_exclude_vendors` is emptied (D25 reverted). Rows in `tie_out_exceptions` get status `excepted` with their reason in the report (first one: 2026-06 FHVHV)

## Tests

- Each check passes and fails at its boundary (for example a 2.00% vs a 2.01% gap)
- A month missing from the indicators is listed as skipped, not failed
- Exit code; report sections present

## Done when

- Runs on factory fixtures and on the G2 month
- At G3, the integrator's full run passes, and any failure has been traced to its owning lane

## Not this lane

- Fixing the pipeline when a check fails (the owning lane does that)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 25 Oct | D25 done on fixtures | Merged `integrator/d24-d25` (e92d1c0). The tie-out now subtracts the `agg_vendor_month` records of the vendors in `tie_out_exclude_vendors` before comparing with TLC, and `agg_vendor_month` is a required input. The report's tie-out table gains Records and Excluded columns and states the rule. The tolerance stays ±2%, and the `tie_out` JSON keys are unchanged. Hand-worked G2 case: green 2025-03 has 51,539 records, 1,222 of them vendor 6, against TLC's 1,624 a day. It fails at +2.37% with vendor 6 and passes at −0.05% without. 7 new tests. `make test`: only the expected `tests/test_clean_*.py` (33) and `test_aggregate_tables.py::test_tables_cover_every_aggregate_schema` fail until L06 and L07 land; everything else passes and the site builds. |
| 24 Oct | done on fixtures | Gate built and tested on factory aggregates. The real indicators CSV is loaded into the shared `data/agg/ref_indicators.parquet`. Two contract points wait on the integrator (see Blocked). The real `make validate` runs at G2 and G3 (integrator). |

**Blocked:** none. Both items raised on 24 Oct are settled on `main`:
- `Percent of Trips Paid with Credit Card` is DOUBLE, a whole-number percent, NULL for FHV (contracts §6).
- `months_checked` is the full sorted month list (contracts §5).

**Hand-off**
- Built:
  - `pipeline/validate.py`. The CLI is unchanged (`python -m pipeline.validate`, run by `make validate`) and `STUB_LANE` is gone. It adds one option, `--indicators-only`, which only loads the CSV.
  - `sql/validate/`: `ref_indicators.sql`, `tie_out.sql`, `quality.sql`, `cbd_list.sql` and `fees.sql`, each with a header block for inputs, params and output columns.
  - `tests/test_validate.py`: 53 tests (7 for D25; 1 added by the integrator for D21).
  - What a run does:
    1. Reloads `data/ref/data_reports_monthly.csv` into `data/agg/ref_indicators.parquet`. The header must be exactly the 14 D19 columns. Values are cast but never coerced: a bad value fails the load and isn't turned into NULL.
    2. Registers the aggregates. Months checked = the `config/sources.yaml` scope plus any month found in `agg_zone_hour`, `agg_quality_month`, `agg_cbd_pairs`, `agg_fee_values` or `agg_vendor_month`.
    3. Runs the five checks. A check that can't run (missing table, zone helper still a stub, unreadable footer) fails with the reason; it doesn't stop the gate.
    4. Writes `reports/validation.md` (pass/fail table first, then a section per check) and `data/agg/validation_summary.json` (contract §5).
    5. Exits 0 only when every check passes; on `fail` or `skipped` it exits 1.
  - Tie-out (D25):
    - Pipeline trips = `SUM(agg_zone_hour.trips_all)` minus the `agg_vendor_month` rows whose `vendor_id` is listed under the mode's dataset in `tie_out_exclude_vendors` (`config/sources.yaml`).
    - `validate.tie_out_exclusions()` reads that list; an unknown dataset or a non-integer vendor fails the check. HVFHV records carry no vendor, so they're never touched.
    - The report's table shows Records, Excluded (count and vendor ids, or "—"), then trips per day after the exclusion.
  - Thresholds are module constants taken from SPEC (2, 95, 3, 98, 95); none is a CLI option. Each boundary is computed with integers, so exactly 2.00%, 95% or 98% passes. For example, the tie-out tests `|trips − TLC × days| × 100 ≤ 2 × TLC × days`. Drift points are rounded to 1e-6 to drop float noise.
  - The schema check calls `pipeline.discover.discover` and `.check` in-process (the same check as `--check`) for the three datasets × months checked. It reads local raw footers when present, otherwise remote footers (D11).
- Checked:
  - `make test` on 24 Oct was green: 183 passed, 6 skipped, and the site builds. On 25 Oct, on the D24/D25 branch, the 34 failures are all the expected L06/L07 ones: 33 in `tests/test_clean_*.py` plus `test_aggregate_tables.py::test_tables_cover_every_aggregate_schema`. The other 307 pass (12 skipped) and the site builds.
  - D25 tests, worked by hand:
    - Green 2025-03 as found at G2 (51,539 records, 1,222 of them vendor 6; TLC 1,624 × 31 = 50,344) passes at 1,623.1 a day, −0.05%, with the config's exclusion. With none it fails at 1,662.5, +2.37%. The report row shows `1,222 (vendor 6)`.
    - Yellow vendor 7's 500 records stay counted; only vendor 6's 310 leave, so the result is exactly 10,000.0 a day.
    - A stray uber row with `vendor_id` 6 leaves HVFHV unchanged.
    - A missing `agg_vendor_month` fails the tie-out with the reason.
    - The real config gives `{yellow: [6], green: [6]}`; an unknown dataset fails the check.
  - Fixture tests:
    - Tie-out ±2.00% passes and ±2.01% fails.
    - The tie-out sums uber + lyft + other_hv, and divides by 29 days in Feb 2024.
    - A month missing from the indicators is skipped and listed, and the check still passes. A single missing class is named.
    - A month with no pipeline trips fails.
    - A missing CSV, or a CSV with another header, fails the tie-out even when an older parquet exists.
    - Quality 95.00% passes, 94.99% fails.
    - Drift at exactly 3.00 points isn't listed; at 3.01 it's listed but doesn't fail.
    - CBD 98.00% passes, 97.99% fails. Pass-through is reported, not failed. The wide list counts a borderline pair.
    - 2025-01 is left out of the CBD check.
    - CBD fails while `zones.cbd_zone_ids` is a stub. With no trips it's `skipped`, and the gate fails.
    - The schema check passes on L03's real-shaped local files and fails on an unreadable footer.
    - Fees 95.00% passes, 94.99% fails. Taxi and ride-hail fees are told apart; other values are listed largest first; zero and negative fees and months before 2025-01 are ignored.
    - The summary matches the §5 example via `assert_matches_contract`.
    - The report's table comes first and every section is present.
    - Exit codes 0/1 and `--indicators-only`.
  - On real data:
    - The indicators CSV has 914 rows, 2010-01 → 2026-08. `Year/Month` is always `YYYY-MM`, and month × class pairs are unique. Numbers are plain: no thousands separators, no `%` signs, no BOM. The percent column holds whole numbers from 30 to 90. That column and `Farebox Per Day` are blank on all 557 FHV rows; `Trips Per Day Shared` is blank on 787.
    - The shared `ref_indicators.parquet` matches the factory schema, every value equals the CSV's, and all 32 months from 2024-01 to 2026-08 exist for FHV - High Volume, Yellow and Green, so G3 skips nothing.
    - Early tie-out read from the raw files in the shared folder, raw rows ÷ days vs TLC:

      | Month | HVFHV | Yellow | Green |
      |---|---:|---:|---:|
      | 2024-01 | −0.001% | +0.94% | +0.01% |
      | 2026-08 | +0.001% | +0.12% | **+1.66%** |

      These counts include vendor 6, and every class passes either way. With D25, Green 2026-08 should come in below +1.66%, since that figure counted vendor 6's records.
- Known limits:
  - The CBD check leaves out 2025-01 (D22) and gates on the core list only (D21). The wide list's result is reported. The report states both.
  - The CBD and fee checks pass or fail on totals over the months (per mode for fees), as in the §5 shape. Single months below the threshold are listed, not failed.
  - D25 excludes only the configured vendors (vendor 6, yellow and green). Any other vendor TLC turns out not to count would show as a tie-out gap; adding it needs the user's approval and a config edit.
  - "Exactly the configured fee" means equal as stored, with no rounding to cents.
  - `months_checked` covers the whole scope, so at G2 the 31 months without aggregates fail the tie-out as "no pipeline trips". That's expected, and the gate exits 1.
  - The schema check reads about 96 remote footers paced 1 s apart, about 2 minutes and ~190 requests. L03 measured CloudFront's limit at roughly 300 requests per 5 minutes, so don't run `make discover` just before.
  - `reports/validation.md` isn't committed by this lane. A fixture-built report would misstate the data, so the integrator commits the one from the real G2/G3 run.
- Follow-ups:
  - **Integrator at G2:** merge L06 and L07's D25 work, so clean carries `vendor_id` and `agg_vendor_month` exists; without it the tie-out fails with "missing data/agg/agg_vendor_month.parquet". Re-run `make month MONTH=2025-03`, then `NYC_DATA_DIR=… make validate`. The gate exits 1 because of the 31 months with no aggregates. G2 holds if the three 2025-03 tie-out rows pass (green should come in near −0.05%, with 1,222 vendor-6 records shown as excluded) and the 2025-03 quality, CBD (core gates), schema and fee results pass. Read them in the tie-out table and the sections of `reports/validation.md`. Route a failure to its owner: tie-out or quality → L06/L07; CBD → L04 (list) or L06 (flags); fees → L06; schema → L03.
  - **At G3:** after the back-fill, `make validate` must exit 0. Commit `reports/validation.md`.
  - **L17:** run `python -m pipeline.ingest --ref --force` before `make validate` so the indicators are current; without `--force`, `make ref` keeps the old copy (L02). Open the issue from `reports/validation.md`. The deploy guard reads `status == "pass"`.
  - **L09:** `ref_indicators.parquet` is in the shared `data/agg/`. `python -m pipeline.validate --indicators-only` rebuilds it without running the gate.
  - **Contract idea:** a `drift` flag on the `quality` rows would let the methods page show drift months. Today they appear only in the check's summary text.
