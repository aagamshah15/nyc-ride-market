"""Load config/schema_map.yaml and resolve a file's raw columns to unified columns.

Raw columns match case-insensitively. A column the map neither maps nor ignores is an
error, never a guess (CLAUDE.md).

Lane L03 · SPEC §4 · docs/lanes/L03-schema.md
"""

from __future__ import annotations

STUB_LANE = "L03"  # remove when the lane implements this module


class UnmappedColumnError(Exception):
    """A raw column that schema_map.yaml neither maps nor ignores."""

    def __init__(self, file: str, column: str):
        super().__init__(f"{file}: column {column!r} is not in config/schema_map.yaml")
        self.file = file
        self.column = column


def load_schema_map() -> dict:
    """Parsed config/schema_map.yaml."""
    raise NotImplementedError(f"schema_map.load_schema_map (lane {STUB_LANE})")


def resolve(dataset: str, month: str, raw_columns: list[str], file: str) -> dict[str, str]:
    """Map each raw column of ``file`` to its unified column name.

    Raises ``UnmappedColumnError`` for a column neither mapped nor ignored, and an error
    when a required source column is missing.
    """
    raise NotImplementedError(f"schema_map.resolve (lane {STUB_LANE})")
