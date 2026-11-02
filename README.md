# NYC Ride Market

An independent, public analytics site profiling New York City's ride market (Uber, Lyft, yellow and green cabs) from NYC Taxi & Limousine Commission trip records.

**Live site:** https://aagamshah15.github.io/nyc-ride-market/ ([executive summary](https://aagamshah15.github.io/nyc-ride-market/summary)) · Independent analysis of public NYC TLC data. Not affiliated with any company named.

## Why

Two policy changes reshaped getting around New York in 2025: congestion pricing for trips into Manhattan's congestion zone (5 Jan 2025) and a new minimum-pay rule for app drivers (1 Aug 2025). The answers to who lost trips, who raised prices and how much of the fare reaches drivers sit in public data. But the TLC publishes tens of millions of raw records a month, and the platforms publish little. This project turns those records into plain, checkable answers to 15 questions ([SPEC.md](SPEC.md), Appendix A).

## Who it's for

| Who | What they get |
|---|---|
| TLC and other regulators | Driver pay and the drivers' share of fares after the pay rule; wheelchair-accessible service; hours worked |
| MTA and city budget watchers | Estimated effect of congestion pricing on trips touching the zone; congestion fees charged by mode |
| Uber, Lyft and rivals | Share by zone and hour, where Lyft leads Uber, airport competition |
| Taxi fleets and medallion owners | Where yellow cabs still lead, airport share, fare comparisons |
| Driver groups | Drivers' share of the fare; pay per hour with a passenger |
| Riders and reporters | Fare per mile and minute by company, hour and borough; waits; tipping |

## How it works

- **Data:** every trip record the TLC publishes for ride-hail apps, yellow and green cabs, from Jan 2024 on, processed one month at a time.
- **Pipeline:** Python 3.12 and DuckDB SQL (`pipeline/`, `sql/`):
  - ingest, then clean (bad rows are flagged, never deleted), then aggregate;
  - 29 metrics, each defined once in `sql/metrics/`;
  - two policy studies (`reports/`).
- **Validation gate:** `make validate` must pass before anything publishes. It checks the tie-out with the TLC's monthly figures, quality drift, the congestion-zone list, the schema and the fees ([reports/validation.md](reports/validation.md)).
- **Site:** Observable Framework and Plot (`site/`), built from small published JSON files, on GitHub Pages.
- **Refresh:** a weekly GitHub Actions workflow (`.github/workflows/refresh.yml`) processes each new month when the TLC posts it. It validates, publishes and deploys the month, and flags TLC revisions of recent months.

Known limits: estimated effects, not proof of cause; only completed trips (no unfilled requests, surge or cash tips). Both are covered on the site's [methods](https://aagamshah15.github.io/nyc-ride-market/methods) and [about](https://aagamshah15.github.io/nyc-ride-market/about) pages.

## Run it

Needs Python 3.12, Node 20+ and GNU Make.

```bash
make setup                    # venv + Python and Node dependencies
make month MONTH=2026-08      # ingest → clean → aggregate one month
make validate                 # tie-out and QA gate
make publish                  # write site/src/data/
make site-dev                 # local preview
make test                     # pytest + site build
```

Pipeline data lives in `data/` (not committed). Set `NYC_DATA_DIR` to use a different folder, for example one shared by several git worktrees.

Build spec: [SPEC.md](SPEC.md) · plan and gate log: [docs/development-plan.md](docs/development-plan.md) · decisions: [docs/decisions.md](docs/decisions.md).
