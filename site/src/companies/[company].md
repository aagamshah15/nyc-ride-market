---
title: Company profile
---

<!-- L13 · One template for Uber, Lyft, yellow and green cabs (SPEC §9.1, §9.3, D3). Every number,
     title, subtitle and finding comes from companies/{company}.json; the page adds none. Taxis list
     the metrics they lack in `not_reported`, and those sections show "not reported for this mode". -->

```js
import {pageHeader, howWeMeasured, notReported, emptyState, compareTable, html} from "../components/page.js";
import {shareLine, lineChart, fareRange, sourceCaption} from "../components/charts.js";
import {countTiles, gapScatter, latestAndYearEarlier, tipSeriesLabel} from "./company.js";
```

```js
const data = FileAttachment(`../data/companies/${observable.params.company}.json`).json();
const tiles = FileAttachment("../data/tiles.json").json();
const events = FileAttachment("../data/events.json").json();
```

```js
document.title = document.title.replace("Company profile", data.name);
const asOf = data.as_of_month;
const reported = (key) => !(data.not_reported ?? []).includes(key);
const cardOnlyTips = data.tip_rate.some((d) => d.mode === data.mode && d.card_only);

// A chart, or a plain state when the file has no rows or no finding for it.
const chartOr = (what, rows, subtitle, draw) =>
  rows?.length && subtitle ? draw() : emptyState(`${what}: no data for this month`);
```

```js
display(pageHeader(data, tiles, {keys: ["trips_per_day", "share", "fpm_median", "driver_share", "tip_rate"]}));
if (cardOnlyTips) display(html`<p class="nrm-note">The tip rate is card-only: TLC records cab tips on card payments only.</p>`);
```

## Share of NYC trips

```js
chartOr("Share of trips", data.share_trend, data.subtitles.share_trend, () =>
  shareLine(data.share_trend, {events: events.events, subtitle: data.subtitles.share_trend, asOf, width, dark}))
```

```js
if (data.lyft_vs_uber) {
  display(html`<h2 id="lyft-vs-uber">Where Lyft beats Uber</h2>`);
  display(chartOr("Lyft and Uber by zone", data.lyft_vs_uber.by_zone, data.subtitles.lyft_vs_uber, () =>
    gapScatter(data.lyft_vs_uber.by_zone, {subtitle: data.subtitles.lyft_vs_uber, asOf, width, dark})));
}
```

## Fare per mile

```js
const fpm = latestAndYearEarlier(data.fpm_dist);
```

```js
chartOr("Fare per mile", fpm.rows, data.subtitles.fpm_dist, () =>
  fareRange(fpm.rows, {fy: "month", fyLabels: fpm.labels, subtitle: data.subtitles.fpm_dist, asOf, width, dark}))
```

## Tips

```js
chartOr("Tip rate", data.tip_rate, data.subtitles.tip_rate, () =>
  lineChart(data.tip_rate, {y: "tip_rate", yUnit: "share", yLabel: "Tips as a share of the fare (%)",
    seriesLabel: tipSeriesLabel(data.tip_rate), subtitle: data.subtitles.tip_rate, asOf, width, dark}))
```

## Wheelchair-accessible service

```js
if (!reported("wav")) {
  display(notReported("Wheelchair-accessible service", data.subtitles.wav ?? undefined));
} else {
  display(chartOr("Wheelchair-accessible service", data.wav, data.subtitles.wav, () =>
    lineChart(data.wav, {y: "wav_share", yUnit: "share", yLabel: "Trips in a wheelchair-accessible vehicle (%)",
      subtitle: data.subtitles.wav, asOf, width, dark})));
  if (data.wav.length) display(countTiles(data.wav, "wav_requests", "completed trips that requested a wheelchair-accessible vehicle"));
  display(html`<p class="nrm-note">TLC's trip records hold completed trips only. Requests for a wheelchair-accessible vehicle that went unfilled aren't in them, so a match rate can't be measured.</p>`);
}
```

## Shared rides

```js
if (!reported("shared")) {
  display(notReported("Shared rides", data.subtitles.shared ?? undefined));
} else {
  display(chartOr("Shared rides", data.shared, data.subtitles.shared, () =>
    lineChart(data.shared, {y: "match_rate", yUnit: "share", yLabel: "Shared-ride requests matched (%)",
      subtitle: data.subtitles.shared, asOf, width, dark})));
  if (data.shared.length) display(countTiles(data.shared, "requests", "shared-ride requests"));
}
```

## Compared with the other companies

```js
html`<div class="nrm-chart"><figure>
  ${data.subtitles.compare ? html`<h3>${data.subtitles.compare}</h3>` : null}
  ${compareTable(data.compare, tiles, {current: data.mode})}
  <figcaption>${sourceCaption(asOf)}</figcaption>
</figure></div>`
```

```js
howWeMeasured("tips", "Cab tip rates are card-only, and accessible-service figures count completed trips only. Definitions, cleaning rules and known limits are on the methods page.")
```
