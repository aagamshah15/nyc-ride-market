// Number, date and label formatting for the site, exactly as contracts/README.md §3.
// findings.py (L11) follows the same rules for generated sentences.
// Every formatter returns NA for a missing value (contracts §4: missing is JSON null).

export const NA = "—";
const MINUS = "−";
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];   // hour_of_week: Sunday 00:00 = 0

const missing = (v) => v == null || (typeof v === "number" && !Number.isFinite(v));
const sign = (v) => (v < 0 ? MINUS : "");
const signed = (v, text) => (v > 0 ? "+" : v < 0 ? MINUS : "") + text;

/** Counts: exact below 1,000; 3 significant figures with commas; "x.y million" from 10 million. */
export function count(n) {
  if (missing(n)) return NA;
  const abs = Math.abs(n);
  if (abs < 1000) return sign(n) + abs.toLocaleString("en-US", {maximumFractionDigits: 1});
  const rounded = Number(abs.toPrecision(3));
  if (rounded >= 1e7) return `${sign(n)}${(abs / 1e6).toFixed(1)} million`;
  return sign(n) + rounded.toLocaleString("en-US");
}

/** Shares (fraction 0–1) as percent: 0 decimals at 10% and above, 1 decimal below. */
export function share(x) {
  if (missing(x)) return NA;
  const p = Math.abs(x * 100);
  return `${sign(x)}${p.toFixed(p >= 9.95 ? 0 : 1)}%`;
}

/** A change in a share (fraction difference) as signed percentage points. */
export function shareChange(d) {
  if (missing(d)) return NA;
  const pts = Math.round(d * 1000) / 10;
  return `${signed(pts, Math.abs(pts).toFixed(1))} pts`;
}

/** A relative change or estimated effect (fraction) as a signed percent. */
export function relChange(x) {
  if (missing(x)) return NA;
  const pct = Math.round(x * 1000) / 10;
  return `${signed(pct, Math.abs(pct).toFixed(1))}%`;
}

export const effect = relChange;

/** Dollars: 2 decimals under $100; whole dollars to $1 million; "$x.y million" above. */
export function usd(x) {
  if (missing(x)) return NA;
  const abs = Math.abs(x);
  if (Math.round(abs * 100) / 100 < 100) return `${sign(x)}$${abs.toFixed(2)}`;
  if (abs <= 1e6) return `${sign(x)}$${Math.round(abs).toLocaleString("en-US")}`;
  return `${sign(x)}$${(abs / 1e6).toFixed(1)} million`;
}

const usdPer = (unit) => (x) => (missing(x) ? NA : `${sign(x)}$${Math.abs(x).toFixed(2)}/${unit}`);
export const usdPerMile = usdPer("mile");
export const usdPerMinute = usdPer("min");
export const usdPerHour = usdPer("hour");

/** Waits (seconds) as minutes, 1 decimal. */
export function seconds(s) {
  return missing(s) ? NA : `${(s / 60).toFixed(1)} min`;
}

/** Not in contracts §3; chosen by L05: trips per hour to 2 decimals, like the money rates. */
export function tripsPerHour(x) {
  return missing(x) ? NA : `${x.toFixed(2)} trips/hour`;
}

/** Not in contracts §3; chosen by L05: a ratio such as p90 ÷ p10 to 1 decimal. */
export function ratio(x) {
  return missing(x) ? NA : `${x.toFixed(1)}×`;
}

/** Parses "YYYY-MM", "YYYY-MM-DD" or a Date as a UTC date (never local time). */
export function utcDate(d) {
  if (d instanceof Date) return d;
  const m = /^(\d{4})-(\d{2})(?:-(\d{2}))?/.exec(String(d));
  if (!m) throw new Error(`format: not a date: ${d}`);
  return new Date(Date.UTC(+m[1], +m[2] - 1, m[3] ? +m[3] : 1));
}

/** "Jan 2025". */
export function month(d) {
  if (missing(d)) return NA;
  const date = utcDate(d);
  return `${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/** "week of 6 Jan 2025" (week_start is the Monday). */
export function week(d) {
  if (missing(d)) return NA;
  const date = utcDate(d);
  return `week of ${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
}

/** "6 am", "12 pm". */
export function hourOfDay(h) {
  if (missing(h)) return NA;
  return `${h % 12 === 0 ? 12 : h % 12} ${h < 12 ? "am" : "pm"}`;
}

/** "Tue 6 pm" from hour of week 0–167, Sunday 00:00 = 0. */
export function hourOfWeek(how) {
  if (missing(how)) return NA;
  return `${DAYS[Math.floor(how / 24)]} ${hourOfDay(how % 24)}`;
}

export function weekday(day) {
  return DAYS[day];
}

/** The data month for captions: "Aug 2026" from "2026-08"; "MOCK" stays as it is. */
export function asOf(asOfMonth) {
  return /^\d{4}-\d{2}$/.test(asOfMonth ?? "") ? month(asOfMonth) : String(asOfMonth ?? NA);
}

// Units from contracts/site/tiles.yaml.
const BY_UNIT = {
  count, share, usd, effect, seconds, ratio,
  usd_per_mile: usdPerMile,
  usd_per_minute: usdPerMinute,
  usd_per_hour: usdPerHour,
  trips_per_hour: tripsPerHour,
  hour_of_day: hourOfDay,
  hour_of_week: hourOfWeek,
  text: (v) => (missing(v) || v === "" ? NA : String(v)),
};

/** Formats a value by its tile unit. */
export function value(unit, v) {
  const f = BY_UNIT[unit];
  if (!f) throw new Error(`format: unknown unit "${unit}"`);
  return f(v);
}

/** Formats a year-on-year change by its tile `yoy` kind; null for kind "none". */
export function change(kind, unit, v) {
  switch (kind) {
    case "relative": return relChange(v);
    case "pts": return shareChange(v);
    case "diff": return missing(v) ? NA : v === 0 ? value(unit, 0) : signed(v, value(unit, Math.abs(v)));
    case "none": return null;
    default: throw new Error(`format: unknown yoy kind "${kind}"`);
  }
}

// Mode codes and display names (contracts §2).
export const MODE_NAMES = {
  uber: "Uber",
  lyft: "Lyft",
  other_hv: "Other ride-hail",
  yellow: "Yellow cab",
  green: "Green cab",
  ride_hail: "Ride-hail",
  taxi: "Cabs",
  all: "All modes",
};

export function modeName(code) {
  return MODE_NAMES[code] ?? String(code);
}

// Axis ticks. Plain values follow §3; axes use compact ticks (200K, $10M) so labels fit,
// with the unit in the axis label.
function compact(v) {
  const abs = Math.abs(v);
  const [d, s] = abs >= 1e9 ? [1e9, "B"] : abs >= 1e6 ? [1e6, "M"] : abs >= 1e3 ? [1e3, "K"] : [1, ""];
  return sign(v) + +(abs / d).toFixed(1) + s;
}

const trimmedPercent = (v) => `${+(Math.abs(v) * 100).toFixed(1)}%`;

const AXIS = {
  count: compact,
  share: (v) => sign(v) + trimmedPercent(v),
  pts: (v) => `${signed(v, String(+(Math.abs(v) * 100).toFixed(1)))}`,
  effect: (v) => signed(v, trimmedPercent(v)),
  usd: (v) => sign(v) + "$" + (Math.abs(v) >= 1000 ? compact(Math.abs(v)) : Number.isInteger(v) ? Math.abs(v) : Math.abs(v).toFixed(2)),
  seconds: (v) => String(+v.toFixed(1)),   // charts draw waits in minutes

  ratio: (v) => `${+v.toFixed(1)}×`,
  trips_per_hour: (v) => String(+v.toFixed(2)),
  hour_of_day: hourOfDay,
  hour_of_week: hourOfWeek,
  month,
  week: (d) => {
    const date = utcDate(d);
    return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`;
  },
  number: (v) => v.toLocaleString("en-US"),
};
AXIS.usd_per_mile = AXIS.usd_per_minute = AXIS.usd_per_hour = AXIS.usd;

/** A Plot tickFormat for a unit (plus "pts", "month", "week" and "number"). */
export function axis(unit) {
  const f = AXIS[unit];
  if (!f) throw new Error(`format: no axis format for "${unit}"`);
  return f;
}
