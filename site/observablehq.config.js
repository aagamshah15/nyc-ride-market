// Observable Framework config. Seeded by L00; owned by L05 (Site foundation).
// Routes follow SPEC §9.1 plus /zones (D13); the route list is pinned in contracts/site/pages.yaml.
//
// Page files arrive from the page lanes (L12–L16) one at a time. Framework fails the build on a
// nav entry or dynamic path whose page doesn't exist yet, so both lists include only the pages
// present in src/.

import {existsSync} from "node:fs";
import {fileURLToPath} from "node:url";

const exists = (source) => existsSync(fileURLToPath(new URL(`./src/${source}`, import.meta.url)));

const COMPANIES = {uber: "Uber", lyft: "Lyft", yellow: "Yellow cabs", green: "Green cabs"};
const ZONES = Array.from({length: 263}, (_, i) => i + 1);   // 264 and 265 are "unknown": no pages

const NAV = [
  {name: "Congestion pricing", path: "/congestion-pricing", source: "congestion-pricing.md"},
  {
    name: "Companies",
    source: "companies/[company].md",
    pages: Object.entries(COMPANIES).map(([company, name]) => ({name, path: `/companies/${company}`}))
  },
  {name: "Zones", path: "/zones/", source: "zones/index.md"},
  {name: "Airports", path: "/airports", source: "airports.md"},
  {name: "Drivers", path: "/drivers", source: "drivers.md"},
  {name: "Prices", path: "/prices", source: "prices.md"},
  {name: "Methods", path: "/methods", source: "methods.md"}
];

export default {
  title: "NYC Ride Market",
  root: "src",
  style: "style.css",
  globalStylesheets: [],   // Inter is self-hosted (style.css); no Google Fonts request
  pages: NAV.filter(({source}) => exists(source)).map(({source, ...page}) => page),
  dynamicPaths: [
    ...(exists("companies/[company].md") ? Object.keys(COMPANIES).map((c) => `/companies/${c}`) : []),
    ...(exists("zones/[zone].md") ? ZONES.map((z) => `/zones/${z}`) : [])
  ],
  toc: false,
  pager: false,
  search: false,
  footer: "Independent analysis of public NYC TLC data. Not affiliated with any company named."
};
