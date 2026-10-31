// Chart helpers (SPEC §9.4). Every helper returns a figure with a finding subtitle, axis labels
// with units, the source caption and a table view of the data drawn, and takes its colours
// from palette.js. Pages pass `width` and `dark` (Framework's reactive built-ins) so charts
// redraw on resize and on a change of colour scheme.
//
// Common options for every helper:
//   subtitle  required; the finding sentence from the page file's `subtitles`
//   asOf      required; the file's `as_of_month`, for "Source: NYC TLC trip records, Aug 2026"
//   dataset   "trip records" (default) or "monthly indicators" for TLC-reported figures
//   title     optional heading above the subtitle
//   width, height, dark

import * as Plot from "npm:@observablehq/plot@0.6.17";
import {html} from "npm:htl@0.3.1";
import * as format from "./format.js";
import * as palette from "./palette.js";

// Pages that need a mark the helpers don't cover use this pinned Plot, never the implicit one.
export {Plot};

const SURFACE = "var(--theme-background)";
const HALO = {stroke: SURFACE, strokeWidth: 4, paintOrder: "stroke"};
const FONT = {fontFamily: "var(--sans-serif)", fontSize: "12px", overflow: "visible"};
const LEGEND = {style: {fontFamily: "var(--sans-serif)", fontSize: "12px"}};

// Values are drawn in the unit their axis is labelled in: waits are stored in seconds but drawn
// in minutes (contracts §3). Tooltips and tables format the stored value.
const drawn = (unit) => (unit === "seconds" ? (v) => (v == null ? v : v / 60) : (v) => v);

// --- shared pieces -----------------------------------------------------------

function required(helper, options, names) {
  for (const name of names) {
    if (options[name] == null || options[name] === "") throw new Error(`${helper}: the "${name}" option is required`);
  }
}

export function sourceCaption(asOf, dataset = "trip records") {
  return `Source: NYC TLC ${dataset}, ${format.asOf(asOf)}`;
}

function frame(helper, options, content, table) {
  required(helper, options, ["subtitle", "asOf"]);
  return html`<div class="nrm-chart"><figure>
    ${options.title ? html`<h2>${options.title}</h2>` : null}
    <h3>${options.subtitle}</h3>
    ${[content].flat(Infinity).filter(Boolean)}
    <figcaption>${sourceCaption(options.asOf, options.dataset)}</figcaption>
  </figure>${table}</div>`;
}

function plotOptions({width = 640, height, marginTop, marginRight, marginBottom, marginLeft}) {
  return {width, height, marginTop, marginRight, marginBottom, marginLeft, style: FONT};
}

/** How a column or tooltip value is shown: a tile unit, or "mode", "month", "week", "hour". */
function formatter(spec) {
  if (typeof spec === "function") return spec;
  switch (spec) {
    case undefined:
    case null: return (v) => (v == null ? format.NA : String(v));
    case "mode": return format.modeName;
    case "month": return format.month;
    case "week": return format.week;
    case "hour": return format.hourOfDay;
    default: return (v) => format.value(spec, v);
  }
}

/**
 * A "Show the data as a table" disclosure, built on first open.
 * columns: [{key, label, format}] where format is a unit, "mode", "month", "week", "hour" or a function.
 */
export function tableView(rows, columns) {
  const cols = columns.map((c) => ({...c, f: formatter(c.format), numeric: !["mode", "month", "week", undefined, null, "text"].includes(c.format)}));
  const details = html`<details class="nrm-table"><summary>Show the data as a table</summary></details>`;
  details.addEventListener("toggle", () => {
    if (!details.open || details.querySelector("table")) return;
    details.append(html`<div class="nrm-table-scroll"><table>
      <thead><tr>${cols.map((c) => html`<th class=${c.numeric ? "nrm-num" : ""}>${c.label}</th>`)}</tr></thead>
      <tbody>${rows.map((r) => html`<tr>${cols.map((c) => html`<td class=${c.numeric ? "nrm-num" : ""}>${c.f(r[c.key])}</td>`)}</tr>`)}</tbody>
    </table></div>`);
  });
  return details;
}

function unique(values) {
  return [...new Set(values)];
}

/** Series keys in the fixed palette order (modes, then groups, then anything else as given). */
function ordered(keys) {
  const order = [...palette.modeOrder, ...palette.groupOrder];
  const rank = (k) => (order.includes(k) ? order.indexOf(k) : order.length);
  return unique(keys).sort((a, b) => rank(a) - rank(b));
}

function seriesColor(keys, {dark, colors = {}, seriesLabel = format.modeName}) {
  return {...palette.seriesScale(keys, dark, colors), tickFormat: seriesLabel};
}

/** Small multiples stacked vertically, one per facet value, each under its own label. */
function facetStack(rows, key, labels, render) {
  if (!key) return [render(rows, null)];
  const label = typeof labels === "function" ? labels : (k) => labels?.[k] ?? format.modeName(k);
  return ordered(rows.map((d) => d[key])).map((k) => html`<div class="nrm-facet">
    <div class="nrm-facet-label">${label(k)}</div>
    ${render(rows.filter((d) => d[key] === k), k)}
  </div>`);
}

/** The x-axis label of a horizontal chart, as text under the plot so it wraps on phones. */
function axisLabel(text) {
  return html`<div class="nrm-axis-label">${text}</div>`;
}

function extent(values) {
  const v = values.filter((x) => x != null && Number.isFinite(x));
  return [Math.min(...v), Math.max(...v)];
}

/** A time-tick interval that leaves about 100 px per label. */
function timeTicks([x0, x1], width) {
  const months = (x1 - x0) / (30.44 * 864e5);
  const fit = Math.max(1, Math.floor(width / 100));
  const step = [1, 3, 6, 12, 24, 60].find((m) => months / m <= fit) ?? 60;
  return step >= 12 ? `${step / 12} year${step > 12 ? "s" : ""}` : `${step} month${step > 1 ? "s" : ""}`;
}

/**
 * Dated rules with labels (events.json rows or {date, label}), labels stacked at the top. A label
 * wraps to the room beside its rule (Plot's lineWidth is in ems, about two characters each), so it
 * stays inside narrow charts. Returns the marks and the inset the stacked labels need.
 */
function eventMarks(events, [x0, x1], dark, innerWidth) {
  const visible = (events ?? [])
    .map((e) => ({...e, date: format.utcDate(e.date)}))
    .filter((e) => e.date >= x0 && e.date <= x1);
  const marks = [Plot.ruleX(visible, {x: "date", stroke: palette.color("muted", dark), strokeWidth: 1.5})];
  let top = 6;
  for (const e of visible) {
    const at = (e.date - x0) / (x1 - x0);
    const right = at <= 0.55;
    const ems = Math.max(6, ((right ? 1 - at : at) * innerWidth - 8) / 11);
    marks.push(Plot.text([e], {
      x: "date", text: "label", frameAnchor: "top", lineAnchor: "top", dy: top, dx: right ? 5 : -5,
      textAnchor: right ? "start" : "end", lineWidth: ems, fill: "currentColor", fontSize: 11, ...HALO
    }));
    top += 11 * Math.ceil(String(e.label).length / (2 * ems)) + 4;
  }
  return {marks, inset: top + 2};
}

/** Labelled vertical rules at numeric x positions ({x, label}), e.g. a transition week. */
function ruleMarks(rules, dark) {
  return (rules ?? []).flatMap((r, i) => [
    Plot.ruleX([r], {x: "x", stroke: palette.color("muted", dark), strokeWidth: 1.5}),
    Plot.text([r], {x: "x", text: "label", frameAnchor: "top", dy: 6 + i * 15, dx: 5, textAnchor: "start",
      fill: "currentColor", fontSize: 11, ...HALO})
  ]);
}

// --- line charts -------------------------------------------------------------

/**
 * lineChart(rows, options): one line per series over time (or another x).
 *   x        field (default "month")
 *   xType    "month" (default), "week", "hour" or "number"
 *   xLabel   required for "hour" and "number" x, with units
 *   y        required field;  yUnit: its tile unit (share, usd_per_mile, …);  yLabel: required, with units
 *   z        series field (default "mode" when rows have it); colors: {series: token} for non-mode series
 *   seriesLabel  series key → legend text (default: mode display names)
 *   events   events.json `events` for dated rules;  rules: [{x, label}] for numeric x
 *   zero     include 0 on the y axis (default true);  endLabels: label line ends (default true)
 */
export function lineChart(rows, options = {}) {
  const {
    x = "month", xType = "month", y, yUnit, yLabel, events, rules, zero = true, endLabels = true,
    colors, seriesLabel = format.modeName, dark = palette.isDark(), width = 640
  } = options;
  const z = options.z === undefined ? (rows.length && "mode" in rows[0] ? "mode" : null) : options.z;
  required("lineChart", options, ["y", "yUnit", "yLabel"]);
  if (xType === "hour" || xType === "number") required("lineChart", options, ["xLabel"]);
  const temporal = xType === "month" || xType === "week";
  const X = temporal ? (d) => format.utcDate(d[x]) : (d) => d[x];
  const Y = drawn(yUnit);
  const data = rows.filter((d) => d[y] != null).map((d) => ({...d, __x: X(d), __y: Y(d[y])}));
  const xDomain = extent(data.map((d) => +d.__x));
  const keys = z ? ordered(data.map((d) => d[z])) : [];
  const color = z ? seriesColor(keys, {dark, colors, seriesLabel}) : null;
  const stroke = z ? z : palette.color(colors?.line ?? "accent", dark);
  const xText = temporal ? (xType === "week" ? format.week : format.month) : xType === "hour" ? format.hourOfDay : (v) => format.axis("number")(v);
  const tipTitle = (d) => `${z ? `${seriesLabel(d[z])} · ` : ""}${xText(d[x])}\n${format.value(yUnit, d[y])}`;
  const labelled = endLabels && z && keys.length > 1 && width >= 480;
  const longest = Math.max(0, ...keys.map((k) => String(seriesLabel(k)).length));
  const marginRight = labelled ? 18 + longest * 7 : 16, marginLeft = options.marginLeft ?? 48;
  const dated = temporal ? eventMarks(events, xDomain.map((t) => new Date(t)), dark, width - marginLeft - marginRight) : null;
  const insetTop = dated ? (dated.marks.length > 1 ? dated.inset : 0) : (rules?.length ? 8 + rules.length * 15 : 0);

  const base = {
    ...plotOptions({width, height: options.height ?? (width < 480 ? 260 : 320), marginTop: 24, marginRight, marginLeft}),
    x: temporal
      ? {type: "utc", label: options.xLabel ?? null, labelArrow: "none", ticks: timeTicks(xDomain.map((t) => new Date(t)), width), tickFormat: format.axis("month")}
      : {label: options.xLabel, labelArrow: "none", tickFormat: xType === "hour" ? format.hourOfDay : format.axis("number"), ticks: xType === "hour" ? [0, 6, 12, 18] : undefined},
    y: {label: yLabel, labelArrow: "none", grid: true, zero, nice: true, tickFormat: format.axis(yUnit),
      ...(insetTop ? {insetTop} : null)},
    color: color ?? undefined
  };
  const marks = [
    ...(dated ? dated.marks : ruleMarks(rules, dark)),
    Plot.lineY(data, {x: "__x", y: "__y", z, stroke, strokeWidth: 2, strokeLinejoin: "round", strokeLinecap: "round"}),
    Plot.ruleX(data, Plot.pointerX({x: "__x", stroke: palette.color("muted", dark)})),
    Plot.dot(data, Plot.pointerX({x: "__x", y: "__y", fill: stroke, r: 4, stroke: SURFACE, strokeWidth: 2})),
    Plot.tip(data, Plot.pointerX({x: "__x", y: "__y", title: tipTitle}))
  ];
  let plot = Plot.plot({...base, marks});
  if (labelled) plot = withEndLabels(plot, base, marks, data, {z, seriesLabel});
  const legend = z && keys.length > 1 ? plot.legend("color", LEGEND) : null;
  const table = tableView(data, [
    {key: x, label: temporal ? (xType === "week" ? "Week" : "Month") : options.xLabel, format: temporal ? xType : xType === "hour" ? "hour" : "number"},
    ...(z ? [{key: z, label: "Series", format: seriesLabel}] : []),
    {key: y, label: yLabel, format: yUnit}
  ]);
  return frame("lineChart", options, [legend, plot], table);
}

/** Redraws a line chart with labels at the line ends, nudged apart, with short leaders. */
function withEndLabels(probe, base, marks, data, {z, seriesLabel}) {
  const scale = probe.scale("y");
  const xEnd = new Map();
  for (const d of data) if (!xEnd.has(d[z]) || d.__x > xEnd.get(d[z]).__x) xEnd.set(d[z], d);
  const items = [...xEnd.values()].map((d) => ({d, py: scale.apply(d.__y), ly: scale.apply(d.__y)})).sort((a, b) => a.py - b.py);
  const gap = 14;
  for (let i = 1; i < items.length; ++i) items[i].ly = Math.max(items[i].py, items[i - 1].ly + gap);
  const bottom = base.height - 30;
  const overflow = (items.at(-1)?.ly ?? 0) - bottom;
  if (overflow > 0) for (const it of items) it.ly -= overflow;
  const labels = items.map(({d, py, ly}) => ({__x: d.__x, y0: scale.invert(py), y1: scale.invert(ly), text: seriesLabel(d[z]), moved: Math.abs(ly - py) > 1}));
  return Plot.plot({
    ...base,
    y: {...base.y, domain: scale.domain, nice: false, zero: false},
    marks: [
      ...marks,
      Plot.link(labels.filter((l) => l.moved), {x1: "__x", x2: "__x", y1: "y0", y2: "y1", dx: 5, stroke: "currentColor", strokeOpacity: 0.4}),
      Plot.text(labels, {x: "__x", y: "y1", text: "text", dx: 9, textAnchor: "start", fill: "currentColor", ...HALO})
    ]
  });
}

/** Share over time (SPEC §9.4): a line per mode with the policy dates as labelled rules. */
export function shareLine(rows, options = {}) {
  required("shareLine", options, ["events"]);
  return lineChart(rows, {y: "share", yUnit: "share", yLabel: "Share of trips (%)", ...options});
}

// --- maps --------------------------------------------------------------------

/**
 * choropleth(geo, rows, options): a zone map (SPEC §9.4).
 *   value        required field in rows;  unit: its tile unit;  legendLabel: required, with units
 *   kind         "sequential" (level, blues) or "diverging" (change, centred on 0)
 *   key          rows' zone field (default "zone"); geo features carry LocationID, zone, borough
 *   href         zone id → link for clicks (optional)
 * Zones without a value draw in the muted colour.
 */
export function choropleth(geo, rows, options = {}) {
  const {value, unit, legendLabel, kind = "sequential", key = "zone", href, dark = palette.isDark(), width = 640} = options;
  required("choropleth", options, ["value", "unit", "legendLabel"]);
  const byZone = new Map(rows.map((d) => [d[key], d[value]]));
  const V = drawn(unit);
  const features = geo.features.map((f) => {
    const v = byZone.get(f.properties.LocationID) ?? null;
    return {...f, value: v, __v: V(v)};
  });
  const colorScale = kind === "diverging" ? palette.divergingScale(dark) : palette.sequentialScale(dark);
  const tipTitle = (f) => `${f.properties.zone} (${f.properties.borough})\n${f.value == null ? "No data" : format.value(unit, f.value)}`;
  const plot = Plot.plot({
    ...plotOptions({width, height: options.height, marginTop: 4, marginRight: 4, marginBottom: 4, marginLeft: 4}),
    projection: {type: "mercator", domain: geo},
    color: {...colorScale, label: legendLabel, tickFormat: format.axis(unit === "share" && kind === "diverging" ? "pts" : unit)},
    marks: [
      Plot.geo(features, Plot.centroid({fill: "__v", stroke: SURFACE, strokeWidth: 0.75, href: href ? (f) => href(f.properties.LocationID) : undefined,
        tip: true, title: tipTitle}))
    ]
  });
  const legend = plot.legend("color", {...LEGEND, width: Math.min(320, width), label: legendLabel});
  const table = tableView(features.map((f) => ({zone: f.properties.LocationID, name: f.properties.zone, borough: f.properties.borough, value: f.value})), [
    {key: "zone", label: "Zone", format: "text"},
    {key: "name", label: "Name", format: "text"},
    {key: "borough", label: "Borough", format: "text"},
    {key: "value", label: legendLabel, format: unit}
  ]);
  return frame("choropleth", options, [legend, plot], table);
}

// --- heatmap -----------------------------------------------------------------

const WEEK_ROWS = [1, 2, 3, 4, 5, 6, 0];   // Monday first; hour_of_week has Sunday = 0

/**
 * hourHeatmap(rows, options): the 24 × 7 hour-of-week grid (SPEC §9.4), one grid per mode.
 *   value        field (default "trips");  unit: its tile unit (default "count")
 *   legendLabel  required, with units (e.g. "Trips per week")
 *   fy           facet field (default "mode"; null for a single grid);  fyLabels: {key: label}
 * All grids share one colour scale, so a quieter mode reads as quieter.
 */
export function hourHeatmap(rows, options = {}) {
  const {value = "trips", unit = "count", legendLabel, fyLabels, dark = palette.isDark(), width = 640} = options;
  const fy = options.fy === undefined ? "mode" : options.fy;
  required("hourHeatmap", options, ["legendLabel"]);
  const V = drawn(unit);
  const [, max] = extent(rows.map((d) => V(d[value])));
  const color = {...palette.sequentialScale(dark), domain: [0, max], label: legendLabel, tickFormat: format.axis(unit)};
  const marginLeft = 36;
  const row = Math.max(15, Math.min(20, (width - marginLeft - 8) / 24));   // tall enough for day labels
  const grid = (data) => Plot.plot({
    ...plotOptions({width, height: row * 7 + 30, marginTop: 4, marginRight: 8, marginBottom: 26, marginLeft}),
    x: {type: "band", domain: Array.from({length: 24}, (_, h) => h), label: null, tickSize: 0, ticks: [0, 6, 12, 18], tickFormat: format.hourOfDay},
    y: {type: "band", domain: WEEK_ROWS, label: null, tickSize: 0, tickFormat: format.weekday},
    color,
    marks: [
      Plot.cell(data, {x: (d) => d.hour_of_week % 24, y: (d) => Math.floor(d.hour_of_week / 24), fill: (d) => V(d[value]), inset: 0.5,
        tip: true, title: (d) => `${fy ? `${(fyLabels?.[d[fy]] ?? format.modeName(d[fy]))} · ` : ""}${format.hourOfWeek(d.hour_of_week)}\n${format.value(unit, d[value])}`})
    ]
  });
  const legend = Plot.legend({color, ...LEGEND, width: Math.min(320, width)});
  const table = tableView(rows, [
    {key: "hour_of_week", label: "Hour of week", format: format.hourOfWeek},
    ...(fy ? [{key: fy, label: "Mode", format: (k) => fyLabels?.[k] ?? format.modeName(k)}] : []),
    {key: value, label: legendLabel, format: unit}
  ]);
  return frame("hourHeatmap", options, [legend, facetStack(rows, fy, fyLabels, grid)], table);
}

// --- dots and ranges ---------------------------------------------------------

/**
 * rangeDots(rows, options): a dot per row with a rule across its range.
 *   x, x1, x2    centre and range fields;  unit: their tile unit;  xLabel: required, with units
 *   y            category field (default "mode");  yLabels: {key: label} (default mode names)
 *   fy           facet field (optional);  fyLabels: {key: label}
 *   zero         draw a rule at 0
 */
export function rangeDots(rows, options = {}) {
  const {x, x1, x2, unit, xLabel, y = "mode", yLabels, fy, fyLabels, zero = false, colors, dark = palette.isDark(), width = 640} = options;
  required("rangeDots", options, ["x", "x1", "x2", "unit", "xLabel"]);
  const yText = (k) => yLabels?.[k] ?? format.modeName(k);
  const V = drawn(unit);
  const drawnRows = rows.map((d) => ({...d, __x: V(d[x]), __x1: V(d[x1]), __x2: V(d[x2])}));
  const domain = extent(drawnRows.flatMap((d) => [d.__x1, d.__x2, d.__x, ...(zero ? [0] : [])]));
  const isSeries = rows.every((d) => palette.mode[d[y]] || palette.group[d[y]] || colors?.[d[y]]);
  const color = isSeries ? seriesColor(rows.map((d) => d[y]), {dark, colors, seriesLabel: yText}) : undefined;
  const fill = isSeries ? y : palette.color("accent", dark);
  const marginLeft = Math.min(width * 0.4, 16 + Math.max(...rows.map((d) => String(yText(d[y])).length)) * 7);
  const panel = (data) => Plot.plot({
    ...plotOptions({width, height: 30 * unique(data.map((d) => d[y])).length + 44, marginTop: 8, marginLeft, marginRight: 16, marginBottom: 24}),
    x: {domain, nice: true, label: null, grid: true, tickFormat: format.axis(unit)},
    y: {type: "band", domain: ordered(data.map((d) => d[y])), label: null, tickSize: 0, tickFormat: yText, padding: 0.4},
    color,
    marks: [
      zero ? Plot.ruleX([0], {stroke: "currentColor", strokeOpacity: 0.5}) : null,
      Plot.ruleY(data, {y, x1: "__x1", x2: "__x2", stroke: fill, strokeWidth: 2, strokeLinecap: "round"}),
      Plot.dot(data, {x: "__x", y, fill, r: 5, stroke: SURFACE, strokeWidth: 2, tip: true,
        title: (d) => `${yText(d[y])}\n${format.value(unit, d[x])} (range ${format.value(unit, d[x1])} to ${format.value(unit, d[x2])})`})
    ]
  });
  const table = tableView(rows, [
    ...(fy ? [{key: fy, label: "Panel", format: (k) => fyLabels?.[k] ?? k}] : []),
    {key: y, label: "Series", format: yText},
    {key: x, label: "Value", format: unit},
    {key: x1, label: "Low", format: unit},
    {key: x2, label: "High", format: unit}
  ]);
  return frame("rangeDots", options, [facetStack(drawnRows, fy, fyLabels, panel), axisLabel(xLabel)], table);
}

/**
 * Policy effects (SPEC §9.4): the median weekly estimated effect with its 10th–90th percentile
 * range, per mode, one panel per metric (congestion.json `effects`).
 */
export function effectDots(rows, options = {}) {
  return rangeDots(rows, {x: "median", x1: "p10", x2: "p90", unit: "effect", fy: "metric", zero: true,
    xLabel: "Estimated effect, median week with 10th–90th percentile range (%)", ...options});
}

/** Price spread as ranges: median fare per mile with its 10th–90th percentile, per mode. */
export function fareRange(rows, options = {}) {
  return rangeDots(rows, {x: "fpm_p50", x1: "fpm_p10", x2: "fpm_p90", unit: "usd_per_mile",
    xLabel: "Fare per mile, median with 10th–90th percentile ($/mile)", ...options});
}

/**
 * Price spread as a strip (SPEC §9.4): one dot per zone, one row per mode.
 *   x       field (default "fpm_p50");  unit (default "usd_per_mile");  xLabel (default below)
 *   label   row → text for the tooltip (default: zone number)
 */
export function fareStrip(rows, options = {}) {
  const {x = "fpm_p50", unit = "usd_per_mile", xLabel = "Median fare per mile in each zone ($/mile)", y = "mode",
    label = (d) => `Zone ${d.zone}`, dark = palette.isDark(), width = 640} = options;
  const V = drawn(unit);
  const data = rows.filter((d) => d[x] != null).map((d) => ({...d, __v: V(d[x])}));
  const keys = ordered(data.map((d) => d[y]));
  const plot = Plot.plot({
    ...plotOptions({width, height: 44 * keys.length + 44, marginTop: 8, marginLeft: 92, marginRight: 16, marginBottom: 24}),
    x: {label: null, grid: true, nice: true, tickFormat: format.axis(unit)},
    y: {type: "band", domain: keys, label: null, tickSize: 0, tickFormat: format.modeName, padding: 0.2},
    color: seriesColor(keys, {dark}),
    marks: [
      Plot.dot(data, {x: "__v", y, fill: y, r: 3, fillOpacity: 0.45, tip: true,
        title: (d) => `${label(d)} · ${format.modeName(d[y])}\n${format.value(unit, d[x])}`})
    ]
  });
  const table = tableView(data, [
    {key: "zone", label: "Zone", format: "text"},
    {key: y, label: "Mode", format: "mode"},
    {key: x, label: xLabel, format: unit}
  ]);
  return frame("fareStrip", options, [plot, axisLabel(xLabel)], table);
}

// --- bars --------------------------------------------------------------------

/**
 * stackedBars100(rows, options): bars stacked to 100% by mode (SPEC §9.4, airport split).
 *   x        value field (default "share"; trips work too, each bar is normalised)
 *   y        category field (default "airport");  yLabels: {key: label}
 *   z        series field (default "mode")
 *   fy       facet field (optional, e.g. "direction");  fyLabels: {key: label}
 *   xLabel   default "Share of trips (%)"
 * Segments carry a share label when they are wide enough to hold one.
 */
export function stackedBars100(rows, options = {}) {
  const {x = "share", y = "airport", z = "mode", yLabels, fy, fyLabels, xLabel = "Share of trips (%)", dark = palette.isDark(), width = 640} = options;
  const keys = ordered(rows.map((d) => d[z]));
  const color = seriesColor(keys, {dark});
  const yText = (k) => yLabels?.[k] ?? String(k);
  const marginLeft = Math.min(width * 0.35, 16 + Math.max(...rows.map((d) => String(yText(d[y])).length)) * 7);
  const plotWidth = width - marginLeft - 16;
  const stacked = [];
  const groups = new Map();
  for (const d of rows) {
    const k = `${d[y]}\u0000${fy ? d[fy] : ""}`;
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k).push(d);
  }
  for (const group of groups.values()) {
    group.sort((a, b) => keys.indexOf(a[z]) - keys.indexOf(b[z]));
    const total = group.reduce((s, d) => s + (d[x] ?? 0), 0);
    let at = 0;
    for (const d of group) {
      const part = total ? (d[x] ?? 0) / total : 0;
      stacked.push({...d, __x1: at, __x2: at + part, __share: part});
      at += part;
    }
  }
  const panel = (data) => Plot.plot({
    ...plotOptions({width, height: 40 * unique(data.map((d) => d[y])).length + 40, marginTop: 4, marginLeft, marginRight: 16, marginBottom: 24}),
    x: {domain: [0, 1], label: null, tickFormat: format.axis("share")},
    y: {type: "band", domain: unique(data.map((d) => d[y])), label: null, tickSize: 0, tickFormat: yText, padding: 0.3},
    color,
    marks: [
      Plot.barX(data, {x1: "__x1", x2: "__x2", y, fill: z, insetLeft: 1, insetRight: 1, tip: true,
        title: (d) => `${yText(d[y])} · ${format.modeName(d[z])}\n${format.share(d.__share)} of trips`}),
      ...keys.map((k) => Plot.text(data.filter((d) => d[z] === k && d.__share * plotWidth >= 38), {
        x: (d) => (d.__x1 + d.__x2) / 2, y, text: (d) => format.share(d.__share), fill: palette.inkOn(palette.color(k, dark)), pointerEvents: "none"
      }))
    ]
  });
  const table = tableView(stacked, [
    ...(fy ? [{key: fy, label: "Panel", format: (k) => fyLabels?.[k] ?? k}] : []),
    {key: y, label: "Bar", format: yText},
    {key: z, label: "Mode", format: "mode"},
    {key: "__share", label: xLabel, format: "share"}
  ]);
  return frame("stackedBars100", options, [Plot.legend({color, ...LEGEND, width}), facetStack(stacked, fy, fyLabels, panel), axisLabel(xLabel)], table);
}

/**
 * barChart(rows, options): horizontal bars with the value at each tip.
 *   x        required value field;  unit: its tile unit;  xLabel: required, with units
 *   y        required category field;  yLabels: {key: label} or a function
 *   fill     a series field (e.g. "mode") or a palette token (default "accent")
 *   sort     true (default) sorts bars by value, largest first
 */
export function barChart(rows, options = {}) {
  const {x, y, unit, xLabel, yLabels, fill = "accent", sort = true, dark = palette.isDark(), width = 640} = options;
  required("barChart", options, ["x", "y", "unit", "xLabel"]);
  const yText = typeof yLabels === "function" ? yLabels : (k) => yLabels?.[k] ?? (palette.mode[k] || palette.group[k] ? format.modeName(k) : String(k));
  const V = drawn(unit);
  const data = rows.filter((d) => d[x] != null).map((d) => ({...d, __v: V(d[x])}));
  const domain = sort ? [...data].sort((a, b) => b[x] - a[x]).map((d) => d[y]) : data.map((d) => d[y]);
  const bySeries = typeof fill === "string" && data.length > 0 && fill in data[0];
  const marginLeft = Math.min(width * 0.4, 16 + Math.max(...data.map((d) => String(yText(d[y])).length)) * 6.5);
  const longestValue = Math.max(...data.map((d) => format.value(unit, d[x]).length));
  const plot = Plot.plot({
    ...plotOptions({width, height: 30 * data.length + 44, marginTop: 4, marginLeft, marginRight: 12 + longestValue * 7, marginBottom: 24}),
    x: {label: null, grid: true, nice: true, tickFormat: format.axis(unit)},
    y: {type: "band", domain, label: null, tickSize: 0, tickFormat: yText, padding: 0.25},
    color: bySeries ? seriesColor(data.map((d) => d[fill]), {dark}) : undefined,
    marks: [
      Plot.barX(data, {x: "__v", y, fill: bySeries ? fill : palette.color(fill, dark), tip: true,
        title: (d) => `${yText(d[y])}\n${format.value(unit, d[x])}`}),
      Plot.ruleX([0], {stroke: "currentColor"}),
      Plot.text(data, {x: "__v", y, text: (d) => format.value(unit, d[x]), dx: 5, textAnchor: "start", fill: "currentColor"})
    ]
  });
  const table = tableView(data, [{key: y, label: "Item", format: yText}, {key: x, label: xLabel, format: unit}]);
  return frame("barChart", options, [plot, axisLabel(xLabel)], table);
}

/**
 * monthlyColumns(rows, options): a column per month, stacked by mode (e.g. fee revenue).
 *   x        month field (default "month");  y: required value field
 *   unit     its tile unit;  yLabel: required, with units
 *   z        series field (default "mode"; null for one series in the accent colour)
 *   events   events.json `events` for dated rules, as in lineChart
 */
export function monthlyColumns(rows, options = {}) {
  const {x = "month", y, unit, yLabel, events, dark = palette.isDark(), width = 640} = options;
  const z = options.z === undefined ? "mode" : options.z;
  required("monthlyColumns", options, ["y", "unit", "yLabel"]);
  const V = drawn(unit);
  const data = rows.filter((d) => d[y] != null).map((d) => ({...d, __x: format.utcDate(d[x]), __y: V(d[y])}));
  const keys = z ? ordered(data.map((d) => d[z])) : [];
  const color = z ? seriesColor(keys, {dark}) : undefined;
  const xDomain = extent(data.map((d) => +d.__x)).map((t) => new Date(t));
  const dated = eventMarks(events, xDomain, dark, width - 56 - 16);
  const plot = Plot.plot({
    ...plotOptions({width, height: options.height ?? (width < 480 ? 240 : 300), marginTop: 16, marginLeft: 56, marginRight: 16}),
    x: {type: "utc", label: null, ticks: timeTicks(xDomain, width), tickFormat: format.axis("month")},
    y: {label: yLabel, labelArrow: "none", grid: true, tickFormat: format.axis(unit),
      ...(dated.marks.length > 1 ? {insetTop: dated.inset} : null)},
    color,
    marks: [
      ...dated.marks,
      Plot.rectY(data, {x: "__x", interval: "month", y: "__y", fill: z ?? palette.color("accent", dark), order: keys.length ? keys : undefined,
        insetLeft: 1, insetRight: 1, tip: true,
        title: (d) => `${z ? `${format.modeName(d[z])} · ` : ""}${format.month(d[x])}\n${format.value(unit, d[y])}`}),
      Plot.ruleY([0], {stroke: "currentColor"})
    ]
  });
  const legend = z && keys.length > 1 ? plot.legend("color", LEGEND) : null;
  const table = tableView(data, [
    {key: x, label: "Month", format: "month"},
    ...(z ? [{key: z, label: "Mode", format: "mode"}] : []),
    {key: y, label: yLabel, format: unit}
  ]);
  return frame("monthlyColumns", options, [legend, plot], table);
}
