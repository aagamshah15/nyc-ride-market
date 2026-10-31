# L12 · Pages: Home + Methods

**Wave** 4 · **Phase** 4–5 · **Spec** §9.1, §9.3, §7.3, §12 · **Data** `home.json`, `share_monthly.json`, `quality.json`

## Goal

The home page (the market at a glance and the top findings) and the methods page every other page links to.

## Owns

- `site/src/index.md`, `site/src/methods.md`

## Starts when

- L05 is done, and G4 passed (30 Oct 2026). The **real, validated site data (as of 2026-08) is committed in `site/src/data/`** (`d6841ef`). Build against it; don't run `make site-mock` (it refuses to overwrite real data) and never commit changes under `site/src/data/`. If a page needs data the files don't carry, add a Blocked note for the integrator (L11 owns the files).

## Tasks

- [x] Home: title from JSON; tiles for trips per day, ride-hail share, platform share and congestion fees last month, each with its change vs a year earlier; share-trend line with the 2025-01-05 and 2025-08-01 rules; top findings linking to their pages; a congestion-pricing slot
- [x] Methods: sources; cleaning rules and the SPEC §4.2 flag table with flag shares from `quality.json`; the CBD zone list with borderline zones and results with and without them (SPEC §7.3); validation results; congestion and pay-rise methods; tips are card-only for taxis; waits are ride-hail only; known limits (SPEC §12); downloads of the published files
- [x] Every anchor in `contracts/site/pages.yaml` exists on the methods page

## Page rules (all page lanes)

- Numbers, titles and subtitles come only from JSON; no digits in markdown prose
- Use components from `site/src/components/` only. Need a change? Add a Blocked note for the integrator
- Every chart has a finding subtitle, units on its axes, and the caption `Source: NYC TLC trip records, {as_of_month}`
- No pies, 3D, dual axes or "Average" line labels; no logos; keep the footer
- Language: "estimated effect", "per hour with a passenger", taxi tips "card-only"
- Check light, dark and 375 px before hand-off

## Done when

- Builds on mock and on real data; every anchor resolves; budget test green

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 31 Oct 2026 | done | `index.md` and `methods.md` built on the real data (as of 2026-08). `make test` green; checked in a browser at desktop and 375 px, light and dark, no console errors. Also builds and renders on mock data (scratch copy). |

**Blocked:** none. One request for the integrator (Follow-ups, first item): `/methods` reads two files that `pages.yaml` doesn't list.

**Hand-off**
- Built:
  - **Home** (`site/src/index.md`). Title and four tiles from `home.json` (trips per day, ride-hail share, platform share, congestion fees last month, each against a year earlier). Share-trend line from `share_monthly.json` with the two SPEC §9.4 rules (congestion pricing, new minimum-pay rule). The March inflation step is left off this chart because it's a pay event. Top findings are the featured ones, and the rest sit under "More findings". The congestion-pricing block has two tiles: the Q2 and Q3 estimated effects, taken from the findings' `value`. It also lists the `/congestion-pricing` findings (Q2, Q3, Q14) and links to that page and to `methods#congestion-method`. The findings lists leave those three out so nothing repeats.
  - **Methods** (`site/src/methods.md`). Front-matter `toc: true` (the site default is off). Explicit ids for every `pages.yaml` anchor, plus `sources`. Sections:
    - sources and cleaning rules;
    - the SPEC §4.2 flag table with each flag's share of records by mode for the latest month, plus a per-month table and a valid-share chart (`quality.json`);
    - the core and wide zone lists and the borderline zones with their notes. "With and without borderline zones" (SPEC §7.3, D9, D21) is shown twice: the fee check per list (`validation.cbd`) and every estimated effect per list (`congestion.json` `effects`);
    - validation: the five checks with their generated summaries, a tie-out chart and the fees table;
    - the congestion and minimum-pay-rule methods (D12, D28 wording; dates from `events.json`);
    - tips (card-only for cabs), waits (ride-hail only), known limits (SPEC §12 plus D24, D26, D27, D29) and downloads.
  - Downloads use the six files in `quality.json` `downloads`. Framework needs literal `FileAttachment` names, so the page lists those six. Nothing is fetched until a reader clicks.
- Checked:
  - `make test`: 490 passed, 13 skipped; the site build is green and validated 274 links. `tests/test_site_budget.py` passed 14 of 14, none skipped.
  - All ten `pages.yaml` anchors exist on `/methods`, and they appear in its TOC.
  - The six download links return their JSON.
  - No digits in either page's markdown prose (scripted check). The thresholds in the flag rules are written in words: three hours, a hundred miles, an hour, a hundred trips.
  - Browser: desktop and 375 px, light and dark, both pages, no console errors and no horizontal page scroll at 375 px. Wide tables scroll inside their own box, as on the companies page.
  - Mock data: `make_mock_site_data.py --out` into a scratch copy of `site/`. It builds, and both pages render with the mock banner and no errors.
- Known limits:
  - `quality.json` has no `subtitles`, so the two Methods charts use the generated validation summaries (`quality_drift`, `tie_out`) as their finding subtitles. Those sentences mention decision ids such as "(D27)".
  - On mock data, the home congestion tiles show "Not available", because the mock's Q2 and Q3 aren't `effect` findings. Real data fills them.
  - Home and Methods link to `/congestion-pricing`, `/drivers`, `/airports` and `/prices`. Those pages belong to L15 and L16, which aren't on `main` yet, so the links resolve once they merge. They're built in JS with `siteUrl`, so Framework's link check doesn't flag them.
  - In the share trend at phone width, the "New driver minimum-pay rule" label crosses the congestion-pricing rule. This is the shared `eventMarks` layout, and it stays readable.
- Follow-ups:
  - **Integrator:** add `congestion.json` and `events.json` to the `/methods` files in `contracts/site/pages.yaml`. The budget test can then measure what the page loads (about 340 KB with `quality.json`, well under budget). The build's size table already counts them, and the six download files, for `/methods`.
  - Optional (L11): a `subtitles` block in `quality.json` for the valid-share and tie-out charts, and a `rules` block if the flag thresholds should come from JSON instead of words.
