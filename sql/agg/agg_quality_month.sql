-- agg_quality_month · SPEC §5, §4.2 · lane L07
-- Row and flag counts per mode and month, over all rows.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py)
-- Grain  month × mode
--
-- month       DATE     first day of the source file's month
-- mode        VARCHAR  uber, lyft, other_hv, yellow, green
-- rows        BIGINT   all rows
-- valid_rows  BIGINT   rows with is_valid
-- f_time      BIGINT   rows with f_time
-- f_miles     BIGINT   rows with f_miles
-- f_fare      BIGINT   rows with f_fare
-- f_zone      BIGINT   rows with f_zone
-- f_wait      BIGINT   rows with f_wait; ride-hail only, NULL for cabs (no request time)
--
-- A row can carry several flags, so the flag counts don't add up to rows - valid_rows.

SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    count(*)::BIGINT                                               AS "rows",
    (count(*) FILTER (WHERE is_valid))::BIGINT                     AS valid_rows,
    (count(*) FILTER (WHERE f_time))::BIGINT                       AS f_time,
    (count(*) FILTER (WHERE f_miles))::BIGINT                      AS f_miles,
    (count(*) FILTER (WHERE f_fare))::BIGINT                       AS f_fare,
    (count(*) FILTER (WHERE f_zone))::BIGINT                       AS f_zone,
    (CASE WHEN mode IN ('uber', 'lyft', 'other_hv')
          THEN count(*) FILTER (WHERE f_wait) END)::BIGINT         AS f_wait
FROM trips
GROUP BY month, mode;
