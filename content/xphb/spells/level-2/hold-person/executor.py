from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    Ability,
    ActiveEffectDefinition,
    CapabilityDefinition,
    CapabilityKind,
    CompositeEffect,
    ConditionEffectDef,
    ConditionType,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    OngoingTriggerDefinition,
    ParameterizedTargetCountGateEffectDef,
    SaveDcSource,
    SaveGateEffect,
    StartActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
    TriggerActorScope,
    TriggerTiming,
)


SPELL_NAME = 'Hold Person'
SPELL_SLUG = 'hold-person'


def _canonical_name(raw_spell: Mapping[str, object]) -> str:
    name = str(raw_spell.get('ENG_name') or raw_spell.get('name') or '').strip()
    if not name:
        raise ValueError('Spell record is missing a canonical name.')
    return name


def build_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition:
    if _canonical_name(raw_spell) != SPELL_NAME:
        raise ValueError(f'Expected {SPELL_NAME!r}.')
    return CapabilityDefinition(
        capability_id=SPELL_SLUG,
        name=SPELL_NAME,
        kind=CapabilityKind.SPELL,
        source='XPHB',
        action_cost='action',
        targeting=TargetingSpec(
            selection_kind=TargetSelectionKind.CREATURE,
            range_ft=60,
            affinity=TargetAffinity.ANY,
            requires_target_to_be_seen=True,
            creature_type_filter='humanoid',
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
                SaveGateEffect(
                    ability=Ability.WIS,
                    dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                    on_failure=(
                        StartActiveEffectDef(
                            active_effect=ActiveEffectDefinition(
                                name=SPELL_NAME,
                                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                                concentration=True,
                                replace_existing_same_name_from_source=True,
                                on_start=(ConditionEffectDef(condition_type=ConditionType.PARALYZED, source_label='hold-person'),),
                                ongoing_triggers=(
                                    OngoingTriggerDefinition(
                                        timing=TriggerTiming.END_OF_TURN,
                                        actor_scope=TriggerActorScope.EACH_TARGET,
                                        save_ability=Ability.WIS,
                                        save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                        end_effect_on_success=True,
                                    ),
                                ),
                            ),
                            split_targets_individually=True,
                            concentration_anchor_name='Hold Person (anchor)',
                        ),
                    ),
                ),
            ),
        ),
    )
