# NYC Ride Market

An independent, public analytics site profiling New York City's ride market (Uber, Lyft, yellow and green cabs) from NYC Taxi & Limousine Commission trip records.

Independent analysis of public NYC TLC data. Not affiliated with any company named.

## Status

Under construction. v1 targets 14 Dec 2026. See [SPEC.md](SPEC.md) for the build spec and [docs/development-plan.md](docs/development-plan.md) for the plan.

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
