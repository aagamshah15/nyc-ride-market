# CLAUDE.md

An independent, public analytics site profiling New York City's ride market (Uber, Lyft, yellow and green cabs) from NYC TLC trip records. The pipeline is Python + DuckDB; the site is Observable Framework + Plot on GitHub Pages.

**Read `SPEC.md` before any task.** It has the locked decisions, schemas, metric SQL, data contracts and phase plan. If a task conflicts with SPEC.md, stop and ask; don't silently diverge.

## Commands

- `make setup`: install everything
- `make month MONTH=2026-08`: ingest → clean → aggregate one month
- `make backfill FROM=2024-01 TO=2026-08`: run months one at a time
- `make validate`: tie-out and QA gate (must pass before publishing)
- `make publish`: write `site/src/data/`
- `make site-dev`: local preview
- `make test`: pytest + site build (run before every commit)

## Rules

**Data**
- Never commit anything under `data/`. Only `site/src/data/` (small published files) and `reports/*.md` are committed.
- Process one month of raw data at a time. Never load several months of raw trips into memory together.
- Heavy lifting happens in DuckDB SQL files under `sql/`, not in pandas loops.
- Flag bad rows; never delete them. Use the flags in SPEC §4.2.
- Raw column names are mapped only through `config/schema_map.yaml`. An unmapped column is an error, not something to guess.

**Metrics**
- Each metric is defined once, in `sql/metrics/`. Pages and `publish.py` read metric outputs; they never recompute from raw or clean trips.
- Ratios are ratios of sums (`SUM(a) / SUM(b)`), never averages of per-trip ratios.
- Every new or changed metric gets a pytest with a fixture and a hand-computed expected value.

**Validation**
- If `make validate` fails, fix the pipeline. Never widen a tolerance to make a check pass without asking.

**Site**
- No hard-coded numbers in page markdown. Findings, titles and tiles come from JSON written by `publish.py`.
- Colours come only from `site/src/components/palette.js`.
- No company logos or wordmarks. Keep the "independent analysis" footer.
- Every chart has a finding subtitle, units on axes and a source caption. No pies, 3D or dual axes, and no "Average" reference-line labels.
- Keep each page's data under 1.5 MB (`make test` enforces this).

**Language on the site**
- Congestion-pricing results are "estimated effects", never "caused".
- "Pay per hour" means per hour with a passenger; say so.
- Taxi tip figures are card-only; say so.

## Gotchas

- Ride-hail `trip_time` is in seconds; taxis have no duration column (compute it from timestamps).
- Yellow and green have no request time, so wait-time metrics are ride-hail only.
- Zones 264 and 265 are "unknown".
- `cbd_congestion_fee` exists from 2025 and is 0 or NULL before then; coalesce to 0.
- Some yellow files may spell `airport_fee` with a capital A; match columns case-insensitively.
- TLC posts data with about a two-month lag and may revise recent months.

## Working style

- Small commits, one pipeline step or one page at a time.
- When a phase's definition of done (SPEC §11) is met, say so and list what was checked.
- Record any change to a locked decision in `docs/decisions.md`.
