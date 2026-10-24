-- Metric: fare_rates_by_hour
-- Questions: Q7
-- Params: $to_month, $window
-- Grain: hour_of_week × mode; each mode, plus all
-- Columns: hour_of_week, mode, fare_per_mile, fare_per_min
-- Source: TLC trip records
--
-- Over the $window months ending at $to_month: fare_base ÷ miles and fare_base ÷
-- (duration_s ÷ 60), summed over valid trips.
WITH by_mode AS (
    SELECT hour_of_week, mode, SUM(fare_base) AS fare_base, SUM(miles) AS miles, SUM(duration_s) AS duration_s
    FROM agg_zone_hour
    WHERE date_diff('month', month, $to_month) BETWEEN 0 AND $window - 1
    GROUP BY hour_of_week, mode
),
with_all AS (
    SELECT * FROM by_mode
    UNION ALL
    SELECT hour_of_week, 'all', SUM(fare_base), SUM(miles), SUM(duration_s) FROM by_mode GROUP BY hour_of_week
)
SELECT hour_of_week,
       mode,
       fare_base / NULLIF(miles, 0) AS fare_per_mile,
       fare_base / NULLIF(duration_s / 60, 0) AS fare_per_min
FROM with_all
ORDER BY hour_of_week, mode;
