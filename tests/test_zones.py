"""Zones (L04): congestion-zone lists, airports, lookup and GeoJSON checks."""

import json
import shutil
import zipfile

import duckdb
import pytest

from pipeline import common, zones

CORE = {4, 12, 13, 45, 48, 50, 68, 79, 87, 88, 90, 100, 107, 113, 114, 125, 137, 144, 148, 158,
        161, 162, 163, 164, 170, 186, 209, 211, 224, 229, 230, 231, 232, 233, 234, 246, 249, 261}
BORDERLINE = {43, 103, 104, 105, 140, 141, 142, 143, 237}


# --- zone lists ----------------------------------------------------------------

def test_core_list():
    assert zones.cbd_zone_ids("core") == CORE
    assert zones.cbd_zone_ids() == CORE


def test_wide_list_adds_borderline_zones():
    assert zones.cbd_zone_ids("wide") == CORE | BORDERLINE


def test_unknown_zone_list():
    with pytest.raises(ValueError, match="zone_list"):
        zones.cbd_zone_ids("all")


def test_borderline_rows_have_notes():
    rows = zones.load_cbd_zones()
    assert [r["LocationID"] for r in rows] == sorted(CORE | BORDERLINE)
    assert all(r["note"] for r in rows if r["borderline"])


@pytest.mark.parametrize("body, match", [
    ("LocationID,zone,borderline\n4,Alphabet City,false\n", "header"),
    ("LocationID,zone,borderline,note\n4,Alphabet City,yes,\n", "true or false"),
    ("LocationID,zone,borderline,note\n264,Unknown,false,\n", "not a mapped zone"),
    ("LocationID,zone,borderline,note\n4,Alphabet City,false,\n4,Alphabet City,true,x\n", "duplicate"),
])
def test_bad_cbd_file_is_rejected(tmp_path, body, match):
    path = tmp_path / "cbd_zones.csv"
    path.write_text(body)
    with pytest.raises(ValueError, match=match):
        zones.load_cbd_zones(path)


# --- airports and lookup -------------------------------------------------------

LOOKUP_ROWS = [
    (1, "EWR", "Newark Airport", "EWR"),
    (2, "Queens", "Jamaica Bay", "Boro Zone"),
    (132, "Queens", "JFK Airport", "Airports"),
    (138, "Queens", "LaGuardia Airport", "Airports"),
    (264, "Unknown", "N/A", "N/A"),
] + [(z, "Manhattan", f"Zone {z}", "Yellow Zone") for z in sorted(CORE | BORDERLINE)]


def write_lookup(rows, data_dir):
    path = data_dir / "ref" / "taxi_zone_lookup.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ['"LocationID","Borough","Zone","service_zone"']
    lines += [f'{z},"{b}","{n}","{s}"' for z, b, n, s in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def lookup_with_real_cbd_names(data_dir):
    names = {r["LocationID"]: r["zone"] for r in zones.load_cbd_zones()}
    rows = [(z, b, names.get(z, n), s) for z, b, n, s in LOOKUP_ROWS]
    write_lookup(rows, data_dir)
    return zones.read_lookup()


def test_airports_match_spec():
    assert zones.airport_zones() == {1: "EWR", 132: "JFK", 138: "LGA"}


def test_config_matches_lookup(data_dir):
    assert zones.config_problems(lookup_with_real_cbd_names(data_dir)) == []


def test_renamed_airport_zone_is_flagged(data_dir):
    lookup = lookup_with_real_cbd_names(data_dir)
    lookup[132] = {**lookup[132], "Zone": "Jamaica"}
    assert zones.config_problems(lookup) == [
        "airports.csv: zone 132 is 'Jamaica' in the lookup, expected 'JFK Airport'"]


def test_unlisted_airport_zone_is_flagged(data_dir):
    lookup = lookup_with_real_cbd_names(data_dir)
    lookup[2] = {**lookup[2], "service_zone": "Airports"}
    assert zones.config_problems(lookup) == [
        "airports.csv: lookup zone 2 (Jamaica Bay) is an airport but not listed"]


def test_cbd_zone_outside_manhattan_is_flagged(data_dir):
    lookup = lookup_with_real_cbd_names(data_dir)
    lookup[4] = {**lookup[4], "Borough": "Brooklyn"}
    assert zones.config_problems(lookup) == ["cbd_zones.csv: zone 4 is in Brooklyn, not Manhattan"]


# --- GeoJSON checks ------------------------------------------------------------

def square(x, y, clockwise=True, size=0.01):
    ring = [[x, y], [x, y + size], [x + size, y + size], [x + size, y], [x, y]]
    return ring if clockwise else ring[::-1]


def feature(zone, ring=None, **props):
    properties = {"LocationID": zone, "zone": f"Zone {zone}", "borough": "Queens", **props}
    return {"type": "Feature", "properties": properties,
            "geometry": {"type": "Polygon", "coordinates": [ring or square(-73.9 + zone / 100, 40.7)]}}


def write_geojson(tmp_path, features):
    path = tmp_path / "zones.geojson"
    path.write_text(json.dumps({"type": "FeatureCollection", "features": features}))
    return path


def test_good_geojson_passes(tmp_path):
    path = write_geojson(tmp_path, [feature(1), feature(2), feature(3)])
    assert zones.geojson_problems(path, expected_ids={1, 2, 3}) == []


def test_geojson_hole_must_run_counter_clockwise(tmp_path):
    outer, hole = square(-73.9, 40.7, size=0.1), square(-73.88, 40.72)
    good = feature(1)
    good["geometry"]["coordinates"] = [outer, hole[::-1]]
    bad = feature(2)
    bad["geometry"]["coordinates"] = [outer, hole]
    path = write_geojson(tmp_path, [good, bad])
    assert zones.geojson_problems(path, expected_ids={1, 2}) == ["zone 2: hole is not counter-clockwise"]


@pytest.mark.parametrize("features, problem", [
    ([feature(1, square(-73.9, 40.7, clockwise=False)), feature(2)], "zone 1: exterior ring is not clockwise"),
    ([feature(1), feature(1), feature(2)], "duplicate LocationIDs [1]"),
    ([feature(1)], "missing LocationIDs [2]"),
    ([feature(1), feature(2), feature(3)], "unexpected LocationIDs [3]"),
    ([feature(1, service_zone="Airports"), feature(2)], "zone 1: properties"),
    ([feature(1, square(1_000_000, 200_000, size=5000)), feature(2)], "outside the NYC lon/lat box"),
])
def test_geojson_problems_are_flagged(tmp_path, features, problem):
    path = write_geojson(tmp_path, features)
    problems = zones.geojson_problems(path, expected_ids={1, 2})
    assert len(problems) == 1 and problem in problems[0]


def test_geojson_over_budget(tmp_path):
    path = write_geojson(tmp_path, [feature(1), feature(2)])
    problems = zones.geojson_problems(path, expected_ids={1, 2}, max_bytes=path.stat().st_size)
    assert problems == [f"zones.geojson: {path.stat().st_size:,} bytes; must be under {path.stat().st_size:,}"]


def test_missing_geojson_is_a_problem(data_dir):
    assert "does not exist" in zones.geojson_problems()[0]


# --- build (needs DuckDB spatial already installed and mapshaper from make setup) --

def spatial_installed() -> bool:
    row = duckdb.connect().execute(
        "SELECT installed FROM duckdb_extensions() WHERE extension_name = 'spatial'").fetchone()
    return bool(row and row[0])


needs_build_tools = pytest.mark.skipif(
    not spatial_installed() or not (zones.SITE_DIR / "node_modules" / ".bin" / "mapshaper").exists(),
    reason="DuckDB spatial not installed locally (tests stay offline) or mapshaper missing (make setup)")


@needs_build_tools
def test_build_reprojects_and_simplifies(data_dir, tmp_path):
    con = zones.spatial_connection()
    shp_dir = tmp_path / "taxi_zones"
    shp_dir.mkdir()
    # Two squares near Columbus Circle in EPSG:2263 feet; zone 2 sits east of zone 1.
    con.execute(f"""COPY (
        SELECT * FROM (VALUES
            (1, 'Zone 1', 'Manhattan', ST_GeomFromText('POLYGON((988000 220000, 988000 221000, 989000 221000, 989000 220000, 988000 220000))')),
            (2, 'Zone 2', 'Manhattan', ST_GeomFromText('POLYGON((989000 220000, 989000 221000, 990000 221000, 990000 220000, 989000 220000))'))
        ) t(LocationID, zone, borough, geom)
    ) TO {common.sql_literal(str(shp_dir / 'taxi_zones.shp'))} (FORMAT GDAL, DRIVER 'ESRI Shapefile', SRS 'EPSG:2263')""")
    archive = data_dir / "ref" / "taxi_zones.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w") as z:
        for part in shp_dir.iterdir():
            z.write(part, f"taxi_zones/{part.name}")
    shutil.rmtree(shp_dir)

    assert zones.source_crs(con, zones.shapefile_source()) == "EPSG:2263"
    out = zones.build_geojson()
    assert out == data_dir / "ref" / "taxi_zones.simplified.geojson"
    assert zones.geojson_problems(out, expected_ids={1, 2}) == []
    data = json.loads(out.read_text())
    assert [f["properties"] for f in data["features"]] == [
        {"LocationID": 1, "zone": "Zone 1", "borough": "Manhattan"},
        {"LocationID": 2, "zone": "Zone 2", "borough": "Manhattan"}]
    x, y = data["features"][0]["geometry"]["coordinates"][0][0]
    assert -74.0 < x < -73.9 and 40.7 < y < 40.8
