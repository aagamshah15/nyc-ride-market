---
title: Drivers
---

<!-- L15 · Driver pay, driver share of the fare and hours worked (SPEC §9.1, §9.3; Q5, Q6, Q15). Every
     number, title and subtitle comes from drivers.json and events.json; the page adds none. Pay is per
     hour with a passenger. The August event is the new minimum-pay rule (D28); its event study marks
     the transition week (D12) and draws the year before as the seasonal reference. -->

```js
import * as format from "./components/format.js";
import * as palette from "./components/palette.js";
import {pageHeader, howWeMeasured, html} from "./components/page.js";
import {lineChart, Plot, sourceCaption, tableView} from "./components/charts.js";
```

```js
const data = FileAttachment("data/drivers.json").json();
const tiles = FileAttachment("data/tiles.json").json();
const events = FileAttachment("data/events.json").json();
```

```js
const asOf = data.as_of_month;
const eventById = (id) => events.events.find((e) => e.id === id);
const payRule = eventById("driver_pay_rise");
const inflationStep = eventById("driver_pay_inflation_step");
const CLASS_LABELS = {"FHV - High Volume": "Ride-hail apps", Yellow: "Yellow cabs", Green: "Green cabs"};
const CLASSES = Object.keys(CLASS_LABELS);
// Series in the site's order (ride-hail, then yellow, then green): the chart keeps the rows' order.
const hours = [...data.hours].sort((a, b) => CLASSES.indexOf(a.license_class) - CLASSES.indexOf(b.license_class));
```

```js
display(pageHeader(data, tiles, {keys: ["pay_per_hour", "driver_share", "trips_per_hour_worked", "active_drivers"]}));
display(html`<p class="nrm-note">Pay and driver share cover Uber and Lyft: TLC's cab records carry no driver pay. Pay per hour counts hours with a passenger only, not time spent waiting for a trip. TLC-reported figures come from TLC's monthly indicators, latest month ${format.month(data.tlc_as_of_month)}.</p>`);
```

## Driver share of the fare

```js
display(lineChart(data.driver_share_trend, {y: "driver_share", yUnit: "share", yLabel: "Driver share of the base fare (%)", zero: false,
  events: events.events, subtitle: data.subtitles.driver_share_trend, asOf, width, dark}));
```

## Pay per hour with a passenger

```js
display(lineChart(data.pay_per_hour_trend, {y: "pay_per_hour", yUnit: "usd_per_hour", yLabel: "Driver pay per hour with a passenger ($/hour)",
  zero: false, events: events.events, subtitle: data.subtitles.pay_per_hour_trend, asOf, width, dark}));
```

## The new minimum-pay rule

```js
if (payRule) {
  display(html`<p>The ${payRule.label.toLowerCase()} took effect in ${format.month(payRule.date)}. It lowered the per-mile pay floor and raised the per-minute floor.${inflationStep ? html` An earlier inflation step, in ${format.month(inflationStep.date)}, raised only the per-minute floor.` : null} The chart follows ride-hail pay and fares week by week around the rule, against the same weeks a year earlier.</p>`);
}
```

```js
// One figure, two panels on a shared week axis: fare per mile and driver pay per mile share a $/mile
// axis; pay per minute gets its own panel (no dual axes). Solid lines are the rule's year, dashed lines
// the same weeks a year earlier (the seasonal reference). The shaded week is the transition week.
const FONT = {fontFamily: "var(--sans-serif)", fontSize: "12px", overflow: "visible"};
const SURFACE = "var(--theme-background)";
const HALO = {stroke: SURFACE, strokeWidth: 4, paintOrder: "stroke"};

function eventStudy(rows, {subtitle, asOf, event, width = 640, dark = palette.isDark()}) {
  const years = [...new Set(rows.map((d) => d.year))].sort();
  const year = years.at(-1), refYear = years[0];
  const series = [
    {key: "fare_per_mile", label: "Base fare per mile", panel: "mile", color: palette.color("accent", dark)},
    {key: "pay_per_mile", label: "Driver pay per mile", panel: "mile", color: palette.color("foreground", dark)},
    {key: "pay_per_min", label: "Driver pay per minute", panel: "minute", color: palette.color("foreground", dark)}
  ];
  const offsets = rows.map((d) => d.week_offset);
  const [x0, x1] = [Math.min(...offsets), Math.max(...offsets)];
  const transition = [...new Set(rows.filter((d) => d.transition).map((d) => d.week_offset))];
  const signed = (v) => (v > 0 ? `+${v}` : v < 0 ? `−${-v}` : "0");
  const dashed = {strokeDasharray: "5,4", strokeWidth: 1.5, strokeOpacity: 0.75};

  const panel = (name, unit, yLabel, height, label) => {
    const lines = series.filter((s) => s.panel === name);
    const long = lines.flatMap((s) => rows.filter((d) => d[s.key] != null).map((d) => ({...d, series: s.label, value: d[s.key]})));
    return Plot.plot({
      width, height, marginTop: 24, marginRight: 16, marginBottom: 26, marginLeft: 48, style: FONT,
      x: {domain: [x0 - 0.5, x1 + 0.5], label: null, ticks: offsets.filter((v) => v % 4 === 0), tickFormat: signed},
      y: {label: yLabel, labelArrow: "none", grid: true, nice: true, zero: false, tickFormat: format.axis(unit)},
      marks: [
        Plot.rect(transition, {x1: (d) => d - 0.5, x2: (d) => d + 0.5, fill: palette.color("muted", dark), fillOpacity: 0.5}),
        // Beside the band rather than over it, clear of the y-axis label at the top left.
        label ? Plot.text(transition, {x: (d) => d + 0.5, text: () => label, frameAnchor: "top", lineAnchor: "bottom", dy: -4, dx: 3,
          textAnchor: "start", fill: "currentColor", fontSize: 11, ...HALO}) : null,
        ...lines.flatMap((s) => [
          Plot.line(rows.filter((d) => d.year === refYear), {x: "week_offset", y: s.key, stroke: s.color, ...dashed}),
          Plot.line(rows.filter((d) => d.year === year), {x: "week_offset", y: s.key, stroke: s.color, strokeWidth: 2,
            strokeLinejoin: "round", strokeLinecap: "round"})
        ]),
        Plot.tip(long, Plot.pointer({x: "week_offset", y: "value",
          title: (d) => `${d.series}, ${format.week(d.week_start)}\n${format.value(unit, d.value)}${d.transition ? "\nTransition week" : ""}`}))
      ]
    });
  };

  const swatch = (color, isDashed) => html`<svg width="26" height="10" aria-hidden="true" style="vertical-align: middle; margin-right: 0.35rem"><line x1="1" x2="25" y1="5" y2="5" stroke=${color} stroke-width="2" stroke-dasharray=${isDashed ? "5,4" : "none"}></line></svg>`;
  const key = (items) => html`<div style="display: flex; flex-wrap: wrap; gap: 0.25rem 1.25rem; font: 12px var(--sans-serif); margin: 0 0 0.5rem">${items.map(([color, isDashed, text]) => html`<span>${swatch(color, isDashed)}${text}</span>`)}</div>`;
  const legend = html`${key(series.filter((s) => s.panel === "mile").map((s) => [s.color, false, s.label]))}${key([
    ["currentColor", false, String(year)],
    ["currentColor", true, `Same weeks of ${refYear}, the seasonal reference`]
  ])}`;

  const table = tableView([...rows].sort((a, b) => b.year - a.year || a.week_offset - b.week_offset), [
    {key: "year", label: "Year", format: "text"},
    {key: "week_offset", label: "Weeks from the rule", format: signed},
    {key: "week_start", label: "Week", format: "week"},
    {key: "fare_per_mile", label: "Base fare per mile", format: "usd_per_mile"},
    {key: "pay_per_mile", label: "Driver pay per mile", format: "usd_per_mile"},
    {key: "pay_per_min", label: "Driver pay per minute", format: "usd_per_minute"},
    {key: "transition", label: "Transition week", format: (v) => (v ? "Yes" : "")}
  ]);

  return html`<div class="nrm-chart"><figure>
    <h3>${subtitle}</h3>
    ${legend}
    <div class="nrm-facet">
      <div class="nrm-facet-label">Fare and pay per mile</div>
      ${panel("mile", "usd_per_mile", "Dollars per mile ($/mile)", width < 480 ? 220 : 260, "Transition week")}
    </div>
    <div class="nrm-facet">
      <div class="nrm-facet-label">Pay per minute with a passenger</div>
      ${panel("minute", "usd_per_minute", "Dollars per minute ($/min)", width < 480 ? 170 : 190, null)}
    </div>
    <div class="nrm-axis-label">Weeks before (−) and after (+) the ${event ? event.label.toLowerCase() : "rule"}</div>
    <figcaption>${sourceCaption(asOf)}</figcaption>
  </figure>${table}</div>`;
}
```

```js
display(eventStudy(data.event_study.filter((d) => d.mode === "ride_hail"), {subtitle: data.subtitles.event_study, asOf, event: payRule, width, dark}));
```

<p class="nrm-note">The shaded week straddles the rule's first day, so it is drawn but left out of the before-and-after comparison. Pay per minute counts minutes with a passenger.</p>

## Hours on the road

```js
display(lineChart(hours, {y: "trips_per_hour_worked", yUnit: "trips_per_hour", yLabel: "Trips per hour worked (TLC-reported)",
  z: "license_class", colors: {"FHV - High Volume": "ride_hail", Yellow: "yellow", Green: "green"}, seriesLabel: (k) => CLASS_LABELS[k] ?? k,
  events: events.events, dataset: "monthly indicators", subtitle: data.subtitles.hours, asOf: data.tlc_as_of_month, width, dark}));
```

```js
display(howWeMeasured("pay-rise-method", "Pay per hour counts hours with a passenger only, and driver pay is reported for the ride-hail apps only. Definitions, the event-study weeks and known limits are on the methods page."));
```
