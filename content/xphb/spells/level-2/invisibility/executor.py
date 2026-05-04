from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    ActiveEffectDefinition,
    CapabilityDefinition,
    CapabilityKind,
    CompositeEffect,
    ConditionEffectDef,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    ParameterizedTargetCountGateEffectDef,
    StartActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)
from shared_types.conditions import ConditionType


SPELL_NAME = 'Invisibility'
SPELL_SLUG = 'invisibility'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    english_name = raw_spell.get('ENG_name')
    if isinstance(english_name, str) and english_name.strip():
        return english_name.strip()
    raw_name = raw_spell.get('name')
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    return ''


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
            range_ft=5,
            affinity=TargetAffinity.ANY,
            requires_target_to_be_seen=True,
            max_targets=None,
        ),
        effect=CompositeEffect(
            effects=(
                ParameterizedTargetCountGateEffectDef(
                    name=SPELL_NAME,
                    base_target_count=1,
                    targets_per_extra_slot_level=1,
                    slot_level_parameter_key='slot-level',
                    base_slot_level=2,
                ),
                StartActiveEffectDef(
                    active_effect=ActiveEffectDefinition(
                        name=SPELL_NAME,
                        duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.TARGET),
                        concentration=True,
                        replace_existing_same_name_from_source=True,
                        end_when_target_attacks_or_harmful_casts=True,
                        end_when_target_casts_spell=True,
                        end_when_target_deals_damage=True,
                        on_start=(ConditionEffectDef(condition_type=ConditionType.INVISIBLE),),
                    ),
                    split_targets_individually=True,
                    concentration_anchor_name='Invisibility (anchor)',
                ),
            ),
        ),
    )
