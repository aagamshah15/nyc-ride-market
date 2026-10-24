# L09 · Metrics library

**Wave** 2 · **Phase** 2–3 · **Spec** §6 · **Feeds** L10, L11

## Goal

Every SPEC §6 metric defined once, as SQL over the aggregate tables, each with a test whose expected value was worked out by hand.

## Owns

- `sql/metrics/*.sql`, except the files `contracts/metrics.md` assigns to L10
- `pipeline/metrics.py`: registers `data/agg/*.parquet` as views, runs a named metric with parameters, returns an Arrow table; CLI `python -m pipeline.metrics <name>` and `--all`
- `tests/test_metrics_<name>.py`

## Tasks

- [ ] One file per metric listed in `contracts/metrics.md`, each with a header comment: question(s), params, grain, output columns
- [ ] Ratios of sums only; divide with `NULLIF(denominator, 0)`
- [ ] Filter modes as SPEC says (driver share: `uber`, `lyft`); taxi tip rate uses card trips only
- [ ] `trips_per_hour_worked` reads `ref_indicators` and is marked TLC-reported in its output
- [ ] Output columns match `contracts/metrics.md` exactly (tested)

## Tests

- One per metric: a factory fixture, with the expected value worked out by hand in a comment

## Done when

- `python -m pipeline.metrics --all` runs on the G2 aggregates without error
- Tests green

## Not this lane

- The congestion and pay-rise studies (L10); shaping site files or writing findings (L11)

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
