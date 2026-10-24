"""Write contract-shaped mock files to site/src/data/, marked ``as_of_month: "MOCK"``.

Run by ``make site-mock``. Mock files are for building pages before real data exists and
must never be committed or deployed.

Lane L01 · docs/lanes/L01-contracts.md
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pipeline.common import not_implemented  # noqa: E402

STUB_LANE = "L01"  # remove when the lane implements this script


def main() -> None:
    not_implemented(STUB_LANE, "make_mock_site_data")


if __name__ == "__main__":
    main()
