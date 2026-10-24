"""Download one month of trip files, or the lookup files, each with a manifest entry.

Lane L02 · SPEC §3.1, §3.2 · docs/lanes/L02-ingest.md

Each file streams to a hidden ``.part`` file beside its target and is renamed only once it
is complete and readable, so an interrupted download leaves nothing behind. Every file gets
an entry in ``data/manifest.json``, keyed by its path under the data folder
(``raw/yellow/2024-01.parquet``, ``ref/taxi_zones.zip``). A re-run re-hashes existing files
and skips the ones whose sha256 matches their entry; ``--force`` downloads again.
"""

from __future__ import annotations

import argparse
import contextlib
import csv
import fcntl
import hashlib
import json
import os
import sys
import tempfile
import time
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Callable, Iterator

import pyarrow.parquet as pq
import requests

from pipeline.common import data_dir, load_yaml, manifest_path, month_arg, raw_path, ref_dir

CHUNK_BYTES = 1 << 20
RETRY_STATUS = {408, 429, 500, 502, 503, 504}
MISSING_STATUS = {403, 404}   # CloudFront answers 403 for a file that isn't posted

EXIT_NOT_POSTED = 1           # --check: at least one dataset isn't posted
EXIT_CHECK_FAILED = 4         # --check: couldn't tell (network or server error)


class IngestError(Exception):
    """A download or check failed. The message names the file."""


class NotPostedError(IngestError):
    """The server answered 403 or 404: the file isn't posted (or access is refused)."""


class _Transient(Exception):
    """A failure worth retrying: 5xx, 429, a dropped connection or a short read."""


# --- config ------------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """The ``download:`` block of ``config/sources.yaml``."""

    attempts: int = 5
    backoff_s: float = 2.0
    timeout_s: float = 60.0
    user_agent: str | None = None

    def __post_init__(self) -> None:
        if self.attempts < 1:
            raise ValueError("download.attempts must be at least 1")

    @classmethod
    def from_sources(cls, sources: dict[str, Any]) -> Settings:
        return cls(**sources.get("download", {}))


def load_sources() -> dict[str, Any]:
    return load_yaml("sources.yaml")


def trip_url(sources: dict[str, Any], dataset: str, month: str) -> str:
    return sources["trip_url"].format(dataset=dataset, month=month)


def make_session(settings: Settings) -> requests.Session:
    session = requests.Session()
    if settings.user_agent:
        session.headers["User-Agent"] = settings.user_agent
    return session


# --- manifest ----------------------------------------------------------------

def load_manifest() -> dict[str, dict[str, Any]]:
    """Manifest entries keyed by path under the data folder, e.g. ``raw/yellow/2024-01.parquet``."""
    path = manifest_path()
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)["files"]


def manifest_key(path: Path) -> str:
    return path.relative_to(data_dir()).as_posix()


@contextlib.contextmanager
def _locked_manifest() -> Iterator[dict[str, dict[str, Any]]]:
    """Read, let the caller change, and atomically rewrite the manifest under a file lock.

    The lock matters because every worktree shares one data folder.
    """
    path = manifest_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path.with_name(path.name + ".lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            files = load_manifest()
            yield files
            _write_json_atomic(path, {"files": dict(sorted(files.items()))})
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)


def _write_json_atomic(path: Path, doc: dict[str, Any]) -> None:
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        _publish(Path(tmp), path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def _publish(tmp: Path, dest: Path) -> None:
    """Give a ``mkstemp`` file (created 0600) the usual umask mode, then move it into place."""
    umask = os.umask(0)
    os.umask(umask)
    os.chmod(tmp, 0o666 & ~umask)
    os.replace(tmp, dest)


def _matches(path: Path, entry: dict[str, Any] | None) -> bool:
    if entry is None or not path.exists() or path.stat().st_size != entry["bytes"]:
        return False
    return sha256_file(path) == entry["sha256"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


# --- download ----------------------------------------------------------------

def _with_retries(label: str, settings: Settings, attempt: Callable[[], Any]) -> Any:
    for n in range(1, settings.attempts + 1):
        try:
            return attempt()
        except (_Transient, requests.ConnectionError, requests.Timeout,
                requests.exceptions.ChunkedEncodingError) as exc:
            if n == settings.attempts:
                raise IngestError(f"{label}: gave up after {n} attempts: {exc}") from exc
            wait = settings.backoff_s * 2 ** (n - 1)
            print(f"{label}: {exc}; retrying in {wait:g} s ({n}/{settings.attempts})", file=sys.stderr)
            time.sleep(wait)
    raise AssertionError("unreachable: attempts >= 1")


def _check_status(resp: requests.Response, label: str, url: str) -> None:
    if resp.status_code in MISSING_STATUS:
        raise NotPostedError(f"{label}: not available, HTTP {resp.status_code} from {url}")
    if resp.status_code in RETRY_STATUS:
        raise _Transient(f"HTTP {resp.status_code}")
    if resp.status_code != 200:
        raise IngestError(f"{label}: HTTP {resp.status_code} from {url}")


def _stream(url: str, out: BinaryIO, *, label: str, session: requests.Session,
            settings: Settings) -> dict[str, Any]:
    digest = hashlib.sha256()
    size = 0
    with session.get(url, stream=True, timeout=settings.timeout_s) as resp:
        _check_status(resp, label, url)
        for chunk in resp.iter_content(CHUNK_BYTES):
            out.write(chunk)
            digest.update(chunk)
            size += len(chunk)
        headers = resp.headers
    # Content-Length counts encoded bytes, so only compare when the body wasn't compressed.
    expected = headers.get("Content-Length")
    if expected is not None and headers.get("Content-Encoding", "identity") == "identity" \
            and size != int(expected):
        raise _Transient(f"got {size} of {expected} bytes")
    return {"bytes": size, "sha256": digest.hexdigest(),
            "etag": headers.get("ETag"), "last_modified": headers.get("Last-Modified")}


def _validate(path: Path, kind: str, label: str) -> int | None:
    """Row count for Parquet (footer only) and CSV; None for a zip. Raises if unreadable."""
    try:
        if kind == "parquet":
            return pq.read_metadata(path).num_rows
        if kind == "zip":
            with zipfile.ZipFile(path) as zf:
                bad = zf.testzip()
            if bad is not None:
                raise ValueError(f"corrupt member {bad}")
            return None
        if kind == "csv":
            with open(path, encoding="utf-8-sig", newline="") as f:
                if f.read(1) in ("", "<"):
                    raise ValueError("empty or HTML")
                f.seek(0)
                rows = sum(1 for _ in csv.reader(f)) - 1
            if rows < 1:
                raise ValueError("no data rows")
            return rows
    except (OSError, ValueError, UnicodeDecodeError, zipfile.BadZipFile) as exc:
        raise IngestError(f"{label}: downloaded file is not valid {kind}: {exc}") from exc
    raise IngestError(f"{label}: don't know how to check a .{kind} file")


def fetch(url: str, dest: Path, *, label: str, session: requests.Session,
          settings: Settings) -> dict[str, Any]:
    """Download ``url`` to ``dest`` through a ``.part`` file; return the manifest fields."""
    dest.parent.mkdir(parents=True, exist_ok=True)

    def attempt() -> dict[str, Any]:
        fd, tmp = tempfile.mkstemp(dir=dest.parent, prefix=f".{dest.name}.", suffix=".part")
        try:
            with os.fdopen(fd, "wb") as out:
                info = _stream(url, out, label=label, session=session, settings=settings)
                out.flush()
                os.fsync(out.fileno())
            info["rows"] = _validate(Path(tmp), dest.suffix.lstrip("."), label)
            _publish(Path(tmp), dest)
            return info
        finally:
            Path(tmp).unlink(missing_ok=True)

    return _with_retries(label, settings, attempt)


def ensure_file(url: str, dest: Path, *, label: str, dataset: str | None = None,
                month: str | None = None, force: bool = False,
                session: requests.Session, settings: Settings) -> dict[str, Any]:
    """Skip ``dest`` if it matches its manifest entry; otherwise download it and record it."""
    key = manifest_key(dest)
    entry = load_manifest().get(key)
    if not force and _matches(dest, entry):
        if "deleted_at" in entry:
            with _locked_manifest() as files:
                files[key] = entry = {k: v for k, v in entry.items() if k != "deleted_at"}
        print(f"{label}: verified, sha256 matches the manifest ({_size(entry['bytes'])})")
        return entry
    if not force and entry is not None and dest.exists():
        print(f"{label}: doesn't match the manifest; downloading again", file=sys.stderr)

    print(f"{label}: downloading {url}")
    started = time.monotonic()
    info = fetch(url, dest, label=label, session=session, settings=settings)
    entry = {
        "file": key, "dataset": dataset, "month": month, "url": url,
        "bytes": info["bytes"], "sha256": info["sha256"], "rows": info["rows"],
        "downloaded_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "etag": info["etag"], "last_modified": info["last_modified"],
    }
    with _locked_manifest() as files:
        files[key] = entry
    rows = "" if info["rows"] is None else f", {info['rows']:,} rows"
    print(f"{label}: {_size(info['bytes'])} in {time.monotonic() - started:.0f} s{rows}")
    return entry


def _size(n: int) -> str:
    return f"{n / 1e6:,.1f} MB" if n >= 100_000 else f"{n / 1e3:,.1f} kB"


# --- steps -------------------------------------------------------------------

def _run_all(jobs: list[Callable[[], Any]], *, not_posted_hint: str | None = None) -> None:
    """Run every job even if some fail, then raise one error listing the failures."""
    failures: list[IngestError] = []
    for job in jobs:
        try:
            job()
        except IngestError as exc:
            failures.append(exc)
    if failures:
        lines = [str(exc) for exc in failures]
        if not_posted_hint and any(isinstance(exc, NotPostedError) for exc in failures):
            lines.append(not_posted_hint)
        raise IngestError("\n".join(lines))


def ingest_month(month: str, *, force: bool = False, sources: dict[str, Any] | None = None,
                 session: requests.Session | None = None) -> None:
    """Download fhvhv, yellow and green for one month to ``data/raw/{dataset}/{month}.parquet``."""
    sources = sources or load_sources()
    settings = Settings.from_sources(sources)
    session = session or make_session(settings)
    _run_all([
        lambda dataset=dataset: ensure_file(
            trip_url(sources, dataset, month), raw_path(dataset, month),
            label=f"{dataset} {month}", dataset=dataset, month=month, force=force,
            session=session, settings=settings)
        for dataset in sources["datasets"]
    ], not_posted_hint="TLC posts each month about two months after it ends; "
                       "`python -m pipeline.ingest --check YYYY-MM` shows what is posted.")


def ingest_ref(*, force: bool = False, sources: dict[str, Any] | None = None,
               session: requests.Session | None = None) -> None:
    """Download the zone lookup, zone shapefile and indicators CSV to ``data/ref/``."""
    sources = sources or load_sources()
    settings = Settings.from_sources(sources)
    session = session or make_session(settings)
    _run_all([
        lambda name=name, url=url: ensure_file(
            url, ref_dir() / name, label=f"ref {name}", force=force,
            session=session, settings=settings)
        for name, url in sources["ref"].items()
    ])


def check_month(month: str, *, sources: dict[str, Any] | None = None,
                session: requests.Session | None = None) -> bool:
    """HEAD each dataset's file for ``month``. True if all are posted."""
    sources = sources or load_sources()
    settings = Settings.from_sources(sources)
    session = session or make_session(settings)

    def head(url: str, label: str) -> requests.Response:
        resp = session.head(url, timeout=settings.timeout_s, allow_redirects=True)
        if resp.status_code not in MISSING_STATUS:
            _check_status(resp, label, url)
        return resp

    posted = True
    for dataset in sources["datasets"]:
        label = f"{dataset} {month}"
        resp = _with_retries(label, settings, lambda: head(trip_url(sources, dataset, month), label))
        if resp.status_code in MISSING_STATUS:
            posted = False
            print(f"{label}: not posted (HTTP {resp.status_code})")
        else:
            size = resp.headers.get("Content-Length")
            size = _size(int(size)) if size else "size unknown"
            print(f"{label}: posted, {size}, last modified {resp.headers.get('Last-Modified')}")
    return posted


def delete_raw(month: str, *, sources: dict[str, Any] | None = None) -> None:
    """Delete one month's raw trip files. Manifest entries stay, marked with ``deleted_at``."""
    sources = sources or load_sources()
    removed = []
    for dataset in sources["datasets"]:
        path = raw_path(dataset, month)
        for stray in path.parent.glob(f".{path.name}.*.part"):
            stray.unlink(missing_ok=True)
        if path.exists():
            path.unlink()
            removed.append(manifest_key(path))
            print(f"{dataset} {month}: deleted {path}")
        else:
            print(f"{dataset} {month}: no raw file")
    if removed:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        with _locked_manifest() as files:
            for key in removed:
                if key in files:
                    files[key]["deleted_at"] = stamp


# --- CLI ---------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.ingest", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--month", type=month_arg, metavar="YYYY-MM",
                        help="download fhvhv, yellow and green for this month")
    action.add_argument("--ref", action="store_true",
                        help="download the zone lookup, zone shapefile and indicators CSV")
    action.add_argument("--check", type=month_arg, metavar="YYYY-MM",
                        help="HEAD all three datasets; exit 0 if all are posted, 1 if not, "
                             f"{EXIT_CHECK_FAILED} if the check itself failed")
    action.add_argument("--delete-raw", type=month_arg, metavar="YYYY-MM",
                        help="delete this month's raw trip files")
    parser.add_argument("--force", action="store_true",
                        help="download again even when the manifest matches")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    sys.stdout.reconfigure(line_buffering=True)   # keep progress in order with stderr under make
    if args.force and not (args.month or args.ref):
        parser.error("--force applies only to --month and --ref")
    try:
        if args.month:
            ingest_month(args.month, force=args.force)
        elif args.ref:
            ingest_ref(force=args.force)
        elif args.check:
            raise SystemExit(0 if check_month(args.check) else EXIT_NOT_POSTED)
        else:
            delete_raw(args.delete_raw)
    except IngestError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(EXIT_CHECK_FAILED if args.check else 1) from None


if __name__ == "__main__":
    main()
