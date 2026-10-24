"""Zone shapefile → simplified GeoJSON, zone checks, and the congestion-zone helper.

Lane L04 · SPEC §3.3, §7 · decision D9 · docs/lanes/L04-zones.md
"""

from __future__ import annotations

import argparse

from pipeline.common import not_implemented

STUB_LANE = "L04"  # remove when the lane implements this module


def cbd_zone_ids(zone_list: str = "core") -> set[int]:
    """LocationIDs in the congestion zone. ``core`` excludes borderline zones; ``wide`` includes them."""
    raise NotImplementedError(f"zones.cbd_zone_ids (lane {STUB_LANE})")


def airport_zones() -> dict[int, str]:
    """LocationID → airport code, from config/airports.csv."""
    raise NotImplementedError(f"zones.airport_zones (lane {STUB_LANE})")


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog="python -m pipeline.zones", description=__doc__)


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "zones")


if __name__ == "__main__":
    main()
