---
title: NYC Ride Market
---

<!-- L12 · Home (SPEC §9.1, §9.3): the market at a glance and the top findings. Every number, title,
     subtitle and finding comes from home.json, share_monthly.json, events.json and tiles.json;
     the page adds none. The congestion-pricing findings get their own block, so the findings
     lists leave them out. -->

```js
import {pageHeader, howWeMeasured, findingsList, siteUrl, html} from "./components/page.js";
import {shareLine} from "./components/charts.js";
import {tile} from "./components/statTiles.js";
```

```js
const home = FileAttachment("data/home.json").json();
const shareMonthly = FileAttachment("data/share_monthly.json").json();
const events = FileAttachment("data/events.json").json();
const tiles = FileAttachment("data/tiles.json").json();
```

```js
const asOf = home.as_of_month;
// The share trend marks the two policy dates of SPEC §9.4; the March inflation step (D28) is a pay event only.
const shareEvents = events.events.filter((e) => e.id === "congestion_pricing_start" || e.id === "driver_pay_rise");
const CONGESTION_PAGE = "/congestion-pricing";
const congestionFindings = home.findings.filter((f) => f.page === CONGESTION_PAGE);
const otherFindings = home.findings.filter((f) => f.page !== CONGESTION_PAGE);
const featured = otherFindings.filter((f) => f.featured);
const more = otherFindings.filter((f) => !f.featured);
// Q2 and Q3 carry the headline estimated effects on trips and on ride-hail fare per mile.
const effectValue = (question) => home.findings.find((f) => f.question === question && f.unit === "effect")?.value ?? null;
```

```js
display(pageHeader(home, tiles, {keys: ["trips_per_day", "rh_share", "platform_share", "cbd_fees_last_month"]}));
```

<p class="nrm-note">Uber, Lyft, yellow cabs and green cabs, from NYC TLC trip records. Platform share is the part of Uber and Lyft base fares that doesn't go to the driver.</p>

## Who carries New York's trips

```js
shareLine(shareMonthly.rows, {events: shareEvents, subtitle: home.subtitles.share_trend, asOf, width, dark})
```

## Top findings

```js
display(findingsList(featured));
if (more.length) display(html`<details class="nrm-table"><summary>More findings</summary>${findingsList(more)}</details>`);
```

## Congestion pricing

```js
display(html`<div class="nrm-tiles">
  ${tile(tiles.tiles.trips_effect, effectValue("Q2"), null)}
  ${tile(tiles.tiles.fpm_effect, effectValue("Q3"), null)}
</div>`);
display(findingsList(congestionFindings));
display(html`<p><a href=${siteUrl(CONGESTION_PAGE)}>See the congestion-pricing estimates</a> and <a href=${siteUrl("methods#congestion-method")}>how they were made</a>.</p>`);
```

```js
howWeMeasured("cleaning", "Shares count every trip record, as TLC does; fares, pay and other per-trip figures use the trips that pass the cleaning rules. Definitions, validation and known limits are on the methods page.")
```
