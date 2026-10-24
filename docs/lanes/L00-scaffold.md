# L00 · Scaffold

**Wave** 0 · **Run in** integrator space (or its own agent) · **Spec** §1, §2 · **Decision** D14 · **Unblocks** every lane

## Goal

A repo where every SPEC §2 make target exists, `make setup && make test` pass on a fresh clone, and each later lane only fills in its own module.

## Owns

Stubs and seeds pass to their owning lane once L00 merges.

- `.gitignore` (`data/`, the venv, `node_modules/`, `site/dist/`, `site/src/.observablehq/cache/`)
- `README.md` (stub), `Makefile`, `pyproject.toml`, `docs/decisions.md`
- `pipeline/__init__.py`, `pipeline/common.py`
- Stub modules with their final CLI, each exiting non-zero with "not implemented (lane LNN)": `pipeline/{ingest,discover,schema_map,zones,clean,aggregate,validate,metrics,studies,publish,release}.py`
- Seed config from SPEC §3: `config/sources.yaml`, `config/periods.yaml`, `config/airports.csv`
- `tests/conftest.py` (temp `NYC_DATA_DIR` fixture), `tests/test_smoke.py`
- `site/package.json` (`@observablehq/framework` pinned to 1.13.4, `mapshaper`), a minimal `site/observablehq.config.js` and placeholder `site/src/index.md`
- `.github/workflows/ci.yml`

## Tasks

- [ ] D14 settled; `git init`, first commit on `main`
- [ ] `pipeline/common.py`: repo root; `data_dir()` from `NYC_DATA_DIR` (default `<repo>/data`); helpers for `raw/`, `clean/`, `agg/`, `ref/`, `scratch/`; YAML/CSV config loaders; `month_range(from, to)`; a DuckDB connection factory (threads, memory limit, temp dir under the data dir)
- [ ] Makefile: every SPEC §2 target, plus `make ref` (lookup files) and `make site-mock`; `MONTH`, `FROM`, `TO` variables; `month` = ingest → clean → aggregate → delete raw; `backfill` runs months one at a time and stops at the first failure; relative paths only, since the folder name has spaces
- [ ] `pyproject.toml`: Python 3.12; exact pins for duckdb (latest 1.5.x), pyarrow, pyyaml, requests, pytest
- [ ] `make test` = pytest + `make site-build`
- [ ] `ci.yml`: on push and PR, Python 3.12 + Node 20, `make setup`, `make test`
- [ ] `docs/decisions.md`: entry format (date, decision, reason, SPEC section) and entries for the §7 decisions the user agreed
- [ ] Ask the user before adding a pointer to `docs/development-plan.md` and `docs/lanes/` in CLAUDE.md

## Tests

- `NYC_DATA_DIR` is honoured by every path helper
- `month_range("2024-11", "2025-02")` gives four months
- Every stub exits non-zero and names its lane

## Done when

- Fresh clone: `make setup && make test` green
- Every SPEC §2 target exists; unimplemented ones fail naming their lane

## Not this lane

- Any real pipeline logic

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 2026-10-23 | done | Scaffold built in the integrator space; D7–D14 recorded in `docs/decisions.md` |

**Blocked:** none

**Hand-off**
- Built: git repo on `main`; `.gitignore` (anchored `/data/` so `site/src/data/` stays tracked); `pyproject.toml` (duckdb 1.5.6, pyarrow 26.0.0, pyyaml 6.0.3, requests 2.34.2, pytest 9.1.1); `Makefile` with every SPEC §2 target plus `ref` and `site-mock`; `pipeline/common.py` (paths under `NYC_DATA_DIR`, config loaders, `parse_month` / `month_arg` / `month_range` / `months_in_scope`, `connect()`, `sql_literal()`, `not_implemented()`, `python -m pipeline.common months FROM TO`); stub modules with final CLIs, each marked `STUB_LANE`; seed `config/sources.yaml` (also holds the HV license → mode map), `periods.yaml`, `airports.csv`; `tests/conftest.py` (autouse temp `NYC_DATA_DIR`), `tests/test_smoke.py`; `site/` with Framework 1.13.4 + mapshaper 0.7.98 and `package-lock.json`; `.github/workflows/ci.yml` (Python 3.12, Node 24)
- Checked: `make setup && make test` green in the project folder (29 tests, site builds); a fresh clone passes the same; `make ingest` without `MONTH` exits 2; `make backfill` stops at the first failing month; each stub exits 3 naming its lane
- Known limits: only top-level Python packages are pinned (no lock file); `npm audit` reports 2 low-severity esbuild advisories (Windows dev server only) that need a Framework downgrade to clear, so the SPEC pin stays; Framework resolves `npm:` imports from the network at build time, so builds need network access
- Follow-ups: when a lane implements its module it deletes `STUB_LANE`, and the matching smoke test skips itself; L05 should pin `npm:` import versions in pages and components
