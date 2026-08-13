"""Pins the entities produced by every ability and ref table entry.

The configure functions decide which entities a device exposes and what their
initial payload looks like. This golden test walks every table entry so a
refactor of the shared matching logic, or an accidental edit to a table, shows
up as an exact diff instead of a device silently losing an entity.

Regenerate deliberately with::

    uv run python -m tests.entity_tables --update
"""

import json
from pathlib import Path

from .entity_tables import full_snapshot

GOLDEN = Path(__file__).parent / "entity_tables_golden.json"


def test_configured_entities_match_the_golden_snapshot() -> None:
    """Every table entry must still produce exactly the recorded entity."""
    expected = json.loads(GOLDEN.read_text(encoding="utf-8"))

    assert full_snapshot() == expected


def test_golden_file_is_normalised() -> None:
    """Keeps regenerated files diffable instead of reordered."""
    raw = GOLDEN.read_text(encoding="utf-8")

    assert (
        raw
        == json.dumps(json.loads(raw), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )
