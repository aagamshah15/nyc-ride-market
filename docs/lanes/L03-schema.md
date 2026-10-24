# L03 · Schema discovery and schema map

**Wave** 1 · **Phase** 1 · **Spec** §4 (intro), §8 (schema check) · **Decision** D11 · **Feeds** L06, L08

## Goal

Know every column of every file in scope, and account for each one exactly once in `config/schema_map.yaml`: mapped to a unified column or explicitly ignored.

## Owns

- `pipeline/discover.py`, `pipeline/schema_map.py` (loader + resolver), `config/schema_map.yaml`
- `reports/schema_discovery.md` (generated, committed)
- `tests/test_discover.py`, `tests/test_schema_map.py`

## Tasks

- [x] `make discover`: DESCRIBE every `fhvhv`, `yellow` and `green` file from 2024-01 to the latest month. Use remote footer reads if D11 is agreed; otherwise local files fetched by L02 one month at a time
- [x] Report: per dataset, a column × month matrix (name as spelled, type), highlighting additions, removals, renames, type changes and case changes
- [x] `schema_map.yaml`: per dataset, ranges with `valid_from` / `valid_to`, each holding `{raw_column: unified_column}`, the expected type, and an `ignore:` list with a one-line reason per column (for example `dispatching_base_num`, `VendorID`, `passenger_count`)
- [x] Resolver `resolve(dataset, month, raw_columns) -> mapping`: case-insensitive; raises `UnmappedColumnError` naming file and column for anything neither mapped nor ignored; also raises when a required source column is missing
- [x] `python -m pipeline.discover --check`: the SPEC §8 schema check; L08 calls it

## Tests

- `Airport_fee` and `airport_fee` both resolve
- An unmapped column raises with file and column name
- Range selection at a boundary month
- An ignored column passes; a missing required column raises

## Done when

- The report covers 2024-01 → 2026-08 for all three datasets
- `--check` exits 0 over every file in scope
- Every unified column in SPEC §4 has a source (or SPEC's constant or NULL) for every dataset and range

## Not this lane

- Computing unified or derived columns (L06)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct 2026 | done | Discovery over all 96 files (2024-01 → 2026-08), map complete, `--check` exits 0, 43 lane tests. Not merged |

**Blocked:** none

**Hand-off**
- Built:
  - `pipeline/discover.py`. `make discover` reads each file's Parquet footer (DESCRIBE plus row count), never the whole file: the local raw file if ingest has fetched it, otherwise the remote file over `httpfs` (D11). It writes `reports/schema_discovery.md` and refuses to overwrite it if any file was unreadable. `--month` limits the run to one month and, without `--check`, prints the report instead of writing it. `--check` is the SPEC §8 check: it exits 1 on an unmapped column, a missing mapped column, a mapped column of another type, or an unreadable file, and prints one line per problem naming the file and column. Remote reads are 1 s apart, and a CloudFront rate block (HTTP 403 whose body says "Request blocked") is waited out (60, 120, then 240 s, one budget per run).
  - `config/schema_map.yaml`. Per dataset, contiguous ranges (`valid_from` / `valid_to`; the last range is open, so new months resolve against it). Each range lists every raw column once, under `columns` (`unified`, DuckDB `type`, optional `rule` for clean) or `ignore` (one-line reason). It also says how each SPEC §4 unified column with no raw column of its own is covered: `constant`, `nulls` or `derived`. Ranges: fhvhv 2024-01 → 2024-12, 2025-01 →; yellow and green 2024-01 → 2024-12, 2025-01 → 2026-05, 2026-06 →.
  - `pipeline/schema_map.py`. `load_schema_map()` checks the map on load (ranges in order with no gaps; no raw column listed twice, ignoring case; each unified column covered exactly once). `resolve(dataset, month, raw_columns, file)` returns `{raw column as spelled: unified column}` in file order, leaving out ignored columns. It raises `UnmappedColumnError` (before `MissingColumnError`, so a rename reads as the new name). `find_problems()` returns every problem, including types (`ColumnTypeError`). `select_range()` gives the whole range for clean (constants, nulls, rules). All errors subclass `SchemaError`, which has `.file`.
- Checked:
  - `make discover` over all 96 files: the report covers 2024-01 → 2026-08 for fhvhv, yellow and green, and its Check section passes.
  - `python -m pipeline.discover --check` exits 0 over all 96 files.
  - Each dataset's "Where each unified column comes from" table in the report shows a source for all 24 SPEC §4 columns in every range, and `test_every_unified_column_has_one_source_in_every_range` asserts the same.
  - Tests: `Airport_fee` / `airport_fee` / `AIRPORT_FEE`; an unmapped column names the file and column; range boundaries at 2024-12 / 2025-01 (`cbd_congestion_fee`) and 2026-05 / 2026-06 (`request_source`); an ignored column passes and is optional; a missing mapped column raises; type mismatch; columns differing only in case; 11 malformed-map cases; local footer reads; rate-block back-off and pacing (faked, no network); CLI exit codes; report content.
  - `make test` green.
- Known limits:
  - Schema changes in scope: `cbd_congestion_fee` appears in all three datasets from 2025-01; `request_source` (VARCHAR) appears in yellow and green from 2026-06. Yellow spells `Airport_fee` in every month; fhvhv spells it `airport_fee`. No type changes, removals or renames.
  - `request_source` is ignored. It isn't in the 18 Mar 2025 dictionaries, and I found no definition published. Its footer min/max run from `A` to `HV0005`, so it holds high-volume licence codes, and about 28% of 2026-08 yellow rows (and 15% of green) are non-null. It looks like the app that booked the cab (Uber or Lyft in the case of the licence codes). That bears on Q1 and Q10, but using it would change SPEC §4.
  - `--check` reads remote footers for every month without a local raw file, so it needs network access to CloudFront. A footer read costs 2 HTTP requests (HEAD plus one ranged GET; measured with DuckDB's HTTP log), so a full run is about 180 requests and takes about 2.5 minutes with pacing.
  - CloudFront rate-blocks the host's IP (HTTP 403 "Request blocked" on every URL) after bursts. An unpaced exploratory scan was blocked for under 10 minutes. The paced `make discover` run wasn't blocked. A `--check` run started right after it was blocked about 316 requests into the pair (roughly 300 per 5 minutes, inferred, not documented), and the back-off waited 60 + 120 s and finished with exit 0. So `make discover` followed by `make validate` costs a few minutes of waiting, not a failure. A missing object also returns 403, so `discover.py` tells the two apart by the response body. Ingest and refresh download from the same host and can hit the same block.
  - The types in the map are DuckDB's names for the Parquet types (`INTEGER`, `BIGINT`, ...). A DuckDB upgrade that renames a type would show up as type problems in `--check`.
- Follow-ups:
  - Integrator: decide whether to use `request_source` (yellow and green, 2026-06 onward), for example to separate app-booked cabs from street hails. This would be a SPEC §4 change and a `docs/decisions.md` entry. For now it is ignored with a reason.
  - L06: build the SELECT from `resolve()` and `select_range()` (`constant` / `nulls` / `derived`); each column's `rule` repeats SPEC §4's formulas. DuckDB matches identifiers case-insensitively, so `airport_fee` works in SQL against `Airport_fee` files.
  - L08: call `python -m pipeline.discover --check` (exit 0 / 1, problems on stderr, summary on stdout), or `discover.discover()` plus `discover.check()` in process.
  - L19 (back-fill): run `make discover` with `months.from` moved back to 2019-02, then add ranges before 2024-01. Pre-2024 files weren't read here, so their differences are unknown; `--check` will name every one.
