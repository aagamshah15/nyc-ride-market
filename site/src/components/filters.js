// Page filters (D34): a compact bar of selects and segmented radios over data the page already
// loads, and the plain description a filtered chart shows in place of its finding.
//
// A page looks like:
//   const filters = view(filterBar([
//     {key: "mode", label: "Mode", options: ["all", "uber", "lyft"], format: modeOption},
//     {key: "days", label: "Days", options: Object.keys(DAY_SETS), format: dayOption, radio: true}
//   ]));
//   const subtitle = filters.changed("mode", "days")
//     ? describe({what: modePhrase(filters.mode), when: timePhrase(filters.days)})
//     : data.subtitles.fpm_by_hour;
//
// Each control opens on its `value` (default: the first option), which is the view the page's
// finding describes. A chart shows its finding only while every filter it reads is at its default;
// otherwise it shows the description, so a chart never states a finding it no longer shows.

import {Inputs, html} from "./page.js";
import * as format from "./format.js";

let bars = 0;   // ids for the controls' labels are page-wide, so each bar numbers its own

/**
 * filterBar(controls, options): the filter bar, for `view()`. Its value is {key: value} per
 * control, plus a non-enumerable `changed(...keys)` that says whether any of those keys has moved
 * from its default. A Reset button returns every control to its default.
 *   controls  [{key, label, options, value, format, radio}]: `radio` draws segmented radios
 *             (for two or three short options) instead of a select
 *   label     the group's accessible name (default "Filter this page")
 */
export function filterBar(controls, {label = "Filter this page"} = {}) {
  const id = `nrm-filters-${++bars}`;
  const defaults = Object.fromEntries(controls.map((c) => [c.key, c.value ?? c.options[0]]));
  const inputs = Object.fromEntries(controls.map((c, i) => {
    const options = {label: c.label, value: defaults[c.key], format: c.format ?? String};
    const input = c.radio ? Inputs.radio(c.options, options) : Inputs.select(c.options, options);
    input.classList.add("nrm-filter", c.radio ? "nrm-filter--radio" : "nrm-filter--select");
    if (c.radio) {
      // Inputs labels a radio group with a bare <label>; name the group for screen readers.
      const name = input.querySelector(":scope > label");
      const group = input.querySelector(":scope > div");
      name.id = `${id}-${i}`;
      group.setAttribute("role", "radiogroup");
      group.setAttribute("aria-labelledby", name.id);
    }
    return [c.key, input];
  }));
  const value = () => {
    const v = Object.fromEntries(controls.map((c) => [c.key, inputs[c.key].value]));
    return Object.defineProperty(v, "changed", {value: (...keys) => keys.some((k) => v[k] !== defaults[k])});
  };
  const reset = html`<button type="button" class="nrm-filters-reset">Reset</button>`;
  const bar = html`<div class="nrm-filters" role="group" aria-label=${label}>${Object.values(inputs)}${reset}</div>`;
  const sync = () => {
    reset.disabled = !controls.some((c) => inputs[c.key].value !== defaults[c.key]);
  };
  reset.onclick = () => {
    for (const c of controls) inputs[c.key].value = defaults[c.key];
    sync();
    bar.dispatchEvent(new Event("input", {bubbles: true}));
  };
  bar.addEventListener("input", sync);
  sync();
  return Object.defineProperty(bar, "value", {get: value});
}

/**
 * Nothing to show, for a cell whose note no longer applies to the selection. Framework clears a
 * cell's output only when the cell displays again, so `if (x) display(note)` would leave the note
 * up after x turns false: `display(x ? note : none())` clears it.
 */
export function none() {
  return document.createDocumentFragment();
}

// --- descriptions ---------------------------------------------------------------

/** "Showing yellow cabs in Brooklyn, weekdays 4–8 pm" from {what, where, when}. */
export function describe({what, where, when}) {
  return `Showing ${[what, where].filter(Boolean).join(" ")}${when ? `, ${when}` : ""}`;
}

// Modes as a sentence names them (format.modeName is for labels: "Yellow cab").
const MODE_PHRASES = {
  uber: "Uber",
  lyft: "Lyft",
  yellow: "yellow cabs",
  green: "green cabs",
  other_hv: "other ride-hail apps",
  ride_hail: "ride-hail apps",
  taxi: "cabs",
  all: "all modes"
};

export function modePhrase(code) {
  return MODE_PHRASES[code] ?? format.modeName(code);
}

/** "Uber's", "yellow cabs'". */
export function modePossessive(code) {
  const name = modePhrase(code);
  return name.endsWith("s") ? `${name}'` : `${name}'s`;
}

/** A mode as a select option: "All modes", "Uber", "Yellow cabs". */
export function modeOption(code) {
  const name = modePhrase(code);
  return name[0].toUpperCase() + name.slice(1);
}

// --- time of day and week -------------------------------------------------------

// Hours [from, to) of the day. None crosses midnight, so a band is one run on an hour axis.
export const TIME_BANDS = {
  all: null,
  overnight: [0, 6],
  morning: [6, 10],
  midday: [10, 16],
  evening: [16, 20],
  late: [20, 24]
};
const BAND_NAMES = {all: "All day", overnight: "Overnight", morning: "Morning rush", midday: "Midday", evening: "Evening rush", late: "Late evening"};

// Days of the week as hour_of_week counts them (Sunday = 0).
export const DAY_SETS = {all: null, weekdays: [1, 2, 3, 4, 5], weekends: [0, 6]};
const DAY_NAMES = {all: "Every day", weekdays: "Weekdays", weekends: "Weekends"};

/** "4–8 pm", "10 am–4 pm", "12–6 am", "8 pm–12 am" for hours [from, to). */
export function hourRange([from, to]) {
  const half = (h) => (h % 24 < 12 ? "am" : "pm");
  const clock = (h) => (h % 12 === 0 ? 12 : h % 12);
  return half(from) === half(to)
    ? `${clock(from)}–${clock(to)} ${half(to)}`
    : `${format.hourOfDay(from)}–${format.hourOfDay(to % 24)}`;
}

/** A band as a select option: "Evening rush, 4–8 pm". */
export function bandOption(key) {
  return TIME_BANDS[key] ? `${BAND_NAMES[key]}, ${hourRange(TIME_BANDS[key])}` : BAND_NAMES[key];
}

export function dayOption(key) {
  return DAY_NAMES[key];
}

/** Whether an hour of the day (0–23) falls in a band. */
export function inBand(hour, band) {
  const range = TIME_BANDS[band];
  return !range || (hour >= range[0] && hour < range[1]);
}

/** Whether an hour of the week (Sunday 00:00 = 0) falls in a day set and a band. */
export function inWeek(hourOfWeek, days, band) {
  const set = DAY_SETS[days];
  return (!set || set.includes(Math.floor(hourOfWeek / 24))) && inBand(hourOfWeek % 24, band);
}

/** "weekdays 4–8 pm", "weekends", "4–8 pm every day"; "" for the whole week. */
export function timePhrase(days = "all", band = "all") {
  const range = TIME_BANDS[band] ? hourRange(TIME_BANDS[band]) : "";
  if (days === "all") return range ? `${range} every day` : "";
  return [days, range].filter(Boolean).join(" ");
}

/** "Uber, Lyft and yellow cabs". */
export function list(items) {
  return items.length < 2 ? (items[0] ?? "") : `${items.slice(0, -1).join(", ")} and ${items.at(-1)}`;
}
