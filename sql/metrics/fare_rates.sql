-- Metric: fare_rates
-- Questions: Q3, Q7
-- Params: none
-- Grain: month × mode; each mode, plus ride_hail (uber + lyft + other_hv), taxi (yellow + green) and all
-- Columns: month, mode, fare_per_mile, fare_per_min, rider_total_per_trip
-- Source: TLC trip records
--
-- City-wide means as ratios of sums over valid trips (SPEC §6): fare_base ÷ miles,
-- fare_base ÷ (duration_s ÷ 60) and rider_total_ex_tip ÷ trips_valid.
WITH by_mode AS (
    SELECT month,
           mode,
           SUM(fare_base) AS fare_base,
           SUM(miles) AS miles,
           SUM(duration_s) AS duration_s,
           SUM(rider_total_ex_tip) AS rider_total,
           SUM(trips_valid) AS trips
    FROM agg_zone_hour
    GROUP BY month, mode
),
with_groups AS (
    SELECT * FROM by_mode
    UNION ALL
    SELECT month,
           CASE WHEN mode IN ('uber', 'lyft', 'other_hv') THEN 'ride_hail' ELSE 'taxi' END,
           SUM(fare_base), SUM(miles), SUM(duration_s), SUM(rider_total), SUM(trips)
    FROM by_mode
    WHERE mode IN ('uber', 'lyft', 'other_hv', 'yellow', 'green')
    GROUP BY 1, 2
    UNION ALL
    SELECT month, 'all', SUM(fare_base), SUM(miles), SUM(duration_s), SUM(rider_total), SUM(trips)
    FROM by_mode
    GROUP BY month
)
SELECT month,
       mode,
       fare_base / NULLIF(miles, 0) AS fare_per_mile,
       fare_base / NULLIF(duration_s / 60, 0) AS fare_per_min,
       rider_total / NULLIF(trips, 0) AS rider_total_per_trip
FROM with_groups
ORDER BY month, mode;
