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
import {explainer} from "../components/notes.js";
import * as format from "../components/format.js";
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

```js
// What a yellow or a green cab is, for readers who don't know New York's taxi rules (D33). The rules
// are TLC licensing facts, so they're written here; the figures come from this page's JSON.
const thisMonth = html`${format.share(data.tiles.share)} of NYC trips in ${format.asOf(asOf)}`;
const EXPLAINERS = {
  yellow: {
    title: "What is a yellow cab?",
    body: html`<p>Yellow cabs are New York's medallion taxis. Each one needs a medallion, a city license whose number is capped, and they're the only vehicles allowed to pick up street hails anywhere in the five boroughs, including the Manhattan core and the airport taxi stands. Fares run on the meter at rates the TLC sets, plus fixed surcharges, and trips between JFK and Manhattan pay a flat fare.</p>`,
    notes: [
      "The only cars that can stop for a street hail anywhere in the city",
      thisMonth,
      "Metered fares set by the TLC, so no surge pricing"
    ]
  },
  green: {
    title: "What is a green cab?",
    body: html`<p>Green cabs, officially street-hail liveries and often called boro taxis, were created to serve the parts of the city where yellow cabs rarely cruise. They can pick up street hails in the Bronx, Brooklyn, Queens, Staten Island and northern Manhattan, but not in the Manhattan core or at the airports, and they can drop passengers off anywhere. They charge the same metered rates as yellow cabs.</p>`,
    notes: [
      "Street hails only outside the Manhattan core and the airports",
      thisMonth,
      "Drop-offs anywhere in the city, pickups in their own area"
    ]
  }
};
if (EXPLAINERS[data.mode]) display(explainer(EXPLAINERS[data.mode]));
```

## Share of NYC trips

```js
// A company whose share is under a twentieth of the largest one's lies on the shared axis's baseline
// (green cabs), so its line gets a panel of its own beneath, on its own scale.
const ownShares = data.share_trend.filter((d) => d.mode === data.mode && d.share != null).map((d) => d.share);
const topShare = Math.max(0, ...data.share_trend.map((d) => d.share ?? 0));
const zoom = ownShares.length && Math.max(...ownShares) < topShare / 20 ? data.mode : undefined;
```

```js
chartOr("Share of trips", data.share_trend, data.subtitles.share_trend, () =>
  shareLine(data.share_trend, {events: events.events, zoom, subtitle: data.subtitles.share_trend, asOf, width, dark}))
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
