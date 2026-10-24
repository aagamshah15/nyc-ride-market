-- Metric: trip_share
-- Questions: Q1, Q4, Q9, Q10
-- Params: none
-- Grain: month × pu_zone × mode; each mode
-- Columns: month, pu_zone SMALLINT, mode, trips BIGINT, share DOUBLE
-- Source: TLC trip records
--
-- SPEC §6. Counts every row (trips_all); share is of all trips picked up in the zone that month.
SELECT month,
       pu_zone,
       mode,
       SUM(trips_all)::BIGINT AS trips,
       SUM(trips_all) / NULLIF(SUM(SUM(trips_all)) OVER (PARTITION BY month, pu_zone), 0) AS share
FROM agg_zone_hour
GROUP BY month, pu_zone, mode
ORDER BY month, pu_zone, mode;
