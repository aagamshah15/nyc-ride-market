// Page-only helpers for companies/[company].md (L13). The shared kit in ../components has no
// scatter and no row of plain count tiles, so these build them from its pieces: the pinned Plot,
// tile(), the chart frame classes, the source caption and the table view. Colours come only
// from palette.js, numbers only from the company file.

import {Plot, sourceCaption, tableView} from "../components/charts.js";
import {html} from "../components/page.js";
import {tile} from "../components/statTiles.js";
import * as format from "../components/format.js";
import * as palette from "../components/palette.js";

const SURFACE = "var(--theme-background)";
const HALO = {stroke: SURFACE, strokeWidth: 4, paintOrder: "stroke"};
const FONT = {fontFamily: "var(--sans-serif)", fontSize: "12px", overflow: "visible"};
const LEGEND = {style: {fontFamily: "var(--sans-serif)", fontSize: "12px"}};

const byMode = (a, b) => palette.modeOrder.indexOf(a.mode) - palette.modeOrder.indexOf(b.mode);

/** The latest `month` in a list of monthly rows ("" for none). */
export function latestMonth(rows) {
  return rows.reduce((latest, d) => (d.month > latest ? d.month : latest), "");
}

/** The same month a year earlier: "2025-08-01" from "2026-08-01". */
export function yearEarlier(month) {
  const date = format.utcDate(month);
  date.setUTCFullYear(date.getUTCFullYear() - 1);
  return date.toISOString().slice(0, 10);
}

/** Rows for the same month a year earlier and the latest month, in that order, plus facet labels. */
export function latestAndYearEarlier(rows) {
  const latest = latestMonth(rows);
  const months = [yearEarlier(latest), latest].filter((m) => rows.some((d) => d.month === m));
  return {
    rows: months.flatMap((m) => rows.filter((d) => d.month === m)),
    labels: Object.fromEntries(months.map((m) => [m, format.month(m)]))
  };
}

/** Series labels for the tip chart: cab series carry "card-only" (rows flag `card_only`). */
export function tipSeriesLabel(rows) {
  const cardOnly = new Set(rows.filter((d) => d.card_only).map((d) => d.mode));
  return (mode) => (cardOnly.has(mode) ? `${format.modeName(mode)}, card-only` : format.modeName(mode));
}

/**
 * One count tile per app for the latest month, e.g. completed trips that requested a
 * wheelchair-accessible vehicle. A count with no change line: the file carries no year-earlier
 * change for it, and the page computes none.
 */
export function countTiles(rows, field, what) {
  const month = latestMonth(rows);
  const now = rows.filter((d) => d.month === month).sort(byMode);
  return html`<div class="nrm-tiles">${now.map((d) =>
    tile({label: `${format.modeName(d.mode)}: ${what}, ${format.month(month)}`, unit: "count", yoy: "none"}, d[field], null)
  )}</div>`;
}

/**
 * Q4: each zone's gap (Lyft's share of the zone's pickups minus Uber's) against its change on a
 * year earlier, from `lyft_vs_uber.by_zone`. Right of zero Lyft leads; above zero Lyft gained.
 * Rows flagged `thin` (too few trips, left out of the published count) draw hollow and unlabelled.
 */
export function gapScatter(rows, {subtitle, asOf, width = 640, dark = palette.isDark()} = {}) {
  if (!subtitle || !asOf) throw new Error("gapScatter: the subtitle and asOf options are required");
  const data = rows.filter((d) => d.gap != null && d.gap_change != null);
  const counted = (d) => d.thin !== true;
  const leader = (d) => (d.gap > 0 ? "lyft" : "uber");
  const leads = {uber: "Uber has the bigger share", lyft: "Lyft has the bigger share"};
  const color = {...palette.seriesScale(["uber", "lyft"], dark), tickFormat: (k) => leads[k]};
  const r = width < 480 ? 2.5 : 3.5;

  // Name the zones the finding rests on: where Lyft leads, the widest gaps first.
  const xs = data.map((d) => d.gap);
  const middle = (Math.min(...xs) + Math.max(...xs)) / 2;
  const named = data.filter((d) => d.gap > 0 && counted(d)).sort((a, b) => b.gap - a.gap).slice(0, 5);
  const label = (anchor, keep) => Plot.text(named.filter(keep), {
    x: "gap", y: "gap_change", text: "name", lineWidth: 12, textAnchor: anchor, dx: anchor === "end" ? -7 : 7,
    fill: "currentColor", fontSize: 11, ...HALO
  });

  const tipTitle = (d) => [
    d.name,
    `Lyft ${format.share(d.lyft_share)} · Uber ${format.share(d.uber_share)} of pickups`,
    `Gap ${format.shareChange(d.gap)}, ${format.shareChange(d.gap_change)} vs a year earlier`,
    ...(counted(d) ? [] : ["Too few trips to count"])
  ].join("\n");

  const plot = Plot.plot({
    width, height: width < 480 ? 300 : 360, marginTop: 24, marginRight: 16, marginBottom: 28, marginLeft: 48, style: FONT,
    x: {label: null, grid: true, nice: true, tickFormat: format.axis("pts")},
    y: {label: "Change in the gap vs a year earlier (pts)", labelArrow: "none", grid: true, nice: true, tickFormat: format.axis("pts")},
    color,
    marks: [
      Plot.ruleX([0], {stroke: "currentColor", strokeOpacity: 0.5}),
      Plot.ruleY([0], {stroke: "currentColor", strokeOpacity: 0.5}),
      Plot.dot(data.filter((d) => counted(d) && d.gap <= 0), {x: "gap", y: "gap_change", fill: leader, r, fillOpacity: 0.6}),
      Plot.dot(data.filter((d) => counted(d) && d.gap > 0), {x: "gap", y: "gap_change", fill: leader, r: r + 1}),
      Plot.dot(data.filter((d) => !counted(d)), {x: "gap", y: "gap_change", stroke: leader, fill: SURFACE, r}),
      label("end", (d) => d.gap > middle),
      label("start", (d) => d.gap <= middle),
      Plot.tip(data, Plot.pointer({x: "gap", y: "gap_change", title: tipTitle}))
    ]
  });

  const note = data.some((d) => !counted(d))
    ? html`<p class="nrm-note" style="margin: 0.5rem 0 0">Hollow dots are zones with too few trips in the month to count.</p>`
    : null;
  const table = tableView([...data].sort((a, b) => b.gap - a.gap), [
    {key: "name", label: "Zone", format: "text"},
    {key: "lyft_share", label: "Lyft share of pickups", format: "share"},
    {key: "uber_share", label: "Uber share of pickups", format: "share"},
    {key: "gap", label: "Gap (pts)", format: format.shareChange},
    {key: "gap_change", label: "Change vs a year earlier (pts)", format: format.shareChange}
  ]);
  return html`<div class="nrm-chart"><figure>
    <h3>${subtitle}</h3>
    ${plot.legend("color", LEGEND)}
    ${plot}
    <div class="nrm-axis-label">Lyft's share of the zone's pickups minus Uber's (pts)</div>
    ${note}
    <figcaption>${sourceCaption(asOf)}</figcaption>
  </figure>${table}</div>`;
}
