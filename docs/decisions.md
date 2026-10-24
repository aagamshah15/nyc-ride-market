# Decisions log

Changes to SPEC.md's locked decisions and fills for gaps in it. SPEC §0 holds D1–D6. Each entry gives the date, the decision, the reason and the SPEC sections it touches. Newest last.

Format:

```
## Dn · Short title
Date · SPEC §x · Lanes affected
Decision. Reason.
```

---

## D7 · `agg_week_cbd` carries the source-file month

23 Oct 2026 · SPEC §5 · L01, L07, L10

The grain of `agg_week_cbd` becomes `month × iso_year × iso_week × mode × cbd_group` (plus `zone_list`, see D9). `month` is the first day of the source file's month. Metrics sum over `month` to get whole weeks.

Reason: ISO weeks straddle month boundaries, so `aggregate.py MONTH=` can't delete and rewrite "that month's rows" in a table keyed only by week.

## D8 · Two QA aggregate tables for the trip-level checks

23 Oct 2026 · SPEC §5, §7.2, §8 · L01, L07, L08

Add to SPEC §5:

| Table | Grain | Columns |
|---|---|---|
| `agg_cbd_pairs` | month × mode × pu_zone × do_zone (months from 2025-01) | `trips_all, trips_cbd_fee` (`cbd_fee > 0`) |
| `agg_fee_values` | month × mode × cbd_fee | `trips` |

The CBD-list check (SPEC §7.2) and the fee check (SPEC §8) read these tables.

Reason: both checks need trip-level detail, but the refresh job restores only aggregates and raw and clean files for past months are gone.

## D9 · Two congestion-zone lists: core and wide

23 Oct 2026 · SPEC §4.1, §5, §7 · L04, L06, L07, L10

`config/cbd_zones.csv` has columns `LocationID, zone, borderline, note`. The `core` list excludes borderline zones; the `wide` list includes them. `agg_week_cbd` gains `zone_list ∈ {core, wide}`, with `cbd_group` computed under each list. Clean computes the CBD flags for both lists. Other uses of `cbd_touch` use `core` unless stated.

Reason: SPEC §7.3 asks for results with and without borderline zones, and `cbd_group` is fixed when the aggregate is built.

## D10 · City-wide distribution row; airport fare tile is a mean

23 Oct 2026 · SPEC §5, §9.3 · L01, L07, L09, L16

`agg_zone_month_dist` gains one row per month × mode with `pu_zone = 0`, holding city-wide percentiles over all valid trips (same n ≥ 100 rule). Company and prices tiles read "median fare per mile" from it. The airport "fare to Manhattan" tile shows the mean fare per trip (ratio of sums from `agg_airport` / `agg_od_month`) and is labelled as a mean.

Reason: percentiles can't be combined across zones, and `agg_airport` stores sums only.

## D11 · Schema discovery reads Parquet footers over HTTP

23 Oct 2026 · SPEC §2, §4 · L03

`discover.py` may load DuckDB `httpfs` and read only each remote file's Parquet footer (DESCRIBE / `parquet_schema`) instead of downloading files. Every other step still works on downloaded files.

Reason: discovery covers 96 files (about 17 GB) in Phase 1, before the pipeline exists; downloading them all would repeat the back-fill. Replaces SPEC §2's "httpfs not needed" for this one script.

## D12 · Congestion effect starts at 2025-W02; 2025-W31 is a transition week

23 Oct 2026 · SPEC §6 · L10

The year-over-year difference-in-differences uses ISO weeks 2025-W02 onward. In the pay-rise event study, 2025-W31 (28 Jul – 3 Aug) is drawn but marked as a transition week and left out of before/after summaries.

Reason: 2025-W01 (30 Dec – 5 Jan) has only one day of pricing, and W31 straddles the 1 Aug 2025 pay rise, so both mix pre and post days.

## D13 · Add a `/zones` index route

23 Oct 2026 · SPEC §9.1 · L01, L05, L14

New route `/zones` from `site/src/zones/index.md`: the zone level and change maps (Q1, Q10) and a searchable table linking to each zone page. It reads `zones/index.json` and `taxi_zones.geojson`.

Reason: `zones/index.json` had no page in SPEC §9.1, and the city-wide zone maps need one.

## D14 · Repo setup

23 Oct 2026 · SPEC §1, §10 · L00, L17

Git repo initialised in the existing project folder. Because the folder name contains spaces, the Makefile and scripts use relative paths only. The user creates the GitHub repo and enables GitHub Pages; L17 needs both.

Reason: worktree-based lanes need git; Pages needs a GitHub repo; Make doesn't handle paths with spaces.

Update 23 Oct 2026: the repo was created at the user's request as https://github.com/aagamshah15/nyc-ride-market, first private, then made public by the user the same day. GitHub Pages is on at https://aagamshah15.github.io/nyc-ride-market/ with source "GitHub Actions" (switched from "Deploy from a branch" on 23 Oct). The `github-pages` environment accepts deploys from `main` only, and the default workflow token is read-only, so deploy workflows declare their own `permissions:`.

---

## D15 · `agg_od_month` carries `rider_total_ex_tip`

24 Oct 2026 · SPEC §5, §12 · L01, L07, L09, L16 · **Status: accepted by the user 24 Oct 2026** (proposed by L01)

Add `rider_total_ex_tip` (sum) to `agg_od_month`.

Reason: the airport "fare to Manhattan" needs an origin–destination table, and SPEC §12 says rider-cost comparisons across modes use `rider_total_ex_tip`; `agg_od_month` only had `fare_base`, whose fee coverage differs between ride-hail and cabs.

## D16 · City-wide distribution rows for mode groups

24 Oct 2026 · SPEC §5 · L01, L07, L09 · **Status: accepted by the user 24 Oct 2026** (proposed by L01)

Extends D10: the `pu_zone = 0` rows of `agg_zone_month_dist` also exist for the groups `ride_hail` (uber + lyft + other_hv) and `all`. Group rows exist only at `pu_zone = 0`.

Reason: the prices page tiles ("median fare per mile", "price volatility") are for all modes, and percentiles can't be combined from per-mode rows.

## D17 · Site data shapes beyond SPEC §9.2

24 Oct 2026 · SPEC §9.2, §9.3 · L05, L11, L12–L16 · **Status: accepted by the user 24 Oct 2026** (proposed by L01)

Pinned in `contracts/` (README §1, examples in `contracts/site/`):

- Every file carries `validated` alongside `as_of_month` and `generated_at`.
- `share_monthly.json` and `zones/index.json` are objects with a `rows` array (SPEC shows bare arrays, which can't carry the envelope).
- Two new files: `events.json` (policy dates and labels from `config/periods.yaml`) and `tiles.json` (the tile registry, `contracts/site/tiles.yaml`).
- Every page file has a generated `title`, a `subtitles` map (one finding per chart) and a `yoy` map matching `tiles`.
- Zone heatmaps keep modes with at least 10% of the zone's trips, to stay under the 50 KB zone-file cap.

Reason: SPEC requires generated titles and subtitles and no numbers in page markdown, but its file shapes had nowhere to put them.

## D18 · Clean partition files keep `mode` and `month`

24 Oct 2026 · SPEC §1, §4 · L06, L07 · **Status: accepted by the user 24 Oct 2026** (proposed by L01)

Files at `data/clean/mode={mode}/month={YYYY-MM}/part-0.parquet` contain every SPEC §4 column, including `mode` and `month` (DATE). Folder names are layout only; readers use `hive_partitioning = false`.

Reason: DuckDB's `PARTITION_BY` drops partition columns from the files and would name the folder `month=2025-03-01`, not SPEC's `month=2025-03`; pinning the files as self-contained avoids type and naming ambiguity.

## D19 · Indicators CSV comes from NYC Open Data

24 Oct 2026 · SPEC §3.2, §8 · L02, L08, L09 · **Status: accepted by the user 24 Oct 2026** (raised by L02)

The TLC monthly indicators are downloaded from NYC Open Data, "TLC Industry Indicators" (dataset `v6kb-cqej`, published by the TLC): `https://data.cityofnewyork.us/api/views/v6kb-cqej/rows.csv?accessType=DOWNLOAD`. It is still saved as `data/ref/data_reports_monthly.csv`, with contents untouched. It has the same 14 columns as SPEC §3.2 lists, except that the first header is **`Year/Month`** (not `Month/Year`); `ref_indicators` keeps that name. On 24 Oct 2026 it already included 2026-08.

Reason: the nyc.gov URL in SPEC §3.2 answers HTTP 403 (Akamai "Access Denied") to non-browser clients, and the pipeline won't spoof a browser user agent. Replaces the indicators URL in SPEC §3.2.
