-- Metric: airport_share
-- Questions: Q9
-- Params: none
-- Grain: month × airport × direction × mode; each mode
-- Columns: month, airport, direction, mode, trips, trips_per_day, share
-- Source: TLC trip records
--
-- agg_airport counts valid trips only (it has no trips_all). share is of all modes' trips
-- for that airport and direction that month; trips_per_day = trips ÷ days in the month.
WITH cells AS (
    SELECT month, airport, direction, mode, SUM(trips_valid) AS trips
    FROM agg_airport
    GROUP BY month, airport, direction, mode
)
SELECT month,
       airport,
       direction,
       mode,
       trips::BIGINT AS trips,
       trips / day(last_day(month)) AS trips_per_day,
       trips / NULLIF(SUM(trips) OVER (PARTITION BY month, airport, direction), 0) AS share
FROM cells
ORDER BY month, airport, direction, mode;
