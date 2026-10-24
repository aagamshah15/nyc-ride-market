"""Tables for the congestion-pricing and pay-rise write-ups in reports/.

Lane L10 · SPEC §6 · decisions D7, D9, D12 · docs/lanes/L10-policy-studies.md
"""

from __future__ import annotations

import argparse

from pipeline.common import not_implemented

STUB_LANE = "L10"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog="python -m pipeline.studies", description=__doc__)


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "studies")


if __name__ == "__main__":
    main()
