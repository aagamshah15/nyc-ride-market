// The stat row (SPEC §9.3): 3–5 tiles, each the latest value plus its change versus the same
// month a year earlier. Labels, units and change kinds come from tiles.json (the registry in
// contracts/site/tiles.yaml); values from the page file's `tiles` and `yoy`.

import {html} from "npm:htl@0.3.1";
import * as format from "./format.js";

/**
 * statTiles(page, registry, options)
 *   page      a page file: {tiles, yoy, not_reported?, flags?}
 *   registry  tiles.json (or its `tiles` object)
 *   options   keys: which tiles, in order (default: every key in page.tiles)
 *             yoyLabel: text after the change (default "vs a year earlier")
 */
export function statTiles(page, registry, {keys, yoyLabel = "vs a year earlier"} = {}) {
  const entries = registry?.tiles ?? registry;
  if (!entries) throw new Error("statTiles: pass tiles.json as the registry");
  const notReported = new Set(page.not_reported ?? []);
  const thin = Boolean(page.flags?.thin);
  return html`<div class="nrm-tiles">${(keys ?? Object.keys(page.tiles)).map((key) => {
    const meta = entries[key];
    if (!meta) throw new Error(`statTiles: "${key}" is not in the tile registry`);
    return tile(meta, page.tiles[key], page.yoy?.[key], {notReported: notReported.has(key), thin, yoyLabel});
  })}</div>`;
}

/** One tile, for a value that isn't part of a page's stat row. */
export function tile({label, unit, yoy: kind}, value, change, {notReported = false, thin = false, yoyLabel = "vs a year earlier"} = {}) {
  if (notReported || value == null) {
    const note = notReported ? "Not reported for this mode" : thin ? "Too few trips" : "Not available";
    return html`<div class="nrm-tile nrm-tile--null">
      <div class="nrm-tile-label">${label}</div>
      <div class="nrm-tile-value">${format.NA}</div>
      <div class="nrm-tile-note">${note}</div>
    </div>`;
  }
  const changeText = kind === "none" ? "" : change == null ? "No year-earlier value" : `${format.change(kind, unit, change)} ${yoyLabel}`;
  return html`<div class="nrm-tile">
    <div class="nrm-tile-label">${label}</div>
    ${unit === "text"
      ? html`<div class="nrm-tile-value nrm-tile-value--text">${format.value(unit, value)}</div>`
      : html`<div class="nrm-tile-value">${splitUnit(format.value(unit, value))}</div>`}
    <div class="nrm-tile-change">${changeText}</div>
  </div>`;
}

// "$3.77/mile" → "$3.77" + a smaller "/mile", so long units don't break the figure.
function splitUnit(text) {
  const [, figure, suffix] = /^([−+]?\$?[\d.,]+%?)(.*)$/.exec(text) ?? [, text, ""];
  return suffix ? html`${figure}<span class="nrm-tile-unit">${suffix}</span>` : figure;
}
