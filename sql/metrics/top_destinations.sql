-- Metric: top_destinations
-- Questions: Q1
-- Params: $to_month, $top_n
-- Grain: pu_zone × do_zone, the $top_n destinations of each pickup zone; all modes summed
-- Columns: pu_zone, do_zone, rank INT, trips BIGINT, share DOUBLE
-- Source: TLC trip records
--
-- Valid trips in $to_month from agg_od_month, which keeps only pairs with at least 20 trips
-- per mode. share is of the zone's valid trips (agg_zone_hour.trips_valid, every pair),
-- as contracts §7 defines it. Ties rank by do_zone.
WITH pairs AS (
    SELECT pu_zone, do_zone, SUM(trips_valid) AS trips
    FROM agg_od_month
    WHERE month = $to_month
    GROUP BY pu_zone, do_zone
),
zone_trips AS (
    SELECT pu_zone, SUM(trips_valid) AS trips
    FROM agg_zone_hour
    WHERE month = $to_month
    GROUP BY pu_zone
),
ranked AS (
    SELECT p.pu_zone,
           p.do_zone,
           row_number() OVER (PARTITION BY p.pu_zone ORDER BY p.trips DESC, p.do_zone) AS rank,
           p.trips,
           p.trips / NULLIF(z.trips, 0) AS share
    FROM pairs p
    LEFT JOIN zone_trips z ON z.pu_zone = p.pu_zone
)
SELECT pu_zone, do_zone, rank::INTEGER AS rank, trips::BIGINT AS trips, share
FROM ranked
WHERE rank <= $top_n
ORDER BY pu_zone, rank;
