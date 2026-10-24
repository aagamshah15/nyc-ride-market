-- Metric: lyft_vs_uber
-- Questions: Q4
-- Params: $to_month
-- Grain: pu_zone, for zones with pickups in $to_month
-- Columns: pu_zone, lyft_share, uber_share, gap, gap_prior, gap_change
-- Source: TLC trip records
--
-- Shares are of all trips picked up in the zone (trips_all, every mode). gap = Lyft share −
-- Uber share; gap_prior is the same month a year earlier; gap_change = gap − gap_prior.
WITH zones AS (
    SELECT pu_zone,
           SUM(trips_all) FILTER (WHERE ago = 0) AS total_now,
           SUM(trips_all) FILTER (WHERE ago = 0 AND mode = 'lyft') AS lyft_now,
           SUM(trips_all) FILTER (WHERE ago = 0 AND mode = 'uber') AS uber_now,
           SUM(trips_all) FILTER (WHERE ago = 12) AS total_prior,
           SUM(trips_all) FILTER (WHERE ago = 12 AND mode = 'lyft') AS lyft_prior,
           SUM(trips_all) FILTER (WHERE ago = 12 AND mode = 'uber') AS uber_prior
    FROM (SELECT *, date_diff('month', month, $to_month) AS ago FROM agg_zone_hour)
    WHERE ago IN (0, 12)
    GROUP BY pu_zone
),
shares AS (
    SELECT pu_zone,
           COALESCE(lyft_now, 0) / NULLIF(total_now, 0) AS lyft_share,
           COALESCE(uber_now, 0) / NULLIF(total_now, 0) AS uber_share,
           (COALESCE(lyft_prior, 0) - COALESCE(uber_prior, 0)) / NULLIF(total_prior, 0) AS gap_prior
    FROM zones
    WHERE total_now > 0
)
SELECT pu_zone,
       lyft_share,
       uber_share,
       lyft_share - uber_share AS gap,
       gap_prior,
       lyft_share - uber_share - gap_prior AS gap_change
FROM shares
ORDER BY pu_zone;
