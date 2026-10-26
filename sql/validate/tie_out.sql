-- Tie-out (SPEC §8; D25): pipeline trips per day against TLC's "Trips Per Day", per month × license class.
--
-- Inputs  months_checked(month), agg_zone_hour, agg_vendor_month, ref_indicators, and
--         excluded_vendors(mode, vendor_id): tie_out_exclude_vendors in config/sources.yaml, by mode
--         (views and tables set up by pipeline/validate.py)
-- Params  $tolerance_pct   pass when |pipeline − TLC| ≤ tolerance_pct % of TLC (2 per SPEC §8)
-- Output  one row per month checked × license class:
--   month, license_class        FHV - High Volume = uber + lyft + other_hv; Yellow; Green
--   records                     SUM(trips_all): every row, valid or not (SPEC §4.2)
--   excluded_records            records from vendors in tie_out_exclude_vendors (agg_vendor_month; D25
--                               mechanism, an empty list since D27); every metric keeps them
--   excluded_vendor_ids         the class's excluded vendors, sorted; NULL when it has none
--   pipeline_trips              records − excluded_records
--   days                        days in the month
--   pipeline_trips_per_day      pipeline_trips / days
--   tlc_trips_per_day           "Trips Per Day"; NULL when the indicators file lacks the row
--   diff                        pipeline ÷ TLC − 1
--   status                      pass | fail | skipped (indicators file lacks that month and class)
-- A month with no pipeline rows counts 0 trips and fails. pipeline/validate.py then applies D27:
-- only FHV - High Volume gates the check, and rows in tie_out_exceptions become 'excepted'.

WITH classes(mode, license_class) AS (
    VALUES ('uber', 'FHV - High Volume'), ('lyft', 'FHV - High Volume'), ('other_hv', 'FHV - High Volume'),
           ('yellow', 'Yellow'), ('green', 'Green')
),
records AS (
    SELECT z.month, c.license_class, CAST(SUM(z.trips_all) AS BIGINT) AS records
    FROM agg_zone_hour z
    JOIN classes c USING (mode)
    GROUP BY z.month, c.license_class
),
excluded AS (
    SELECT v.month, c.license_class, CAST(SUM(v.rows) AS BIGINT) AS records
    FROM agg_vendor_month v
    JOIN excluded_vendors e ON e.mode = v.mode AND e.vendor_id = v.vendor_id
    JOIN classes c ON c.mode = v.mode
    GROUP BY v.month, c.license_class
),
class_vendors AS (
    SELECT c.license_class, list_sort(list(DISTINCT e.vendor_id)) AS vendor_ids
    FROM excluded_vendors e
    JOIN classes c USING (mode)
    GROUP BY c.license_class
),
grid AS (
    SELECT m.month, l.license_class, day(last_day(m.month)) AS days
    FROM months_checked m
    CROSS JOIN (SELECT DISTINCT license_class FROM classes) l
),
joined AS (
    SELECT g.month, g.license_class, g.days,
           COALESCE(r.records, 0)                          AS records,
           COALESCE(x.records, 0)                          AS excluded_records,
           cv.vendor_ids                                   AS excluded_vendor_ids,
           COALESCE(r.records, 0) - COALESCE(x.records, 0) AS pipeline_trips,
           i."Trips Per Day"                               AS tlc_trips_per_day,
           i.month IS NOT NULL                             AS has_indicator
    FROM grid g
    LEFT JOIN records r ON r.month = g.month AND r.license_class = g.license_class
    LEFT JOIN excluded x ON x.month = g.month AND x.license_class = g.license_class
    LEFT JOIN class_vendors cv ON cv.license_class = g.license_class
    LEFT JOIN ref_indicators i ON i.month = g.month AND i."License Class" = g.license_class
)
SELECT
    month, license_class, records, excluded_records, excluded_vendor_ids, pipeline_trips, days,
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
