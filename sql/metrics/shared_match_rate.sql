-- Metric: shared_match_rate
-- Questions: Q12
-- Params: none
-- Grain: month × pu_zone × mode, plus city-wide rows at pu_zone = 0; uber and lyft
-- Columns: month, pu_zone, mode, requests, matched, match_rate
-- Source: TLC trip records
--
-- SPEC §6: shared-ride requests matched, SUM(shared_match) ÷ SUM(shared_req). match_rate is
-- NULL where there were no shared requests.
WITH cells AS (
    SELECT month, pu_zone, mode, SUM(shared_req) AS requests, SUM(shared_match) AS matched
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, pu_zone, mode
    UNION ALL
    SELECT month, 0::SMALLINT, mode, SUM(shared_req), SUM(shared_match)
    FROM agg_zone_hour
    WHERE mode IN ('uber', 'lyft')
    GROUP BY month, mode
)
SELECT month,
       pu_zone,
       mode,
       requests::BIGINT AS requests,
       matched::BIGINT AS matched,
       matched / NULLIF(requests, 0) AS match_rate
FROM cells
ORDER BY month, pu_zone, mode;
