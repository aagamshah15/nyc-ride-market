"""Pack and unpack data/agg/ as aggregates.tar.zst, and move it to and from a GitHub Release.

The archive holds every file in ``data/agg/`` (the aggregate tables, ``ref_indicators`` and
``validation_summary.json``), ``data/manifest.json`` (the trip files each month came from) and
``release.json``, which records the latest month and each file's size and sha256. ``pack``
refuses an incomplete set of aggregate tables; ``unpack`` checks every file against
``release.json`` before anything lands in ``data/``, and won't overwrite aggregates already
there without ``--force``.

The refresh workflow uploads each archive to a Release tagged ``data-YYYY-MM``, the latest month
in the aggregates, and ``download`` takes the newest such Release. Compression goes through the
``zstd`` command (Python 3.12 has no zstd module). GitHub calls go through the ``gh`` command,
which reads ``GH_TOKEN`` and ``GH_REPO``.

    python -m pipeline.release pack                  # data/agg/ → data/aggregates.tar.zst
    python -m pipeline.release unpack                # data/aggregates.tar.zst → data/agg/
    python -m pipeline.release upload                # → Release data-YYYY-MM
    python -m pipeline.release download --dir DIR    # newest data-YYYY-MM Release; prints its tag
    python -m pipeline.release latest-month          # latest month in data/agg/
    python -m pipeline.release next-month            # the month after it: the next one to process

Lane L17 · SPEC §10 · docs/lanes/L17-refresh-deploy.md
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline import common
from pipeline.aggregate import TABLES
from pipeline.ingest import sha256_file

ASSET = "aggregates.tar.zst"
INDEX = "release.json"
MANIFEST = "manifest.json"
TAG_PREFIX = "data-"
MONTH_TABLE = "agg_zone_hour"   # the next expected month is read from this table (SPEC §10)
AGG_SUFFIXES = (".parquet", ".json")

_AGG_MEMBER = re.compile(r"^agg/[A-Za-z0-9_][A-Za-z0-9_.-]*\.(parquet|json)$")
_TAG = re.compile(rf"^{TAG_PREFIX}(\d{{4}}-\d{{2}})$")


class ReleaseError(Exception):
    """Packing, unpacking or a Release step failed. The message says what to do."""


class GhError(ReleaseError):
    """The ``gh`` command exited non-zero."""

    def __init__(self, args: tuple[str, ...], returncode: int, stderr: str):
        self.returncode, self.stderr = returncode, stderr
        super().__init__(f"gh {' '.join(args)}: exit {returncode}: {stderr}")


# --- months ------------------------------------------------------------------

def latest_month(data: Path | None = None) -> str:
    """Latest ``YYYY-MM`` in ``data/agg/agg_zone_hour.parquet``."""
    path = (data or common.data_dir()) / "agg" / f"{MONTH_TABLE}.parquet"
    if not path.is_file():
        raise ReleaseError(f"{path} not found: restore the aggregates first (release download, then unpack)")
    with common.connect() as con:
        (month,) = con.execute(f"SELECT max(month) FROM read_parquet({common.sql_literal(str(path))})").fetchone()
    if month is None:
        raise ReleaseError(f"{path} has no rows")
    return common.format_month(month)


def next_month(data: Path | None = None) -> str:
    """The month after :func:`latest_month`: the next one TLC should post."""
    month = common.parse_month(latest_month(data))
    return common.format_month(month.replace(year=month.year + 1, month=1) if month.month == 12
                               else month.replace(month=month.month + 1))


def tag_month(tag: str) -> str | None:
    """``data-2026-08`` → ``2026-08``; None for any other tag."""
    match = _TAG.match(tag)
    if not match:
        return None
    try:
        return common.format_month(common.parse_month(match[1]))
    except ValueError:
        return None


# --- pack and unpack ---------------------------------------------------------

def zstd() -> str:
    exe = shutil.which("zstd")
    if exe is None:
        raise ReleaseError("zstd not found: install it (apt-get install zstd, brew install zstd)")
    return exe


def pack_list(data: Path) -> dict[str, Path]:
    """Archive member name → file: ``agg/*.parquet``, ``agg/*.json`` and ``manifest.json``."""
    agg = data / "agg"
    missing = [t for t in TABLES if not (agg / f"{t}.parquet").is_file()]
    if missing:
        raise ReleaseError(f"{agg} is missing {', '.join(missing)}: run make month before packing")
    files = {f"agg/{p.name}": p for p in sorted(agg.iterdir())
             if p.is_file() and p.suffix in AGG_SUFFIXES and not p.name.startswith(".")}
    if (data / MANIFEST).is_file():
        files[MANIFEST] = data / MANIFEST
    return files


def pack(archive: Path, data: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Write ``data/agg/`` and the manifest to ``archive``; return the ``release.json`` index."""
    data = data or common.data_dir()
    now = now or datetime.now(timezone.utc)
    files = pack_list(data)
    index = {
        "latest_month": latest_month(data),
        "packed_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "files": {name: {"bytes": path.stat().st_size, "sha256": sha256_file(path)}
                  for name, path in files.items()},
    }
    archive.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=archive.parent, prefix=f".{archive.name}.", suffix=".part")
    try:
        with os.fdopen(fd, "wb") as out:
            proc = subprocess.Popen([zstd(), "-q", "-T0", "-c"], stdin=subprocess.PIPE, stdout=out)
            try:
                with tarfile.open(fileobj=proc.stdin, mode="w|", format=tarfile.PAX_FORMAT) as tar:
                    body = (json.dumps(index, indent=2) + "\n").encode()
                    info = _normalise(tarfile.TarInfo(INDEX))
                    info.size, info.mtime = len(body), int(now.timestamp())
                    tar.addfile(info, io.BytesIO(body))   # first, so read_index stops early
                    for name, path in files.items():
                        tar.add(path, arcname=name, recursive=False, filter=_normalise)
            finally:
                proc.stdin.close()
                code = proc.wait()
        if code != 0:
            raise ReleaseError(f"zstd exited {code} while packing {archive}")
        os.replace(tmp, archive)
    finally:
        Path(tmp).unlink(missing_ok=True)
    return index


def _normalise(info: tarfile.TarInfo) -> tarfile.TarInfo:
    info.uid = info.gid = 0
    info.uname = info.gname = ""
    info.mode = 0o644
    return info


def _check_member(member: tarfile.TarInfo) -> None:
    name = member.name
    if not member.isfile() or not (name in (INDEX, MANIFEST) or _AGG_MEMBER.match(name)):
        raise ReleaseError(f"unexpected archive member {name!r}: not an aggregates archive")


def read_index(archive: Path) -> dict[str, Any]:
    """The ``release.json`` index, read from the archive's first member."""
    proc = subprocess.Popen([zstd(), "-q", "-d", "-c", str(archive)], stdout=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            member = tar.next()
            if member is None or member.name != INDEX or not member.isfile():
                raise ReleaseError(f"{archive}: first member is not {INDEX}")
            return json.load(tar.extractfile(member))
    except (tarfile.TarError, ValueError) as exc:
        raise ReleaseError(f"{archive}: not a readable aggregates archive: {exc}") from None
    finally:
        proc.kill()   # the rest of the stream isn't needed
        proc.stdout.close()
        proc.wait()


def unpack(archive: Path, data: Path | None = None, force: bool = False) -> dict[str, Any]:
    """Restore ``archive`` into ``data/``; return its index. Every file is checked first."""
    data = data or common.data_dir()
    agg = data / "agg"
    existing = sorted(p.name for p in agg.glob("*.parquet")) if agg.is_dir() else []
    if (data / MANIFEST).is_file():
        existing.append(MANIFEST)
    if existing and not force:
        raise ReleaseError(f"{data} already has {', '.join(existing[:3])}{' …' if len(existing) > 3 else ''}: "
                           "unpack --force overwrites them with the archive's copies")
    data.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=data, prefix=".unpack-") as tmp:
        staging = Path(tmp)
        names = _extract(archive, staging)
        index = json.loads((staging / INDEX).read_text(encoding="utf-8"))
        expected = set(index.get("files", {}))
        if names != expected:
            extra, absent = sorted(names - expected), sorted(expected - names)
            raise ReleaseError(f"{archive}: members don't match {INDEX} (extra {extra}, missing {absent})")
        for name in sorted(names):
            entry, path = index["files"][name], staging / name
            if path.stat().st_size != entry["bytes"] or sha256_file(path) != entry["sha256"]:
                raise ReleaseError(f"{archive}: {name} doesn't match its sha256 in {INDEX}")
        agg.mkdir(parents=True, exist_ok=True)
        for name in sorted(names):
            os.replace(staging / name, data / name)
    return index


def _extract(archive: Path, dest: Path) -> set[str]:
    """Extract every member to ``dest``; return the member names other than the index."""
    proc = subprocess.Popen([zstd(), "-q", "-d", "-c", str(archive)], stdout=subprocess.PIPE)
    names: set[str] = set()
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
            for member in tar:
                _check_member(member)
                if member.name in names:
                    raise ReleaseError(f"{archive}: {member.name} appears twice")
                tar.extract(member, dest, filter="data")
                if member.name != INDEX:
                    names.add(member.name)
    except tarfile.TarError as exc:
        raise ReleaseError(f"{archive}: not a readable aggregates archive: {exc}") from None
    finally:
        proc.stdout.close()
        code = proc.wait()
    if code != 0:
        raise ReleaseError(f"zstd exited {code} while reading {archive}")
    if not (dest / INDEX).is_file():
        raise ReleaseError(f"{archive}: no {INDEX}")
    return names


# --- GitHub Releases ---------------------------------------------------------

def gh(*args: str) -> str:
    """Run ``gh`` and return its stdout. The only place this module calls GitHub."""
    exe = shutil.which("gh")
    if exe is None:
        raise ReleaseError("gh not found: install the GitHub CLI")
    result = subprocess.run([exe, *args], capture_output=True, text=True)
    if result.returncode != 0:
        raise GhError(args, result.returncode, result.stderr.strip())
    return result.stdout


def latest_tag() -> str | None:
    """The published Release whose ``data-YYYY-MM`` tag has the latest month, if any."""
    releases = json.loads(gh("release", "list", "--limit", "200", "--json", "tagName,isDraft"))
    tags = [r["tagName"] for r in releases if not r["isDraft"] and tag_month(r["tagName"])]
    return max(tags, key=tag_month) if tags else None


def release_exists(tag: str) -> bool:
    try:
        gh("release", "view", tag, "--json", "tagName")
    except GhError as exc:
        if "not found" in exc.stderr.lower():
            return False
        raise
    return True


def download(dest: Path, tag: str | None = None) -> tuple[str, Path]:
    """Download the Release asset to ``dest/aggregates.tar.zst``; return ``(tag, path)``."""
    tag = tag or latest_tag()
    if tag is None:
        raise ReleaseError(f"no Release tagged {TAG_PREFIX}YYYY-MM: upload the first one from a local back-fill "
                           "(python -m pipeline.release pack, then upload)")
    dest.mkdir(parents=True, exist_ok=True)
    gh("release", "download", tag, "--pattern", ASSET, "--dir", str(dest), "--clobber")
    path = dest / ASSET
    if not path.is_file():
        raise ReleaseError(f"Release {tag} has no {ASSET}")
    month = read_index(path).get("latest_month")
    if tag_month(tag) and month != tag_month(tag):
        raise ReleaseError(f"Release {tag} holds aggregates through {month}, not {tag_month(tag)}")
    return tag, path


def upload(archive: Path, tag: str | None = None, target: str | None = None) -> str:
    """Upload ``archive`` to Release ``data-<latest month>``, creating it if needed; return the tag."""
    index = read_index(archive)
    tag = tag or f"{TAG_PREFIX}{index['latest_month']}"
    if release_exists(tag):
        gh("release", "upload", tag, str(archive), "--clobber")
        return tag
    notes = (f"Aggregate tables (`data/agg/`) through {index['latest_month']}, packed {index['packed_at']} "
             f"by `python -m pipeline.release`. The refresh workflow restores the newest `{TAG_PREFIX}*` "
             "Release before processing the next month (SPEC §10). Tables hold sums, not averages (SPEC §5).")
    args = ["release", "create", tag, str(archive),
            "--title", f"Aggregates through {index['latest_month']}", "--notes", notes]
    if target:
        args += ["--target", target]
    gh(*args)
    return tag


# --- CLI ---------------------------------------------------------------------

def default_archive() -> Path:
    return common.data_dir() / ASSET


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.release", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("pack", help="data/agg/ and the manifest → aggregates.tar.zst")
    p.add_argument("--archive", type=Path, help=f"output file (default data/{ASSET})")
    p = sub.add_parser("unpack", help="aggregates.tar.zst → data/agg/ and the manifest")
    p.add_argument("--archive", type=Path, help=f"input file (default data/{ASSET})")
    p.add_argument("--force", action="store_true", help="overwrite aggregates already in data/")
    p = sub.add_parser("upload", help="upload aggregates.tar.zst as a Release asset")
    p.add_argument("--archive", type=Path, help=f"input file (default data/{ASSET})")
    p.add_argument("--tag", help=f"Release tag (default {TAG_PREFIX}<latest month in the archive>)")
    p.add_argument("--target", help="commit a new tag points at (default: the repo's default branch)")
    p = sub.add_parser("download", help="download the newest data Release asset; prints its tag")
    p.add_argument("--dir", type=Path, help="folder to save it in (default data/)")
    p.add_argument("--tag", help=f"Release tag (default: the newest {TAG_PREFIX}YYYY-MM)")
    sub.add_parser("latest-month", help="print the latest month in data/agg/")
    sub.add_parser("next-month", help="print the month after the latest in data/agg/")
    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    archive = getattr(args, "archive", None) or default_archive()
    try:
        if args.command == "pack":
            index = pack(archive)
            print(f"release: packed {len(index['files'])} files through {index['latest_month']} "
                  f"into {archive} ({archive.stat().st_size / 1e6:,.1f} MB)", file=sys.stderr)
        elif args.command == "unpack":
            index = unpack(archive, force=args.force)
            print(f"release: restored {len(index['files'])} files through {index['latest_month']} "
                  f"to {common.data_dir()}", file=sys.stderr)
        elif args.command == "upload":
            tag = upload(archive, tag=args.tag, target=args.target)
            print(f"release: uploaded {archive.name} to Release {tag}", file=sys.stderr)
        elif args.command == "download":
            tag, path = download(args.dir or common.data_dir(), tag=args.tag)
            print(f"release: downloaded {path} from Release {tag}", file=sys.stderr)
            print(tag)
        elif args.command == "latest-month":
            print(latest_month())
        else:
            print(next_month())
    except ReleaseError as exc:
        print(f"release: {exc}", file=sys.stderr)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
