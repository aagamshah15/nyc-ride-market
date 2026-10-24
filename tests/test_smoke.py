"""Scaffold checks: shared helpers, config seeds, and stubs that name their lane."""

import importlib
import subprocess
import sys

import pytest

from pipeline import common

REPO_ROOT = common.REPO_ROOT

# Stub CLIs and a valid argument list for each. A module drops STUB_LANE when its lane
# implements it, and its check here is skipped from then on.
CLI_STUBS = {
    "ingest": ["--month", "2026-08"],
    "discover": [],
    "zones": [],
    "clean": ["--month", "2026-08"],
    "aggregate": ["--month", "2026-08"],
    "validate": [],
    "metrics": ["--all"],
    "studies": [],
    "publish": [],
    "release": ["pack"],
}


def test_data_dir_honours_env(data_dir):
    assert common.data_dir() == data_dir.resolve()
    assert common.raw_path("yellow", "2026-08") == data_dir / "raw" / "yellow" / "2026-08.parquet"
    assert common.clean_partition("uber", "2025-01") == data_dir / "clean" / "mode=uber" / "month=2025-01"
    assert common.agg_path("agg_zone_hour") == data_dir / "agg" / "agg_zone_hour.parquet"
    assert common.ref_dir() == data_dir / "ref"
    assert common.manifest_path() == data_dir / "manifest.json"
    assert common.scratch_dir("L04") == data_dir / "scratch" / "L04"
    assert (data_dir / "scratch" / "L04").is_dir()


def test_data_dir_default(monkeypatch):
    monkeypatch.delenv("NYC_DATA_DIR")
    assert common.data_dir() == REPO_ROOT / "data"


def test_month_range_crosses_year():
    assert common.month_range("2024-11", "2025-02") == ["2024-11", "2024-12", "2025-01", "2025-02"]


@pytest.mark.parametrize("bad", ["2024-13", "2024-1", "24-01", "2024/01", ""])
def test_parse_month_rejects(bad):
    with pytest.raises(ValueError):
        common.parse_month(bad)


def test_month_range_rejects_reversed():
    with pytest.raises(ValueError):
        common.month_range("2025-02", "2025-01")


def test_unknown_dataset_and_mode():
    with pytest.raises(ValueError):
        common.raw_path("fhv", "2026-08")
    with pytest.raises(ValueError):
        common.clean_partition("via", "2026-08")


def test_months_in_scope_starts_2024_01():
    months = common.months_in_scope()
    assert months[0] == "2024-01"
    assert months == sorted(months)


def test_config_seeds_match_spec():
    periods = common.load_yaml("periods.yaml")
    assert str(periods["congestion_pricing_start"]) == "2025-01-05"
    assert str(periods["driver_pay_rise"]) == "2025-08-01"
    assert periods["fees"] == {"cbd_fee_hvfhv": 1.50, "cbd_fee_taxi": 0.75}
    airports = {row["LocationID"]: row["airport"] for row in common.load_csv("airports.csv")}
    assert airports == {"1": "EWR", "132": "JFK", "138": "LGA"}
    sources = common.load_yaml("sources.yaml")
    assert sources["datasets"] == list(common.DATASETS)
    assert set(sources["hv_license"].values()) == {"uber", "lyft", "other_hv"}


def test_connect_uses_spill_dir(data_dir):
    con = common.connect()
    temp = con.execute("SELECT current_setting('temp_directory')").fetchone()[0]
    assert temp.startswith(str(data_dir))


def test_common_months_cli():
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.common", "months", "2025-12", "2026-01"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert result.stdout.split() == ["2025-12", "2026-01"]


@pytest.mark.parametrize("module", sorted(CLI_STUBS))
def test_stub_cli_names_its_lane(module):
    mod = importlib.import_module(f"pipeline.{module}")
    lane = getattr(mod, "STUB_LANE", None)
    if lane is None:
        pytest.skip(f"pipeline.{module} is implemented")
    result = subprocess.run(
        [sys.executable, "-m", f"pipeline.{module}", *CLI_STUBS[module]],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 3
    assert f"lane {lane}" in result.stderr


def test_stub_cli_rejects_bad_month():
    result = subprocess.run(
        [sys.executable, "-m", "pipeline.clean", "--month", "2026-8"],
        cwd=REPO_ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "YYYY-MM" in result.stderr


@pytest.mark.parametrize("module, call", [
    ("schema_map", lambda m: m.resolve("yellow", "2026-08", [], "f.parquet")),
    ("zones", lambda m: m.cbd_zone_ids()),
    ("metrics", lambda m: m.run("trip_share")),
])
def test_stub_library_names_its_lane(module, call):
    mod = importlib.import_module(f"pipeline.{module}")
    lane = getattr(mod, "STUB_LANE", None)
    if lane is None:
        pytest.skip(f"pipeline.{module} is implemented")
    with pytest.raises(NotImplementedError, match=f"lane {lane}"):
        call(mod)


def test_mock_script_stub():
    script = REPO_ROOT / "scripts" / "make_mock_site_data.py"
    if "STUB_LANE" not in script.read_text():
        pytest.skip("mock script is implemented")
    result = subprocess.run([sys.executable, str(script)], cwd=REPO_ROOT, capture_output=True, text=True)
    assert result.returncode == 3
    assert "lane L01" in result.stderr
