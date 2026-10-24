-- agg_cbd_pairs · D8, SPEC §7.2 · lane L07
-- Trips and trips charged the congestion fee, by zone pair, for the CBD-list check (L08).
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); all rows
-- Grain  month × mode × pu_zone × do_zone, for months from $cbd_from_month on (2025-01, the month
--        congestion pricing started, config/periods.yaml). Earlier months get no rows.
--
-- month          DATE      first day of the source file's month
-- mode           VARCHAR   uber, lyft, other_hv, yellow, green
-- pu_zone        SMALLINT  pickup zone; NULL and unknown zones kept
-- do_zone        SMALLINT  drop-off zone; NULL and unknown zones kept
-- trips_all      BIGINT    all rows
-- trips_cbd_fee  BIGINT    rows with cbd_fee > 0
--
-- All rows, not just valid ones: like the tie-out, the check describes the data as TLC sent it.

SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    pu_zone::SMALLINT                                              AS pu_zone,
    do_zone::SMALLINT                                              AS do_zone,
    count(*)::BIGINT                                               AS trips_all,
    (count(*) FILTER (WHERE cbd_fee > 0))::BIGINT                  AS trips_cbd_fee
FROM trips
WHERE month >= getvariable('cbd_from_month')
GROUP BY month, mode, pu_zone, do_zone;
