from __future__ import annotations

from collections.abc import Mapping


DISPLAY_NAME = 'Flame Blade'
SOURCE_ID = 'XPHB:spell:flame-blade'
BLOCKER_REASON = (
    'Blocked: missing a held conjured weapon lifecycle primitive that grants a reusable '
    'Flame Blade melee spell attack, tracks the blade in a free hand, dismisses it when '
    'released, and allows the spell\'s bonus-action resummon while concentration lasts.'
)


def _matches_local_spell(raw_spell: Mapping[str, object]) -> bool:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return False
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str):
        english_name = raw_spell.get('name')
    return isinstance(english_name, str) and english_name.strip() == DISPLAY_NAME


def build_capability_definition(raw_spell: Mapping[str, object]) -> None:
    """Return None until the exact shared Flame Blade primitive exists."""
    if not _matches_local_spell(raw_spell):
        return None
    return None
