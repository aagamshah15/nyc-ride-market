-- Metric: fare_dist
-- Questions: Q3, Q7
-- Params: none
-- Grain: month × pu_zone × mode; each mode, plus ride_hail and all at pu_zone = 0 (city-wide)
-- Columns: month, pu_zone, mode, n, fpm_p10, fpm_p50, fpm_p90, fpmin_p50
-- Source: TLC trip records
--
-- Fare-per-mile and fare-per-minute percentiles from agg_zone_month_dist, which holds only
-- zone × mode cells with n ≥ 100 valid trips and the city-wide rows of D10 and D16.
SELECT month, pu_zone, mode, n, fpm_p10, fpm_p50, fpm_p90, fpmin_p50
FROM agg_zone_month_dist
ORDER BY month, pu_zone, mode;
