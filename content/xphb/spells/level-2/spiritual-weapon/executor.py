from __future__ import annotations

from collections.abc import Mapping


DISPLAY_NAME = 'Spiritual Weapon'
SOURCE_ID = 'XPHB:spell:spiritual-weapon'
BLOCKER_REASON = (
    'Blocked: missing a floating weapon command primitive that creates a persistent '
    'weapon anchor at a chosen point, makes the spell\'s immediate melee spell '
    'attack, and on later turns reuses the caster\'s bonus action to move up to 20 '
    'feet and attack again from the weapon\'s position.'
)


def _matches_local_spell(raw_spell: Mapping[str, object]) -> bool:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return False
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str):
        english_name = raw_spell.get('name')
    return isinstance(english_name, str) and english_name.strip() == DISPLAY_NAME


def build_capability_definition(raw_spell: Mapping[str, object]) -> None:
    """Return None until the exact shared Spiritual Weapon primitive exists."""
    if not _matches_local_spell(raw_spell):
        return None
    return None
