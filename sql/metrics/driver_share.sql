-- Metric: driver_share
-- Questions: Q3, Q5, Q6
-- Params: none
-- Grain: month × mode; uber, lyft and ride_hail (= uber + lyft)
-- Columns: month, mode, driver_pay, fare_base, driver_share, platform_share
-- Source: TLC trip records
--
-- SPEC §6: SUM(driver_pay) ÷ SUM(fare_base) over valid trips; platform_share = 1 − driver_share.
-- fare_base is base_passenger_fare, which excludes tolls, tips, taxes and fees.
WITH by_mode AS (
    SELECT month, mode, SUM(driver_pay) AS driver_pay, SUM(fare_base) AS fare_base
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, mode
),
with_group AS (
    SELECT * FROM by_mode
    UNION ALL
    SELECT month, 'ride_hail', SUM(driver_pay), SUM(fare_base) FROM by_mode GROUP BY month
)
SELECT month,
       mode,
       driver_pay,
       fare_base,
       driver_pay / NULLIF(fare_base, 0) AS driver_share,
       1 - driver_pay / NULLIF(fare_base, 0) AS platform_share
FROM with_group
ORDER BY month, mode;
