-- Metric: fare_rates_by_borough
-- Questions: Q7
-- Params: $to_month, $window
-- Grain: pu_borough × mode; each mode, plus all. Boroughs with valid trips only
-- Columns: pu_borough, mode, fare_per_mile, fare_per_min
-- Source: TLC trip records
--
-- Over the $window months ending at $to_month: fare_base ÷ miles and fare_base ÷
-- (duration_s ÷ 60), summed over valid trips. Borough from ref_zones (pickup zone); the
-- unknown zones 264 and 265 have no valid trips, so their rows drop out.
WITH by_mode AS (
    SELECT z.Borough AS pu_borough,
           a.mode,
           SUM(a.fare_base) AS fare_base,
           SUM(a.miles) AS miles,
           SUM(a.duration_s) AS duration_s,
           SUM(a.trips_valid) AS trips
    FROM agg_zone_hour a
    JOIN ref_zones z ON z.LocationID = a.pu_zone
    WHERE date_diff('month', a.month, $to_month) BETWEEN 0 AND $window - 1
    GROUP BY z.Borough, a.mode
),
with_all AS (
    SELECT * FROM by_mode
    UNION ALL
    SELECT pu_borough, 'all', SUM(fare_base), SUM(miles), SUM(duration_s), SUM(trips)
    FROM by_mode
    GROUP BY pu_borough
)
SELECT pu_borough,
       mode,
       fare_base / NULLIF(miles, 0) AS fare_per_mile,
       fare_base / NULLIF(duration_s / 60, 0) AS fare_per_min
FROM with_all
WHERE trips > 0
ORDER BY pu_borough, mode;
