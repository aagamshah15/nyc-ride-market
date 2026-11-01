"""Release archive (L17): pack/unpack round trip, Release steps with gh mocked, and the deploy guard."""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import tarfile
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from factories import agg_table, write_agg

from pipeline import common, release
from pipeline.aggregate import TABLES

REPO_ROOT = Path(__file__).resolve().parents[1]
NOW = datetime(2026, 10, 31, 14, 0, tzinfo=timezone.utc)

requires_zstd = pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd command not installed")


def _load_guard():
    spec = importlib.util.spec_from_file_location("deploy_guard", REPO_ROOT / "scripts" / "deploy_guard.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = _load_guard()


def write_aggregates(months=(date(2025, 3, 1),)):
    """Every aggregate table, a validation summary and a manifest under NYC_DATA_DIR."""
    for name in TABLES:
        write_agg(name, agg_table(name, [{"month": m} for m in months]))
    agg = common.agg_dir()
    (agg / "validation_summary.json").write_text(json.dumps({"status": "pass"}))
    common.manifest_path().write_text(json.dumps({"files": {"raw/yellow/2025-03.parquet": {"bytes": 1}}}))
    return common.data_dir()


def snapshot(data: Path) -> dict[str, bytes]:
    files = {p.relative_to(data).as_posix(): p.read_bytes() for p in (data / "agg").iterdir()}
    files["manifest.json"] = (data / "manifest.json").read_bytes()
    return files


def write_archive(path: Path, members: dict[str, bytes]) -> Path:
    """A hand-built archive: members in order, compressed with zstd."""
    with open(path, "wb") as out:
        proc = subprocess.Popen(["zstd", "-q", "-c"], stdin=subprocess.PIPE, stdout=out)
        with tarfile.open(fileobj=proc.stdin, mode="w|") as tar:
            for name, body in members.items():
                info = tarfile.TarInfo(name)
                info.size = len(body)
                tar.addfile(info, io.BytesIO(body))
        proc.stdin.close()
        assert proc.wait() == 0
    return path


def index_for(members: dict[str, bytes], month="2025-03") -> bytes:
    files = {n: {"bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()} for n, b in members.items()}
    return json.dumps({"latest_month": month, "packed_at": "2026-10-31T14:00:00Z", "files": files}).encode()


# --- months ------------------------------------------------------------------

def test_next_month_comes_from_the_aggregates_and_rolls_the_year():
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [{"month": date(2025, 11, 1)},
                                                           {"month": date(2025, 12, 1)}]))
    assert release.latest_month() == "2025-12"
    assert release.next_month() == "2026-01"


def test_latest_month_needs_the_aggregates():
    with pytest.raises(release.ReleaseError, match="restore the aggregates first"):
        release.latest_month()


@pytest.mark.parametrize("tag, month", [
    ("data-2026-08", "2026-08"), ("data-2026-13", None), ("data-2026-8", None),
    ("v1.0", None), ("data-2026-08-rc", None),
])
def test_tag_month(tag, month):
    assert release.tag_month(tag) == month


# --- pack and unpack ---------------------------------------------------------

@requires_zstd
def test_pack_unpack_round_trip(tmp_path):
    data = write_aggregates(months=(date(2025, 2, 1), date(2025, 3, 1)))
    archive = tmp_path / "out" / release.ASSET
    index = release.pack(archive, now=NOW)

    assert index["latest_month"] == "2025-03"
    assert index["packed_at"] == "2026-10-31T14:00:00Z"
    assert set(index["files"]) == ({f"agg/{t}.parquet" for t in TABLES}
                                   | {"agg/validation_summary.json", "manifest.json"})
    assert release.read_index(archive) == index
    assert not list(archive.parent.glob("*.part"))

    restored = tmp_path / "restored"
    assert release.unpack(archive, data=restored) == index
    assert snapshot(restored) == snapshot(data)
    assert sorted(p.name for p in restored.iterdir()) == ["agg", "manifest.json"]   # staging folder gone
    assert release.next_month(restored) == "2025-04"


@requires_zstd
def test_pack_skips_hidden_and_foreign_files(tmp_path):
    write_aggregates()
    (common.agg_dir() / ".agg_zone_hour.parquet.tmp").write_bytes(b"partial")
    (common.agg_dir() / "notes.txt").write_text("not an aggregate")
    index = release.pack(tmp_path / release.ASSET)
    assert not any("tmp" in name or "notes" in name for name in index["files"])


def test_pack_refuses_an_incomplete_set_of_tables(tmp_path):
    write_aggregates()
    common.agg_path("agg_fee_values").unlink()
    with pytest.raises(release.ReleaseError, match="missing agg_fee_values"):
        release.pack(tmp_path / release.ASSET)


@requires_zstd
def test_unpack_wont_overwrite_aggregates_without_force(tmp_path):
    write_aggregates()
    archive = tmp_path / release.ASSET
    release.pack(archive)
    with pytest.raises(release.ReleaseError, match="unpack --force"):
        release.unpack(archive)

    marker = common.agg_dir() / "validation_summary.json"
    marker.write_text("changed locally")
    release.unpack(archive, force=True)
    assert json.loads(marker.read_text()) == {"status": "pass"}


@requires_zstd
def test_unpack_rejects_a_file_that_doesnt_match_its_checksum(tmp_path):
    good = {"agg/agg_zone_hour.parquet": b"PAR1 real"}
    archive = write_archive(tmp_path / release.ASSET, {
        release.INDEX: index_for(good), "agg/agg_zone_hour.parquet": b"PAR1 tampered"})
    target = tmp_path / "data2"
    with pytest.raises(release.ReleaseError, match="doesn't match its sha256"):
        release.unpack(archive, data=target)
    assert not (target / "agg").exists()
    assert not list(target.glob(".unpack-*"))


@requires_zstd
def test_unpack_rejects_members_the_index_doesnt_list(tmp_path):
    listed = {"agg/agg_zone_hour.parquet": b"PAR1"}
    archive = write_archive(tmp_path / release.ASSET, {
        release.INDEX: index_for(listed), **listed, "agg/agg_extra.parquet": b"PAR1"})
    with pytest.raises(release.ReleaseError, match="extra"):
        release.unpack(archive, data=tmp_path / "data2")


@requires_zstd
@pytest.mark.parametrize("name", ["../escape.parquet", "agg/sub/table.parquet", "raw/yellow/2025-03.parquet",
                                  "agg/.hidden.parquet", "agg/table.csv", "/etc/passwd"])
def test_unpack_rejects_unexpected_paths(tmp_path, name):
    archive = write_archive(tmp_path / release.ASSET, {release.INDEX: index_for({}), name: b"x"})
    with pytest.raises(release.ReleaseError, match="unexpected archive member"):
        release.unpack(archive, data=tmp_path / "data2")
    assert not (tmp_path / "escape.parquet").exists()


@requires_zstd
def test_read_index_needs_the_index_first(tmp_path):
    archive = write_archive(tmp_path / release.ASSET, {"manifest.json": b"{}", release.INDEX: index_for({})})
    with pytest.raises(release.ReleaseError, match="first member is not release.json"):
        release.read_index(archive)


@requires_zstd
def test_unpack_rejects_a_file_that_isnt_an_archive(tmp_path):
    bogus = tmp_path / release.ASSET
    bogus.write_text("<html>Not Found</html>")
    with pytest.raises(release.ReleaseError):
        release.unpack(bogus, data=tmp_path / "data2")


# --- GitHub Releases (gh is mocked; never called for real) -------------------

class FakeGh:
    """Stands in for ``release.gh``: records calls and answers from ``releases``."""

    def __init__(self, releases=(), assets=None):
        self.releases = list(releases)           # [{"tagName": ..., "isDraft": ...}]
        self.assets = assets or {}                # tag → archive path to hand out
        self.calls = []

    def __call__(self, *args):
        self.calls.append(args)
        if args[:2] == ("release", "list"):
            return json.dumps(self.releases)
        if args[:2] == ("release", "view"):
            if any(r["tagName"] == args[2] for r in self.releases):
                return json.dumps({"tagName": args[2]})
            raise release.GhError(args, 1, "release not found")
        if args[:2] == ("release", "download"):
            tag, dest = args[2], Path(args[args.index("--dir") + 1])
            shutil.copyfile(self.assets[tag], dest / release.ASSET)
            return ""
        if args[:2] in (("release", "create"), ("release", "upload")):
            return ""
        raise AssertionError(f"unexpected gh call {args}")


def test_latest_tag_takes_the_latest_data_month(monkeypatch):
    fake = FakeGh([{"tagName": "data-2026-07", "isDraft": False},
                   {"tagName": "data-2026-09", "isDraft": True},
                   {"tagName": "v1.0", "isDraft": False},
                   {"tagName": "data-2026-08", "isDraft": False},
                   {"tagName": "data-2025-12", "isDraft": False}])
    monkeypatch.setattr(release, "gh", fake)
    assert release.latest_tag() == "data-2026-08"


def test_download_without_a_data_release_says_how_to_seed_one(monkeypatch, tmp_path):
    monkeypatch.setattr(release, "gh", FakeGh([{"tagName": "v1.0", "isDraft": False}]))
    with pytest.raises(release.ReleaseError, match="upload the first one"):
        release.download(tmp_path)


@requires_zstd
def test_download_fetches_the_newest_release_and_checks_its_month(monkeypatch, tmp_path):
    write_aggregates()
    archive = tmp_path / "packed" / release.ASSET
    release.pack(archive)
    fake = FakeGh([{"tagName": "data-2025-02", "isDraft": False}, {"tagName": "data-2025-03", "isDraft": False}],
                  assets={"data-2025-03": archive, "data-2025-02": archive})
    monkeypatch.setattr(release, "gh", fake)

    tag, path = release.download(tmp_path / "dl")
    assert (tag, path) == ("data-2025-03", tmp_path / "dl" / release.ASSET)
    assert fake.calls[-1] == ("release", "download", "data-2025-03", "--pattern", release.ASSET,
                              "--dir", str(tmp_path / "dl"), "--clobber")

    with pytest.raises(release.ReleaseError, match="through 2025-03, not 2025-02"):
        release.download(tmp_path / "dl2", tag="data-2025-02")


@requires_zstd
def test_upload_creates_the_release_for_the_archives_month(monkeypatch, tmp_path):
    write_aggregates()
    archive = tmp_path / release.ASSET
    release.pack(archive)
    fake = FakeGh([{"tagName": "data-2025-02", "isDraft": False}])
    monkeypatch.setattr(release, "gh", fake)

    assert release.upload(archive, target="abc123") == "data-2025-03"
    create = fake.calls[-1]
    assert create[:4] == ("release", "create", "data-2025-03", str(archive))
    assert create[create.index("--target") + 1] == "abc123"
    assert create[create.index("--title") + 1] == "Aggregates through 2025-03"


@requires_zstd
def test_upload_replaces_the_asset_when_the_release_exists(monkeypatch, tmp_path):
    write_aggregates()
    archive = tmp_path / release.ASSET
    release.pack(archive)
    fake = FakeGh([{"tagName": "data-2025-03", "isDraft": False}])
    monkeypatch.setattr(release, "gh", fake)

    assert release.upload(archive) == "data-2025-03"
    assert fake.calls[-1] == ("release", "upload", "data-2025-03", str(archive), "--clobber")
    assert not any(call[1] == "create" for call in fake.calls)


def test_release_exists_reraises_other_gh_errors(monkeypatch):
    def broken(*args):
        raise release.GhError(args, 4, "HTTP 401: Bad credentials")
    monkeypatch.setattr(release, "gh", broken)
    with pytest.raises(release.GhError, match="Bad credentials"):
        release.release_exists("data-2025-03")


def _fake_gh_on_path(tmp_path, monkeypatch, script: str) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "gh"
    fake.write_text("#!/bin/sh\n" + script)
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bin_dir}{os.pathsep}{os.environ['PATH']}")


def test_gh_runs_the_command_on_path(tmp_path, monkeypatch):
    _fake_gh_on_path(tmp_path, monkeypatch, 'echo "args: $*"\n')
    assert release.gh("release", "list", "--limit", "5") == "args: release list --limit 5\n"


def test_gh_failure_raises_with_its_stderr(tmp_path, monkeypatch):
    _fake_gh_on_path(tmp_path, monkeypatch, 'echo "release not found" >&2\nexit 1\n')
    with pytest.raises(release.GhError, match="release not found") as caught:
        release.gh("release", "view", "data-2025-03")
    assert caught.value.returncode == 1


# --- CLI ---------------------------------------------------------------------

def test_cli_next_month_prints_only_the_month(capsys):
    write_agg("agg_zone_hour", agg_table("agg_zone_hour", [{"month": date(2026, 8, 1)}]))
    release.main(["next-month"])
    assert capsys.readouterr().out == "2026-09\n"


@requires_zstd
def test_cli_download_prints_only_the_tag(monkeypatch, tmp_path, capsys):
    write_aggregates()
    archive = tmp_path / "packed" / release.ASSET
    release.pack(archive)
    monkeypatch.setattr(release, "gh", FakeGh([{"tagName": "data-2025-03", "isDraft": False}],
                                              assets={"data-2025-03": archive}))
    release.main(["download", "--dir", str(tmp_path / "dl")])
    assert capsys.readouterr().out == "data-2025-03\n"


def test_cli_errors_exit_1(capsys):
    with pytest.raises(SystemExit) as caught:
        release.main(["latest-month"])
    assert caught.value.code == 1
    assert "restore the aggregates first" in capsys.readouterr().err


# --- deploy guard ------------------------------------------------------------

def site_data(root: Path, files: dict[str, dict]) -> Path:
    for rel, obj in files.items():
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj))
    return root


REAL = {"as_of_month": "2026-08", "generated_at": "2026-10-31T00:00:00Z", "validated": True}


def test_guard_passes_validated_real_data(tmp_path):
    data = site_data(tmp_path / "data", {"home.json": REAL, "companies/uber.json": REAL, "zones/index.json": REAL})
    (data / "taxi_zones.geojson").write_text('{"type": "FeatureCollection", "features": []}')
    assert guard.problems(data) == []
    assert guard.problems(data, month="2026-08") == []


def test_guard_refuses_mock_data(tmp_path):
    mock = {**REAL, "as_of_month": "MOCK", "validated": False}
    data = site_data(tmp_path / "data", {"home.json": REAL, "zones/17.json": mock})
    found = guard.problems(data)
    assert any("zones/17.json: mock data" in p for p in found)
    assert any("zones/17.json: validated is False" in p for p in found)


@pytest.mark.parametrize("override, message", [
    ({"validated": False}, "validated is False, not true"),
    ({"validated": "true"}, "validated is 'true', not true"),
    ({"as_of_month": "2026-8"}, "as_of_month is '2026-8', not YYYY-MM"),
])
def test_guard_refuses_unvalidated_or_malformed_envelopes(tmp_path, override, message):
    data = site_data(tmp_path / "data", {"home.json": REAL, "drivers.json": {**REAL, **override}})
    assert guard.problems(data) == [f"drivers.json: {message}"]


def test_guard_refuses_a_missing_validated_key(tmp_path):
    data = site_data(tmp_path / "data", {"home.json": {"as_of_month": "2026-08"}})
    assert guard.problems(data) == ["home.json: validated is None, not true"]


def test_guard_refuses_mixed_or_unexpected_months(tmp_path):
    data = site_data(tmp_path / "data", {"home.json": REAL, "prices.json": {**REAL, "as_of_month": "2026-07"}})
    assert guard.problems(data) == ["files disagree on as_of_month: 2026-07 (1 files), 2026-08 (1 files)"]
    single = site_data(tmp_path / "single", {"home.json": REAL})
    assert guard.problems(single, month="2026-09") == ["as_of_month is 2026-08, expected 2026-09"]


def test_guard_refuses_an_empty_or_missing_folder(tmp_path):
    assert guard.problems(tmp_path / "nowhere") == [f"{tmp_path / 'nowhere'} not found"]
    (tmp_path / "empty").mkdir()
    assert guard.problems(tmp_path / "empty") == ["home.json missing"]


def test_guard_cli_exits_1_and_lists_problems(tmp_path, capsys):
    data = site_data(tmp_path / "data", {"home.json": {**REAL, "validated": False}})
    with pytest.raises(SystemExit) as caught:
        guard.main(["--data", str(data)])
    assert caught.value.code == 1
    assert "- home.json: validated is False, not true" in capsys.readouterr().err

    guard.main(["--data", str(site_data(tmp_path / "ok", {"home.json": REAL})), "--month", "2026-08"])
    assert "1 files" in capsys.readouterr().out


def test_committed_site_data_passes_the_guard():
    home = common.SITE_DATA_DIR / "home.json"
    if not home.is_file() or json.loads(home.read_text()).get("as_of_month") == "MOCK":
        pytest.skip("no real site data in this checkout")
    assert guard.problems(common.SITE_DATA_DIR) == []
