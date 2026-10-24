---
title: Component gallery
draft: true
index: false
toc: true
---

<!-- Dev only (L05): every component on mock data, at /dev/components under `make site-dev`.
     `draft: true` keeps it out of every build, so it never ships and CI needs no site data for it. -->

```js
import * as palette from "../components/palette.js";
import * as format from "../components/format.js";
import {statTiles} from "../components/statTiles.js";
import {lineChart, shareLine, choropleth, hourHeatmap, effectDots, fareRange, fareStrip, stackedBars100,
  barChart, monthlyColumns, Plot} from "../components/charts.js";
import {pageHeader, howWeMeasured, notReported, tooFewTrips, emptyState, compareTable, findingsList,
  html} from "../components/page.js";
```

```js
const tiles = FileAttachment("../data/tiles.json").json();
const events = FileAttachment("../data/events.json").json();
const home = FileAttachment("../data/home.json").json();
const shareMonthly = FileAttachment("../data/share_monthly.json").json();
const uber = FileAttachment("../data/companies/uber.json").json();
const yellow = FileAttachment("../data/companies/yellow.json").json();
const zonesIndex = FileAttachment("../data/zones/index.json").json();
const zone = FileAttachment("../data/zones/132.json").json();
const thinZone = FileAttachment("../data/zones/37.json").json();
const geo = FileAttachment("../data/taxi_zones.geojson").json();
const congestion = FileAttachment("../data/congestion.json").json();
const drivers = FileAttachment("../data/drivers.json").json();
const airports = FileAttachment("../data/airports.json").json();
const prices = FileAttachment("../data/prices.json").json();
```

# Component gallery

Every helper in `site/src/components/`, drawn from `make site-mock` data. Check it in light and dark mode, at phone width and on a desktop.

## Page header

`pageHeader(data, tiles)`: mock banner, the generated title and the stat row.

```js
display(pageHeader(home, tiles));
```

## Stat tiles

Null states: a metric a mode doesn't report, and a zone with too few trips.

```js
display(statTiles(yellow, tiles));
```

```js
display(statTiles(thinZone, tiles));
```

```js
display(statTiles(drivers, tiles));
```

## Palette

Mode colours in the current scheme, in the fixed order; then the sequential and diverging ramps.

```js
display(html`<div style="display: flex; flex-wrap: wrap; gap: 0.75rem; font: 13px var(--sans-serif)">
  ${[...palette.modeOrder, ...palette.groupOrder].map((key) => html`<div style="display: flex; align-items: center; gap: 0.4rem">
    <span style=${{display: "inline-block", width: "1rem", height: "1rem", borderRadius: "3px", background: palette.color(key, dark)}}></span>${format.modeName(key)}
  </div>`)}
</div>`);
```

```js
display(Plot.legend({color: {...palette.sequentialScale(dark), domain: [0, 1], label: "Sequential (level maps, heatmaps)"}, width: 320}));
display(Plot.legend({color: {...palette.divergingScale(dark), domain: [-1, 1], label: "Diverging, centred on 0 (change maps)"}, width: 320}));
```

## Share over time

```js
display(shareLine(shareMonthly.rows, {events: events.events, subtitle: home.subtitles.share_trend, asOf: home.as_of_month, width, dark}));
```

## Line charts

```js
display(lineChart(drivers.driver_share_trend, {y: "driver_share", yUnit: "share", yLabel: "Driver share of fare (%)", zero: false,
  events: events.events, subtitle: drivers.subtitles.driver_share_trend, asOf: drivers.as_of_month, width, dark}));
```

Pay-rise event study: the year as the series, the reference year in the muted colour, and a labelled rule at the transition week.

```js
display(lineChart(drivers.event_study.filter((d) => d.mode === "ride_hail"), {
  x: "week_offset", xType: "number", xLabel: "Weeks from the pay rise", y: "pay_per_mile", yUnit: "usd_per_mile",
  yLabel: "Driver pay per mile ($/mile)", z: "year", colors: {2025: "accent", 2024: "muted"}, seriesLabel: String, zero: false,
  rules: [{x: 0, label: "Transition week"}], subtitle: drivers.subtitles.event_study, asOf: drivers.as_of_month, width, dark}));
```

```js
display(lineChart(zone.waits.by_hour, {x: "hour", xType: "hour", xLabel: "Hour of day", y: "wait_mean", yUnit: "seconds",
  yLabel: "Mean wait (minutes)", subtitle: zone.subtitles.waits, asOf: zone.as_of_month, width, dark}));
```

TLC-reported figures carry the indicators caption.

```js
display(lineChart(drivers.hours, {y: "trips_per_hour_worked", yUnit: "trips_per_hour", yLabel: "Trips per hour worked (TLC-reported)",
  z: "license_class", colors: {"FHV - High Volume": "ride_hail", Yellow: "yellow", Green: "green"}, seriesLabel: String, zero: false,
  dataset: "monthly indicators", subtitle: drivers.subtitles.hours, asOf: drivers.tlc_as_of_month, width, dark}));
```

## Zone maps

```js
display(choropleth(geo, zonesIndex.rows, {value: "rh_share", unit: "share", legendLabel: "Ride-hail share of trips (%)",
  subtitle: zonesIndex.subtitles.level_map, asOf: zonesIndex.as_of_month, width, dark}));
```

```js
display(choropleth(geo, zonesIndex.rows, {value: "share_change_yoy", unit: "share", kind: "diverging",
  legendLabel: "Change in ride-hail share vs a year earlier (pts)", subtitle: zonesIndex.subtitles.change_map,
  asOf: zonesIndex.as_of_month, width, dark}));
```

```js
display(choropleth(geo, congestion.zone_change, {value: "change", unit: "effect", kind: "diverging",
  legendLabel: "Pickups per day, 2025 vs 2024 (%)", subtitle: congestion.subtitles.zone_change, asOf: congestion.as_of_month, width, dark}));
```

## Hour × weekday

```js
display(hourHeatmap(zone.hour_heatmap, {legendLabel: "Average trips per week", subtitle: zone.subtitles.hour_heatmap,
  asOf: zone.as_of_month, width, dark}));
```

## Policy effects

```js
display(effectDots(congestion.effects.filter((d) => d.zone_list === "core"), {
  fyLabels: {trips: "Zone trips", fare_per_mile: "Fare per mile", driver_share: "Driver share of fare"},
  subtitle: congestion.subtitles.effects, asOf: congestion.as_of_month, width, dark}));
```

## Price spread

```js
const latestFpm = prices.fpm_by_mode.filter((d) => d.month === prices.fpm_by_mode.at(-1).month);
display(fareRange(latestFpm, {subtitle: prices.subtitles.fpm_by_mode, asOf: prices.as_of_month, width, dark}));
```

```js
display(fareStrip(prices.volatility_by_zone, {subtitle: prices.subtitles.volatility_by_zone, asOf: prices.as_of_month, width, dark}));
```

## Airport split

```js
display(stackedBars100(airports.split, {fy: "direction", fyLabels: {from: "Trips from the airport", to: "Trips to the airport"},
  subtitle: airports.subtitles.split, asOf: airports.as_of_month, width, dark}));
```

## Bars

```js
display(barChart(zone.top_destinations, {x: "trips", y: "name", unit: "count", xLabel: "Trips in the latest month",
  subtitle: zone.subtitles.top_destinations, asOf: zone.as_of_month, width, dark}));
```

```js
display(barChart(airports.fares.filter((d) => d.airport === "JFK"), {x: "fare_mean", y: "mode", unit: "usd", fill: "mode",
  xLabel: "Mean rider fare to Manhattan, excluding tip ($)", subtitle: airports.subtitles.fares, asOf: airports.as_of_month, width, dark}));
```

## Monthly columns

```js
display(monthlyColumns(congestion.fees, {y: "cbd_fee", unit: "usd", yLabel: "Congestion fees collected ($)",
  subtitle: congestion.subtitles.fees, asOf: congestion.as_of_month, width, dark}));
```

## Comparison block

```js
display(compareTable(yellow.compare, tiles, {current: "yellow"}));
```

## Findings

```js
display(findingsList(home.findings, {featuredOnly: true}));
```

## Null states

```js
display(notReported("Wheelchair-accessible match rate"));
display(tooFewTrips("Wait percentiles"));
display(emptyState("No shared-ride data", "This mode has no shared requests in the period."));
```

## Methods link

```js
display(howWeMeasured("congestion-method"));
```
