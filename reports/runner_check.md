# Runner check: one `make month` on a GitHub-hosted runner

Lane L17 · SPEC §10 ("check the hosted runner's free disk and job time limit before relying on the job") · plan written 1 Nov 2026, **numbers to be filled in at G6**

## Why

The refresh workflow (`.github/workflows/refresh.yml`) processes a new month on `ubuntu-latest`. Before the weekly schedule is switched on, one real run has to show that a month fits the runner's disk, memory and time limit. If it doesn't, the month is processed locally (fallback below).

## What we expect, from the local run of 2026-08

| Item | Local figure | Source |
|---|---|---|
| Raw trip files | fhvhv 502.4 MB, yellow 59.0 MB, green 1.0 MB (562 MB) | `data/manifest.json` |
| Clean partitions for the month | uber 375 MB, lyft 152 MB, yellow 59 MB, green 0.8 MB (587 MB) | `du -sh data/clean/mode=*/month=2026-08` |
| Aggregates, all 32 months | 219 MB on disk; 193 MB as `aggregates.tar.zst` (13 files) | `python -m pipeline.release pack` |
| Estimated peak disk for the data | about 1.5 GB plus DuckDB spill, before `make month` deletes the raw files | sum of the above |

The published runner limits are 6 hours per job and, for `ubuntu-latest` on a public repo, 4 vCPU, 16 GB RAM and 14 GB of SSD guaranteed free. Hosted runners usually have more free disk than that, so the run records what it actually had.

## How the run measures it

The `refresh` job records these on every run and writes them to the job summary ("Runner check: make month YYYY-MM"):

- **Disk:** `df` on the workspace before `make month`, then the free space sampled every 5 seconds during it. The lowest sample gives peak use.
- **Memory and wall time:** `make month` runs under GNU `/usr/bin/time -v`, which reports "Maximum resident set size" and "Elapsed (wall clock) time". If `/usr/bin/time` is missing on the image, the step still runs, and the summary says there was no GNU time output.
- **Data sizes:** `du -sh data/*` after `make month`.
- **Step times:** from the run page (setup, restore, `make ref` and `make zones`, `make month`, `make validate`, `make publish` and `make test`, then deploy and release).

To measure without waiting for a new TLC month, dispatch the workflow on `main` with `month: 2026-08`. That reprocesses the latest month (`make month` rewrites only that month's rows) and does a full end-to-end run.

## Results (G6, 1 Nov 2026)

Run: [refresh #41362907480](https://github.com/aagamshah15/nyc-ride-market/actions/runs/41362907480) on `main` with `month: 2026-08` (commit `7d874bb`). The timings come from the step timestamps. Disk and memory are in that run's "Runner check" job summary on GitHub, which the API doesn't return; copy them into the rows marked "see summary".

| Measure | Value | Limit or threshold | OK? |
|---|---|---|---|
| Runner image | `ubuntu-latest` | `ubuntu-latest` | ✅ |
| Cores / RAM | see summary | 4 vCPU / 16 GB | |
| Free disk before `make month` | see summary | | |
| Least free disk during `make month` | see summary | ≥ 2 GB left | ✅ (the run finished) |
| Peak disk used by `make month` | see summary | | |
| Peak memory (max RSS, `make month`) | see summary (about 5.2 GB locally at G2) | ≤ 12 GB | ✅ (no OOM) |
| `make month` wall time | 40 s | | ✅ |
| `make validate` time | 1 min 39 s (most of it the remote schema check) | | ✅ |
| `make publish` + `make test` time | 59 s | | ✅ |
| Whole `refresh` job | 4 min 0 s (whole run, four jobs: 5 min 9 s) | ≤ 120 min (job limit 360) | ✅ |
| `aggregates.tar.zst` size | 193.7 MB | Release asset limit 2 GB | ✅ |

**Verdict:** fits, with wide margins. A month runs end to end in about 5 minutes on the hosted runner, so the local fallback isn't needed for routine months.

The thresholds leave headroom for months bigger than 2026-08. If a month misses one, use the fallback for that month and look again at the next run's numbers. Don't relax the workflow to make it fit.

## Fallback: process the month locally

Use this when a month doesn't fit the runner, or when the runner can't download from TLC. It needs `zstd` and an authenticated `gh` (`gh auth status`) on the laptop.

1. Make sure the local aggregates are the newest Release's. If in doubt, restore them. The `--force` flag overwrites `data/agg/` and `data/manifest.json`:
   ```bash
   python -m pipeline.release download
   python -m pipeline.release unpack --force
   ```
2. Process and validate the month. Don't continue unless the validation passes:
   ```bash
   make month MONTH=YYYY-MM
   make validate
   ```
3. Upload the new aggregates as Release `data-YYYY-MM`:
   ```bash
   python -m pipeline.release pack
   python -m pipeline.release upload
   ```
4. Dispatch **refresh** on `main` with `redeploy_only: true`. The run restores `data-YYYY-MM`, skips `make month`, validates, publishes, tests, commits `site/src/data/` and deploys, then re-uploads the asset with the new `validation_summary.json`.

Steps 1–3 replace SPEC §10 steps 2–3 on the runner. Step 4 is steps 4–5. A local `make publish` isn't needed, because the workflow publishes from the Release, so the site and the Release always match.
