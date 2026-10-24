-- agg_zone_hour · SPEC §5 · lane L07
-- One month of clean trips summed by mode, pickup zone and hour of week.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py)
-- Grain  month × mode × pu_zone × hour_of_week. Every row of the month lands in a group, including
--        rows with a NULL or unknown zone, so SUM(trips_all) is the month's row count (tie-out).
--
-- month               DATE      first day of the source file's month
-- mode                VARCHAR   uber, lyft, other_hv, yellow, green
-- pu_zone             SMALLINT  pickup zone; NULL is a group of its own
-- hour_of_week        SMALLINT  0–167 from pickup, Sunday 00:00 = 0
-- trips_all           BIGINT    all rows, valid or not
-- trips_valid         BIGINT    rows with is_valid
-- miles               DOUBLE    sum over valid rows
-- duration_s          BIGINT    sum over valid rows
-- fare_base           DOUBLE    sum over valid rows
-- rider_total_ex_tip  DOUBLE    sum over valid rows
-- driver_pay          DOUBLE    sum over valid rows; ride-hail only
-- tips                DOUBLE    sum over valid rows (cab tips in the source are card-only)
-- card_trips          BIGINT    valid rows with is_card; cabs only
-- card_tips           DOUBLE    tips on valid card rows; cabs only
-- card_fare_base      DOUBLE    fare_base on valid card rows; cabs only
-- wait_s_sum          BIGINT    wait_s on valid rows, leaving out f_wait rows and NULL waits; ride-hail only
-- wait_n              BIGINT    rows in wait_s_sum; ride-hail only
-- cbd_fee             DOUBLE    sum over valid rows
-- shared_req          BIGINT    valid rows with shared_request; ride-hail only
-- shared_match        BIGINT    valid rows with shared_match; ride-hail only
-- wav_req             BIGINT    valid rows with wav_request; ride-hail only
-- wav_match           BIGINT    valid rows with wav_match; ride-hail only
--
-- Ride-hail is uber, lyft and other_hv. "Ride-hail only" columns are NULL for cabs and "cabs only"
-- columns NULL for ride-hail; otherwise a sum over no qualifying rows is 0. Money and miles are
-- summed as DECIMAL(18, 4), exact for TLC values (cents, hundredths of a mile), so the sums don't
-- depend on row order and a re-run gives the same numbers.

WITH t AS (
    SELECT
        month, mode, pu_zone, hour_of_week,
        mode IN ('uber', 'lyft', 'other_hv') AS hv,
        is_valid,
        is_valid AND is_card AS card,
        is_valid AND f_wait IS NOT TRUE AND wait_s IS NOT NULL AS wait_ok,
        miles::DECIMAL(18, 4) AS miles,
        duration_s,
        fare_base::DECIMAL(18, 4) AS fare_base,
        rider_total_ex_tip::DECIMAL(18, 4) AS rider_total_ex_tip,
        driver_pay::DECIMAL(18, 4) AS driver_pay,
        tips::DECIMAL(18, 4) AS tips,
        cbd_fee::DECIMAL(18, 4) AS cbd_fee,
        wait_s, shared_request, shared_match, wav_request, wav_match
    FROM trips
),
g AS (
    SELECT
        month, mode, hv, pu_zone, hour_of_week,
        count(*)                                                   AS trips_all,
        count(*) FILTER (WHERE is_valid)                           AS trips_valid,
        sum(miles) FILTER (WHERE is_valid)                         AS miles,
        sum(duration_s) FILTER (WHERE is_valid)                    AS duration_s,
        sum(fare_base) FILTER (WHERE is_valid)                     AS fare_base,
        sum(rider_total_ex_tip) FILTER (WHERE is_valid)            AS rider_total_ex_tip,
        sum(driver_pay) FILTER (WHERE is_valid)                    AS driver_pay,
        sum(tips) FILTER (WHERE is_valid)                          AS tips,
        count(*) FILTER (WHERE card)                               AS card_trips,
        sum(tips) FILTER (WHERE card)                              AS card_tips,
        sum(fare_base) FILTER (WHERE card)                         AS card_fare_base,
        sum(wait_s) FILTER (WHERE wait_ok)                         AS wait_s_sum,
        count(*) FILTER (WHERE wait_ok)                            AS wait_n,
        sum(cbd_fee) FILTER (WHERE is_valid)                       AS cbd_fee,
        count(*) FILTER (WHERE is_valid AND shared_request)        AS shared_req,
        count(*) FILTER (WHERE is_valid AND shared_match)          AS shared_match,
        count(*) FILTER (WHERE is_valid AND wav_request)           AS wav_req,
        count(*) FILTER (WHERE is_valid AND wav_match)             AS wav_match
    FROM t
    GROUP BY month, mode, hv, pu_zone, hour_of_week
)
SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    pu_zone::SMALLINT                                              AS pu_zone,
    hour_of_week::SMALLINT                                         AS hour_of_week,
    trips_all::BIGINT                                              AS trips_all,
    trips_valid::BIGINT                                            AS trips_valid,
    coalesce(miles, 0)::DOUBLE                                     AS miles,
    coalesce(duration_s, 0)::BIGINT                                AS duration_s,
    coalesce(fare_base, 0)::DOUBLE                                 AS fare_base,
    coalesce(rider_total_ex_tip, 0)::DOUBLE                        AS rider_total_ex_tip,
    (CASE WHEN hv THEN coalesce(driver_pay, 0) END)::DOUBLE        AS driver_pay,
    coalesce(tips, 0)::DOUBLE                                      AS tips,
    (CASE WHEN NOT hv THEN card_trips END)::BIGINT                 AS card_trips,
    (CASE WHEN NOT hv THEN coalesce(card_tips, 0) END)::DOUBLE     AS card_tips,
    (CASE WHEN NOT hv THEN coalesce(card_fare_base, 0) END)::DOUBLE AS card_fare_base,
    (CASE WHEN hv THEN coalesce(wait_s_sum, 0) END)::BIGINT        AS wait_s_sum,
    (CASE WHEN hv THEN wait_n END)::BIGINT                         AS wait_n,
    coalesce(cbd_fee, 0)::DOUBLE                                   AS cbd_fee,
    (CASE WHEN hv THEN shared_req END)::BIGINT                     AS shared_req,
    (CASE WHEN hv THEN shared_match END)::BIGINT                   AS shared_match,
    (CASE WHEN hv THEN wav_req END)::BIGINT                        AS wav_req,
    (CASE WHEN hv THEN wav_match END)::BIGINT                      AS wav_match
FROM g;
