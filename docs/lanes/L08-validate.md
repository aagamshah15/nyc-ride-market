# L08 · Validation gate

**Wave** 2 · **Phase** 2 · **Spec** §8, §7.2, §3.2 (indicators) · **Decision** D8 · **Feeds** G3, L09, L11, L17

## Goal

`make validate` decides whether the data may be published: it writes `reports/validation.md` and exits non-zero on any failure.

## Owns

- `pipeline/validate.py`, `sql/validate/*.sql`, `tests/test_validate.py`
- Generated: `reports/validation.md` (committed), `data/agg/ref_indicators.parquet`, `data/agg/validation_summary.json`

## Tasks

- [ ] Load the indicators CSV into `ref_indicators` without changing values. Check the real file's formats for `Month/Year`, thousands separators and percent strings
- [ ] Tie-out: trips per day = `SUM(trips_all)` ÷ days in month, against `"Trips Per Day"`, within ±2%, for HVFHV (uber + lyft + other_hv vs `FHV - High Volume`), Yellow and Green. Months the indicators file doesn't have yet are skipped and listed
- [ ] Quality drift: `valid_rows / rows` ≥ 95% per month × mode; list any month more than 3 points below its mode's median
- [ ] CBD list: share of both-in trips with a fee ≥ 98%; share of neither-in (pass-through) trips with a fee reported, not failed. From `agg_cbd_pairs` (D8), for both zone lists
- [ ] Schema: run `python -m pipeline.discover --check`. How it covers months with no local files depends on D11
- [ ] Fees: since 2025-01-05, ≥ 95% of trips with `cbd_fee > 0` carry exactly the configured fee for their mode (from `agg_fee_values`, D8); list the other values found
- [ ] Report: pass/fail table first, then details. The summary JSON feeds `quality.json`
- [ ] Never widen a tolerance. A failure goes to the integrator with the evidence

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
