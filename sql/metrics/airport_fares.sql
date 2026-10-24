-- Metric: airport_fares
-- Questions: Q9
-- Params: $to_month
-- Grain: airport × mode, trips from the airport to Manhattan; each mode
-- Columns: airport, mode, trips, fare_mean, fare_base_mean, fare_per_mile
-- Source: TLC trip records
--
-- Valid trips in $to_month from agg_od_month (pairs with at least 20 trips per mode) whose
-- pickup zone is an airport (ref_airports, config/airports.csv) and whose drop-off zone is in
-- Manhattan (ref_zones). Means are ratios of sums (D10): fare_mean = rider_total_ex_tip ÷
-- trips, fare_base_mean = fare_base ÷ trips, fare_per_mile = fare_base ÷ miles.
SELECT ap.airport,
       od.mode,
       SUM(od.trips_valid)::BIGINT AS trips,
       SUM(od.rider_total_ex_tip) / NULLIF(SUM(od.trips_valid), 0) AS fare_mean,
       SUM(od.fare_base) / NULLIF(SUM(od.trips_valid), 0) AS fare_base_mean,
       SUM(od.fare_base) / NULLIF(SUM(od.miles), 0) AS fare_per_mile
FROM agg_od_month od
JOIN ref_airports ap ON ap.LocationID = od.pu_zone
JOIN ref_zones dz ON dz.LocationID = od.do_zone
WHERE od.month = $to_month
  AND dz.Borough = 'Manhattan'
GROUP BY ap.airport, od.mode
ORDER BY ap.airport, od.mode;
