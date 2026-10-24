"""Load config/schema_map.yaml and resolve a file's raw columns to unified columns.

Raw columns match case-insensitively. A column the map neither maps nor ignores is an
error, never a guess (CLAUDE.md).

    mapping = resolve("yellow", "2025-03", ["VendorID", "Airport_fee", ...], "yellow_2025-03.parquet")
    # {"Airport_fee": "airport_fee", ...}: raw column as spelled in the file → unified column

Several raw columns can feed one unified column (``bcf`` and ``sales_tax`` → ``other_fees``);
each column entry's ``rule`` says how. ``select_range`` gives the whole range, including the
unified columns that come from a constant, NULL or a derivation rather than a raw column.

Lane L03 · SPEC §4 · docs/lanes/L03-schema.md
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from pipeline import common

SCHEMA_MAP_PATH = common.CONFIG_DIR / "schema_map.yaml"

# SPEC §4 unified columns, in table order. Clean (L06) adds the derived columns of §4.1.
UNIFIED_COLUMNS = (
    "mode", "month", "request_ts", "pickup_ts", "dropoff_ts", "pu_zone", "do_zone", "miles",
    "duration_s", "fare_base", "tips", "tolls", "airport_fee", "congestion_surcharge", "cbd_fee",
    "other_fees", "rider_total_ex_tip", "driver_pay", "is_card", "shared_request", "shared_match",
    "wav_request", "wav_match", "street_hail",
)

# Ways a range covers a unified column other than through a raw column.
_COVER_KEYS = ("constant", "nulls", "derived")
_RANGE_KEYS = {"valid_from", "valid_to", "columns", "ignore", *_COVER_KEYS}
_COLUMN_KEYS = {"unified", "type", "rule"}


class SchemaError(Exception):
    """A file or the map itself disagrees with config/schema_map.yaml."""

    def __init__(self, file: str, message: str):
        super().__init__(f"{file}: {message}")
        self.file = file
        self.message = message


class UnmappedColumnError(SchemaError):
    """A raw column that schema_map.yaml neither maps nor ignores."""

    def __init__(self, file: str, column: str):
        super().__init__(file, f"column {column!r} is not in config/schema_map.yaml")
        self.column = column


class MissingColumnError(SchemaError):
    """A column the file's range maps is absent from the file."""

    def __init__(self, file: str, column: str):
        super().__init__(file, f"column {column!r} is mapped in config/schema_map.yaml but missing")
        self.column = column


class ColumnTypeError(SchemaError):
    """A mapped column whose type differs from the type schema_map.yaml expects."""

    def __init__(self, file: str, column: str, expected: str, found: str):
        super().__init__(file, f"column {column!r} is {found}, config/schema_map.yaml expects {expected}")
        self.column = column
        self.expected = expected
        self.found = found


def load_schema_map(path: Path | None = None) -> dict:
    """Parsed config/schema_map.yaml (or ``path``), checked for consistency.

    Raises ``SchemaError`` naming the map file when a range is malformed, ranges overlap or
    leave a gap, a raw column appears twice, or a unified column is not covered exactly once.
    """
    path = path or SCHEMA_MAP_PATH
    with open(path, encoding="utf-8") as f:
        schema_map = yaml.safe_load(f)
    _check_map(schema_map, path.name)
    return schema_map


def select_range(dataset: str, month: str, schema_map: dict | None = None) -> dict:
    """The range of ``dataset`` whose ``valid_from``–``valid_to`` contains ``month``."""
    schema_map = schema_map if schema_map is not None else load_schema_map()
    if dataset not in schema_map:
        raise ValueError(f"unknown dataset {dataset!r}; expected one of {sorted(schema_map)}")
    wanted = common.parse_month(month)
    for rng in schema_map[dataset]:
        if _month(rng["valid_from"]) <= wanted and (rng["valid_to"] is None or wanted <= _month(rng["valid_to"])):
            return rng
    raise SchemaError(f"{dataset} {month}", "no range in config/schema_map.yaml covers this month")


def resolve(dataset: str, month: str, raw_columns: list[str], file: str,
            schema_map: dict | None = None) -> dict[str, str]:
    """Map each raw column of ``file`` to its unified column name.

    Keys are the raw columns as spelled in the file, in file order; ignored columns are
    left out. Raises ``UnmappedColumnError`` for a column neither mapped nor ignored, and
    ``MissingColumnError`` when a mapped column is missing.
    """
    schema_map = schema_map if schema_map is not None else load_schema_map()
    problems = find_problems(dataset, month, [(name, None) for name in raw_columns], file, schema_map)
    if problems:
        raise problems[0]
    rng = select_range(dataset, month, schema_map)
    mapped = {name.lower(): spec["unified"] for name, spec in rng["columns"].items()}
    return {name: mapped[name.lower()] for name in raw_columns if name.lower() in mapped}


def find_problems(dataset: str, month: str, columns: list[tuple[str, str | None]], file: str,
                  schema_map: dict | None = None) -> list[SchemaError]:
    """Every way ``file``'s columns break the map, unmapped columns first.

    ``columns`` holds ``(name, type)`` pairs as DuckDB's DESCRIBE reports them; a type of
    ``None`` skips the type check for that column.
    """
    try:
        rng = select_range(dataset, month, schema_map)
    except SchemaError as exc:
        return [SchemaError(file, exc.message)]
    mapped = {name.lower(): (name, spec) for name, spec in rng["columns"].items()}
    ignored = {name.lower() for name in rng["ignore"]}

    problems: list[SchemaError] = []
    seen: dict[str, str] = {}
    for name, found_type in columns:
        key = name.lower()
        if key in seen:
            problems.append(SchemaError(file, f"columns {seen[key]!r} and {name!r} differ only in case"))
            continue
        seen[key] = name
        if key in mapped:
            expected = mapped[key][1]["type"]
            if found_type is not None and found_type != expected:
                problems.append(ColumnTypeError(file, name, expected, found_type))
        elif key not in ignored:
            problems.append(UnmappedColumnError(file, name))
    problems.extend(MissingColumnError(file, name) for key, (name, _) in mapped.items() if key not in seen)
    problems.sort(key=lambda p: not isinstance(p, UnmappedColumnError))
    return problems


def unified_sources(rng: dict) -> dict[str, str]:
    """For each SPEC §4 unified column, a short description of where ``rng`` gets it."""
    sources: dict[str, list[str]] = {}
    for name, spec in rng["columns"].items():
        sources.setdefault(spec["unified"], []).append(name)
    described = {unified: " + ".join(names) for unified, names in sources.items()}
    described |= {unified: f"= {value!r}" for unified, value in (rng.get("constant") or {}).items()}
    described |= {unified: "NULL" for unified in rng.get("nulls") or []}
    described |= {unified: f"derived: {rule}" for unified, rule in (rng.get("derived") or {}).items()}
    return {unified: described[unified] for unified in UNIFIED_COLUMNS}


# --- map consistency ------------------------------------------------------------

def _month(value) -> date:
    return common.parse_month(str(value))


def _month_index(value) -> int:
    month = _month(value)
    return month.year * 12 + month.month


def _check_map(schema_map: dict, source: str) -> None:
    if not isinstance(schema_map, dict) or not schema_map:
        raise SchemaError(source, "expected a mapping of dataset → list of ranges")
    for dataset, ranges in schema_map.items():
        if dataset not in common.DATASETS:
            raise SchemaError(source, f"unknown dataset {dataset!r}")
        if not isinstance(ranges, list) or not ranges:
            raise SchemaError(source, f"{dataset}: expected a non-empty list of ranges")
        previous_end = None
        for i, rng in enumerate(ranges):
            where = f"{dataset} range {i + 1}"
            _check_range(rng, f"{source}: {where}")
            start = _month_index(rng["valid_from"])
            if previous_end is not None and start != previous_end + 1:
                raise SchemaError(source, f"{where} starts {rng['valid_from']}, not the month after the previous range")
            if rng["valid_to"] is None:
                if i != len(ranges) - 1:
                    raise SchemaError(source, f"{where}: only the last range may have valid_to: null")
            else:
                previous_end = _month_index(rng["valid_to"])
                if previous_end < start:
                    raise SchemaError(source, f"{where}: valid_to is before valid_from")


def _check_range(rng: dict, where: str) -> None:
    if not isinstance(rng, dict) or "valid_from" not in rng or "valid_to" not in rng:
        raise SchemaError(where, "needs valid_from and valid_to")
    if extra := set(rng) - _RANGE_KEYS:
        raise SchemaError(where, f"unknown keys {sorted(extra)}")
    try:
        _month(rng["valid_from"])
        if rng["valid_to"] is not None:
            _month(rng["valid_to"])
    except ValueError as exc:
        raise SchemaError(where, str(exc)) from None

    columns = rng.get("columns") or {}
    ignore = rng.get("ignore") or {}
    rng["columns"], rng["ignore"] = columns, ignore   # an absent or empty list becomes {}
    seen: dict[str, str] = {}
    for name in [*columns, *ignore]:
        if name.lower() in seen:
            raise SchemaError(where, f"raw column {name!r} is listed twice (as {seen[name.lower()]!r})")
        seen[name.lower()] = name
    for name, spec in columns.items():
        if not isinstance(spec, dict) or not {"unified", "type"} <= set(spec) or set(spec) - _COLUMN_KEYS:
            raise SchemaError(where, f"column {name!r} needs unified and type (and optionally rule)")
        if spec["unified"] not in UNIFIED_COLUMNS:
            raise SchemaError(where, f"column {name!r} maps to {spec['unified']!r}, not a SPEC §4 unified column")
    for name, reason in ignore.items():
        if not isinstance(reason, str) or not reason.strip():
            raise SchemaError(where, f"ignored column {name!r} needs a one-line reason")

    covered: dict[str, list[str]] = {}
    for name, spec in columns.items():
        covered.setdefault(spec["unified"], []).append("columns")
    for key in _COVER_KEYS:
        for unified in rng.get(key) or []:
            if unified not in UNIFIED_COLUMNS:
                raise SchemaError(where, f"{key} names {unified!r}, not a SPEC §4 unified column")
            covered.setdefault(unified, []).append(key)
    for unified in UNIFIED_COLUMNS:
        kinds = set(covered.get(unified, []))
        if len(kinds) != 1:
            how = " and ".join(sorted(kinds)) if kinds else "nothing"
            raise SchemaError(where, f"unified column {unified!r} is covered by {how}; expected exactly one")
