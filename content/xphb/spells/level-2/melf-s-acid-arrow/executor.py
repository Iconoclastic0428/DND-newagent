from __future__ import annotations

from collections.abc import Mapping

from shared_types.capabilities import (
    ActiveEffectDefinition,
    AttackBonusSource,
    AttackExecutionKind,
    AttackRollGateEffect,
    CapabilityDefinition,
    CapabilityKind,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    ParameterizedActiveEffectDef,
    ParameterizedDamageEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)


SPELL_NAME = "Melf's Acid Arrow"
SPELL_SLUG = 'melf-s-acid-arrow'


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
            range_ft=90,
            affinity=TargetAffinity.ANY,
            requires_target_to_be_seen=True,
            max_targets=1,
        ),
        effect=AttackRollGateEffect(
            attack_kind=AttackExecutionKind.RANGED_SPELL,
            attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
            range_ft=90,
            magical=True,
            damaging=True,
            on_hit=(
                ParameterizedDamageEffectDef(
                    name=SPELL_NAME,
                    base_dice_count=4,
                    die_faces=4,
                    damage_type='acid',
                    slot_level_parameter_key='slot-level',
                    base_slot_level=2,
                    bonus_dice_per_slot_level=1,
                ),
                ParameterizedActiveEffectDef(
                    active_effect=ActiveEffectDefinition(
                        name=SPELL_NAME,
                        duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.TARGET),
                        on_end=(
                            ParameterizedDamageEffectDef(
                                name=SPELL_NAME,
                                base_dice_count=2,
                                die_faces=4,
                                damage_type='acid',
                                slot_level_parameter_key='slot-level',
                                base_slot_level=2,
                                bonus_dice_per_slot_level=1,
                            ),
                        ),
                    ),
                    metadata_parameter_keys=('slot-level',),
                ),
            ),
            on_miss=(
                ParameterizedDamageEffectDef(
                    name=SPELL_NAME,
                    base_dice_count=4,
                    die_faces=4,
                    damage_type='acid',
                    damage_divisor=2,
                    slot_level_parameter_key='slot-level',
                    base_slot_level=2,
                    bonus_dice_per_slot_level=1,
                ),
            ),
        ),
    )
