# L10 · Policy studies

**Wave** 3 · **Phase** 3 (9 – 29 Nov) · **Spec** §6 (congestion effect, pay-rise event study), §12 · **Decisions** D7, D9, D12 · **Feeds** L11, L15

## Goal

The two policy analyses: a year-over-year difference-in-differences for congestion pricing (Q2, Q3) and a weekly event study around the 1 Aug 2025 pay rise (Q6).

## Owns

- `sql/metrics/{cp_effect,cp_effect_summary,cp_weekly_trips,cp_zone_change,pay_event}.sql` (outputs in `contracts/metrics.md`), `pipeline/studies.py`
- `config/periods.yaml`: the excluded-holiday-weeks key only
- `reports/congestion_pricing.md`, `reports/pay_rise.md`
- `tests/test_cp_effect.py`, `tests/test_pay_event.py`

## Starts when

- L09's runner exists. Build on factories first; real numbers after G3

## Tasks

- [ ] Holiday weeks: compute in code which US federal holidays fall in different ISO weeks in 2024 and 2025; write them to `periods.yaml` with each holiday's name
- [ ] Congestion effect: per 2025 ISO week (from W02 if D12 is agreed) × mode × metric (`trips_all`, `fare_base / miles`, `driver_pay / fare_base`): growth of treated ÷ growth of control − 1. Report the median and the p10–p90 range across weeks, for both zone lists (D9)
- [ ] Pay rise: 12 ISO weeks before and after 2025-08-01; HVFHV `driver_pay / miles`, `driver_pay / minute` and `fare_base / miles`; the same weeks of 2024 as the seasonal reference; W31 as a transition week (D12)
- [ ] `pipeline/studies.py` writes the report tables. The narrative is written by hand: "estimated effect", never "caused"; limits from SPEC §12
- [ ] Sanity sections in each report: the weekly series per group, and which weeks were excluded and why

## Tests

- A fixture with known weekly sums → effect, median and p10/p90 worked out by hand
- Excluded weeks are dropped; week-boundary handling

## Done when

- Both metrics run on the back-filled aggregates; both reports merged
- `python -m pipeline.studies` reproduces every number in the reports

## Not this lane

- Site pages (L15); finding sentences for the site (L11)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct | in progress | Five metrics, `pipeline/studies.py`, the periods.yaml holiday key and both report templates are built. `tests/test_cp_effect.py` (15 tests) passes, and L09's `run_all` passes on its full fixture. Still to do: tests for `cp_weekly_trips`, `cp_zone_change`, `pay_event` and the studies CLI, then the hand-off. The real numbers and narrative wait for G3. |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
