---
title: Airports
---

<!-- L16 · Who wins the airport trip, at what fare and when (Q9; SPEC §9.1, §9.3, D10). Every number,
     title, subtitle and finding comes from airports.json; the page adds none. TLC vehicles don't pick
     up at Newark (G4 review), so its pickup rows stay out of the pickup bars and Newark shows as
     drop-offs. -->

```js
import {pageHeader, howWeMeasured, emptyState, html} from "./components/page.js";
import {Plot, lineChart, stackedBars100, sourceCaption, tableView} from "./components/charts.js";
import * as format from "./components/format.js";
import * as palette from "./components/palette.js";
```

```js
const data = FileAttachment("data/airports.json").json();
const tiles = FileAttachment("data/tiles.json").json();
```

```js
const asOf = data.as_of_month;
const AIRPORTS = {JFK: "JFK", LGA: "LaGuardia", EWR: "Newark"};
const airportName = (code) => AIRPORTS[code] ?? code;
const DIRECTIONS = {from: "Pickups at the airport", to: "Drop-offs at the airport"};
// Pickup records there aren't TLC trips (G4 review; publish.py NO_PICKUP_SHARES): drop-offs only.
const NO_PICKUPS = new Set(["EWR"]);

const airports = [...new Set(data.split.map((d) => d.airport))];
const dropoffOnly = airports.filter((a) => NO_PICKUPS.has(a));
const list = (codes) => codes.map(airportName).reduce((s, name, i, all) =>
  i === 0 ? name : `${s}${i === all.length - 1 ? " and " : ", "}${name}`, "");

// A chart, or a plain state when the file has no rows or no finding for it.
const chartOr = (what, rows, subtitle, draw) =>
  rows?.length && subtitle ? draw() : emptyState(`${what}: no data for this month`);
```

```js
display(pageHeader(data, tiles, {keys: ["trips_per_day", "yellow_share", "fare_to_manhattan_mean", "busiest_hour"]}));
const fareAirports = [...new Set(data.fares.map((d) => d.airport))];
if (fareAirports.length) display(html`<p class="nrm-note">The mean fare to Manhattan is what riders paid before tip, including tolls, taxes and fees, on trips from ${list(fareAirports)} taken together. The busiest hour is for an average day.</p>`);
```

## Who carries airport trips

```js
const split = data.split.filter((d) => !(d.direction === "from" && NO_PICKUPS.has(d.airport)));
```

```js
chartOr("Airport trips by mode", split, data.subtitles.split, () =>
  stackedBars100(split, {y: "airport", yLabels: AIRPORTS, fy: "direction", fyLabels: DIRECTIONS,
    xLabel: "Share of the airport's trips in the month (%)", subtitle: data.subtitles.split, asOf, width, dark}))
```

```js
if (dropoffOnly.length) display(html`<p class="nrm-note">TLC vehicles don't pick up at ${list(dropoffOnly)} Airport, so it appears as drop-offs only.</p>`);
```

## Yellow cabs over time

```js
const yellowTrend = data.share_trend.filter((d) => d.mode === "yellow");
const trendLabel = (code) => airportName(code);
```

```js
chartOr("Yellow-cab share", yellowTrend, data.subtitles.share_trend, () =>
  lineChart(yellowTrend, {z: "airport", y: "share", yUnit: "share", yLabel: "Yellow-cab share of the airport's trips (%)",
    colors: {JFK: "accent", LGA: "foreground", EWR: "other_hv"}, seriesLabel: trendLabel,
    subtitle: data.subtitles.share_trend, asOf, width, dark}))
```

```js
if (dropoffOnly.some((a) => yellowTrend.some((d) => d.airport === a))) {
  display(html`<p class="nrm-note">Pickups and drop-offs together; ${list(dropoffOnly)} counts drop-offs only.</p>`);
}
```

## When airport trips happen

```js
// Trips per day in each hour, summed over airports and directions: a line per mode and one for
// all modes, the total the finding names.
function byHour(rows) {
  const sums = new Map();
  const add = (hour, mode, v) => {
    const key = `${hour}|${mode}`;
    sums.set(key, {hour, mode, trips_per_day: (sums.get(key)?.trips_per_day ?? 0) + (v ?? 0)});
  };
  for (const d of rows) {
    add(d.hour, d.mode, d.trips_per_day);
    add(d.hour, "all", d.trips_per_day);
  }
  return [...sums.values()].sort((a, b) => a.hour - b.hour);
}
const hourly = byHour(data.by_hour);
```

```js
chartOr("Airport trips by hour", hourly, data.subtitles.by_hour, () =>
  // On phones the long axis label runs into the "6 pm" tick, so it shortens there.
  lineChart(hourly, {x: "hour", xType: "hour", xLabel: width < 480 ? "Hour" : "Hour of day", y: "trips_per_day", yUnit: "count",
    yLabel: "Trips in that hour, average day", colors: {all: "accent"},   // Uber's grey sits too close to the text colour
    subtitle: data.subtitles.by_hour, asOf, width, dark}))
```

## Fares to Manhattan

```js
// Mean fare per trip, before tip, from each airport to Manhattan: a panel per airport with a bar
// per mode on one shared axis. The kit's barChart draws a single panel, so this builds the same
// bars from the pinned Plot, tableView and source caption.
function fareBars(rows, {subtitle, asOf, width = 640, dark = palette.isDark()}) {
  const data = rows.filter((d) => d.fare_mean != null);
  const modes = palette.modeOrder.filter((m) => data.some((d) => d.mode === m));
  const xLabel = "Mean fare per trip to Manhattan, before tip ($)";
  const max = Math.max(...data.map((d) => d.fare_mean));
  const longestMode = Math.max(...modes.map((m) => format.modeName(m).length));
  const longestValue = Math.max(...data.map((d) => format.usd(d.fare_mean).length));
  const panel = (airport) => Plot.plot({
    width, height: 30 * modes.length + 36, marginTop: 4, marginLeft: 16 + longestMode * 7,
    marginRight: 12 + longestValue * 7, marginBottom: 24,
    style: {fontFamily: "var(--sans-serif)", fontSize: "12px", overflow: "visible"},
    x: {domain: [0, max], nice: true, label: null, grid: true, tickFormat: format.axis("usd")},
    y: {type: "band", domain: modes, label: null, tickSize: 0, tickFormat: format.modeName, padding: 0.25},
    color: palette.seriesScale(modes, dark),
    marks: [
      Plot.barX(data.filter((d) => d.airport === airport), {x: "fare_mean", y: "mode", fill: "mode", tip: true,
        title: (d) => `${format.modeName(d.mode)} from ${airportName(d.airport)}\n${format.usd(d.fare_mean)} mean fare before tip`}),
      Plot.ruleX([0], {stroke: "currentColor"}),
      Plot.text(data.filter((d) => d.airport === airport), {x: "fare_mean", y: "mode", text: (d) => format.usd(d.fare_mean),
        dx: 5, textAnchor: "start", fill: "currentColor"})
    ]
  });
  const panels = [...new Set(data.map((d) => d.airport))].map((a) => html`<div class="nrm-facet">
    <div class="nrm-facet-label">From ${airportName(a)}</div>
    ${panel(a)}
  </div>`);
  const table = tableView(data, [
    {key: "airport", label: "Airport", format: airportName},
    {key: "mode", label: "Mode", format: "mode"},
    {key: "fare_mean", label: "Mean fare before tip", format: "usd"},
    {key: "fare_base_mean", label: "Mean base fare", format: "usd"},
    {key: "fare_per_mile", label: "Base fare per mile (total ÷ total miles)", format: "usd_per_mile"},
    {key: "trips_per_day", label: "Trips per day", format: "count"}
  ]);
  return html`<div class="nrm-chart"><figure>
    <h3>${subtitle}</h3>
    ${panels}
    <div class="nrm-axis-label">${xLabel}</div>
    <figcaption>${sourceCaption(asOf)}</figcaption>
  </figure>${table}</div>`;
}
```

```js
const fares = data.fares.filter((d) => !NO_PICKUPS.has(d.airport));   // trips from the airport are pickups there
```

```js
chartOr("Fares to Manhattan", fares, data.subtitles.fares, () =>
  fareBars(fares, {subtitle: data.subtitles.fares, asOf, width, dark}))
```

```js
display(html`<p class="nrm-note">Means are total fares ÷ trips. The fare before tip includes tolls, taxes and fees; the base fare in the table doesn't.</p>`);
```

```js
howWeMeasured("cleaning", "Airport trips are pickups or drop-offs in the airport's taxi zone. Fares are before tip. Definitions, cleaning rules and known limits are on the methods page.")
```
