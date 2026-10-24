"""Validation gate: tie-out, quality drift, CBD list, schema and fee checks.

Writes reports/validation.md and data/agg/validation_summary.json; exits non-zero if any
check fails. Never widen a tolerance to make a check pass (CLAUDE.md).

Lane L08 · SPEC §8, §7.2 · decision D8 · docs/lanes/L08-validate.md
"""

from __future__ import annotations

import argparse

from pipeline.common import not_implemented

STUB_LANE = "L08"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(prog="python -m pipeline.validate", description=__doc__)


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "validate")


if __name__ == "__main__":
    main()
