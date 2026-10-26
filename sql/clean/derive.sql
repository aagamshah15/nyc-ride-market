-- derive · SPEC §4.1, §4.2 · decision D9 · lane L06
-- Unified trips from any dataset → clean trips: the derived columns and quality flags, in the exact
-- column order and types of CLEAN_TRIPS_SCHEMA (tests/factories.py).
--
-- Input  view `unified`: the 25 unified columns from hvfhv.sql, yellow.sql or green.sql
--        (duration_s still BIGINT there)
--        table `ref_zone` (zone, borough, airport, cbd, cbd_wide), one row per zone, built by
--        pipeline/clean.py from data/ref/taxi_zone_lookup.csv and pipeline.zones: airports from
--        config/airports.csv, cbd from the core list, cbd_wide from the wide list (D9)
--        variables `cp_start` and `pay_rise` (DATE, config/periods.yaml)
-- Output one row per input row, nothing dropped.
--
-- wait_s          epoch(pickup_ts − request_ts); NULL when request_ts is NULL (cabs)
-- hour_of_week    dayofweek(pickup_ts) * 24 + hour(pickup_ts), 0–167, Sunday 00:00 = 0
-- pu/do_borough   Borough from the zone lookup; NULL for a NULL zone
-- airport_pu/do   EWR, JFK or LGA, else NULL
-- cbd_*           zone in the core list; cbd_*_wide: zone in the wide list. A NULL zone is false
-- period          pre_cp before cp_start, post_cp from cp_start, post_pay from pay_rise; by pickup_ts
--
-- f_time          duration_s <= 0 or > 10800 (3 h), or pickup before the month's first day − 1 day or
--                 on or after the next month's first day + 1 day
-- f_miles         miles <= 0 or > 100
-- f_fare          fare_base <= 0
-- f_zone          pu_zone or do_zone is 264, 265 or NULL
-- f_wait          ride-hail and (wait_s < 0 or > 3600); false for cabs and for a NULL wait
-- is_valid        none of f_time, f_miles, f_fare, f_zone
--
-- Flags are never NULL: a NULL duration, pickup, miles or fare can't pass its test, so it sets the
-- flag. duration_s and wait_s are INTEGER; a value outside INTEGER range (a cab timestamp decades
-- off) is stored as NULL, and the flags are worked out on the full value.

WITH d AS (
    SELECT
        u.*,
        epoch(u.pickup_ts - u.request_ts)::BIGINT                  AS wait_full,
        pz.borough                                                 AS pu_borough,
        dz.borough                                                 AS do_borough,
        pz.airport                                                 AS airport_pu,
        dz.airport                                                 AS airport_do,
        coalesce(pz.cbd, false)                                    AS cbd_pu,
        coalesce(dz.cbd, false)                                    AS cbd_do,
        coalesce(pz.cbd_wide, false)                               AS cbd_pu_wide,
        coalesce(dz.cbd_wide, false)                               AS cbd_do_wide
    FROM unified AS u
    LEFT JOIN ref_zone AS pz ON pz.zone = u.pu_zone
    LEFT JOIN ref_zone AS dz ON dz.zone = u.do_zone
),
f AS (
    SELECT
        d.*,
        coalesce(duration_s <= 0 OR duration_s > 10800
                 OR pickup_ts < month - INTERVAL 1 DAY
                 OR pickup_ts >= month + INTERVAL 1 MONTH + INTERVAL 1 DAY, true)  AS f_time,
        coalesce(miles <= 0 OR miles > 100, true)                  AS f_miles,
        coalesce(fare_base <= 0, true)                             AS f_fare,
        pu_zone IS NULL OR do_zone IS NULL
            OR pu_zone IN (264, 265) OR do_zone IN (264, 265)      AS f_zone,
        coalesce(mode IN ('uber', 'lyft', 'other_hv')
                 AND (wait_full < 0 OR wait_full > 3600), false)   AS f_wait
    FROM d
)
SELECT
    mode::VARCHAR                                                  AS mode,
    month::DATE                                                    AS month,
    request_ts::TIMESTAMP                                          AS request_ts,
    pickup_ts::TIMESTAMP                                           AS pickup_ts,
    dropoff_ts::TIMESTAMP                                          AS dropoff_ts,
    pu_zone::SMALLINT                                              AS pu_zone,
    do_zone::SMALLINT                                              AS do_zone,
    miles::DOUBLE                                                  AS miles,
    TRY_CAST(duration_s AS INTEGER)                                AS duration_s,
    fare_base::DOUBLE                                              AS fare_base,
    tips::DOUBLE                                                   AS tips,
    tolls::DOUBLE                                                  AS tolls,
    airport_fee::DOUBLE                                            AS airport_fee,
    congestion_surcharge::DOUBLE                                   AS congestion_surcharge,
    cbd_fee::DOUBLE                                                AS cbd_fee,
    other_fees::DOUBLE                                             AS other_fees,
    rider_total_ex_tip::DOUBLE                                     AS rider_total_ex_tip,
    driver_pay::DOUBLE                                             AS driver_pay,
    is_card::BOOLEAN                                               AS is_card,
    shared_request::BOOLEAN                                        AS shared_request,
    shared_match::BOOLEAN                                          AS shared_match,
    wav_request::BOOLEAN                                           AS wav_request,
    wav_match::BOOLEAN                                             AS wav_match,
    street_hail::BOOLEAN                                           AS street_hail,
    vendor_id::SMALLINT                                            AS vendor_id,
    TRY_CAST(wait_full AS INTEGER)                                 AS wait_s,
    (dayofweek(pickup_ts) * 24 + hour(pickup_ts))::SMALLINT        AS hour_of_week,
    pu_borough::VARCHAR                                            AS pu_borough,
    do_borough::VARCHAR                                            AS do_borough,
    airport_pu::VARCHAR                                            AS airport_pu,
    airport_do::VARCHAR                                            AS airport_do,
    cbd_pu,
    cbd_do,
    cbd_pu OR cbd_do                                               AS cbd_touch,
    cbd_pu_wide,
    cbd_do_wide,
    cbd_pu_wide OR cbd_do_wide                                     AS cbd_touch_wide,
    (CASE WHEN pickup_ts < getvariable('cp_start') THEN 'pre_cp'
          WHEN pickup_ts < getvariable('pay_rise') THEN 'post_cp'
          WHEN pickup_ts IS NOT NULL THEN 'post_pay' END)::VARCHAR AS period,
    f_time,
    f_miles,
    f_fare,
    f_zone,
    f_wait,
    NOT (f_time OR f_miles OR f_fare OR f_zone)                    AS is_valid
FROM f
