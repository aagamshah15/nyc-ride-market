# Validation report

Generated 2026-11-02 22:06 UTC by `make validate` (`pipeline/validate.py`). Don't edit by hand. SPEC §8 and §7.2 set the checks; the thresholds are never widened to pass.

**Status: PASS** · months checked: 2024-01 → 2026-09 (33 months)

| Check | Status | Summary |
|---|---|---|
| Tie-out | PASS | All 31 FHV - High Volume months with indicators within ±2%; reported, not gated (D27): Yellow 11 of 33 months outside ±2%, Green 1 of 33 months outside ±2%; excepted (D27): FHV - High Volume 2026-06; 2026-09 (FHV - High Volume) skipped (not yet in indicators) |
| Quality drift | PASS | All 132 month × mode rows at least 85% valid (D26); 8 more than 3 points below the mode's median (listed): yellow 2025-05 (5.83 pts), yellow 2025-06 (5.44 pts), yellow 2025-07 (5.29 pts), lyft 2025-08 (3.21 pts), yellow 2025-08 (5.92 pts) and 3 more |
| CBD list | PASS | core: 98.95% of both-in trips carry a fee, pass-through 3.28%; wide (reported, not gated): 96.12% of both-in trips carry a fee (below 98%), pass-through 1.30% (2025-02 → 2026-09) |
| Schema | PASS | 99 files, no unmapped, missing or mistyped columns |
| Fees | PASS | uber 100.00%, lyft 100.00%, yellow 100.00%, green 100.00% of trips with a CBD fee carry the configured fee (at least 95%) |

## Tie-out

**PASS**: All 31 FHV - High Volume months with indicators within ±2%; reported, not gated (D27): Yellow 11 of 33 months outside ±2%, Green 1 of 33 months outside ±2%; excepted (D27): FHV - High Volume 2026-06; 2026-09 (FHV - High Volume) skipped (not yet in indicators)

Pipeline trips per day against TLC's "Trips Per Day" in `ref_indicators`; a row passes within ±2%. Only FHV - High Volume (uber + lyft + other_hv) gates the check (D27). Yellow and Green rows carry their own pass/fail as information, reported, not gated, because TLC's cab figures follow counting rules the pipeline can't reproduce. A row listed in `tie_out_exceptions` (`config/sources.yaml`) is `excepted`: shown with its reason below, not gating.

Records are `SUM(trips_all)` from `agg_zone_hour` (every row). The records of vendors listed in `tie_out_exclude_vendors` (`config/sources.yaml`, from `agg_vendor_month`) are taken out before dividing by the days in the month (D25 mechanism, emptied by D27; now: none); every metric keeps them. A month the indicators file doesn't have yet is skipped; a month with no pipeline trips fails.

| Month | License class | Records | Excluded | Pipeline trips/day | TLC trips/day | Diff | Status |
|---|---|---:|---:|---:|---:|---:|---|
| 2024-01 | FHV - High Volume | 19,663,930 | — | 634,320.3 | 634,329.0 | -0.00% | pass |
| 2024-01 | Green | 56,551 | — | 1,824.2 | 1,824.0 | +0.01% | pass |
| 2024-01 | Yellow | 2,964,624 | — | 95,633.0 | 94,748.0 | +0.93% | pass |
| 2024-02 | FHV - High Volume | 19,359,148 | — | 667,556.8 | 667,561.0 | -0.00% | pass |
| 2024-02 | Green | 53,577 | — | 1,847.5 | 1,848.0 | -0.03% | pass |
| 2024-02 | Yellow | 3,007,526 | — | 103,707.8 | 102,732.0 | +0.95% | pass |
| 2024-03 | FHV - High Volume | 21,280,788 | — | 686,477.0 | 686,479.0 | -0.00% | pass |
| 2024-03 | Green | 57,457 | — | 1,853.5 | 1,853.0 | +0.02% | pass |
| 2024-03 | Yellow | 3,582,628 | — | 115,568.6 | 114,395.0 | +1.03% | pass |
| 2024-04 | FHV - High Volume | 19,733,038 | — | 657,767.9 | 657,766.0 | +0.00% | pass |
| 2024-04 | Green | 56,471 | — | 1,882.4 | 1,879.0 | +0.18% | pass |
| 2024-04 | Yellow | 3,514,289 | — | 117,143.0 | 115,851.0 | +1.12% | pass |
| 2024-05 | FHV - High Volume | 20,704,538 | — | 667,888.3 | 667,886.0 | +0.00% | pass |
| 2024-05 | Green | 61,003 | — | 1,967.8 | 1,946.0 | +1.12% | pass |
| 2024-05 | Yellow | 3,723,833 | — | 120,123.6 | 118,858.0 | +1.06% | pass |
| 2024-06 | FHV - High Volume | 20,123,226 | — | 670,774.2 | 670,772.0 | +0.00% | pass |
| 2024-06 | Green | 54,748 | — | 1,824.9 | 1,806.0 | +1.05% | pass |
| 2024-06 | Yellow | 3,539,193 | — | 117,973.1 | 116,804.0 | +1.00% | pass |
| 2024-07 | FHV - High Volume | 19,182,934 | — | 618,804.3 | 618,803.0 | +0.00% | pass |
| 2024-07 | Green | 51,837 | — | 1,672.2 | 1,659.0 | +0.79% | pass |
| 2024-07 | Yellow | 3,076,903 | — | 99,254.9 | 97,967.0 | +1.31% | pass |
| 2024-08 | FHV - High Volume | 19,128,392 | — | 617,044.9 | 617,043.0 | +0.00% | pass |
| 2024-08 | Green | 51,771 | — | 1,670.0 | 1,654.0 | +0.97% | pass |
| 2024-08 | Yellow | 2,979,183 | — | 96,102.7 | 94,776.0 | +1.40% | pass |
| 2024-09 | FHV - High Volume | 19,209,788 | — | 640,326.3 | 640,325.0 | +0.00% | pass |
| 2024-09 | Green | 54,440 | — | 1,814.7 | 1,794.0 | +1.15% | pass |
| 2024-09 | Yellow | 3,633,030 | — | 121,101.0 | 119,945.0 | +0.96% | pass |
| 2024-10 | FHV - High Volume | 20,028,282 | — | 646,073.6 | 646,073.0 | +0.00% | pass |
| 2024-10 | Green | 56,147 | — | 1,811.2 | 1,808.0 | +0.18% | pass |
| 2024-10 | Yellow | 3,833,771 | — | 123,670.0 | 122,351.0 | +1.08% | pass |
| 2024-11 | FHV - High Volume | 19,987,533 | — | 666,251.1 | 666,250.0 | +0.00% | pass |
| 2024-11 | Green | 52,222 | — | 1,740.7 | 1,740.0 | +0.04% | pass |
| 2024-11 | Yellow | 3,646,369 | — | 121,545.6 | 120,215.0 | +1.11% | pass |
| 2024-12 | FHV - High Volume | 21,068,851 | — | 679,640.4 | 679,640.0 | +0.00% | pass |
| 2024-12 | Green | 53,994 | — | 1,741.7 | 1,742.0 | -0.01% | pass |
| 2024-12 | Yellow | 3,668,371 | — | 118,334.5 | 117,058.0 | +1.09% | pass |
| 2025-01 | FHV - High Volume | 20,405,666 | — | 658,247.3 | 658,247.0 | +0.00% | pass |
| 2025-01 | Green | 48,326 | — | 1,558.9 | 1,558.0 | +0.06% | pass |
| 2025-01 | Yellow | 3,475,226 | — | 112,104.1 | 110,848.0 | +1.13% | pass |
| 2025-02 | FHV - High Volume | 19,339,461 | — | 690,695.0 | 690,694.0 | +0.00% | pass |
| 2025-02 | Green | 46,621 | — | 1,665.0 | 1,666.0 | -0.06% | pass |
| 2025-02 | Yellow | 3,577,543 | — | 127,769.4 | 126,465.0 | +1.03% | pass |
| 2025-03 | FHV - High Volume | 20,536,879 | — | 662,480.0 | 662,479.0 | +0.00% | pass |
| 2025-03 | Green | 51,539 | — | 1,662.5 | 1,663.0 | -0.03% | pass |
| 2025-03 | Yellow | 4,145,257 | — | 133,718.0 | 132,393.0 | +1.00% | pass |
| 2025-04 | FHV - High Volume | 19,753,983 | — | 658,466.1 | 658,465.0 | +0.00% | pass |
| 2025-04 | Green | 52,132 | — | 1,737.7 | 1,738.0 | -0.02% | pass |
| 2025-04 | Yellow | 3,970,553 | — | 132,351.8 | 130,938.0 | +1.08% | pass |
| 2025-05 | FHV - High Volume | 21,091,193 | — | 680,361.1 | 680,417.0 | -0.01% | pass |
| 2025-05 | Green | 55,399 | — | 1,787.1 | 1,787.0 | +0.00% | pass |
| 2025-05 | Yellow | 4,591,845 | — | 148,124.0 | 146,711.0 | +0.96% | pass |
| 2025-06 | FHV - High Volume | 19,868,009 | — | 662,267.0 | 662,266.0 | +0.00% | pass |
| 2025-06 | Green | 49,390 | — | 1,646.3 | 1,644.0 | +0.14% | pass |
| 2025-06 | Yellow | 4,322,960 | — | 144,098.7 | 142,540.0 | +1.09% | pass |
| 2025-07 | FHV - High Volume | 19,653,012 | — | 633,968.1 | 633,967.0 | +0.00% | pass |
| 2025-07 | Green | 48,205 | — | 1,555.0 | 1,555.0 | +0.00% | pass |
| 2025-07 | Yellow | 3,898,963 | — | 125,773.0 | 123,998.0 | +1.43% | pass |
| 2025-08 | FHV - High Volume | 19,271,461 | — | 621,660.0 | 621,659.0 | +0.00% | pass |
| 2025-08 | Green | 46,306 | — | 1,493.7 | 1,492.0 | +0.12% | pass |
| 2025-08 | Yellow | 3,574,091 | — | 115,293.3 | 113,023.0 | +2.01% | fail (reported, not gated) |
| 2025-09 | FHV - High Volume | 19,434,641 | — | 647,821.4 | 647,819.0 | +0.00% | pass |
| 2025-09 | Green | 48,893 | — | 1,629.8 | 1,628.0 | +0.11% | pass |
| 2025-09 | Yellow | 4,251,015 | — | 141,700.5 | 138,831.0 | +2.07% | fail (reported, not gated) |
| 2025-10 | FHV - High Volume | 21,308,701 | — | 687,377.5 | 687,181.0 | +0.03% | pass |
| 2025-10 | Green | 49,416 | — | 1,594.1 | 1,593.0 | +0.07% | pass |
| 2025-10 | Yellow | 4,428,699 | — | 142,861.3 | 139,510.0 | +2.40% | fail (reported, not gated) |
| 2025-11 | FHV - High Volume | 20,818,240 | — | 693,941.3 | 693,939.0 | +0.00% | pass |
| 2025-11 | Green | 46,912 | — | 1,563.7 | 1,564.0 | -0.02% | pass |
| 2025-11 | Yellow | 4,181,444 | — | 139,381.5 | 135,745.0 | +2.68% | fail (reported, not gated) |
| 2025-12 | FHV - High Volume | 22,108,438 | — | 713,175.4 | 713,174.0 | +0.00% | pass |
| 2025-12 | Green | 48,236 | — | 1,556.0 | 1,556.0 | +0.00% | pass |
| 2025-12 | Yellow | 4,305,006 | — | 138,871.2 | 135,110.0 | +2.78% | fail (reported, not gated) |
| 2026-01 | FHV - High Volume | 20,940,373 | — | 675,495.9 | 675,495.0 | +0.00% | pass |
| 2026-01 | Green | 40,272 | — | 1,299.1 | 1,299.0 | +0.01% | pass |
| 2026-01 | Yellow | 3,724,889 | — | 120,157.7 | 116,590.0 | +3.06% | fail (reported, not gated) |
| 2026-02 | FHV - High Volume | 19,875,686 | — | 709,845.9 | 709,845.0 | +0.00% | pass |
| 2026-02 | Green | 37,373 | — | 1,334.8 | 1,335.0 | -0.02% | pass |
| 2026-02 | Yellow | 3,399,866 | — | 121,423.8 | 117,837.0 | +3.04% | fail (reported, not gated) |
| 2026-03 | FHV - High Volume | 22,058,358 | — | 711,559.9 | 711,559.0 | +0.00% | pass |
| 2026-03 | Green | 44,208 | — | 1,426.1 | 1,426.0 | +0.00% | pass |
| 2026-03 | Yellow | 3,952,451 | — | 127,498.4 | 123,033.0 | +3.63% | fail (reported, not gated) |
| 2026-04 | FHV - High Volume | 20,995,953 | — | 699,865.1 | 699,863.0 | +0.00% | pass |
| 2026-04 | Green | 44,238 | — | 1,474.6 | 1,475.0 | -0.03% | pass |
| 2026-04 | Yellow | 3,831,240 | — | 127,708.0 | 122,882.0 | +3.93% | fail (reported, not gated) |
| 2026-05 | FHV - High Volume | 22,125,744 | — | 713,733.7 | 713,732.0 | +0.00% | pass |
| 2026-05 | Green | 44,921 | — | 1,449.1 | 1,478.0 | -1.96% | pass |
| 2026-05 | Yellow | 4,090,836 | — | 131,962.5 | 127,519.0 | +3.48% | fail (reported, not gated) |
| 2026-06 | FHV - High Volume | 20,775,868 | — | 692,528.9 | 707,753.0 | -2.15% | excepted |
| 2026-06 | Green | 44,163 | — | 1,472.1 | 1,467.0 | +0.35% | pass |
| 2026-06 | Yellow | 3,837,248 | — | 127,908.3 | 127,908.0 | +0.00% | pass |
| 2026-07 | FHV - High Volume | 20,921,249 | — | 674,879.0 | 674,878.0 | +0.00% | pass |
| 2026-07 | Green | 41,252 | — | 1,330.7 | 1,331.0 | -0.02% | pass |
| 2026-07 | Yellow | 3,530,109 | — | 113,874.5 | 113,873.0 | +0.00% | pass |
| 2026-08 | FHV - High Volume | 20,493,480 | — | 661,080.0 | 661,079.0 | +0.00% | pass |
| 2026-08 | Green | 40,687 | — | 1,312.5 | 1,313.0 | -0.04% | pass |
| 2026-08 | Yellow | 3,336,716 | — | 107,636.0 | 107,637.0 | -0.00% | pass |
| 2026-09 | FHV - High Volume | 20,987,681 | — | 699,589.4 |  |  | skipped |
| 2026-09 | Green | 46,676 | — | 1,555.9 | 1,486.0 | +4.70% | fail (reported, not gated) |
| 2026-09 | Yellow | 3,876,044 | — | 129,201.5 | 115,307.0 | +12.05% | fail (reported, not gated) |

Exceptions (D27):

- FHV - High Volume 2026-06: -2.15%, outside ±2%. Reason: TLC reports 707,670 trips a day, but its published file (unchanged since 17 Sep 2026) holds 20,775,868 rows, 692,529 a day.

## Quality drift

**PASS**: All 132 month × mode rows at least 85% valid (D26); 8 more than 3 points below the mode's median (listed): yellow 2025-05 (5.83 pts), yellow 2025-06 (5.44 pts), yellow 2025-07 (5.29 pts), lyft 2025-08 (3.21 pts), yellow 2025-08 (5.92 pts) and 3 more

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
| 2025-05 | 99.97% | 99.98% | 88.82% *drift −5.83 pts* | 93.26% |
| 2025-06 | 99.96% | 99.77% | 89.22% *drift −5.44 pts* | 94.53% |
| 2025-07 | 99.96% | 99.77% | 89.37% *drift −5.29 pts* | 95.36% |
| 2025-08 | 99.95% | 96.77% *drift −3.21 pts* | 88.73% *drift −5.92 pts* | 95.08% |
| 2025-09 | 99.95% | 99.98% | 90.03% *drift −4.62 pts* | 95.48% |
| 2025-10 | 99.96% | 99.46% | 88.77% *drift −5.89 pts* | 94.84% |
| 2025-11 | 99.94% | 99.98% | 86.85% *drift −7.80 pts* | 94.77% |
| 2025-12 | 99.95% | 99.47% | 93.78% | 94.39% |
| 2026-01 | 99.58% | 99.27% | 94.16% | 94.28% |
| 2026-02 | 99.94% | 99.99% | 94.18% | 93.78% |
| 2026-03 | 99.92% | 99.99% | 94.98% | 94.10% |
| 2026-04 | 99.93% | 99.66% | 95.68% | 93.79% |
| 2026-05 | 99.89% | 99.98% | 95.42% | 93.97% |
| 2026-06 | 99.90% | 99.97% | 94.83% | 93.70% |
| 2026-07 | 99.93% | 99.75% | 94.61% | 93.05% |
| 2026-08 | 99.96% | 99.97% | 94.65% | 93.05% |
| 2026-09 | 99.95% | 99.75% | 94.45% | 92.71% |
| median | 99.96% | 99.97% | 94.65% | 93.78% |

## CBD list

**PASS**: core: 98.95% of both-in trips carry a fee, pass-through 3.28%; wide (reported, not gated): 96.12% of both-in trips carry a fee (below 98%), pass-through 1.30% (2025-02 → 2026-09)

From `agg_cbd_pairs`, months 2025-02 → 2026-09. 2025-01 left out: congestion pricing began on 2025-01-05, and the table has no day grain to drop the trips before it. Both-in: pickup and drop-off zones both in the list; passes when at least 98% carry a fee (`cbd_fee > 0`). Only the core list gates the check (D21); the other list's result is reported, since its borderline zones lie mostly outside the charge zone. Pass-through: neither zone in the list; reported, not failed. Zone lists from `pipeline.zones.cbd_zone_ids`: core 38 zones, wide 47 zones.

| Zone list | Both-in trips | With fee | Share | Pass-through trips | With fee | Share | Status |
|---|---:|---:|---:|---:|---:|---:|---|
| core | 87,485,698 | 86,566,830 | 98.95% | 304,736,083 | 10,003,290 | 3.28% | pass |
| wide | 111,204,281 | 106,889,528 | 96.12% | 281,945,922 | 3,673,570 | 1.30% | fail |

By mode:

| Zone list | Mode | Both-in trips | Share with fee | Pass-through trips | Share with fee |
|---|---|---:|---:|---:|---:|
| core | uber | 41,396,331 | 99.83% | 202,479,975 | 2.69% |
| core | lyft | 14,696,862 | 98.52% | 78,889,738 | 2.96% |
| core | yellow | 31,391,895 | 97.99% | 22,526,017 | 9.82% |
| core | green | 610 | 7.38% | 840,353 | 1.56% |
| wide | uber | 50,107,677 | 97.87% | 192,991,256 | 1.19% |
| wide | lyft | 18,049,640 | 96.68% | 75,173,385 | 1.31% |
| wide | yellow | 43,028,817 | 93.87% | 13,040,019 | 2.90% |
| wide | green | 18,147 | 45.92% | 741,262 | 0.84% |

Months below 98% (listed; the check is on the totals): core 2026-05 (96.76%), wide 2025-02 (96.16%), wide 2025-03 (96.06%), wide 2025-04 (96.07%), wide 2025-05 (95.95%), wide 2025-06 (96.09%), wide 2025-07 (96.38%), wide 2025-08 (96.03%), wide 2025-09 (96.10%), wide 2025-10 (96.08%), wide 2025-11 (96.19%), wide 2025-12 (95.84%), wide 2026-01 (95.83%), wide 2026-02 (96.33%), wide 2026-03 (96.50%), wide 2026-04 (96.49%), wide 2026-05 (93.79%), wide 2026-06 (95.90%), wide 2026-07 (97.05%), wide 2026-08 (97.06%), wide 2026-09 (96.72%)

## Schema

**PASS**: 99 files, no unmapped, missing or mistyped columns

Footers of 99 trip files (0 local, 99 read over HTTP, D11) checked against `config/schema_map.yaml` by `pipeline.discover`, the same check as `python -m pipeline.discover --check`.

No problems.

## Fees

**PASS**: uber 100.00%, lyft 100.00%, yellow 100.00%, green 100.00% of trips with a CBD fee carry the configured fee (at least 95%)

From `agg_fee_values`, months from 2025-01 (congestion pricing began on 2025-01-05). Of trips with `cbd_fee > 0`, the share carrying exactly the configured fee for the mode ($1.50 ride-hail, $0.75 cabs, `config/periods.yaml`); passes at 95% or more.

| Mode | Configured fee | Trips with a fee | At configured fee | Share | Status |
|---|---:|---:|---:|---:|---|
| uber | $1.50 | 104,385,855 | 104,385,855 | 100.00% | pass |
| lyft | $1.50 | 39,319,210 | 39,318,954 | 100.00% | pass |
| yellow | $0.75 | 59,140,562 | 59,140,362 | 100.00% | pass |
| green | $0.75 | 87,571 | 87,571 | 100.00% | pass |

Other values found:

| Mode | cbd_fee | Trips |
|---|---:|---:|
| lyft | 3.0 | 243 |
| lyft | 4.5 | 13 |
| yellow | 1.25 | 133 |
| yellow | 1.5 | 65 |
| yellow | 0.25 | 1 |
| yellow | 1.75 | 1 |

No single month below 95% for any mode.
