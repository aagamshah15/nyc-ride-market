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

## D20 · Dark-mode map ramps and other palette additions

24 Oct 2026 · SPEC §9.5 · L05, L12–L16 · **Status: accepted by the user 24 Oct 2026** (raised by L05)

`site/src/components/palette.js` keeps every SPEC §9.5 token unchanged and adds:

- **Sequential (magnitude) ramp:** Plot scheme `blues`, using its 0.12–1 range so the lightest bin stays visible on white. In dark mode the ramp is reversed, so larger values sit further from the dark surface.
- **Diverging ramp, dark mode:** `accent.dark` (`#6E9CF0`) → `muted.dark` (`#4A4F55`) → `#E07B39`, centred on 0. Light mode keeps SPEC's `#2F6FDB` → `#F2F2F2` → `#E07B39`.
- **Mode-group colours:** `ride_hail` = accent, `taxi` = yellow, `all` = the text colour.
- **`ink`:** text colour for labels drawn on top of marks (`#1B1E23` on light fills, `#FFFFFF` on dark fills).

Reason: SPEC §9.5 gives only light-mode ramps. A light-to-dark ramp drawn on a dark page would put the smallest values brightest, and SPEC's `#F2F2F2` midpoint would glare.

The colour-blindness check is recorded in L05's status log. Two mode pairs fall below the floor as lines (green vs Lyft light, other ride-hail vs Lyft dark), and yellow is 2.45:1 on white. The components compensate with fixed legend order, line-end labels, tooltips and table views; SPEC's mode colours are unchanged.

## D21 · The 98% congestion-zone check gates on the core list only

24 Oct 2026 · SPEC §7.2, §8 · L04, L08, L12 · **Status: accepted by the user 24 Oct 2026** (raised by L04)

The SPEC §7.2 check (share of trips with both ends in the list that carry `cbd_fee > 0`, at least 98%) passes or fails on the **core** list (`borderline = false`). The **wide** list's result is computed, reported in `reports/validation.md` and `validation_summary.json`, and shown on the methods page, but it doesn't fail the gate. The 98% threshold itself is unchanged.

Reason (SPEC §7.2 asks for a written one): the wide list adds nine borderline zones. Six straddle 60th St with most of their area north of it, outside the charge zone, and three are islands with no road access. So trips touching them often carry no fee, and the wide list can't reach 98% by construction (97.91% on 2026-08 HVFHV, against 99.70% for core). Its job is the "with borderline zones" sensitivity result (SPEC §7.3), not to validate the list.

## D22 · The congestion-zone check leaves out 2025-01

24 Oct 2026 · SPEC §7.2, §8 · L08 · **Status: accepted by the user 24 Oct 2026** (raised by L08)

The CBD-list check (D21) starts at 2025-02, the first month wholly under congestion pricing. The fee check (SPEC §8) still starts at the pricing start date, 2025-01-05.

Reason: pricing began on 5 Jan 2025, and `agg_cbd_pairs` has no day grain, so the 1–4 Jan trips, which carry no fee, can't be dropped. Across the scope they'd lower the both-in share by about half a point, enough to fail 98% for a reason that has nothing to do with the zone list. The report states the exclusion.

## D23 · Fee revenue sums every trip record

24 Oct 2026 · SPEC §4.2, §5, §6 (fee revenue, Q14) · L07, L09, L15 · **Status: accepted by the user 24 Oct 2026** (raised by L07)

`agg_fees_month` sums `cbd_fee`, `congestion_surcharge`, `airport_fee` and `trips_with_cbd_fee` over **all** rows, not only `is_valid` ones. This is an exception to SPEC §4.2's "metrics use `is_valid` rows". Every other money sum keeps that rule.

Reason: a fee was charged whether or not a trip's distance, duration or fare looks odd, and Q14 asks how much fee money each mode generates. Trip counts already use all rows for the same reason, so they match TLC's own figures. Using valid rows would understate fee revenue.

## D24 · A WAV or shared "match" counts only when the trip asked for it

25 Oct 2026 · SPEC §5, §6 (Q11, Q12) · L07, L09, L13 · **Status: accepted by the user 25 Oct 2026** (found at G2)

In `agg_zone_hour`, `wav_match` counts trips with `wav_request AND wav_match`, and `shared_match` counts trips with `shared_request AND shared_match`. `wav_req` and `shared_req` are unchanged, and so are SPEC §6's ratios: accessible match rate = `SUM(wav_match) / SUM(wav_req)`, shared match rate = `SUM(shared_match) / SUM(shared_req)`. Clean trips keep the raw flags as published.

Reason: in the TLC data, `wav_match_flag = Y` means the trip ran in a wheelchair-accessible vehicle, whether or not the rider asked for one. In 2025-03, 1.36 million Uber trips ran in accessible vehicles against 39,879 requests, so SPEC's ratio came out at 34.7, not a rate. Q11 and Q12 ask how often *requests* are matched, so the match has to be counted among requesting trips (2025-03: Uber 39,879 of 39,879 WAV requests, Lyft 16,612 of 16,615; Uber shared 298,194 of 570,285).

## D25 · Carry VendorID; the tie-out leaves out vendor 6

25 Oct 2026 · SPEC §4, §5, §8 · L03 (closed; integrator), L06, L07, L08 · **Status: accepted by the user 25 Oct 2026** (found at G2)

- **Clean:** the cab files' `VendorID` becomes a unified column, `vendor_id` (SMALLINT; NULL for HVFHV), mapped in `config/schema_map.yaml` and kept in clean trips.
- **Aggregate:** a QA table, `agg_vendor_month` (month × mode × vendor_id: `rows`, over all rows), records how many records each vendor sent.
- **Tie-out (SPEC §8):** compares TLC's trips per day with the pipeline's `trips_all` **minus** the records of vendors listed in `tie_out_exclude_vendors` in `config/sources.yaml` (vendor 6 for yellow and green). The excluded count is shown in the report.
- **Everything else is unchanged:** every metric, share and count keeps vendor 6's trips, and the ±2% tolerance stays.

Reason: green 2025-03 was +2.37% against TLC's indicators. The gap is exactly vendor 6's 1,222 records (Myle Technologies in TLC's 2025 dictionaries): without them the pipeline counts 50,317 trips against TLC's 50,344 (−0.05%). TLC's indicators evidently don't count that vendor, so the tie-out has to compare like with like rather than widen its tolerance. Yellow also has vendor-6 records (334 in 2025-03) and passes either way. Vendor 7's yellow records aren't excluded: they don't explain a failing gap, and the user approved vendor 6 only.

## D26 · Quality rule: zone 265 is a real place; the gate's floor is 85%

26 Oct 2026 · SPEC §4.2 (`f_zone`), §8 (quality drift) · L06, L08, L11, L12 · **Status: accepted by the user 26 Oct 2026** (from the G3 back-fill)

- **`f_zone`** is true when `pu_zone` or `do_zone` is **264** ("Unknown") or NULL. Zone **265** ("Outside of NYC" in the TLC lookup) is no longer flagged: trips to or from New Jersey, Westchester and other places outside the city are valid trips. Zone pages still cover only 1–263, so zone 265 gets no page, but it counts in city-wide metrics.
- **Quality check (SPEC §8):** a month × mode **fails below 85%** `valid_rows / rows`. A month **more than 3 points below its mode's median** is listed in the report but doesn't fail, as SPEC already had it. SPEC's flat 95% floor is replaced.

Reason: on the 32 back-filled months (2024-01 → 2026-08), the 95% floor failed 57 of 128 month × mode rows on data quality that isn't a pipeline fault. Green was below in all 32 months (zero-mile records, 4.5% on average), and yellow in 21 (fares of $0 or less, 3.2% on average, peaking in 2025-05 → 2025-11). Uber and Lyft cleared it by fractions of a point only because 4.4% of their trips touch zone 265, which SPEC had treated as unknown. With 265 valid, Uber and Lyft have a 99.96% median. Every mode-month clears 85% (lowest: yellow 2025-11), and yellow's 2025 fare episode shows up as listed drift. The evidence is the valid-share table in the integrator's G3 report; `reports/validation.md` from the next full run will carry it.
