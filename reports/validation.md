# Validation report

Generated 2026-10-26 19:49 UTC by `make validate` (`pipeline/validate.py`). Don't edit by hand. SPEC §8 and §7.2 set the checks; the thresholds are never widened to pass.

**Status: PASS** · months checked: 2024-01 → 2026-08 (32 months)

| Check | Status | Summary |
|---|---|---|
| Tie-out | PASS | All 31 FHV - High Volume months with indicators within ±2%; reported, not gated (D27): Yellow 10 of 32 months outside ±2%, Green 19 of 32 months outside ±2%; excepted (D27): FHV - High Volume 2026-06 |
| Quality drift | PASS | All 128 month × mode rows at least 85% valid (D26); 8 more than 3 points below the mode's median (listed): yellow 2025-05 (5.92 pts), yellow 2025-06 (5.52 pts), yellow 2025-07 (5.37 pts), lyft 2025-08 (3.21 pts), yellow 2025-08 (6.01 pts) and 3 more |
| CBD list | PASS | core: 98.92% of both-in trips carry a fee, pass-through 3.28%; wide (reported, not gated): 96.09% of both-in trips carry a fee (below 98%), pass-through 1.30% (2025-02 → 2026-08) |
| Schema | PASS | 96 files, no unmapped, missing or mistyped columns |
| Fees | PASS | uber 100.00%, lyft 100.00%, yellow 100.00%, green 100.00% of trips with a CBD fee carry the configured fee (at least 95%) |

## Tie-out

**PASS**: All 31 FHV - High Volume months with indicators within ±2%; reported, not gated (D27): Yellow 10 of 32 months outside ±2%, Green 19 of 32 months outside ±2%; excepted (D27): FHV - High Volume 2026-06

Pipeline trips per day against TLC's "Trips Per Day" in `ref_indicators`; a row passes within ±2%. Only FHV - High Volume (uber + lyft + other_hv) gates the check (D27). Yellow and Green rows carry their own pass/fail as information, reported, not gated, because TLC's cab figures follow counting rules the pipeline can't reproduce. A row listed in `tie_out_exceptions` (`config/sources.yaml`) is `excepted`: shown with its reason below, not gating.

Records are `SUM(trips_all)` from `agg_zone_hour` (every row). The records of vendors listed in `tie_out_exclude_vendors` (`config/sources.yaml`, from `agg_vendor_month`) are taken out before dividing by the days in the month (D25 mechanism, emptied by D27; now: none); every metric keeps them. A month the indicators file doesn't have yet is skipped; a month with no pipeline trips fails.

| Month | License class | Records | Excluded | Pipeline trips/day | TLC trips/day | Diff | Status |
|---|---|---:|---:|---:|---:|---:|---|
| 2024-01 | FHV - High Volume | 19,663,930 | — | 634,320.3 | 634,329.0 | -0.00% | pass |
| 2024-01 | Green | 56,551 | — | 1,824.2 | 1,824.0 | +0.01% | pass |
| 2024-01 | Yellow | 2,964,624 | — | 95,633.0 | 94,742.0 | +0.94% | pass |
| 2024-02 | FHV - High Volume | 19,359,148 | — | 667,556.8 | 667,560.0 | -0.00% | pass |
| 2024-02 | Green | 53,577 | — | 1,847.5 | 1,847.0 | +0.03% | pass |
| 2024-02 | Yellow | 3,007,526 | — | 103,707.8 | 102,708.0 | +0.97% | pass |
| 2024-03 | FHV - High Volume | 21,280,788 | — | 686,477.0 | 686,479.0 | -0.00% | pass |
| 2024-03 | Green | 57,457 | — | 1,853.5 | 1,853.0 | +0.02% | pass |
| 2024-03 | Yellow | 3,582,628 | — | 115,568.6 | 114,353.0 | +1.06% | pass |
| 2024-04 | FHV - High Volume | 19,733,038 | — | 657,767.9 | 657,765.0 | +0.00% | pass |
| 2024-04 | Green | 56,471 | — | 1,882.4 | 1,879.0 | +0.18% | pass |
| 2024-04 | Yellow | 3,514,289 | — | 117,143.0 | 115,813.0 | +1.15% | pass |
| 2024-05 | FHV - High Volume | 20,704,538 | — | 667,888.3 | 667,886.0 | +0.00% | pass |
| 2024-05 | Green | 61,003 | — | 1,967.8 | 1,946.0 | +1.12% | pass |
| 2024-05 | Yellow | 3,723,833 | — | 120,123.6 | 118,819.0 | +1.10% | pass |
| 2024-06 | FHV - High Volume | 20,123,226 | — | 670,774.2 | 670,772.0 | +0.00% | pass |
| 2024-06 | Green | 54,748 | — | 1,824.9 | 1,805.0 | +1.10% | pass |
| 2024-06 | Yellow | 3,539,193 | — | 117,973.1 | 116,772.0 | +1.03% | pass |
| 2024-07 | FHV - High Volume | 19,182,934 | — | 618,804.3 | 618,802.0 | +0.00% | pass |
| 2024-07 | Green | 51,837 | — | 1,672.2 | 1,658.0 | +0.85% | pass |
| 2024-07 | Yellow | 3,076,903 | — | 99,254.9 | 97,929.0 | +1.35% | pass |
| 2024-08 | FHV - High Volume | 19,128,392 | — | 617,044.9 | 617,043.0 | +0.00% | pass |
| 2024-08 | Green | 51,771 | — | 1,670.0 | 1,653.0 | +1.03% | pass |
| 2024-08 | Yellow | 2,979,183 | — | 96,102.7 | 94,731.0 | +1.45% | pass |
| 2024-09 | FHV - High Volume | 19,209,788 | — | 640,326.3 | 640,325.0 | +0.00% | pass |
| 2024-09 | Green | 54,440 | — | 1,814.7 | 1,794.0 | +1.15% | pass |
| 2024-09 | Yellow | 3,633,030 | — | 121,101.0 | 119,900.0 | +1.00% | pass |
| 2024-10 | FHV - High Volume | 20,028,282 | — | 646,073.6 | 646,072.0 | +0.00% | pass |
| 2024-10 | Green | 56,147 | — | 1,811.2 | 1,807.0 | +0.23% | pass |
| 2024-10 | Yellow | 3,833,771 | — | 123,670.0 | 122,312.0 | +1.11% | pass |
| 2024-11 | FHV - High Volume | 19,987,533 | — | 666,251.1 | 666,250.0 | +0.00% | pass |
| 2024-11 | Green | 52,222 | — | 1,740.7 | 1,740.0 | +0.04% | pass |
| 2024-11 | Yellow | 3,646,369 | — | 121,545.6 | 120,183.0 | +1.13% | pass |
| 2024-12 | FHV - High Volume | 21,068,851 | — | 679,640.4 | 679,639.0 | +0.00% | pass |
| 2024-12 | Green | 53,994 | — | 1,741.7 | 1,701.0 | +2.40% | fail (reported, not gated) |
| 2024-12 | Yellow | 3,668,371 | — | 118,334.5 | 116,820.0 | +1.30% | pass |
| 2025-01 | FHV - High Volume | 20,405,666 | — | 658,247.3 | 658,246.0 | +0.00% | pass |
| 2025-01 | Green | 48,326 | — | 1,558.9 | 1,523.0 | +2.36% | fail (reported, not gated) |
| 2025-01 | Yellow | 3,475,226 | — | 112,104.1 | 110,654.0 | +1.31% | pass |
| 2025-02 | FHV - High Volume | 19,339,461 | — | 690,695.0 | 690,694.0 | +0.00% | pass |
| 2025-02 | Green | 46,621 | — | 1,665.0 | 1,630.0 | +2.15% | fail (reported, not gated) |
| 2025-02 | Yellow | 3,577,543 | — | 127,769.4 | 126,270.0 | +1.19% | pass |
| 2025-03 | FHV - High Volume | 20,536,879 | — | 662,480.0 | 662,479.0 | +0.00% | pass |
| 2025-03 | Green | 51,539 | — | 1,662.5 | 1,624.0 | +2.37% | fail (reported, not gated) |
| 2025-03 | Yellow | 4,145,257 | — | 133,718.0 | 132,177.0 | +1.17% | pass |
| 2025-04 | FHV - High Volume | 19,753,983 | — | 658,466.1 | 658,465.0 | +0.00% | pass |
| 2025-04 | Green | 52,132 | — | 1,737.7 | 1,701.0 | +2.16% | fail (reported, not gated) |
| 2025-04 | Yellow | 3,970,553 | — | 132,351.8 | 130,718.0 | +1.25% | pass |
| 2025-05 | FHV - High Volume | 21,091,193 | — | 680,361.1 | 680,359.0 | +0.00% | pass |
| 2025-05 | Green | 55,399 | — | 1,787.1 | 1,745.0 | +2.41% | fail (reported, not gated) |
| 2025-05 | Yellow | 4,591,845 | — | 148,124.0 | 146,482.0 | +1.12% | pass |
| 2025-06 | FHV - High Volume | 19,868,009 | — | 662,267.0 | 662,265.0 | +0.00% | pass |
| 2025-06 | Green | 49,390 | — | 1,646.3 | 1,602.0 | +2.77% | fail (reported, not gated) |
| 2025-06 | Yellow | 4,322,960 | — | 144,098.7 | 142,320.0 | +1.25% | pass |
| 2025-07 | FHV - High Volume | 19,653,012 | — | 633,968.1 | 633,966.0 | +0.00% | pass |
| 2025-07 | Green | 48,205 | — | 1,555.0 | 1,515.0 | +2.64% | fail (reported, not gated) |
| 2025-07 | Yellow | 3,898,963 | — | 125,773.0 | 123,794.0 | +1.60% | pass |
| 2025-08 | FHV - High Volume | 19,271,461 | — | 621,660.0 | 621,658.0 | +0.00% | pass |
| 2025-08 | Green | 46,306 | — | 1,493.7 | 1,450.0 | +3.02% | fail (reported, not gated) |
| 2025-08 | Yellow | 3,574,091 | — | 115,293.3 | 112,842.0 | +2.17% | fail (reported, not gated) |
| 2025-09 | FHV - High Volume | 19,434,641 | — | 647,821.4 | 647,819.0 | +0.00% | pass |
| 2025-09 | Green | 48,893 | — | 1,629.8 | 1,589.0 | +2.57% | fail (reported, not gated) |
| 2025-09 | Yellow | 4,251,015 | — | 141,700.5 | 138,644.0 | +2.20% | fail (reported, not gated) |
| 2025-10 | FHV - High Volume | 21,308,701 | — | 687,377.5 | 687,375.0 | +0.00% | pass |
| 2025-10 | Green | 49,416 | — | 1,594.1 | 1,557.0 | +2.38% | fail (reported, not gated) |
| 2025-10 | Yellow | 4,428,699 | — | 142,861.3 | 139,316.0 | +2.54% | fail (reported, not gated) |
| 2025-11 | FHV - High Volume | 20,818,240 | — | 693,941.3 | 693,938.0 | +0.00% | pass |
| 2025-11 | Green | 46,912 | — | 1,563.7 | 1,529.0 | +2.27% | fail (reported, not gated) |
| 2025-11 | Yellow | 4,181,444 | — | 139,381.5 | 135,491.0 | +2.87% | fail (reported, not gated) |
| 2025-12 | FHV - High Volume | 22,108,438 | — | 713,175.4 | 713,174.0 | +0.00% | pass |
| 2025-12 | Green | 48,236 | — | 1,556.0 | 1,521.0 | +2.30% | fail (reported, not gated) |
| 2025-12 | Yellow | 4,305,006 | — | 138,871.2 | 134,893.0 | +2.95% | fail (reported, not gated) |
| 2026-01 | FHV - High Volume | 20,940,373 | — | 675,495.9 | 672,214.0 | +0.49% | pass |
| 2026-01 | Green | 40,272 | — | 1,299.1 | 1,271.0 | +2.21% | fail (reported, not gated) |
| 2026-01 | Yellow | 3,724,889 | — | 120,157.7 | 116,444.0 | +3.19% | fail (reported, not gated) |
| 2026-02 | FHV - High Volume | 19,875,686 | — | 709,845.9 | 709,840.0 | +0.00% | pass |
| 2026-02 | Green | 37,373 | — | 1,334.8 | 1,304.0 | +2.36% | fail (reported, not gated) |
| 2026-02 | Yellow | 3,399,866 | — | 121,423.8 | 117,694.0 | +3.17% | fail (reported, not gated) |
| 2026-03 | FHV - High Volume | 22,058,358 | — | 711,559.9 | 711,542.0 | +0.00% | pass |
| 2026-03 | Green | 44,208 | — | 1,426.1 | 1,394.0 | +2.30% | fail (reported, not gated) |
| 2026-03 | Yellow | 3,952,451 | — | 127,498.4 | 122,891.0 | +3.75% | fail (reported, not gated) |
| 2026-04 | FHV - High Volume | 20,995,953 | — | 699,865.1 | 699,863.0 | +0.00% | pass |
| 2026-04 | Green | 44,238 | — | 1,474.6 | 1,444.0 | +2.12% | fail (reported, not gated) |
| 2026-04 | Yellow | 3,831,240 | — | 127,708.0 | 122,733.0 | +4.05% | fail (reported, not gated) |
| 2026-05 | FHV - High Volume | 22,125,744 | — | 713,733.7 | 713,730.0 | +0.00% | pass |
| 2026-05 | Green | 44,921 | — | 1,449.1 | 1,449.0 | +0.00% | pass |
| 2026-05 | Yellow | 4,090,836 | — | 131,962.5 | 127,442.0 | +3.55% | fail (reported, not gated) |
| 2026-06 | FHV - High Volume | 20,775,868 | — | 692,528.9 | 707,670.0 | -2.14% | excepted |
| 2026-06 | Green | 44,163 | — | 1,472.1 | 1,439.0 | +2.30% | fail (reported, not gated) |
| 2026-06 | Yellow | 3,837,248 | — | 127,908.3 | 127,837.0 | +0.06% | pass |
| 2026-07 | FHV - High Volume | 20,921,249 | — | 674,879.0 | 674,877.0 | +0.00% | pass |
| 2026-07 | Green | 41,252 | — | 1,330.7 | 1,304.0 | +2.05% | fail (reported, not gated) |
| 2026-07 | Yellow | 3,530,109 | — | 113,874.5 | 113,811.0 | +0.06% | pass |
| 2026-08 | FHV - High Volume | 20,493,480 | — | 661,080.0 | 661,076.0 | +0.00% | pass |
| 2026-08 | Green | 40,687 | — | 1,312.5 | 1,291.0 | +1.66% | pass |
| 2026-08 | Yellow | 3,336,716 | — | 107,636.0 | 107,510.0 | +0.12% | pass |

Exceptions (D27):

- FHV - High Volume 2026-06: -2.14%, outside ±2%. Reason: TLC reports 707,670 trips a day, but its published file (unchanged since 17 Sep 2026) holds 20,775,868 rows, 692,529 a day.

## Quality drift

**PASS**: All 128 month × mode rows at least 85% valid (D26); 8 more than 3 points below the mode's median (listed): yellow 2025-05 (5.92 pts), yellow 2025-06 (5.52 pts), yellow 2025-07 (5.37 pts), lyft 2025-08 (3.21 pts), yellow 2025-08 (6.01 pts) and 3 more

`valid_rows / rows` per month × mode from `agg_quality_month`; a row fails below 85% (D26, replacing SPEC §8's 95%: green's zero-mile records and yellow's fares of $0 or less are data quality, not pipeline faults). A month more than 3 percentage points below its mode's median over the months checked is listed (marked *drift*), not failed.

| Month | uber | lyft | yellow | green |
|---|---:|---:|---:|---:|
| 2024-01 | 99.97% | 99.84% | 96.15% | 93.90% |
| 2024-02 | 99.92% | 99.98% | 95.88% | 93.74% |
| 2024-03 | 99.97% | 99.98% | 95.42% | 93.79% |
| 2024-04 | 99.97% | 99.98% | 96.54% | 93.44% |
| 2024-05 | 99.97% | 99.98% | 96.50% | 93.84% |
| 2024-06 | 99.97% | 99.97% | 96.23% | 94.02% |
| 2024-07 | 99.97% | 99.97% | 96.07% | 93.18% |
| 2024-08 | 99.97% | 99.97% | 95.71% | 93.55% |
| 2024-09 | 99.96% | 99.98% | 95.41% | 93.75% |
| 2024-10 | 99.86% | 99.98% | 95.39% | 94.27% |
| 2024-11 | 99.96% | 99.99% | 95.74% | 93.63% |
| 2024-12 | 99.96% | 99.38% | 95.40% | 93.36% |
| 2025-01 | 99.95% | 99.71% | 93.13% | 93.26% |
| 2025-02 | 99.97% | 99.99% | 92.03% | 93.10% |
| 2025-03 | 99.97% | 98.94% | 91.98% | 92.88% |
| 2025-04 | 99.97% | 99.73% | 92.14% | 92.63% |
| 2025-05 | 99.97% | 99.98% | 88.82% *drift −5.92 pts* | 93.26% |
| 2025-06 | 99.96% | 99.77% | 89.22% *drift −5.52 pts* | 94.53% |
| 2025-07 | 99.96% | 99.77% | 89.37% *drift −5.37 pts* | 95.36% |
| 2025-08 | 99.95% | 96.77% *drift −3.21 pts* | 88.73% *drift −6.01 pts* | 95.08% |
| 2025-09 | 99.95% | 99.98% | 90.03% *drift −4.71 pts* | 95.48% |
| 2025-10 | 99.96% | 99.46% | 88.77% *drift −5.97 pts* | 94.84% |
| 2025-11 | 99.94% | 99.98% | 86.85% *drift −7.89 pts* | 94.77% |
| 2025-12 | 99.95% | 99.47% | 93.78% | 94.39% |
| 2026-01 | 99.58% | 99.27% | 94.16% | 94.28% |
| 2026-02 | 99.94% | 99.99% | 94.18% | 93.78% |
| 2026-03 | 99.92% | 99.99% | 94.98% | 94.10% |
| 2026-04 | 99.93% | 99.66% | 95.68% | 93.79% |
| 2026-05 | 99.89% | 99.98% | 95.42% | 93.97% |
| 2026-06 | 99.90% | 99.97% | 94.83% | 93.70% |
| 2026-07 | 99.93% | 99.75% | 94.61% | 93.05% |
| 2026-08 | 99.96% | 99.97% | 94.65% | 93.05% |
| median | 99.96% | 99.97% | 94.74% | 93.79% |

## CBD list

**PASS**: core: 98.92% of both-in trips carry a fee, pass-through 3.28%; wide (reported, not gated): 96.09% of both-in trips carry a fee (below 98%), pass-through 1.30% (2025-02 → 2026-08)

From `agg_cbd_pairs`, months 2025-02 → 2026-08. 2025-01 left out: congestion pricing began on 2025-01-05, and the table has no day grain to drop the trips before it. Both-in: pickup and drop-off zones both in the list; passes when at least 98% carry a fee (`cbd_fee > 0`). Only the core list gates the check (D21); the other list's result is reported, since its borderline zones lie mostly outside the charge zone. Pass-through: neither zone in the list; reported, not failed. Zone lists from `pipeline.zones.cbd_zone_ids`: core 38 zones, wide 47 zones.

| Zone list | Both-in trips | With fee | Share | Pass-through trips | With fee | Share | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| core | 83,098,705 | 82,197,406 | 98.92% | 289,345,788 | 9,496,628 | 3.28% | pass |
| wide | 105,662,544 | 101,529,349 | 96.09% | 267,716,579 | 3,483,996 | 1.30% | fail |

By mode:

| Zone list | Mode | Both-in trips | Share with fee | Pass-through trips | Share with fee |
|---|---|---:|---:|---:|---:|
| core | uber | 39,093,412 | 99.83% | 192,259,274 | 2.68% |
| core | lyft | 14,109,185 | 98.50% | 74,809,893 | 2.99% |
| core | yellow | 29,895,561 | 97.92% | 21,477,858 | 9.73% |
| core | green | 547 | 7.13% | 798,763 | 1.53% |
| wide | uber | 47,335,737 | 97.86% | 183,278,370 | 1.19% |
| wide | lyft | 17,337,235 | 96.67% | 71,259,073 | 1.32% |
| wide | yellow | 40,972,253 | 93.82% | 12,474,785 | 2.84% |
| wide | green | 17,319 | 46.08% | 704,351 | 0.81% |

Months below 98% (listed; the check is on the totals): core 2026-05 (96.76%), wide 2025-02 (96.16%), wide 2025-03 (96.06%), wide 2025-04 (96.07%), wide 2025-05 (95.95%), wide 2025-06 (96.09%), wide 2025-07 (96.38%), wide 2025-08 (96.03%), wide 2025-09 (96.10%), wide 2025-10 (96.08%), wide 2025-11 (96.19%), wide 2025-12 (95.84%), wide 2026-01 (95.83%), wide 2026-02 (96.33%), wide 2026-03 (96.50%), wide 2026-04 (96.49%), wide 2026-05 (93.79%), wide 2026-06 (95.90%), wide 2026-07 (97.05%), wide 2026-08 (97.06%)

## Schema

**PASS**: 96 files, no unmapped, missing or mistyped columns

Footers of 96 trip files (0 local, 96 read over HTTP, D11) checked against `config/schema_map.yaml` by `pipeline.discover`, the same check as `python -m pipeline.discover --check`.

No problems.

## Fees

**PASS**: uber 100.00%, lyft 100.00%, yellow 100.00%, green 100.00% of trips with a CBD fee carry the configured fee (at least 95%)

From `agg_fee_values`, months from 2025-01 (congestion pricing began on 2025-01-05). Of trips with `cbd_fee > 0`, the share carrying exactly the configured fee for the mode ($1.50 ride-hail, $0.75 cabs, `config/periods.yaml`); passes at 95% or more.

| Mode | Configured fee | Trips with a fee | At configured fee | Share | Status |
|---|---:|---:|---:|---:|---|
| uber | $1.50 | 98,955,408 | 98,955,408 | 100.00% | pass |
| lyft | $1.50 | 37,745,537 | 37,745,289 | 100.00% | pass |
| yellow | $0.75 | 56,219,671 | 56,219,471 | 100.00% | pass |
| green | $0.75 | 82,507 | 82,507 | 100.00% | pass |

Other values found:

| Mode | cbd_fee | Trips |
|---|---:|---:|
| lyft | 3.0 | 235 |
| lyft | 4.5 | 13 |
| yellow | 1.25 | 133 |
| yellow | 1.5 | 65 |
| yellow | 0.25 | 1 |
| yellow | 1.75 | 1 |

No single month below 95% for any mode.
