-- Metric: cp_weekly_trips
-- Questions: Q2
-- Params: none
-- Grain: iso week × cbd_group × mode × zone_list, ISO years 2024 and 2025; ride_hail (uber + lyft + other_hv), taxi (yellow + green) and all
-- Columns: iso_year, iso_week, week_start, cbd_group, mode, zone_list, trips_per_day
-- Source: TLC trip records
--
-- Trips per day inside (treated) and outside (control) the zone, every row counted (trips_all),
-- under both zone lists (D9): the weekly series behind cp_effect. Weeks are summed over month
-- (D7). trips_per_day divides by the days of the ISO week whose month is in agg_week_cbd, so a
-- week cut by the first or last month in the table isn't understated. week_start is the
-- Monday of the ISO week.
WITH study AS (
    SELECT 2024 AS base_year, 2025 AS study_year
),
weekly AS (
    SELECT w.iso_year, w.iso_week, w.zone_list, w.cbd_group, w.mode, SUM(w.trips_all) AS trips
    FROM agg_week_cbd w, study s
    WHERE w.iso_year IN (s.base_year, s.study_year)
    GROUP BY w.iso_year, w.iso_week, w.zone_list, w.cbd_group, w.mode
),
grouped AS (
    SELECT iso_year, iso_week, zone_list, cbd_group,
           CASE WHEN mode IN ('uber', 'lyft', 'other_hv') THEN 'ride_hail' ELSE 'taxi' END AS mode,
           SUM(trips) AS trips
    FROM weekly
    WHERE mode IN ('uber', 'lyft', 'other_hv', 'yellow', 'green')
    GROUP BY ALL
    UNION ALL
    SELECT iso_year, iso_week, zone_list, cbd_group, 'all', SUM(trips)
    FROM weekly
    GROUP BY iso_year, iso_week, zone_list, cbd_group
),
weeks AS (
    SELECT DISTINCT iso_year, iso_week,
           date_trunc('week', make_date(iso_year, 1, 4))::DATE + 7 * (iso_week - 1) AS week_start
    FROM weekly
),
coverage AS (   -- days of each week whose month is in agg_week_cbd
    SELECT w.iso_year, w.iso_week, w.week_start, count(m.month) AS days
    FROM weeks w
    CROSS JOIN range(7) d(i)
    LEFT JOIN (SELECT DISTINCT month FROM agg_week_cbd) m
           ON m.month = date_trunc('month', w.week_start + d.i::INTEGER)::DATE
    GROUP BY w.iso_year, w.iso_week, w.week_start
)
SELECT g.iso_year::SMALLINT AS iso_year,
       g.iso_week::SMALLINT AS iso_week,
       c.week_start,
       g.cbd_group,
       g.mode,
       g.zone_list,
       g.trips / NULLIF(c.days, 0) AS trips_per_day
FROM grouped g
JOIN coverage c USING (iso_year, iso_week)
ORDER BY iso_year, iso_week, zone_list, cbd_group, mode;
