-- CBD-list check (SPEC §7.2, §8; D8, D9): how often trips carry a congestion fee, by whether
-- they start and end inside the congestion-zone list.
--
-- Inputs  months_checked(month), agg_cbd_pairs, cbd_zones(zone_list, zone) (set up by pipeline/validate.py)
-- Params  $cbd_from          first month wholly under congestion pricing; earlier months are left out
--         $min_both_in_pct   pass when at least this percentage of both-in trips has a fee (98)
-- Output  GROUPING SETS, told apart by `level`:
--   level = 'total'   one row per zone_list: the check itself
--   level = 'mode'    zone_list × mode (details)
--   level = 'month'   zone_list × month (details)
-- Columns: zone_list, mode, month, level,
--   both_in_trips, both_in_fee_trips, both_in_fee_share         pickup and drop-off both in the list
--   neither_in_trips, neither_in_fee_trips, neither_in_fee_share pass-through: reported, never failed
--   status   pass | fail | skipped (no both-in trips)
-- A NULL or unknown zone counts as outside the list.

WITH lists AS (
    SELECT DISTINCT zone_list FROM cbd_zones
),
pairs AS (
    SELECT l.zone_list, p.month, p.mode, p.trips_all, p.trips_cbd_fee,
           pu.zone IS NOT NULL AS pu_in,
           dz.zone IS NOT NULL AS do_in
    FROM agg_cbd_pairs p
    CROSS JOIN lists l
    LEFT JOIN cbd_zones pu ON pu.zone_list = l.zone_list AND pu.zone = p.pu_zone
    LEFT JOIN cbd_zones dz ON dz.zone_list = l.zone_list AND dz.zone = p.do_zone
    WHERE p.month >= $cbd_from
      AND p.month IN (SELECT month FROM months_checked)
),
sums AS (
    SELECT
        zone_list, mode, month,
        CASE WHEN GROUPING(mode) = 0 THEN 'mode'
             WHEN GROUPING(month) = 0 THEN 'month'
             ELSE 'total' END                                                AS level,
        CAST(COALESCE(SUM(trips_all) FILTER (WHERE pu_in AND do_in), 0) AS BIGINT)             AS both_in_trips,
        CAST(COALESCE(SUM(trips_cbd_fee) FILTER (WHERE pu_in AND do_in), 0) AS BIGINT)         AS both_in_fee_trips,
        CAST(COALESCE(SUM(trips_all) FILTER (WHERE NOT pu_in AND NOT do_in), 0) AS BIGINT)     AS neither_in_trips,
        CAST(COALESCE(SUM(trips_cbd_fee) FILTER (WHERE NOT pu_in AND NOT do_in), 0) AS BIGINT) AS neither_in_fee_trips
    FROM pairs
    GROUP BY GROUPING SETS ((zone_list), (zone_list, mode), (zone_list, month))
)
SELECT
    zone_list, mode, month, level,
    both_in_trips, both_in_fee_trips,
    both_in_fee_trips / NULLIF(both_in_trips, 0)           AS both_in_fee_share,
    neither_in_trips, neither_in_fee_trips,
    neither_in_fee_trips / NULLIF(neither_in_trips, 0)     AS neither_in_fee_share,
    CASE WHEN both_in_trips = 0 THEN 'skipped'
         -- integer comparison, so exactly min_both_in_pct passes
         WHEN both_in_fee_trips * 100 >= $min_both_in_pct * both_in_trips THEN 'pass'
         ELSE 'fail' END                                   AS status
FROM sums
ORDER BY zone_list, level, mode, month;
