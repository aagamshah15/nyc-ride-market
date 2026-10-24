// Design tokens (SPEC §9.5). This is the only file in site/src that holds literal colours;
// components and pages take every colour from here.

export const mode = {
  uber:   {light: "#3A3A3A", dark: "#D4D4D4"},
  lyft:   {light: "#B4447F", dark: "#E07AB0"},
  yellow: {light: "#D99A00", dark: "#F2C14E"},
  green:  {light: "#3C8D5A", dark: "#6CC08A"},
  other_hv: {light: "#9AA0A6", dark: "#80868B"},
};
export const accent = {light: "#2F6FDB", dark: "#6E9CF0"};
export const muted  = {light: "#C9CDD2", dark: "#4A4F55"};
// sequential: Plot scheme "blues"; diverging: custom interpolate #2F6FDB → #F2F2F2 → #E07B39

// Fixed order for legends, stacks and series: SPEC's order. It keeps Lyft and green, the one
// pair that falls below the colour-blindness floor, apart in stacks (see the L05 status log).
export const modeOrder = ["uber", "lyft", "yellow", "green", "other_hv"];

// Mode groups from contracts/README.md §2, drawn from the tokens above. `all` uses the page's
// text colour so it never reads as a company.
export const group = {
  ride_hail: accent,
  taxi: mode.yellow,
  all: {light: "currentColor", dark: "currentColor"},
};
export const groupOrder = ["ride_hail", "taxi", "all"];

// Sequential (magnitude): one hue. In dark mode the ramp flips so bigger values sit further
// from the dark surface.
export const sequential = {
  light: {scheme: "blues", range: [0.12, 1]},
  dark: {scheme: "blues", range: [0.12, 1], reverse: true},
};

// Diverging (polarity), centred on 0. Light is SPEC's ramp; dark keeps the poles readable on
// the dark surface and uses the dark muted token as its neutral midpoint.
export const diverging = {
  light: ["#2F6FDB", "#F2F2F2", "#E07B39"],
  dark: [accent.dark, muted.dark, "#E07B39"],
};

// Text set inside a coloured mark (a stacked segment): whichever of these clears contrast.
export const ink = {dark: "#1B1E23", light: "#FFFFFF"};

/** Whether the page is showing its dark scheme now (same test as Framework's `dark`). */
export function isDark() {
  if (typeof document === "undefined") return false;
  const scheme = getComputedStyle(document.body).getPropertyValue("color-scheme").split(/\s+/);
  if (scheme.includes("light") && scheme.includes("dark")) return matchMedia("(prefers-color-scheme: dark)").matches;
  return scheme.includes("dark");
}

const scheme = (dark) => (dark ? "dark" : "light");

/** A token's colour for the scheme: `accent`, `muted`, `foreground`, a mode or a group. */
export function color(key, dark = isDark()) {
  if (key === "accent") return accent[scheme(dark)];
  if (key === "muted") return muted[scheme(dark)];
  if (key === "foreground") return "currentColor";
  const token = mode[key] ?? group[key];
  if (!token) throw new Error(`palette: no colour for "${key}"`);
  return token[scheme(dark)];
}

/** A Plot ordinal colour scale for the series keys present, in the fixed order. */
export function seriesScale(keys, dark = isDark(), colors = {}) {
  const order = [...modeOrder, ...groupOrder];
  const domain = [...new Set(keys)].sort((a, b) => rank(order, a) - rank(order, b));
  return {type: "ordinal", domain, range: domain.map((k) => color(colors[k] ?? k, dark))};
}

function rank(order, key) {
  const i = order.indexOf(key);
  return i < 0 ? order.length : i;
}

/** Plot colour options for a sequential (magnitude) scale. */
export function sequentialScale(dark = isDark()) {
  return {type: "linear", ...sequential[scheme(dark)], unknown: muted[scheme(dark)]};
}

/** Plot colour options for a diverging scale centred on 0. */
export function divergingScale(dark = isDark()) {
  return {type: "diverging", pivot: 0, symmetric: true, interpolate: interpolate3(diverging[scheme(dark)]),
    unknown: muted[scheme(dark)]};
}

/** Piecewise linear RGB interpolation through three colours, t in [0, 1]. */
export function interpolate3([a, b, c]) {
  const [ra, rb, rc] = [a, b, c].map(rgb);
  return (t) => {
    const [from, to, u] = t < 0.5 ? [ra, rb, t * 2] : [rb, rc, t * 2 - 1];
    return `rgb(${from.map((v, i) => Math.round(v + (to[i] - v) * u)).join(",")})`;
  };
}

/** The ink token with the higher WCAG contrast against a fill colour. */
export function inkOn(fill) {
  const contrast = (a, b) => (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
  const l = luminance(fill);
  return contrast(l, luminance(ink.dark)) >= contrast(l, luminance(ink.light)) ? ink.dark : ink.light;
}

function luminance(hex) {
  const [r, g, b] = rgb(hex).map((v) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function rgb(hex) {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) throw new Error(`palette: expected #rrggbb, got ${hex}`);
  return [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16));
}
