# L02 · Ingest

**Wave** 1 · **Phase** 1 (26 Oct – 1 Nov) · **Spec** §2, §3.1, §3.2 · **Feeds** L03, L04, L06, L17

## Goal

`make ingest MONTH=YYYY-MM` reliably downloads one month's three trip files, and `make ref` the lookup files, each with a manifest entry.

## Owns

- `pipeline/ingest.py`, `config/sources.yaml`, `tests/test_ingest.py`

## Reads

- `pipeline/common.py` paths; SPEC §3.1 URL pattern; SPEC §3.2 lookup URLs

## Tasks

- [ ] Download `fhvhv`, `yellow`, `green` to `data/raw/{dataset}/{YYYY-MM}.parquet`: stream to a `.part` file and rename when complete; retry with backoff; a clear error naming dataset and month when a month isn't posted (403/404)
- [ ] `data/manifest.json` entry per file: file, month, bytes, sha256, rows (from Parquet metadata, no full read), downloaded_at, ETag / Last-Modified; written atomically
- [ ] Skip a file that exists and matches the manifest; `--force` re-downloads
- [ ] `make ref`: zone lookup CSV, shapefile zip and indicators CSV to `data/ref/`, with manifest entries
- [ ] `--check MONTH`: HEAD all three datasets; exit 0 if all are posted, 1 if not (L17 uses this)
- [ ] `--delete-raw MONTH` for `make month`
- [ ] Never more than one month of raw files per call

## Tests

- Local HTTP server or patched session: manifest entry written; re-run is a no-op; an interrupted download leaves no file; a 404 message names dataset and month; `--check` exit codes

## Done when

- `make ingest MONTH=2024-01` and `MONTH=2026-08` succeed against the real URLs; `make ref` succeeds
- Re-run verifies sha256 against the manifest; tests green

## Not this lane

- Reading or transforming trip columns (L03, L06); the refresh workflow (L17)

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
