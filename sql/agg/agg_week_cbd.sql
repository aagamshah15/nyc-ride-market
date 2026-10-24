-- agg_week_cbd · SPEC §5, D7, D9 · lane L07
-- Trips by ISO week, inside or outside the congestion zone, under both zone lists.
--
-- Input  view `trips`: that month's clean files (pipeline/aggregate.py)
-- Grain  month × iso_year × iso_week × mode × zone_list × cbd_group. `month` is the source file's
--        month (D7), so an ISO week that straddles two months has rows under both; sum over month
--        to get the whole week. Every trip appears once per zone_list (D9), so never sum across lists.
--
-- month               DATE      first day of the source file's month (D7)
-- iso_year            SMALLINT  ISO year of pickup_ts (2024-12-30 is 2025-W01)
-- iso_week            SMALLINT  ISO week of pickup_ts, 1–53
-- mode                VARCHAR   uber, lyft, other_hv, yellow, green
-- zone_list           VARCHAR   core (cbd_touch) or wide (cbd_touch_wide) (D9)
-- cbd_group           VARCHAR   treated = the trip touches the zone under that list; control = not
-- trips_all           BIGINT    all rows, valid or not
-- trips_valid         BIGINT    rows with is_valid
-- miles               DOUBLE    sum over valid rows
-- duration_s          BIGINT    sum over valid rows
-- fare_base           DOUBLE    sum over valid rows
-- driver_pay          DOUBLE    sum over valid rows; ride-hail only, NULL for cabs
-- rider_total_ex_tip  DOUBLE    sum over valid rows
--
-- A NULL cbd flag (only possible with a NULL zone) counts as control, as an unknown zone (264, 265)
-- does. A sum over no valid rows is 0. Money and miles are summed as DECIMAL(18, 4), exact for TLC
-- values, so the sums don't depend on row order.

WITH t AS (
    SELECT
        month,
        isoyear(pickup_ts) AS iso_year,
        week(pickup_ts) AS iso_week,
        mode,
        mode IN ('uber', 'lyft', 'other_hv') AS hv,
        is_valid, cbd_touch, cbd_touch_wide,
        miles::DECIMAL(18, 4) AS miles,
        duration_s,
        fare_base::DECIMAL(18, 4) AS fare_base,
        driver_pay::DECIMAL(18, 4) AS driver_pay,
        rider_total_ex_tip::DECIMAL(18, 4) AS rider_total_ex_tip
    FROM trips
),
lists AS (
    SELECT 'core' AS zone_list, cbd_touch IS TRUE AS treated, * FROM t
    UNION ALL
    SELECT 'wide' AS zone_list, cbd_touch_wide IS TRUE AS treated, * FROM t
),
g AS (
    SELECT
        month, iso_year, iso_week, mode, hv, zone_list, treated,
        count(*)                                                   AS trips_all,
        count(*) FILTER (WHERE is_valid)                           AS trips_valid,
        sum(miles) FILTER (WHERE is_valid)                         AS miles,
        sum(duration_s) FILTER (WHERE is_valid)                    AS duration_s,
        sum(fare_base) FILTER (WHERE is_valid)                     AS fare_base,
        sum(driver_pay) FILTER (WHERE is_valid)                    AS driver_pay,
        sum(rider_total_ex_tip) FILTER (WHERE is_valid)            AS rider_total_ex_tip
    FROM lists
    GROUP BY month, iso_year, iso_week, mode, hv, zone_list, treated
)
SELECT
    month::DATE                                                    AS month,
    iso_year::SMALLINT                                             AS iso_year,
    iso_week::SMALLINT                                             AS iso_week,
    mode::VARCHAR                                                  AS mode,
    zone_list::VARCHAR                                             AS zone_list,
    (CASE WHEN treated THEN 'treated' ELSE 'control' END)::VARCHAR AS cbd_group,
    trips_all::BIGINT                                              AS trips_all,
    trips_valid::BIGINT                                            AS trips_valid,
    coalesce(miles, 0)::DOUBLE                                     AS miles,
    coalesce(duration_s, 0)::BIGINT                                AS duration_s,
    coalesce(fare_base, 0)::DOUBLE                                 AS fare_base,
    (CASE WHEN hv THEN coalesce(driver_pay, 0) END)::DOUBLE        AS driver_pay,
    coalesce(rider_total_ex_tip, 0)::DOUBLE                        AS rider_total_ex_tip
FROM g;
