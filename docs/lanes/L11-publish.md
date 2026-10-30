# L11 · Publish and findings

**Wave** 3 · **Phase** 3–4 · **Spec** §9.2, §11 (phase 3), CLAUDE.md "Language on the site" · **Feeds** L12–L17

## Goal

`make publish` turns metric outputs into the contract files the site reads, including every title, subtitle and finding sentence, all generated from computed values and never typed.

## Owns

- `pipeline/publish.py`, `pipeline/findings.py`, `tests/test_publish.py`, `tests/test_findings.py`
- Committed output: `site/src/data/**` (real data only)

## Tasks

- [x] Run metrics through `pipeline.metrics`; shape each file exactly to `contracts/site/`; `as_of_month` and `generated_at` on every file
- [x] Refuse to write unless `validation_summary.json` passes. `--dev` writes locally with `"validated": false`, which deploy refuses
- [x] Copy `taxi_zones.simplified.geojson`; zone files 1–263 each under 50 KB; thin zones produce nulls, not errors
- [x] Write `tiles.json` from `contracts/site/tiles.yaml` and `events.json` from `config/periods.yaml` (D17)
- [x] Check every written file with `tests/contract_check.py` against `contracts/site/` in your tests
- [x] `findings.py`: one builder per question (Q1–Q15), plus page titles and chart subtitles. Numbers formatted per `contracts/README.md`. Language: "estimated effect"; "per hour with a passenger"; taxi tips "card-only"
- [x] Changes vs a year earlier compare the latest month with the same month of the previous year
- [x] Remove stale files the contract no longer lists
- [ ] D28: `events.json` has three events in date order (`congestion_pricing_start`, `driver_pay_inflation_step`, `driver_pay_rise` labelled "New driver minimum-pay rule"); Q6 text uses the rule's name and `pay_event` net of 2024, never "5%"
- [ ] D29: company `wav` rows and Q11 come from `wav_service` (completed WAV-requested trips, share of trips in a WAV); `compare` key `wav_share`; say unfulfilled requests aren't in TLC's records

## Tests

- Factory aggregates → every file matches its contract example
- Every route stays within 1.5 MB
- Three or four finding sentences checked against values worked out by hand
- Generated text never contains "caused" or "causes"; taxi tip text says card-only; pay-per-hour text says "with a passenger"

## Done when

- On validated aggregates (G3), `make publish` writes every contract file
- Q1–Q15 each has a generated finding (G4)

## Not this lane

- Metric formulas (L09, L10); page layout (L12–L16)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 27 Oct 2026 | done | Built on factory aggregates and checked with a real run on the G3 aggregates (2024-01 → 2026-08). Main merged in (D24–D27, L10's metrics). |

**Blocked:** one contract gap for the integrator; it doesn't hold up this lane.
- **`taxi_zones.example.geojson` only has Polygon features.** L04's real map has 12 MultiPolygon zones, so `assert_matches_contract` fails on the copied map (`coordinates` nest one level deeper). The map itself passes `zones.geojson_problems`. Fix in `contracts/`: add a MultiPolygon feature to the example (the checker merges items, so it would still reject Polygons), or check the geojson only down to `geometry.type`. The tests use the mock grid map, which is all Polygons.

**Hand-off**
- **Built:**
  - `pipeline/publish.py`: `Outputs` runs each metric once through `metrics.run` (L10's five included), and `Site` builds one method per file in `contracts/site/pages.yaml`. It also writes `tiles.json` (from `tiles.yaml`) and `events.json` (from `periods.yaml`), copies the zone map, and removes stale `.json`/`.geojson` files.
  - Before anything is written, `publish.py` refuses unless all of these hold:
    - `validation_summary.json` has status `pass` and lists the latest month in `months_checked`
    - the zone map passes `zones.geojson_problems`
    - every page has a title and Q1–Q15 each have a finding
    - every route fits its budget
  - `--dev` turns those failures into warnings (the zone-map check still refuses) and writes `validated: false`. `--out` picks the folder.
  - `pipeline/findings.py`: formatters that match `format.js` (tested against Node), one builder per page title, chart subtitle and question, and the language rules.
- **Checked:**
  - `tests/test_publish.py` (30) runs on a full factory set:
    - every file matches its contract example, carries the envelope and fits its budget, including a zone with five modes in all 168 hours
    - 11 findings and the home tiles match values worked out by hand
    - language rules hold over all 870+ generated sentences
    - the gate refuses a missing, failed or stale summary
    - thin and empty zones give nulls; stale files are removed
    - L10's metrics go through the runner
  - `tests/test_findings.py` (48): formats, hand-worked sentences, language rules and missing values.
  - `make test`: 474 passed, 13 skipped; the site builds.
  - Real run: `NYC_DATA_DIR=<shared data> python -m pipeline.publish` writes 278 files in under 2 seconds, `validated: true`. Every route is within budget; the largest zone file is 39.6 KB and the largest route (`/congestion-pricing`) about 685 KB. Every JSON file matches its contract; the zone map doesn't (see Blocked). **Not committed:** `site/src/data/` is left for the integrator.
- **Known limits (choices made where the contract is silent):**
  - A zone is thin with fewer than 100 trips (all rows, from `trip_share`) in the month. No metric gives per-zone valid trips; the gap is about 2%.
  - Zone `wait_p50`/`wait_p90` (zone tiles and the index) are the leading ride-hail app's percentiles, by trips that month, because percentiles can't be combined across apps. The waits subtitle names the app.
  - Zone counts (yellow leads, Lyft ahead of Uber, ride-hail share up) leave out zones that are thin in that year. `zones_lyft_ahead` on the company pages is the same count as `zones_lyft_beats_uber`.
  - `compare` row `fare_per_min` is `fare_rates.fare_per_min`, a city-wide mean (ratio of sums); `fpm_median` is the median from `fare_dist`.
  - The "varies most" sentences (prices subtitle, Q7) consider only zone × company cells with at least 5,000 trips (`VOLATILITY_MIN_TRIPS`). Smaller yellow-cab cells reach p90 ÷ p10 of 130× to 740×. The data rows keep every cell.
  - The highest-fare borough sentence considers the five boroughs only: EWR, the zone-1 pickups, comes out at $47.12/mile.
  - Q6 compares ride-hail pay per hour with a passenger (and fare per mile) in Aug 2025, the month the minimum-pay rise began, with Jul 2025. It is descriptive, not an estimate; the event-study chart carries the seasonal reference.
  - Event labels ("Congestion pricing starts", "Driver minimum pay rises 5%") are constants in `publish.py`, because `periods.yaml` has no labels.
  - Changes on a year earlier come from unrounded values; tiles are rounded per `contracts/README.md` §2 afterwards.
- **Follow-ups:**
  - Integrator: the geojson example (Blocked).
  - L14: "Outside of NYC" (zone 265, valid since D26) is the top destination of 39 zones. Its name comes straight from the TLC lookup; the page may want to say it covers every out-of-city place.
  - L06/L08 (data quality, to look at): yellow-cab cells in outer zones have p10 fare per mile near zero (Richmond Hill p90 ÷ p10 = 676 in Aug 2026). Zone 1 (Newark Airport) has 15 pickups a day, 99% yellow, at $47 a mile.
  - Real numbers to sanity-check on review (G4): Q11 is 100% for both apps (D24); Lyft leads Uber in only 1 zone; shared-ride requests fell 51% on a year earlier; pay per hour with a passenger is $63–65.
