# L18 · Launch review (fresh eyes)

**Wave** 5 · **Phase** 5 (7 – 14 Dec) · **Run by** an agent that built none of the pages · **Spec** §9, §11 (phase 5), CLAUDE.md

## Goal

Check every page against its data and the project rules before v1 goes live. Report problems; don't fix them.

## Owns

- `reports/launch_review.md` only

## Checklist

- [ ] Each title and subtitle finding matches its chart and the JSON value behind it
- [ ] No digits in page markdown prose; no hex or rgb colours anywhere in `site/src` outside `palette.js`
- [ ] Language: no "caused"; pay per hour says "with a passenger"; taxi tips say "card-only"; congestion results say "estimated effect"
- [ ] Every chart has a subtitle, units and a source caption; no pies, 3D, dual axes or "Average" labels
- [ ] No logos or wordmarks; the footer is on every page
- [ ] Light and dark modes; colour-blindness simulation of the mode colours and both map scales
- [ ] Phone layout at 375 px, one column below 640 px (screenshots from the built-in browser)
- [ ] Every `/methods#…` link resolves; methods covers SPEC §12 limits and §7.3
- [ ] Published data has no `MOCK` and has `validated: true`; budgets pass
- [ ] Spot-check ten zone pages, including thin zones, the airports (1, 132, 138) and a congestion-zone zone

## Output

- Numbered findings, each with page, evidence (screenshot or value), owning lane and severity
- The integrator routes fixes; re-check until every finding is closed or accepted by the user

---

## Status log

_Only this lane writes here. Newest first._

| Date | State | Note |
|---|---|---|
| 1 Nov 2026 | review done | `reports/launch_review.md` on `main` at `83f2488`: 0 blockers, 10 should-fix, 17 nits. The integrator routes the fixes; re-check when they land |

**Blocked:** none

**Hand-off**
- Built: `reports/launch_review.md`, with 27 numbered findings (route, evidence, owner, severity), a summary table and the checklist. Results: 7 items pass, 3 fail (subtitle vs chart, dark mode, zone spot-check).
- Checked:
  - **Built site:** real 2026-08 data, served from `site/dist`.
  - **Light mode at 1280 px:** all 10 top-level routes.
  - **Dark mode:** 6 routes and zones.
  - **375 px:** 8 routes plus zone 132.
  - **Ten zone pages:** 1, 27, 43, 105, 132, 138, 161, 199, 207, 237, plus a script over all 263 zone files.
  - **Scripted checks:** prose digits, colour literals, banned words, anchors, `validated` and `MOCK`, budget and contract tests (61 passed).
  - **Colour blindness:** Machado (2009) simulation, numeric (CIEDE2000) and as an in-page SVG filter.
- Known limits:
  - The built-in browser pane was often hidden, so pages rendered only when a screenshot forced a frame.
  - Dark mode wasn't screenshotted on `/drivers`, `/methods` or the company pages; they share components already checked in dark.
  - Only the Uber company page was checked at 375 px; the other three share its template.
- Follow-ups: the fixes routed by owner (L05: findings 1, 5, 7, 8, 17; L11: 15 findings; L12, L13, L14, L15, L16: see the report's summary). Finding 7 touches D20's colours and finding 10 touches `contracts/site/tiles.yaml`, so both go through the integrator.
