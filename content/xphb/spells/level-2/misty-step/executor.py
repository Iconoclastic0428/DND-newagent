from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import CapabilityDefinition, CapabilityKind, TeleportEffectDef, TargetAffinity, TargetSelectionKind, TargetingSpec


SPELL_NAME = 'Misty Step'
SPELL_SLUG = 'misty-step'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    return str(raw_spell.get('ENG_name') or raw_spell.get('name') or '').strip()


def build_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    if str(raw_spell.get('source', '')).upper() != 'XPHB' or raw_spell.get('level') != 2:
        return None
    if _canonical_name(raw_spell) != SPELL_NAME:
        return None
    return CapabilityDefinition(
        capability_id=SPELL_SLUG,
        name=SPELL_NAME,
        kind=CapabilityKind.SPELL,
        source='XPHB',
        action_cost='bonus-action',
        targeting=TargetingSpec(
            selection_kind=TargetSelectionKind.POINT,
            range_ft=30,
            affinity=TargetAffinity.SELF_ONLY,
            requires_line_of_effect=False,
            requires_unoccupied_point=True,
            point_must_be_visible=True,
        ),
        effect=TeleportEffectDef(
            requires_visible_destination=True,
            requires_unoccupied_destination=True,
            requires_line_of_effect=False,
        ),
    )
