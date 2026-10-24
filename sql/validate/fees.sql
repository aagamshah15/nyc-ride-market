-- Fee check (SPEC §8; D8): of the trips with cbd_fee > 0, the share carrying exactly the configured
-- fee for their mode.
--
-- Inputs  months_checked(month), agg_fee_values (views set up by pipeline/validate.py)
-- Params  $fee_from        month containing congestion_pricing_start (config/periods.yaml)
--         $fee_hvfhv       configured fee for uber, lyft, other_hv (cbd_fee_hvfhv)
--         $fee_taxi        configured fee for yellow, green (cbd_fee_taxi)
--         $min_exact_pct   pass when at least this percentage carries the configured fee (95)
-- Output  GROUPING SETS, told apart by `level`:
--   level = 'mode'    one row per mode: the check itself
--   level = 'month'   mode × month (details)
--   level = 'value'   mode × cbd_fee: every fee value found, for listing the others
-- Columns: mode, month, cbd_fee, level, configured_fee, fee_trips, exact_trips, exact_share,
--          status (pass | fail; on 'value' rows, whether the value is the configured one)
-- "Exactly" means equal as stored; a mode outside the five codes has no configured fee and fails.

WITH fees AS (
    SELECT month, mode, cbd_fee, trips,
           CASE WHEN mode IN ('uber', 'lyft', 'other_hv') THEN CAST($fee_hvfhv AS DOUBLE)
                WHEN mode IN ('yellow', 'green') THEN CAST($fee_taxi AS DOUBLE) END AS configured_fee
    FROM agg_fee_values
    WHERE cbd_fee > 0
      AND month >= $fee_from
      AND month IN (SELECT month FROM months_checked)
),
sums AS (
    SELECT
        mode, month, cbd_fee,
        CASE WHEN GROUPING(month) = 0 THEN 'month'
             WHEN GROUPING(cbd_fee) = 0 THEN 'value'
             ELSE 'mode' END                                                       AS level,
        any_value(configured_fee)                                                  AS configured_fee,
        CAST(SUM(trips) AS BIGINT)                                                 AS fee_trips,
        CAST(COALESCE(SUM(trips) FILTER (WHERE cbd_fee = configured_fee), 0) AS BIGINT) AS exact_trips
    FROM fees
    GROUP BY GROUPING SETS ((mode), (mode, month), (mode, cbd_fee))
)
SELECT
    mode, month, cbd_fee, level, configured_fee, fee_trips, exact_trips,
    exact_trips / NULLIF(fee_trips, 0)                       AS exact_share,
    -- integer comparison, so exactly min_exact_pct passes
    CASE WHEN fee_trips > 0 AND exact_trips * 100 >= $min_exact_pct * fee_trips
         THEN 'pass' ELSE 'fail' END                         AS status
FROM sums
ORDER BY mode, level, month, fee_trips DESC, cbd_fee;
