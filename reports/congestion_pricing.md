# Congestion pricing: estimated effects on trips, fares and driver pay

Lane L10 · SPEC §6, §12 · decisions D7, D9, D12, D21 · questions Q2, Q3 · metrics `cp_effect`, `cp_effect_summary`, `cp_weekly_trips`, `cp_zone_change`

> **Status: structure only (24 Oct 2026).** The back-filled aggregates arrive with gate G3, so the tables below aren't generated yet and the findings aren't written. After G3: run `python -m pipeline.studies`, read the sanity checks, then write the findings by hand from the generated tables. Every number in this report comes from that command; nothing in the generated blocks is edited by hand.

<!-- BEGIN generated: provenance -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: provenance -->

## Question

Did the Congestion Relief Zone toll, which began on 5 January 2025, shift trips into or out of the zone below 60th Street, and which modes gained or lost (Q2)? Did ride-hail base fares or the driver's share of them move after it began (Q3)?

## Method

- **Design.** A year-over-year difference-in-differences by ISO week (SPEC §6). For each 2025 ISO week, against the same ISO week of 2024:
  - growth of a group = its 2025 value ÷ its 2024 value
  - estimated effect = growth of treated trips ÷ growth of control trips − 1

  Treated trips start or end in the congestion zone; control trips do neither. Comparing each group with itself a year earlier takes out the season. Comparing the two groups takes out whatever changed citywide between the years (weather, the economy, fleet size), as long as it changed both groups alike.
- **Measures,** each a ratio of sums over the week:
  - trips: every trip record, valid or not, as TLC counts them
  - base fare per mile: sum of base fare ÷ sum of miles, valid trips
  - driver share of base fare: sum of driver pay ÷ sum of base fare, valid ride-hail trips (Uber, Lyft, and the two together)
- **Modes.** Uber, Lyft, other ride-hail, yellow cabs and green cabs, plus ride-hail (the three ride-hail modes; Uber and Lyft only for driver share) and all modes.
- **Weeks.** From 2025-W02 (week of 6 Jan 2025). 2025-W01 has one day of pricing and is left out (D12). A week is also left out when a federal holiday falls in it in one year but not the other (SPEC §6; the list is in `config/periods.yaml`), or when the aggregates don't cover all seven of its days in both years. The sanity checks list every week left out and why.
- **Summary.** The median weekly estimated effect, with the 10th to 90th percentile range across weeks as its spread. Percentiles interpolate between weeks.
- **Zone lists (D9, D21).** The headline uses the core list, the zones wholly south of 60th Street. The wide list adds the borderline zones and is the sensitivity result. How the lists were drawn: [`reports/cbd_zones.md`](cbd_zones.md).

## Headline: core zone list

Median weekly estimated effect and its 10th to 90th percentile range across weeks.

<!-- BEGIN generated: effects_core -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: effects_core -->

## Findings

_Written by hand after G3, from the tables in this report. Results are "estimated effects", never "caused"._

## Sensitivity: wide zone list

The same estimate with the borderline zones counted as inside the zone. "Wide − core" is the difference between the two medians, in percentage points.

<!-- BEGIN generated: effects_wide -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: effects_wide -->

## Weekly estimated effects

One estimate per week, core list. Weeks marked "excluded" are drawn on the site but left out of the summary.

<!-- BEGIN generated: weekly_effects -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: weekly_effects -->

## Sanity checks

### Weekly trips per day, by group

Treated and control trips per day for each ISO week of both years, core list. Look for a break in one series that the other doesn't share (a storm, a data outage, a short week): it would distort that week's estimate.

<!-- BEGIN generated: weekly_trips -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: weekly_trips -->

### Weeks left out and why

<!-- BEGIN generated: excluded_weeks -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: excluded_weeks -->

### Federal holidays

Each US federal holiday, as observed, with its ISO week in each year. A holiday that moves between weeks removes both weeks from the summary.

<!-- BEGIN generated: holidays -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: holidays -->

## Pickups by zone, 2025 against 2024

Pickups per day in each zone, all modes, over 2025 against the same months of 2024 (`cp_zone_change`). This has no control group, so it isn't an estimated effect: it shows where pickups moved, for the zone map.

<!-- BEGIN generated: zone_change -->
_Not generated yet: run `python -m pipeline.studies` after G3._
<!-- END generated: zone_change -->

## Limits

- **Not a randomised test** (SPEC §12). The estimate assumes that, without the toll, trips touching the zone and trips elsewhere would have grown alike from 2024 to 2025. Anything else that changed in the zone between the two years and not outside it (office attendance, events, transit service, street works) lands in the estimate.
- **Some control trips pay the toll.** A trip that drives through the zone without starting or ending there can carry the fee (SPEC §7.2 reports how many), yet counts as control. That pulls the estimate towards zero.
- **Riders can move across the line.** A rider who now gets out just north of 60th Street turns a treated trip into a control trip. That counts twice: once as a lost treated trip, once as a gained control trip.
- **Zones don't follow 60th Street.** Taxi zones straddle the boundary; the core and wide lists bracket that.
- **Base fare excludes tolls, tips, taxes and fees** (SPEC §12), so base fare per mile doesn't include the congestion fee itself. It shows whether platforms and meters moved the fare under the fee.
- **No surge flag and no rider identity** in trip files (SPEC §12), so pricing changes can't be split from demand changes.
- **Each week counts once** in the median and percentiles, whatever its trip volume.
- **TLC may revise recent months** and does not guarantee vendor-submitted records (SPEC §12).
