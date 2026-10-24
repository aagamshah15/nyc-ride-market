"""Metric outputs → site/src/data/ files, including generated titles and findings.

Refuses to write unless validation passed. ``--dev`` writes locally with
``"validated": false``, which deploy refuses.

Lane L11 · SPEC §9.2 · docs/lanes/L11-publish.md
"""

from __future__ import annotations

import argparse

from pipeline.common import not_implemented

STUB_LANE = "L11"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.publish", description=__doc__)
    parser.add_argument("--dev", action="store_true",
                        help="write without a passing validation, marked validated: false")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "publish")


if __name__ == "__main__":
    main()
