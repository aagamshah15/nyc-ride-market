# L11 · Publish and findings

**Wave** 3 · **Phase** 3–4 · **Spec** §9.2, §11 (phase 3), CLAUDE.md "Language on the site" · **Feeds** L12–L17

## Goal

`make publish` turns metric outputs into the contract files the site reads, including every title, subtitle and finding sentence, all generated from computed values and never typed.

## Owns

- `pipeline/publish.py`, `pipeline/findings.py`, `tests/test_publish.py`, `tests/test_findings.py`
- Committed output: `site/src/data/**` (real data only)

## Tasks

- [ ] Run metrics through `pipeline.metrics`; shape each file exactly to `contracts/site/`; `as_of_month` and `generated_at` on every file
- [ ] Refuse to write unless `validation_summary.json` passes. `--dev` writes locally with `"validated": false`, which deploy refuses
- [ ] Copy `taxi_zones.simplified.geojson`; zone files 1–263 each under 50 KB; thin zones produce nulls, not errors
- [ ] `findings.py`: one builder per question (Q1–Q15), plus page titles and chart subtitles. Numbers formatted per `contracts/README.md`. Language: "estimated effect"; "per hour with a passenger"; taxi tips "card-only"
- [ ] Changes vs a year earlier compare the latest month with the same month of the previous year
- [ ] Remove stale files the contract no longer lists

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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
