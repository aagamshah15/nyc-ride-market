-- agg_airport · SPEC §5 · lane L07
-- Valid airport trips summed by mode, airport, direction and hour of day.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py); valid rows only
-- Grain  month × mode × airport × direction × hour_of_day.
--        direction 'from' = picked up at the airport (airport = airport_pu);
--        direction 'to'   = dropped off at the airport (airport = airport_do).
--        A trip between two airports, or from an airport back to itself, counts once in each
--        direction, so summing both directions double counts it; sum one direction at a time.
--        hour_of_day is the pickup hour for both directions.
--
-- month               DATE      first day of the source file's month
-- mode                VARCHAR   uber, lyft, other_hv, yellow, green
-- airport             VARCHAR   EWR, JFK, LGA (config/airports.csv, via clean)
-- direction           VARCHAR   from, to
-- hour_of_day         SMALLINT  0–23, pickup hour
-- trips_valid         BIGINT    valid trips
-- miles               DOUBLE    sum
-- duration_s          BIGINT    sum
-- fare_base           DOUBLE    sum
-- rider_total_ex_tip  DOUBLE    sum
-- tips                DOUBLE    sum (cab tips in the source are card-only)
--
-- Money and miles are summed as DECIMAL(18, 4), exact for TLC values, so the sums don't depend on
-- row order.

WITH t AS (
    SELECT
        month, mode, airport_pu, airport_do,
        hour(pickup_ts) AS hour_of_day,
        miles::DECIMAL(18, 4) AS miles,
        duration_s,
        fare_base::DECIMAL(18, 4) AS fare_base,
        rider_total_ex_tip::DECIMAL(18, 4) AS rider_total_ex_tip,
        tips::DECIMAL(18, 4) AS tips
    FROM trips
    WHERE is_valid AND (airport_pu IS NOT NULL OR airport_do IS NOT NULL)
),
legs AS (
    SELECT airport_pu AS airport, 'from' AS direction, * FROM t WHERE airport_pu IS NOT NULL
    UNION ALL
    SELECT airport_do AS airport, 'to' AS direction, * FROM t WHERE airport_do IS NOT NULL
),
g AS (
    SELECT
        month, mode, airport, direction, hour_of_day,
        count(*)                                                   AS trips_valid,
        sum(miles)                                                 AS miles,
        sum(duration_s)                                            AS duration_s,
        sum(fare_base)                                             AS fare_base,
        sum(rider_total_ex_tip)                                    AS rider_total_ex_tip,
        sum(tips)                                                  AS tips
    FROM legs
    GROUP BY month, mode, airport, direction, hour_of_day
)
SELECT
    month::DATE                                                    AS month,
    mode::VARCHAR                                                  AS mode,
    airport::VARCHAR                                               AS airport,
    direction::VARCHAR                                             AS direction,
    hour_of_day::SMALLINT                                          AS hour_of_day,
    trips_valid::BIGINT                                            AS trips_valid,
    miles::DOUBLE                                                  AS miles,
    duration_s::BIGINT                                             AS duration_s,
    fare_base::DOUBLE                                              AS fare_base,
    rider_total_ex_tip::DOUBLE                                     AS rider_total_ex_tip,
    tips::DOUBLE                                                   AS tips
FROM g;
