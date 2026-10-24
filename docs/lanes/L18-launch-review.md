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
| | not started | |

**Blocked:** none

**Hand-off**
- Built:
- Checked:
- Known limits:
- Follow-ups:
