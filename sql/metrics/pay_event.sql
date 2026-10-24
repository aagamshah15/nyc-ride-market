-- Metric: pay_event
-- Questions: Q6
-- Params: none
-- Grain: year × week_offset × mode, 12 ISO weeks either side of 2025-W31 and the same ISO weeks of 2024; uber, lyft and ride_hail (= uber + lyft)
-- Columns: year, week_offset INT, week_start, mode, pay_per_mile, pay_per_min, fare_per_mile, transition BOOLEAN
-- Source: TLC trip records
--
-- SPEC §6 event study around the TLC minimum-pay rise of 1 Aug 2025 (driver_pay_rise in
-- config/periods.yaml). week_offset 0 is the ISO week containing that date, 2025-W31
-- (28 Jul – 3 Aug), which mixes pre and post days: transition is true there, in both years, so
-- before/after summaries leave out the same week of the 2024 reference (D12). year 2024 holds
-- the same ISO weeks a year earlier, the seasonal reference. Ratios of sums over valid trips,
-- city-wide (agg_week_cbd's core list, both groups, summed over month, D7):
--   pay_per_mile = SUM(driver_pay) ÷ SUM(miles)
--   pay_per_min  = SUM(driver_pay) ÷ (SUM(duration_s) ÷ 60), per minute with a passenger
--   fare_per_mile = SUM(fare_base) ÷ SUM(miles)
-- Every year × week_offset × mode row is returned; a week with no data has NULL values.
WITH study AS (
    SELECT isoyear(DATE '2025-08-01')::INTEGER AS study_year,
           weekofyear(DATE '2025-08-01')::INTEGER AS event_week,
           12 AS span
),
grid AS (
    SELECT y.year, o.week_offset, md.mode, s.event_week + o.week_offset AS iso_week
    FROM study s
    CROSS JOIN (SELECT study_year - 1 AS year FROM study UNION ALL SELECT study_year FROM study) y
    CROSS JOIN (SELECT range::INTEGER AS week_offset FROM study, range(-span, span + 1)) o
    CROSS JOIN (VALUES ('uber'), ('lyft'), ('ride_hail')) md(mode)
),
weekly AS (
    SELECT iso_year, iso_week, mode,
           SUM(driver_pay) AS driver_pay,
           SUM(miles) AS miles,
           SUM(duration_s) AS duration_s,
           SUM(fare_base) AS fare_base
    FROM agg_week_cbd
    WHERE zone_list = 'core'
      AND mode IN ('uber', 'lyft')
    GROUP BY iso_year, iso_week, mode
),
with_group AS (
    SELECT * FROM weekly
    UNION ALL
    SELECT iso_year, iso_week, 'ride_hail', SUM(driver_pay), SUM(miles), SUM(duration_s), SUM(fare_base)
    FROM weekly
    GROUP BY iso_year, iso_week
)
SELECT g.year::SMALLINT AS year,
       g.week_offset,
       date_trunc('week', make_date(g.year, 1, 4))::DATE + 7 * (g.iso_week - 1) AS week_start,
       g.mode,
       w.driver_pay / NULLIF(w.miles, 0) AS pay_per_mile,
       w.driver_pay / NULLIF(w.duration_s / 60, 0) AS pay_per_min,
       w.fare_base / NULLIF(w.miles, 0) AS fare_per_mile,
       g.week_offset = 0 AS transition
FROM grid g
LEFT JOIN with_group w ON w.iso_year = g.year AND w.iso_week = g.iso_week AND w.mode = g.mode
ORDER BY g.year, g.week_offset, g.mode;
