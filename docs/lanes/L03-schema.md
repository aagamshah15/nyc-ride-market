# L03 · Schema discovery and schema map

**Wave** 1 · **Phase** 1 · **Spec** §4 (intro), §8 (schema check) · **Decision** D11 · **Feeds** L06, L08

## Goal

Know every column of every file in scope, and account for each one exactly once in `config/schema_map.yaml`: mapped to a unified column or explicitly ignored.

## Owns

- `pipeline/discover.py`, `pipeline/schema_map.py` (loader + resolver), `config/schema_map.yaml`
- `reports/schema_discovery.md` (generated, committed)
- `tests/test_discover.py`, `tests/test_schema_map.py`

## Tasks

- [ ] `make discover`: DESCRIBE every `fhvhv`, `yellow` and `green` file from 2024-01 to the latest month. Use remote footer reads if D11 is agreed; otherwise local files fetched by L02 one month at a time
- [ ] Report: per dataset, a column × month matrix (name as spelled, type), highlighting additions, removals, renames, type changes and case changes
- [ ] `schema_map.yaml`: per dataset, ranges with `valid_from` / `valid_to`, each holding `{raw_column: unified_column}`, the expected type, and an `ignore:` list with a one-line reason per column (for example `dispatching_base_num`, `VendorID`, `passenger_count`)
- [ ] Resolver `resolve(dataset, month, raw_columns) -> mapping`: case-insensitive; raises `UnmappedColumnError` naming file and column for anything neither mapped nor ignored; also raises when a required source column is missing
- [ ] `python -m pipeline.discover --check`: the SPEC §8 schema check; L08 calls it

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
