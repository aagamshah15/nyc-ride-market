# Congestion-zone list: how it was drawn

Lane L04 · 24 Oct 2026 · SPEC §3.3, §7.1 · decision D9 · list in [`config/cbd_zones.csv`](../config/cbd_zones.csv)

**Result.** `core` has 38 zones: the Manhattan zones on the street grid that lie wholly south of 60th Street. `wide` adds 9 borderline zones: the 6 that straddle 60th Street and the 3 island zones. On the August 2026 ride-hail file, 99.70% of trips with both ends in `core` carry the congestion fee; for `wide` the figure is 97.91%.

This is the first draft for G1, refined by the exploratory fee check below. The formal SPEC §7.2 check on every 2025+ month is L08's, from `agg_cbd_pairs`.

## 1. Inputs

| File | Notes |
|---|---|
| `data/ref/taxi_zones.zip` | TLC shapefile, files dated 18 Feb 2026. 263 polygons. CRS **EPSG:2263** (NAD83 / New York Long Island, US feet), read from the `.prj` by DuckDB `spatial` |
| `data/ref/taxi_zone_lookup.csv` | 265 rows: 1–263 plus 264 (`Unknown` / `N/A`) and 265 (`N/A` / `Outside of NYC`) |
| `data/raw/fhvhv/2026-08.parquet` | 20,493,480 ride-hail trips; `cbd_congestion_fee` is 0 (14,078,947), 1.50 (6,414,519) or 3.00 (14) |

## 2. Lookup vs shapefile

`python -m pipeline.zones --check` runs these checks each time:

- LocationIDs 1–263 each appear exactly once in the shapefile, with no duplicates and none missing. `OBJECTID` equals `LocationID` on every row.
- Every zone name and borough in the shapefile matches the lookup exactly.
- Every geometry is valid and non-empty. Jamaica Bay (2) is the largest multi-part zone, with 33 parts.
- 264 and 265 have no polygon, as expected. They stay "unknown" and are flagged in clean (SPEC §4.2).
- Older copies of this shapefile had repeated LocationIDs. This copy has none, so the GeoJSON needs no documented exceptions.

## 3. How the list was drawn

1. **Candidates:** the 69 zones in the lookup's Manhattan borough.
2. **Area south of 60th Street,** measured in EPSG:2263. The 60th Street line runs through Columbus Circle (59th St, −73.98190, 40.76803), moved one block (264 ft) north and laid along Manhattan's street grid, 29° off true east–west. It is accurate to about half a block. The result splits cleanly: 41 zones lie 100% south, 7 straddle the line, and the remaining 21 lie wholly north.
3. **Fee check** (section 5): for each zone, the share of pickups, drop-offs and same-zone trips carrying `cbd_congestion_fee > 0`.

## 4. Borderline calls

| ID | Zone | Area south of 60th St | Call | Reason |
|---|---|---|---|---|
| 142 | Lincoln Square East | 13% | borderline (wide only) | Runs from about 58th to 74th St. Its pickup fee share (69.5%) sits between the core zones (96–100%) and zones wholly north (43% at most); about half of its same-zone trips (51.6%) are charged |
| 143 | Lincoln Square West | 13% | borderline | Same shape as 142, west of it; 65.5% of pickups charged, 29.0% of same-zone trips |
| 237 | Upper East Side South | 6% | borderline | The block from 59th to 60th St is inside; 67.3% of pickups charged, 32.8% of same-zone trips |
| 141 | Lenox Hill West | 5% | borderline | The block from 59th to 60th St is inside; 60.2% of pickups charged, 12.9% of same-zone trips |
| 140 | Lenox Hill East | 4% | borderline | The block from 59th to 60th St is inside; 54.4% of pickups charged, 12.4% of same-zone trips |
| 43 | Central Park | 2% | borderline | Runs from 59th to 110th St, so by area it is almost wholly outside. But pickups cluster at the park's edges, including Central Park South and Columbus Circle, which are inside. As a result its fee shares (66.2% of pickups, 41.3% of same-zone trips) look like the other straddling zones, not like zones north of 60th St |
| 103 | Liberty Island | 100% | borderline | South of 60th St in the borough of Manhattan, but not reachable by road. No ride-hail trips in August 2026 |
| 104 | Ellis Island | 100% | borderline | As 103. No trips |
| 105 | Governors Island | 100% | borderline | As 103. 3 pickups and 8 drop-offs in August 2026, too few to test |
| 202 | Roosevelt Island | 27% of its area falls south of the line's extension | **out** (not listed) | The island lies off Manhattan's street grid, and its road access is from Queens. The fee data agree: 0.8% of same-zone trips are charged, like zones wholly north (0–3.6%), and 19.2% of pickups are, below Upper East Side North (42.0%) |

The three island zones share one name in the lookup. IDs were matched to islands by area and centroid: 103 is 14.7 acres at (−74.045, 40.690); 104 is 27.6 acres at (−74.041, 40.699); 105 is 177.5 acres at (−74.019, 40.689).

Other calls:

- **Core zones along the untolled highways stay core.** Battery Park City (96.2% of pickups charged), Financial District South (96.7%), Clinton West (97.8%), World Trade Center (98.0%) and West Chelsea/Hudson Yards (98.3%) run along West Street/Route 9A, the Battery Park Underpass or the FDR Drive. Those roads are outside the toll zone, so a trip that joins them at once can avoid the fee. All five sit far above the highest borderline zone (69.5%).
- **The 98% both-in threshold holds for `core` (99.70%) but not for `wide` (97.91%).** The borderline zones lie mostly north of 60th St, so trips between their northern parts are not charged (28.2% of trips between two borderline zones are). L08 checks both lists against SPEC §7.2. See the follow-up in the L04 status log.
- **Pass-through trips** (neither end in the list) carry the fee 2.53% of the time for `core` and 2.05% excluding zones 264 and 265. Drop-offs in zone 265 ("Outside of NYC") are charged 41.5% of the time, which fits trips to New Jersey that cross Manhattan.

## 5. Fee check, August 2026 ride-hail

Reproduce with `NYC_DATA_DIR=… python -m pipeline.zones --explore 2026-08`. It reads three raw columns and writes `data/scratch/L04/fhvhv_2026-08_pairs.parquet` (same shape as `agg_cbd_pairs`) and `fee_check_2026-08.csv`. The brief asked for a 2025 month; August 2026 was used because it is the post-pricing month already downloaded, and the fee rules were unchanged.

"Same-zone trips" have both pickup and drop-off in that zone. For zones wholly inside, nearly all of them pay the fee; for zones wholly outside, almost none do.

| List | Zones | Both in: trips | Both in: fee share | One in: fee share | Neither in: trips | Neither in: fee share |
|---|---|---|---|---|---|---|
| core | 38 | 2,615,766 | 99.70% | 98.51% | 14,382,896 | 2.53% |
| wide | 47 | 3,150,431 | 97.91% | 89.19% | 13,793,002 | 1.19% |

| ID | Zone | List | Area south of 60th St | Pickups | Pickup fee share | Drop-offs | Drop-off fee share | Same-zone trips | Same-zone fee share |
|---|---|---|---|---|---|---|---|---|---|
| 12 | Battery Park | core | 100.0% | 3,054 | 99.8% | 4,145 | 98.3% | 1 | 100.0% |
| 230 | Times Sq/Theatre District | core | 100.0% | 224,239 | 99.8% | 191,210 | 99.2% | 4,063 | 98.8% |
| 79 | East Village | core | 100.0% | 227,121 | 99.8% | 185,744 | 99.6% | 6,685 | 99.4% |
| 211 | SoHo | core | 100.0% | 100,811 | 99.8% | 90,685 | 99.7% | 1,042 | 98.6% |
| 100 | Garment District | core | 100.0% | 107,000 | 99.8% | 81,989 | 99.4% | 816 | 96.9% |
| 114 | Greenwich Village South | core | 100.0% | 102,675 | 99.8% | 86,010 | 99.6% | 932 | 98.3% |
| 144 | Little Italy/NoLiTa | core | 100.0% | 128,469 | 99.8% | 103,087 | 99.6% | 1,279 | 98.6% |
| 113 | Greenwich Village North | core | 100.0% | 97,062 | 99.7% | 77,880 | 99.5% | 1,210 | 98.9% |
| 162 | Midtown East | core | 100.0% | 146,051 | 99.7% | 156,157 | 99.3% | 1,952 | 98.3% |
| 163 | Midtown North | core | 100.0% | 143,565 | 99.7% | 122,811 | 99.2% | 1,707 | 98.9% |
| 164 | Midtown South | core | 100.0% | 188,599 | 99.7% | 156,018 | 99.3% | 2,331 | 98.7% |
| 186 | Penn Station/Madison Sq West | core | 100.0% | 120,750 | 99.7% | 131,639 | 99.5% | 798 | 96.9% |
| 249 | West Village | core | 100.0% | 166,138 | 99.7% | 137,672 | 99.6% | 2,883 | 99.1% |
| 148 | Lower East Side | core | 100.0% | 195,758 | 99.7% | 148,629 | 99.6% | 3,366 | 98.3% |
| 48 | Clinton East | core | 100.0% | 173,842 | 99.7% | 138,182 | 99.5% | 4,095 | 98.7% |
| 161 | Midtown Center | core | 100.0% | 221,684 | 99.7% | 185,890 | 99.3% | 3,400 | 98.9% |
| 229 | Sutton Place/Turtle Bay North | core | 100.0% | 97,383 | 99.7% | 79,457 | 99.4% | 1,309 | 99.0% |
| 68 | East Chelsea | core | 100.0% | 202,326 | 99.7% | 209,607 | 99.5% | 5,377 | 99.2% |
| 170 | Murray Hill | core | 100.0% | 162,922 | 99.7% | 165,335 | 99.4% | 3,110 | 98.8% |
| 234 | Union Sq | core | 100.0% | 187,209 | 99.7% | 157,874 | 99.5% | 2,738 | 99.1% |
| 107 | Gramercy | core | 100.0% | 125,456 | 99.7% | 109,718 | 99.4% | 1,969 | 98.6% |
| 45 | Chinatown | core | 100.0% | 49,945 | 99.6% | 42,824 | 99.4% | 385 | 98.4% |
| 90 | Flatiron | core | 100.0% | 119,647 | 99.6% | 97,914 | 99.2% | 1,669 | 98.1% |
| 125 | Hudson Sq | core | 100.0% | 65,346 | 99.6% | 55,813 | 99.3% | 399 | 96.5% |
| 87 | Financial District North | core | 100.0% | 117,528 | 99.5% | 108,183 | 98.9% | 1,271 | 97.6% |
| 209 | Seaport | core | 100.0% | 41,118 | 99.4% | 37,725 | 95.6% | 251 | 96.0% |
| 137 | Kips Bay | core | 100.0% | 98,653 | 99.3% | 99,374 | 98.0% | 993 | 97.3% |
| 231 | TriBeCa/Civic Center | core | 100.0% | 181,573 | 99.2% | 153,247 | 98.8% | 6,225 | 99.2% |
| 224 | Stuy Town/Peter Cooper Village | core | 100.0% | 36,539 | 99.2% | 30,745 | 97.6% | 172 | 98.3% |
| 158 | Meatpacking/West Village West | core | 100.0% | 98,192 | 99.0% | 86,017 | 98.8% | 1,134 | 98.8% |
| 232 | Two Bridges/Seward Park | core | 100.0% | 81,773 | 99.0% | 68,098 | 98.1% | 2,022 | 97.1% |
| 233 | UN/Turtle Bay South | core | 100.0% | 100,272 | 98.8% | 92,168 | 97.3% | 1,164 | 98.7% |
| 4 | Alphabet City | core | 100.0% | 53,056 | 98.6% | 45,602 | 99.2% | 505 | 97.8% |
| 246 | West Chelsea/Hudson Yards | core | 100.0% | 188,779 | 98.3% | 175,587 | 98.5% | 5,454 | 97.7% |
| 261 | World Trade Center | core | 100.0% | 67,853 | 98.0% | 62,217 | 95.6% | 556 | 94.6% |
| 50 | Clinton West | core | 100.0% | 101,176 | 97.8% | 82,631 | 97.1% | 1,516 | 97.1% |
| 88 | Financial District South | core | 100.0% | 50,713 | 96.7% | 52,312 | 97.7% | 193 | 97.4% |
| 13 | Battery Park City | core | 100.0% | 75,673 | 96.2% | 66,204 | 97.2% | 994 | 97.3% |
| 142 | Lincoln Square East | borderline | 13.1% | 114,157 | 69.5% | 104,276 | 63.7% | 2,449 | 51.6% |
| 237 | Upper East Side South | borderline | 5.7% | 131,240 | 67.3% | 126,806 | 58.0% | 5,449 | 32.8% |
| 43 | Central Park | borderline | 1.8% | 31,083 | 66.2% | 39,587 | 67.8% | 550 | 41.3% |
| 143 | Lincoln Square West | borderline | 13.4% | 80,573 | 65.5% | 61,368 | 63.6% | 1,628 | 29.0% |
| 141 | Lenox Hill West | borderline | 5.1% | 111,950 | 60.2% | 98,919 | 51.4% | 2,294 | 12.9% |
| 140 | Lenox Hill East | borderline | 3.7% | 106,964 | 54.4% | 117,625 | 45.3% | 2,362 | 12.4% |
| 239 | Upper West Side South | out | 0.0% | 105,141 | 43.1% | 96,857 | 38.8% | 3,013 | 0.9% |
| 236 | Upper East Side North | out | 0.0% | 104,786 | 42.0% | 101,347 | 38.4% | 3,712 | 1.0% |
| 262 | Yorkville East | out | 0.0% | 59,635 | 41.2% | 51,837 | 38.8% | 645 | 3.6% |
| 263 | Yorkville West | out | 0.0% | 94,128 | 39.1% | 87,371 | 38.2% | 1,692 | 1.2% |
| 105 | Governor's Island/Ellis Island/Liberty Island | borderline | 100.0% | 3 | 33.3% | 8 | 50.0% | 0 | — |
| 238 | Upper West Side North | out | 0.0% | 87,932 | 29.4% | 79,096 | 31.0% | 2,560 | 0.9% |
| 151 | Manhattan Valley | out | 0.0% | 54,878 | 23.1% | 49,926 | 24.6% | 1,279 | 1.4% |
| 24 | Bloomingdale | out | 0.0% | 25,591 | 20.7% | 24,276 | 22.0% | 277 | 0.4% |
| 194 | Randalls Island | out | 0.0% | 4,067 | 20.5% | 13,482 | 15.7% | 54 | 1.8% |
| 202 | Roosevelt Island | out | 26.6% | 12,976 | 19.2% | 14,135 | 26.4% | 379 | 0.8% |
| 75 | East Harlem South | out | 0.0% | 127,542 | 18.8% | 130,385 | 18.0% | 8,774 | 0.3% |
| 166 | Morningside Heights | out | 0.0% | 72,953 | 17.7% | 77,466 | 17.5% | 4,502 | 0.2% |
| 152 | Manhattanville | out | 0.0% | 45,360 | 12.3% | 45,408 | 11.2% | 1,234 | 0.3% |
| 116 | Hamilton Heights | out | 0.0% | 93,688 | 10.9% | 87,318 | 11.2% | 5,625 | 0.1% |
| 41 | Central Harlem | out | 0.0% | 136,798 | 10.7% | 122,282 | 11.7% | 9,100 | 0.2% |
| 74 | East Harlem North | out | 0.0% | 154,503 | 10.3% | 143,553 | 9.0% | 11,568 | 0.1% |
| 244 | Washington Heights South | out | 0.0% | 156,860 | 10.1% | 151,312 | 10.5% | 14,314 | 0.1% |
| 243 | Washington Heights North | out | 0.0% | 111,765 | 10.0% | 98,647 | 10.1% | 11,732 | 0.0% |
| 128 | Inwood Hill Park | out | 0.0% | 6,621 | 9.2% | 8,137 | 6.9% | 29 | 0.0% |
| 42 | Central Harlem North | out | 0.0% | 192,374 | 9.0% | 171,695 | 9.7% | 20,977 | 0.1% |
| 127 | Inwood | out | 0.0% | 82,464 | 7.4% | 79,686 | 7.2% | 4,778 | 0.1% |
| 120 | Highbridge Park | out | 0.0% | 2,172 | 7.0% | 3,050 | 10.9% | 6 | 0.0% |
| 153 | Marble Hill | out | 0.0% | 20,472 | 2.4% | 16,795 | 3.1% | 294 | 0.0% |
| 103 | Governor's Island/Ellis Island/Liberty Island | borderline | 100.0% | 0 | — | 0 | — | 0 | — |
| 104 | Governor's Island/Ellis Island/Liberty Island | borderline | 100.0% | 0 | — | 0 | — | 0 | — |

## 6. Map geometry

`python -m pipeline.zones` writes `data/ref/taxi_zones.simplified.geojson` (generated, not committed; L11 copies it to `site/src/data/taxi_zones.geojson`):

- Reprojected EPSG:2263 → EPSG:4326 with DuckDB `ST_Transform(…, always_xy := true)`, so coordinates are lon/lat.
- Simplified with mapshaper 0.7.98 (`site/node_modules`) to 10% of vertices with `keep-shapes` and 0.00001° precision: **388,275 bytes**, 263 features, 263 distinct LocationIDs, properties `LocationID`, `zone`, `borough` only.
- **Winding:** mapshaper 0.7 writes RFC 7946 winding (counter-clockwise exteriors) by default. The build passes `gj2008`, so exterior rings run clockwise as d3-geo expects (contracts/README.md §7). The check fails on any counter-clockwise exterior ring.
- `keep-shapes` keeps every zone, but it drops tiny islets: 354 exterior rings in the source become 315.
- mapshaper reports about 96 segment intersections it cannot repair. They come from the source, where neighbouring zones overlap slightly: there are more at 50% retention (212) than at 10%. Neither the checks nor a rendered preview show visible artefacts.
