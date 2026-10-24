-- Metric: trips_per_hour_worked
-- Questions: Q15
-- Params: none
-- Grain: month × license_class; every license class in the TLC indicators
-- Columns: month, license_class, trips_per_day, vehicles_per_day, hours_per_day_per_vehicle, trips_per_hour_worked, unique_drivers
-- Source: TLC-reported
--
-- SPEC §6: from the TLC's monthly indicators, not trip records. trips_per_hour_worked =
-- Trips Per Day ÷ (Vehicles Per Day × Avg Hours Per Day Per Vehicle).
SELECT month,
       "License Class" AS license_class,
       "Trips Per Day" AS trips_per_day,
       "Vehicles Per Day" AS vehicles_per_day,
       "Avg Hours Per Day Per Vehicle" AS hours_per_day_per_vehicle,
       "Trips Per Day" / NULLIF("Vehicles Per Day" * "Avg Hours Per Day Per Vehicle", 0) AS trips_per_hour_worked,
       "Unique Drivers" AS unique_drivers
FROM ref_indicators
ORDER BY month, license_class;
