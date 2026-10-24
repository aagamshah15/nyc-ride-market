# NYC Ride-Hail vs Taxi: Analytics Action Plan

Oct 22, 2026 · Aagam

## Summary

Build a multi-page website that profiles New York City's for-hire ride market (Uber, Lyft, yellow and green cabs) from the city's own trip records, and answers the questions each company's marketing skips.

- **Data:** NYC Taxi & Limousine Commission (TLC) trip records, one row per trip, monthly Parquet files through August 2026. In July 2026 that was about 675,000 ride-hail trips and 114,000 yellow-cab trips a day.
- **Hook:** congestion pricing started on 5 Jan 2025 and adds $1.50 to every ride-hail trip and $0.75 to every cab trip in the zone. A federal judge kept it alive in March 2026, so it is a live natural experiment.
- **Format:** profile pages modelled on a program website's tabs (company, zone, airport, driver, policy), each opening with three or four headline stats and a finding.
- **Target:** version 1 live by mid-December 2026, then a monthly refresh as TLC posts each new month.

## Why this dataset

It captures a real market fight at trip level, with prices, pay and fees on every row, which almost no other open dataset does.

- **A lopsided, shifting market.** Ride-hail apps ran about six trips for every yellow-cab trip in July 2026 (675,000 vs 114,000 a day), on 84,000 vehicles vs 10,000 ([TLC monthly indicators](https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv)).
- **Money on every trip.** Ride-hail rows carry the rider's fare, the driver's pay, tips, tolls and each fee, so the platform's cut can be computed trip by trip ([HVFHV data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf)).
- **Policy shocks to measure.** Congestion pricing began 5 Jan 2025; officials report 27 million fewer vehicles entering the zone and 11% less traffic in year one ([6sqft, Mar 2026](https://www.6sqft.com/congestion-pricing-lives-on-after-federal-judge-rules-trumps-effort-to-end-program-unlawful/)). Driver minimum pay rose 5% on 1 Aug 2025 ([WageIndicator](https://wageindicator.org/ai/what-we-do/news-stories/nyc-ridehailing-pay-increase/)).
- **Clients who would pay for the answers.** Platform strategy teams (Uber vs Lyft share by zone), taxi fleets and medallion owners (where cabs still win), the TLC and MTA (who bears the fee, whether pay rules work), and driver groups (what share of the fare reaches drivers).

NYC taxi data is a common portfolio dataset, but most projects stop at yellow-cab trip counts. The ride-hail money fields, the congestion-pricing break and zone-level profiles are where this one differs.

## Data sources

The core is the TLC's trip-level Parquet files, posted monthly with about a two-month lag ([TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page)). Everything else is small lookup or context data.

| Source | Grain | Coverage (checked 22 Oct 2026) | Role |
| --- | --- | --- | --- |
| [High Volume FHV trips](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) (Uber, Lyft) | One row per trip | Feb 2019 to Aug 2026 | Core: share, fares, driver pay, waits |
| [Yellow taxi trips](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) | One row per trip | Listed back to 2015, through Aug 2026 | Core: the taxi side of every comparison |
| [Green taxi trips](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page) | One row per trip | Through Aug 2026 | Outer-borough street hails (about 1,300 trips a day) |
| [Taxi zone lookup](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zone_lookup.csv) + [shapefile](https://d37ci6vzurychx.cloudfront.net/misc/taxi_zones.zip) | One row per zone | Static | Join key for every map and zone page |
| [TLC monthly indicators](https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv) | Industry by month | Jul 2018 to Jul 2026 | Drivers, vehicles, hours on road (not in trip files) |
| [FHV Base Aggregate Report](https://data.cityofnewyork.us/Transportation/FHV-Base-Aggregate-Report/2v9c-2k7f) | Dispatch base by month | Monthly | Cross-check of trip counts |
| [MTA Congestion Relief Zone rules](https://www.mta.info/fares-tolls/tolls/congestion-relief-zone/about) | Policy | Current | Fee amounts and peak hours |

**Scale.** At about 20 million ride-hail trips a month (675,000 a day), the ride-hail table alone runs past a billion rows since 2019. That is an estimate from the daily rate, not a counted figure. Each monthly file is processed on its own, so a laptop with DuckDB handles it.

**Key ride-hail fields:** company code (HV0003 is Uber, HV0005 is Lyft), request, pickup and drop-off times, pickup and drop-off zone, miles, seconds, `base_passenger_fare`, `driver_pay`, `tips`, `tolls`, `airport_fee`, `congestion_surcharge`, `cbd_congestion_fee`, and shared-ride and wheelchair flags.

**Known gaps that shape the analysis:**

- Driver pay excludes tips, and the rider fare excludes tolls, tips, taxes and fees. Both are defined in the [data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf).
- Yellow-cab tips appear only for card payments, so cash tips are invisible.
- Driver time between trips (empty cruising) is not in trip files; only monthly hours per driver are, from the indicators file.
- TLC states it cannot guarantee the accuracy of vendor-submitted records, and the Parquet schema may still be standardised across years.
- Optional context joins (Central Park weather, subway ridership) are not yet checked.

## Questions people in the field need answered

Fifteen questions, each tied to someone who would act on the answer. Q1, Q2, Q5 and Q9 carry the site's main story; the rest fill out the profile pages.

| # | Question | Who acts on it | Decision it feeds |
| --- | --- | --- | --- |
| Q1 | What share of trips does each of Uber, Lyft, yellow and green hold, by zone and hour, and how has it moved since 2019? | Platform strategy, taxi fleets | Where to compete, where to put cars |
| Q2 | Did congestion pricing shift trips into or out of the zone below 60th St, and which mode lost or gained? | MTA, TLC, platforms | Whether the fee design needs changing |
| Q3 | Who absorbed the $1.50 fee: did ride-hail fares or driver pay move after 5 Jan 2025? | MTA, driver groups | Fee incidence |
| Q4 | Where does Lyft beat Uber on share, and is the gap growing? | Lyft and Uber strategy | Zone-level marketing and driver incentives |
| Q5 | What share of the rider's fare reaches the driver, by company and over time? | Driver groups, TLC | Pay rules, public pressure |
| Q6 | Did the 5% pay increase on 1 Aug 2025 raise driver pay per hour, and did fares rise with it? | TLC, platforms | Whether the next increase should differ |
| Q7 | What do riders pay per mile and per minute by company, hour and borough, and where is pricing most volatile? | Riders, journalists, platforms | Pricing strategy, consumer advice |
| Q8 | How long do riders wait from request to pickup, by zone and hour? | TLC, outer-borough officials | Service-gap targeting |
| Q9 | At JFK, LaGuardia and Newark, who wins the airport trip, at what fare, and when? | Taxi fleets, Port Authority, platforms | Airport staffing and pricing |
| Q10 | Where do yellow cabs still win against ride-hail, and is that ground shrinking? | Medallion owners, fleets | Fleet size and where to cruise |
| Q11 | How often are wheelchair-accessible requests matched, by company? | TLC accessibility | Enforcement of accessibility rules |
| Q12 | Are shared rides coming back, and where? | Platforms, MTA | Pooling incentives |
| Q13 | How do tipping rates differ by company, borough and payment type? | Drivers, platforms | Tipping prompts and defaults |
| Q14 | How much congestion-fee money does each mode generate per month? | MTA finance | Revenue forecasting |
| Q15 | How many hours do drivers and vehicles work, and how many trips per hour on the road? | TLC, driver groups | Licence caps and utilisation rules |

## How each answer is derived

Every answer comes from one pipeline. Raw trips are reduced to a few small aggregate tables, and no web page ever touches a raw trip.

1. **Download** each month's ride-hail, yellow and green Parquet files.
2. **Clean.** Flag rather than delete: trip time of 0 or over 3 hours, miles of 0 or over 100, a fare of $0 or less, and unknown zones (264, 265). Log the share flagged per month so data-quality drift is visible.
3. **Enrich.** Add pickup and drop-off zone names and boroughs, an hour-of-week key, an airport flag, a congestion-zone flag, and a period label (pre-pricing, post-pricing, post-pay-rise).
4. **Aggregate** into four tables:
   - month × company × pickup zone × hour of week: trips, miles, minutes, fares, driver pay, tips, waits
   - month × company × top origin-destination pairs
   - month × company × airport × direction × hour
   - month × company: fees collected
5. **Publish** the aggregates as small Parquet or JSON files the site reads.

**The congestion-zone flag.** Taxi zones do not line up exactly with 60th Street, so the zone list is built by hand from the shapefile. It is then checked against the data itself: from 2025 on, any zone pair where `cbd_congestion_fee` is above zero is inside the zone. Borderline zones are listed on the methods page.

### Metrics

| Metric | Definition | Answers |
| --- | --- | --- |
| Trip share | A company's trips ÷ all trips, same zone, hour and month | Q1, Q4, Q9, Q10 |
| Driver share of fare | `driver_pay` ÷ `base_passenger_fare`, summed per group (formula below) | Q3, Q5, Q6 |
| Fare per mile, per minute | Base fare ÷ trip miles, ÷ trip minutes; median with 10th and 90th percentiles | Q3, Q7, Q9 |
| Price volatility | Spread of fare per mile within the same zone and hour (90th ÷ 10th percentile) | Q7 |
| Wait time | `pickup_datetime` − `request_datetime`, median and 90th percentile; ride-hail only | Q8 |
| Pay per on-trip hour | Driver pay ÷ hours carrying a passenger | Q6 |
| Trips per hour worked | Trips ÷ driver hours, from the monthly indicators file | Q15 |
| Tip rate | Tips ÷ base fare; yellow uses card trips only | Q13 |
| Accessible match rate | Wheelchair trips matched ÷ wheelchair trips requested | Q11 |
| Shared match rate | Shared trips matched ÷ shared trips requested | Q12 |
| Fee revenue | Sum of `cbd_congestion_fee` | Q14 |

The platform's cut is what is left after the driver is paid:

```latex
\text{platform share} = 1 - \frac{\sum \text{driver\_pay}}{\sum \text{base\_passenger\_fare}}
```

It is a ratio of sums, not an average of per-trip ratios, so short trips do not dominate. Tips are excluded on both sides, and fees pass through to the MTA and state, so they are left out too.

### Methods for the causal questions

- **Congestion pricing (Q2, Q3).** A before-and-after comparison against a control group. Treated trips start or end in the zone; control trips stay outside it. Compare each week of 2025 with the same week of 2024 for both groups, so seasonality cancels out. Report the change in trips, fare per mile and driver share of fare.
- **The 5% pay rise (Q6).** A weekly event study around 1 Aug 2025: driver pay per mile and per minute, with fares tracked alongside to see whether riders paid for it.
- **Share shifts (Q1, Q4, Q10).** Zone-level change maps for 2019 to 2026 and for 2024 to 2025, so long-run drift and the pricing shock are shown separately.

### Limits to state on the site

- Without a randomised control, the congestion-pricing results are strong evidence, not proof. Other changes in early 2025 are noted where known.
- Yellow trips have no request time, so wait times are ride-hail only.
- Ride-hail base fare and yellow `fare_amount` both exclude fees, but their surcharges differ. Rider-cost comparisons add each mode's fees back explicitly.
- There is no surge flag and no rider identity, so pricing is described by its spread, not by surge events.

## Design decisions

The site borrows a program website's structure: a home page plus profile pages with tabs. The difference is that every page leads with a measured finding, not a claim.

**Site map: six profile sections answer all 15 questions**

- **Home: the market at a glance** (latest month, headline stats, top findings)
  - **Company profiles**: Uber, Lyft, yellow, green; share, tips, access, sharing (Q4, Q5, Q11, Q12, Q13)
  - **Zone profiles**: 263 pages from one template; share, waits, top routes (Q1, Q8, Q10)
  - **Airports**: JFK, LaGuardia, Newark; who wins, at what fare, when (Q9)
  - **Congestion pricing**: the case-study page; trips, fares, fee revenue (Q2, Q3, Q14)
  - **Drivers**: pay, platform share, hours; before and after 1 Aug 2025 (Q5, Q6, Q15)
  - **Rider prices**: fare per mile and minute; volatility by zone and hour (Q7)
- **Methods and data**: cleaning rules, zone list, limits, downloads

Congestion pricing is the lead story, so it gets its own case-study page and a slot on the home page.

### Page template

Every profile page has the same four parts:

1. **A title that states the finding with its number**, for example "Lyft gained share in N zones since 2024".
2. **A headline stat row** of three or four tiles: the latest month, with the change from the same month a year earlier.
3. **Two to four charts**, each answering one question from the list above.
4. **A "how we measured this" note** linking to the methods page.

### Headline stats per page

| Page | Stat tiles |
| --- | --- |
| Home | Trips per day (all modes) · ride-hail share of trips · platform share of fare · congestion fees last month |
| Company | Trips per day · share of NYC trips · median fare per mile · driver share of fare · tip rate |
| Zone | Trips per day · ride-hail share · median and 90th-percentile wait · top destination |
| Airport | Trips per day · yellow-cab share · median fare to Manhattan · busiest hour |
| Congestion pricing | Change in zone trips vs control · change in fare per mile · fees collected to date |
| Drivers | Pay per on-trip hour · driver share of fare · trips per hour worked · active drivers |
| Rider prices | Median fare per mile · price volatility · cheapest and dearest hour |

### Chart choices

| Question type | Chart | Why this one |
| --- | --- | --- |
| Share over time (Q1, Q4, Q5) | Line per company, monthly, with dated markers at 5 Jan 2025 and 1 Aug 2025 | Shows drift and the two policy breaks together |
| Level by zone (Q1, Q8, Q10) | Map of the 263 zones, one colour shaded light to dark | Geography is the point; zone pages link from it |
| Change by zone (Q2, Q4) | Map shaded in two colours for gain and loss, centred on zero | Gains and losses read apart at a glance |
| Hour by weekday (Q8, Q9) | Heatmap, 24 hours × 7 days | Daily and weekly rhythm in one view |
| Policy effects (Q2, Q3, Q6) | Dot with a range bar per measure, or a before-and-after slope | Shows the size of the effect and its uncertainty |
| Price spread (Q7) | Box or strip plot of fare per mile by company | Spread matters as much as the median |
| Airport split (Q9) | Bars per airport split by mode, summing to 100% | Parts of a whole |

No pies, no 3D, no charts with two y-axes.

### Colour

- **Fixed company colours everywhere:** Uber charcoal, Lyft muted magenta, yellow cab amber, green cab green. The same company is the same colour on every page. These are cues, not brand colours, and no logos appear.
- **Grey first:** anything that is not the point of a chart is light grey, with one accent on what the title is about.
- **Maps:** a single blue shaded light to dark for levels; blue to orange for change, centred on zero. Check every palette with a colour-blindness simulator.
- **Themes:** colours defined as tokens with light and dark versions.

### Type and labels

- One sans-serif family (Inter or IBM Plex Sans) with tabular figures, so numbers line up in tiles and tables.
- Plain data labels only on the points the finding rests on. No "Average" reference-line labels; the finding goes in the subtitle.
- Units in every axis title; dates written as "Jan 2025".
- Charts stack into one column at phone width.

## Action plan

Five phases over about seven weeks, with one gate: the pipeline's monthly trip totals must match TLC's published monthly indicators before any analysis is published.

**Timeline: version 1 goes live on 14 Dec 2026** (dates are targets)

| Step | Dates (2026) |
| --- | --- |
| Set up and download | Oct 26 – Nov 1 |
| Build the pipeline | Nov 2 – Nov 15 |
| Gate: totals tie to TLC | Nov 15 |
| Answer Q1 to Q15 | Nov 9 – Nov 29 |
| Build the site | Nov 23 – Dec 10 |
| Review and polish | Dec 7 – Dec 13 |
| **Version 1 live** | **Dec 14** |

Analysis starts before the pipeline gate on the 2024–2025 months already processed, so the congestion-pricing study is not held up by back-filling 2019–2023.

### Phase 1: Set up and download (26 Oct – 1 Nov)

- [ ] Create a public GitHub repo with folders for raw, clean, aggregate and site
- [ ] Install DuckDB and Python (polars or pandas for small tables)
- [ ] Download ride-hail, yellow and green files for Jan 2024 – Aug 2026, plus the zone lookup and shapefile
- [ ] Build the congestion-zone list from the shapefile

### Phase 2: Build the pipeline (2 – 15 Nov)

- [ ] Write cleaning rules as SQL, with a per-month log of flagged rows
- [ ] Add zone names, hour-of-week, airport and congestion-zone flags, and period labels
- [ ] Produce the four aggregate tables as Parquet
- [ ] Check the congestion-zone list against `cbd_congestion_fee` for 2025 onward
- [ ] **Gate:** monthly trips per day match the TLC indicators file within a small, stated tolerance
- [ ] Back-fill Feb 2019 – Dec 2023 once the gate passes

### Phase 3: Answer the questions (9 – 29 Nov)

- [ ] Market share, airport and zone questions (Q1, Q4, Q9, Q10)
- [ ] Congestion-pricing study with the 2024 control (Q2, Q3, Q14)
- [ ] Pay-rise event study and driver share of fare (Q5, Q6, Q15)
- [ ] Prices, waits, tips, accessibility and shared rides (Q7, Q8, Q11–Q13)
- [ ] Write each finding as one sentence with its number, ready to be a page title

### Phase 4: Build the site (23 Nov – 10 Dec)

- [ ] Scaffold the Observable Framework site (Observable Plot charts, GitHub Pages hosting)
- [ ] Build the page template once: title, stat tiles, charts, methods note
- [ ] Generate the 263 zone pages from the template
- [ ] Build the home, company, airport, congestion, driver and price pages
- [ ] Set the colour tokens and check them in light and dark modes and in a colour-blindness simulator

### Phase 5: Review and launch (7 – 14 Dec)

- [ ] Write the methods page: cleaning rules, zone list, limits
- [ ] Get a fresh-eyes review of every page's finding against its chart
- [ ] Check phone layouts
- [ ] Schedule a monthly GitHub Actions job that pulls the new month, re-aggregates and redeploys
- [ ] Publish version 1 on 14 Dec

## Risks and open questions

| Risk | Effect | Fallback |
| --- | --- | --- |
| TLC changes the Parquet schema (it has said it may) | A monthly refresh breaks | Pin column names in one mapping file; fail loudly on unknown columns |
| Taxi zones don't match the 60th St boundary | Congestion results are blurred at the edge | Validate with `cbd_congestion_fee`; show results with and without borderline zones |
| Another change in early 2025 confounds the pricing effect | Over-claiming | Year-over-year control group; say "evidence", not "proof" |
| Using company names and colours | Looks like an official or branded page | Plain names in text, no logos, own palette, an "independent analysis" line in the footer |
| GitHub Actions disk or time limits on a 20M-row month | Automated refresh fails | Process one file at a time; fall back to a manual monthly run |
| "Another taxi project" | Reviewers discount it | Lead with the ride-hail money fields and congestion pricing, not yellow-cab counts |

**Decisions made 22 Oct 2026:**

- Site stack: a static site built with Observable Framework and Observable Plot, hosted on GitHub Pages.
- Version 1 covers Jan 2024 to the latest month; 2019–2023 is back-filled after launch.
- Uber and Lyft get separate company pages, each with a comparison block.
- The build details for Claude Code live in SPEC.md and CLAUDE.md in the project folder.

### Sources

- [TLC Trip Record Data](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page), checked 22 Oct 2026
- [High Volume FHV data dictionary](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf), dated 18 Mar 2025
- [TLC aggregated reports](https://www.nyc.gov/site/tlc/about/aggregated-reports.page) and [monthly indicators CSV](https://www.nyc.gov/assets/tlc/downloads/csv/data_reports_monthly.csv)
- [MTA Congestion Relief Zone toll](https://www.mta.info/fares-tolls/tolls/congestion-relief-zone/about)
- [6sqft: congestion pricing ruling and year-one results](https://www.6sqft.com/congestion-pricing-lives-on-after-federal-judge-rules-trumps-effort-to-end-program-unlawful/), 4 Mar 2026
- [WageIndicator: 5% ride-hail pay increase](https://wageindicator.org/ai/what-we-do/news-stories/nyc-ridehailing-pay-increase/)
