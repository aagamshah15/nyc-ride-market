-- agg_vendor_month · D25, SPEC §8 · lane L07
-- How many records each technology vendor sent, per mode and month, for the tie-out (L08).
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); all rows
-- Grain  month × mode × vendor_id
--
-- month      DATE      first day of the source file's month
-- mode       VARCHAR   uber, lyft, other_hv, yellow, green
-- vendor_id  SMALLINT  the cab files' VendorID; NULL for ride-hail (one row per ride-hail mode),
--                      and NULL for a cab record with no VendorID
-- rows       BIGINT    all rows, valid or not
--
-- All rows, like trips_all: the tie-out subtracts the records of the vendors in
-- tie_out_exclude_vendors (config/sources.yaml) from trips_all (D25).

SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    (CASE WHEN mode NOT IN ('uber', 'lyft', 'other_hv') THEN vendor_id END)::SMALLINT AS vendor_id,
    count(*)::BIGINT                                               AS "rows"
FROM trips
GROUP BY ALL;
