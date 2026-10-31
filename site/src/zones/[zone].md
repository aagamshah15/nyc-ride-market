---
title: Zone profile
---

```js
// One page per taxi zone, /zones/1 … /zones/263 (SPEC §9.1; L14). Every number, title and
// subtitle comes from zones/{zone}.json; zones 264 and 265 get no page (D26). A zone with
// flags.thin (fewer than 100 valid trips in the latest month, or Newark Airport, whose
// pickups aren't TLC trips) shows its title and tiles and a "too few trips" state in place
// of the charts.
import * as format from "../components/format.js";
import {shareLine, lineChart, hourHeatmap, barChart} from "../components/charts.js";
import {pageHeader, howWeMeasured, tooFewTrips, emptyState, siteUrl, html} from "../components/page.js";
```

```js
const zone = FileAttachment(`../data/zones/${observable.params.zone}.json`).json();
const events = FileAttachment("../data/events.json").json();
const tiles = FileAttachment("../data/tiles.json").json();
```

```js
document.title = `${zone.name} | NYC Ride Market`;
const asOf = zone.as_of_month;
const thin = Boolean(zone.flags?.thin);
// Top destinations rank zones 1–263; trips leaving the city (zone 265) are in the subtitle.
const destinations = zone.top_destinations.filter((d) => d.do_zone >= 1 && d.do_zone <= 263);
const destinationName = new Map(destinations.map((d) => [d.do_zone, d.name]));
```

<p class="nrm-zone-crumb"><a href="./">All zones</a> · Zone ${zone.zone} · ${zone.borough}${zone.flags?.cbd ? " · Inside the congestion zone" : ""}</p>

```js
display(pageHeader(zone, tiles, {keys: ["trips_per_day", "rh_share", "wait_p50", "wait_p90", "top_destination"]}));
```

```js
if (thin) display(tooFewTrips("Charts of pickups by mode, hour, wait and destination"));
```

```js
if (!thin) {
  display(zone.share_trend.length && zone.subtitles.share_trend
    ? shareLine(zone.share_trend, {events: events.events, yLabel: "Share of pickups here (%)", title: "Who picks up here",
        subtitle: zone.subtitles.share_trend, asOf, width, dark})
    : emptyState("No pickups to chart", zone.subtitles.share_trend ?? ""));
}
```

```js
if (!thin) {
  if (zone.hour_heatmap.length && zone.subtitles.hour_heatmap) {
    display(hourHeatmap(zone.hour_heatmap, {legendLabel: "Pickups in the hour, average week", title: "When pickups happen",
      subtitle: zone.subtitles.hour_heatmap, asOf, width, dark}));
    display(html`<p class="nrm-note">Average week over the latest three months. Modes with less than a tenth of the zone's pickups are left out.</p>`);
  } else {
    display(emptyState("No pickups to chart", zone.subtitles.hour_heatmap ?? ""));
  }
}
```

```js
if (!thin) {
  if (zone.waits.monthly.length) {
    display(lineChart(zone.waits.monthly, {y: "wait_p50", yUnit: "seconds", yLabel: "Median wait from request to pickup (minutes)",
      title: "How long riders wait", subtitle: zone.subtitles.waits, asOf, width, dark}));
    display(html`<p class="nrm-note">Ride-hail only: cab records have no request time.</p>`);
  } else {
    display(tooFewTrips("Wait percentiles"));
  }
}
```

```js
if (!thin) {
  if (destinations.length) {
    // barChart caps its label margin at 40% of the width; shorten names that wouldn't fit on phones.
    const fit = Math.floor((width * 0.4 - 16) / 6.5);
    const clip = (name) => (name.length > fit ? `${name.slice(0, fit - 1).trimEnd()}…` : name);
    display(barChart(destinations, {x: "share", y: "do_zone", yLabels: (z) => clip(destinationName.get(z)), unit: "share",
      xLabel: `Share of pickups here that ended in each zone, ${format.month(asOf)} (%)`, title: "Where trips from here go",
      subtitle: zone.subtitles.top_destinations, asOf, width, dark}));
    display(html`<p class="nrm-zone-links">Destination pages: ${destinations.map((d, i) => html`${i ? " · " : ""}${
      d.do_zone === zone.zone ? d.name : html`<a href=${siteUrl(`zones/${d.do_zone}`)}>${d.name}</a>`}`)}</p>`);
  } else {
    display(emptyState("No destinations to list", zone.subtitles.top_destinations ?? ""));
  }
}
```

```js
display(howWeMeasured("waits"));
```

<style>
.nrm-zone-crumb {
  color: var(--theme-foreground-muted);
  font-size: 14px;
  margin: 0 0 -0.5rem;
}
.nrm-chart + .nrm-note {
  margin-top: -2rem;
  margin-bottom: 2.5rem;
}
.nrm-zone-links {
  color: var(--theme-foreground-muted);
  font-size: 13px;
  max-width: 760px;
  margin-top: -1.5rem;
}
</style>
