-- Metric: fee_revenue
-- Questions: Q14
-- Params: none
-- Grain: month × mode; each mode
-- Columns: month, mode, cbd_fee, trips_with_cbd_fee, congestion_surcharge, airport_fee
-- Source: TLC trip records
--
-- SPEC §6: fee dollars collected per month, from agg_fees_month. cbd_fee is the congestion
-- relief zone toll (0 before 2025-01-05).
SELECT month,
       mode,
       SUM(cbd_fee) AS cbd_fee,
       SUM(trips_with_cbd_fee)::BIGINT AS trips_with_cbd_fee,
       SUM(congestion_surcharge) AS congestion_surcharge,
       SUM(airport_fee) AS airport_fee
FROM agg_fees_month
GROUP BY month, mode
ORDER BY month, mode;
