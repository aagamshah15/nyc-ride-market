-- Quality drift (SPEC §8; D26): share of valid rows per month × mode.
--
-- Inputs  months_checked(month), agg_quality_month (views set up by pipeline/validate.py)
-- Params  $min_valid_pct   fail when valid_rows / rows is below this percentage (85 per D26; SPEC had 95)
--         $drift_points    list a month more than this many points below its mode's median (3)
-- Output  one row per month × mode:
--   month, mode, rows, valid_rows
--   valid_share             valid_rows / rows
--   mode_median             median valid_share of the mode over the months checked
--   points_below_median     (mode_median − valid_share) × 100, rounded to 1e-6 to drop float noise
--   drift                   points_below_median > drift_points (listed, not failed)
--   status                  pass | fail

WITH shares AS (
    SELECT month, mode,
           CAST(SUM(rows) AS BIGINT)                  AS rows,
           CAST(SUM(valid_rows) AS BIGINT)            AS valid_rows,
           SUM(valid_rows) / NULLIF(SUM(rows), 0)     AS valid_share
    FROM agg_quality_month
    WHERE month IN (SELECT month FROM months_checked)
    GROUP BY month, mode
),
medians AS (
    SELECT mode, median(valid_share) AS mode_median
    FROM shares
    GROUP BY mode
)
SELECT
    s.month, s.mode, s.rows, s.valid_rows, s.valid_share, m.mode_median,
    round((m.mode_median - s.valid_share) * 100, 6)                       AS points_below_median,
    COALESCE(round((m.mode_median - s.valid_share) * 100, 6) > $drift_points, false) AS drift,
    -- integer comparison, so exactly min_valid_pct passes
    CASE WHEN s.rows > 0 AND s.valid_rows * 100 >= $min_valid_pct * s.rows
         THEN 'pass' ELSE 'fail' END                                       AS status
FROM shares s
JOIN medians m USING (mode)
ORDER BY s.month, s.mode;
