# Metric contracts

One SQL file per metric in `sql/metrics/` (SPEC §6). Each is a single `SELECT` over the aggregate tables. `pipeline/metrics.py` (L09) registers every `data/agg/*.parquet` as a view of the same name, plus `ref_zones` (`LocationID SMALLINT, Borough, Zone, service_zone` from `data/ref/taxi_zone_lookup.csv`) and `ref_airports` (`LocationID SMALLINT, airport` from `config/airports.csv`), then runs a metric with DuckDB named parameters (`$to_month`). `run()` checks every output against this file (names, order and types) and raises `ContractError` on a mismatch, for L10's metrics too.

## Conventions

- **Params.** `$to_month` DATE, default the latest month in `agg_zone_hour`. `$window` INTEGER months ending at `$to_month`, default 3. `$top_n` INTEGER, default 10. The runner fills defaults; SQL never hard-codes a month.
- **Ratios of sums only** (CLAUDE.md), with `NULLIF(denominator, 0)`.
- **Rows.** Metric rows use `is_valid` sums except trip counts and shares, which use `trips_all` (SPEC §4.2), and fee revenue, which `agg_fees_month` sums over every row (D23).
- **"Prior" and "change"** (`share_prior`, `gap_prior`, `change`, `gap_change`) compare `$to_month` with the same month a year earlier.
- **`zone_hour_profile.mode_share_in_zone`** is the mode's share of the zone's trips over the whole window and all hours; the zone heatmap keeps modes at 10% or more (contracts/README.md §1).
- **Mode groups** (`ride_hail`, `taxi`, `all`) are extra rows with that value in `mode`, only where the Modes column lists them. See contracts/README.md §2.
- **`trips_per_day`** = trips ÷ days in that month (or in the window).
- **`agg_week_cbd` holds every trip once per `zone_list`.** Filter `zone_list = 'core'` unless the metric compares the two lists; summing across lists double counts.
- **Header comment** in each file: questions, params, grain, output columns, as below.
- The output columns are exact: names, order and types. L09's tests check them.
- **Column types.** A type written next to a column anywhere in the table applies to every column of that name. Untyped columns follow these rules, as `pipeline/metrics.py` applies them:
  - VARCHAR: `mode`, `pu_borough`, `airport`, `direction`, `license_class`, `metric`, `zone_list`, `cbd_group`, `exclusion_reason`
  - SMALLINT: `do_zone`, `iso_year`, `iso_week`, `year` (and `pu_zone`, `hour_of_week`, `hour` as typed below)
  - BIGINT: `n`, `requests`, `matched`, `rows`, `valid_rows`, `f_time`, `f_miles`, `f_fare`, `f_zone`, `f_wait`, `trips_with_cbd_fee` (and `trips` as typed below)
  - DOUBLE: everything else, including `unique_drivers` as TLC reports it

## Metrics

Owner is L09 unless marked L10.

| Metric | Q | Params | Grain | Modes | Output columns | Reads |
|---|---|---|---|---|---|---|
| `share_monthly` | Q1 | — | month × mode | each + `ride_hail`, `taxi` | `month DATE, mode, trips BIGINT, days INT, trips_per_day DOUBLE, share DOUBLE` | agg_zone_hour |
| `trip_share` | Q1, Q4, Q9, Q10 | — | month × pu_zone × mode | each | `month, pu_zone SMALLINT, mode, trips BIGINT, share DOUBLE` (SPEC §6 SQL) | agg_zone_hour |
| `zone_share_change` | Q1, Q4, Q10 | to_month | pu_zone × mode | each + `ride_hail` | `pu_zone, mode, trips_per_day, share, share_prior, change` | agg_zone_hour |
| `lyft_vs_uber` | Q4 | to_month | pu_zone | — | `pu_zone, lyft_share, uber_share, gap, gap_prior, gap_change` (shares of all trips in the zone) | agg_zone_hour |
| `zone_hour_profile` | Q1 | to_month, window | pu_zone × hour_of_week × mode | each | `pu_zone, hour_of_week SMALLINT, mode, trips_per_week DOUBLE, mode_share_in_zone DOUBLE` | agg_zone_hour |
| `top_destinations` | Q1 | to_month, top_n | pu_zone × do_zone | all modes summed | `pu_zone, do_zone, rank INT, trips BIGINT, share DOUBLE` (`share` = trips ÷ the zone's valid trips in `agg_zone_hour`) | agg_od_month, agg_zone_hour |
| `driver_share` | Q3, Q5, Q6 | — | month × mode | `uber`, `lyft`, `ride_hail` (= uber + lyft) | `month, mode, driver_pay, fare_base, driver_share, platform_share` | agg_zone_hour |
| `pay_per_hour` | Q6 | — | month × mode | `uber`, `lyft`, `ride_hail` (= uber + lyft) | `month, mode, driver_pay, on_trip_hours, pay_per_hour` | agg_zone_hour |
| `fare_rates` | Q3, Q7 | — | month × mode | each + `ride_hail`, `taxi`, `all` | `month, mode, fare_per_mile, fare_per_min, rider_total_per_trip` | agg_zone_hour |
| `fare_rates_by_hour` | Q7 | to_month, window | hour_of_week × mode | each + `all` | `hour_of_week, mode, fare_per_mile, fare_per_min` | agg_zone_hour |
| `fare_rates_by_borough` | Q7 | to_month, window | pu_borough × mode | each + `all` | `pu_borough, mode, fare_per_mile, fare_per_min` | agg_zone_hour, ref_zones |
| `fare_dist` | Q3, Q7 | — | month × pu_zone × mode | each; `ride_hail`, `all` at `pu_zone = 0` | `month, pu_zone, mode, n, fpm_p10, fpm_p50, fpm_p90, fpmin_p50` | agg_zone_month_dist |
| `price_volatility` | Q7 | — | month × pu_zone × mode | as `fare_dist` | `month, pu_zone, mode, n, volatility` (= fpm_p90 ÷ fpm_p10) | agg_zone_month_dist |
| `wait_time` | Q8 | — | month × pu_zone × mode (`pu_zone = 0` city-wide) | `uber`, `lyft` | `month, pu_zone, mode, wait_p50, wait_p90, wait_mean` | agg_zone_month_dist, agg_zone_hour |
| `wait_by_hour` | Q8 | to_month, window | pu_zone × hour × mode (`pu_zone = 0` city-wide) | `uber`, `lyft` | `pu_zone, hour SMALLINT, mode, wait_mean` | agg_zone_hour |
| `tip_rate` | Q13 | — | month × pu_borough × mode (`pu_borough = 'all'` city-wide) | each | `month, pu_borough, mode, tips, fare_base, tip_rate, card_only BOOLEAN` | agg_zone_hour, ref_zones |
| `wav_match_rate` | Q11 | — | month × mode | `uber`, `lyft` | `month, mode, requests, matched, match_rate` | agg_zone_hour |
| `shared_match_rate` | Q12 | — | month × pu_zone × mode (`pu_zone = 0` city-wide) | `uber`, `lyft` | `month, pu_zone, mode, requests, matched, match_rate` | agg_zone_hour |
| `fee_revenue` | Q14 | — | month × mode | each | `month, mode, cbd_fee, trips_with_cbd_fee, congestion_surcharge, airport_fee` | agg_fees_month |
| `airport_share` | Q9 | — | month × airport × direction × mode | each | `month, airport, direction, mode, trips, trips_per_day, share` (share within airport × direction) | agg_airport |
| `airport_by_hour` | Q9 | to_month, window | airport × direction × hour × mode | each | `airport, direction, hour, mode, trips_per_day` | agg_airport |
| `airport_fares` | Q9 | to_month | airport × mode, trips from the airport to Manhattan | each | `airport, mode, trips, fare_mean, fare_base_mean, fare_per_mile` (`fare_mean` = rider_total_ex_tip ÷ trips) | agg_od_month, ref_zones, config/airports.csv |
| `trips_per_hour_worked` | Q15 | — | month × license_class | — | `month, license_class, trips_per_day, vehicles_per_day, hours_per_day_per_vehicle, trips_per_hour_worked, unique_drivers` (TLC-reported) | ref_indicators |
| `quality_month` | methods | — | month × mode | each | `month, mode, rows, valid_rows, valid_share, f_time, f_miles, f_fare, f_zone, f_wait` | agg_quality_month |
| `cp_effect` (L10) | Q2, Q3 | — | iso week × mode × metric × zone_list | each + `ride_hail`, `all` | `iso_year, iso_week, week_start DATE, mode, metric, zone_list, growth_treated, growth_control, effect, excluded BOOLEAN, exclusion_reason` | agg_week_cbd, config/periods.yaml |
| `cp_effect_summary` (L10) | Q2, Q3 | — | mode × metric × zone_list | as `cp_effect` | `mode, metric, zone_list, weeks INT, median, p10, p90` (non-excluded weeks only) | agg_week_cbd |
| `cp_weekly_trips` (L10) | Q2 | — | iso week × cbd_group × mode × zone_list, 2024 and 2025 | `ride_hail`, `taxi`, `all` | `iso_year, iso_week, week_start, cbd_group, mode, zone_list, trips_per_day` | agg_week_cbd |
| `cp_zone_change` (L10) | Q2 | — | pu_zone | all modes summed | `pu_zone, trips_per_day_2024, trips_per_day_2025, change` | agg_zone_hour |
| `pay_event` (L10) | Q6 | — | year × week_offset × mode, 12 ISO weeks either side of 2025-08-01, 2024 as reference | `uber`, `lyft`, `ride_hail` | `year, week_offset INT, week_start, mode, pay_per_mile, pay_per_min, fare_per_mile, transition BOOLEAN` | agg_week_cbd |

In `cp_effect`, `metric ∈ {trips, fare_per_mile, driver_share}`; `driver_share` rows exist only for `uber`, `lyft`, `ride_hail`. Weeks start at 2025-W02 (D12); `excluded` marks holiday weeks (SPEC §6). In `pay_event`, `week_offset` 0 is 2025-W31, the transition week (D12).
