-- agg_fee_values · D8, SPEC §8 · lane L07
-- How many trips carry each distinct congestion-fee value, for the fee check (L08).
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); all rows
-- Grain  month × mode × cbd_fee, every month (before 2025 the only value is 0)
--
-- month    DATE     first day of the source file's month
-- mode     VARCHAR  uber, lyft, other_hv, yellow, green
-- cbd_fee  DOUBLE   the exact value on the trip, 0 included
-- trips    BIGINT   rows with that value
--
-- All rows, not just valid ones, and the fee values exactly as clean wrote them, so the check sees
-- every value TLC sent.

SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    cbd_fee::DOUBLE                                                AS cbd_fee,
    count(*)::BIGINT                                               AS trips
FROM trips
GROUP BY month, mode, cbd_fee;
