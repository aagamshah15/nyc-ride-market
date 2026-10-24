-- Tie-out (SPEC §8): pipeline trips per day against TLC's "Trips Per Day", per month × license class.
--
-- Inputs  months_checked(month), agg_zone_hour, ref_indicators (views set up by pipeline/validate.py)
-- Params  $tolerance_pct   pass when |pipeline − TLC| ≤ tolerance_pct % of TLC (2 per SPEC §8)
-- Output  one row per month checked × license class:
--   month, license_class        FHV - High Volume = uber + lyft + other_hv; Yellow; Green
--   pipeline_trips              SUM(trips_all): every row, valid or not (SPEC §4.2)
--   days                        days in the month
--   pipeline_trips_per_day      pipeline_trips / days
--   tlc_trips_per_day           "Trips Per Day"; NULL when the indicators file lacks the row
--   diff                        pipeline ÷ TLC − 1
--   status                      pass | fail | skipped (indicators file lacks that month and class)
-- A month with no pipeline rows counts 0 trips and fails.

WITH classes(mode, license_class) AS (
    VALUES ('uber', 'FHV - High Volume'), ('lyft', 'FHV - High Volume'), ('other_hv', 'FHV - High Volume'),
           ('yellow', 'Yellow'), ('green', 'Green')
),
pipeline AS (
    SELECT z.month, c.license_class, CAST(SUM(z.trips_all) AS BIGINT) AS trips
    FROM agg_zone_hour z
    JOIN classes c USING (mode)
    GROUP BY z.month, c.license_class
),
grid AS (
    SELECT m.month, l.license_class, day(last_day(m.month)) AS days
    FROM months_checked m
    CROSS JOIN (SELECT DISTINCT license_class FROM classes) l
),
joined AS (
    SELECT g.month, g.license_class, g.days,
           COALESCE(p.trips, 0)        AS pipeline_trips,
           r."Trips Per Day"           AS tlc_trips_per_day,
           r.month IS NOT NULL         AS has_indicator
    FROM grid g
    LEFT JOIN pipeline p ON p.month = g.month AND p.license_class = g.license_class
    LEFT JOIN ref_indicators r ON r.month = g.month AND r."License Class" = g.license_class
)
SELECT
    month, license_class, pipeline_trips, days,
    pipeline_trips / days                                     AS pipeline_trips_per_day,
    tlc_trips_per_day,
    pipeline_trips / days / NULLIF(tlc_trips_per_day, 0) - 1 AS diff,
    CASE
        WHEN NOT has_indicator THEN 'skipped'
        -- multiplied out so the boundary is exact: |trips − TLC × days| × 100 ≤ tolerance × TLC × days
        WHEN tlc_trips_per_day > 0
             AND abs(pipeline_trips - tlc_trips_per_day * days) * 100
                 <= $tolerance_pct * tlc_trips_per_day * days THEN 'pass'
        ELSE 'fail'
    END                                                       AS status
FROM joined
ORDER BY month, license_class;
