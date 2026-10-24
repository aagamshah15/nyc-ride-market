-- Metric: price_volatility
-- Questions: Q7
-- Params: none
-- Grain: month × pu_zone × mode; each mode, plus ride_hail and all at pu_zone = 0 (city-wide)
-- Columns: month, pu_zone, mode, n, volatility
-- Source: TLC trip records
--
-- SPEC §6: volatility = fpm_p90 ÷ fpm_p10, the spread of fare per mile within the cell.
SELECT month, pu_zone, mode, n, fpm_p90 / NULLIF(fpm_p10, 0) AS volatility
FROM agg_zone_month_dist
ORDER BY month, pu_zone, mode;
