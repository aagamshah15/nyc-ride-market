// The profile-page template (SPEC §9.3): title from JSON, the stat row, chart blocks and the
// "How we measured this" note, plus the null states from contracts/README.md §4.
//
// A page looks like:
//   const data = FileAttachment("data/drivers.json").json();
//   const tiles = FileAttachment("data/tiles.json").json();
//   ${pageHeader(data, tiles)}            → mock banner, h1 title, stat row
//   ${lineChart(data.driver_share_trend, {…, subtitle: data.subtitles.driver_share_trend, asOf: data.as_of_month, width, dark})}
//   ${howWeMeasured("pay-rise-method")}
// Give the page a plain front-matter `title` for the browser tab; the h1 comes from the JSON.

import * as Inputs from "npm:@observablehq/inputs@0.12.0";
import {html} from "npm:htl@0.3.1";
import * as format from "./format.js";
import {statTiles} from "./statTiles.js";

// Pinned for pages: use these rather than Framework's implicit (unpinned) `Inputs` and `html`.
export {Inputs, html};

// This module is served from {root}/_import/components/, so the site root is two levels up.
// Resolving against it keeps links right under the GitHub Pages base path (/nyc-ride-market/).
const ROOT = new URL("../../", import.meta.url);

/** An absolute URL for a site path such as "methods#tips" or "zones/132". */
// Routes whose page is an index file (zones/index.md): Framework's preview serves them only with the
// trailing slash, so findings that link to "/zones" get it added here.
const INDEX_ROUTES = new Set(["/zones"]);

export function siteUrl(path) {
  return new URL((INDEX_ROUTES.has(path) ? `${path}/` : path).replace(/^\//, ""), ROOT).href;
}

/** A notice while a page shows mock or unvalidated data; nothing for validated real data. */
export function mockBanner(data) {
  if (data.as_of_month === "MOCK") {
    return html`<div class="nrm-mock" role="note">Mock data from <code>make site-mock</code>. Every number on this page is made up.</div>`;
  }
  if (data.validated === false) {
    return html`<div class="nrm-mock" role="note">These figures have not passed validation yet.</div>`;
  }
  return null;
}

/** The page's headline finding, from the file's generated `title`. */
export function pageTitle(data) {
  if (!data.title) throw new Error("pageTitle: the page file has no title");
  return html`<h1>${data.title}</h1>`;
}

/** Banner, title and stat row in one go. Options pass through to statTiles. */
export function pageHeader(data, registry, options) {
  return html`${mockBanner(data)}${pageTitle(data)}${statTiles(data, registry, options)}`;
}

/** The "How we measured this" note linking to /methods#{anchor} (anchors: contracts/site/pages.yaml). */
export function howWeMeasured(anchor, text = "Definitions, cleaning rules and known limits are on the methods page.") {
  if (!anchor) throw new Error("howWeMeasured: an anchor from contracts/site/pages.yaml is required");
  return html`<p class="nrm-methods"><a href=${siteUrl(`methods#${anchor}`)}>How we measured this</a>. ${text}</p>`;
}

/** A plain empty or null state in place of a chart. */
export function emptyState(title, text = "") {
  return html`<div class="nrm-null" role="note"><strong>${title}</strong>${text}</div>`;
}

/** For metrics listed in a company file's `not_reported` (taxis: driver share, WAV, shared rides). */
export function notReported(what, why = "TLC trip records don't carry this for this mode.") {
  return emptyState(`${what}: not reported for this mode`, why);
}

/** For zones with `flags.thin` (fewer than 100 valid trips in the latest month). */
export function tooFewTrips(what = "Percentiles") {
  return emptyState("Too few trips", `${what} need at least 100 trips in the month; this zone had fewer.`);
}

/** Generated findings (home.json `findings`) as a list linking to their pages. */
export function findingsList(findings, {featuredOnly = false} = {}) {
  const items = featuredOnly ? findings.filter((f) => f.featured) : findings;
  return html`<ul class="nrm-findings">${items.map((f) => html`<li>${f.text}${f.page ? html` <a href=${siteUrl(f.page)}>More</a>` : null}</li>`)}</ul>`;
}

// Labels for comparison metrics that aren't stat tiles (contracts §7: compare[] uses tile units).
const COMPARE_LABELS = {
  fare_per_min: "Fare per minute",
  wav_share: "Share of trips in a wheelchair-accessible vehicle",
  shared_match_rate: "Shared-ride match rate",
};

const COMPANIES = ["uber", "lyft", "yellow", "green"];

/**
 * The comparison block (companies `compare[]`): one row per metric, one column per company,
 * each value formatted by the row's unit. `current` bolds that company's column.
 */
export function compareTable(rows, registry, {current, companies = COMPANIES} = {}) {
  const entries = registry?.tiles ?? registry ?? {};
  const label = (metric) => entries[metric]?.label ?? COMPARE_LABELS[metric] ?? metric;
  const cell = (row, company) => {
    const text = row[company] == null ? "Not reported" : format.value(row.unit, row[company]);
    return company === current ? html`<td class="nrm-num"><strong>${text}</strong></td>` : html`<td class="nrm-num">${text}</td>`;
  };
  const cabTips = rows.some((r) => r.metric === "tip_rate") && companies.some((c) => c === "yellow" || c === "green");
  return html`<div class="nrm-scroll-x"><table class="nrm-compare">
    <thead><tr><th>Metric</th>${companies.map((c) => html`<th class="nrm-num">${format.modeName(c)}</th>`)}</tr></thead>
    <tbody>${rows.map((row) => html`<tr><td>${label(row.metric)}</td>${companies.map((c) => cell(row, c))}</tr>`)}</tbody>
  </table></div>${cabTips ? html`<p class="nrm-note">Cab tip rates are card-only: TLC records tips on card payments only.</p>` : null}`;
}
