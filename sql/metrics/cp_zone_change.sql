-- Metric: cp_zone_change
-- Questions: Q2
-- Params: none
-- Grain: pu_zone; all modes summed
-- Columns: pu_zone, trips_per_day_2024, trips_per_day_2025, change
-- Source: TLC trip records
--
-- Pickups per day in 2025 against 2024, every row counted (trips_all), over the 2025 months
-- whose month a year earlier is also in agg_zone_hour (all twelve once both years are in).
-- Each year divides by the days of its own months, so 2024's 29 February is allowed for.
-- change = trips_per_day_2025 ÷ trips_per_day_2024 − 1. A zone with pickups in one year only
-- gets 0 for the other; change is NULL when 2024 has none. This is a plain before/after
-- comparison, not an estimated effect: it has no control group.
WITH study AS (
    SELECT 2024 AS base_year, 2025 AS study_year
),
months AS (
    SELECT DISTINCT month FROM agg_zone_hour
),
matched AS (    -- (year, month) for each 2025 month and its 2024 month, when both are in the table
    SELECT s.study_year AS year, m.month
    FROM months m
    JOIN months p ON p.month = (m.month - INTERVAL 12 MONTH)::DATE
    CROSS JOIN study s
    WHERE year(m.month) = s.study_year
    UNION ALL
    SELECT s.base_year, p.month
    FROM months m
    JOIN months p ON p.month = (m.month - INTERVAL 12 MONTH)::DATE
    CROSS JOIN study s
    WHERE year(m.month) = s.study_year
),
days AS (
    SELECT SUM(day(last_day(month))) FILTER (WHERE year = s.base_year) AS days_base,
           SUM(day(last_day(month))) FILTER (WHERE year = s.study_year) AS days_now
    FROM matched, study s
),
zones AS (
    SELECT z.pu_zone,
           COALESCE(SUM(z.trips_all) FILTER (WHERE m.year = s.base_year), 0) AS trips_base,
           COALESCE(SUM(z.trips_all) FILTER (WHERE m.year = s.study_year), 0) AS trips_now
    FROM agg_zone_hour z
    JOIN matched m USING (month)
    CROSS JOIN study s
    GROUP BY z.pu_zone
)
SELECT z.pu_zone,
       z.trips_base / d.days_base AS trips_per_day_2024,
       z.trips_now / d.days_now AS trips_per_day_2025,
       (z.trips_now / d.days_now) / NULLIF(z.trips_base / d.days_base, 0) - 1 AS change
FROM zones z, days d
ORDER BY z.pu_zone;
