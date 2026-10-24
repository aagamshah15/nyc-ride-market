# L02 · Ingest

**Wave** 1 · **Phase** 1 (26 Oct – 1 Nov) · **Spec** §2, §3.1, §3.2 · **Feeds** L03, L04, L06, L17

## Goal

`make ingest MONTH=YYYY-MM` reliably downloads one month's three trip files, and `make ref` the lookup files, each with a manifest entry.

## Owns

- `pipeline/ingest.py`, `config/sources.yaml`, `tests/test_ingest.py`

## Reads

- `pipeline/common.py` paths; SPEC §3.1 URL pattern; SPEC §3.2 lookup URLs

## Tasks

- [x] Download `fhvhv`, `yellow`, `green` to `data/raw/{dataset}/{YYYY-MM}.parquet`: stream to a `.part` file and rename when complete; retry with backoff; a clear error naming dataset and month when a month isn't posted (403/404)
- [x] `data/manifest.json` entry per file: file, month, bytes, sha256, rows (from Parquet metadata, no full read), downloaded_at, ETag / Last-Modified; written atomically
- [x] Skip a file that exists and matches the manifest; `--force` re-downloads
- [x] `make ref`: zone lookup CSV, shapefile zip and indicators CSV to `data/ref/`, with manifest entries
- [x] `--check MONTH`: HEAD all three datasets; exit 0 if all are posted, 1 if not (L17 uses this)
- [x] `--delete-raw MONTH` for `make month`
- [x] Never more than one month of raw files per call

## Tests

- Local HTTP server or patched session: manifest entry written; re-run is a no-op; an interrupted download leaves no file; a 404 message names dataset and month; `--check` exit codes

## Done when

- [x] `make ingest MONTH=2024-01` and `MONTH=2026-08` succeed against the real URLs
- [x] `make ref` succeeds (indicators CSV from NYC Open Data; see the 24 Oct entry)
- [x] Re-run verifies sha256 against the manifest; tests green

## Not this lane

- Reading or transforming trip columns (L03, L06); the refresh workflow (L17)

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 24 Oct | done | The user approved switching the indicators CSV to NYC Open Data, "TLC Industry Indicators" (v6kb-cqej), `https://data.cityofnewyork.us/api/views/v6kb-cqej/rows.csv?accessType=DOWNLOAD`. It's saved unchanged as `data_reports_monthly.csv`; the URL is in `config/sources.yaml`. `make ref` passes, and a re-run verifies all three ref files by sha256. **For the integrator:** this copy's first header is `Year/Month`, not SPEC's `Month/Year`, so the contract, `tests/factories.py` and the L08 brief need that name (D19). |
| 24 Oct | blocked on one file | Ingest built and committed (c655237). Real 2024-01 and 2026-08 downloads and the sha256 re-run pass. `make ref` gets the lookup CSV and shapefile but not the indicators CSV (see Blocked). |

**Blocked:** none. The indicators source is recorded as D19 (`main` 48abda6), and the integrator renamed the column to `Year/Month` in the contract and the L08 brief.

**Hand-off**
- Built: `pipeline/ingest.py` (CLI unchanged from the stub; `STUB_LANE` removed). Downloads stream to a hidden `.{name}.*.part` file beside the target, are checked (Parquet footer, zip CRC, CSV parse) and renamed into place. Retries: 5 attempts, backoff 2/4/8/16 s, for 5xx, 429, dropped connections and short reads. A 403/404 fails at once with "`{dataset} {month}: not available, HTTP 403 from {url}`" plus a hint about the two-month lag. All three datasets are attempted before the step fails, and every failure is listed. `data/manifest.json` is `{"files": {"raw/yellow/2024-01.parquet": {file, dataset, month, url, bytes, sha256, rows, downloaded_at, etag, last_modified[, deleted_at]}}}`. It is rewritten atomically under an `fcntl` lock (`manifest.json.lock`) because worktrees share one data folder. `load_manifest()` is the reader for other lanes. `--check` exits 0 (all posted), 1 (any not posted) or 4 (the check itself failed after retries), so a network outage isn't read as "nothing new". `--delete-raw` removes the month's files and stray `.part` files, and stamps `deleted_at` on their entries; a later download clears it. `config/sources.yaml` gains a `download:` block, including an honest project user agent.
- Checked: `tests/test_ingest.py`, 17 tests against a local HTTP server. They cover the manifest fields, a no-op re-run (no GETs, same mtimes), `--force`, re-downloading a changed file, retrying a 503, a truncated download leaving no file and no `.part`, Ctrl-C cleanup, a 403 naming dataset and month, non-Parquet bodies, `--check` exit codes 0/1/4 (HEAD only), `--delete-raw`, ref files and modes. `make test` is green. Real runs into the shared data folder: 2024-01 (fhvhv 19,663,930 rows; yellow 2,964,624; green 56,551) and 2026-08 (20,493,480; 3,336,716; 40,687), about 11 s per month. A re-run verified all six files by sha256 in about 0.4 s and downloaded nothing. An independent `shasum -a 256` matches every manifest entry. `--check 2026-08` → 0; `--check 2026-09` → 1 (CloudFront 403). `make ref`: lookup CSV (265 rows), `taxi_zones.zip`, and indicators (914 rows, 63,784 bytes; Socrata serves it gzip-encoded, so the length check is skipped and the decoded size matches a plain `curl`). Indicators formats, for L08: `Year/Month` is `YYYY-MM`, 2010-01 → 2026-08. License classes: Yellow, Green, `FHV - High Volume`, and Black Car / Livery / Lux Limo. Numbers are plain, with no thousands separators or `%` signs; inapplicable cells are blank. Spot tie-out for 2026-08, trips per day × 31 vs raw rows: HV 20,493,356 vs 20,493,480; yellow 3,332,810 vs 3,336,716.
- Known limits: verifying re-hashes every file (about 1 GB per month, under a second here). "Matches the manifest" is a local check: it doesn't ask TLC whether a file was revised; that's L17's proposal. The ETag and Last-Modified needed for that are recorded. Ref files follow the same skip rule, so `make ref` won't pick up a newer indicators month unless it's run with `--force`. A hard kill (SIGKILL) can leave a hidden `.part` file; the next `--delete-raw` for that month removes it.
- Follow-ups: L17: use `python -m pipeline.ingest --ref --force` in the refresh job so the indicators CSV is current, and treat `--check` exit 4 as an error, not as "nothing to do". L06: row counts to compare against are `load_manifest()["raw/{dataset}/{month}.parquet"]["rows"]`.
