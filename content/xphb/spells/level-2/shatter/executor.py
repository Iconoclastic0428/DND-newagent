from __future__ import annotations

from collections.abc import Mapping


SPELL_NAME = 'Shatter'
SPELL_SLUG = 'shatter'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    english_name = raw_spell.get('ENG_name')
    if isinstance(english_name, str) and english_name.strip():
        return english_name.strip()
    raw_name = raw_spell.get('name')
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    return ''


def build_capability_definition(raw_spell: Mapping[str, object]):
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    if _canonical_name(raw_spell) != SPELL_NAME:
        return None
    return None
