-- agg_zone_month_dist · SPEC §5, D10, D16 · lane L07
-- Percentiles of per-trip fare per mile, fare per minute and wait, by mode and pickup zone.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); valid rows only
-- Grain  month × mode × pu_zone, plus city-wide rows at pu_zone = 0: one per mode (D10) and one
--        each for the groups ride_hail (uber + lyft + other_hv) and all (every mode) (D16).
--        Group rows exist only at pu_zone = 0. A row is kept only when n ≥ $dist_min_n (100).
--
-- month      DATE      first day of the source file's month
-- mode       VARCHAR   uber, lyft, other_hv, yellow, green; ride_hail, all at pu_zone = 0
-- pu_zone    SMALLINT  pickup zone; 0 = city-wide
-- n          BIGINT    valid trips in the group
-- fpm_p10    DOUBLE    10th percentile of fare_base / miles, dollars per mile
-- fpm_p50    DOUBLE    median of fare_base / miles
-- fpm_p90    DOUBLE    90th percentile of fare_base / miles
-- fpmin_p50  DOUBLE    median of fare_base / (duration_s / 60), dollars per minute
-- wait_p50   DOUBLE    median wait_s, seconds, leaving out f_wait rows and NULL waits
-- wait_p90   DOUBLE    90th percentile wait_s
--
-- Percentiles are quantile_cont (linear interpolation). Waits are NULL for cabs (no request time)
-- and for the all group, which would otherwise report ride-hail waits under an all-modes label.
-- Valid rows have miles > 0 and duration_s > 0 (SPEC §4.2), so the ratios are defined.

WITH v AS (
    SELECT
        month, mode, pu_zone,
        fare_base / miles                                          AS fpm,
        fare_base / (duration_s / 60.0)                            AS fpmin,
        (CASE WHEN f_wait IS NOT TRUE THEN wait_s END)::DOUBLE     AS wait_s
    FROM trips
    WHERE is_valid
),
members AS (
    SELECT month, mode, pu_zone, fpm, fpmin, wait_s FROM v
    UNION ALL
    SELECT month, mode, 0, fpm, fpmin, wait_s FROM v
    UNION ALL
    SELECT month, 'ride_hail', 0, fpm, fpmin, wait_s FROM v WHERE mode IN ('uber', 'lyft', 'other_hv')
    UNION ALL
    SELECT month, 'all', 0, fpm, fpmin, NULL FROM v
),
g AS (
    SELECT
        month, mode, pu_zone,
        count(*)                                                   AS n,
        quantile_cont(fpm, [0.1, 0.5, 0.9])                        AS fpm_q,
        quantile_cont(fpmin, 0.5)                                  AS fpmin_p50,
        quantile_cont(wait_s, [0.5, 0.9])                          AS wait_q
    FROM members
    GROUP BY month, mode, pu_zone
    HAVING count(*) >= getvariable('dist_min_n')
)
SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    pu_zone::SMALLINT                                              AS pu_zone,
    n::BIGINT                                                      AS n,
    fpm_q[1]::DOUBLE                                               AS fpm_p10,
    fpm_q[2]::DOUBLE                                               AS fpm_p50,
    fpm_q[3]::DOUBLE                                               AS fpm_p90,
    fpmin_p50::DOUBLE                                              AS fpmin_p50,
    wait_q[1]::DOUBLE                                              AS wait_p50,
    wait_q[2]::DOUBLE                                              AS wait_p90
FROM g;
