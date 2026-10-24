-- Metric: airport_by_hour
-- Questions: Q9
-- Params: $to_month, $window
-- Grain: airport × direction × hour × mode; each mode
-- Columns: airport, direction, hour, mode, trips_per_day
-- Source: TLC trip records
--
-- Over the $window months ending at $to_month: valid trips in that hour of day ÷ days in
-- the window, counting the days of the window's months that are in agg_airport.
WITH win AS (
    SELECT *
    FROM agg_airport
    WHERE date_diff('month', month, $to_month) BETWEEN 0 AND $window - 1
),
days AS (
    SELECT SUM(day(last_day(month))) AS days FROM (SELECT DISTINCT month FROM win)
)
SELECT w.airport,
       w.direction,
       w.hour_of_day AS hour,
       w.mode,
       SUM(w.trips_valid) / any_value(d.days) AS trips_per_day
FROM win w, days d
GROUP BY w.airport, w.direction, w.hour_of_day, w.mode
ORDER BY w.airport, w.direction, hour, w.mode;
