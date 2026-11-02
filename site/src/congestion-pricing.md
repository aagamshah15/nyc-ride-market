---
title: Congestion pricing
---

<!-- L15 · The congestion-pricing case study (SPEC §9.1, §9.3; Q2, Q3, Q14). Every number, title and
     subtitle comes from congestion.json; the page adds none. The core zone list is the headline and
     the wide list (borderline zones counted as inside) the sensitivity result (D21). Results are
     always worded as estimated effects (CLAUDE.md). Page filters (D34): mode, measure and zone list;
     the wide list draws against the core list, so the sensitivity shows on the charts. A chart moved
     off its default shows a description of its selection in place of its finding. -->

```js
import * as format from "./components/format.js";
import {pageHeader, howWeMeasured, siteUrl, emptyState, html} from "./components/page.js";
import {effectDots, lineChart, monthlyColumns, choropleth, sourceCaption} from "./components/charts.js";
import {filterBar, describe, modePhrase, modeOption} from "./components/filters.js";
```

```js
const data = FileAttachment("data/congestion.json").json();
const geo = FileAttachment("data/taxi_zones.geojson").json();
const tiles = FileAttachment("data/tiles.json").json();
const events = FileAttachment("data/events.json").json();
// The published congestion-zone list, for the map's outline of the core zones.
const quality = FileAttachment("data/quality.json").json();
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

// Measures as a sentence names them, and the weekly chart's axis for each.
const METRIC_PHRASES = {
  trips: "trips touching the zone",
  fare_per_mile: "the base fare per mile",
  driver_share: "the driver share of the base fare"
};
const ZONE_LISTS = {core: "Core list", wide: "With borderline zones"};
const excludedReasons = [...new Set(data.excluded_weeks.map((d) => d.reason))];

const [firstYear, lastYear] = [Math.min(...data.weekly_trips.map((d) => d.iso_year)), Math.max(...data.weekly_trips.map((d) => d.iso_year))];
const GROUP_LABELS = {treated: "Touching the zone", control: "Elsewhere"};
const coreZones = (quality.cbd_zones ?? []).filter((z) => !z.borderline).map((z) => z.zone);
```

```js
display(pageHeader(data, tiles, {keys: ["trips_effect", "fpm_effect", "fees_to_date"]}));
```

```js
// The defaults are the headline: every measure and mode, the core zone list. "Core and wide" draws
// the wide list (borderline zones counted as inside) against the core list.
const filters = view(filterBar([
  {key: "mode", label: "Mode", options: MODES, format: modeOption},
  {key: "measure", label: "Measure", options: ["all", ...METRICS],
    format: (m) => ({all: "All measures", trips: "Trips", fare_per_mile: "Fare per mile", driver_share: "Driver share"})[m]},
  {key: "zones", label: "Zone list", options: ["core", "wide"], radio: true, format: (z) => ({core: "Core only", wide: "Core and wide"})[z]}
]));
```

```js
const {mode, measure} = filters;
const wide = filters.changed("zones");
const lists = wide ? ["core", "wide"] : ["core"];
const pick = (d) => (!filters.changed("mode") || d.mode === mode) && (measure === "all" || d.metric === measure) && lists.includes(d.zone_list);
const pair = wide ? {key: "zone_list", values: ["core", "wide"], labels: {core: "Core list", wide: "With borderline zones (wide list)"}} : null;
const versus = wide ? "core list against the wide list" : "";

const core = data.effects.filter(pick).sort(byMetricAndMode);
const effectsSubtitle = filters.changed("mode", "measure", "zones")
  ? describe({what: measure === "all" ? "estimated effects" : `the estimated effect on ${METRIC_PHRASES[measure]}`,
      where: filters.changed("mode") ? `for ${modePhrase(mode)}` : "by mode", when: versus})
  : data.subtitles.effects;

// The headline weekly series: trips touching the zone, all modes, core list; another measure or mode
// when chosen. Weeks left out of the summary (holiday weeks that fall differently in the two years)
// are left off the line too, which breaks there rather than joining across them.
const weeklyMetric = measure === "all" ? "trips" : measure;
const weekly = data.weekly_effect.filter((d) => d.metric === weeklyMetric && d.mode === mode && lists.includes(d.zone_list));
const excludedWeeks = [...new Set(weekly.filter((d) => d.excluded).map((d) => d.week_start))];
const weeklyFiltered = weeklyMetric !== "trips" || filters.changed("mode", "zones");
const weeklySubtitle = weeklyFiltered
  ? describe({what: `the weekly estimated effect on ${METRIC_PHRASES[weeklyMetric]}`, where: `for ${modePhrase(mode)}`, when: versus})
  : data.subtitles.weekly_effect;

// Driver pay is in the ride-hail records only, so a cab has no driver-share rows.
const noRows = (what) => emptyState(`${what}: no data for this selection`,
  measure === "driver_share" ? "Driver share is reported for the ride-hail apps only." : "");
```

Every result on this page is an estimated effect. It compares the year-on-year change in trips that start or end inside the congestion zone with the year-on-year change in trips elsewhere in the city, week by week. The headline uses the core zone list; counting the borderline zones as inside gives the sensitivity result further down.

## Estimated effects by mode

```js
// All modes takes the one palette colour no row here uses: the text colour would match Uber's.
display(core.length
  ? effectDots(core, {fyLabels: METRIC_LABELS, colors: {all: "other_hv"}, pair, subtitle: effectsSubtitle, asOf, width, dark})
  : noRows("Estimated effects"));
```

<p class="nrm-note">Base fare excludes the congestion fee itself, which riders pay on top. Driver share is reported for the ride-hail apps only.</p>

## Week by week

```js
display(weekly.length
  ? lineChart(weekly.map((d) => (d.excluded ? {...d, effect: null} : d)), {
    x: "week_start", xType: "week", y: "effect", yUnit: "effect", gaps: true,
    // With both lists, a line each: the core list in the accent, the wide list in the text colour.
    z: wide ? "zone_list" : null, colors: {core: "accent", wide: "foreground"}, seriesLabel: (k) => ZONE_LISTS[k] ?? k,
    yLabel: `Estimated effect on ${METRIC_PHRASES[weeklyMetric].replace(/^the /, "")} (%)`,
    events: events.events, subtitle: weeklySubtitle, asOf, width, dark
  })
  : noRows("Weekly estimated effect"));
if (weekly.length && excludedWeeks.length) {
  display(html`<p class="nrm-note">Left out of the summary and off the line: the ${excludedWeeks.map(format.week).join(" and ")}. ${excludedReasons.map((r) => r.replace(/\.?$/, ".")).join(" ")}</p>`);
}
```

```js
// The groups' trips are published for all modes and the ride-hail apps together (and cabs together),
// not for each company.
const groupMode = ["all", "ride_hail"].includes(mode) ? mode : null;
const groupSubtitle = filters.changed("mode")
  ? describe({what: "trips per day", where: `by ${modePhrase(mode)}, touching the zone and elsewhere`})
  : data.subtitles.weekly_trips;
display(groupMode
  ? lineChart(data.weekly_trips.filter((d) => d.mode === groupMode), {
    x: "week_start", xType: "week", y: "trips_per_day", yUnit: "count", z: "cbd_group",
    yLabel: "Trips per day in each week", zero: false,
    colors: {treated: "accent", control: "foreground"}, seriesLabel: (k) => GROUP_LABELS[k] ?? k,
    events: events.events, subtitle: groupSubtitle, asOf, width, dark
  })
  : emptyState(`Trips per day touching the zone and elsewhere: not published for ${modePhrase(mode)}`,
    "These weekly counts are published for all modes and for the ride-hail apps together."));
if (groupMode && wide) display(html`<p class="nrm-note">Trips touching the zone are counted on the core list here.</p>`);
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
      ${METRICS.filter((metric) => rowsCore.some((d) => d.metric === metric)).map((metric) => html`<tbody>
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
const sensitivityRows = data.effects.filter((d) => (!filters.changed("mode") || d.mode === mode) && (measure === "all" || d.metric === measure));
display(sensitivityRows.length ? sensitivityTable(sensitivityRows) : noRows("Core and wide lists"));
```

<p class="nrm-note">Each figure is the median week's estimated effect; the range runs across the weeks, as in the chart above.</p>

## Congestion fees

```js
const RIDE_HAIL = ["uber", "lyft"];
const fees = data.fees.filter((d) => !filters.changed("mode") || d.mode === mode || (mode === "ride_hail" && RIDE_HAIL.includes(d.mode)));
const feesSubtitle = filters.changed("mode")
  ? describe({what: "congestion fees", where: `on trips by ${modePhrase(mode)}`})
  : data.subtitles.fees;
display(fees.length
  ? monthlyColumns(fees, {y: "cbd_fee", unit: "usd", yLabel: "Congestion fees charged ($ per month)",
    events: events.events, subtitle: feesSubtitle, asOf, width, dark})
  : emptyState("Congestion fees: no data for this selection"));
```

## Where pickups moved

```js
display(choropleth(geo, data.zone_change, {value: "change", unit: "effect", kind: "diverging",
  legendLabel: `Change in pickups per day, ${lastYear} on ${firstYear} (%)`, href: (zone) => siteUrl(`zones/${zone}`),
  outline: {zones: coreZones, label: "Congestion zone (core list)"}, subtitle: data.subtitles.zone_change, asOf, width: Math.min(width, 640), dark}));
```

<p class="nrm-note">This map has no comparison group, so it shows where pickups moved, not an estimated effect. The outline marks the taxi zones on the congestion zone's core list. ${filters.changed("mode") ? "It counts pickups by every mode, whatever the filter. " : ""}Click a zone to open its page.</p>

## Limits

- **Not a randomised test.** The estimate assumes that, without the toll, trips touching the zone and trips elsewhere would have grown alike. Anything else that changed inside the zone and not outside it, such as office attendance, events or transit service, lands in the estimate.
- **Some trips counted as elsewhere pay the toll.** A trip that drives through the zone without starting or ending there can carry the fee, which pulls the estimate towards zero.
- **Riders can move across the line.** A rider who now gets out just outside the zone turns a trip touching the zone into one elsewhere.
- **A mode's comparison group can move for its own reasons.** Where a mode grew very fast outside the zone, or trips shifted between Uber and Lyft, the estimate depends on what the comparison group holds. The all-modes and ride-hail totals are the least exposed.
- **No surge flag and no rider identity** in the trip records, so price changes can't be split from changes in demand.

```js
display(howWeMeasured("congestion-method", "The zone lists, the week-by-week comparison and the full list of limits are on the methods page."));
```
