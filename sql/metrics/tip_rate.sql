-- Metric: tip_rate
-- Questions: Q13
-- Params: none
-- Grain: month × pu_borough × mode, plus city-wide rows with pu_borough = 'all'; each mode.
--        Boroughs with valid trips only
-- Columns: month, pu_borough, mode, tips, fare_base, tip_rate, card_only BOOLEAN
-- Source: TLC trip records
--
-- SPEC §6. Ride-hail: SUM(tips) ÷ SUM(fare_base). Cabs: card trips only, SUM(card_tips) ÷
-- SUM(card_fare_base), which fill the tips and fare_base columns; card_only marks them.
-- Borough from ref_zones (pickup zone).
WITH tagged AS (
    SELECT a.month,
           z.Borough AS pu_borough,
           a.mode,
           a.mode IN ('yellow', 'green') AS card_only,
           CASE WHEN a.mode IN ('yellow', 'green') THEN a.card_tips ELSE a.tips END AS tips,
           CASE WHEN a.mode IN ('yellow', 'green') THEN a.card_fare_base ELSE a.fare_base END AS fare_base,
           a.trips_valid
    FROM agg_zone_hour a
    JOIN ref_zones z ON z.LocationID = a.pu_zone
),
cells AS (
    SELECT month, pu_borough, mode, card_only, SUM(tips) AS tips, SUM(fare_base) AS fare_base,
           SUM(trips_valid) AS trips
    FROM tagged
    GROUP BY month, pu_borough, mode, card_only
    UNION ALL
    SELECT month, 'all', mode, card_only, SUM(tips), SUM(fare_base), SUM(trips_valid)
    FROM tagged
    GROUP BY month, mode, card_only
)
SELECT month, pu_borough, mode, tips, fare_base, tips / NULLIF(fare_base, 0) AS tip_rate, card_only
FROM cells
WHERE trips > 0
ORDER BY month, pu_borough, mode;
