from __future__ import annotations

from dataclasses import dataclass, replace

from shared_types.adjudication import ImprovisedTemplateId
from shared_types.capabilities import (
    ActiveEffectDefinition,
    AttackBonusSource,
    AttackExecutionKind,
    AttackRollGateEffect,
    CapabilityDefinition,
    CapabilityKind,
    ConditionEffectDef,
    CreateTerrainEffectDef,
    DamageEffectDef,
    DiceModifierSpec,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    HealingBonusSource,
    HealingEffectDef,
    SaveDcSource,
    SaveGateEffect,
    StartActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetingSpec,
)
from shared_types.conditions import ConditionType
from shared_types.encounter_models import AttackUsageKind, MonsterRecord, RuntimeActorState, RuntimeCapabilityState
from shared_types.models import Ability, CharacterRecord, ItemRecord
from shared_types.rest import RestRecoveryMode, RestRecoveryRule, RestRecoverySpec


@dataclass(frozen=True)
class StarterContentEntry:
    option_id: str
    name: str
    source: str
    mechanic_family: str
    note: str = ''


STARTER_CONTENT_REGISTRY: tuple[StarterContentEntry, ...] = (
    StarterContentEntry('second-wind', 'Second Wind', 'XPHB', 'class-feature', 'bonus-action healing; limited use'),
    StarterContentEntry('rage', 'Rage', 'XPHB', 'class-feature', 'bonus-action self-buff; limited use'),
    StarterContentEntry('thaumaturge', 'Thaumaturge', 'XPHB', 'class-feature', 'passive skill modifier'),
    StarterContentEntry('unarmored-defense', 'Unarmored Defense', 'XPHB', 'class-feature', 'passive armor class modifier'),
    StarterContentEntry('potion-of-healing', 'Potion of Healing', 'XDMG', 'item', 'consumable healing'),
    StarterContentEntry('acid', 'Acid', 'XPHB', 'item', 'thrown damage item'),
    StarterContentEntry('ball-bearings', 'Ball Bearings', 'XPHB', 'item', 'battlefield hazard item'),
    StarterContentEntry('ghoul-claw', 'Ghoul Claw', 'XMM', 'monster-ability', 'attack plus save rider'),
    StarterContentEntry('giant-spider-web', 'Giant Spider Web', 'XMM', 'monster-ability', 'save rider; recharge'),
)


_SKILL_ABILITY_MAP = {
    'Arcana': Ability.INT,
    'Religion': Ability.INT,
}


def _uses_by_level(level: int, table: tuple[tuple[int, int], ...]) -> int:
    uses = table[0][1]
    for threshold, value in table:
        if level >= threshold:
            uses = value
    return uses


_SECOND_WIND_USES = ((1, 2), (4, 3), (10, 4))
_RAGE_USES = ((1, 2), (3, 3), (6, 4), (12, 5), (17, 6))
_RAGE_DAMAGE = ((1, 2), (9, 3), (16, 4))


_SHORT_PLUS_ONE_LONG_FULL = RestRecoverySpec(
    short_rest=RestRecoveryRule(mode=RestRecoveryMode.FIXED, amount=1),
    long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL),
)



def _runtime_capability(
    *,
    option_id: str,
    name: str,
    source: str,
    kind: CapabilityKind,
    action_cost: str,
    remaining_uses: int | None,
    capability: CapabilityDefinition,
    source_record_id: str | None = None,
    recharge_min_roll: int | None = None,
    rest_recovery: RestRecoverySpec | None = None,
) -> RuntimeCapabilityState:
    return RuntimeCapabilityState(
        option_id=option_id,
        name=name,
        source=source,
        kind=kind,
        action_cost=action_cost,
        remaining_uses=remaining_uses,
        capability=capability,
        source_record_id=source_record_id,
        recharge_min_roll=recharge_min_roll,
        max_uses=remaining_uses,
        rest_recovery=(rest_recovery or RestRecoverySpec()),
    )


def ensure_special_spell_items(item_catalog: dict[str, ItemRecord]) -> None:
    if 'goodberry' not in item_catalog:
        item_catalog['goodberry'] = ItemRecord(
            record_id='goodberry',
            name='Goodberry',
            source='XPHB',
            edition='2024',
            official=True,
            homebrew=False,
            cost_cp=0,
            weight_lb=0,
            is_magical=True,
            tags=('food', 'magical', 'consumable', 'goodberry'),
        )
    if 'spell-incense' not in item_catalog:
        item_catalog['spell-incense'] = ItemRecord(
            record_id='spell-incense',
            name='Incense',
            source='XPHB',
            edition='2024',
            official=True,
            homebrew=False,
            cost_cp=1000,
            weight_lb=0,
            is_magical=False,
            tags=('material-component', 'incense'),
        )


def build_item_capability(item: ItemRecord, *, quantity: int) -> RuntimeCapabilityState | None:
    if quantity <= 0:
        return None
    if item.name == 'Potion of Healing':
        capability = CapabilityDefinition(
            capability_id='potion-of-healing',
            name='Potion of Healing',
            kind=CapabilityKind.ITEM,
            source=item.source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=HealingEffectDef(dice_count=2, die_faces=4, bonus=2),
        )
        return _runtime_capability(
            option_id=item.record_id,
            name=item.name,
            source=item.source,
            kind=CapabilityKind.ITEM,
            action_cost='bonus',
            remaining_uses=quantity,
            capability=capability,
            source_record_id=item.record_id,
        )
    if item.name == 'Acid':
        capability = CapabilityDefinition(
            capability_id='acid',
            name='Acid',
            kind=CapabilityKind.ITEM,
            source=item.source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=20,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_WEAPON,
                attack_bonus_source=AttackBonusSource.ACTOR_ABILITY_MODIFIER,
                attack_ability=Ability.DEX,
                include_proficiency=False,
                range_ft=20,
                on_hit=(DamageEffectDef(dice_count=2, die_faces=6, bonus=0, damage_type='acid'),),
            ),
        )
        return _runtime_capability(
            option_id=item.record_id,
            name=item.name,
            source=item.source,
            kind=CapabilityKind.ITEM,
            action_cost='action',
            remaining_uses=quantity,
            capability=capability,
            source_record_id=item.record_id,
        )
    if item.name == 'Ball Bearings':
        capability = CapabilityDefinition(
            capability_id='ball-bearings',
            name='Ball Bearings',
            kind=CapabilityKind.ITEM,
            source=item.source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=5,
                affinity=TargetAffinity.ANY,
                point_must_be_visible=True,
            ),
            effect=CreateTerrainEffectDef(template_id=ImprovisedTemplateId.BALL_BEARINGS_PATCH.value),
        )
        return _runtime_capability(
            option_id=item.record_id,
            name=item.name,
            source=item.source,
            kind=CapabilityKind.ITEM,
            action_cost='action',
            remaining_uses=quantity,
            capability=capability,
            source_record_id=item.record_id,
        )
    if item.name == 'Goodberry':
        capability = CapabilityDefinition(
            capability_id='goodberry',
            name='Goodberry',
            kind=CapabilityKind.ITEM,
            source=item.source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=False,
            ),
            effect=HealingEffectDef(dice_count=0, die_faces=0, bonus=1),
        )
        return _runtime_capability(
            option_id=item.record_id,
            name=item.name,
            source=item.source,
            kind=CapabilityKind.ITEM,
            action_cost='bonus',
            remaining_uses=quantity,
            capability=capability,
            source_record_id=item.record_id,
        )
    return None



def _default_skill_total(actor: RuntimeActorState, *, skill_name: str) -> int:
    ability = _SKILL_ABILITY_MAP[skill_name]
    return actor.skill_bonuses.get(skill_name, actor.ability_modifiers[ability])



def _has_class_feature(record: CharacterRecord, feature_name: str) -> bool:
    return feature_name in record.class_feature_names



def _selected_proficiency_name(record: CharacterRecord, record_id: str) -> str:
    for selection in record.proficiency_selections:
        if selection.record_id == record_id:
            return selection.name
    return record_id.replace('-', ' ').title()



def apply_player_passive_features(actor: RuntimeActorState, record: CharacterRecord, item_catalog: dict[str, ItemRecord]) -> None:
    if _has_class_feature(record, 'Thaumaturge'):
        thaumaturge_bonus = max(1, actor.ability_modifiers[Ability.WIS])
        for skill_name in ('Arcana', 'Religion'):
            actor.skill_bonuses[skill_name] = _default_skill_total(actor, skill_name=skill_name) + thaumaturge_bonus
    for skill_id in record.expertise_skill_ids:
        skill_name = _selected_proficiency_name(record, skill_id)
        actor.skill_bonuses[skill_name] = actor.skill_bonuses.get(skill_name, 0) + actor.proficiency_bonus
    if 'Defense' in record.fighting_style_names and actor.equipped_armor_item_id is not None:
        actor.armor_class += 1
    off_hand_item = item_catalog.get(actor.off_hand_item_id) if actor.off_hand_item_id is not None else None
    off_hand_is_weapon = bool(off_hand_item and 'weapon' in off_hand_item.tags and off_hand_item.armor_category != ArmorCategory.SHIELD)
    updated_attacks = dict(actor.attacks)
    for attack_id, attack in actor.attacks.items():
        updated = attack
        if 'Archery' in record.fighting_style_names and attack.attack_usage_kind == AttackUsageKind.WEAPON_RANGED:
            updated = replace(updated, to_hit_bonus=updated.to_hit_bonus + 2)
        if (
            'Dueling' in record.fighting_style_names
            and attack.attack_usage_kind == AttackUsageKind.WEAPON_MELEE
            and attack.required_hand_count <= 1
            and not off_hand_is_weapon
        ):
            updated = replace(updated, damage_bonus=updated.damage_bonus + 2)
        updated_attacks[attack_id] = updated
    actor.attacks = updated_attacks



def build_player_capabilities(record: CharacterRecord, item_catalog: dict[str, ItemRecord]) -> dict[str, RuntimeCapabilityState]:
    capabilities: dict[str, RuntimeCapabilityState] = {}
    if record.class_id == 'fighter' and record.level >= 1:
        capability = CapabilityDefinition(
            capability_id='second-wind',
            name='Second Wind',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=HealingEffectDef(dice_count=1, die_faces=10, bonus=0, bonus_source=HealingBonusSource.ACTOR_LEVEL),
        )
        capabilities['second-wind'] = _runtime_capability(
            option_id='second-wind',
            name='Second Wind',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=_uses_by_level(record.level, _SECOND_WIND_USES),
            capability=capability,
            source_record_id='fighter-second-wind',
            rest_recovery=_SHORT_PLUS_ONE_LONG_FULL,
        )
    if record.class_id == 'barbarian' and record.level >= 1:
        rage_damage = _uses_by_level(record.level, _RAGE_DAMAGE)
        capability = CapabilityDefinition(
            capability_id='rage',
            name='Rage',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Rage',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    damage_resistances=('bludgeoning', 'piercing', 'slashing'),
                    ability_check_advantage_abilities=(Ability.STR,),
                    saving_throw_advantage_abilities=(Ability.STR,),
                    melee_attack_damage_bonus=rage_damage,
                    cannot_cast_spells=True,
                )
            ),
        )
        capabilities['rage'] = _runtime_capability(
            option_id='rage',
            name='Rage',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=_uses_by_level(record.level, _RAGE_USES),
            capability=capability,
            source_record_id='barbarian-rage',
            rest_recovery=_SHORT_PLUS_ONE_LONG_FULL,
        )
    if record.class_id == 'bard' and record.level >= 1:
        capability = CapabilityDefinition(
            capability_id='bardic-inspiration',
            name='Bardic Inspiration',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ALLY,
                requires_target_to_be_seen=True,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Bardic Inspiration',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.TARGET),
                    attack_roll_bonus=DiceModifierSpec(dice_count=1, die_faces=6),
                    saving_throw_bonus=DiceModifierSpec(dice_count=1, die_faces=6),
                    ability_check_bonus=DiceModifierSpec(dice_count=1, die_faces=6),
                    end_on_next_d20_test=True,
                )
            ),
        )
        capabilities['bardic-inspiration'] = _runtime_capability(
            option_id='bardic-inspiration',
            name='Bardic Inspiration',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=max(1, record.ability_modifiers[Ability.CHA]),
            capability=capability,
            source_record_id='bard-bardic-inspiration',
            rest_recovery=RestRecoverySpec(long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL)),
        )
    if record.class_id == 'sorcerer' and record.level >= 1:
        capability = CapabilityDefinition(
            capability_id='innate-sorcery',
            name='Innate Sorcery',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Innate Sorcery',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    spell_save_dc_bonus=1,
                    spell_attack_roll_advantage=True,
                )
            ),
        )
        capabilities['innate-sorcery'] = _runtime_capability(
            option_id='innate-sorcery',
            name='Innate Sorcery',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=2,
            capability=capability,
            source_record_id='sorcerer-innate-sorcery',
            rest_recovery=RestRecoverySpec(long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL)),
        )
    if record.class_id == 'paladin' and record.level >= 1:
        capability = CapabilityDefinition(
            capability_id='lay-on-hands',
            name='Lay on Hands',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=HealingEffectDef(dice_count=0, die_faces=0, bonus=0),
        )
        capabilities['lay-on-hands'] = _runtime_capability(
            option_id='lay-on-hands',
            name='Lay on Hands',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=None,
            capability=capability,
            source_record_id='paladin-lay-on-hands',
        )
    if record.class_id == 'wizard' and record.level >= 1:
        capability = CapabilityDefinition(
            capability_id='arcane-recovery',
            name='Arcane Recovery',
            kind=CapabilityKind.CLASS_FEATURE,
            source='XPHB',
            action_cost='special',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=HealingEffectDef(dice_count=0, die_faces=0, bonus=0),
        )
        capabilities['arcane-recovery'] = _runtime_capability(
            option_id='arcane-recovery',
            name='Arcane Recovery',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='special',
            remaining_uses=None,
            capability=capability,
            source_record_id='wizard-arcane-recovery',
        )
    for item_id, quantity in sorted(record.inventory.items()):
        if quantity <= 0:
            continue
        item = item_catalog.get(item_id)
        if item is None:
            continue
        runtime = build_item_capability(item, quantity=quantity)
        if runtime is not None:
            capabilities[item_id] = runtime
    return capabilities



def build_monster_capabilities(monster: MonsterRecord) -> dict[str, RuntimeCapabilityState]:
    capabilities: dict[str, RuntimeCapabilityState] = {}
    if monster.name == 'Ghoul' and monster.source == 'XMM':
        claw = next((attack for attack in monster.attacks if attack.name == 'Claw'), None)
        if claw is not None:
            capability = CapabilityDefinition(
                capability_id='ghoul-claw',
                name='Ghoul Claw',
                kind=CapabilityKind.MONSTER_ACTION,
                source='XMM',
                action_cost='action',
                targeting=TargetingSpec(
                    selection_kind=TargetSelectionKind.CREATURE,
                    range_ft=claw.reach_ft or 5,
                    affinity=TargetAffinity.ENEMY,
                    requires_target_to_be_seen=True,
                ),
                effect=AttackRollGateEffect(
                    attack_kind=AttackExecutionKind.MELEE_WEAPON,
                    attack_bonus_source=AttackBonusSource.FLAT,
                    flat_attack_bonus=claw.to_hit_bonus,
                    reach_ft=claw.reach_ft,
                    on_hit=(
                        DamageEffectDef(
                            dice_count=claw.damage_dice_count,
                            die_faces=claw.damage_die_faces,
                            bonus=claw.damage_bonus,
                            damage_type=claw.damage_type,
                        ),
                        SaveGateEffect(
                            ability=Ability.CON,
                            dc_source=SaveDcSource.FLAT,
                            flat_dc=10,
                            on_failure=(ConditionEffectDef(condition_type=ConditionType.PARALYZED, source_label='ghoul-claw'),),
                        ),
                    ),
                ),
            )
            capabilities['ghoul-claw'] = _runtime_capability(
                option_id='ghoul-claw',
                name='Ghoul Claw',
                source='XMM',
                kind=CapabilityKind.MONSTER_ACTION,
                action_cost='action',
                remaining_uses=None,
                capability=capability,
                source_record_id=monster.record_id,
            )
    if monster.name == 'Giant Spider' and monster.source == 'XMM':
        capability = CapabilityDefinition(
            capability_id='giant-spider-web',
            name='Web',
            kind=CapabilityKind.MONSTER_ACTION,
            source='XMM',
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
                requires_line_of_effect=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.FLAT,
                flat_dc=13,
                on_failure=(ConditionEffectDef(condition_type=ConditionType.RESTRAINED, source_label='giant-spider-web'),),
            ),
        )
        capabilities['giant-spider-web'] = _runtime_capability(
            option_id='giant-spider-web',
            name='Web',
            source='XMM',
            kind=CapabilityKind.MONSTER_ACTION,
            action_cost='action',
            remaining_uses=1,
            capability=capability,
            source_record_id=monster.record_id,
            recharge_min_roll=5,
        )
    return capabilities
