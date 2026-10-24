"""Pack and unpack data/agg/ as aggregates.tar.zst, and move it to and from a GitHub Release.

Lane L17 · SPEC §10 · docs/lanes/L17-refresh-deploy.md
"""

from __future__ import annotations

import argparse

from pipeline.common import not_implemented

STUB_LANE = "L17"  # remove when the lane implements this module


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m pipeline.release", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("pack", help="data/agg/ → aggregates.tar.zst")
    sub.add_parser("unpack", help="aggregates.tar.zst → data/agg/")
    sub.add_parser("upload", help="upload aggregates.tar.zst as a Release asset")
    sub.add_parser("download", help="download the latest Release asset")
    return parser


def main(argv: list[str] | None = None) -> None:
    build_parser().parse_args(argv)
    not_implemented(STUB_LANE, "release")


if __name__ == "__main__":
    main()
