-- Metric: zone_hour_profile
-- Questions: Q1
-- Params: $to_month, $window
-- Grain: pu_zone × hour_of_week × mode; each mode
-- Columns: pu_zone, hour_of_week SMALLINT, mode, trips_per_week DOUBLE, mode_share_in_zone DOUBLE
-- Source: TLC trip records
--
-- Over the $window months ending at $to_month (trips_all). trips_per_week = trips in the
-- hour-of-week slot ÷ (days in the window ÷ 7), counting the days of the window's months
-- that are in the table. mode_share_in_zone is the mode's share of all the zone's trips in
-- the window, every hour: the site keeps heatmap modes with at least 10% (contracts §1).
WITH win AS (
    SELECT *
    FROM agg_zone_hour
    WHERE date_diff('month', month, $to_month) BETWEEN 0 AND $window - 1
),
days AS (
    SELECT SUM(day(last_day(month))) AS days FROM (SELECT DISTINCT month FROM win)
),
cells AS (
    SELECT pu_zone, hour_of_week, mode, SUM(trips_all) AS trips
    FROM win
    GROUP BY pu_zone, hour_of_week, mode
)
SELECT c.pu_zone,
       c.hour_of_week,
       c.mode,
       c.trips / (d.days / 7) AS trips_per_week,
       SUM(c.trips) OVER (PARTITION BY c.pu_zone, c.mode)
           / NULLIF(SUM(c.trips) OVER (PARTITION BY c.pu_zone), 0) AS mode_share_in_zone
FROM cells c, days d
ORDER BY c.pu_zone, c.hour_of_week, c.mode;
