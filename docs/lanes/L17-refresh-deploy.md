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

- [ ] SPEC §10 steps 1–5. The next expected month comes from the restored aggregates; the HEAD check is `python -m pipeline.ingest --check`
- [ ] On a validation failure: open an issue containing `reports/validation.md`, and don't deploy
- [ ] Commit `site/src/data/` under a bot identity; deploy with the GitHub Pages actions; upload the new aggregates as a Release asset
- [ ] Declare `permissions:` in `refresh.yml` (`contents: write`, `pages: write`, `id-token: write`, `issues: write`); the repo's default workflow token is read-only, and that default stays
- [ ] Until the first deploy, Pages still serves the old "Deploy from a branch" build (the repo's markdown); the first Actions deploy replaces it
- [ ] Measure one real `make month` on a hosted runner (disk, memory, time) in `reports/runner_check.md`; document the local fallback
- [ ] Proposal, needs integrator approval: flag TLC revisions by comparing the last three months' size and ETag with the manifest

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
