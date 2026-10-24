"""Site data budgets and component checks (L05).

Budgets: each route's data files within 1.5 MB, each zone file under 50 KB. Reads the route →
files map in contracts/site/pages.yaml and measures what is in site/src/data/ now: mock data
after `make site-mock`, real data after `make publish`. Skips when that folder holds no data yet
(a fresh checkout).

Components: format.js against the contracts/README.md §3 examples, palette.js against SPEC §9.5,
no literal colours elsewhere in site/src, and every component parses. These run in Node.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from pipeline import common

PAGES = yaml.safe_load((common.REPO_ROOT / "contracts" / "site" / "pages.yaml").read_text())
SITE_SRC = common.REPO_ROOT / "site" / "src"
COMPONENTS = SITE_SRC / "components"


def route_file_lists(route: dict) -> list[list[str]]:
    """Every concrete file list for a route: one per parameter value, or the route's own list."""
    params = route.get("params") or {}
    if not params:
        return [route["files"]]
    (key, values), = params.items()
    if isinstance(values, str):
        first, last = (int(v) for v in values.split(".."))
        values = [str(v) for v in range(first, last + 1)]
    return [[f.format(**{key: v}) for f in route["files"]] for v in values]


def budget_problems(data_dir: Path, pages: dict = PAGES) -> list[str]:
    """Routes over budget, zone files over their cap, and route files that are missing."""
    problems = []
    for name, route in pages["routes"].items():
        for files in route_file_lists(route):
            missing = [f for f in files if not (data_dir / f).is_file()]
            if missing:
                problems.append(f"{name}: missing {', '.join(missing)}")
                continue
            size = sum((data_dir / f).stat().st_size for f in files)
            if size > pages["budget_bytes"]:
                problems.append(f"{name} ({files[0]}): {size:,} bytes > {pages['budget_bytes']:,}")
    for path in sorted((data_dir / "zones").glob("[0-9]*.json")):
        if path.stat().st_size >= pages["zone_file_max_bytes"]:
            problems.append(f"zones/{path.name}: {path.stat().st_size:,} bytes >= {pages['zone_file_max_bytes']:,}")
    return problems


def test_site_data_within_budget():
    data_dir = common.SITE_DATA_DIR
    if not any(data_dir.glob("*.json")):
        pytest.skip("no site data yet: run make site-mock or make publish")
    assert budget_problems(data_dir) == []


# --- the checker itself ------------------------------------------------------

SMALL_PAGES = {
    "budget_bytes": 100,
    "zone_file_max_bytes": 40,
    "routes": {
        "/": {"files": ["home.json", "tiles.json"]},
        "/zones/{zone}": {"params": {"zone": "1..2"}, "files": ["zones/{zone}.json", "tiles.json"]},
    },
}


def _write(path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"x": "a" * max(0, size - 9)}))   # {"x": ""} is 9 bytes


def test_expands_parameter_ranges():
    lists = route_file_lists(SMALL_PAGES["routes"]["/zones/{zone}"])
    assert lists == [["zones/1.json", "tiles.json"], ["zones/2.json", "tiles.json"]]
    assert len(route_file_lists(PAGES["routes"]["/zones/{zone}"])) == 263
    assert len(route_file_lists(PAGES["routes"]["/companies/{company}"])) == 4


def test_passes_within_budget(tmp_path):
    for name, size in [("home.json", 50), ("tiles.json", 50), ("zones/1.json", 30), ("zones/2.json", 39)]:
        _write(tmp_path / name, size)
    assert budget_problems(tmp_path, SMALL_PAGES) == []


def test_flags_a_route_over_budget(tmp_path):
    for name, size in [("home.json", 51), ("tiles.json", 50), ("zones/1.json", 30), ("zones/2.json", 30)]:
        _write(tmp_path / name, size)
    assert budget_problems(tmp_path, SMALL_PAGES) == ["/ (home.json): 101 bytes > 100"]


def test_flags_a_zone_file_over_its_cap(tmp_path):
    for name, size in [("home.json", 10), ("tiles.json", 10), ("zones/1.json", 40), ("zones/2.json", 10)]:
        _write(tmp_path / name, size)
    assert budget_problems(tmp_path, SMALL_PAGES) == ["zones/1.json: 40 bytes >= 40"]


def test_flags_missing_files(tmp_path):
    for name, size in [("home.json", 10), ("tiles.json", 10), ("zones/1.json", 10)]:
        _write(tmp_path / name, size)
    assert budget_problems(tmp_path, SMALL_PAGES) == ["/zones/{zone}: missing zones/2.json"]


# --- components --------------------------------------------------------------

needs_node = pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")


def _node_eval(module: str, expressions: list[str]) -> list:
    """Imports a component in Node and returns the JSON value of each expression (`m` is the module)."""
    script = (f"const m = await import({json.dumps((COMPONENTS / module).as_uri())});\n"
              f"console.log(JSON.stringify([{', '.join(expressions)}]));")
    result = subprocess.run(["node", "--input-type=module", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


FORMAT_CASES = [   # contracts/README.md §3 examples, then edges L05 pinned
    ("m.count(842)", "842"),
    ("m.count(1280)", "1,280"),
    ("m.count(675432)", "675,000"),
    ("m.count(20100000)", "20.1 million"),
    ("m.share(0.84)", "84%"),
    ("m.share(0.032)", "3.2%"),
    ("m.shareChange(0.021)", "+2.1 pts"),
    ("m.shareChange(-0.004)", "−0.4 pts"),
    ("m.relChange(0.031)", "+3.1%"),
    ("m.relChange(-0.074)", "−7.4%"),
    ("m.usd(18.4)", "$18.40"),
    ("m.usd(4812)", "$4,812"),
    ("m.usd(48200000)", "$48.2 million"),
    ("m.usdPerMile(2.87)", "$2.87/mile"),
    ("m.usdPerMinute(1.12)", "$1.12/min"),
    ("m.usdPerHour(38.5)", "$38.50/hour"),
    ("m.seconds(252)", "4.2 min"),
    ("m.month('2025-01-01')", "Jan 2025"),
    ("m.month('2026-08')", "Aug 2026"),
    ("m.week('2025-01-06')", "week of 6 Jan 2025"),
    ("m.hourOfDay(6)", "6 am"),
    ("m.hourOfDay(12)", "12 pm"),
    ("m.hourOfDay(18)", "6 pm"),
    ("m.hourOfWeek(2 * 24 + 18)", "Tue 6 pm"),
    ("m.count(842.3)", "842.3"),
    ("m.count(9999999)", "10.0 million"),
    ("m.share(0.0996)", "10%"),
    ("m.shareChange(-0.0004)", "0.0 pts"),
    ("m.usd(99.999)", "$100"),
    ("m.usd(1000000)", "$1,000,000"),
    ("m.hourOfDay(0)", "12 am"),
    ("m.hourOfWeek(0)", "Sun 12 am"),
    ("m.asOf('MOCK')", "MOCK"),
    ("m.share(null)", "—"),
    ("m.value('usd_per_mile', 3.198)", "$3.20/mile"),
    ("m.change('pts', 'share', 0.0036)", "+0.4 pts"),
    ("m.change('diff', 'count', -3)", "−3"),
    ("m.change('none', 'text', null)", None),
    ("m.modeName('other_hv')", "Other ride-hail"),
]


@needs_node
def test_format_follows_the_contract():
    got = _node_eval("format.js", [expr for expr, _ in FORMAT_CASES])
    assert dict(zip([e for e, _ in FORMAT_CASES], got)) == dict(FORMAT_CASES)


SPEC_PALETTE = {   # SPEC §9.5
    "mode": {
        "uber": {"light": "#3A3A3A", "dark": "#D4D4D4"},
        "lyft": {"light": "#B4447F", "dark": "#E07AB0"},
        "yellow": {"light": "#D99A00", "dark": "#F2C14E"},
        "green": {"light": "#3C8D5A", "dark": "#6CC08A"},
        "other_hv": {"light": "#9AA0A6", "dark": "#80868B"},
    },
    "accent": {"light": "#2F6FDB", "dark": "#6E9CF0"},
    "muted": {"light": "#C9CDD2", "dark": "#4A4F55"},
}


@needs_node
def test_palette_matches_spec():
    mode, accent, muted, diverging, sequential = _node_eval(
        "palette.js", ["m.mode", "m.accent", "m.muted", "m.diverging.light", "m.sequential.light.scheme"])
    assert {"mode": mode, "accent": accent, "muted": muted} == SPEC_PALETTE
    assert diverging == ["#2F6FDB", "#F2F2F2", "#E07B39"]
    assert sequential == "blues"


HEX_COLOUR = re.compile(r"(?<![\w&])#(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})(?![\w-])")
CSS_COLOUR = re.compile(r"\b(?:rgba?|hsla?)\(")


def test_no_literal_colours_outside_the_palette():
    skip = {COMPONENTS / "palette.js"}
    found = []
    for path in SITE_SRC.rglob("*"):
        rel = path.relative_to(SITE_SRC)
        if path in skip or not path.is_file() or path.suffix not in {".js", ".md", ".css"} or rel.parts[0] in {"data", ".observablehq"}:
            continue
        for n, line in enumerate(path.read_text().splitlines(), 1):
            if HEX_COLOUR.search(line) or CSS_COLOUR.search(line):
                found.append(f"{rel}:{n}: {line.strip()[:80]}")
    assert found == []


@needs_node
@pytest.mark.parametrize("module", sorted(p.name for p in COMPONENTS.glob("*.js")))
def test_component_parses(module):
    result = subprocess.run(["node", "--check", str(COMPONENTS / module)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
