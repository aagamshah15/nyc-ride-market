# Every pipeline step is a make target (SPEC §2). Owned by the integrator.
# Paths are relative: the project folder name contains spaces (D14).
# Data goes to $NYC_DATA_DIR if set, else ./data.

PYTHON ?= python3.12
PY     := .venv/bin/python
NPM    ?= npm

MONTH ?=
FROM  ?=
TO    ?=

.PHONY: help setup discover ref ingest clean aggregate month backfill validate publish \
        site-mock site-dev site-build test require-month require-range

help:
	@echo "make setup                    venv + Python and Node dependencies"
	@echo "make discover                 schema discovery → reports/schema_discovery.md"
	@echo "make ref                      download zone lookup, shapefile, indicators CSV"
	@echo "make ingest MONTH=YYYY-MM     download the three trip files for a month"
	@echo "make clean MONTH=YYYY-MM      raw → unified trips for a month"
	@echo "make aggregate MONTH=YYYY-MM  rebuild that month's aggregate rows"
	@echo "make month MONTH=YYYY-MM      ingest → clean → aggregate → delete raw"
	@echo "make backfill FROM= TO=       make month for each month, one at a time"
	@echo "make validate                 validation gate → reports/validation.md"
	@echo "make publish                  aggregates → site/src/data/"
	@echo "make site-mock                mock site data (never commit it)"
	@echo "make site-dev | site-build    Framework preview / static build"
	@echo "make test                     pytest + site build"

setup:
	$(PYTHON) -m venv .venv
	$(PY) -m pip install --quiet -e ".[dev]"
	cd site && $(NPM) ci

discover:
	$(PY) -m pipeline.discover

ref:
	$(PY) -m pipeline.ingest --ref

ingest: require-month
	$(PY) -m pipeline.ingest --month $(MONTH)

clean: require-month
	$(PY) -m pipeline.clean --month $(MONTH)

aggregate: require-month
	$(PY) -m pipeline.aggregate --month $(MONTH)

month: require-month
	$(MAKE) ingest MONTH=$(MONTH)
	$(MAKE) clean MONTH=$(MONTH)
	$(MAKE) aggregate MONTH=$(MONTH)
	$(PY) -m pipeline.ingest --delete-raw $(MONTH)

backfill: require-range
	@months="$$($(PY) -m pipeline.common months $(FROM) $(TO))" || exit 1; \
	for m in $$months; do \
		echo "== $$m =="; \
		$(MAKE) month MONTH=$$m || exit 1; \
	done

validate:
	$(PY) -m pipeline.validate

publish:
	$(PY) -m pipeline.publish

site-mock:
	$(PY) scripts/make_mock_site_data.py

site-dev:
	cd site && $(NPM) run dev

site-build:
	cd site && $(NPM) run build

test:
	$(PY) -m pytest
	$(MAKE) site-build

require-month:
	@test -n "$(MONTH)" || { echo "MONTH=YYYY-MM is required" >&2; exit 2; }

require-range:
	@test -n "$(FROM)" -a -n "$(TO)" || { echo "FROM=YYYY-MM and TO=YYYY-MM are required" >&2; exit 2; }
