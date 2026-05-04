from __future__ import annotations

from collections.abc import Mapping


def build_capability_definition(raw_spell: Mapping[str, object]):
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str):
        english_name = raw_spell.get('name')
    if not isinstance(english_name, str) or english_name.strip() != 'Flaming Sphere':
        return None
    return None
