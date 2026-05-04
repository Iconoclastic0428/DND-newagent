from __future__ import annotations

from collections.abc import Mapping


DISPLAY_NAME = 'Heat Metal'
SOURCE_ID = 'XPHB:spell:heat-metal'
BLOCKER_REASON = (
    'Blocked: missing an item-linked harmful effect primitive that anchors the spell '
    'to a specific manufactured metal object, reapplies bonus-action damage through '
    'that object, tracks holder or wearer contact, forces a drop on a failed '
    'Constitution save when possible, and applies attack-roll and ability-check '
    'disadvantage until the caster\'s next turn if the object stays in contact.'
)


def _matches_local_spell(raw_spell: Mapping[str, object]) -> bool:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return False
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str):
        english_name = raw_spell.get('name')
    return isinstance(english_name, str) and english_name.strip() == DISPLAY_NAME


def build_capability_definition(raw_spell: Mapping[str, object]) -> None:
    """Return None until the exact shared Heat Metal primitive exists."""
    if not _matches_local_spell(raw_spell):
        return None
    return None
