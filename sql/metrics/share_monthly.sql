-- Metric: share_monthly
-- Questions: Q1
-- Params: none
-- Grain: month × mode; each mode, plus ride_hail (uber + lyft + other_hv) and taxi (yellow + green)
-- Columns: month DATE, mode, trips BIGINT, days INT, trips_per_day DOUBLE, share DOUBLE
-- Source: TLC trip records
--
-- Counts every row (trips_all), as TLC does. share is of all modes' trips that month.
WITH by_mode AS (
    SELECT month, mode, SUM(trips_all) AS trips
    FROM agg_zone_hour
    GROUP BY month, mode
),
with_groups AS (
    SELECT month, mode, trips FROM by_mode
    UNION ALL
    SELECT month,
           CASE WHEN mode IN ('uber', 'lyft', 'other_hv') THEN 'ride_hail' ELSE 'taxi' END,
           SUM(trips)
    FROM by_mode
    WHERE mode IN ('uber', 'lyft', 'other_hv', 'yellow', 'green')
    GROUP BY 1, 2
),
totals AS (
    SELECT month, SUM(trips) AS total FROM by_mode GROUP BY month
)
SELECT g.month,
       g.mode,
       g.trips::BIGINT AS trips,
       day(last_day(g.month))::INTEGER AS days,
       g.trips / day(last_day(g.month)) AS trips_per_day,
       g.trips / NULLIF(t.total, 0) AS share
FROM with_groups g
JOIN totals t ON t.month = g.month
ORDER BY g.month, g.mode;
