-- agg_od_month · SPEC §5, D15 · lane L07
-- Valid trips summed by mode and pickup → drop-off zone pair.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); valid rows only
-- Grain  month × mode × pu_zone × do_zone. A pair is kept only when it has at least
--        $od_min_trips (20) valid trips that month.
--
-- month               DATE      first day of the source file's month
-- mode                VARCHAR   uber, lyft, other_hv, yellow, green
-- pu_zone             SMALLINT  pickup zone
-- do_zone             SMALLINT  drop-off zone
-- trips_valid         BIGINT    valid trips
-- miles               DOUBLE    sum
-- duration_s          BIGINT    sum
-- fare_base           DOUBLE    sum
-- driver_pay          DOUBLE    sum; ride-hail only, NULL for cabs
-- rider_total_ex_tip  DOUBLE    sum (D15)
--
-- Money and miles are summed as DECIMAL(18, 4), exact for TLC values, so the sums don't depend on
-- row order.

WITH t AS (
    SELECT
        month, mode, pu_zone, do_zone,
        mode IN ('uber', 'lyft', 'other_hv') AS hv,
        miles::DECIMAL(18, 4) AS miles,
        duration_s,
        fare_base::DECIMAL(18, 4) AS fare_base,
        driver_pay::DECIMAL(18, 4) AS driver_pay,
        rider_total_ex_tip::DECIMAL(18, 4) AS rider_total_ex_tip
    FROM trips
    WHERE is_valid
),
g AS (
    SELECT
        month, mode, hv, pu_zone, do_zone,
        count(*)                                                   AS trips_valid,
        sum(miles)                                                 AS miles,
        sum(duration_s)                                            AS duration_s,
        sum(fare_base)                                             AS fare_base,
        sum(driver_pay)                                            AS driver_pay,
        sum(rider_total_ex_tip)                                    AS rider_total_ex_tip
    FROM t
    GROUP BY month, mode, hv, pu_zone, do_zone
    HAVING count(*) >= getvariable('od_min_trips')
)
SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    pu_zone::SMALLINT                                              AS pu_zone,
    do_zone::SMALLINT                                              AS do_zone,
    trips_valid::BIGINT                                            AS trips_valid,
    miles::DOUBLE                                                  AS miles,
    duration_s::BIGINT                                             AS duration_s,
    fare_base::DOUBLE                                              AS fare_base,
    (CASE WHEN hv THEN driver_pay END)::DOUBLE                     AS driver_pay,
    rider_total_ex_tip::DOUBLE                                     AS rider_total_ex_tip
FROM g;
