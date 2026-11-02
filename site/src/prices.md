---
title: Prices
---

<!-- L16 · What riders pay per mile and per minute, and where pricing is most volatile (Q7; SPEC §9.1,
     §9.3, D10, D16). Every number, title, subtitle and finding comes from prices.json; the page adds
     none. Two measures sit side by side and are named each time (G4 review): medians of each trip's
     fare per mile, and overall rates (total fares ÷ total miles). Page filters (D34): mode for the
     page, borough by the borough chart, days and time band by the hourly grid; a chart moved off its
     default shows a description of its selection in place of its finding. -->

```js
import {pageHeader, howWeMeasured, emptyState, html, siteUrl} from "./components/page.js";
import {fareRange, hourHeatmap, barChart, choropleth} from "./components/charts.js";
import {tile} from "./components/statTiles.js";
import * as format from "./components/format.js";
import {filterBar, describe, modePhrase, modeOption, list, none, TIME_BANDS, DAY_SETS, bandOption, dayOption, inWeek, timePhrase} from "./components/filters.js";
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

// A chart, or a plain state when the file has no rows or no finding for it, or a filter leaves no rows.
const chartOr = (what, rows, subtitle, draw, filtered = false) =>
  rows?.length && subtitle ? draw() : emptyState(`${what}: no data for ${filtered ? "this selection" : "this month"}`);
```

```js
display(pageHeader(data, tiles, {keys: ["fpm_median", "volatility", "cheapest_hour", "dearest_hour"]}));
display(html`<p class="nrm-note">The median fare per mile and the price volatility cover every trip in ${format.month(latest)}, all modes. The cheapest and dearest hours rank the hours of the week by overall fare per mile (total fares ÷ total miles). Fares are base fares, before tip, tolls, taxes and fees.</p>`);
```

```js
// "All modes" is each chart's default: every mode side by side, or the all-modes rows.
const filters = view(filterBar([
  {key: "mode", label: "Mode", options: ["all", "uber", "lyft", "yellow", "green"], format: modeOption}
]));
```

## Fare per mile by mode

```js
const months = [yearEarlier(latest), latest].filter((m) => data.fpm_by_mode.some((d) => d.month === m));
const fpmRows = months.flatMap((m) => data.fpm_by_mode.filter((d) => d.month === m && MODES.includes(d.mode)).sort(byMode));
const monthLabels = Object.fromEntries(months.map((m) => [m, format.month(m)]));
const fpmShown = filters.changed("mode") ? fpmRows.filter((d) => d.mode === filters.mode) : fpmRows;
const fpmSubtitle = filters.changed("mode")
  ? describe({what: modePhrase(filters.mode), when: list(months.map(format.month))})
  : data.subtitles.fpm_by_mode;
```

```js
chartOr("Fare per mile by mode", fpmShown, fpmSubtitle, () =>
  fareRange(fpmShown, {fy: "month", fyLabels: monthLabels, colors: {all: "accent"},   // Uber's grey sits too close to the text colour
    subtitle: fpmSubtitle, asOf, width, dark}), filters.changed("mode"))
```

```js
display(html`<p class="nrm-note">Medians and percentiles of each trip's base fare ÷ its miles.</p>`);
```

## Fare per minute

```js
const perMinute = data.fpm_by_mode.filter((d) => d.month === latest && MODES.includes(d.mode)
  && (!filters.changed("mode") || d.mode === filters.mode)).sort(byMode);
```

```js
perMinute.length
  ? html`<p>Median fare per minute in ${format.month(latest)}: the middle of each trip's base fare ÷ its minutes, before tip, tolls, taxes and fees.</p>
    <div class="nrm-tiles" style=${filters.changed("mode") ? "grid-template-columns: repeat(auto-fill, minmax(10rem, 1fr))" : null}>${perMinute.map((d) =>
      tile({label: format.modeName(d.mode), unit: "usd_per_minute", yoy: "none"}, d.fpmin_p50, null))}</div>`
  : emptyState("Fare per minute: no data for this month")
```

## By hour of the week

```js
const time = view(filterBar([
  {key: "days", label: "Days", options: Object.keys(DAY_SETS), format: dayOption, radio: true},
  {key: "band", label: "Time of day", options: Object.keys(TIME_BANDS), format: bandOption}
], {label: "Filter the hourly grid"}));
```

```js
// The grid keeps all 168 hours; hours outside the selection stay empty, and the colour scale spans
// the selected hours.
const hourRows = data.fpm_by_hour.filter((d) => d.mode === filters.mode && inWeek(d.hour_of_week, time.days, time.band));
const hourFiltered = filters.changed("mode") || time.changed("days", "band");
const hourSubtitle = hourFiltered
  ? describe({what: modePhrase(filters.mode), when: timePhrase(time.days, time.band)})
  : data.subtitles.fpm_by_hour;
```

```js
chartOr("Fare per mile by hour", hourRows, hourSubtitle, () =>
  hourHeatmap(hourRows, {value: "fare_per_mile", unit: "usd_per_mile", fy: null, zero: false,   // a rate: the scale spans its own range
    legendLabel: `Overall fare per mile, ${modePhrase(filters.mode)} ($/mile)`, subtitle: hourSubtitle, asOf, width, dark}), hourFiltered)
```

```js
display(html`<p class="nrm-note">Each hour's overall fare per mile: total fares ÷ total miles for trips starting in that hour.</p>`);
```

## By borough

```js
const place = view(filterBar([
  {key: "borough", label: "Borough", options: ["all", ...BOROUGHS], format: (b) => (b === "all" ? "All boroughs" : b)}
], {label: "Filter the borough chart"}));
```

```js
const boroughRows = data.fpm_by_borough.filter((d) => BOROUGHS.includes(d.borough));
// A bar per borough for the chosen mode; with a borough chosen, a bar per mode there (or the one
// mode chosen).
const oneBorough = place.borough !== "all";
const boroughShown = oneBorough
  ? boroughRows.filter((d) => d.borough === place.borough && (!filters.changed("mode") || d.mode === filters.mode)).sort(byMode)
  : boroughRows.filter((d) => d.mode === filters.mode);
const boroughFiltered = oneBorough || filters.changed("mode");
const boroughSubtitle = boroughFiltered
  ? describe({what: oneBorough && !filters.changed("mode") ? "every mode" : modePhrase(filters.mode),
      where: oneBorough ? `in ${place.borough}` : "in each borough"})
  : data.subtitles.fpm_by_borough;
const boroughLabel = oneBorough
  ? `Overall fare per mile in ${place.borough}, total fares ÷ total miles ($/mile)`
  : `Overall fare per mile, ${modePhrase(filters.mode)}, total fares ÷ total miles ($/mile)`;
```

```js
chartOr("Fare per mile by borough", boroughShown, boroughSubtitle, () =>
  barChart(boroughShown, {x: "fare_per_mile", y: oneBorough ? "mode" : "borough", unit: "usd_per_mile",
    fill: oneBorough ? "mode" : "accent", xLabel: boroughLabel, subtitle: boroughSubtitle, asOf, width, dark}), boroughFiltered)
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
const boroughTableRows = boroughRows.filter((d) => (!oneBorough || d.borough === place.borough)
  && (!filters.changed("mode") || d.mode === filters.mode));
if (boroughTableRows.length) display(boroughTable(boroughTableRows));
```

## Where prices vary most

```js
// Uber and Lyft pick up in nearly every zone. Many zones have few cab pickups, which makes their
// spread unstable, so the map leaves cabs out; the file keeps their rows. The page's mode picks the
// map: Uber by default (and for all modes), Lyft when chosen.
const volMode = filters.mode === "lyft" ? "lyft" : "uber";
const volMapped = ["all", "uber", "lyft"].includes(filters.mode);
const volRows = data.volatility_by_zone.filter((d) => d.mode === volMode);
// Each mode's map states its own finding; without a Lyft one, the Lyft map describes itself.
const volSubtitle = volMode === "lyft"
  ? data.subtitles.volatility_by_zone_lyft ?? describe({what: "Lyft", where: "in each zone"})
  : data.subtitles.volatility_by_zone;
```

```js
volMapped
  ? chartOr("Price volatility by zone", volRows, volSubtitle, () =>
    choropleth(geo, volRows, {value: "volatility", unit: "ratio", legendLabel: "Price volatility, p90 ÷ p10 fare per mile (×)",
      href: zoneHref, missingLabel: "Too few trips", subtitle: volSubtitle, asOf, width: Math.min(width, 720), dark}))   // a full-width map is taller than the screen
  : emptyState(`Price volatility by zone: not mapped for ${modePhrase(filters.mode)}`,
    "Many zones have few cab pickups, which makes their spread unstable. Choose all modes, Uber or Lyft to see the map.")
```

```js
display(!volMapped ? none() : html`<p class="nrm-note">Each zone's 90th-percentile fare per mile ÷ its 10th, for ${format.modeName(volMode)} trips picked up there in ${format.month(latest)}. Each mode's map has its own colour scale. Hatched zones had too few trips. Cabs are left off the map: many zones have few cab pickups, which makes their spread unstable. Click a zone to open its page.</p>`);
```

```js
howWeMeasured("cleaning", "Fares per mile and per minute use the base fare, before tip, tolls, taxes and fees. Medians are of each trip's own fare per mile; overall rates are total fares ÷ total miles. Definitions, cleaning rules and known limits are on the methods page.")
```
