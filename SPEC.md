# NYC Ride Market — Development Spec

Version 1.0 · 22 Oct 2026 · Owner: Aagam

This is the build spec. The product brief (why, audiences, the 15 questions, design rationale) lives in the doc
"NYC Ride-Hail vs Taxi: Analytics Action Plan". Where the two disagree, this file wins for implementation details.

---

## 0. Decisions (locked for v1)

| # | Decision | Choice |
|---|---|---|
| D1 | Site stack | Static site built with **Observable Framework** (charts in **Observable Plot**), hosted on **GitHub Pages** |
| D2 | Time scope | **Jan 2024 → latest TLC month** for v1. Back-fill Feb 2019 → Dec 2023 after launch (Phase 6) |
| D3 | Company pages | **Separate pages** for Uber, Lyft, Yellow, Green, each with a comparison block against the others |
| D4 | Compute | **DuckDB (Python)** on a laptop; one month of raw data in memory at a time |
| D5 | Data in git | **Never** commit raw, clean or aggregate data. Commit only the small published JSON/Parquet the site reads |
| D6 | Refresh | Monthly, via GitHub Actions, triggered when a new TLC month appears |

Changing any of these needs a note in `docs/decisions.md` with date and reason.

---

## 1. Repo layout

```
nyc-ride-market/
├── CLAUDE.md                  # conventions for Claude Code
├── SPEC.md                    # this file
├── README.md                  # public-facing: what the site is, how to run it
├── Makefile                   # every pipeline step is a make target
├── pyproject.toml             # Python deps (pinned)
├── config/
│   ├── sources.yaml           # URL pattern, datasets, months in scope
│   ├── schema_map.yaml        # raw column → unified column, per dataset and year range
│   ├── cbd_zones.csv          # congestion-zone LocationIDs (built in Phase 1)
│   ├── airports.csv           # LocationID → airport code
│   └── periods.yaml           # policy dates used for period labels
├── pipeline/
│   ├── ingest.py              # download one month, checksum, manifest entry
│   ├── discover.py            # DESCRIBE every file in scope → reports/schema_discovery.md
│   ├── clean.py               # raw → unified trips (runs sql/clean/*.sql)
│   ├── aggregate.py           # clean → aggregate tables (runs sql/agg/*.sql)
│   ├── validate.py            # tie-out vs TLC monthly indicators; CBD-list check
│   ├── publish.py             # aggregates → site/src/data/*.json
│   └── zones.py               # shapefile → simplified GeoJSON; CBD zone helper
├── sql/
│   ├── clean/                 # one file per dataset: hvfhv.sql, yellow.sql, green.sql
│   ├── agg/                   # one file per aggregate table
│   └── metrics/               # one file per metric (Section 6)
├── data/                      # GITIGNORED
│   ├── raw/{dataset}/{YYYY-MM}.parquet
│   ├── clean/mode={mode}/month={YYYY-MM}/part-0.parquet
│   ├── agg/{table}.parquet
│   └── manifest.json          # file, month, bytes, sha256, rows, downloaded_at
├── reports/                   # generated QA reports (committed: small markdown only)
├── site/                      # Observable Framework project
│   ├── observablehq.config.js
│   └── src/
│       ├── index.md
│       ├── companies/[company].md
│       ├── zones/[zone].md
│       ├── airports.md
│       ├── congestion-pricing.md
│       ├── drivers.md
│       ├── prices.md
│       ├── methods.md
│       ├── components/        # statTiles.js, charts.js, palette.js, format.js
│       └── data/              # published files the pages read (committed)
├── tests/
│   ├── fixtures/              # tiny hand-built Parquet files
│   └── test_*.py
├── docs/decisions.md
└── .github/workflows/
    ├── ci.yml                 # tests + site build on every push
    └── refresh.yml            # monthly data refresh + deploy
```

---

## 2. Environment

- Python 3.12. Pin in `pyproject.toml`: `duckdb` (latest 1.5.x; do not move to 2.x without testing), `pyarrow`, `pyyaml`, `requests`, `pytest`.
- DuckDB extensions: `spatial` (read the zone shapefile, point-in-polygon helpers), `httpfs` not needed (files are downloaded first).
- Node 20+. `@observablehq/framework` pinned to `1.13.4` (latest as of 22 Oct 2026, released 2 Mar 2026; releases are infrequent, so pin and don't chase). `@observablehq/plot` comes with Framework.
- `mapshaper` (npm) for simplifying the zone GeoJSON.

Make targets (all accept `MONTH=YYYY-MM` where relevant):

| Target | Does |
|---|---|
| `make setup` | Create venv, install Python and Node deps |
| `make discover` | Run schema discovery over every month in scope |
| `make ingest MONTH=` | Download the three datasets for that month |
| `make clean MONTH=` | Build the unified trips partition for that month |
| `make aggregate MONTH=` | Rebuild that month's rows in every aggregate table |
| `make month MONTH=` | ingest → clean → aggregate → delete raw for that month |
| `make backfill FROM= TO=` | `make month` for each month in range, one at a time |
| `make validate` | Tie-out and CBD checks → `reports/validation.md`; non-zero exit on failure |
| `make publish` | Write `site/src/data/` from aggregates |
| `make site-dev` / `make site-build` | Framework preview / static build |
| `make test` | pytest + site build |

---

## 3. Data sources

### 3.1 Trip files

URL pattern (checked 22 Oct 2026 on the [TLC Trip Record Data page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)):

```
https://d37ci6vzurychx.cloudfront.net/trip-data/{dataset}_tripdata_{YYYY-MM}.parquet
dataset ∈ { fhvhv, yellow, green }
```

- Latest month on 22 Oct 2026: **2026-08** for all three. TLC posts with about a two-month lag.
- Non-high-volume FHV (`fhv_`) is out of scope for v1.
- Ride-hail (`fhvhv`) exists from 2019-02.

### 3.2 Lookups and context

| File | URL | Use |
|---|---|---|
| Zone lookup CSV | https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv | LocationID → Borough, Zone, service_zone |
| Zone shapefile | https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip | Maps; CBD zone list |
| TLC monthly indicators | https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv | Tie-out; drivers, vehicles, hours (Q15) |
| Data dictionaries (18 Mar 2025) | [HVFHV](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf), [Yellow](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf), [Green](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_green.pdf) | Field meanings |

The indicators CSV has columns `Month/Year, License Class, Trips Per Day, Farebox Per Day, Unique Drivers, Unique Vehicles, Vehicles Per Day, Avg Days Vehicles on Road, Avg Hours Per Day Per Vehicle, Avg Days Drivers on Road, Avg Hours Per Day Per Driver, Avg Minutes Per Trip, Percent of Trips Paid with Credit Card, Trips Per Day Shared`. License classes include `FHV - High Volume`, `Yellow`, `Green`. It runs from 2018-07; latest row on 22 Oct 2026 was 2026-07.

### 3.3 Reference values

- `config/airports.csv`: `1,EWR` · `132,JFK` · `138,LGA`. Confirm against the zone lookup in Phase 1.
- Unknown zones: `264`, `265` (flag, don't drop).
- `config/periods.yaml`:

```yaml
congestion_pricing_start: 2025-01-05   # MTA Congestion Relief Zone toll begins
driver_pay_inflation_step: 2025-03-01  # TLC annual CPI-W step: per-minute minimum +3.92% (D28)
driver_pay_rise: 2025-08-01            # TLC minimum-pay rule: per-mile floor down, per-minute floor up (D28)
fees:
  cbd_fee_hvfhv: 1.50                  # per trip, peak and overnight
  cbd_fee_taxi: 0.75                   # yellow and green, per trip
```

- HV license codes: `HV0003` → `uber`, `HV0005` → `lyft`, `HV0002` (Juno) and `HV0004` (Via) → `other_hv`.

---

## 4. Unified trip schema

Every dataset is mapped into one table. **Step 1 of Phase 1 is schema discovery**: run `DESCRIBE` on every file in scope and write `reports/schema_discovery.md` (column names and types per file). Build `config/schema_map.yaml` from that report, not from the dictionaries alone. Match raw column names case-insensitively; some yellow files are reported to spell `airport_fee` as `Airport_fee`. If a file has a column not in the map, `clean.py` must fail with the file and column name.

| Unified column | Type | HVFHV source | Yellow source | Green source |
|---|---|---|---|---|
| `mode` | VARCHAR | from `hvfhs_license_num` (uber / lyft / other_hv) | `'yellow'` | `'green'` |
| `month` | DATE | first day of the file's month | same | same |
| `request_ts` | TIMESTAMP | `request_datetime` | NULL | NULL |
| `pickup_ts` | TIMESTAMP | `pickup_datetime` | `tpep_pickup_datetime` | `lpep_pickup_datetime` |
| `dropoff_ts` | TIMESTAMP | `dropoff_datetime` | `tpep_dropoff_datetime` | `lpep_dropoff_datetime` |
| `pu_zone`, `do_zone` | SMALLINT | `PULocationID`, `DOLocationID` | same | same |
| `miles` | DOUBLE | `trip_miles` | `trip_distance` | `trip_distance` |
| `duration_s` | INTEGER | `trip_time` | `epoch(dropoff − pickup)` | same as yellow |
| `fare_base` | DOUBLE | `base_passenger_fare` | `fare_amount` | `fare_amount` |
| `tips` | DOUBLE | `tips` | `tip_amount` (card only) | `tip_amount` (card only) |
| `tolls` | DOUBLE | `tolls` | `tolls_amount` | `tolls_amount` |
| `airport_fee` | DOUBLE | `airport_fee` | `airport_fee` | 0 |
| `congestion_surcharge` | DOUBLE | `congestion_surcharge` | same | same |
| `cbd_fee` | DOUBLE | `cbd_congestion_fee` (0 before 2025) | same | same |
| `other_fees` | DOUBLE | `bcf + sales_tax` | `extra + mta_tax + improvement_surcharge` | same as yellow |
| `rider_total_ex_tip` | DOUBLE | `fare_base + tolls + other_fees + congestion_surcharge + airport_fee + cbd_fee` | `total_amount − tip_amount` | same as yellow |
| `driver_pay` | DOUBLE | `driver_pay` | NULL | NULL |
| `is_card` | BOOLEAN | NULL | `payment_type = 1` | same |
| `shared_request`, `shared_match` | BOOLEAN | `shared_request_flag`, `shared_match_flag` = 'Y' | NULL | NULL |
| `wav_request`, `wav_match` | BOOLEAN | `wav_request_flag`, `wav_match_flag` = 'Y' | NULL | NULL |
| `street_hail` | BOOLEAN | NULL | NULL | `trip_type = 1` |

### 4.1 Derived columns (added in clean)

| Column | Rule |
|---|---|
| `wait_s` | `epoch(pickup_ts − request_ts)`; HVFHV only |
| `hour_of_week` | `dayofweek(pickup_ts) * 24 + hour(pickup_ts)`, 0–167, Sunday = 0 (DuckDB `dayofweek`) |
| `pu_borough`, `do_borough` | from zone lookup |
| `airport_pu`, `airport_do` | airport code or NULL, from `config/airports.csv` |
| `cbd_pu`, `cbd_do` | zone in `config/cbd_zones.csv` |
| `cbd_touch` | `cbd_pu OR cbd_do` |
| `period` | `pre_cp` (< 2025-01-05), `post_cp` (≥ 2025-01-05 and < 2025-08-01), `post_pay` (≥ 2025-08-01), by `pickup_ts` |

### 4.2 Quality flags (flag, never delete)

| Flag | True when |
|---|---|
| `f_time` | `duration_s <= 0` or `> 10800` (3 h), or pickup outside the file's month ± 1 day |
| `f_miles` | `miles <= 0` or `> 100` |
| `f_fare` | `fare_base <= 0` |
| `f_zone` | `pu_zone` or `do_zone` in (264, 265) or NULL |
| `f_wait` | HVFHV and (`wait_s < 0` or `> 3600`) |
| `is_valid` | none of `f_time`, `f_miles`, `f_fare`, `f_zone` |

Metrics use `is_valid` rows. Trip counts for share and tie-out use **all** rows, so they match TLC's own counts. Wait metrics also exclude `f_wait`.

---

## 5. Aggregate tables

Stored in `data/agg/{table}.parquet`. `aggregate.py MONTH=` deletes and rewrites that month's rows only. Sums are stored, not averages, so any roll-up stays correct.

| Table | Grain | Columns |
|---|---|---|
| `agg_zone_hour` | month × mode × pu_zone × hour_of_week | `trips_all, trips_valid, miles, duration_s, fare_base, rider_total_ex_tip, driver_pay, tips, card_trips, card_tips, card_fare_base, wait_s_sum, wait_n, cbd_fee, shared_req, shared_match, wav_req, wav_match, wav_trips` (D29) |
| `agg_zone_month_dist` | month × mode × pu_zone | `n, fpm_p10, fpm_p50, fpm_p90, fpmin_p50, wait_p50, wait_p90` (fpm = fare_base / miles; only zones × modes with n ≥ 100) |
| `agg_od_month` | month × mode × pu_zone × do_zone | `trips_valid, miles, duration_s, fare_base, driver_pay` (keep pairs with ≥ 20 trips that month) |
| `agg_airport` | month × mode × airport × direction × hour_of_day | `trips_valid, miles, duration_s, fare_base, rider_total_ex_tip, tips` (direction ∈ from, to) |
| `agg_week_cbd` | iso_year × iso_week × mode × cbd_group | `trips_all, trips_valid, miles, duration_s, fare_base, driver_pay, rider_total_ex_tip` (cbd_group ∈ treated = `cbd_touch`, control = not) |
| `agg_fees_month` | month × mode | `cbd_fee, congestion_surcharge, airport_fee, trips_with_cbd_fee` |
| `agg_quality_month` | month × mode | `rows, valid_rows, f_time, f_miles, f_fare, f_zone, f_wait` |

Indicators CSV is loaded as `ref_indicators` (month × license class) without changes.

---

## 6. Metric definitions

One file per metric in `sql/metrics/`, each a `SELECT` over aggregate tables with named parameters. The site never recomputes a metric from raw rows. Every metric gets a pytest using a fixture with a hand-computed answer.

**Trip share** (Q1, Q4, Q9, Q10)

```sql
-- sql/metrics/trip_share.sql   params: none (returns all months, zones)
SELECT month, pu_zone, mode,
       SUM(trips_all) AS trips,
       SUM(trips_all) / SUM(SUM(trips_all)) OVER (PARTITION BY month, pu_zone) AS share
FROM agg_zone_hour
GROUP BY month, pu_zone, mode;
```

**Driver share of fare / platform share** (Q3, Q5, Q6) — ratio of sums, HVFHV modes only

```sql
SELECT month, mode,
       SUM(driver_pay) / SUM(fare_base)       AS driver_share,
       1 - SUM(driver_pay) / SUM(fare_base)   AS platform_share
FROM agg_zone_hour
WHERE mode IN ('uber', 'lyft')
GROUP BY month, mode;
```

**Fare per mile and minute** (Q3, Q7, Q9): medians and percentiles from `agg_zone_month_dist`; city-wide means as `SUM(fare_base) / SUM(miles)` and `SUM(fare_base) / (SUM(duration_s) / 60)`.

**Price volatility** (Q7): `fpm_p90 / fpm_p10` per zone, month, mode.

**Wait time** (Q8): `wait_p50`, `wait_p90` from `agg_zone_month_dist`; mean = `wait_s_sum / wait_n`.

**Pay per on-trip hour** (Q6): `SUM(driver_pay) / (SUM(duration_s) / 3600)`, HVFHV only. Label it "per hour with a passenger" everywhere.

**Trips per hour worked** (Q15): from `ref_indicators`: `Trips Per Day / (Vehicles Per Day * Avg Hours Per Day Per Vehicle)`. Label as TLC-reported.

**Tip rate** (Q13): HVFHV `SUM(tips) / SUM(fare_base)`; taxis `SUM(card_tips) / SUM(card_fare_base)` (card trips only, state this on every chart).

**Accessible service** (Q11, D29): completed trips that requested a WAV, `SUM(wav_req)`, and the share of trips in a WAV, `SUM(wav_trips) / SUM(trips_valid)`, HVFHV only. Trip records hold completed trips only, so a match rate can't be measured; say so wherever Q11 appears. **Shared match rate** (Q12): `SUM(shared_match) / SUM(shared_req)`.

**Fee revenue** (Q14): `agg_fees_month.cbd_fee` by month and mode.

**Congestion-pricing effect** (Q2, Q3) — year-over-year difference-in-differences, weekly

```sql
-- For each ISO week w of 2025 and mode m:
-- growth_g = metric(2025, w, g) / metric(2024, w, g)  for g ∈ {treated, control}
-- effect   = growth_treated / growth_control - 1
-- metric ∈ { trips_all, fare_base/miles, driver_pay/fare_base }
```

Report the median weekly effect and the 10th–90th percentile range across weeks. Exclude ISO weeks containing US federal holidays that fall in different weeks across the two years (list them in `config/periods.yaml`). On the site, call it "estimated effect", never "caused".

**Pay-rise event study** (Q6): weekly HVFHV `driver_pay / miles` and `driver_pay / (duration_s / 60)` for the 12 ISO weeks before and after 2025-08-01, with the same weeks of 2024 drawn as the seasonal reference. Fares per mile on the same chart.

---

## 7. Congestion-zone list (`config/cbd_zones.csv`)

Taxi zones don't align exactly with the 60th Street boundary.

1. Load the shapefile with DuckDB `spatial`. Candidate zones = Manhattan zones whose polygon lies mostly south of 60th St. Build the first list by hand from the zone map; record each borderline zone and the call made in `reports/cbd_zones.md`.
2. Validate on 2025+ data:
   - Trips with both `pu_zone` and `do_zone` in the list: share with `cbd_fee > 0` should be ≥ 98% (initial threshold; adjust only with a written reason).
   - Trips with neither in the list: report the share with `cbd_fee > 0` (pass-through trips). This is expected to be non-zero and is reported, not failed.
3. Publish results with and without borderline zones on the methods page.

---

## 8. Validation gate (Phase 2)

`make validate` fails if any check fails. Output: `reports/validation.md`.

| Check | Pass condition |
|---|---|
| Tie-out | For every month in scope: trips per day from `agg_zone_hour.trips_all` within **±2%** of `ref_indicators."Trips Per Day"` for HVFHV (uber + lyft + other_hv vs `FHV - High Volume`), Yellow and Green. Months the indicators file doesn't have yet are skipped and listed |
| Quality drift | `valid_rows / rows` per month × mode ≥ 95%; any month more than 3 points below its mode's median is listed |
| CBD list | Section 7 thresholds |
| Schema | No unmapped columns in any file in scope |
| Fees | Since 2025-01-05, ≥ 95% of trips with `cbd_fee > 0` carry exactly the configured fee for their mode; list the other values found |

If the tie-out fails, investigate and fix the pipeline. Do not widen the tolerance to pass.

---

## 9. Site

### 9.1 Pages and routes

| Route | Source | Answers |
|---|---|---|
| `/` | `index.md` | Home: headline tiles, share trend, top findings |
| `/companies/{uber,lyft,yellow,green}` | `companies/[company].md` | Q4, Q5, Q11, Q12, Q13 + comparison block |
| `/zones/{1..263}` | `zones/[zone].md` | Q1, Q8, Q10 |
| `/airports` | `airports.md` | Q9 |
| `/congestion-pricing` | `congestion-pricing.md` | Q2, Q3, Q14 |
| `/drivers` | `drivers.md` | Q5, Q6, Q15 |
| `/prices` | `prices.md` | Q7 |
| `/methods` | `methods.md` | Cleaning, CBD list, validation results, limits, downloads |

Parameterized pages use Framework's `[param]` routes with `dynamicPaths` listed in `observablehq.config.js` (supported since Framework 1.12; confirm against the pinned version's docs before building).

### 9.2 Data contracts (`site/src/data/`, written by `publish.py`)

Every file carries `as_of_month` and `generated_at`. Budget: **≤ 1.5 MB of data per page**; `make test` fails if any page's files exceed it.

| File | Shape |
|---|---|
| `home.json` | `{as_of_month, tiles: {trips_per_day, rh_share, platform_share, cbd_fees_last_month}, yoy: {same keys}, findings: [{text, value, unit, page}]}` |
| `share_monthly.json` | `[{month, mode, trips_per_day, share}]` |
| `companies/{mode}.json` | `{tiles: {...}, share_trend: [...], fpm_dist: [...], tip_rate: [...], wav: [...], shared: [...], compare: [{metric, uber, lyft, yellow, green}]}` |
| `zones/index.json` | `[{zone, name, borough, trips_per_day, rh_share, wait_p50, share_change_yoy}]` |
| `zones/{zone}.json` | `{zone, name, borough, tiles, share_trend, hour_heatmap: [{hour_of_week, mode, trips}], waits, top_destinations: [{do_zone, name, trips}]}` (< 50 KB each) |
| `taxi_zones.geojson` | Simplified with mapshaper to < 1 MB |
| `airports.json`, `congestion.json`, `drivers.json`, `prices.json` | One object per page; keys mirror that page's charts |
| `quality.json` | `agg_quality_month` + validation summary for the methods page |

**Findings text is generated, not typed.** `publish.py` builds each finding sentence from computed values (e.g. `f"Lyft gained share in {n} zones since {base_year}"`). Markdown pages render findings from JSON and never contain hard-coded numbers.

### 9.3 Page template (every profile page)

1. Title stating the finding with its number (from JSON).
2. Stat row: 3–4 tiles, latest month + change vs same month a year earlier.
3. 2–4 charts; each has a finding subtitle and a source caption (`Source: NYC TLC trip records, {as_of_month}`).
4. "How we measured this" note linking to `/methods#{anchor}`.

### 9.4 Charts

| Use | Plot mark |
|---|---|
| Share over time | `Plot.line` per mode + `Plot.ruleX` at 2025-01-05 and 2025-08-01 with text labels |
| Zone level | `Plot.geo` choropleth, sequential blues |
| Zone change | `Plot.geo`, diverging, centred on 0 |
| Hour × weekday | `Plot.cell` heatmap, 24 × 7 |
| Policy effects | `Plot.dot` + `Plot.ruleY`/`ruleX` for the 10th–90th range, per metric |
| Price spread | `Plot.boxX` or `Plot.dot` strip of fare per mile by mode |
| Airport split | `Plot.barX` stacked to 100% |

Rules: no pies, no 3D, no dual y-axes. Plain data labels only on the points the finding rests on; no "Average" reference-line labels. Units in every axis label. Dates as `Jan 2025`.

### 9.5 Design tokens (`components/palette.js`)

All colours come from this file; components never use literal colours.

```js
export const mode = {
  uber:   {light: "#3A3A3A", dark: "#D4D4D4"},
  lyft:   {light: "#B4447F", dark: "#E07AB0"},
  yellow: {light: "#D99A00", dark: "#F2C14E"},
  green:  {light: "#3C8D5A", dark: "#6CC08A"},
  other_hv: {light: "#9AA0A6", dark: "#80868B"},
};
export const accent = {light: "#2F6FDB", dark: "#6E9CF0"};
export const muted  = {light: "#C9CDD2", dark: "#4A4F55"};
// sequential: Plot scheme "blues"; diverging: custom interpolate #2F6FDB → #F2F2F2 → #E07B39
```

Check every palette in a colour-blindness simulator and in dark mode before Phase 5 sign-off. No company logos or wordmarks anywhere; footer says "Independent analysis of public NYC TLC data. Not affiliated with any company named."

Type: Inter (self-hosted), `font-variant-numeric: tabular-nums` on tiles and tables. Layout collapses to one column below 640 px.

---

## 10. Monthly refresh (`.github/workflows/refresh.yml`)

- Trigger: weekly cron (Mondays 14:00 UTC) + manual `workflow_dispatch`.
- Step 1: HTTP `HEAD` the next expected month for all three datasets. If any is missing, exit 0 (nothing to do).
- Step 2: restore aggregates from the latest GitHub Release asset (`aggregates.tar.zst`).
- Step 3: `make month MONTH=<new>` (raw deleted after aggregation to stay within runner disk).
- Step 4: `make validate`. On failure: open an issue with `reports/validation.md` and stop; do not deploy.
- Step 5: `make publish && make site-build`, commit `site/src/data/`, deploy to GitHub Pages, upload new aggregates as a Release asset.
- Schema change (unmapped column) fails Step 3 loudly; fix `schema_map.yaml` by hand.
- Check the hosted runner's free disk and job time limit before relying on the job. If a month doesn't fit, fall back to running `make month` locally and pushing the aggregates.

---

## 11. Phases and definition of done

| Phase | Dates (2026) | Done when |
|---|---|---|
| 1. Setup + discovery | 26 Oct – 1 Nov | Repo scaffolded; `make ingest` works for any month; `reports/schema_discovery.md` covers 2024-01 → latest; `schema_map.yaml` complete; `cbd_zones.csv` first draft; airports confirmed |
| 2. Pipeline | 2 – 15 Nov | `make backfill FROM=2024-01 TO=<latest>` runs clean; all aggregate tables built; **`make validate` passes (gate)**; pytest covers cleaning flags and every metric |
| 3. Analysis | 9 – 29 Nov | Every metric in Section 6 produces output; congestion and pay-rise studies written up in `reports/`; each of Q1–Q15 has a one-sentence finding generated by code |
| 4. Site | 23 Nov – 10 Dec | All routes in 9.1 build; 263 zone pages generate; data budgets pass; palette and dark mode in place |
| 5. Review + launch | 7 – 14 Dec | Methods page complete; fresh-eyes review of each finding vs its chart; phone layout checked; refresh workflow ran once end-to-end; v1 deployed |
| 6. Back-fill (post-launch) | Jan 2027 | 2019-02 → 2023-12 processed and validated; long-run share charts extended |

Analysis may start on validated 2025 months before the full gate passes, but nothing is published until the gate passes.

---

## 12. Known limits (state on `/methods`)

- Congestion-pricing results are a year-over-year comparison against trips outside the zone, not a randomised test.
- Ride-hail `base_passenger_fare` excludes tolls, tips, taxes and fees; rider-cost comparisons use `rider_total_ex_tip`.
- Taxi tips are card-only.
- No surge flag, no rider identity, no driver time between trips in trip files.
- TLC does not guarantee vendor-submitted records and may change the Parquet schema.

---

## Appendix A. The 15 questions

Every page, metric and finding traces back to one of these. Q1, Q2, Q5 and Q9 carry the main story.

| # | Question | Who acts on it |
|---|---|---|
| Q1 | What share of trips does each of Uber, Lyft, yellow and green hold, by zone and hour, and how has it moved? | Platform strategy, taxi fleets |
| Q2 | Did congestion pricing shift trips into or out of the zone below 60th St, and which mode lost or gained? | MTA, TLC, platforms |
| Q3 | Who absorbed the $1.50 fee: did ride-hail fares or driver pay move after 5 Jan 2025? | MTA, driver groups |
| Q4 | Where does Lyft beat Uber on share, and is the gap growing? | Lyft and Uber strategy |
| Q5 | What share of the rider's fare reaches the driver, by company and over time? | Driver groups, TLC |
| Q6 | Did the new minimum-pay rule of 1 Aug 2025 (per-mile floor down, per-minute floor up) raise driver pay per hour, and did fares rise with it? (D28) | TLC, platforms |
| Q7 | What do riders pay per mile and per minute by company, hour and borough, and where is pricing most volatile? | Riders, journalists, platforms |
| Q8 | How long do riders wait from request to pickup, by zone and hour? | TLC, outer-borough officials |
| Q9 | At JFK, LaGuardia and Newark, who wins the airport trip, at what fare, and when? | Taxi fleets, Port Authority, platforms |
| Q10 | Where do yellow cabs still win against ride-hail, and is that ground shrinking? | Medallion owners, fleets |
| Q11 | How many trips that requested a wheelchair-accessible vehicle does each company complete, and what share of all its trips run in one? (D29) | TLC accessibility |
| Q12 | Are shared rides coming back, and where? | Platforms, MTA |
| Q13 | How do tipping rates differ by company, borough and payment type? | Drivers, platforms |
| Q14 | How much congestion-fee money does each mode generate per month? | MTA finance |
| Q15 | How many hours do drivers and vehicles work, and how many trips per hour on the road? | TLC, driver groups |
