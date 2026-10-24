"""Structural check of a JSON value against its contract example (contracts/site/).

Objects must have exactly the example's keys; values must have the example's JSON type;
every item of an array must match the example's items (merged into one template).
``null`` is allowed anywhere (contracts/README.md §4), and an empty example array or a
``null`` example value leaves that position unconstrained.

Owned by L01; changed through the integrator.
"""

from __future__ import annotations

MAX_ERRORS = 50


def _kind(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"not a JSON value: {type(value).__name__}")


def _template(items: list):
    """One template from an example array: for objects, each key's first non-null value."""
    if items and all(isinstance(item, dict) for item in items):
        merged: dict = {}
        for item in items:
            for key, value in item.items():
                if merged.get(key) is None:
                    merged[key] = value
        return merged
    return next((item for item in items if item is not None), None)


def contract_errors(actual, example, path: str = "$") -> list[str]:
    """Every way ``actual`` departs from ``example``, as ``path: problem`` strings."""
    if actual is None or example is None:
        return []
    actual_kind, example_kind = _kind(actual), _kind(example)
    if actual_kind != example_kind:
        return [f"{path}: expected {example_kind}, got {actual_kind}"]
    errors: list[str] = []
    if example_kind == "object":
        errors += [f"{path}.{key}: missing" for key in sorted(example.keys() - actual.keys())]
        errors += [f"{path}.{key}: not in contract" for key in sorted(actual.keys() - example.keys())]
        for key in sorted(example.keys() & actual.keys()):
            errors += contract_errors(actual[key], example[key], f"{path}.{key}")
            if len(errors) >= MAX_ERRORS:
                break
    elif example_kind == "array":
        template = _template(example)
        if template is not None:
            for i, item in enumerate(actual):
                errors += contract_errors(item, template, f"{path}[{i}]")
                if len(errors) >= MAX_ERRORS:
                    break
    return errors


def assert_matches_contract(actual, example, path: str = "$") -> None:
    """Raise ``AssertionError`` listing every departure from the example."""
    errors = contract_errors(actual, example, path)
    if errors:
        raise AssertionError("does not match its contract:\n  " + "\n  ".join(errors[:MAX_ERRORS]))
