from typing import Any


def one(rows: list[dict[str, Any]] | None, resource_name: str) -> dict[str, Any]:
    """The single expected row from a query, or a clear error naming what was missing."""
    if not rows:
        raise ValueError(f"{resource_name} not found.")
    return rows[0]
