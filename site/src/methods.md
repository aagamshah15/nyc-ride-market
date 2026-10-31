---
title: Methods
toc: true
---

<!-- L12 · Methods (SPEC §9.1, §4.2, §7, §8, §12): how the data is processed, validated and published.
     Every number comes from JSON: quality.json (flags, validation, the zone list, downloads),
     congestion.json (estimated effects with and without the borderline zones, SPEC §7.3) and
     events.json (policy dates). The section ids are the anchors in contracts/site/pages.yaml that
     every page's "How we measured this" note links to. Thresholds in the prose are written in words. -->

<style>
  .nrm-mtable {
    margin: 0;
  }

  .nrm-mtable td.nrm-num {
    white-space: nowrap;
  }

  .nrm-sub {
    color: var(--theme-foreground-muted);
    font-size: 13px;
  }
</style>

```js
import * as format from "./components/format.js";
import * as palette from "./components/palette.js";
import {lineChart, sourceCaption, tableView} from "./components/charts.js";
import {mockBanner, siteUrl, html} from "./components/page.js";
```

```js
const quality = FileAttachment("data/quality.json").json();
const congestion = FileAttachment("data/congestion.json").json();
const events = FileAttachment("data/events.json").json();
```

```js
// Framework needs literal file names, so every downloadable file is referenced here (nothing is
// fetched until a reader clicks). Which files are listed, with descriptions and sizes, comes from
// quality.json `downloads`.
const FILES = {
  "share_monthly.json": FileAttachment("data/share_monthly.json"),
  "zones/index.json": FileAttachment("data/zones/index.json"),
  "congestion.json": FileAttachment("data/congestion.json"),
  "drivers.json": FileAttachment("data/drivers.json"),
  "prices.json": FileAttachment("data/prices.json"),
  "airports.json": FileAttachment("data/airports.json"),
  "quality.json": FileAttachment("data/quality.json")
};
```

```js
const asOf = quality.as_of_month;
const validation = quality.validation;
const months = [...new Set(quality.quality.map((d) => d.month))].sort();
const latest = months.at(-1);
const modes = palette.modeOrder.filter((m) => quality.quality.some((d) => d.mode === m));
const check = (id) => validation.checks.find((c) => c.id === id);
const status = (s) => ({pass: "Pass", fail: "Fail", skipped: "Skipped", excepted: "Exception"})[s] ?? s;
const day = (d) => `${format.utcDate(d).getUTCDate()} ${format.month(d)}`;
const eventDate = (id) => {
  const e = events.events.find((e) => e.id === id);
  return e ? day(e.date) : format.NA;
};
const published = day(quality.generated_at.slice(0, 10));
const zoneLink = (zone, name) => html`<a href=${siteUrl(`zones/${zone}`)}>${name}</a>`;
// A flag share too small to show at one decimal reads as "under" the smallest step rather than "0.0%".
const flagShare = (n, rows) => (n == null ? format.NA : n > 0 && format.share(n / rows) === format.share(0) ? `under ${format.share(0.001)}` : format.share(n / rows));
const table = (head, rows, {minWidth = "30rem"} = {}) =>
  html`<div class="nrm-scroll-x"><table class="nrm-mtable" style=${{minWidth}}><thead>${head}</thead><tbody>${rows}</tbody></table></div>`;
const tableFigure = (title, content, caption) =>
  html`<div class="nrm-chart"><figure><h2>${title}</h2>${content}<figcaption>${caption}</figcaption></figure></div>`;
```

```js
const banner = mockBanner(quality);
if (banner) display(banner);
```

# Methods

How the site turns NYC TLC trip records into the figures on every page: where the data comes from, how each record is cleaned and flagged, how the pipeline is checked before anything is published, how the two policy studies work, and what the data can't tell you.

<p class="nrm-note">Data from ${format.month(months[0])} to ${format.asOf(asOf)} · published ${published} · validation: ${status(validation.status)}</p>

<h2 id="sources" tabindex="-1"><a class="observablehq-header-anchor" href="#sources">Sources</a></h2>

- **Trip records.** TLC's monthly files of every trip by the high-volume ride-hail companies (Uber, Lyft and any others still licensed), yellow cabs and green cabs, from the [TLC Trip Record Data page](https://www.nyc.gov/site/tlc/about/tlc-trip-record-data.page). Other for-hire vehicles, such as black cars and liveries, aren't covered.
- **Zones.** TLC's taxi-zone lookup and zone map, for zone names, boroughs, the maps and the congestion-zone list.
- **Monthly indicators.** TLC's own monthly figures for each licence class: trips per day, drivers, vehicles and hours. They check the pipeline's trip counts, and the driver figures labelled "TLC-reported" come from them.
- **Data dictionaries.** TLC's definitions of each field, for [ride-hail](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_hvfhs.pdf), [yellow](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_yellow.pdf) and [green](https://www.nyc.gov/assets/tlc/downloads/pdf/data_dictionary_trip_records_green.pdf) trips.

TLC posts each month about two months after it ends, and may revise recent months.

<h2 id="cleaning" tabindex="-1"><a class="observablehq-header-anchor" href="#cleaning">Cleaning</a></h2>

- **One month at a time.** Each month's three files are mapped into one table with the same columns for every mode. A column the mapping doesn't know stops the pipeline; it is never guessed.
- **Flag, never delete.** Each record is checked against the rules under [Quality flags](#flags) and keeps every flag it earns. A record is valid when it has none of the time, distance, fare or zone flags.
- **Counts use every record.** Trip counts and shares count all records, valid or not, so they match TLC's own counts. Fee revenue also sums every record, since the fee was charged whatever the rest of the record says.
- **Everything else uses valid records.** Fares, driver pay, tips, distances and durations come from valid trips only.
- **Ratios of sums.** Fare per mile is total fare divided by total miles, never the average of each trip's own fare per mile. Long trips count for more than short ones, as they do in the money.
- **Durations.** Ride-hail records carry a trip time. Cab records don't, so a cab trip lasts from pickup to drop-off.
- **Base fare and rider cost.** Base fare is the fare before tolls, taxes, surcharges, fees and tips. Comparisons of what riders paid use the total before tip.
- **Percentiles need enough trips.** Medians and other percentiles of fare per mile and of waits are computed for a zone and mode only when the month has at least a hundred valid trips; zones with fewer show "too few trips".
- **Zones.** TLC's "Unknown" zone is flagged. Its "Outside of NYC" zone is a real place (New Jersey, Westchester and beyond): those trips are valid and count in citywide figures. Neither gets a zone page. TLC-licensed vehicles don't pick up at Newark Airport, so its page shows drop-offs, and its stray pickup records are left out of every zone count and map.

<h2 id="flags" tabindex="-1"><a class="observablehq-header-anchor" href="#flags">Quality flags</a></h2>

Each flag is a column on the record; a record can carry more than one, so the flag shares can add up to more than the share of records that aren't valid.

```js
const FLAGS = [
  ["f_time", "Time", "The trip lasts zero seconds or less, or more than three hours, or its pickup falls outside the file's month (give or take a day)"],
  ["f_miles", "Distance", "The trip is zero miles or less, or more than a hundred miles"],
  ["f_fare", "Fare", "The base fare is zero or less"],
  ["f_zone", "Zone", "The pickup or drop-off zone is TLC's \"Unknown\" zone, or missing"],
  ["f_wait", "Wait", "Ride-hail only: the wait from request to pickup is negative or longer than an hour. These records stay in every figure except waits"]
];
const latestRows = new Map(quality.quality.filter((d) => d.month === latest).map((d) => [d.mode, d]));
const modeCells = (f) => modes.map((m) => html`<td class="nrm-num">${latestRows.has(m) ? f(latestRows.get(m)) : format.NA}</td>`);
display(tableFigure(`Share of records flagged, ${format.month(latest)}`, table(
  html`<tr><th>Flag</th><th>Flagged when</th>${modes.map((m) => html`<th class="nrm-num">${format.modeName(m)}</th>`)}</tr>`,
  [
    ...FLAGS.map(([key, name, rule]) => html`<tr><td><strong>${name}</strong><br><code>${key}</code></td><td style="min-width: 16rem">${rule}</td>${modeCells((d) => flagShare(d[key], d.rows))}</tr>`),
    html`<tr><td><strong>Valid</strong><br><code>is_valid</code></td><td>None of the time, distance, fare or zone flags</td>${modeCells((d) => format.share(d.valid_share))}</tr>`,
    html`<tr><td><strong>Records</strong></td><td>Every record in the month's file</td>${modeCells((d) => format.count(d.rows))}</tr>`
  ],
  {minWidth: "44rem"}
), sourceCaption(asOf)));
display(tableView(quality.quality, [
  {key: "month", label: "Month", format: "month"},
  {key: "mode", label: "Mode", format: "mode"},
  {key: "rows", label: "Records", format: "count"},
  {key: "valid_share", label: "Valid", format: "share"},
  ...FLAGS.map(([key, name]) => ({key, label: `${name} flags`, format: "count"}))
]));
```

```js
lineChart(quality.quality, {y: "valid_share", yUnit: "share", yLabel: "Valid records (%)", zero: false,
  title: "Valid records by month", subtitle: check("quality_drift")?.summary, asOf, width, dark})
```

The validation gate fails a month and mode whose valid share falls below a fixed floor, and lists any month well below its mode's usual share.

<h2 id="cbd-zones" tabindex="-1"><a class="observablehq-header-anchor" href="#cbd-zones">Congestion-zone list</a></h2>

Congestion pricing charges vehicles in Manhattan south of Sixtieth Street. Taxi zones don't follow that line, so the list of zones that count as "in the zone" was drawn from the zone map and checked against the fees trips actually paid.

```js
const core = quality.cbd_zones.filter((z) => !z.borderline);
const borderline = quality.cbd_zones.filter((z) => z.borderline);
```

- **Core list:** the ${core.length} zones that lie wholly south of the line. Every congestion figure on the site uses it unless it says otherwise.
- **Wide list:** the core list plus ${borderline.length} borderline zones that straddle the line or are islands with no road access. It shows whether the results hinge on that call.

```js
display(tableFigure("Borderline zones (wide list only)", table(
  html`<tr><th class="nrm-num">Zone</th><th>Name</th><th>Why it's borderline</th></tr>`,
  borderline.map((z) => html`<tr><td class="nrm-num">${z.zone}</td><td>${zoneLink(z.zone, z.name)}</td><td>${z.note}</td></tr>`)
), "Zone map: NYC TLC taxi zones"));
display(html`<details class="nrm-table"><summary>The ${core.length} core zones</summary>
  <p>${core.map((z, i) => html`${i ? ", " : ""}${zoneLink(z.zone, z.name)}`)}</p>
</details>`);
```

### Results with and without the borderline zones

If the list matches the charge zone, nearly every trip with both ends in it should carry a fee. Trips with neither end in it can still pass through the zone and pay. The validation gate tests the core list only; the wide list can't pass by construction, because most of the area of its straddling zones lies outside the charge zone. The check starts with the first month wholly under pricing.

```js
const LIST_NAMES = {core: "Core (without borderline zones)", wide: "Wide (with borderline zones)"};
const listSize = {core: core.length, wide: quality.cbd_zones.length};
const listResult = (r) => (r.status === "pass" ? "Pass" : r.zone_list === "core" ? status(r.status) : "Reported, not gated");
display(tableFigure("Trips that carry a congestion fee, by zone list", table(
  html`<tr><th>Zone list</th><th class="nrm-num">Zones</th><th class="nrm-num">Both ends in the list</th><th class="nrm-num">Neither end in the list</th><th>Gate</th></tr>`,
  validation.cbd.map((r) => html`<tr><td>${LIST_NAMES[r.zone_list] ?? r.zone_list}</td><td class="nrm-num">${listSize[r.zone_list] ?? format.NA}</td>
    <td class="nrm-num">${format.share(r.both_in_fee_share)}</td><td class="nrm-num">${format.share(r.neither_in_fee_share)}</td><td>${listResult(r)}</td></tr>`)
), sourceCaption(asOf)));
```

```js
const METRICS = {trips: "Trips touching the zone", fare_per_mile: "Base fare per mile", driver_share: "Driver share of base fare"};
const EFFECT_MODES = ["all", "ride_hail", ...palette.modeOrder];
const effectKey = (d) => `${d.metric}|${d.mode}`;
const byList = Object.fromEntries(["core", "wide"].map((list) => [list, new Map(congestion.effects.filter((d) => d.zone_list === list).map((d) => [effectKey(d), d]))]));
const effectRows = congestion.effects
  .filter((d) => d.zone_list === "core")
  .sort((a, b) => Object.keys(METRICS).indexOf(a.metric) - Object.keys(METRICS).indexOf(b.metric) || EFFECT_MODES.indexOf(a.mode) - EFFECT_MODES.indexOf(b.mode));
const effectCell = (d) => (d ? html`<td class="nrm-num"><strong>${format.effect(d.median)}</strong><br><span class="nrm-sub">${format.effect(d.p10)} to ${format.effect(d.p90)}</span></td>` : html`<td class="nrm-num">${format.NA}</td>`);
display(tableFigure("Estimated effects of congestion pricing with each zone list", table(
  html`<tr><th>Measure</th><th>Mode</th><th class="nrm-num">${LIST_NAMES.core}</th><th class="nrm-num">${LIST_NAMES.wide}</th></tr>`,
  effectRows.map((d) => html`<tr><td>${METRICS[d.metric] ?? d.metric}</td><td>${format.modeName(d.mode)}</td>${effectCell(d)}${effectCell(byList.wide.get(effectKey(d)))}</tr>`),
  {minWidth: "34rem"}
), sourceCaption(congestion.as_of_month)));
```

<p class="nrm-note">Each estimate is the median weekly estimated effect, with the range from the tenth to the ninetieth percentile of weeks beneath it. The method is under <a href="#congestion-method">Congestion-pricing method</a>.</p>

<h2 id="validation" tabindex="-1"><a class="observablehq-header-anchor" href="#validation">Validation</a></h2>

```js
const CHECKS = {
  tie_out: ["Tie-out with TLC", "Trips per day in the pipeline against TLC's monthly indicators. Ride-hail must match within a fixed tolerance. Cab figures follow TLC counting rules the files can't reproduce, so they are reported but don't gate; a month whose TLC figure covers trips missing from TLC's own file is a documented exception."],
  quality_drift: ["Record quality", "Every month and mode must have enough valid records; months well below their mode's usual share are listed."],
  cbd_list: ["Congestion-zone list", "Trips with both ends in the core list must nearly all carry a congestion fee."],
  schema: ["Schema", "Every column in every file maps to the unified table; an unmapped, missing or mistyped column fails."],
  fees: ["Congestion fees", "Since pricing began, nearly every trip with a congestion fee carries exactly the fee set for its mode."]
};
```

Nothing is published until the validation gate passes: all ${validation.checks.length} checks, over every month from ${format.month(months[0])} to ${format.asOf(asOf)}. Each data file the site reads records whether it passed, and a page shows a notice if its figures haven't. Latest result: **${status(validation.status)}**.

```js
display(tableFigure("Validation checks", table(
  html`<tr><th>Check</th><th>Result</th><th>What it tests, and the latest run</th></tr>`,
  validation.checks.map((c) => html`<tr><td><strong>${CHECKS[c.id]?.[0] ?? c.id}</strong></td><td>${status(c.status)}</td>
    <td>${CHECKS[c.id]?.[1] ?? ""}<br><span class="nrm-sub">${c.summary}</span></td></tr>`),
  {minWidth: "20rem"}
), sourceCaption(asOf, "trip records and monthly indicators")));
```

```js
const LICENCE_MODES = {"FHV - High Volume": "ride_hail", Yellow: "yellow", Green: "green"};
const tieOut = validation.tie_out.map((d) => ({...d, mode: LICENCE_MODES[d.license_class] ?? d.license_class}));
const exceptions = tieOut.filter((d) => d.status === "excepted");
```

```js
lineChart(tieOut, {y: "diff", yUnit: "effect", yLabel: "Pipeline trips per day vs TLC's figure (%)",
  title: "Tie-out with TLC's monthly indicators", subtitle: check("tie_out")?.summary, asOf,
  dataset: "trip records and monthly indicators", width, dark})
```

```js
const one = exceptions.length === 1;
if (exceptions.length) display(html`<p class="nrm-note">${one ? "Documented exception" : "Documented exceptions"}: ${exceptions.map((d) => `${format.modeName(d.mode)}, ${format.month(d.month)} (${format.effect(d.diff)})`).join("; ")}. ${one ? "It is" : "They are"} reported with ${one ? "its" : "their"} reason in the validation report rather than gating.</p>`);
```

```js
const otherValues = (vals) => vals.length
  ? vals.map((v) => `${format.usd(v.cbd_fee)} (${format.count(v.trips)} trips)`).join(", ")
  : "None";
display(tableFigure("Congestion fees charged, by mode", table(
  html`<tr><th>Mode</th><th class="nrm-num">Fee set for the mode</th><th class="nrm-num">Trips charged exactly that</th><th>Other amounts seen</th><th>Result</th></tr>`,
  validation.fees.map((r) => html`<tr><td>${format.modeName(r.mode)}</td><td class="nrm-num">${format.usd(r.configured_fee)}</td>
    <td class="nrm-num">${format.share(r.exact_share)}</td><td>${otherValues(r.other_values)}</td><td>${status(r.status)}</td></tr>`),
  {minWidth: "36rem"}
), sourceCaption(asOf)));
```

<h2 id="congestion-method" tabindex="-1"><a class="observablehq-header-anchor" href="#congestion-method">Congestion-pricing method</a></h2>

Congestion pricing began on ${eventDate("congestion_pricing_start")}. The site estimates its effect with a year-over-year difference-in-differences, week by week:

- **Two groups.** Trips that start or end in the congestion zone (core list), and trips that do neither.
- **Growth.** For each week since pricing began, each group's value is compared with the same week a year earlier.
- **Estimated effect.** The growth of trips touching the zone divided by the growth of the rest, minus one. Comparing each group with itself a year earlier takes out the season; comparing the two groups takes out whatever changed citywide between the years, as long as it changed both groups alike.
- **Measures,** each a ratio of sums over the week: trips (every record, as TLC counts them), base fare per mile (valid trips) and the driver share of the base fare (valid Uber and Lyft trips).
- **Summary.** The median weekly estimated effect over ${congestion.effects[0]?.weeks ?? format.NA} weeks, with the range from the tenth to the ninetieth percentile of weeks as its spread.
- **Weeks left out.** The week pricing began, since only its last day was charged, and weeks where a federal holiday falls in a different week in the two years: ${[...new Set(congestion.excluded_weeks.map((w) => w.reason))].join("; ") || "none so far"}.

These are estimated effects, not proof of cause. The comparison is against trips outside the zone, not a randomised test, so anything else that changed for trips in the zone but not elsewhere between the two years shows up in the estimate too. The results: ${html`<a href=${siteUrl("/congestion-pricing")}>Congestion pricing</a>`}.

<h2 id="pay-rise-method" tabindex="-1"><a class="observablehq-header-anchor" href="#pay-rise-method">Minimum-pay rule method</a></h2>

On ${eventDate("driver_pay_rise")} a new TLC minimum-pay rule for ride-hail drivers took effect. It lowered the per-mile floor and raised the per-minute floor, so whether a trip's minimum went up or down depends on its mix of miles and minutes. Earlier, on ${eventDate("driver_pay_inflation_step")}, TLC's yearly inflation step raised the per-minute minimum only. The site looks for the new rule in an event study:

- **Series.** Weekly and citywide, for Uber, Lyft and the two together: driver pay per mile, driver pay per minute with a passenger, and base fare per mile, each a ratio of sums over valid trips.
- **Window.** The twelve weeks before and the twelve weeks after the week the rule took effect. That week mixes days under both rules, so it is drawn but left out of the before-and-after comparison.
- **Seasonal reference.** The same weeks a year earlier, when pay rules didn't change. The reported change is the before-to-after change net of the same change a year earlier.
- **Medians.** Before and after are each the median weekly value, so one odd week doesn't move the result.

**Pay per hour** on the drivers page is per hour with a passenger: driver pay divided by the hours a rider was aboard. Trip records don't show a driver's time between trips, so it isn't pay per hour worked. Trips per hour worked and active drivers come from TLC's monthly indicators and are labelled TLC-reported. Driver pay in the records leaves out tips and tolls. The results: ${html`<a href=${siteUrl("/drivers")}>Drivers</a>`}.

<h2 id="tips" tabindex="-1"><a class="observablehq-header-anchor" href="#tips">Tips</a></h2>

- **Tip rate** is total tips divided by total base fare, a ratio of sums.
- **Ride-hail** records carry the tip on every trip, since riders tip in the app.
- **Cab tips are card-only.** TLC records a cab tip only when the rider pays by card; cash tips aren't in the data. A cab tip rate is card tips divided by the base fare of card trips, so it describes card-paying riders, not every cab rider.

<h2 id="waits" tabindex="-1"><a class="observablehq-header-anchor" href="#waits">Waits</a></h2>

- **Wait** is the time from a ride-hail request to pickup. Cab records have no request time, so waits are ride-hail only; cab pages show them as not reported.
- **Flagged waits** (negative, or longer than an hour) are left out of wait figures only; the trips still count everywhere else.
- **By pickup zone.** Median and ninetieth-percentile waits for a zone need at least a hundred valid trips in the month; zones with fewer show "too few trips". Waits are for completed trips: a request that was cancelled or never filled has no record.

<h2 id="limits" tabindex="-1"><a class="observablehq-header-anchor" href="#limits">Known limits</a></h2>

- **Congestion-pricing results** are a year-over-year comparison against trips outside the zone, not a randomised test. They are estimated effects.
- **Ride-hail base fare** excludes tolls, tips, taxes and fees; comparisons of what riders paid use the total before tip.
- **Cab tips are card-only.**
- **No surge flag, no rider identity and no driver time between trips** are in the trip files, so the site can't measure surge pricing, repeat riders or pay per hour worked.
- **Completed trips only.** Requests for a wheelchair-accessible vehicle that went unfilled aren't in TLC's records, so the site reports how many requested trips were completed and what share of trips ran in an accessible vehicle, not a match rate. A shared-ride match counts only when the rider asked to share.
- **Cab counts** differ from TLC's monthly indicators by a few percent in some months, because TLC counts cab trips in ways its files don't show. Every cab record is still checked in and out of the pipeline.
- **High-volume ride-hail only.** Black cars, liveries and other for-hire vehicles aren't covered.
- **Zone lines.** Taxi zones don't follow the congestion-zone boundary; see [Congestion-zone list](#cbd-zones).
- **TLC's data.** TLC doesn't guarantee records submitted by companies and may change its file layout. It posts each month about two months late and may revise recent months.

<h2 id="downloads" tabindex="-1"><a class="observablehq-header-anchor" href="#downloads">Downloads</a></h2>

The files the pages read, as published. Each carries the month it runs to, when it was generated and whether it passed validation.

```js
const kb = (bytes) => `${format.count(Math.round(bytes / 100) / 10)} KB`;
display(tableFigure("Published data files", table(
  html`<tr><th>File</th><th>What it holds</th><th class="nrm-num">Size</th></tr>`,
  quality.downloads.map((d) => html`<tr>
    <td>${FILES[d.file] ? html`<a href=${FILES[d.file].href} download=${d.file.replace("/", "_")}><code>${d.file}</code></a>` : html`<code>${d.file}</code>`}</td>
    <td>${d.description}</td><td class="nrm-num">${kb(d.bytes)}</td></tr>`),
  {minWidth: "18rem"}
), sourceCaption(asOf)));
```
