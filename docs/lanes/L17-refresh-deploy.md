# L17 · Refresh and deploy

**Wave** 4 · **Phase** 5 definition of done · **Spec** §10, D6 · **Decision** D14 · **Repo** https://github.com/aagamshah15/nyc-ride-market (public) · **Pages** https://aagamshah15.github.io/nyc-ride-market/, source "GitHub Actions", `github-pages` environment deploys from `main` only

## Goal

A workflow that each Monday notices a new TLC month, processes, validates, publishes and deploys it, or stops and opens an issue.

## Owns

- `.github/workflows/refresh.yml`
- `pipeline/release.py`: pack and unpack `aggregates.tar.zst`; upload and download the Release asset with `gh`
- `scripts/deploy_guard.py`: refuses `MOCK` or unvalidated data
- `tests/test_release.py`, `reports/runner_check.md`

## Tasks

- [x] SPEC §10 steps 1–5. The next expected month comes from the restored aggregates; the HEAD check is `python -m pipeline.ingest --check`
- [x] On a validation failure: open an issue containing `reports/validation.md`, and don't deploy
- [x] Commit `site/src/data/` under a bot identity; deploy with the GitHub Pages actions; upload the new aggregates as a Release asset
- [x] Declare `permissions:` in `refresh.yml` (`contents: write`, `pages: write`, `id-token: write`, `issues: write`); the repo's default workflow token is read-only, and that default stays
- [ ] Until the first deploy, Pages still serves the old "Deploy from a branch" build (the repo's markdown); the first Actions deploy replaces it _(at G6)_
- [ ] Measure one real `make month` on a hosted runner (disk, memory, time) in `reports/runner_check.md`; document the local fallback _(plan and fallback written; numbers at G6)_
- [x] Proposal, needs integrator approval: flag TLC revisions by comparing the last three months' size and ETag with the manifest _(in the hand-off)_

## Tests

- Pack/unpack round trip; deploy guard rejects `MOCK` and `validated: false`

## Done when

- One `workflow_dispatch` run completes end to end (needed for G6). Steps 1–4 can be tried on a test branch, but the deploy step must run from `main`, the only branch the `github-pages` environment allows
- The failure path ran once: a forced validation failure opened an issue and nothing deployed

## Not this lane

- Pipeline logic; CI for tests (`ci.yml` belongs to L00)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 1 Nov 2026 | **G6 done** | Integrator, with the user's go-ahead: `actionlint` clean, Release `data-2026-08` seeded. Run 1 failed in the restore step (fixed `472bb5a`: `.venv/bin` on PATH). Run 2 failed validation on NYC Open Data's new `Year/Month` format, opening issue #1; fixed in `7d874bb`. [Run 3](https://github.com/aagamshah15/nyc-ride-market/actions/runs/41362907480) passed end to end: bot commit `cc76515`, site deployed, Release refreshed. The [failure drill](https://github.com/aagamshah15/nyc-ride-market/actions/runs/41363445673) opened issue #2, skipped deploy and release, and made no commit. Schedule enabled. `reports/runner_check.md` filled in |
| 1 Nov 2026 | built, waiting for G6 | `refresh.yml`, `release.py`, `deploy_guard.py`, 42 tests and the runner-check plan written. `make test` passes. Nothing has run against GitHub; the hand-off lists the G6 steps |
| 31 Oct 2026 | started | Worktree `l17-refresh-cce526` |

**Blocked:** none for the code. G6 needs the user (steps below).

**Hand-off**

- **Built:**
  - **`.github/workflows/refresh.yml`.** Its only active trigger is `workflow_dispatch`. The Monday 14:00 UTC `schedule` is in the file, commented out. Four jobs:
    - **`check`** restores the newest `data-YYYY-MM` Release, takes `next-month` from the restored aggregates and runs `python -m pipeline.ingest --check`. Exit 1 (not posted) ends the run green with a notice. Exit 4 (the check failed) fails it.
    - **`refresh`** restores the same tag, then runs `make ref`, `make zones`, `make month`, `make validate`, `make publish`, `make test` and `scripts/deploy_guard.py`. On `main`, it then commits `site/src/data/` and `reports/validation.md` as `github-actions[bot]`, uploads the Pages artifact and packs the aggregates.
    - **`deploy`** runs `actions/deploy-pages` in the `github-pages` environment.
    - **`release`** runs last and uploads `aggregates.tar.zst` to Release `data-YYYY-MM`, so a month only counts as done once it's live. If any earlier step fails, the next run redoes the month (`make month` is idempotent).
  - **Failure path:** if `make validate` fails, the run opens an issue "Refresh YYYY-MM: validation failed" whose body is `reports/validation.md`, or comments on an open issue with that title. It also keeps the report as a run artifact. Nothing is committed, deployed or uploaded.
  - **Permissions:** the workflow default is `contents: read`. Each job asks only for what it uses: `refresh` gets `contents: write` and `issues: write`, `deploy` gets `pages: write` and `id-token: write`, and `release` gets `contents: write`. The repo default stays read-only.
  - **Inputs:**
    - `month` reprocesses a given month. It's used for the G6 run, because 2026-09 isn't posted yet.
    - `drill_validation_failure` treats a passing validation as failed, for the failure drill.
    - `redeploy_only` skips `make month` and validates, publishes and deploys the newest Release. It's for the local fallback and for site changes on `main`, which nothing else deploys.
  - **Off `main`:** on any other branch the run stops after the deploy guard. That's how steps 1–4 can be tried on a test branch.
  - **`pipeline/release.py`:**
    - `pack` and `unpack` handle `aggregates.tar.zst`. It holds every file in `data/agg/` plus `data/manifest.json` and a `release.json` index (latest month, plus bytes and sha256 for each file). Compression goes through the `zstd` command.
    - `pack` refuses an incomplete set of `aggregate.TABLES`.
    - `unpack` checks every member's name and sha256 before anything lands in `data/`. It won't overwrite existing aggregates without `--force`.
    - `upload` creates Release `data-<latest month>` or replaces its asset. `download` takes the newest `data-*` tag (drafts and other tags are ignored) and checks that the tag matches the archive's month.
    - `latest-month` and `next-month` read `agg_zone_hour`.
    - Every GitHub call goes through one `gh()` function.
  - **`scripts/deploy_guard.py`** refuses data that is `MOCK`, `validated` not `true`, a malformed `as_of_month`, mixed months, a missing `home.json`, or (with `--month`) the wrong month.
  - **`tests/test_release.py`** has 42 tests:
    - a pack/unpack round trip
    - tampered, unlisted, path-escaping and non-archive members are refused
    - year rollover in `next-month`
    - Release steps with `gh` replaced by a fake, plus two tests that put a fake `gh` script first on `PATH`
    - guard tests
    - the committed `site/src/data/` passes the guard
  - **`reports/runner_check.md`:** the measurement plan, a results table left blank for G6, and the local fallback.
- **Checked:**
  - `make test` passes.
  - Pack and unpack ran on a copy of the real 32-month aggregates in a scratch folder: 13 files, a 193 MB archive, under a second each way, byte-identical after the round trip. `next-month` gave 2026-09.
  - The guard passes the committed site data (277 files, 2026-08) and refuses `--month 2026-09`.
  - **actionlint wasn't run.** It isn't installed, and installing it was blocked: the `actionlint-py` package fetches the binary from GitHub. In its place, a scratch script parsed the workflow and checked it:
    - triggers are `workflow_dispatch` only
    - job and step keys are known ones, and permission values are valid
    - every `steps.*`, `needs.*.outputs.*` and `inputs.*` reference resolves
    - no `${{ }}` inside `run:` (inputs pass through `env`)
    - `bash -n` passes on all 29 steps
  - No `gh` call against the repo, no workflow run, Release, tag, push, deploy or issue.
- **Known limits:**
  - **Action versions:** `upload-artifact`, `download-artifact`, `upload-pages-artifact` and `deploy-pages` are pinned at `@v4`, and their versions weren't checked against the latest releases. actionlint flags any whose runtime is too old.
  - **The site-data commit isn't re-tested by CI.** `github-actions[bot]` pushes it with `GITHUB_TOKEN`, so `ci.yml` doesn't run on it; `refresh` runs `make test` before committing instead. If `main` has a ruleset that blocks direct pushes, the commit step fails.
  - Each refresh adds a commit to `main`, so pull before merging lanes.
  - **`config/sources.yaml` `months.to` stays 2026-08.** `make validate` checks scope ∪ aggregates, so new months are still gated, but `make discover`'s scope doesn't grow. Bumping it is the integrator's call.
  - **CloudFront rate limit:** `make validate`'s schema check reads about 100 Parquet footers over HTTP on every run (L08 design, D11). Together with the HEADs and downloads, a run makes roughly 300 requests to CloudFront, near the limit L03 inferred (about 300 per 5 minutes). `discover.py` paces and backs off.
  - **Only a validation failure opens an issue.** Any other failure (say an unmapped column in `make month`, SPEC §10) fails the run, and GitHub emails the actor. For the schedule, that's whoever last edited the cron line.
  - **Release upload failure:** if the upload fails after a deploy, use "Re-run failed jobs" (the aggregates artifact is kept 7 days). Otherwise the next run reprocesses the month.
  - **Zone map:** `make zones` rebuilds it on the runner with the pinned mapshaper. If the output ever differs from the committed `taxi_zones.geojson`, the site-data commit will include it.
- **What the user does at G6** (in order):
  1. Merge L17 into `main` (integrator).
  2. Lint: `brew install actionlint`, then `actionlint .github/workflows/refresh.yml`. Fix anything it flags. That includes `@v4` pins it reports as outdated: bump them to the current major.
  3. Check that nothing stops `github-actions[bot]` from pushing to `main` (Settings → Rules / Branches). Leave Settings → Actions → "Workflow permissions" read-only.
  4. Seed the first Release from the local back-fill. Run `make validate` first if `data/agg/validation_summary.json` might be stale. You need `zstd` on `PATH` and `gh auth status` logged in.
     ```bash
     python -m pipeline.release pack
     python -m pipeline.release upload
     ```
     This creates Release `data-2026-08` with `aggregates.tar.zst` (about 193 MB) at `main`'s head.
  5. **End-to-end run.** Go to Actions → refresh → Run workflow, on `main`, with `month: 2026-08` (2026-09 is due about two months after it ends). Expect all four jobs green, then check:
     - a "Refresh site data through 2026-08" commit by `github-actions[bot]` on `main`
     - https://aagamshah15.github.io/nyc-ride-market/ serves the site, replacing the old branch build
     - Release `data-2026-08` has a fresh asset
     - fill `reports/runner_check.md` from the job summary ("Runner check")
  6. **Failure drill.** Run workflow on `main` with `month: 2026-08` and `drill_validation_failure: true`. Expect:
     - issue "[drill] Refresh 2026-08: validation failed", carrying the report
     - `deploy` and `release` skipped
     - no new commit

     Close the issue afterwards.
  7. Enable the schedule: uncomment the three `schedule:` lines in `refresh.yml` and commit to `main`.
  8. Record steps 5 and 6 (run links) in this status log, or have the integrator do it, and tick SPEC §11 Phase 5's "refresh workflow ran once end-to-end".
- **Follow-ups:**
  - **Proposal, needs integrator approval: flag TLC revisions.** TLC may revise recent months (CLAUDE.md), and D27's 2026-06 exception depends on it.
    - **What it does:** the check job already restores `data/manifest.json` with the aggregates. After that, it would HEAD the three trip files of each of the last three months in the aggregates (9 requests) and compare `Content-Length` and `ETag` with the manifest's `bytes` and `etag` for `raw/{dataset}/{YYYY-MM}.parquet`.
    - **On a difference:** the run opens or comments on an issue "TLC revised YYYY-MM", listing the old and new size, ETag and `Last-Modified`. It reprocesses nothing by itself, because a revision changes figures already published. The user decides, then dispatches refresh with `month: YYYY-MM`, which downloads again, rewrites that month's rows, validates, publishes and deploys. They also review D27's 2026-06 exception if 2026-06 changed.
    - **Where:** a `--revisions N` option in `pipeline/ingest.py` (L02's module). It would reuse `check_month`'s HEAD-with-retries and `load_manifest`, and exit 0 when unchanged, 5 when revised, 4 when the check failed. Then one step in `refresh.yml`'s check job (L17).
    - **Caveat:** TLC's multipart ETags (`…-30`) change if a file is re-uploaded with the same bytes. Same size with a new ETag should read "possibly revised".
  - **Optional:** a deploy on push to `main` for site-only changes. `redeploy_only` covers it by hand for now.
