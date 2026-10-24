-- Metric: wait_by_hour
-- Questions: Q8
-- Params: $to_month, $window
-- Grain: pu_zone × hour × mode, plus city-wide rows at pu_zone = 0; uber and lyft
-- Columns: pu_zone, hour SMALLINT, mode, wait_mean
-- Source: TLC trip records
--
-- Over the $window months ending at $to_month: SUM(wait_s_sum) ÷ SUM(wait_n), in seconds,
-- by hour of day (hour_of_week mod 24).
WITH win AS (
    SELECT pu_zone, (hour_of_week % 24)::SMALLINT AS hour, mode, wait_s_sum, wait_n
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
      AND date_diff('month', month, $to_month) BETWEEN 0 AND $window - 1
),
cells AS (
    SELECT pu_zone, hour, mode, SUM(wait_s_sum) AS wait_s, SUM(wait_n) AS waits
    FROM win
    GROUP BY pu_zone, hour, mode
    UNION ALL
    SELECT 0::SMALLINT, hour, mode, SUM(wait_s_sum), SUM(wait_n)
    FROM win
    GROUP BY hour, mode
)
SELECT pu_zone, hour, mode, wait_s / NULLIF(waits, 0) AS wait_mean
FROM cells
ORDER BY pu_zone, hour, mode;
