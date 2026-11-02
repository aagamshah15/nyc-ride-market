---
title: About
---

<!-- About (D31): why the site exists, how it's built and who can use it. Prose only; the few
     figures (date range, trips a day, policy dates) come from home.json, share_monthly.json and
     events.json, so the page adds no numbers of its own. -->

```js
import * as format from "./components/format.js";
```

```js
const home = FileAttachment("data/home.json").json();
const shareMonthly = FileAttachment("data/share_monthly.json").json();
const events = FileAttachment("data/events.json").json();
```

```js
const firstMonth = shareMonthly.rows.reduce((a, r) => (r.month < a ? r.month : a), shareMonthly.rows[0].month);
const span = `${format.month(firstMonth)} to ${format.asOf(home.as_of_month)}`;
const tripsPerDay = format.count(home.tiles.trips_per_day);
const eventDate = (id) => events.events.find((e) => e.id === id)?.date;
const eventDay = (id) => format.day(eventDate(id));
const policyYear = format.utcDate(eventDate("congestion_pricing_start")).getUTCFullYear();
```

# About NYC Ride Market

An independent, public look at New York City's ride market (Uber, Lyft, yellow cabs and green cabs), built entirely from the trip records the city's Taxi and Limousine Commission (TLC) publishes.

## Why it exists

Two policy changes reshaped getting around New York in ${policyYear}. Congestion pricing began charging trips into Manhattan's congestion zone on ${eventDay("congestion_pricing_start")}, and a new minimum-pay rule for app drivers took effect on ${eventDay("driver_pay_rise")}. Riders, drivers, the platforms and the city all have a stake in what followed: who lost trips, who raised prices, and how much of the fare reaches the driver.

The answers sit in public data, but not in a usable form. The TLC releases tens of millions of trip records a month and leaves the analysis to others, and the platforms publish little. This site turns those records into plain answers that anyone can check, with every chart traced back to the same published numbers.

## How it works

- **Public data only.** Every trip record the TLC publishes for ride-hail apps, yellow cabs and green cabs, from ${span}: about ${tripsPerDay} trips a day.
- **Cleaned, never deleted.** Records with impossible times, distances or fares, or an unknown zone, are flagged and left out of the averages, but they're kept and counted.
- **Checked before publishing.** Each month must match the TLC's own monthly totals and pass quality checks. If a check fails, nothing is published until it's fixed.
- **Measured once.** Each measure is defined once, and every page reads the same results. Rates are totals divided by totals, never averages of per-trip ratios.
- **Refreshed on its own.** A weekly job picks up each new month when the TLC posts it, about two months after the month ends, then validates it and updates the site. It also watches for the TLC revising recent months.

The [methods page](./methods) has the details: cleaning rules, the checks, how the policy effects are estimated, known limits and the data files to download.

## Who it's for

| Who | What they can use here | Where |
|---|---|---|
| The TLC and other regulators | How app drivers' pay and their share of the fare moved after the new pay rule; how many trips run in wheelchair-accessible vehicles; how many hours drivers work | [Drivers](./drivers), [Companies](./companies/uber) |
| The MTA and city budget watchers | The estimated effect of congestion pricing on trips touching the zone, and the congestion fees charged each month by mode | [Congestion pricing](./congestion-pricing) |
| Uber, Lyft and their rivals | Market share by zone and hour, where Lyft leads Uber, and who wins the airport trip | [Zones](./zones/), [Companies](./companies/lyft), [Airports](./airports) |
| Taxi fleets and medallion owners | Where yellow cabs still lead, their share at the airports, and how cab fares compare | [Zones](./zones/), [Airports](./airports), [Prices](./prices) |
| Driver groups | What share of the fare drivers keep, and their pay per hour with a passenger | [Drivers](./drivers) |
| Riders and reporters | What a mile or a minute costs by company, hour and borough; how long riders wait; how much riders tip | [Prices](./prices), [Zones](./zones/) |

## What it isn't

- **Not affiliated.** The site is independent and isn't funded or reviewed by any company it names. It uses no logos.
- **Not proof of cause.** The congestion-pricing results are estimated effects: they compare trips touching the zone with trips elsewhere, against the same weeks a year earlier. Other changes in those weeks can't be ruled out.
- **Only what the records show.** The data covers trips that happened. Unfilled requests, surge pricing, driver identity and cash tips aren't in it, so cab tip rates are card-only.
- **Pay per hour means per hour with a passenger,** not per hour logged in.

The code and data pipeline are open on [GitHub](https://github.com/aagamshah15/nyc-ride-market).
