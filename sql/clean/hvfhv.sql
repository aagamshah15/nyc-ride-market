-- hvfhv · SPEC §4 · lane L06
-- One high-volume FHV file → the 24 SPEC §4 unified columns, in SPEC order.
--
-- Input  view `src` (pipeline/clean.py), built from config/schema_map.yaml for the file's month range:
--        a raw column that alone feeds a unified column appears under the unified name, holding the
--        raw value; columns that share a unified column keep their map names (bcf, sales_tax);
--        constants and NULL columns from the map appear under the unified name.
--        table `hv_license` (code, mode) from config/sources.yaml
--        variable `file_month` (DATE): first day of the file's month
-- Output one row per raw row. Derived columns and flags are added by derive.sql.
--
-- Rules (config/schema_map.yaml):
--   mode                 src.mode is hvfhs_license_num; HV0003 uber, HV0005 lyft, HV0002 and HV0004
--                        other_hv. clean.py fails on any other code before this runs
--   duration_s           trip_time, seconds
--   cbd_fee              cbd_congestion_fee from 2025-01 (NULL → 0); the constant 0 before then
--   other_fees           bcf + sales_tax
--   rider_total_ex_tip   fare_base + tolls + other_fees + congestion_surcharge + airport_fee + cbd_fee
--   shared_*, wav_*      = 'Y' (a NULL flag stays NULL)

SELECT
    lic.mode::VARCHAR                                              AS mode,
    getvariable('file_month')::DATE                                AS month,
    src.request_ts::TIMESTAMP                                      AS request_ts,
    src.pickup_ts::TIMESTAMP                                       AS pickup_ts,
    src.dropoff_ts::TIMESTAMP                                      AS dropoff_ts,
    src.pu_zone::SMALLINT                                          AS pu_zone,
    src.do_zone::SMALLINT                                          AS do_zone,
    src.miles::DOUBLE                                              AS miles,
    src.duration_s::BIGINT                                         AS duration_s,
    src.fare_base::DOUBLE                                          AS fare_base,
    src.tips::DOUBLE                                               AS tips,
    src.tolls::DOUBLE                                              AS tolls,
    src.airport_fee::DOUBLE                                        AS airport_fee,
    src.congestion_surcharge::DOUBLE                               AS congestion_surcharge,
    coalesce(src.cbd_fee, 0)::DOUBLE                               AS cbd_fee,
    (src.bcf + src.sales_tax)::DOUBLE                              AS other_fees,
    (src.fare_base + src.tolls + (src.bcf + src.sales_tax) + src.congestion_surcharge
        + src.airport_fee + coalesce(src.cbd_fee, 0))::DOUBLE      AS rider_total_ex_tip,
    src.driver_pay::DOUBLE                                         AS driver_pay,
    src.is_card::BOOLEAN                                           AS is_card,
    (src.shared_request = 'Y')                                     AS shared_request,
    (src.shared_match = 'Y')                                       AS shared_match,
    (src.wav_request = 'Y')                                        AS wav_request,
    (src.wav_match = 'Y')                                          AS wav_match,
    src.street_hail::BOOLEAN                                       AS street_hail
FROM src
LEFT JOIN hv_license AS lic ON lic.code = src.mode
