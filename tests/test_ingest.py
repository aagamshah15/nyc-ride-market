"""Ingest against a local HTTP server that plays the TLC CloudFront bucket."""

from __future__ import annotations

import hashlib
import io
import json
import os
import threading
import zipfile
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from pipeline import common, ingest

ROWS = {"fhvhv": 5, "yellow": 3, "green": 2}


@dataclass
class Route:
    body: bytes
    status: int = 200
    fail_times: int = 0          # answer 503 to this many GETs first
    truncate: bool = False       # promise more bytes than are sent, then hang up


@dataclass
class FakeTLC:
    base: str = ""
    routes: dict[str, Route] = field(default_factory=dict)
    requests: list[tuple[str, str]] = field(default_factory=list)

    def gets(self, path: str | None = None) -> int:
        return sum(1 for method, p in self.requests if method == "GET" and path in (None, p))

    def post_month(self, month: str, skip: tuple[str, ...] = ()) -> dict[str, bytes]:
        bodies = {}
        for dataset, n in ROWS.items():
            if dataset not in skip:
                bodies[dataset] = parquet_bytes(n, seed=hash((dataset, month)))
                self.routes[trip_path(dataset, month)] = Route(bodies[dataset])
        return bodies


def trip_path(dataset: str, month: str) -> str:
    return f"/trip-data/{dataset}_tripdata_{month}.parquet"


def parquet_bytes(n: int, seed: int = 0) -> bytes:
    buf = io.BytesIO()
    pq.write_table(pa.table({"x": [seed + i for i in range(n)]}), buf)
    return buf.getvalue()


def zip_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("taxi_zones/taxi_zones.shp", b"\x00" * 64)
    return buf.getvalue()


def _handler(tlc: FakeTLC):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def do_HEAD(self):
            self._respond(head=True)

        def do_GET(self):
            self._respond(head=False)

        def _respond(self, head: bool) -> None:
            tlc.requests.append((self.command, self.path))
            route = tlc.routes.get(self.path)
            if route is None or route.status != 200:
                self.send_response(403 if route is None else route.status)  # like CloudFront
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if route.fail_times and not head:
                route.fail_times -= 1
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(route.body) + (1000 if route.truncate else 0)))
            self.send_header("ETag", f'"{hashlib.md5(route.body).hexdigest()}"')
            self.send_header("Last-Modified", "Thu, 01 Oct 2026 13:38:15 GMT")
            self.end_headers()
            if not head:
                self.wfile.write(route.body)

    return Handler


@pytest.fixture
def tlc(monkeypatch):
    for var in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(var, raising=False)
    fake = FakeTLC()
    server = ThreadingHTTPServer(("127.0.0.1", 0), _handler(fake))
    fake.base = f"http://127.0.0.1:{server.server_address[1]}"
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.05}, daemon=True)
    thread.start()
    sources = {
        "trip_url": fake.base + "/trip-data/{dataset}_tripdata_{month}.parquet",
        "datasets": list(ROWS),
        "ref": {
            "taxi_zone_lookup.csv": fake.base + "/misc/taxi_zone_lookup.csv",
            "taxi_zones.zip": fake.base + "/misc/taxi_zones.zip",
            "data_reports_monthly.csv": fake.base + "/csv/data_reports_monthly.csv",
        },
        "download": {"attempts": 3, "backoff_s": 0, "timeout_s": 5},
    }
    monkeypatch.setattr(ingest, "load_sources", lambda: sources)
    yield fake
    server.shutdown()
    server.server_close()


def run(*argv: str) -> int:
    try:
        ingest.main(list(argv))
    except SystemExit as exc:
        return exc.code
    return 0


def manifest() -> dict:
    return json.loads(common.manifest_path().read_text())["files"]


def leftovers(data_dir) -> list[str]:
    return sorted(p.name for p in data_dir.rglob(".*") if p.name.endswith((".part", ".tmp")))


# --- month -------------------------------------------------------------------

def test_month_writes_files_and_manifest(tlc, data_dir):
    bodies = tlc.post_month("2024-01")
    assert run("--month", "2024-01") == 0

    entries = manifest()
    for dataset, body in bodies.items():
        path = common.raw_path(dataset, "2024-01")
        assert path.read_bytes() == body
        key = f"raw/{dataset}/2024-01.parquet"
        entry = entries[key]
        assert entry["file"] == key
        assert entry["dataset"] == dataset and entry["month"] == "2024-01"
        assert entry["url"] == tlc.base + trip_path(dataset, "2024-01")
        assert entry["bytes"] == len(body)
        assert entry["sha256"] == hashlib.sha256(body).hexdigest()
        assert entry["rows"] == ROWS[dataset]
        assert entry["etag"] == f'"{hashlib.md5(body).hexdigest()}"'
        assert entry["last_modified"] == "Thu, 01 Oct 2026 13:38:15 GMT"
        datetime.strptime(entry["downloaded_at"], "%Y-%m-%dT%H:%M:%SZ")
    assert leftovers(data_dir) == []


def test_files_get_the_umask_mode_not_mkstemps_0600(tlc):
    tlc.post_month("2024-01")
    old = os.umask(0o022)
    try:
        assert run("--month", "2024-01") == 0
    finally:
        os.umask(old)
    assert common.raw_path("green", "2024-01").stat().st_mode & 0o777 == 0o644
    assert common.manifest_path().stat().st_mode & 0o777 == 0o644


def test_rerun_verifies_and_downloads_nothing(tlc, capsys):
    tlc.post_month("2024-01")
    assert run("--month", "2024-01") == 0
    before = manifest()
    mtimes = {d: common.raw_path(d, "2024-01").stat().st_mtime_ns for d in ROWS}
    capsys.readouterr()

    assert run("--month", "2024-01") == 0

    assert tlc.gets() == 3
    assert manifest() == before
    assert {d: common.raw_path(d, "2024-01").stat().st_mtime_ns for d in ROWS} == mtimes
    assert capsys.readouterr().out.count("sha256 matches the manifest") == 3


def test_force_downloads_again(tlc):
    tlc.post_month("2024-01")
    assert run("--month", "2024-01") == 0
    assert run("--month", "2024-01", "--force") == 0
    assert tlc.gets() == 6


def test_file_that_no_longer_matches_is_downloaded_again(tlc):
    bodies = tlc.post_month("2024-01")
    assert run("--month", "2024-01") == 0
    path = common.raw_path("yellow", "2024-01")
    path.write_bytes(b"\x00" * len(bodies["yellow"]))     # same size, different bytes

    assert run("--month", "2024-01") == 0

    assert tlc.gets(trip_path("yellow", "2024-01")) == 2
    assert tlc.gets(trip_path("green", "2024-01")) == 1
    assert path.read_bytes() == bodies["yellow"]


def test_transient_errors_are_retried(tlc):
    bodies = tlc.post_month("2024-01")
    tlc.routes[trip_path("green", "2024-01")].fail_times = 2

    assert run("--month", "2024-01") == 0

    assert tlc.gets(trip_path("green", "2024-01")) == 3
    assert common.raw_path("green", "2024-01").read_bytes() == bodies["green"]


def test_interrupted_download_leaves_no_file(tlc, data_dir, capsys):
    tlc.post_month("2024-01")
    tlc.routes[trip_path("yellow", "2024-01")].truncate = True

    assert run("--month", "2024-01") == 1

    assert tlc.gets(trip_path("yellow", "2024-01")) == 3      # every attempt was cut short
    assert not common.raw_path("yellow", "2024-01").exists()
    assert "raw/yellow/2024-01.parquet" not in manifest()
    assert leftovers(data_dir) == []
    assert "yellow 2024-01: gave up after 3 attempts" in capsys.readouterr().err
    assert common.raw_path("fhvhv", "2024-01").exists()       # the others still land


def test_keyboard_interrupt_leaves_no_file(tlc, data_dir, monkeypatch):
    tlc.post_month("2024-01")

    def interrupt(path, kind, label):
        raise KeyboardInterrupt

    monkeypatch.setattr(ingest, "_validate", interrupt)
    with pytest.raises(KeyboardInterrupt):
        run("--month", "2024-01")

    assert not common.raw_path("fhvhv", "2024-01").exists()
    assert not common.manifest_path().exists()
    assert leftovers(data_dir) == []


def test_missing_month_names_dataset_and_month(tlc, capsys):
    tlc.post_month("2026-09", skip=("green",))

    assert run("--month", "2026-09") == 1

    err = capsys.readouterr().err
    assert "green 2026-09: not available, HTTP 403" in err
    assert "about two months" in err
    assert tlc.gets(trip_path("green", "2026-09")) == 1         # a 403 isn't retried
    assert common.raw_path("yellow", "2026-09").exists()


def test_file_that_is_not_parquet_is_rejected(tlc, data_dir, capsys):
    tlc.post_month("2024-01")
    tlc.routes[trip_path("fhvhv", "2024-01")] = Route(b"<html>Access Denied</html>")

    assert run("--month", "2024-01") == 1

    assert "fhvhv 2024-01: downloaded file is not valid parquet" in capsys.readouterr().err
    assert not common.raw_path("fhvhv", "2024-01").exists()
    assert leftovers(data_dir) == []


# --- check -------------------------------------------------------------------

def test_check_exit_codes(tlc, capsys):
    tlc.post_month("2026-08")
    tlc.post_month("2026-09", skip=("fhvhv",))

    assert run("--check", "2026-08") == 0
    assert run("--check", "2026-09") == ingest.EXIT_NOT_POSTED
    assert "fhvhv 2026-09: not posted (HTTP 403)" in capsys.readouterr().out
    assert tlc.gets() == 0                                    # HEAD only


def test_check_failure_is_not_read_as_not_posted(tlc):
    tlc.post_month("2026-08")
    tlc.routes[trip_path("yellow", "2026-08")].status = 500

    assert run("--check", "2026-08") == ingest.EXIT_CHECK_FAILED
    assert [r for r in tlc.requests if r[1] == trip_path("yellow", "2026-08")] == [("HEAD", trip_path("yellow", "2026-08"))] * 3


# --- delete-raw ----------------------------------------------------------------

def test_delete_raw_removes_files_and_marks_manifest(tlc):
    tlc.post_month("2024-01")
    tlc.post_month("2024-02")
    assert run("--month", "2024-01") == 0
    assert run("--month", "2024-02") == 0

    assert run("--delete-raw", "2024-01") == 0

    entries = manifest()
    for dataset in ROWS:
        assert not common.raw_path(dataset, "2024-01").exists()
        assert common.raw_path(dataset, "2024-02").exists()
        assert "deleted_at" in entries[f"raw/{dataset}/2024-01.parquet"]
        assert "deleted_at" not in entries[f"raw/{dataset}/2024-02.parquet"]

    assert run("--month", "2024-01") == 0
    assert tlc.gets() == 9
    assert "deleted_at" not in manifest()["raw/yellow/2024-01.parquet"]


# --- ref -----------------------------------------------------------------------

def post_ref(tlc) -> None:
    tlc.routes["/misc/taxi_zone_lookup.csv"] = Route(
        b'"LocationID","Borough","Zone","service_zone"\n'
        b'1,"EWR","Newark Airport","EWR"\n2,"Queens","Jamaica Bay","Boro Zone"\n'
        b'264,"Unknown","N/A","N/A"\n')
    tlc.routes["/misc/taxi_zones.zip"] = Route(zip_bytes())
    tlc.routes["/csv/data_reports_monthly.csv"] = Route(
        b"Month/Year,License Class,Trips Per Day\n2026-07,Yellow,\"110,000\"\n")


def test_ref_downloads_lookups_with_manifest_entries(tlc, data_dir):
    post_ref(tlc)
    assert run("--ref") == 0

    entries = manifest()
    assert (common.ref_dir() / "taxi_zones.zip").read_bytes() == zip_bytes()
    assert entries["ref/taxi_zone_lookup.csv"]["rows"] == 3
    assert entries["ref/data_reports_monthly.csv"]["rows"] == 1
    assert entries["ref/taxi_zones.zip"]["rows"] is None
    assert all(entries[k]["month"] is None and entries[k]["dataset"] is None for k in entries)

    assert run("--ref") == 0
    assert tlc.gets() == 3


def test_ref_reports_every_failure(tlc, capsys):
    post_ref(tlc)
    del tlc.routes["/csv/data_reports_monthly.csv"]
    tlc.routes["/misc/taxi_zones.zip"] = Route(b"not a zip")

    assert run("--ref") == 1

    err = capsys.readouterr().err
    assert "ref data_reports_monthly.csv: not available, HTTP 403" in err
    assert "ref taxi_zones.zip: downloaded file is not valid zip" in err
    assert "two months" not in err                            # that hint is for trip files
    assert (common.ref_dir() / "taxi_zone_lookup.csv").exists()


# --- CLI and config ------------------------------------------------------------

def test_force_only_with_month_or_ref():
    assert run("--check", "2026-08", "--force") == 2


def test_sources_config():
    sources = common.load_yaml("sources.yaml")
    assert ingest.trip_url(sources, "fhvhv", "2026-08") == (
        "https://d37ci6vzurychx.cloudfront.net/trip-data/fhvhv_tripdata_2026-08.parquet")
    assert set(sources["ref"]) == {"taxi_zone_lookup.csv", "taxi_zones.zip", "data_reports_monthly.csv"}
    settings = ingest.Settings.from_sources(sources)
    assert settings.attempts >= 1 and settings.timeout_s > 0
