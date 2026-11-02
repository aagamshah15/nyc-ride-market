---
title: Zones
---

```js
// /zones (D13; L14): the city-wide zone maps (Q1, Q10) and a searchable table linking to each
// zone page. Every number, title and subtitle comes from zones/index.json. Thin zones
// (flags.thin, Newark Airport included) are left out of the maps, so they draw hatched.
// Page filters (D34): borough and a pick of zones; the maps fade the zones outside the selection and
// the tables list only the selection, with a description of it in place of the finding.
import * as format from "../components/format.js";
import {choropleth, sourceCaption} from "../components/charts.js";
import {pageHeader, howWeMeasured, siteUrl, emptyState, html} from "../components/page.js";
import {filterBar, describe} from "../components/filters.js";
```

```js
const index = FileAttachment("../data/zones/index.json").json();
const geo = FileAttachment("../data/taxi_zones.geojson").json();
const tiles = FileAttachment("../data/tiles.json").json();
```

```js
const asOf = index.as_of_month;
const label = (key) => tiles.tiles[key].label;
const zoneHref = (zone) => siteUrl(`zones/${zone}`);
const mapped = index.rows.filter((d) => !d.thin);
const thinLabel = "Too few trips";
const thinNames = [...new Set(index.rows.filter((d) => d.thin).map((d) => d.name))];
const yellowLeadsAll = mapped.filter((d) => d.top_mode === "yellow").sort((a, b) => b.yellow_share - a.yellow_share);
```

```js
display(pageHeader(index, tiles, {keys: ["zones_yellow_leads", "zones_lyft_beats_uber", "zones_rh_share_up"]}));
```

```js
// The city's boroughs (Newark Airport, in New Jersey, is in the airport pick) and the airport zones:
// Newark, JFK and LaGuardia.
const BOROUGHS = ["Bronx", "Brooklyn", "Manhattan", "Queens", "Staten Island"];
const AIRPORT_ZONES = [1, 132, 138];
const filters = view(filterBar([
  {key: "borough", label: "Borough", options: ["all", ...BOROUGHS], format: (b) => (b === "all" ? "All boroughs" : b)},
  {key: "zones", label: "Zones", options: ["all", "cbd", "airports"], radio: true,
    format: (z) => ({all: "All zones", cbd: "Congestion zone", airports: "Airports"})[z]}
]));
```

```js
const inSelection = (d) => (filters.borough === "all" || d.borough === filters.borough)
  && (filters.zones === "all" || (filters.zones === "cbd" ? d.cbd : AIRPORT_ZONES.includes(d.zone)));
const zoneFiltered = filters.changed("borough", "zones");
const selected = index.rows.filter(inSelection);
const focus = zoneFiltered ? selected.map((d) => d.zone) : null;
const yellowLeads = yellowLeadsAll.filter(inSelection);
const selection = {
  what: ({all: "zones", cbd: "zones inside the congestion zone", airports: "the airport zones"})[filters.zones],
  where: filters.borough === "all" ? "" : `in ${filters.borough}`
};
// A map's finding, or what it shows when filtered.
const mapSubtitle = (finding) => (zoneFiltered ? describe({...selection, when: "other zones faded"}) : finding);
const noZones = () => emptyState(`No ${selection.what.replace(/^the /, "")} ${selection.where}`.trim(), "Choose another borough or set of zones.");
```

## How each zone rides

<div class="nrm-pair">
  <div>${selected.length ? resize((width) => choropleth(geo, mapped, {value: "rh_share", unit: "share", legendLabel: "Ride-hail share of pickups (%)",
    title: "Ride-hail share of pickups", subtitle: mapSubtitle(index.subtitles.level_map), href: zoneHref, missingLabel: thinLabel, focus, asOf, width, dark})) : noZones()}</div>
  <div>${selected.length ? resize((width) => choropleth(geo, mapped, {value: "share_change_yoy", unit: "share", kind: "diverging",
    legendLabel: "Change in ride-hail share vs a year earlier (pts)", title: "Change in ride-hail share",
    subtitle: mapSubtitle(index.subtitles.change_map), href: zoneHref, missingLabel: thinLabel, focus, asOf, width, dark})) : noZones()}</div>
</div>

```js
display(html`<p class="nrm-note">Hatched zones had too few trips in the month to map: ${thinNames.join(", ")}. Click a zone to open its page.</p>`);
```

## Where yellow cabs still lead

<div class="nrm-pair">
  <div>${selected.length ? resize((width) => choropleth(geo, mapped, {value: "yellow_share", unit: "share", legendLabel: "Yellow-cab share of pickups (%)",
    title: "Yellow-cab share of pickups", subtitle: mapSubtitle(index.subtitles.yellow_map), href: zoneHref, missingLabel: thinLabel, focus, asOf, width, dark})) : noZones()}</div>
  <div class="nrm-chart"><figure>
    <h2>${label("zones_yellow_leads")}</h2>
    <div class="nrm-scroll-x"><table class="nrm-zone-leads">
      <thead><tr><th>Zone</th><th class="nrm-num">${label("yellow_share")}</th><th class="nrm-num">Change vs a year earlier</th><th class="nrm-num">${label("rh_share")}</th></tr></thead>
      <tbody>${yellowLeads.length ? "" : html`<tr><td colspan="4">None in this selection</td></tr>`}${yellowLeads.map((d) => html`<tr>
        <td><a href=${zoneHref(d.zone)}>${d.name}</a></td>
        <td class="nrm-num">${format.share(d.yellow_share)}</td>
        <td class="nrm-num">${format.shareChange(d.yellow_share_change_yoy)}</td>
        <td class="nrm-num">${format.share(d.rh_share)}</td>
      </tr>`)}</tbody>
    </table></div>
    <figcaption>${sourceCaption(asOf)}</figcaption>
  </figure></div>
</div>

## Every zone

```js
// A plain table rather than Inputs.table: Framework loads the Inputs stylesheet only for the
// unpinned import, so the pinned Inputs from page.js renders unstyled (see the L14 brief).
function zoneTable(rows) {
  const columns = [
    {key: "name", label: "Zone", sort: (d) => d.name.toLowerCase()},
    {key: "borough", label: "Borough", f: format.borough, text: true, sort: (d) => format.borough(d.borough).toLowerCase()},
    {key: "trips_per_day", label: label("trips_per_day"), f: format.count},
    {key: "rh_share", label: label("rh_share"), f: format.share},
    {key: "share_change_yoy", label: "Change vs a year earlier", f: format.shareChange},
    {key: "yellow_share", label: label("yellow_share"), f: format.share},
    {key: "wait_p50", label: label("wait_p50"), f: format.seconds}
  ].map((c) => ({...c, numeric: Boolean(c.f) && !c.text, sort: c.sort ?? ((d) => d[c.key])}));
  // Thin zones show no figures, like their grey on the maps.
  const blank = Object.fromEntries(columns.filter((c) => c.numeric).map((c) => [c.key, null]));
  const data = rows.map((d) => (d.thin ? {...d, ...blank} : d));
  let sortBy = columns.find((c) => c.key === "trips_per_day"), descending = true;
  const input = html`<input type="search" class="nrm-zone-search" placeholder="Search by zone or borough" aria-label="Search zones by name or borough">`;
  const status = html`<span class="nrm-zone-count" aria-live="polite"></span>`;
  const tbody = html`<tbody>`;
  const heads = columns.map((c) => {
    const th = html`<th class=${c.numeric ? "nrm-num" : ""}><button type="button">${c.label}</button></th>`;
    th.querySelector("button").onclick = () => {
      descending = sortBy === c ? !descending : c.numeric;
      sortBy = c;
      render();
    };
    return th;
  });
  function render() {
    const q = input.value.trim().toLowerCase();
    const shown = data.filter((d) => !q || d.name.toLowerCase().includes(q) || format.borough(d.borough).toLowerCase().includes(q));
    const key = sortBy.sort;
    shown.sort((a, b) => {
      const [x, y] = [key(a), key(b)];
      if (x == null || y == null) return (x == null) - (y == null);   // empty cells last either way
      return (x < y ? -1 : x > y ? 1 : 0) * (descending ? -1 : 1);
    });
    heads.forEach((th, i) => th.setAttribute("aria-sort", columns[i] === sortBy ? (descending ? "descending" : "ascending") : "none"));
    status.textContent = `${format.count(shown.length)} of ${format.count(data.length)} zones`;
    tbody.replaceChildren(...shown.map((d) => html`<tr>
      <td><a href=${zoneHref(d.zone)}>${d.name}</a>${d.thin ? html` <span class="nrm-zone-thin">Too few trips</span>` : ""}</td>
      ${columns.slice(1).map((c) => html`<td class=${c.numeric ? "nrm-num" : ""}>${c.f ? c.f(d[c.key]) : d[c.key]}</td>`)}
    </tr>`));
  }
  input.oninput = render;
  render();
  return html`<div class="nrm-zone-table">
    <div class="nrm-zone-tools">${input}${status}</div>
    <div class="nrm-table-scroll"><table><thead><tr>${heads}</tr></thead>${tbody}</table></div>
  </div>`;
}
```

<div class="nrm-chart"><figure>
  <h3>${zoneFiltered ? describe(selection) : index.subtitles.table}</h3>
  ${selected.length ? zoneTable(selected) : noZones()}
  <figcaption>${sourceCaption(asOf)} · The median wait is for ride-hail only: cab records have no request time. Click a column to sort it.</figcaption>
</figure></div>

```js
display(howWeMeasured("cleaning"));
```

<style>
.nrm-zone-leads {
  margin: 0;
  min-width: 22rem;
}
.nrm-zone-thin {
  color: var(--theme-foreground-muted);
  font-size: 12px;
  white-space: nowrap;
}
.nrm-zone-tools {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem 1rem;
}
.nrm-zone-search {
  font: inherit;
  font-size: 14px;
  width: min(100%, 20rem);
  padding: 0.35rem 0.5rem;
  border: solid 1px var(--theme-foreground-faint);
  border-radius: var(--nrm-radius);
  background: var(--theme-background);
  color: var(--theme-foreground);
}
.nrm-zone-count {
  color: var(--theme-foreground-muted);
  font-size: 13px;
}
.nrm-zone-table .nrm-table-scroll {
  max-height: 32rem;
}
.nrm-zone-table table {
  font-size: 14px;
}
.nrm-zone-table th {
  vertical-align: bottom;
}
.nrm-zone-table th.nrm-num {
  min-width: 4.5rem;
}
.nrm-zone-table td.nrm-num {
  white-space: nowrap;
}
.nrm-zone-table th button {
  all: unset;
  cursor: pointer;
}
.nrm-zone-table th button:focus-visible {
  outline: 2px solid var(--theme-foreground-focus);
  outline-offset: 2px;
}
.nrm-zone-table th[aria-sort="ascending"] button::after {
  content: " ▲";
  font-size: 10px;
}
.nrm-zone-table th[aria-sort="descending"] button::after {
  content: " ▼";
  font-size: 10px;
}
</style>
