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

- [ ] D25: the tie-out subtracts the `agg_vendor_month` rows of vendors in `tie_out_exclude_vendors` (`config/sources.yaml`) from the pipeline count before comparing with TLC; the report shows the excluded records per month and class. The tolerance stays ±2%

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
| 24 Oct | done on fixtures | Gate built and tested on factory aggregates. The real indicators CSV is loaded into the shared `data/agg/ref_indicators.parquet`. Two contract points wait on the integrator (see Blocked). The real `make validate` runs at G2 and G3 (integrator). |

**Blocked** (neither stops the lane; both need contract edits only the integrator makes)
1. **Percent column type.** I checked the real file (914 rows, 2010-01 → 2026-08). `Year/Month` is always `YYYY-MM` and (month, class) pairs are unique. Numbers are plain: no thousands separators or `%` signs, and no BOM. `Percent of Trips Paid with Credit Card` holds whole numbers from 30 to 90 (e.g. `79` = 79%). It's blank on all 557 FHV rows, as are `Farebox Per Day` (557 rows) and `Trips Per Day Shared` (787 rows). Proposal: type it `DOUBLE`, values unchanged (79.0, not 0.79), NULL when blank. That's three edits, to be made together:
   - `tests/factories.py`: in `AGG_SCHEMAS["ref_indicators"]`, `("Percent of Trips Paid with Credit Card", F64)`, with default `None` (the default row is FHV).
   - `contracts/README.md` §6: replace "stays as text until L08 sees the real file" with "DOUBLE, a whole-number percent (79 = 79%), NULL for the FHV classes".
   - Lane files, which the integrator can edit at merge: `sql/validate/ref_indicators.sql`, change that line to `CAST("Percent of Trips Paid with Credit Card" AS DOUBLE) AS "Percent of Trips Paid with Credit Card"`. `tests/test_validate.py::test_ref_indicators_keeps_names_and_values`, change `"79"` to `79.0`. That test compares the loaded schema with the factory, so it fails until both sides agree.
   Until then the loader writes the column as text, as the contract says now.
2. **`months_checked` shape.** The §5 example `["2024-01", "2026-08"]` reads as either a [first, last] range or a list cut short. I write the full sorted list of every month checked. That's unambiguous, it can carry a gap, and `[0]` and `[-1]` still give the range. Please confirm, and pin it in `contracts/README.md` §5.

**Hand-off**
- Built:
  - `pipeline/validate.py`. The CLI is unchanged (`python -m pipeline.validate`, run by `make validate`) and `STUB_LANE` is gone. It adds one option, `--indicators-only`, which only loads the CSV.
  - `sql/validate/`: `ref_indicators.sql`, `tie_out.sql`, `quality.sql`, `cbd_list.sql` and `fees.sql`, each with a header block for inputs, params and output columns.
  - `tests/test_validate.py`: 45 tests.
  - What a run does:
    1. Reloads `data/ref/data_reports_monthly.csv` into `data/agg/ref_indicators.parquet`. The header must be exactly the 14 D19 columns. Values are cast but never coerced: a bad value fails the load and isn't turned into NULL.
    2. Registers the aggregates. Months checked = the `config/sources.yaml` scope plus any month found in `agg_zone_hour`, `agg_quality_month`, `agg_cbd_pairs` or `agg_fee_values`.
    3. Runs the five checks. A check that can't run (missing table, zone helper still a stub, unreadable footer) fails with the reason; it doesn't stop the gate.
    4. Writes `reports/validation.md` (pass/fail table first, then a section per check) and `data/agg/validation_summary.json` (contract §5).
    5. Exits 0 only when every check passes; on `fail` or `skipped` it exits 1.
  - Thresholds are module constants taken from SPEC (2, 95, 3, 98, 95); none is a CLI option. Each boundary is computed with integers, so exactly 2.00%, 95% or 98% passes. For example, the tie-out tests `|trips − TLC × days| × 100 ≤ 2 × TLC × days`. Drift points are rounded to 1e-6 to drop float noise.
  - The schema check calls `pipeline.discover.discover` and `.check` in-process (the same check as `--check`) for the three datasets × months checked. It reads local raw footers when present, otherwise remote footers (D11).
- Checked:
  - `make test` is green: 183 passed, 6 skipped, and the site builds.
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
    - The shared `ref_indicators.parquet` matches the factory schema, every value equals the CSV's, and all 32 months from 2024-01 to 2026-08 exist for FHV - High Volume, Yellow and Green, so G3 skips nothing.
    - Early tie-out read from the raw files in the shared folder, raw rows ÷ days vs TLC:

      | Month | HVFHV | Yellow | Green |
      |---|---:|---:|---:|
      | 2024-01 | −0.001% | +0.94% | +0.01% |
      | 2026-08 | +0.001% | +0.12% | **+1.66%** |

      All pass if clean keeps every row. Green 2026-08 sits near the 2% limit; that's TLC's figure, not a pipeline fault, so watch it.
- Known limits (readings of SPEC for the integrator to confirm):
  - The CBD check leaves out 2025-01. Pricing began on 5 Jan and `agg_cbd_pairs` has no day grain, so the fee-less 1–4 Jan trips would drag the both-in share down. Over the scope that's about 0.5 points, which could fail 98% by itself. The report says so.
  - The CBD and fee checks pass or fail on totals over the months (per zone list, per mode), as in the §5 shape. Single months below the threshold are listed, not failed.
  - "Exactly the configured fee" means equal as stored, with no rounding to cents.
  - `months_checked` covers the whole scope, so at G2 the 31 months without aggregates fail the tie-out as "no pipeline trips". That's expected, and the gate exits 1.
  - The schema check reads about 96 remote footers paced 1 s apart, about 2 minutes and ~190 requests. L03 measured CloudFront's limit at roughly 300 requests per 5 minutes, so don't run `make discover` just before.
  - `reports/validation.md` isn't committed by this lane. A fixture-built report would misstate the data, so the integrator commits the one from the real G2/G3 run.
- Follow-ups:
  - **Integrator at G2:** merge L04 (or `make validate`'s CBD check fails with "zones.cbd_zone_ids (lane L04)"), L06 and L07. Run `make month MONTH=2025-03`, then `NYC_DATA_DIR=… make validate`. The gate exits 1 because of the 31 months with no aggregates. G2 holds if the three 2025-03 tie-out rows pass and the 2025-03 quality, CBD (core and wide), schema and fee results pass. Read them in the tie-out table and the sections of `reports/validation.md`. Route a failure to its owner: tie-out or quality → L06/L07; CBD → L04 (list) or L06 (flags); fees → L06; schema → L03.
  - **At G3:** after the back-fill, `make validate` must exit 0. Commit `reports/validation.md`.
  - **L17:** run `python -m pipeline.ingest --ref --force` before `make validate` so the indicators are current; without `--force`, `make ref` keeps the old copy (L02). Open the issue from `reports/validation.md`. The deploy guard reads `status == "pass"`.
  - **L09:** `ref_indicators.parquet` is in the shared `data/agg/`. `python -m pipeline.validate --indicators-only` rebuilds it without running the gate.
  - **Contract idea:** a `drift` flag on the `quality` rows would let the methods page show drift months. Today they appear only in the check's summary text.
