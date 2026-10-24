-- Metric: quality_month
-- Questions: methods
-- Params: none
-- Grain: month × mode; each mode
-- Columns: month, mode, rows, valid_rows, valid_share, f_time, f_miles, f_fare, f_zone, f_wait
-- Source: TLC trip records
--
-- Rows and flag counts from agg_quality_month (SPEC §4.2); valid_share = valid_rows ÷ rows.
-- f_wait is NULL for cabs, which have no request time.
SELECT month,
       mode,
       SUM("rows")::BIGINT AS "rows",
       SUM(valid_rows)::BIGINT AS valid_rows,
       SUM(valid_rows) / NULLIF(SUM("rows"), 0) AS valid_share,
       SUM(f_time)::BIGINT AS f_time,
       SUM(f_miles)::BIGINT AS f_miles,
       SUM(f_fare)::BIGINT AS f_fare,
       SUM(f_zone)::BIGINT AS f_zone,
       SUM(f_wait)::BIGINT AS f_wait
FROM agg_quality_month
GROUP BY month, mode
ORDER BY month, mode;
