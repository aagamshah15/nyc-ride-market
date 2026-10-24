-- Metric: cp_effect_summary
-- Questions: Q2, Q3
-- Params: none
-- Grain: mode × metric × zone_list; each mode, plus ride_hail and all (as cp_effect)
-- Columns: mode, metric, zone_list, weeks INT, median, p10, p90
-- Source: TLC trip records
--
-- SPEC §6: the median weekly estimated effect and its 10th–90th percentile range across the
-- 2025 weeks of cp_effect that are not excluded (holiday weeks and weeks the aggregates don't
-- fully cover), from W02 on (D12). Percentiles interpolate linearly between weeks
-- (quantile_cont). weeks counts the weeks with an effect; a group with none gets weeks 0 and
-- NULL median, p10 and p90. The weekly effects are computed exactly as in cp_effect.sql.

-- BEGIN weekly effects: keep identical in cp_effect.sql and cp_effect_summary.sql (tests/test_cp_effect.py)
WITH study AS (
    -- congestion_pricing_start (config/periods.yaml). Study weeks are the 2025 ISO weeks that
    -- start on or after it, 2025-W02 on (D12), each against the same ISO week of 2024.
    SELECT DATE '2025-01-05' AS cp_start, 2024 AS base_year, 2025 AS study_year
),
holiday_weeks(iso_week, holiday, reason) AS (
    -- config/periods.yaml excluded_holiday_weeks, mirrored because metrics read only the
    -- aggregate tables. tests/test_cp_effect.py fails if the two lists differ.
    VALUES (3, 'Martin Luther King Jr. Day',
            'Martin Luther King Jr. Day is in ISO week 3 in 2024 (Mon 15 Jan) and week 4 in 2025 (Mon 20 Jan)'),
           (4, 'Martin Luther King Jr. Day',
            'Martin Luther King Jr. Day is in ISO week 3 in 2024 (Mon 15 Jan) and week 4 in 2025 (Mon 20 Jan)')
),
weekly AS (
    SELECT w.iso_year, w.iso_week, w.zone_list, w.cbd_group, w.mode,
           SUM(w.trips_all) AS trips,
           SUM(w.miles) AS miles,
           SUM(w.fare_base) AS fare_base,
           SUM(w.driver_pay) AS driver_pay
    FROM agg_week_cbd w, study s
    WHERE w.iso_year IN (s.base_year, s.study_year)
    GROUP BY w.iso_year, w.iso_week, w.zone_list, w.cbd_group, w.mode
),
grouped AS (    -- ds_pay and ds_fare are the driver_share sums
    SELECT iso_year, iso_week, zone_list, cbd_group, mode, trips, miles, fare_base,
           driver_pay AS ds_pay, fare_base AS ds_fare
    FROM weekly
    UNION ALL
    SELECT iso_year, iso_week, zone_list, cbd_group, 'ride_hail', SUM(trips), SUM(miles), SUM(fare_base),
           SUM(driver_pay) FILTER (WHERE mode IN ('uber', 'lyft')),
           SUM(fare_base) FILTER (WHERE mode IN ('uber', 'lyft'))
    FROM weekly
    WHERE mode IN ('uber', 'lyft', 'other_hv')
    GROUP BY iso_year, iso_week, zone_list, cbd_group
    UNION ALL
    SELECT iso_year, iso_week, zone_list, cbd_group, 'all', SUM(trips), SUM(miles), SUM(fare_base), NULL, NULL
    FROM weekly
    GROUP BY iso_year, iso_week, zone_list, cbd_group
),
metric_values AS (
    SELECT iso_year, iso_week, zone_list, cbd_group, mode, 'trips' AS metric, trips::DOUBLE AS value
    FROM grouped
    UNION ALL
    SELECT iso_year, iso_week, zone_list, cbd_group, mode, 'fare_per_mile', fare_base / NULLIF(miles, 0)
    FROM grouped
    UNION ALL
    SELECT iso_year, iso_week, zone_list, cbd_group, mode, 'driver_share', ds_pay / NULLIF(ds_fare, 0)
    FROM grouped
    WHERE mode IN ('uber', 'lyft', 'ride_hail')
),
study_weeks AS (
    SELECT DISTINCT w.iso_week,
           date_trunc('week', make_date(s.study_year, 1, 4))::DATE + 7 * (w.iso_week - 1) AS week_start
    FROM weekly w, study s
    WHERE w.iso_year = s.study_year
      AND date_trunc('week', make_date(s.study_year, 1, 4))::DATE + 7 * (w.iso_week - 1) >= s.cp_start
),
week_days AS (  -- the 7 days of each study week, in 2025 and in the same ISO week of 2024
    SELECT w.iso_week, y.iso_year,
           date_trunc('week', make_date(y.iso_year, 1, 4))::DATE + 7 * (w.iso_week - 1) + d.i::INTEGER AS day
    FROM study_weeks w
    CROSS JOIN (SELECT base_year AS iso_year FROM study UNION ALL SELECT study_year FROM study) y
    CROSS JOIN range(7) d(i)
),
coverage AS (   -- days whose month is in agg_week_cbd
    SELECT wd.iso_week,
           count(m.month) FILTER (WHERE wd.iso_year = s.base_year) AS days_base,
           count(m.month) FILTER (WHERE wd.iso_year = s.study_year) AS days_now
    FROM week_days wd
    CROSS JOIN study s
    LEFT JOIN (SELECT DISTINCT month FROM agg_week_cbd) m ON m.month = date_trunc('month', wd.day)::DATE
    GROUP BY wd.iso_week
),
cells AS (
    SELECT v.iso_week, v.zone_list, v.mode, v.metric,
           any_value(v.value) FILTER (WHERE v.iso_year = s.study_year AND v.cbd_group = 'treated') AS treated_now,
           any_value(v.value) FILTER (WHERE v.iso_year = s.base_year AND v.cbd_group = 'treated') AS treated_base,
           any_value(v.value) FILTER (WHERE v.iso_year = s.study_year AND v.cbd_group = 'control') AS control_now,
           any_value(v.value) FILTER (WHERE v.iso_year = s.base_year AND v.cbd_group = 'control') AS control_base
    FROM metric_values v
    JOIN study_weeks USING (iso_week)
    CROSS JOIN study s
    GROUP BY v.iso_week, v.zone_list, v.mode, v.metric
),
growth AS (
    SELECT c.*,
           c.treated_now / NULLIF(c.treated_base, 0) AS growth_treated,
           c.control_now / NULLIF(c.control_base, 0) AS growth_control
    FROM cells c
),
effects AS (
    SELECT s.study_year AS iso_year, g.iso_week, w.week_start, g.mode, g.metric, g.zone_list,
           g.growth_treated, g.growth_control,
           g.growth_treated / NULLIF(g.growth_control, 0) - 1 AS effect,
           h.reason IS NOT NULL OR cov.days_base < 7 OR cov.days_now < 7 AS excluded,
           NULLIF(concat_ws('; ',
               h.reason,
               CASE WHEN cov.days_base < 7
                    THEN format('the aggregates cover {} of the 7 days of {}-W{:02d}', cov.days_base, s.base_year, g.iso_week) END,
               CASE WHEN cov.days_now < 7
                    THEN format('the aggregates cover {} of the 7 days of {}-W{:02d}', cov.days_now, s.study_year, g.iso_week) END
           ), '') AS exclusion_reason
    FROM growth g
    JOIN study_weeks w USING (iso_week)
    JOIN coverage cov USING (iso_week)
    LEFT JOIN (SELECT iso_week, string_agg(reason, '; ' ORDER BY reason) AS reason
               FROM holiday_weeks GROUP BY iso_week) h USING (iso_week)
    CROSS JOIN study s
)
-- END weekly effects
SELECT mode,
       metric,
       zone_list,
       count(effect) FILTER (WHERE NOT excluded)::INTEGER AS weeks,
       quantile_cont(effect, 0.5) FILTER (WHERE NOT excluded) AS median,
       quantile_cont(effect, 0.1) FILTER (WHERE NOT excluded) AS p10,
       quantile_cont(effect, 0.9) FILTER (WHERE NOT excluded) AS p90
FROM effects
GROUP BY mode, metric, zone_list
ORDER BY zone_list, metric, mode;
