-- ref_indicators: the TLC monthly indicators CSV as published, plus a parsed month (SPEC §3.2, §5; D19).
--
-- Input   indicators_csv: data/ref/data_reports_monthly.csv read with every column as text
--         (pipeline/validate.py checks the header first). Empty cells arrive as NULL.
-- Output  one row per Year/Month × License Class, column names unchanged:
--   month                                   DATE, first day of "Year/Month"
--   "Year/Month"                            text as published, e.g. 2026-08
--   "License Class"                         text, e.g. FHV - High Volume, Yellow, Green
--   numeric columns                         DOUBLE, values unchanged
--   "Percent of Trips Paid with Credit Card" DOUBLE, a whole-number percent (79 = 79%), NULL for FHV classes
-- A value that doesn't parse fails the load; nothing is coerced to NULL.

SELECT
    CAST(strptime("Year/Month", '%Y-%m') AS DATE)           AS month,
    "Year/Month",
    "License Class",
    CAST("Trips Per Day" AS DOUBLE)                         AS "Trips Per Day",
    CAST("Farebox Per Day" AS DOUBLE)                       AS "Farebox Per Day",
    CAST("Unique Drivers" AS DOUBLE)                        AS "Unique Drivers",
    CAST("Unique Vehicles" AS DOUBLE)                       AS "Unique Vehicles",
    CAST("Vehicles Per Day" AS DOUBLE)                      AS "Vehicles Per Day",
    CAST("Avg Days Vehicles on Road" AS DOUBLE)             AS "Avg Days Vehicles on Road",
    CAST("Avg Hours Per Day Per Vehicle" AS DOUBLE)         AS "Avg Hours Per Day Per Vehicle",
    CAST("Avg Days Drivers on Road" AS DOUBLE)              AS "Avg Days Drivers on Road",
    CAST("Avg Hours Per Day Per Driver" AS DOUBLE)          AS "Avg Hours Per Day Per Driver",
    CAST("Avg Minutes Per Trip" AS DOUBLE)                  AS "Avg Minutes Per Trip",
    CAST("Percent of Trips Paid with Credit Card" AS DOUBLE) AS "Percent of Trips Paid with Credit Card",
    CAST("Trips Per Day Shared" AS DOUBLE)                  AS "Trips Per Day Shared"
FROM indicators_csv
ORDER BY month, "License Class";
