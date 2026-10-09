"""Explicit source-owned action recipes; generic execution stays in the kernel.

LMoP Redbrand Ruffian and MM Nothic entries were verified in the configured
5e.tools mirror. Multiattack uses the parsed source weapon statistics.
"""

from shared_types.capabilities import (
    AttackBonusSource,
    AttackExecutionKind,
    AttackRollGateEffect,
    CapabilityDefinition,
    CapabilityKind,
    CompositeEffect,
    DamageEffectDef,
    SaveDcSource,
    SaveGateEffect,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)
from shared_types.encounter_models import RuntimeCapabilityState
from shared_types.errors import ContentLoadError
from shared_types.models import Ability


def source_action_capabilities(monster):
    result = {}

    def add(key, name, range_ft, effect):
        definition = CapabilityDefinition(
            capability_id=key,
            name=name,
            kind=CapabilityKind.MONSTER_ACTION,
            source=monster.source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=range_ft,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
                requires_line_of_effect=True,
            ),
            effect=effect,
        )
        result[key] = RuntimeCapabilityState(
            key,
            name,
            monster.source,
            CapabilityKind.MONSTER_ACTION,
            'action',
            None,
            definition,
            source_record_id=monster.record_id,
        )

    sequence = {('Redbrand Ruffian', 'LMOP'): 'Shortsword', ('Nothic', 'MM'): 'Claw'}
    weapon = sequence.get((monster.name, monster.source))
    if weapon is not None:
        attack = next((attack for attack in monster.attacks if attack.name == weapon), None)
        if attack is None:
            raise ContentLoadError(f'{monster.record_id} requires its source attack {weapon}.')
        gate = AttackRollGateEffect(
            attack_kind=AttackExecutionKind.MELEE_WEAPON,
            attack_bonus_source=AttackBonusSource.FLAT,
            flat_attack_bonus=attack.to_hit_bonus,
            reach_ft=attack.reach_ft,
            on_hit=(
                DamageEffectDef(
                    dice_count=attack.damage_dice_count,
                    die_faces=attack.damage_die_faces,
                    bonus=attack.damage_bonus,
                    damage_type=attack.damage_type,
                ),
            ),
        )
        add('multiattack', 'Multiattack', attack.reach_ft, CompositeEffect(effects=(gate, gate)))
    if (monster.name, monster.source) == ('Nothic', 'MM'):
        add(
            'rotting-gaze',
            'Rotting Gaze',
            30,
            SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.FLAT,
                flat_dc=12,
                on_failure=(DamageEffectDef(dice_count=3, die_faces=6, bonus=0, damage_type='necrotic'),),
            ),
        )
    return result
