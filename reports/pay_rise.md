# The 1 August 2025 driver pay rise: weekly event study

Lane L10 · SPEC §6, §12 · decision D12 · question Q6 · metric `pay_event`

> **Status: structure only (24 Oct 2026).** The back-filled aggregates arrive with gate G3, so the tables below aren't generated yet and the findings aren't written. After G3: run `python -m pipeline.studies`, read the sanity checks, then write the findings by hand from the generated tables. Every number in this report comes from that command; nothing in the generated blocks is edited by hand.

<!-- BEGIN generated: provenance -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: provenance -->

## Question

Did the TLC's rise in minimum driver pay on 1 August 2025 raise what ride-hail drivers earn per mile and per minute with a passenger, and did base fares rise with it (Q6)?

## Method

- **Series.** Weekly, for Uber, Lyft and the two together (ride-hail), citywide, valid trips, each a ratio of sums over the week:
  - driver pay per mile: sum of driver pay ÷ sum of miles
  - driver pay per minute with a passenger: sum of driver pay ÷ sum of trip minutes
  - base fare per mile: sum of base fare ÷ sum of miles
- **Window.** The 12 ISO weeks before and the 12 after 2025-W31, the week containing 1 August 2025 (offset 0).
- **Transition week (D12).** 2025-W31 (28 Jul to 3 Aug) mixes days before and after the rise. It is drawn but left out of the before/after summary, and so is the same week of the reference year.
- **Seasonal reference.** The same ISO weeks of 2024, when pay rules didn't change on 1 August. They show the usual summer-to-autumn movement.
- **Before/after summary.** The median weekly value over the 12 weeks before and over the 12 weeks after; the change between them; and the change net of the 2024 reference, (1 + change in 2025) ÷ (1 + change in 2024) − 1. Medians keep one odd week from moving the summary.

## Before and after

Median weekly value before and after the transition week, by year.

<!-- BEGIN generated: summary -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: summary -->

## Findings

_Written by hand after G3, from the tables in this report. Results are "estimated effects", never "caused"; pay per minute is per minute with a passenger._

## Weekly series

Each week of the window, 2025 against the same ISO week of 2024.

<!-- BEGIN generated: weekly -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: weekly -->

## Sanity checks: weeks used

<!-- BEGIN generated: weeks -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: weeks -->

## Limits

- **Not a randomised test** (SPEC §12). The 2024 weeks take out the usual seasonal movement, but not anything else that changed between the two years and around August 2025, such as a platform's own pricing changes.
- **Per minute with a passenger.** Trip files have no time between trips (SPEC §12), so this is not pay per hour worked.
- **Driver pay excludes tips and tolls** in the trip records, and base fare excludes tolls, tips, taxes and fees (SPEC §12).
- **Congestion pricing** was in force through both the before and after windows of 2025 and through neither window of 2024. It shifts the 2025 level against 2024 but not the change from before to after.
- **Each week counts once** in the medians, whatever its trip volume.
- **TLC may revise recent months** and does not guarantee vendor-submitted records (SPEC §12).
