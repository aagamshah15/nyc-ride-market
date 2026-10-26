-- yellow · SPEC §4 · lane L06
-- One yellow-cab file → the 25 unified columns (SPEC §4 plus vendor_id, D25), in SPEC order.
--
-- Input  view `src` (pipeline/clean.py), built from config/schema_map.yaml for the file's month range:
--        a raw column that alone feeds a unified column appears under the unified name, holding the
--        raw value; columns that share a unified column keep their map names (extra, mta_tax,
--        improvement_surcharge); constants and NULL columns from the map appear under the unified name.
--        variable `file_month` (DATE): first day of the file's month
-- Output one row per raw row. Derived columns and flags are added by derive.sql.
--
-- Rules (config/schema_map.yaml):
--   mode                 the constant 'yellow'
--   duration_s           epoch(dropoff_ts − pickup_ts); cabs have no duration column
--   airport_fee          airport_fee, matched case-insensitively (files spell it Airport_fee)
--   cbd_fee              cbd_congestion_fee from 2025-01 (NULL → 0); the constant 0 before then
--   other_fees           extra + mta_tax + improvement_surcharge
--   rider_total_ex_tip   total_amount − tip_amount (src.rider_total_ex_tip holds total_amount)
--   tips                 tip_amount, which cab files record for card payments only
--   is_card              payment_type = 1 (src.is_card holds payment_type)
--   vendor_id            VendorID, the technology provider (D25)

SELECT
    src.mode::VARCHAR                                              AS mode,
    getvariable('file_month')::DATE                                AS month,
    src.request_ts::TIMESTAMP                                      AS request_ts,
    src.pickup_ts::TIMESTAMP                                       AS pickup_ts,
    src.dropoff_ts::TIMESTAMP                                      AS dropoff_ts,
    src.pu_zone::SMALLINT                                          AS pu_zone,
    src.do_zone::SMALLINT                                          AS do_zone,
    src.miles::DOUBLE                                              AS miles,
    epoch(src.dropoff_ts - src.pickup_ts)::BIGINT                  AS duration_s,
    src.fare_base::DOUBLE                                          AS fare_base,
    src.tips::DOUBLE                                               AS tips,
    src.tolls::DOUBLE                                              AS tolls,
    src.airport_fee::DOUBLE                                        AS airport_fee,
    src.congestion_surcharge::DOUBLE                               AS congestion_surcharge,
    coalesce(src.cbd_fee, 0)::DOUBLE                               AS cbd_fee,
    (src.extra + src.mta_tax + src.improvement_surcharge)::DOUBLE  AS other_fees,
    (src.rider_total_ex_tip - src.tips)::DOUBLE                    AS rider_total_ex_tip,
    src.driver_pay::DOUBLE                                         AS driver_pay,
    (src.is_card = 1)                                              AS is_card,
    src.shared_request::BOOLEAN                                    AS shared_request,
    src.shared_match::BOOLEAN                                      AS shared_match,
    src.wav_request::BOOLEAN                                       AS wav_request,
    src.wav_match::BOOLEAN                                         AS wav_match,
    src.street_hail::BOOLEAN                                       AS street_hail,
    src.vendor_id::SMALLINT                                        AS vendor_id
FROM src
