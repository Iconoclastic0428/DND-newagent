from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    ActiveEffectDefinition,
    CapabilityDefinition,
    CapabilityKind,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    ParameterizedActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)


SPELL_NAME = 'Aid'
SPELL_SLUG = 'aid'


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
        action_cost='action',
        targeting=TargetingSpec(
            selection_kind=TargetSelectionKind.CREATURE,
            range_ft=30,
            affinity=TargetAffinity.ANY,
            requires_target_to_be_seen=True,
            max_targets=3,
        ),
        effect=ParameterizedActiveEffectDef(
            active_effect=ActiveEffectDefinition(
                name=SPELL_NAME,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=4800, anchor=DurationAnchor.SOURCE),
                max_hit_points_bonus=5,
            ),
            slot_level_parameter_key='slot-level',
            base_slot_level=2,
            bonus_max_hit_points_per_slot_level=5,
        ),
    )
