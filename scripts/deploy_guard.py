"""Refuse to deploy site data that is mock or unvalidated.

Every JSON file in site/src/data/ must carry the envelope (contracts/README.md §1) with a real
``as_of_month`` (``YYYY-MM``, never ``"MOCK"``) and ``validated: true``, and all of them must
share one ``as_of_month``. ``--month`` also requires that month. Exits 0 when the data can be
deployed, or 1 listing the problems. ``taxi_zones.geojson`` carries no envelope and isn't checked.

    python scripts/deploy_guard.py                  # site/src/data/
    python scripts/deploy_guard.py --month 2026-09  # and every file is as of 2026-09

Run by .github/workflows/refresh.yml before anything is committed or deployed.

Lane L17 · SPEC §10 · contracts/README.md §1
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SITE_DATA = REPO_ROOT / "site" / "src" / "data"
REQUIRED = ("home.json",)   # an empty or half-written folder isn't a site
MOCK = "MOCK"
MAX_LISTED = 20

_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def problems(data: Path, month: str | None = None) -> list[str]:
    """Everything that stops ``data`` from being deployed; empty when it can be."""
    if not data.is_dir():
        return [f"{data} not found"]
    files = sorted(data.rglob("*.json"))
    found = [f"{name} missing" for name in REQUIRED if not (data / name).is_file()]
    months: dict[str, list[str]] = {}
    for path in files:
        rel = path.relative_to(data).as_posix()
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            found.append(f"{rel}: not readable JSON ({exc})")
            continue
        if not isinstance(obj, dict):
            found.append(f"{rel}: not a JSON object, so no envelope")
            continue
        as_of = obj.get("as_of_month")
        if as_of == MOCK:
            found.append(f"{rel}: mock data (as_of_month \"MOCK\")")
        elif not isinstance(as_of, str) or not _MONTH.match(as_of):
            found.append(f"{rel}: as_of_month is {as_of!r}, not YYYY-MM")
        else:
            months.setdefault(as_of, []).append(rel)
        if obj.get("validated") is not True:
            found.append(f"{rel}: validated is {obj.get('validated')!r}, not true")
    if len(months) > 1:
        counts = ", ".join(f"{m} ({len(paths)} files)" for m, paths in sorted(months.items()))
        found.append(f"files disagree on as_of_month: {counts}")
    if month is not None and months and set(months) != {month}:
        found.append(f"as_of_month is {', '.join(sorted(months))}, expected {month}")
    return found


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="scripts/deploy_guard.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data", type=Path, default=SITE_DATA, help="site data folder (default site/src/data/)")
    parser.add_argument("--month", help="require every file to be as of this YYYY-MM")
    args = parser.parse_args(argv)
    if args.month is not None and not _MONTH.match(args.month):
        parser.error(f"--month must look like YYYY-MM, got {args.month!r}")
    found = problems(args.data, args.month)
    if found:
        listed = found[:MAX_LISTED] + ([f"… and {len(found) - MAX_LISTED} more"] if len(found) > MAX_LISTED else [])
        print("deploy_guard: refusing to deploy " + str(args.data), file=sys.stderr)
        print("\n".join(f"- {p}" for p in listed), file=sys.stderr)
        raise SystemExit(1)
    count = sum(1 for _ in args.data.rglob("*.json"))
    print(f"deploy_guard: {count} files in {args.data} are validated real data")


if __name__ == "__main__":
    main()
