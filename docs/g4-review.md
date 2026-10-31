# G4 review: findings Q1–Q15

**Date:** 30 Oct 2026 · **Data:** G3 aggregates, 2024-01 → 2026-08, re-aggregated after D29 · **Status:** signed off by the user on 30 Oct 2026, with the four fixes below applied (L11 `7589a93`, merged as `c228b61`)

G4 (SPEC §11, phase 3) is done when the studies are written and every question Q1–Q15 has a checked finding. This review covers the 15 findings `pipeline/findings.py` wrote from the real publish (`site/src/data/`, 278 files, `validated: true`). It also covers the page titles and subtitles behind them.

## Verdict

- **13 of the 15 findings are confirmed.** For most, I recomputed the numbers straight from the aggregate tables, without going through the metric SQL; the rest were checked against L10's reports or are TLC-reported.
- **Q10 needs a fix before sign-off:** zone 1, Newark Airport, is counted as a zone where yellow cabs lead.
- **Q9 needs a wording fix.**
- **Two subtitles need wording fixes:** the home share trend and the prices borough line. None of the fixes needs a SPEC change or a decision.

## How it was checked

- **Pipeline:** `make validate` passes all five checks (re-run 30 Oct), and `pipeline.metrics --all` exits 0. Every published file matches its contract and every route fits its budget.
- **Independent recomputation** from `data/agg/*.parquet`: Q1, Q4, Q5, Q7, Q8, Q9, Q10, Q11, Q12, Q13, Q14, the home share trend and the zones table.
- **Policy findings:** Q2, Q3 and Q6 are compared with L10's reports (`reports/congestion_pricing.md`, `reports/pay_rise.md`), which their tests reproduce byte for byte.
- **TLC's numbers:** Q15 is TLC-reported (`ref_indicators`) and labelled so.
- **Language rules:** L11's tests check about 870 generated sentences:
  - every congestion result is an "estimated effect";
  - pay is "per hour with a passenger";
  - cab tips are "card-only";
  - no text says "5%" or "pay rise" (D28);
  - no WAV text gives a match rate (D29).

## Fixed before sign-off

**Q10, and zone 1 on the zones pages.** "Yellow cabs carried more pickups than any other mode in 7 zones in Aug 2026, down from 10" counts zone 1, Newark Airport, in both years.

TLC-licensed vehicles don't pick up at Newark. Its 480 pickup records in Aug 2026 (478 yellow) are junk: 88% of them end at Newark too. That's the same artifact L11 already removed from the airports page.

- **Corrected Q10:** 6 zones, down from 9. Those zones are 43 Central Park, 186 Penn Station/Madison Sq West, 236 and 237 Upper East Side North and South, 239 Upper West Side South, and 262 Yorkville East.
- **Fix (L11):** leave zone 1 out of every pickup-based count and map: Q1's zone counts, Q10, the zones-index maps, and pickup sentences on the Newark zone page.
  - Zone 1 keeps its page and its data rows (D26: pages cover 1–263).
  - Its page says pickups at Newark aren't TLC trips and shows drop-offs.

## Wording fixes (applied)

| Where | Now | Problem | Suggested |
|---|---|---|---|
| Q9 (home, airports) | "the mean fare to Manhattan was $87.96 before tip" | Blends JFK ($106.38) and LaGuardia ($75.52) | Name the airports, or give each: "$106 from JFK and $76 from LaGuardia" |
| Home `share_trend` | "Uber's share fell 1.6 pts between Jan 2024 and Aug 2026, the biggest shift of any company" | January vs August mixes seasons. It reads oddly next to the Uber page's "+2.8 pts between Aug 2025 and Aug 2026" | Same month at both ends: Aug 2024 → Aug 2026 is −1.7 pts and still the biggest shift. Uber dipped to 59.2% in Aug 2025, and one clause can say so |
| Prices `fpm_by_borough` | "Manhattan had the highest fare per mile, $6.41/mile across all modes" | This is total fares ÷ total miles over 3 months; the page headline is a median ($6.52). Read together, the "highest" borough sits below the city figure | Name the measure: "overall fare per mile (total fares ÷ total miles)" |

## Question by question

All figures are for Aug 2026 unless stated otherwise. "Recomputed" means from the aggregate tables directly.

| Q | Finding (short) | Check | Verdict |
|---|---|---|---|
| Q1 | Ride-hail 86% of trips, +1.7 pts; share rose in 231 of 257 zones | Recomputed: Uber 62.00% + Lyft 23.85% = 85.85%, against 84.19% in Aug 2025. 232 of 261 zones rose before the thin rule (under 100 trips) | ✅ after the fix: 231 of 256 zones |
| Q2 | Estimated effect −4.2% (weeks −7.4% to −0.9%); ride-hail −8.1%, yellow −7.8%, green +4.1% (0.2% of trips) | Matches L10's core-list summary | ✅ |
| Q3 | Ride-hail fare per mile +3.0%, driver share of base fare −3.7% (estimated effects) | Matches L10 | ✅ |
| Q4 | Lyft leads Uber in 1 zone, as a year earlier | Recomputed: zone 207 (Saint Michaels Cemetery/Woodside: Lyft 3,463, Uber 872). Zone 105 (3 trips) is thin | ✅ |
| Q5 | Drivers got 78% of base fares, −0.3 pts; Uber 78%, Lyft 76% | Recomputed: 77.59% (Uber 78.18%, Lyft 75.94%) against 77.89% | ✅ |
| Q6 | After the new minimum-pay rule: pay per minute with a passenger −0.9%, per mile −1.2%, base fare per mile −2.2%, net of 2024 | Matches L10's pay-rise report; D28 wording | ✅ |
| Q7 | Median $6.52/mile; most volatile: Uber from Garment District (90th percentile 5.4× the 10th) | Recomputed: the city-wide `all` p50 is $6.516. The volatility ranking uses cells with at least 5,000 trips | ✅ |
| Q8 | Median wait: Uber 4.3 min, Lyft 4.5 min; longest 9.8 min, Uber in Breezy Point | Recomputed: 261 s and 270 s; zone 27, Uber 591 s over 3,070 trips | ✅ |
| Q9 | Uber 63% of airport trips; mean fare to Manhattan $87.96; peak 2 pm | Recomputed: 63.3%. $87.96 is JFK and LaGuardia together | ✅ after the fix: "$106 from JFK and $75.52 from LaGuardia" |
| Q10 | Yellow leads in 7 zones, down from 10 | Recomputed: includes zone 1 (Newark) both years | ✅ after the fix: 6 zones, down from 9 |
| Q11 | Uber completed 43,600 WAV-requested trips, Lyft 24,400; 12% of Uber's and 6.4% of Lyft's trips ran in a WAV; unfilled requests aren't in TLC's records | Recomputed: 43,554 and 24,365; 11.95% and 6.41% | ✅ (D29) |
| Q12 | 273,000 shared-ride requests, −50.9%; 59% matched; most from LaGuardia | Recomputed: 273,197 against 556,804; 59.3%; LaGuardia 10,663, then JFK 9,909 | ✅ |
| Q13 | Tips: Uber 4.3%, Lyft 5.3% of base fare; card-only, yellow 22%, green 20% | Recomputed: 4.27%, 5.33%, 22.02%, 20.40% | ✅ |
| Q14 | $11.5M in congestion fees, +1.9%; Uber $7.2M; $246.8M since Jan 2025, Uber 60% | Recomputed: $11.533M against $11.320M; Uber $7.233M; $246.82M, Uber 60.1% | ✅ |
| Q15 | TLC-reported: 1.74 trips/hour worked, 6.4 hours a day, 85,800 drivers | From `ref_indicators`, labelled TLC-reported | ✅ |

**Other numbers checked:**
- JFK as the busiest pickup zone, 17,300 trips a day: recomputed 17,273.
- The fee shares by mode.

## Worth knowing for the pages

- **Uber's share** fell from 63.7% (Aug 2024) to 59.2% (Aug 2025), then came back to 62.0% (Aug 2026). A share chart will show the dip, and the companies page's "+2.8 pts" is the recovery.
- **Lyft's shared rides** barely exist: 2,900 requests and 4.9% matched, against Uber's 270,300 and 60%.
- **Accessible vehicles:** Uber's share of trips in one rose from 9.4% (Mar 2025) to 12.0%, while Lyft's fell from 8.4% to 6.4%.
- **Congestion zone pickups:** in the zone-change table (all 261 zones with data in both years), 19 zones lost pickups. L10's report counts 16 of 246, using zones with at least 100 pickups a day; both are right on their own terms.

## After the fixes (re-published 30 Oct 2026)

- **Zone 1:** marked thin in both years, so the existing thin rule drops it from every zone count and map. Its page title now reads "TLC vehicles dropped off 4,980 trips a day at Newark Airport in Aug 2026; pickups there aren't TLC trips", and its pickup tiles are null.
- **Q10:** 6 zones, down from 9. **Q1:** share rose in 231 of 256 zones.
- **Home share trend:** "Uber's share fell 1.7 pts between Aug 2024 and Aug 2026, the biggest shift of any company; it dipped to 59% in Aug 2025".
- **Prices:** "the highest overall fare per mile (total fares ÷ total miles)".
- **Checks:** 278 files with `validated: true` and no mock data. Every contract and route budget passes, `make test` passes (490 tests), and the site builds with the real data.
