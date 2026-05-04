from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import CapabilityDefinition

"""Blocked until the shared trail-suppression primitive exists."""


def build_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    return None
