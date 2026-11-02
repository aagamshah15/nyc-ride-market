---
title: Executive summary
---

<!-- Executive summary (D32): every finding on one page for readers without time for the detail.
     The tiles and all fifteen findings come from home.json (written by findings.py each month),
     grouped by theme; the page adds only theme names, who each theme matters to, and caveats, so it
     stays right after every refresh. Prints as a short report (print styles below). -->

```js
import {mockBanner, findingsList, siteUrl, html} from "./components/page.js";
import {statTiles} from "./components/statTiles.js";
import * as format from "./components/format.js";
```

```js
const home = FileAttachment("data/home.json").json();
const tiles = FileAttachment("data/tiles.json").json();
```

```js
// Themes in reading order: each lists its questions (SPEC Appendix A) and who acts on them.
const THEMES = [
  {title: "Who carries the city's trips", questions: ["Q1", "Q4", "Q10"], page: "/zones",
   who: "Uber, Lyft and their rivals; taxi fleets and medallion owners"},
  {title: "Congestion pricing", questions: ["Q2", "Q3", "Q14"], page: "/congestion-pricing",
   who: "The MTA, the TLC and anyone tracking the toll's money and its effect on trips"},
  {title: "Drivers and pay", questions: ["Q5", "Q6", "Q15"], page: "/drivers",
   who: "Driver groups, the TLC and the platforms"},
  {title: "What riders pay and how long they wait", questions: ["Q7", "Q8", "Q13"], page: "/prices",
   who: "Riders, reporters and the platforms' pricing teams"},
  {title: "Airports", questions: ["Q9"], page: "/airports",
   who: "Taxi fleets, the Port Authority and the platforms"},
  {title: "Accessible and shared rides", questions: ["Q11", "Q12"], page: "/companies/uber",
   who: "The TLC's accessibility program, the MTA and the platforms"}
];
const byQuestion = new Map(home.findings.map((f) => [f.question, f]));
// Headline findings first within each theme, then the rest in question order.
const themeFindings = (t) => t.questions.map((q) => byQuestion.get(q)).filter(Boolean)
  .sort((a, b) => (b.featured === true) - (a.featured === true));
```

```js
const banner = mockBanner(home);   // nothing for validated real data
if (banner) display(banner);
```

# Executive summary

<p class="nrm-summary-meta">NYC's ride market on one page: Uber, Lyft, yellow cabs and green cabs, from the TLC's public trip records. Data through ${format.asOf(home.as_of_month)}, updated as each month is published. ${html`<button class="nrm-print" type="button" onclick=${() => window.print()}>Print or save as PDF</button>`}</p>

## At a glance

```js
display(statTiles(home, tiles, {keys: ["trips_per_day", "rh_share", "platform_share", "cbd_fees_last_month"]}));
```

```js
display(html`${THEMES.map((t) => html`<section class="nrm-summary-theme">
  <h2>${t.title}</h2>
  <p class="nrm-note">Matters to: ${t.who}.</p>
  ${findingsList(themeFindings(t))}
  <p class="nrm-summary-more"><a href=${siteUrl(t.page)}>Full analysis</a></p>
</section>`)}`);
```

## How to read this

- Congestion-pricing results are **estimated effects**: trips touching the zone are compared with trips elsewhere, against the same weeks a year earlier. Other changes in those weeks can't be ruled out.
- Pay per hour means **per hour with a passenger**, not per hour logged in.
- Cab tip rates are **card-only**: cash tips aren't recorded.
- The records cover completed trips only. Unfilled requests, surge pricing and driver identity aren't in them.

Definitions, checks and known limits are on the [methods page](./methods). [Why the site exists and who it's for.](./about)

<style>
.nrm-summary-meta {
  color: var(--theme-foreground-muted);
  max-width: 760px;
}
.nrm-print {
  margin-left: 0.5rem;
  font: inherit;
  font-size: 13px;
  cursor: pointer;
}
.nrm-summary-theme {
  max-width: 760px;
  margin-top: 2rem;
}
.nrm-summary-theme h2 {
  margin-bottom: 0.25rem;
}
.nrm-summary-more {
  font-size: 14px;
  margin-top: 0.25rem;
}
@media print {
  #observablehq-sidebar, #observablehq-sidebar-toggle, #observablehq-toc, .nrm-print {
    display: none !important;
  }
  #observablehq-center {
    margin: 0 !important;
  }
  .nrm-summary-theme {
    break-inside: avoid;
    margin-top: 1rem;
  }
}
</style>
