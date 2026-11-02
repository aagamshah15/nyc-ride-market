---
title: Airports
---

<!-- L16 · Who wins the airport trip, at what fare and when (Q9; SPEC §9.1, §9.3, D10). Every number,
     title, subtitle and finding comes from airports.json; the page adds none. TLC vehicles don't pick
     up at Newark (G4 review), so its pickup rows stay out of the pickup bars and Newark shows as
     drop-offs. Page filters (D34): airport, direction and mode for the page, time of day by the hourly
     chart; a chart moved off its default shows a description of its selection in place of its
     finding. -->

```js
import {pageHeader, howWeMeasured, emptyState, html} from "./components/page.js";
import {Plot, lineChart, stackedBars100, barChart, sourceCaption, tableView} from "./components/charts.js";
import * as format from "./components/format.js";
import * as palette from "./components/palette.js";
import {filterBar, describe, modePhrase, modePossessive, modeOption, none, TIME_BANDS, bandOption, inBand, hourRange} from "./components/filters.js";
import {explainer} from "./components/notes.js";
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

// A chart, or a plain state when the file has no rows or no finding for it, or a filter leaves no rows.
const chartOr = (what, rows, subtitle, draw, filtered = false) =>
  rows?.length && subtitle ? draw() : emptyState(`${what}: no data for ${filtered ? "this selection" : "this month"}`);
const capital = (text) => text[0].toUpperCase() + text.slice(1);
```

```js
display(pageHeader(data, tiles, {keys: ["trips_per_day", "yellow_share", "fare_to_manhattan_mean", "busiest_hour"]}));
const fareAirports = [...new Set(data.fares.map((d) => d.airport))];
if (fareAirports.length) display(html`<p class="nrm-note">The mean fare to Manhattan is what riders paid before tip, including tolls, taxes and fees, on trips from ${list(fareAirports)} taken together. The busiest hour is for an average day.</p>`);
```

```js
// How airport trips work (D33): Port Authority and TLC rules written here; the busiest hour from JSON.
display(explainer({
  title: "How do airport trips work?",
  body: html`<p>JFK and LaGuardia are in Queens, inside the city: yellow cabs serve their taxi stands, and app riders meet their cars at set pickup areas. Newark is in New Jersey, outside the TLC's area, so TLC vehicles can drop passengers off there, but their pickup records at Newark aren't TLC trips and are left out; Newark counts drop-offs only. Yellow cabs between JFK and Manhattan charge a flat fare, while other airport trips run on the meter or the app's price.</p>`,
  notes: [
    "Newark: drop-offs only in TLC data",
    "JFK to Manhattan by yellow cab: a flat fare",
    `Busiest hour on an average day: ${format.hourOfDay(data.tiles.busiest_hour)}`
  ]
}));
```

```js
const filters = view(filterBar([
  {key: "airport", label: "Airport", options: ["all", ...airports], format: (a) => (a === "all" ? "All airports" : airportName(a))},
  {key: "direction", label: "Direction", options: ["both", "to", "from"], radio: true,
    format: (d) => ({both: "Both ways", to: "To airport", from: "From airport"})[d]},
  {key: "mode", label: "Mode", options: ["all", "uber", "lyft", "yellow", "green"], format: modeOption}
]));
```

```js
const {airport, direction, mode} = filters;
const oneAirport = airport !== "all";
const byPlace = (d) => (!oneAirport || d.airport === airport) && (direction === "both" || d.direction === direction);
// "to and from the airports", "from JFK": where a selection's trips go.
const place = (all = "the airports") =>
  `${({both: "to and from", to: "to", from: "from"})[direction]} ${oneAirport ? airportName(airport) : all}`;
// The selection asks for pickups where TLC vehicles don't pick up: a fresh state for each chart.
const noPickups = direction === "from" && NO_PICKUPS.has(airport)
  ? () => emptyState(`No pickups at ${airportName(airport)} Airport`, "TLC vehicles don't pick up there, so it appears as drop-offs only.")
  : null;
```

## Who carries airport trips

```js
const split = data.split.filter((d) => !(d.direction === "from" && NO_PICKUPS.has(d.airport)));
// With a mode chosen, one bar per airport and direction holds that mode's share.
const splitShown = split.filter(byPlace);
const modeShares = splitShown.filter((d) => d.mode === mode)
  .map((d) => ({...d, bar: `${d.direction === "from" ? "Pickups" : "Drop-offs"} at ${airportName(d.airport)}`}));
const splitFiltered = filters.changed("airport", "direction", "mode");
const splitSubtitle = splitFiltered
  ? describe({what: `${filters.changed("mode") ? modePossessive(mode) : "each mode's"} share of trips`, where: place("each airport")})
  : data.subtitles.split;
```

```js
noPickups?.() ?? (filters.changed("mode")
  ? chartOr("Airport trips by mode", modeShares, splitSubtitle, () =>
    barChart(modeShares, {x: "share", y: "bar", unit: "share", fill: "mode", sort: false,
      xLabel: `${capital(modePossessive(mode))} share of the airport's trips in the month (%)`, subtitle: splitSubtitle, asOf, width, dark}), true)
  : chartOr("Airport trips by mode", splitShown, splitSubtitle, () =>
    stackedBars100(splitShown, {y: "airport", yLabels: AIRPORTS, fy: "direction", fyLabels: DIRECTIONS,
      xLabel: "Share of the airport's trips in the month (%)", subtitle: splitSubtitle, asOf, width, dark}), splitFiltered))
```

```js
display(dropoffOnly.some((a) => splitShown.some((d) => d.airport === a)) ? html`<p class="nrm-note">TLC vehicles don't pick up at ${list(dropoffOnly)} Airport, so it appears as drop-offs only.</p>` : none());
```

```js
// Yellow cabs by default (the finding); a chosen mode replaces them.
const trendMode = filters.changed("mode") ? mode : "yellow";
```

## ${`${modeOption(trendMode)} over time`}

```js
const yellowTrend = data.share_trend.filter((d) => d.mode === trendMode && (!oneAirport || d.airport === airport));
const trendLabel = (code) => airportName(code);
const trendFiltered = filters.changed("airport", "mode");
const trendSubtitle = trendFiltered
  ? describe({what: `${modePossessive(trendMode)} share of trips`, where: `at ${oneAirport ? airportName(airport) : "each airport"}`})
  : data.subtitles.share_trend;
const trendLabelY = trendMode === "yellow" ? "Yellow-cab share of the airport's trips (%)" : `${capital(modePossessive(trendMode))} share of the airport's trips (%)`;
```

```js
chartOr(`${modeOption(trendMode)} share`, yellowTrend, trendSubtitle, () =>
  lineChart(yellowTrend, {z: "airport", y: "share", yUnit: "share", yLabel: trendLabelY,
    colors: {JFK: "accent", LGA: "foreground", EWR: "other_hv"}, seriesLabel: trendLabel,
    subtitle: trendSubtitle, asOf, width, dark}), trendFiltered)
```

```js
display(dropoffOnly.some((a) => yellowTrend.some((d) => d.airport === a))
  ? html`<p class="nrm-note">Pickups and drop-offs together; ${list(dropoffOnly)} counts drop-offs only.</p>`
  : filters.changed("direction")
  ? html`<p class="nrm-note">Pickups and drop-offs together: the monthly shares have no split by direction.</p>`
  : none());
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
```

```js
const time = view(filterBar([
  {key: "band", label: "Time of day", options: Object.keys(TIME_BANDS), format: bandOption}
], {label: "Filter the hourly chart"}));
```

```js
// The default sums every row, as the finding does. A filtered view leaves out Newark's pickup
// records, which aren't TLC trips (G4 review), and keeps one mode's line when a mode is chosen.
const hourFiltered = filters.changed("airport", "direction", "mode") || time.changed("band");
const hourly = hourFiltered
  ? byHour(data.by_hour.filter((d) => byPlace(d) && !(d.direction === "from" && NO_PICKUPS.has(d.airport)) && inBand(d.hour, time.band)))
    .filter((d) => !filters.changed("mode") || d.mode === mode)
  : byHour(data.by_hour);
const hourSubtitle = hourFiltered
  ? describe({what: "trips", where: `${place()}${filters.changed("mode") ? ` by ${modePhrase(mode)}` : ""}`,
      when: TIME_BANDS[time.band] ? hourRange(TIME_BANDS[time.band]) : ""})
  : data.subtitles.by_hour;
```

```js
noPickups?.() ?? chartOr("Airport trips by hour", hourly, hourSubtitle, () =>
  // On phones the long axis label runs into the "6 pm" tick, so it shortens there.
  lineChart(hourly, {x: "hour", xType: "hour", xLabel: width < 480 ? "Hour" : "Hour of day", y: "trips_per_day", yUnit: "count",
    yLabel: "Trips in that hour, average day", colors: {all: "accent"},   // Uber's grey sits too close to the text colour
    subtitle: hourSubtitle, asOf, width, dark}), hourFiltered)
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
  const panel = (airport) => {
    const rows = data.filter((d) => d.airport === airport);
    const labels = new Map(rows.map((d, i) => [d, format.usdGroup(rows.map((r) => r.fare_mean))[i]]));
    return Plot.plot({
    width, height: 30 * modes.length + 36, marginTop: 4, marginLeft: 16 + longestMode * 7,
    marginRight: 12 + longestValue * 7, marginBottom: 24,
    style: {fontFamily: "var(--sans-serif)", fontSize: "12px", overflow: "visible"},
    x: {domain: [0, max], nice: true, label: null, grid: true, tickFormat: format.axis("usd")},
    y: {type: "band", domain: modes, label: null, tickSize: 0, tickFormat: format.modeName, padding: 0.25},
    color: palette.seriesScale(modes, dark),
    marks: [
      Plot.barX(rows, {x: "fare_mean", y: "mode", fill: "mode", tip: true,
        title: (d) => `${format.modeName(d.mode)} from ${airportName(d.airport)}\n${format.usd(d.fare_mean)} mean fare before tip`}),
      Plot.ruleX([0], {stroke: "currentColor"}),
      Plot.text(rows, {x: "fare_mean", y: "mode", text: (d) => labels.get(d), dx: 5, textAnchor: "start", fill: "currentColor"})
    ]
  });
  };
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
const fares = data.fares.filter((d) => !NO_PICKUPS.has(d.airport))   // trips from the airport are pickups there
  .filter((d) => (!oneAirport || d.airport === airport) && (!filters.changed("mode") || d.mode === mode));
const faresFiltered = filters.changed("airport", "mode");
const faresSubtitle = faresFiltered
  ? describe({what: "fares", where: [filters.changed("mode") ? `by ${modePhrase(mode)}` : "",
      `from ${oneAirport ? airportName(airport) : "each airport"}`, "to Manhattan"].filter(Boolean).join(" ")})
  : data.subtitles.fares;
```

```js
noPickups?.() ?? (direction === "to"
  ? emptyState("Fares to Manhattan: trips from the airport only", "The fares are for trips from the airport into Manhattan. Choose both ways or from the airport to see them.")
  : NO_PICKUPS.has(airport)
  ? emptyState(`Fares to Manhattan: none from ${airportName(airport)} Airport`, "TLC vehicles don't pick up there, so there are no trips from it to Manhattan.")
  : chartOr("Fares to Manhattan", fares, faresSubtitle, () =>
    fareBars(fares, {subtitle: faresSubtitle, asOf, width, dark}), faresFiltered))
```

```js
display(html`<p class="nrm-note">Means are total fares ÷ trips. The fare before tip includes tolls, taxes and fees; the base fare in the table doesn't.</p>`);
```

```js
howWeMeasured("cleaning", "Airport trips are pickups or drop-offs in the airport's taxi zone. Fares are before tip. Definitions, cleaning rules and known limits are on the methods page.")
```
