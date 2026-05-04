from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import CapabilityDefinition


SPELL_NAME = 'Ray of Enfeeblement'


def build_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    english_name = raw_spell.get('ENG_name')
    if not isinstance(english_name, str) or english_name.strip() != SPELL_NAME:
        return None
    return None
