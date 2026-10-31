---
title: Prices
---

<!-- L16 · What riders pay per mile and per minute, and where pricing is most volatile (Q7; SPEC §9.1,
     §9.3, D10, D16). Every number, title, subtitle and finding comes from prices.json; the page adds
     none. Two measures sit side by side and are named each time (G4 review): medians of each trip's
     fare per mile, and overall rates (total fares ÷ total miles). -->

```js
import {pageHeader, howWeMeasured, emptyState, html, Inputs, siteUrl} from "./components/page.js";
import {fareRange, hourHeatmap, barChart, choropleth} from "./components/charts.js";
import {tile} from "./components/statTiles.js";
import * as format from "./components/format.js";
```

```js
const data = FileAttachment("data/prices.json").json();
const geo = FileAttachment("data/taxi_zones.geojson").json();
const tiles = FileAttachment("data/tiles.json").json();
```

```js
const asOf = data.as_of_month;
// Companies and all modes; the ride-hail group row stays in the file.
const MODES = ["uber", "lyft", "yellow", "green", "other_hv", "all"];
// The city's boroughs: Newark Airport's pickup records aren't TLC trips (G4 review), and "N/A" is
// pickups outside the city.
const BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"];
const zoneHref = (zone) => siteUrl(`zones/${zone}`);

const latest = data.fpm_by_mode.reduce((m, d) => (d.month > m ? d.month : m), "");
const yearEarlier = (month) => {
  const date = format.utcDate(month);
  date.setUTCFullYear(date.getUTCFullYear() - 1);
  return date.toISOString().slice(0, 10);
};
const byMode = (a, b) => MODES.indexOf(a.mode) - MODES.indexOf(b.mode);

// A chart, or a plain state when the file has no rows or no finding for it.
const chartOr = (what, rows, subtitle, draw) =>
  rows?.length && subtitle ? draw() : emptyState(`${what}: no data for this month`);
```

```js
display(pageHeader(data, tiles, {keys: ["fpm_median", "volatility", "cheapest_hour", "dearest_hour"]}));
display(html`<p class="nrm-note">The median fare per mile and the price volatility cover every trip in ${format.month(latest)}, all modes. The cheapest and dearest hours rank the hours of the week by overall fare per mile (total fares ÷ total miles). Fares are base fares, before tip, tolls, taxes and fees.</p>`);
```

## Fare per mile by mode

```js
const months = [yearEarlier(latest), latest].filter((m) => data.fpm_by_mode.some((d) => d.month === m));
const fpmRows = months.flatMap((m) => data.fpm_by_mode.filter((d) => d.month === m && MODES.includes(d.mode)).sort(byMode));
const monthLabels = Object.fromEntries(months.map((m) => [m, format.month(m)]));
```

```js
chartOr("Fare per mile by mode", fpmRows, data.subtitles.fpm_by_mode, () =>
  fareRange(fpmRows, {fy: "month", fyLabels: monthLabels, colors: {all: "accent"},   // Uber's grey sits too close to the text colour
    subtitle: data.subtitles.fpm_by_mode, asOf, width, dark}))
```

```js
display(html`<p class="nrm-note">Medians and percentiles of each trip's base fare ÷ its miles.</p>`);
```

## Fare per minute

```js
const perMinute = data.fpm_by_mode.filter((d) => d.month === latest && MODES.includes(d.mode)).sort(byMode);
```

```js
perMinute.length
  ? html`<p>Median fare per minute in ${format.month(latest)}: the middle of each trip's base fare ÷ its minutes, before tip, tolls, taxes and fees.</p>
    <div class="nrm-tiles nrm-minute-tiles">${perMinute.map((d) =>
      tile({label: format.modeName(d.mode), unit: "usd_per_minute", yoy: "none"}, d.fpmin_p50, null))}</div>`
  : emptyState("Fare per minute: no data for this month")
```

## By hour of the week

```js
const hourRows = data.fpm_by_hour.filter((d) => d.mode === "all");
```

```js
chartOr("Fare per mile by hour", hourRows, data.subtitles.fpm_by_hour, () =>
  hourHeatmap(hourRows, {value: "fare_per_mile", unit: "usd_per_mile", fy: null,
    legendLabel: "Overall fare per mile, all modes ($/mile)", subtitle: data.subtitles.fpm_by_hour, asOf, width, dark}))
```

```js
display(html`<p class="nrm-note">Each hour's overall fare per mile: total fares ÷ total miles for trips starting in that hour.</p>`);
```

## By borough

```js
const boroughRows = data.fpm_by_borough.filter((d) => BOROUGHS.includes(d.borough));
const boroughAll = boroughRows.filter((d) => d.mode === "all");
```

```js
chartOr("Fare per mile by borough", boroughAll, data.subtitles.fpm_by_borough, () =>
  barChart(boroughAll, {x: "fare_per_mile", y: "borough", unit: "usd_per_mile",
    xLabel: "Overall fare per mile, all modes, total fares ÷ total miles ($/mile)",
    subtitle: data.subtitles.fpm_by_borough, asOf, width, dark}))
```

```js
// Every mode in each borough, per mile and per minute, as a second disclosure under the chart.
function boroughTable(rows) {
  const sorted = BOROUGHS.flatMap((b) => rows.filter((d) => d.borough === b).sort(byMode));
  return html`<details class="nrm-table"><summary>Every mode, per mile and per minute</summary>
    <div class="nrm-table-scroll"><table>
      <thead><tr><th>Borough</th><th>Mode</th><th class="nrm-num">Overall fare per mile</th><th class="nrm-num">Overall fare per minute</th></tr></thead>
      <tbody>${sorted.map((d) => html`<tr>
        <td>${d.borough}</td><td>${format.modeName(d.mode)}</td>
        <td class="nrm-num">${format.usdPerMile(d.fare_per_mile)}</td>
        <td class="nrm-num">${format.usdPerMinute(d.fare_per_min)}</td>
      </tr>`)}</tbody>
    </table></div>
  </details>`;
}
```

```js
display(html`<p class="nrm-note">By pickup borough. Trips picked up outside the city or at Newark Airport are left out.</p>`);
if (boroughRows.length) display(boroughTable(boroughRows));
```

## Where prices vary most

```js
// Uber and Lyft pick up in nearly every zone. Many zones have few cab pickups, which makes their
// spread unstable, so the map leaves cabs out; the file keeps their rows.
const mapModes = ["uber", "lyft"].filter((m) => data.volatility_by_zone.some((d) => d.mode === m));
const volMode = view(Inputs.radio(mapModes, {label: "Mode", value: mapModes[0], format: format.modeName}));
```

```js
const volRows = data.volatility_by_zone.filter((d) => d.mode === volMode);
```

```js
chartOr("Price volatility by zone", volRows, data.subtitles.volatility_by_zone, () =>
  choropleth(geo, volRows, {value: "volatility", unit: "ratio", legendLabel: "Price volatility, p90 ÷ p10 fare per mile (×)",
    href: zoneHref, subtitle: data.subtitles.volatility_by_zone, asOf, width: Math.min(width, 720), dark}))   // a full-width map is taller than the screen
```

```js
display(html`<p class="nrm-note">Each zone's 90th-percentile fare per mile ÷ its 10th, for ${format.modeName(volMode)} trips picked up there in ${format.month(latest)}. Each mode's map has its own colour scale. Grey zones had too few trips. Cabs are left off the map: many zones have few cab pickups, which makes their spread unstable. Click a zone to open its page.</p>`);
```

```js
howWeMeasured("cleaning", "Fares per mile and per minute use the base fare, before tip, tolls, taxes and fees. Medians are of each trip's own fare per mile; overall rates are total fares ÷ total miles. Definitions, cleaning rules and known limits are on the methods page.")
```

<style>
/* Five small tiles: two to a row on phones rather than the stat row's one. */
@media (max-width: 639.98px) {
  .nrm-tiles.nrm-minute-tiles {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
