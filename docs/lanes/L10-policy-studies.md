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

- [x] Holiday weeks: compute in code which US federal holidays fall in different ISO weeks in 2024 and 2025; write them to `periods.yaml` with each holiday's name
- [x] Congestion effect: per 2025 ISO week (from W02 if D12 is agreed) × mode × metric (`trips_all`, `fare_base / miles`, `driver_pay / fare_base`): growth of treated ÷ growth of control − 1. Report the median and the p10–p90 range across weeks, for both zone lists (D9)
- [x] Pay rise: 12 ISO weeks before and after 2025-08-01; HVFHV `driver_pay / miles`, `driver_pay / minute` and `fare_base / miles`; the same weeks of 2024 as the seasonal reference; W31 as a transition week (D12)
- [x] `pipeline/studies.py` writes the report tables. The narrative is written by hand: "estimated effect", never "caused"; limits from SPEC §12
- [x] Sanity sections in each report: the weekly series per group, and which weeks were excluded and why

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
| 27 Oct | D28 applied | Merged `main` (D28). `reports/pay_rise.md` now calls 1 Aug 2025 the new minimum-pay rule (per-mile floor down, per-minute floor up) and uses D28's Q6 wording. TLC's 5% is described as its sample-trip figure against 2024 rates, including the March step. The monthly context table marks Mar 2025 (`driver_pay_inflation_step`) and Aug 2025 (`driver_pay_rise`) from `config/periods.yaml`, with notes under the table. No other generated block changed. The event study, W31 and `pay_event` are unchanged. |
| 27 Oct | pay-rise narrative revised | Added a sourced "What the rule changed" section to `reports/pay_rise.md`. I checked every figure against the text of TLC's Notice of Promulgation (adopted 25 June 2025; it states no effective date). Re-read the findings against the rule: the March step is the CPI-W per-minute step; per mile, no rise is expected because the floor fell; per minute, a rise is expected only where the floor binds. Tables, metrics, `config/periods.yaml`, SPEC, the publish event label and the Q6 wording are unchanged (the integrator is asking the user about those). |
| 27 Oct | written up from real data | Merged `main` (G3 passed) and ran `python -m pipeline.studies` on the validated 2024-01 → 2026-08 aggregates. I wrote the Findings in both reports by hand from the generated tables and checked that a rerun reproduces both reports byte for byte. Added two generated tables built from existing metric outputs: "Growth of each group" (from `cp_effect`) and monthly pay per hour with a passenger (L09's `pay_per_hour`). The report's zone tables are now limited to map zones 1–263 and give a count of falling zones. One item is recorded under Blocked (the trip-mix metric); the findings don't depend on it. |
| 25 Oct | built on fixtures; real numbers and narrative wait for G3 | All five metrics, `pipeline/studies.py`, the `excluded_holiday_weeks` key and both report templates are built. 36 lane tests pass (hand-worked values), L09's `run_all` passes with the L10 metrics in, and `make test` is green. The reports' generated tables, the findings and every real number wait for the back-filled aggregates at G3. |
| 24 Oct | in progress | Five metrics, `pipeline/studies.py`, the periods.yaml holiday key and both report templates are built. `tests/test_cp_effect.py` (15 tests) passes, and L09's `run_all` passes on its full fixture. Still to do: tests for `cp_weekly_trips`, `cp_zone_change`, `pay_event` and the studies CLI, then the hand-off. The real numbers and narrative wait for G3. |

**Blocked:** one item, not stopping the write-up.
- *Trip-mix metric (27 Oct).* Two checks in the reports are exploratory and not published as tables, because they need a metric the contract doesn't have:
  - ride-hail zone trips got slightly longer, not shorter, in 2025;
  - miles and minutes per trip moved alike in 2024 and 2025 across W31.

  Both would be publishable with valid trips, miles and duration_s summed per week × cbd_group × mode, either as a new `cp_trip_mix` metric or as columns added to `cp_weekly_trips`. Either is a `contracts/metrics.md` change for the integrator. Until then the reports state the checks in words only, marked exploratory.

**Hand-off**
- Built:
  - Metrics in `sql/metrics/`, all with no params, contract-exact:
    - `cp_effect`: one row per 2025 ISO week from W02 (D12) × mode × metric × zone list. growth = 2025 ÷ same ISO week of 2024 per group; effect = growth_treated ÷ growth_control − 1. Metrics are `trips` (trips_all), `fare_per_mile` and `driver_share`, each a ratio of sums per week × group. Weeks are summed over `month` (D7), and each zone list is read separately (D9). `ride_hail` = uber + lyft + other_hv, except driver_share, which uses uber + lyft (contracts/README.md §2).
    - `cp_effect_summary`: the median, p10 and p90 (`quantile_cont`, linear interpolation) over weeks that aren't excluded. A group with no usable weeks still gets a row, with `weeks` 0 and NULLs.
    - `cp_weekly_trips`: treated and control trips per day for every ISO week of 2024 and 2025, for `ride_hail`, `taxi` and `all`, both lists.
    - `cp_zone_change`: pickups per day by zone, all modes, over the 2025 months whose 2024 month is also in `agg_zone_hour`. Each year divides by its own days. change = 2025 ÷ 2024 − 1.
    - `pay_event`: a fixed grid of 2 years × offsets −12…+12 × `uber`, `lyft` and `ride_hail` (uber + lyft), always 150 rows. Weeks with no data have NULL values. Offset 0 is the ISO week containing `driver_pay_rise` (2025-W31). `transition` is true at offset 0 in both years, as the mock does, so before/after summaries drop the same week of the 2024 reference. The ratios are city-wide: core list, both groups.
  - `pipeline/studies.py`:
    - `--holidays` computes the US federal holidays as observed (5 U.S.C. § 6103: Saturday → Friday, Sunday → Monday) and writes the `excluded_holiday_weeks` key into `config/periods.yaml` between marker lines, leaving the other keys alone. For 2024 against 2025, only MLK Day moves (W03 → W04), so both weeks are excluded.
    - A plain run checks that key is current, runs the five metrics and rewrites only the `<!-- BEGIN/END generated: … -->` blocks of the two reports. The same aggregates give byte-identical reports. `--reports-dir` points it at another folder.
  - `reports/congestion_pricing.md` and `reports/pay_rise.md`: question, method, the Findings placeholder, sanity sections (weekly series per group, weeks left out and why, the holiday table) and limits from SPEC §12 plus design-specific ones. All their numbers come from the generated blocks, which are placeholders until G3.
- Checked:
  - `tests/test_cp_effect.py` (15), `test_cp_weekly_trips.py`, `test_cp_zone_change.py`, `test_pay_event.py` and `test_cp_studies.py` (16). They cover, with hand-worked expected values in comments:
    - the effect, median and p10/p90
    - holiday weeks excluded with their reasons, and W01 left out
    - ISO weeks that span two months summed (D7), with fare per mile as a ratio of sums across them
    - core and wide never summed together
    - the mode groups, including driver_share's uber + lyft rule
    - incomplete weeks
    - per-day divisors for partial weeks and for Feb 2024's 29 days
    - pay_event's grid, offsets, week starts and transition flag
    - both reports end to end on a full factory fixture set, reproducibility, the CLI and its error paths
  - Guards:
    - the SQL holiday list equals periods.yaml, which equals the computed list
    - the shared effect block is identical in `cp_effect.sql` and `cp_effect_summary.sql`
    - the SQL date literals match periods.yaml
    - the headers follow the L09 convention
  - Mutation spot check: letting W01 back in, dropping pay_event's `zone_list` filter, or averaging miles instead of summing them each fails a test.
  - `make test`: 336 passed, 12 skipped; the site builds.
- Known limits:
  - Metrics read only the aggregate tables, so `cp_effect.sql` and `cp_effect_summary.sql` carry a copy of periods.yaml's holiday list and the study dates (2025-01-05, 2025-08-01), guarded by tests. The two files also share one CTE block, since a metric can't read another's output.
  - Beyond the holiday weeks, `cp_effect` also marks a week excluded when the aggregates don't cover all 7 of its days in either year, with the reason given. This changes nothing on a full back-fill; it keeps G2-style partial data from producing biased growth figures. `cp_weekly_trips` divides by covered days for the same reason.
  - The pay-rise before/after summary in the report is the median of weekly values, worked out in `studies.py` from `pay_event` (no contract metric holds it).
  - `cp_zone_change` is a plain before/after comparison (no control group); the report says so. The report's zone tables keep zones with at least 100 pickups a day in 2024 (`ZONE_MIN_TRIPS_PER_DAY`).
- Follow-ups:
  1. After G3: run `python -m pipeline.studies`, read the sanity sections, then write the Findings sections by hand from the tables ("estimated effect", never "caused").
  2. For the integrator, optional: have the runner expose periods.yaml's `excluded_holiday_weeks` as a view, so `cp_effect` reads it instead of carrying a copy. That's a change to L09's `pipeline/metrics.py` and the contract's view list.
  3. For the integrator and L11: if the drivers page needs a before/after pay number, add a `pay_event_summary` metric to `contracts/metrics.md`. Until then, use the same rule as the report (medians of the 12 weeks either side, offset 0 dropped).
  4. L19 (2027): with 2023 data, a placebo run of 2024 against 2023 on the same weeks (development plan §9). `holiday_weeks(base_year, study_year)` already takes the years.
  5. ~~Check `driver_pay_rise: 2025-08-01` against TLC's published rule.~~ Answered by the integrator on 27 Oct, and the report now has a "What the rule changed" section:
     - The March 2025 step is the CPI-W per-minute increase (3.92%).
     - The 1 August rule lowered the per-mile floor (about −5.5%) and raised the per-minute floor (about +8.8%).
     - TLC's "5%" is for one sample trip and includes March.

     Whether to change `config/periods.yaml`, SPEC §3.3, the publish event label or the Q6 wording is a user decision the integrator is taking; L10 changed none of them.
  6. For L11 and L15, from the 27 Oct write-up:
     - Per-company congestion estimates (Uber, Lyft) drift in opposite directions through 2025, so ride-hail combined is the safer site figure.
     - The yellow-cab trips estimate moves by about 10 points between the lists (−7.8% core, −18.1% wide) because yellow's comparison group grew very fast. Its finding sentence should carry that caveat or use the all-modes and ride-hail figures.
