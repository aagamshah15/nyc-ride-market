"""Zone shapefile → simplified GeoJSON, zone checks, and the congestion-zone helper.

Lane L04 · SPEC §3.3, §7 · decision D9 · docs/lanes/L04-zones.md

    python -m pipeline.zones                    # build data/ref/taxi_zones.simplified.geojson, then check
    python -m pipeline.zones --check            # check the lookup, shapefile, zone lists and GeoJSON only
    python -m pipeline.zones --explore 2026-08  # area south of 60th St and fee share by zone → data/scratch/L04/

The congestion-zone list lives in ``config/cbd_zones.csv`` (``LocationID, zone, borderline, note``).
``core`` excludes borderline zones; ``wide`` includes them (D9). The reasons for each call are in
``reports/cbd_zones.md``.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter
from pathlib import Path

from pipeline import common
from pipeline.common import sql_literal

ZONE_IDS = frozenset(range(1, 264))   # zones with polygons; 264 and 265 are "unknown" (SPEC §3.3)
ZONE_LISTS = ("core", "wide")
CBD_COLUMNS = ["LocationID", "zone", "borderline", "note"]
AIRPORT_NAMES = {"EWR": "Newark Airport", "JFK": "JFK Airport", "LGA": "LaGuardia Airport"}
AIRPORT_SERVICE_ZONES = ("Airports", "EWR")

GEOJSON_PROPERTIES = ("LocationID", "zone", "borough")
GEOJSON_MAX_BYTES = 1_000_000          # SPEC §9.2: under 1 MB
SIMPLIFY = "10%"                       # share of vertices mapshaper keeps
PRECISION = "0.00001"                  # degrees, about 1 m
NYC_BBOX = (-74.35, 40.45, -73.65, 40.95)   # lon/lat box every vertex must fall in

# 60th Street, for the area check in --explore: a line through Columbus Circle (59th St)
# moved one block north, running along Manhattan's street grid (29° off true east-west).
COLUMBUS_CIRCLE = (-73.98190, 40.76803)
GRID_ANGLE_DEG = 29.0
BLOCK_FT = 264.0

SITE_DIR = common.REPO_ROOT / "site"


# --- paths -------------------------------------------------------------------

def shapefile_path() -> Path:
    return common.ref_dir() / "taxi_zones.zip"


def lookup_path() -> Path:
    return common.ref_dir() / "taxi_zone_lookup.csv"


def geojson_path() -> Path:
    """Generated map geometry; L11 copies it to ``site/src/data/taxi_zones.geojson``."""
    return common.ref_dir() / "taxi_zones.simplified.geojson"


# --- zone lists --------------------------------------------------------------

def load_cbd_zones(path: Path | None = None) -> list[dict]:
    """Rows of ``config/cbd_zones.csv`` with ``LocationID`` as int and ``borderline`` as bool."""
    path = path or common.CONFIG_DIR / "cbd_zones.csv"
    with open(path, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != CBD_COLUMNS:
            raise ValueError(f"{path.name}: header must be {CBD_COLUMNS}, got {reader.fieldnames}")
        rows = []
        for line, row in enumerate(reader, start=2):
            if row["borderline"] not in ("true", "false"):
                raise ValueError(f"{path.name}:{line}: borderline must be true or false, got {row['borderline']!r}")
            zone = int(row["LocationID"])
            if zone not in ZONE_IDS:
                raise ValueError(f"{path.name}:{line}: LocationID {zone} is not a mapped zone (1–263)")
            rows.append({**row, "LocationID": zone, "borderline": row["borderline"] == "true"})
    dupes = [z for z, n in Counter(r["LocationID"] for r in rows).items() if n > 1]
    if dupes:
        raise ValueError(f"{path.name}: duplicate LocationIDs {sorted(dupes)}")
    return rows


def cbd_zone_ids(zone_list: str = "core") -> set[int]:
    """LocationIDs in the congestion zone. ``core`` excludes borderline zones; ``wide`` includes them."""
    if zone_list not in ZONE_LISTS:
        raise ValueError(f"zone_list must be one of {ZONE_LISTS}, got {zone_list!r}")
    return {r["LocationID"] for r in load_cbd_zones() if zone_list == "wide" or not r["borderline"]}


def airport_zones() -> dict[int, str]:
    """LocationID → airport code, from config/airports.csv."""
    rows = common.load_csv("airports.csv")
    airports = {int(r["LocationID"]): r["airport"] for r in rows}
    if len(airports) != len(rows):
        raise ValueError("airports.csv: duplicate LocationIDs")
    return airports


# --- lookup and config checks ------------------------------------------------

def read_lookup(path: Path | None = None) -> dict[int, dict[str, str]]:
    """``taxi_zone_lookup.csv`` as LocationID → {Borough, Zone, service_zone}."""
    path = path or lookup_path()
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    lookup = {int(r["LocationID"]): r for r in rows}
    if len(lookup) != len(rows):
        raise ValueError(f"{path.name}: duplicate LocationIDs")
    return lookup


def config_problems(lookup: dict[int, dict[str, str]]) -> list[str]:
    """Airports and the congestion-zone list checked against the zone lookup."""
    problems = []
    airports = airport_zones()
    for zone, code in sorted(airports.items()):
        expected = AIRPORT_NAMES.get(code)
        if expected is None:
            problems.append(f"airports.csv: unknown airport code {code!r} for zone {zone}")
        elif zone not in lookup:
            problems.append(f"airports.csv: zone {zone} ({code}) is not in the lookup")
        elif lookup[zone]["Zone"] != expected:
            problems.append(f"airports.csv: zone {zone} is {lookup[zone]['Zone']!r} in the lookup, expected {expected!r}")
    for zone, row in sorted(lookup.items()):
        if row["service_zone"] in AIRPORT_SERVICE_ZONES and zone not in airports:
            problems.append(f"airports.csv: lookup zone {zone} ({row['Zone']}) is an airport but not listed")
    for row in load_cbd_zones():
        zone = row["LocationID"]
        if zone not in lookup:
            problems.append(f"cbd_zones.csv: zone {zone} is not in the lookup")
        elif lookup[zone]["Borough"] != "Manhattan":
            problems.append(f"cbd_zones.csv: zone {zone} is in {lookup[zone]['Borough']}, not Manhattan")
        elif lookup[zone]["Zone"] != row["zone"]:
            problems.append(f"cbd_zones.csv: zone {zone} is {lookup[zone]['Zone']!r} in the lookup, not {row['zone']!r}")
        if row["borderline"] and not row["note"]:
            problems.append(f"cbd_zones.csv: borderline zone {zone} has no note")
    return problems


# --- shapefile ---------------------------------------------------------------

def spatial_connection():
    con = common.connect()
    con.execute("INSTALL spatial")    # no-op once installed
    con.execute("LOAD spatial")
    return con


def shapefile_source(path: Path | None = None) -> str:
    """GDAL path to the one ``.shp`` inside the zone archive."""
    path = path or shapefile_path()
    with zipfile.ZipFile(path) as z:
        shps = [n for n in z.namelist() if n.lower().endswith(".shp")]
    if len(shps) != 1:
        raise ValueError(f"{path.name}: expected one .shp, found {shps}")
    return f"/vsizip/{path.resolve()}/{shps[0]}"


def source_crs(con, source: str) -> str:
    """The layer's CRS as ``AUTH:CODE`` (EPSG:2263 for the TLC file). No CRS is an error."""
    layers = con.execute(f"SELECT layers FROM ST_Read_Meta({sql_literal(source)})").fetchone()[0]
    crs = layers[0]["geometry_fields"][0].get("crs") or {}
    if not crs.get("auth_name") or not crs.get("auth_code"):
        raise ValueError(f"{source}: the shapefile has no recognised CRS")
    return f"{crs['auth_name']}:{crs['auth_code']}"


def source_problems(con, source: str, lookup: dict[int, dict[str, str]]) -> list[str]:
    """Shapefile vs lookup: IDs 1–263 each once, names and boroughs equal, geometries valid."""
    rows = con.execute(f"""
        SELECT LocationID, zone, borough, ST_IsValid(geom) AND NOT ST_IsEmpty(geom)
        FROM ST_Read({sql_literal(source)})""").fetchall()
    problems = []
    counts = Counter(r[0] for r in rows)
    if dupes := sorted(z for z, n in counts.items() if n > 1):
        problems.append(f"shapefile: duplicate LocationIDs {dupes}")
    if missing := sorted(ZONE_IDS - set(counts)):
        problems.append(f"shapefile: missing LocationIDs {missing}")
    if extra := sorted(set(counts) - ZONE_IDS, key=str):
        problems.append(f"shapefile: unexpected LocationIDs {extra}")
    for zone, name, borough, valid in sorted(rows, key=lambda r: (r[0] is None, r[0])):
        if not valid:
            problems.append(f"shapefile: zone {zone} has an invalid or empty geometry")
        ref = lookup.get(zone)
        if ref and (ref["Zone"], ref["Borough"]) != (name, borough):
            problems.append(f"shapefile: zone {zone} is {name!r}/{borough!r}, lookup says {ref['Zone']!r}/{ref['Borough']!r}")
    if missing_in_shp := sorted(set(lookup) - set(counts) - {264, 265}):
        problems.append(f"lookup: zones without a polygon {missing_in_shp}")
    return problems


# --- GeoJSON -----------------------------------------------------------------

def build_geojson(out: Path | None = None, shapefile: Path | None = None) -> Path:
    """Reproject the zone shapefile to WGS84 and simplify it with mapshaper.

    Exterior rings come out clockwise, as d3-geo expects (contracts/README.md §7). Mapshaper
    0.7 writes RFC 7946 (counter-clockwise) winding by default, so this passes ``gj2008``.
    """
    out = out or geojson_path()
    con = spatial_connection()
    source = shapefile_source(shapefile)
    crs = source_crs(con, source)
    rows = con.execute(f"""
        SELECT LocationID, zone, borough,
               ST_AsGeoJSON(ST_Transform(geom, {sql_literal(crs)}, 'EPSG:4326', always_xy := true))
        FROM ST_Read({sql_literal(source)}) ORDER BY LocationID""").fetchall()
    features = [{"type": "Feature",
                 "properties": {"LocationID": zone, "zone": name, "borough": borough},
                 "geometry": json.loads(geometry)}
                for zone, name, borough, geometry in rows]
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=common.scratch_dir("L04")) as tmp:
        full, simplified = Path(tmp) / "taxi_zones.wgs84.geojson", Path(tmp) / "taxi_zones.simplified.geojson"
        full.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
        cmd = ["npx", "--no", "--", "mapshaper", "-i", str(full),
               "-filter-fields", ",".join(GEOJSON_PROPERTIES),
               "-simplify", f"percentage={SIMPLIFY}", "keep-shapes",
               "-o", str(simplified), "format=geojson", "gj2008", f"precision={PRECISION}"]
        result = subprocess.run(cmd, cwd=SITE_DIR, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"mapshaper failed (run `make setup` if it is missing):\n{result.stderr}")
        os.replace(simplified, out)
    return out


def _ring_area(ring: list[list[float]]) -> float:
    """Signed planar area in degrees²; negative when the ring runs clockwise."""
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(ring, ring[1:])) / 2


def geojson_problems(path: Path | None = None, expected_ids=ZONE_IDS,
                     max_bytes: int = GEOJSON_MAX_BYTES) -> list[str]:
    """Size, IDs, properties, WGS84 range and ring winding of the map file."""
    path = path or geojson_path()
    if not path.exists():
        return [f"{path} does not exist; run python -m pipeline.zones"]
    problems = []
    size = path.stat().st_size
    if size >= max_bytes:
        problems.append(f"{path.name}: {size:,} bytes; must be under {max_bytes:,}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("type") != "FeatureCollection":
        return problems + [f"{path.name}: not a FeatureCollection"]
    west, south, east, north = NYC_BBOX
    ids = Counter()
    for feature in data.get("features", []):
        props = feature.get("properties") or {}
        zone = props.get("LocationID")
        ids[zone] += 1
        if set(props) != set(GEOJSON_PROPERTIES):
            problems.append(f"zone {zone}: properties {sorted(props)}, expected {sorted(GEOJSON_PROPERTIES)}")
        geometry = feature.get("geometry") or {}
        kind = geometry.get("type")
        if kind not in ("Polygon", "MultiPolygon") or not geometry.get("coordinates"):
            problems.append(f"zone {zone}: geometry {kind!r} is not a non-empty polygon")
            continue
        polygons = [geometry["coordinates"]] if kind == "Polygon" else geometry["coordinates"]
        for polygon in polygons:
            for i, ring in enumerate(polygon):
                if len(ring) < 4 or ring[0] != ring[-1]:
                    problems.append(f"zone {zone}: a ring is not closed or has under 4 points")
                    break
                if not all(west <= x <= east and south <= y <= north for x, y in ring):
                    problems.append(f"zone {zone}: coordinates outside the NYC lon/lat box (not WGS84?)")
                    break
                area = _ring_area(ring)
                if (i == 0 and area >= 0) or (i > 0 and area <= 0):
                    which = "exterior ring is not clockwise" if i == 0 else "hole is not counter-clockwise"
                    problems.append(f"zone {zone}: {which}")
                    break
    if dupes := sorted(z for z, n in ids.items() if n > 1):
        problems.append(f"{path.name}: duplicate LocationIDs {dupes}")
    if missing := sorted(set(expected_ids) - set(ids)):
        problems.append(f"{path.name}: missing LocationIDs {missing}")
    if extra := sorted(set(ids) - set(expected_ids), key=str):
        problems.append(f"{path.name}: unexpected LocationIDs {extra}")
    return problems


# --- exploratory fee check (SPEC §7.1; the formal §7.2 check is L08's) --------

def _south_of_60th_wkt(con) -> str:
    """Half-plane south of 60th Street as a polygon in EPSG:2263 (feet)."""
    lon, lat = COLUMBUS_CIRCLE
    cx, cy = con.execute(f"""
        SELECT ST_X(g), ST_Y(g) FROM (SELECT ST_Transform(ST_Point({lon}, {lat}),
               'EPSG:4326', 'EPSG:2263', always_xy := true) AS g)""").fetchone()
    angle = math.radians(GRID_ANGLE_DEG)
    up = (math.sin(angle), math.cos(angle))        # uptown, along the avenues
    east = (math.cos(angle), -math.sin(angle))     # along the streets
    px, py = cx + up[0] * BLOCK_FT, cy + up[1] * BLOCK_FT
    reach, depth = 60_000, 200_000
    a = (px - east[0] * reach, py - east[1] * reach)
    b = (px + east[0] * reach, py + east[1] * reach)
    c = (b[0] - up[0] * depth, b[1] - up[1] * depth)
    d = (a[0] - up[0] * depth, a[1] - up[1] * depth)
    return "POLYGON((" + ", ".join(f"{x} {y}" for x, y in (a, b, c, d, a)) + "))"


def explore(month: str) -> tuple[Path, str]:
    """Area south of 60th St and fee share by pickup / drop-off zone for one HVFHV month.

    Exploratory, for reports/cbd_zones.md: reads three raw columns directly and writes only
    under ``data/scratch/L04/``. Returns the per-zone CSV and a markdown summary.
    """
    raw = common.raw_path("fhvhv", month)
    if not raw.exists():
        raise FileNotFoundError(f"{raw} not found; L02 downloads it")
    scratch = common.scratch_dir("L04")
    pairs = scratch / f"fhvhv_{month}_pairs.parquet"
    zones_csv = scratch / f"fee_check_{month}.csv"
    con = spatial_connection()
    source = shapefile_source()
    crs = source_crs(con, source)
    con.execute(f"""COPY (
        SELECT PULocationID AS pu_zone, DOLocationID AS do_zone, count(*) AS trips_all,
               count(*) FILTER (WHERE coalesce(cbd_congestion_fee, 0) > 0) AS trips_cbd_fee
        FROM read_parquet({sql_literal(str(raw))}) GROUP BY ALL
    ) TO {sql_literal(str(pairs))} (FORMAT parquet)""")
    con.execute(f"CREATE TEMP VIEW pairs AS SELECT * FROM read_parquet({sql_literal(str(pairs))})")
    rows = load_cbd_zones()
    lists = {"core": {r["LocationID"] for r in rows if not r["borderline"]},
             "wide": {r["LocationID"] for r in rows}}
    con.execute("CREATE TEMP TABLE lists (LocationID INTEGER, list VARCHAR)")
    con.executemany("INSERT INTO lists VALUES (?, ?)",
                    [(r["LocationID"], "borderline" if r["borderline"] else "core") for r in rows])
    con.execute(f"""COPY (
        WITH shp AS (
            SELECT LocationID, zone, ST_Transform(geom, {sql_literal(crs)}, 'EPSG:2263', always_xy := true)::GEOMETRY AS g
            FROM ST_Read({sql_literal(source)}) WHERE borough = 'Manhattan'),
        half AS (SELECT ST_GeomFromText({sql_literal(_south_of_60th_wkt(con))}) AS h),
        pu AS (SELECT pu_zone AS z, sum(trips_all) AS n, sum(trips_cbd_fee) AS f FROM pairs GROUP BY 1),
        dz AS (SELECT do_zone AS z, sum(trips_all) AS n, sum(trips_cbd_fee) AS f FROM pairs GROUP BY 1),
        intra AS (SELECT pu_zone AS z, sum(trips_all) AS n, sum(trips_cbd_fee) AS f FROM pairs
                  WHERE pu_zone = do_zone GROUP BY 1)
        SELECT shp.LocationID, shp.zone, coalesce(lists.list, 'out') AS list,
               round(ST_Area(ST_Intersection(shp.g, half.h)) / ST_Area(shp.g), 3) AS area_south_60th,
               coalesce(pu.n, 0) AS pu_trips, round(pu.f / pu.n, 4) AS pu_fee_share,
               coalesce(dz.n, 0) AS do_trips, round(dz.f / dz.n, 4) AS do_fee_share,
               coalesce(intra.n, 0) AS intra_trips, round(intra.f / intra.n, 4) AS intra_fee_share
        FROM shp CROSS JOIN half LEFT JOIN lists USING (LocationID)
        LEFT JOIN pu ON pu.z = shp.LocationID LEFT JOIN dz ON dz.z = shp.LocationID
        LEFT JOIN intra ON intra.z = shp.LocationID
        ORDER BY pu_fee_share DESC NULLS LAST, LocationID
    ) TO {sql_literal(str(zones_csv))} (HEADER)""")
    lines = [f"Fee share by zone list, HVFHV {month} (`cbd_congestion_fee > 0`)", "",
             "| List | Zones | Both in: trips | Both in: fee share | One in: fee share | Neither in: trips | Neither in: fee share |",
             "|---|---|---|---|---|---|---|"]
    for name, ids in lists.items():
        inlist = ",".join(map(str, sorted(ids)))
        both, one, neither = (con.execute(f"""
            SELECT sum(trips_all), sum(trips_cbd_fee) / sum(trips_all) FROM pairs
            WHERE {cond}""").fetchone() for cond in (
            f"pu_zone IN ({inlist}) AND do_zone IN ({inlist})",
            f"(pu_zone IN ({inlist})) <> (do_zone IN ({inlist}))",
            f"pu_zone NOT IN ({inlist}) AND do_zone NOT IN ({inlist})"))
        lines.append(f"| {name} | {len(ids)} | {both[0]:,} | {both[1]:.2%} | {one[1]:.2%} | {neither[0]:,} | {neither[1]:.2%} |")
    lines += ["", "| ID | Zone | List | Area south of 60th St | Pickups | Pickup fee share | Drop-offs | Drop-off fee share | Same-zone trips | Same-zone fee share |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for r in con.execute(f"SELECT * FROM read_csv({sql_literal(str(zones_csv))}, header = true)").fetchall():
        cells = [str(r[0]), r[1], r[2], f"{r[3]:.1%}"]
        for n, share in ((r[4], r[5]), (r[6], r[7]), (r[8], r[9])):
            cells += [f"{n:,}", "—" if share is None else f"{share:.1%}"]
        lines.append("| " + " | ".join(cells) + " |")
    return zones_csv, "\n".join(lines)


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.zones", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="run the checks without rebuilding the GeoJSON")
    mode.add_argument("--explore", type=common.month_arg, metavar="YYYY-MM",
                      help="exploratory fee check on that month's raw HVFHV file")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    if args.explore:
        path, summary = explore(args.explore)
        print(summary)
        print(f"\nwrote {path}")
        return
    lookup = read_lookup()
    con = spatial_connection()
    source = shapefile_source()
    print(f"shapefile CRS: {source_crs(con, source)} → EPSG:4326")
    problems = source_problems(con, source, lookup) + config_problems(lookup)
    if not args.check:
        print(f"wrote {build_geojson()}")
    problems += geojson_problems()
    if problems:
        print("\n".join(problems), file=sys.stderr)
        raise SystemExit(1)
    size = geojson_path().stat().st_size
    print(f"ok: {len(ZONE_IDS)} zones, GeoJSON {size:,} bytes; core {len(cbd_zone_ids('core'))} zones, "
          f"wide {len(cbd_zone_ids('wide'))}; airports {airport_zones()}")


if __name__ == "__main__":
    main()
