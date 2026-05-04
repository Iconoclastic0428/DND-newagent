from __future__ import annotations

from collections.abc import Mapping


DISPLAY_NAME = "Dragon's Breath"
SOURCE_ID = 'XPHB:spell:dragon-s-breath'
BLOCKER_REASON = (
    'Blocked: missing an active-effect-granted reusable breath action primitive that '
    'attaches to the touched target, stores the chosen damage type and slot scaling, '
    'and resolves a 15-foot cone from that target with a Magic action.'
)


def _matches_local_spell(raw_spell: Mapping[str, object]) -> bool:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return False
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str):
        english_name = raw_spell.get('name')
    return isinstance(english_name, str) and english_name.strip() == DISPLAY_NAME


def build_capability_definition(raw_spell: Mapping[str, object]) -> None:
    """Return None until the exact shared Dragon's Breath primitive exists."""
    if not _matches_local_spell(raw_spell):
        return None
    return None
