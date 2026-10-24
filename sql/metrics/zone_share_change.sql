-- Metric: zone_share_change
-- Questions: Q1, Q4, Q10
-- Params: $to_month
-- Grain: pu_zone × mode; each mode, plus ride_hail (uber + lyft + other_hv)
-- Columns: pu_zone, mode, trips_per_day, share, share_prior, change
-- Source: TLC trip records
--
-- Pickups in $to_month against the same month a year earlier (trips_all). share is of all
-- trips picked up in the zone; change = share − share_prior, in fraction points. A mode
-- with trips in only one of the two months gets share 0 in the other, as long as the zone
-- had trips then; a zone with no trips in a month gets NULL.
WITH cells AS (
    SELECT pu_zone,
           mode,
           SUM(trips_all) FILTER (WHERE date_diff('month', month, $to_month) = 0) AS trips_now,
           SUM(trips_all) FILTER (WHERE date_diff('month', month, $to_month) = 12) AS trips_prior
    FROM agg_zone_hour
    WHERE date_diff('month', month, $to_month) IN (0, 12)
    GROUP BY pu_zone, mode
),
zoned AS (
    SELECT *,
           SUM(trips_now) OVER (PARTITION BY pu_zone) AS zone_now,
           SUM(trips_prior) OVER (PARTITION BY pu_zone) AS zone_prior
    FROM cells
),
with_group AS (
    SELECT pu_zone, mode, trips_now, trips_prior, zone_now, zone_prior FROM zoned
    UNION ALL
    SELECT pu_zone, 'ride_hail', SUM(trips_now), SUM(trips_prior), any_value(zone_now), any_value(zone_prior)
    FROM zoned
    WHERE mode IN ('uber', 'lyft', 'other_hv')
    GROUP BY pu_zone
),
shares AS (
    SELECT pu_zone,
           mode,
           COALESCE(trips_now, 0) / day(last_day($to_month)) AS trips_per_day,
           COALESCE(trips_now, 0) / NULLIF(zone_now, 0) AS share,
           COALESCE(trips_prior, 0) / NULLIF(zone_prior, 0) AS share_prior
    FROM with_group
)
SELECT pu_zone, mode, trips_per_day, share, share_prior, share - share_prior AS change
FROM shares
ORDER BY pu_zone, mode;
