-- agg_fees_month · SPEC §5, D23 · lane L07
-- Fees collected per mode and month.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); all rows (D23)
-- Grain  month × mode
--
-- month                 DATE     first day of the source file's month
-- mode                  VARCHAR  uber, lyft, other_hv, yellow, green
-- cbd_fee               DOUBLE   sum of cbd_fee (0 before 2025: clean coalesces it)
-- congestion_surcharge  DOUBLE   sum
-- airport_fee           DOUBLE   sum (0 for green: the source has no column)
-- trips_with_cbd_fee    BIGINT   rows with cbd_fee > 0
--
-- All rows, valid or not (D23, an exception to SPEC §4.2): a fee was charged whether or not the
-- trip's distance, duration or fare looks odd, and Q14 asks for the fee money each mode generates.
-- Money is summed as DECIMAL(18, 4), exact for TLC values.

WITH t AS (
    SELECT
        month, mode,
        cbd_fee::DECIMAL(18, 4) AS cbd_fee,
        congestion_surcharge::DECIMAL(18, 4) AS congestion_surcharge,
        airport_fee::DECIMAL(18, 4) AS airport_fee
    FROM trips
),
g AS (
    SELECT
        month, mode,
        sum(cbd_fee)                                               AS cbd_fee,
        sum(congestion_surcharge)                                  AS congestion_surcharge,
        sum(airport_fee)                                           AS airport_fee,
        count(*) FILTER (WHERE cbd_fee > 0)                        AS trips_with_cbd_fee
    FROM t
    GROUP BY month, mode
)
SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    coalesce(cbd_fee, 0)::DOUBLE                                   AS cbd_fee,
    coalesce(congestion_surcharge, 0)::DOUBLE                      AS congestion_surcharge,
    coalesce(airport_fee, 0)::DOUBLE                               AS airport_fee,
    trips_with_cbd_fee::BIGINT                                     AS trips_with_cbd_fee
FROM g;
