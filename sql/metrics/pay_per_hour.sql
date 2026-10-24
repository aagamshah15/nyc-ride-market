-- Metric: pay_per_hour
-- Questions: Q6
-- Params: none
-- Grain: month × mode; uber, lyft and ride_hail (= uber + lyft)
-- Columns: month, mode, driver_pay, on_trip_hours, pay_per_hour
-- Source: TLC trip records
--
-- SPEC §6: SUM(driver_pay) ÷ (SUM(duration_s) ÷ 3600) over valid trips. This is pay per hour
-- with a passenger: trip files have no time between trips.
WITH by_mode AS (
    SELECT month, mode, SUM(driver_pay) AS driver_pay, SUM(duration_s) AS duration_s
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, mode
),
with_group AS (
    SELECT * FROM by_mode
    UNION ALL
    SELECT month, 'ride_hail', SUM(driver_pay), SUM(duration_s) FROM by_mode GROUP BY month
)
SELECT month,
       mode,
       driver_pay,
       duration_s / 3600 AS on_trip_hours,
       driver_pay / NULLIF(duration_s / 3600, 0) AS pay_per_hour
FROM with_group
ORDER BY month, mode;
