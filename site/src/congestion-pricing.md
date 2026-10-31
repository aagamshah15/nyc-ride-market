---
title: Congestion pricing
---

<!-- L15 · The congestion-pricing case study (SPEC §9.1, §9.3; Q2, Q3, Q14). Every number, title and
     subtitle comes from congestion.json; the page adds none. The core zone list is the headline and
     the wide list (borderline zones counted as inside) the sensitivity result (D21). Results are
     always worded as estimated effects (CLAUDE.md). -->

```js
import * as format from "./components/format.js";
import {pageHeader, howWeMeasured, siteUrl, html} from "./components/page.js";
import {effectDots, lineChart, monthlyColumns, choropleth, sourceCaption} from "./components/charts.js";
```

```js
const data = FileAttachment("data/congestion.json").json();
const geo = FileAttachment("data/taxi_zones.geojson").json();
const tiles = FileAttachment("data/tiles.json").json();
const events = FileAttachment("data/events.json").json();
```

```js
const asOf = data.as_of_month;

// Panels in reading order: trips first (Q2), then who absorbed the fee (Q3).
const METRICS = ["trips", "fare_per_mile", "driver_share"];
const METRIC_LABELS = {
  trips: "Trips touching the zone",
  fare_per_mile: "Base fare per mile",
  driver_share: "Driver share of the base fare"
};
const MODES = ["all", "ride_hail", "uber", "lyft", "yellow", "green"];
const byMetricAndMode = (a, b) =>
  METRICS.indexOf(a.metric) - METRICS.indexOf(b.metric) || MODES.indexOf(a.mode) - MODES.indexOf(b.mode);

const core = data.effects.filter((d) => d.zone_list === "core").sort(byMetricAndMode);

// The headline weekly series: trips touching the zone, all modes, core list. Weeks left out of the
// summary (holiday weeks that fall differently in the two years) are left off the line too.
const weekly = data.weekly_effect.filter((d) => d.metric === "trips" && d.mode === "all" && d.zone_list === "core");
const excludedWeeks = [...new Set(weekly.filter((d) => d.excluded).map((d) => d.week_start))];
const excludedReasons = [...new Set(data.excluded_weeks.map((d) => d.reason))];

const [firstYear, lastYear] = [Math.min(...data.weekly_trips.map((d) => d.iso_year)), Math.max(...data.weekly_trips.map((d) => d.iso_year))];
const GROUP_LABELS = {treated: "Touching the zone", control: "Elsewhere"};
```

```js
display(pageHeader(data, tiles, {keys: ["trips_effect", "fpm_effect", "fees_to_date"]}));
```

Every result on this page is an estimated effect. It compares the year-on-year change in trips that start or end inside the congestion zone with the year-on-year change in trips elsewhere in the city, week by week. The headline uses the core zone list; counting the borderline zones as inside gives the sensitivity result further down.

## Estimated effects by mode

```js
display(effectDots(core, {fyLabels: METRIC_LABELS, subtitle: data.subtitles.effects, asOf, width, dark}));
```

<p class="nrm-note">Base fare excludes the congestion fee itself, which riders pay on top. Driver share is reported for the ride-hail apps only.</p>

## Week by week

```js
display(lineChart(weekly.filter((d) => !d.excluded), {
  x: "week_start", xType: "week", y: "effect", yUnit: "effect", z: null,
  yLabel: "Estimated effect on trips touching the zone (%)",
  events: events.events, subtitle: data.subtitles.weekly_effect, asOf, width, dark
}));
if (excludedWeeks.length) {
  display(html`<p class="nrm-note">Left out of the summary and off the line: the ${excludedWeeks.map(format.week).join(" and ")}. ${excludedReasons.map((r) => r.replace(/\.?$/, ".")).join(" ")}</p>`);
}
```

```js
display(lineChart(data.weekly_trips.filter((d) => d.mode === "all"), {
  x: "week_start", xType: "week", y: "trips_per_day", yUnit: "count", z: "cbd_group",
  yLabel: "Trips per day in each week", zero: false,
  colors: {treated: "accent", control: "foreground"}, seriesLabel: (k) => GROUP_LABELS[k] ?? k,
  events: events.events, subtitle: data.subtitles.weekly_trips, asOf, width, dark
}));
```

## With and without borderline zones

Some taxi zones straddle the edge of the congestion zone, and a few are islands with no road access, so trips touching them often pay no fee. The core list leaves them out; the wide list counts them as inside. Where the two disagree, read the result with care.

```js
// One block of rows per measure; each row is a mode's median week and range under both lists.
function sensitivityTable(rows) {
  const key = (d) => `${d.metric}|${d.mode}`;
  const wide = new Map(rows.filter((d) => d.zone_list === "wide").map((d) => [key(d), d]));
  const range = (d) => (d ? `${format.effect(d.p10)} to ${format.effect(d.p90)}` : format.NA);
  const rowsCore = rows.filter((d) => d.zone_list === "core").sort(byMetricAndMode);
  const num = "nrm-num", nowrap = "white-space: nowrap";
  return html`<div class="nrm-chart"><figure>
    <div class="nrm-scroll-x"><table class="nrm-compare">
      <thead><tr style=${nowrap}>
        <th>Mode</th>
        <th class=${num}>Core list</th><th class=${num}>Range</th>
        <th class=${num}>With borderline zones</th><th class=${num}>Range</th>
      </tr></thead>
      ${METRICS.map((metric) => html`<tbody>
        <tr><th colspan="5" style="padding-top: 0.75rem">${METRIC_LABELS[metric]}</th></tr>
        ${rowsCore.filter((d) => d.metric === metric).map((d) => {
          const w = wide.get(key(d));
          return html`<tr>
            <td>${format.modeName(d.mode)}</td>
            <td class=${num} style=${nowrap}><strong>${format.effect(d.median)}</strong></td><td class=${num} style=${nowrap}>${range(d)}</td>
            <td class=${num} style=${nowrap}>${format.effect(w?.median)}</td><td class=${num} style=${nowrap}>${range(w)}</td>
          </tr>`;
        })}
      </tbody>`)}
    </table></div>
    <figcaption>${sourceCaption(asOf)}</figcaption>
  </figure></div>`;
}
```

```js
display(sensitivityTable(data.effects));
```

<p class="nrm-note">Each figure is the median week's estimated effect; the range runs across the weeks, as in the chart above.</p>

## Congestion fees

```js
display(monthlyColumns(data.fees, {y: "cbd_fee", unit: "usd", yLabel: "Congestion fees charged ($ per month)",
  subtitle: data.subtitles.fees, asOf, width, dark}));
```

## Where pickups moved

```js
display(choropleth(geo, data.zone_change, {value: "change", unit: "effect", kind: "diverging",
  legendLabel: `Change in pickups per day, ${lastYear} on ${firstYear} (%)`, href: (zone) => siteUrl(`zones/${zone}`),
  subtitle: data.subtitles.zone_change, asOf, width: Math.min(width, 640), dark}));
```

<p class="nrm-note">This map has no comparison group, so it shows where pickups moved, not an estimated effect. Click a zone to open its page.</p>

## Limits

- **Not a randomised test.** The estimate assumes that, without the toll, trips touching the zone and trips elsewhere would have grown alike. Anything else that changed inside the zone and not outside it, such as office attendance, events or transit service, lands in the estimate.
- **Some trips counted as elsewhere pay the toll.** A trip that drives through the zone without starting or ending there can carry the fee, which pulls the estimate towards zero.
- **Riders can move across the line.** A rider who now gets out just outside the zone turns a trip touching the zone into one elsewhere.
- **A mode's comparison group can move for its own reasons.** Where a mode grew very fast outside the zone, or trips shifted between Uber and Lyft, the estimate depends on what the comparison group holds. The all-modes and ride-hail totals are the least exposed.
- **No surge flag and no rider identity** in the trip records, so price changes can't be split from changes in demand.

```js
display(howWeMeasured("congestion-method", "The zone lists, the week-by-week comparison and the full list of limits are on the methods page."));
```
