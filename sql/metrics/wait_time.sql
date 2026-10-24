-- Metric: wait_time
-- Questions: Q8
-- Params: none
-- Grain: month × pu_zone × mode, plus city-wide rows at pu_zone = 0; uber and lyft
-- Columns: month, pu_zone, mode, wait_p50, wait_p90, wait_mean
-- Source: TLC trip records
--
-- Seconds from request to pickup. Percentiles come from agg_zone_month_dist (NULL where a
-- cell has n < 100); wait_mean = SUM(wait_s_sum) ÷ SUM(wait_n) from agg_zone_hour, which
-- leaves out f_wait rows. Cabs have no request time, so they have no rows.
WITH means AS (
    SELECT month, pu_zone, mode, SUM(wait_s_sum) AS wait_s, SUM(wait_n) AS waits
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, pu_zone, mode
    UNION ALL
    SELECT month, 0::SMALLINT, mode, SUM(wait_s_sum), SUM(wait_n)
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, mode
),
percentiles AS (
    SELECT month, pu_zone, mode, wait_p50, wait_p90
    FROM agg_zone_month_dist
    WHERE mode IN ('uber', 'lyft')
)
SELECT month, pu_zone, mode, p.wait_p50, p.wait_p90, m.wait_s / NULLIF(m.waits, 0) AS wait_mean
FROM means m
FULL JOIN percentiles p USING (month, pu_zone, mode)
ORDER BY month, pu_zone, mode;
