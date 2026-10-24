# L05 · Site foundation

**Wave** 1 (after L01) · **Phase** 4 groundwork · **Spec** §9.1, §9.3–§9.5 · **Decision** D13 · **Feeds** L12–L16

## Goal

The Framework project, design tokens and a small component kit, so page lanes assemble pages without writing styles, colours or chart boilerplate.

## Owns

- `site/observablehq.config.js` (after the L00 seed), `site/src/style.css`
- `site/src/components/{palette,format,statTiles,charts,page}.js`
- Self-hosted Inter under `site/src/assets/`
- A component gallery page `site/src/dev/components.md`, kept out of the nav and removed or excluded before launch
- `tests/test_site_budget.py`

## Tasks

- [ ] Confirm in the pinned 1.13.4 docs: `[param]` routes, `dynamicPaths`, and `observable.params` inside `FileAttachment` template literals. Record what works in the status log
- [ ] Pin every `npm:` import to an exact version (for example `npm:@observablehq/plot@0.6.17`); otherwise Framework resolves `@latest` from the network at each build
- [ ] Config: nav; footer text exactly as SPEC §9.5; `dynamicPaths` for the four companies and zones 1–263; the `/zones` index if D13 is agreed
- [ ] `palette.js` exactly as SPEC §9.5; light and dark via `prefers-color-scheme`; the diverging interpolator
- [ ] `format.js`: counts, percentages, dollars, durations, dates as `Jan 2025`, following `contracts/README.md`
- [ ] `statTiles.js`: 3–4 tiles, value plus change vs a year earlier, tabular figures, a null state
- [ ] `charts.js`: one helper per SPEC §9.4 row (share line with labelled rules at 2025-01-05 and 2025-08-01; sequential and diverging choropleths; 24 × 7 heatmap; effect dot with p10–p90 rule; fare strip or box; 100% stacked bars). Each helper requires a subtitle, axis labels with units and a source caption, and takes colours only from `palette.js`
- [ ] `page.js`: the SPEC §9.3 template (title from JSON, stat row, chart blocks, "How we measured this" link to `/methods#anchor`)
- [ ] One column below 640 px
- [ ] Check the mode palette in a colour-blindness simulator and in dark mode; record results
- [ ] Budget test: sum each route's files from `contracts/site/pages.yaml`; fail above 1.5 MB

## Done when

- `make site-mock && make site-build` green
- The gallery shows every helper in light and dark, at 375 px and desktop width
- The budget test runs as part of `make test`

## Not this lane

- Page content (L12–L16); producing data (L11)

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
