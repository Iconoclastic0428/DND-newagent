from __future__ import annotations

from collections.abc import Mapping

from shared_types.battlefield import ObscurementLevel
from shared_types.capabilities import (
    ActiveEffectDefinition,
    AlarmWardEffectDef,
    AreaOriginMode,
    AreaShape,
    AttackBonusSource,
    AttackExecutionKind,
    AttackRollGateEffect,
    CapabilityDefinition,
    CapabilityKind,
    ChainingSpellAttackEffectDef,
    ChosenDamageReductionEffectDef,
    ChosenSkillBonusEffectDef,
    ChosenWeaponEnchantmentEffectDef,
    CommandWordEffectDef,
    CompositeEffect,
    ConditionalCreatureTypeDamageEffectDef,
    CreateOrDestroyWaterEffectDef,
    ConditionEffectDef,
    DamageEffectDef,
    DashEffectDef,
    DetectionScanEffectDef,
    DetectionSenseKind,
    DiceModifierSpec,
    FriendsEffectDef,
    HeldConjurationEffectDef,
    HeldConjurationKind,
    MissingHitPointsDamageEffectDef,
    GroupSaveGateEffectDef,
    HealingBonusSource,
    HealingEffectDef,
    DurationAnchor,
    DurationSpec,
    EffectDurationType,
    ForcedMovementEffectDef,
    ForcedMovementMode,
    ForcedMovementVectorMode,
    ForcedReactionMoveEffectDef,
    InstantWeaponStrikeEffectDef,
    PersistentObserverFilter,
    InformationShareMode,
    InformationPayloadKind,
    InformationPayloadDefinition,
    IllusionTemplateId,
    OngoingTriggerDefinition,
    ParameterizedIllusionEffectDef,
    SummonCompanionEffectDef,
    SummonedCreatureDefinition,
    PurifyConsumablesEffectDef,
    ParameterizedActiveEffectDef,
    MarkTargetEffectDef,
    ItemInspectionEffectDef,
    GrantInventoryItemEffectDef,
    PersistentAreaDefinition,
    RecursiveSpellAttackEffectDef,
    RitualCastingMetadata,
    SaveDcSource,
    SaveGateEffect,
    StabilizeEffectDef,
    StartActiveEffectDef,
    TargetAffinity,
    TargetSelectionKind,
    TargetRadiusSaveEffectDef,
    TargetingSpec,
    TeleportEffectDef,
    TemporaryHitPointsEffectDef,
    TriggerActorScope,
    TriggerTiming,
    ZoneTickDefinition,
)
from shared_types.conditions import ConditionType
from shared_types.d20 import D20RollMode
from shared_types.models import Ability, slugify

from .fiveetools_loader import _canonical_name
from .tier2_spell_registry import build_tier2_spell_capability_definition


_ALL_SKILLS = (
    'Acrobatics', 'Animal Handling', 'Arcana', 'Athletics', 'Deception', 'History', 'Insight', 'Intimidation',
    'Investigation', 'Medicine', 'Nature', 'Perception', 'Performance', 'Persuasion', 'Religion', 'Sleight of Hand',
    'Stealth', 'Survival',
)

_RESISTANCE_DAMAGE_TYPES = ('acid', 'bludgeoning', 'cold', 'fire', 'lightning', 'necrotic', 'piercing', 'poison', 'radiant', 'slashing', 'thunder')
_SORCEROUS_BURST_DAMAGE_TYPES = ('acid', 'cold', 'fire', 'lightning', 'poison', 'psychic', 'thunder')


def build_spell_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    name = _canonical_name(raw_spell)
    source = str(raw_spell.get('source', '')).upper()
    capability_id = slugify(name)
    tier2_capability = build_tier2_spell_capability_definition(raw_spell)
    if tier2_capability is not None:
        return tier2_capability
    if name == 'Guidance':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ALLY,
                requires_target_to_be_seen=True,
            ),
            effect=ChosenSkillBonusEffectDef(
                name='Guidance',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                bonus=DiceModifierSpec(dice_count=1, die_faces=4),
                concentration=True,
                skill_parameter_key='skill',
                allowed_skill_names=_ALL_SKILLS,
            ),
        )
    if name == 'Elementalism':
        return None
    if name == 'Fire Bolt':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=120,
                magical=True,
                damaging=True,
                on_hit=(DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='fire', scale_with_cantrip_level=True),),
            ),
        )
    if name == 'Friends':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=10,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=FriendsEffectDef(
                name='Friends',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
        )
    if name == 'Acid Splash':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_line_of_effect=True,
                area_shape=AreaShape.SPHERE,
                area_size_ft=5,
                area_origin_mode=AreaOriginMode.SELECTED_POINT,
                point_must_be_visible=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='acid', scale_with_cantrip_level=True),),
            ),
        )
    if name == 'Blade Ward':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Blade Ward',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    incoming_attack_roll_penalty=DiceModifierSpec(dice_count=1, die_faces=4),
                )
            ),
        )
    if name == 'Burning Hands':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                range_ft=15,
                affinity=TargetAffinity.ANY,
                requires_line_of_effect=True,
                area_shape=AreaShape.CONE,
                area_size_ft=15,
                area_origin_mode=AreaOriginMode.SOURCE_DIRECTION,
                point_must_be_visible=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=3, die_faces=6, bonus=0, damage_type='fire', damage_divisor=2),),
                on_failure=(DamageEffectDef(dice_count=3, die_faces=6, bonus=0, damage_type='fire'),),
            ),
        )
    if name == 'Chill Touch':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.MELEE_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                reach_ft=5,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='necrotic', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Chill Touch',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            healing_blocked=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Dancing Lights':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=120, requires_line_of_effect=False),
            effect=HeldConjurationEffectDef(
                name='Dancing Lights',
                kind=HeldConjurationKind.DANCING_LIGHTS,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
        )
    if name == 'Druidcraft':
        return None
    if name == 'Eldritch Blast':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=120,
                magical=True,
                damaging=True,
                on_hit=(DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='force'),),
            ),
        )
    if name == 'Light':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=5,
                requires_line_of_effect=False,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Light',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    replace_existing_same_name_from_source=True,
                    persistent_areas=(
                        PersistentAreaDefinition(
                            name='Light',
                            area_shape=AreaShape.SPHERE,
                            area_size_ft=40,
                            semantic_tags=('light', 'cantrip'),
                            bright_light_radius_ft=20,
                            dim_light_radius_ft=40,
                        ),
                    ),
                )
            ),
        )
    if name == 'Mage Hand':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=30, requires_line_of_effect=False),
            effect=HeldConjurationEffectDef(
                name='Mage Hand',
                kind=HeldConjurationKind.MAGE_HAND,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
            ),
        )
    if name == 'Mending':
        return None
    if name == 'Message':
        return None
    if name == 'Mind Sliver':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.INT,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='psychic', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Mind Sliver',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            next_saving_throw_penalty=DiceModifierSpec(dice_count=1, die_faces=4),
                        )
                    ),
                ),
            ),
        )
    if name == 'Minor Illusion':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=30,
                requires_line_of_effect=False,
            ),
            effect=ParameterizedIllusionEffectDef(
                name='Minor Illusion',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                concentration=False,
            ),
        )
    if name == 'Prestidigitation':
        return None
    if name == 'Poison Spray':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=30,
                magical=True,
                damaging=True,
                on_hit=(DamageEffectDef(dice_count=1, die_faces=12, bonus=0, damage_type='poison', scale_with_cantrip_level=True),),
            ),
        )
    if name == 'Produce Flame':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus-action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=HeldConjurationEffectDef(
                name='Produce Flame',
                kind=HeldConjurationKind.PRODUCE_FLAME,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                scale_with_cantrip_level=True,
            ),
        )
    if name == 'Resistance':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ALLY,
                requires_target_to_be_seen=True,
            ),
            effect=ChosenDamageReductionEffectDef(
                name='Resistance',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                reduction=DiceModifierSpec(dice_count=1, die_faces=4),
                concentration=True,
                allowed_damage_types=_RESISTANCE_DAMAGE_TYPES,
            ),
        )
    if name == 'Ray of Frost':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=60,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=8, bonus=0, damage_type='cold', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Ray of Frost',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_START_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            speed_penalty_ft=10,
                        )
                    ),
                ),
            ),
        )
    if name == 'Shillelagh':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus-action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=ChosenWeaponEnchantmentEffectDef(
                name='Shillelagh',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                allowed_name_fragments=('club', 'quarterstaff', 'staff'),
                requires_weapon=True,
                requires_melee=True,
                requires_held=True,
                scaled_damage_tiers=((1, 1, 8), (5, 1, 10), (11, 1, 12), (17, 2, 6)),
                damage_type_parameter_key='damage-type',
                allowed_damage_types=('force',),
                end_when_item_not_carried=True,
            ),
        )
    if name == 'Sorcerous Burst':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=RecursiveSpellAttackEffectDef(
                name='Sorcerous Burst',
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=120,
                damage_die_faces=8,
                allowed_damage_types=_SORCEROUS_BURST_DAMAGE_TYPES,
                scale_with_cantrip_level=True,
            ),
        )
    if name == 'Shocking Grasp':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.MELEE_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                reach_ft=5,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=8, bonus=0, damage_type='lightning', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Shocking Grasp',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_START_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            blocks_opportunity_attacks=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Spare the Dying':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=15,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=StabilizeEffectDef(),
        )
    if name == 'Starry Wisp':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=60,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=8, bonus=0, damage_type='radiant', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Starry Wisp',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            suppress_invisible_benefits=True,
                            dim_light_radius_ft=10,
                        )
                    ),
                ),
            ),
        )
    if name == 'Thaumaturgy':
        return None
    if name == 'Thorn Whip':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=30,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='piercing', scale_with_cantrip_level=True),
                    ForcedMovementEffectDef(mode=ForcedMovementMode.PULL, distance_ft=10, vector_mode=ForcedMovementVectorMode.TOWARD_SOURCE),
                ),
            ),
        )
    if name == 'Thunderclap':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                affinity=TargetAffinity.ENEMY,
                area_shape=AreaShape.SPHERE,
                area_size_ft=5,
                area_origin_mode=AreaOriginMode.SELF,
            ),
            effect=SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='thunder', scale_with_cantrip_level=True),),
            ),
        )
    if name == 'Toll the Dead':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(MissingHitPointsDamageEffectDef(dice_count=1, undamaged_die_faces=8, damaged_die_faces=12, bonus=0, damage_type='necrotic', scale_with_cantrip_level=True),),
            ),
        )
    if name == 'True Strike':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=InstantWeaponStrikeEffectDef(
                name='True Strike',
                damage_type_parameter_key='damage-type',
                allowed_damage_types=('radiant',),
                requires_proficiency=True,
                scale_with_cantrip_level=True,
                scaled_bonus_damage_die_faces=6,
                scaled_bonus_damage_type='radiant',
            ),
        )
    if name == 'Vicious Mockery':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='psychic', scale_with_cantrip_level=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Vicious Mockery',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            next_attack_roll_disadvantage=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Word of Radiance':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
                area_shape=AreaShape.SPHERE,
                area_size_ft=5,
                area_origin_mode=AreaOriginMode.SELF,
            ),
            effect=SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='radiant'),),
            ),
        )
    if name == 'Sacred Flame':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(DamageEffectDef(dice_count=1, die_faces=8, bonus=0, damage_type='radiant', scale_with_cantrip_level=True),),
            ),
        )

    if name == 'Arms of Hadar':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                affinity=TargetAffinity.ANY,
                area_shape=AreaShape.SPHERE,
                area_size_ft=10,
                area_origin_mode=AreaOriginMode.SELF,
            ),
            effect=SaveGateEffect(
                ability=Ability.STR,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=2, die_faces=6, bonus=0, damage_type='necrotic', damage_divisor=2),),
                on_failure=(
                    DamageEffectDef(dice_count=2, die_faces=6, bonus=0, damage_type='necrotic'),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Arms of Hadar',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            cannot_take_reactions=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Color Spray':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                affinity=TargetAffinity.ANY,
                range_ft=15,
                area_shape=AreaShape.CONE,
                area_size_ft=15,
                area_origin_mode=AreaOriginMode.SOURCE_DIRECTION,
            ),
            effect=SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Color Spray',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            on_start=(ConditionEffectDef(condition_type=ConditionType.BLINDED),),
                        )
                    ),
                ),
            ),
        )
    if name == 'Faerie Fire':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                range_ft=60,
                affinity=TargetAffinity.ANY,
                area_shape=AreaShape.CUBE,
                area_size_ft=20,
                area_origin_mode=AreaOriginMode.SELECTED_POINT,
                point_must_be_visible=True,
            ),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Faerie Fire',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            attackers_have_advantage=True,
                            suppress_invisible_benefits=True,
                            dim_light_radius_ft=10,
                        )
                    ),
                ),
            ),
        )
    if name == 'Guiding Bolt':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=120,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=4, die_faces=6, bonus=0, damage_type='radiant'),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Guiding Bolt',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            attackers_have_advantage=True,
                            end_on_next_incoming_attack_roll=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Inflict Wounds':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=False,
            ),
            effect=SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=2, die_faces=10, bonus=0, damage_type='necrotic', damage_divisor=2),),
                on_failure=(DamageEffectDef(dice_count=2, die_faces=10, bonus=0, damage_type='necrotic'),),
            ),
        )
    if name == 'Ray of Sickness':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=60,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=2, die_faces=8, bonus=0, damage_type='poison'),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Ray of Sickness',
                            duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                            on_start=(ConditionEffectDef(condition_type=ConditionType.POISONED),),
                        )
                    ),
                ),
            ),
        )
    if name == 'Armor of Agathys':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=CompositeEffect(
                effects=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Armor of Agathys',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                            retaliatory_melee_hit_damage=DamageEffectDef(dice_count=0, die_faces=0, bonus=5, damage_type='cold', double_dice_on_critical_hit=False),
                            retaliatory_requires_temp_hit_points=True,
                        )
                    ),
                    TemporaryHitPointsEffectDef(dice_count=0, die_faces=0, bonus=5),
                )
            ),
        )
    if name == 'False Life':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=TemporaryHitPointsEffectDef(dice_count=2, die_faces=4, bonus=4),
        )
    if name == 'Bless':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=30, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True, max_targets=3),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Bless',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    attack_roll_bonus=DiceModifierSpec(dice_count=1, die_faces=4),
                    saving_throw_bonus=DiceModifierSpec(dice_count=1, die_faces=4),
                )
            ),
        )
    if name == 'Bane':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=30, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True, max_targets=3),
            effect=GroupSaveGateEffectDef(
                ability=Ability.CHA,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                failure_active_effect=ActiveEffectDefinition(
                    name='Bane',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    attack_roll_penalty=DiceModifierSpec(dice_count=1, die_faces=4),
                    saving_throw_penalty=DiceModifierSpec(dice_count=1, die_faces=4),
                ),
            ),
        )
    if name == 'Command':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    CommandWordEffectDef(
                        name='Command',
                        duration=DurationSpec(duration_type=EffectDurationType.UNTIL_END_OF_NEXT_TURN, anchor=DurationAnchor.TARGET),
                        command_parameter_key='word',
                    ),
                ),
            ),
        )
    if name == 'Compelled Duel':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=30, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Compelled Duel',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            attack_roll_disadvantage_against_other_targets_except_source=True,
                            cannot_willingly_move_beyond_source_ft=30,
                            end_if_target_out_of_range_ft=30,
                            replace_existing_same_name_from_source=True,
                        )
                    ),
                ),
            ),
        )
    if name == 'Dissonant Whispers':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=3, die_faces=6, bonus=0, damage_type='psychic', damage_divisor=2),),
                on_failure=(
                    DamageEffectDef(dice_count=3, die_faces=6, bonus=0, damage_type='psychic'),
                    ForcedReactionMoveEffectDef(),
                ),
            ),
        )
    if name == 'Chromatic Orb':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=90, affinity=TargetAffinity.ENEMY, requires_target_to_be_seen=True),
            effect=ChainingSpellAttackEffectDef(
                name='Chromatic Orb',
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=90,
                base_dice_count=3,
                damage_die_faces=8,
                allowed_damage_types=('acid', 'cold', 'fire', 'lightning', 'poison', 'thunder'),
                chain_parameter_key='jump-target',
                chain_range_ft=30,
                max_additional_targets=1,
                duplicate_threshold=2,
            ),
        )
    if name == 'Divine Favor':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Divine Favor',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    weapon_attack_bonus_damage=DamageEffectDef(dice_count=1, die_faces=4, bonus=0, damage_type='radiant'),
                )
            ),
        )
    if name == 'Ensnaring Strike':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=False,
            ),
            effect=SaveGateEffect(
                ability=Ability.STR,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                advantage_for_target_sizes=('Large', 'Huge', 'Gargantuan'),
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Ensnaring Strike',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            on_start=(ConditionEffectDef(condition_type=ConditionType.RESTRAINED),),
                            ongoing_triggers=(
                                OngoingTriggerDefinition(
                                    timing=TriggerTiming.START_OF_TURN,
                                    actor_scope=TriggerActorScope.EACH_TARGET,
                                    on_trigger=(DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='piercing'),),
                                    save_ability=Ability.STR,
                                    save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                    end_effect_on_success=True,
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    if name == 'Divine Smite':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ENEMY, requires_target_to_be_seen=False),
            effect=ConditionalCreatureTypeDamageEffectDef(
                base_damage=DamageEffectDef(dice_count=2, die_faces=8, bonus=0, damage_type='radiant'),
                bonus_damage=DamageEffectDef(dice_count=1, die_faces=8, bonus=0, damage_type='radiant'),
                creature_types=('fiend', 'undead'),
            ),
        )
    if name == 'Searing Smite':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=False,
            ),
            effect=CompositeEffect(
                effects=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='fire'),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Searing Smite',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            ongoing_triggers=(
                                OngoingTriggerDefinition(
                                    timing=TriggerTiming.START_OF_TURN,
                                    actor_scope=TriggerActorScope.EACH_TARGET,
                                    on_trigger=(DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='fire'),),
                                    save_ability=Ability.CON,
                                    save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                    end_effect_on_success=True,
                                ),
                            ),
                        )
                    ),
                )
            ),
        )
    if name == 'Entangle':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.AREA, range_ft=90, affinity=TargetAffinity.ANY, area_shape=AreaShape.CUBE, area_size_ft=20, area_origin_mode=AreaOriginMode.SELECTED_POINT, point_must_be_visible=True),
            effect=CompositeEffect(
                effects=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Entangle Area',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            persistent_areas=(
                                PersistentAreaDefinition(
                                    name='Entangle',
                                    area_shape=AreaShape.CUBE,
                                    area_size_ft=20,
                                    difficult_terrain=True,
                                ),
                            ),
                        )
                    ),
                    GroupSaveGateEffectDef(
                        ability=Ability.STR,
                        dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                        failure_active_effect=ActiveEffectDefinition(
                            name='Entangle Restrained',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            end_when_source_effect_name_missing='Entangle Area',
                            on_start=(ConditionEffectDef(condition_type=ConditionType.RESTRAINED),),
                        ),
                    ),
                )
            ),
        )
    if name == 'Fog Cloud':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.AREA, range_ft=120, affinity=TargetAffinity.ANY, area_shape=AreaShape.SPHERE, area_size_ft=20, area_origin_mode=AreaOriginMode.SELECTED_POINT, point_must_be_visible=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Fog Cloud',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    persistent_areas=(
                        PersistentAreaDefinition(
                            name='Fog Cloud',
                            area_shape=AreaShape.SPHERE,
                            area_size_ft=20,
                            blocks_vision=True,
                            obscurement_level=ObscurementLevel.HEAVY,
                        ),
                    ),
                )
            ),
        )
    if name == 'Thunderous Smite':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=False,
            ),
            effect=CompositeEffect(
                effects=(
                    DamageEffectDef(dice_count=2, die_faces=6, bonus=0, damage_type='thunder'),
                    SaveGateEffect(
                        ability=Ability.STR,
                        dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                        on_failure=(
                            ForcedMovementEffectDef(
                                mode=ForcedMovementMode.PUSH,
                                distance_ft=10,
                                vector_mode=ForcedMovementVectorMode.AWAY_FROM_SOURCE,
                            ),
                            ConditionEffectDef(condition_type=ConditionType.PRONE),
                        ),
                    ),
                )
            ),
        )
    if name == 'Hail of Thorns':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.AREA, affinity=TargetAffinity.ANY, area_shape=AreaShape.SPHERE, area_size_ft=5, area_origin_mode=AreaOriginMode.TARGET, max_targets=1),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='piercing', damage_divisor=2),),
                on_failure=(DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='piercing'),),
            ),
        )
    if name == 'Hellish Rebuke':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='reaction',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, affinity=TargetAffinity.ENEMY, requires_target_to_be_seen=True),
            effect=SaveGateEffect(
                ability=Ability.DEX,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=2, die_faces=10, bonus=0, damage_type='fire', damage_divisor=2),),
                on_failure=(DamageEffectDef(dice_count=2, die_faces=10, bonus=0, damage_type='fire'),),
            ),
        )
    if name == 'Wrathful Smite':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=False,
            ),
            effect=CompositeEffect(
                effects=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='psychic'),
                    SaveGateEffect(
                        ability=Ability.WIS,
                        dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                        on_failure=(
                            StartActiveEffectDef(
                                active_effect=ActiveEffectDefinition(
                                    name='Wrathful Smite',
                                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                                    on_start=(ConditionEffectDef(condition_type=ConditionType.FRIGHTENED),),
                                    ongoing_triggers=(
                                        OngoingTriggerDefinition(
                                            timing=TriggerTiming.END_OF_TURN,
                                            actor_scope=TriggerActorScope.EACH_TARGET,
                                            save_ability=Ability.WIS,
                                            save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                            end_effect_on_success=True,
                                        ),
                                    ),
                                )
                            ),
                        ),
                    ),
                )
            ),
        )
    if name == 'Heroism':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ALLY, requires_target_to_be_seen=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Heroism',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    granted_condition_immunities=(ConditionType.FRIGHTENED,),
                    start_of_turn_temp_hit_points_bonus_source=HealingBonusSource.ACTOR_SPELLCASTING_MODIFIER,
                    ongoing_triggers=(
                        OngoingTriggerDefinition(timing=TriggerTiming.START_OF_TURN, actor_scope=TriggerActorScope.EACH_TARGET),
                    ),
                )
            ),
        )
    if name == 'Jump':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ALLY, requires_target_to_be_seen=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Jump',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                    jump_replacement_distance_ft=30,
                    jump_replacement_movement_cost_ft=10,
                )
            ),
        )
    if name == 'Expeditious Retreat':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=CompositeEffect(
                effects=(
                    DashEffectDef(use_bonus_action_speed=True),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Expeditious Retreat',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            replace_existing_same_name_from_source=True,
                            can_dash_as_bonus_action=True,
                        )
                    ),
                )
            ),
        )
    if name == 'Longstrider':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Longstrider',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    speed_bonus_ft=10,
                )
            ),
        )
    if name == 'Mage Armor':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ALLY, requires_target_to_be_seen=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Mage Armor',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=4800, anchor=DurationAnchor.SOURCE),
                    armor_class_base_override=13,
                    armor_class_base_add_dex_modifier=True,
                    end_when_armor_equipped=True,
                )
            ),
        )
    if name == 'Alarm':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=30, requires_line_of_effect=False, point_must_be_visible=True),
            effect=AlarmWardEffectDef(
                name='Alarm',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=4800, anchor=DurationAnchor.SOURCE),
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Comprehend Languages':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Comprehend Languages',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    understand_all_languages=True,
                    replace_existing_same_name_from_source=True,
                )
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Detect Magic':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=DetectionScanEffectDef(
                name='Detect Magic',
                sense_kind=DetectionSenseKind.MAGIC,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Detect Poison and Disease':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=DetectionScanEffectDef(
                name='Detect Poison and Disease',
                sense_kind=DetectionSenseKind.POISON_AND_DISEASE,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Detect Evil and Good':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=DetectionScanEffectDef(
                name='Detect Evil and Good',
                sense_kind=DetectionSenseKind.EVIL_AND_GOOD,
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
        )
    if name == 'Feather Fall':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='reaction',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True, max_targets=5),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Feather Fall',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.TARGET),
                    fall_speed_override_ft=60,
                    prevent_falling_damage=True,
                    replace_existing_same_name_from_source=True,
                )
            ),
        )
    if name == 'Sleep':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.AREA, range_ft=60, affinity=TargetAffinity.ANY, area_shape=AreaShape.SPHERE, area_size_ft=5, area_origin_mode=AreaOriginMode.SELECTED_POINT, point_must_be_visible=True),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Sleep (Drowsy)',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            speed_override_ft=0,
                            on_start=(ConditionEffectDef(condition_type=ConditionType.INCAPACITATED),),
                            ongoing_triggers=(
                                OngoingTriggerDefinition(
                                    timing=TriggerTiming.END_OF_TURN,
                                    actor_scope=TriggerActorScope.EACH_TARGET,
                                    save_ability=Ability.WIS,
                                    save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                    on_failure=(
                                        StartActiveEffectDef(
                                            active_effect=ActiveEffectDefinition(
                                                name='Sleep',
                                                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                                                concentration=True,
                                                on_start=(ConditionEffectDef(condition_type=ConditionType.UNCONSCIOUS),),
                                            )
                                        ),
                                    ),
                                    end_effect_on_success=True,
                                    end_effect_on_failure=True,
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    if name == 'Speak with Animals':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Speak with Animals',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                    can_communicate_with_beasts=True,
                    replace_existing_same_name_from_source=True,
                )
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == "Tasha's Hideous Laughter":
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=30, affinity=TargetAffinity.ANY, requires_target_to_be_seen=True),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name="Tasha's Hideous Laughter",
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            on_start=(ConditionEffectDef(condition_type=ConditionType.PRONE), ConditionEffectDef(condition_type=ConditionType.INCAPACITATED)),
                            ongoing_triggers=(
                                OngoingTriggerDefinition(
                                    timing=TriggerTiming.END_OF_TURN,
                                    actor_scope=TriggerActorScope.EACH_TARGET,
                                    save_ability=Ability.WIS,
                                    save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                    end_effect_on_success=True,
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    if name == 'Protection from Evil and Good':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=5, affinity=TargetAffinity.ALLY, requires_target_to_be_seen=True),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Protection from Evil and Good',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    protected_from_creature_types=('aberration', 'celestial', 'elemental', 'fey', 'fiend', 'undead'),
                    protected_condition_types=(ConditionType.CHARMED, ConditionType.FRIGHTENED),
                )
            ),
        )
    if name == 'Witch Bolt':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE, range_ft=60, affinity=TargetAffinity.ENEMY, requires_target_to_be_seen=True),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.RANGED_SPELL,
                attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                range_ft=60,
                magical=True,
                damaging=True,
                on_hit=(
                    DamageEffectDef(dice_count=2, die_faces=12, bonus=0, damage_type='lightning'),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Witch Bolt',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            end_if_target_out_of_range_ft=60,
                            end_if_target_has_total_cover=True,
                        )
                    ),
                ),
                on_miss=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Witch Bolt',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
                            end_if_target_out_of_range_ft=60,
                            end_if_target_has_total_cover=True,
                        )
                    ),
                ),
            ),
        )

    if name == 'Thunderwave':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                area_shape=AreaShape.CUBE,
                area_size_ft=15,
                area_origin_mode=AreaOriginMode.SOURCE_DIRECTION,
            ),
            effect=SaveGateEffect(
                ability=Ability.CON,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_success=(DamageEffectDef(dice_count=2, die_faces=8, bonus=0, damage_type='thunder', damage_divisor=2),),
                on_failure=(
                    DamageEffectDef(dice_count=2, die_faces=8, bonus=0, damage_type='thunder'),
                    ForcedMovementEffectDef(mode=ForcedMovementMode.PUSH, distance_ft=10, vector_mode=ForcedMovementVectorMode.AWAY_FROM_SOURCE),
                ),
            ),
        )
    if name == 'Hold Person':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
                creature_type_filter='humanoid',
            ),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Hold Person',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            concentration=True,
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
                        )
                    ),
                ),
            ),
        )
    if name == 'Magic Missile':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=120,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=CompositeEffect(effects=(DamageEffectDef(dice_count=3, die_faces=4, bonus=3, damage_type='force'),)),
        )
    if name == 'Cure Wounds':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=False,
            ),
            effect=HealingEffectDef(
                dice_count=2,
                die_faces=8,
                bonus=0,
                bonus_source=HealingBonusSource.ACTOR_SPELLCASTING_MODIFIER,
            ),
        )
    if name == 'Healing Word':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=HealingEffectDef(
                dice_count=2,
                die_faces=4,
                bonus=0,
                bonus_source=HealingBonusSource.ACTOR_SPELLCASTING_MODIFIER,
            ),
        )
    if name == 'Misty Step':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
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
    if name == 'Invisibility':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Invisibility',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.TARGET),
                    concentration=True,
                    replace_existing_same_name_from_source=True,
                    end_when_target_attacks_or_harmful_casts=True,
                    on_start=(ConditionEffectDef(condition_type=ConditionType.INVISIBLE),),
                )
            ),
        )
    if name == 'Magic Weapon':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.SELF,
                affinity=TargetAffinity.SELF_ONLY,
            ),
            effect=ChosenWeaponEnchantmentEffectDef(
                name='Magic Weapon',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                concentration=False,
                item_parameter_key='item',
                requires_weapon=True,
                requires_melee=False,
                requires_held=False,
                enchanted_attack_bonus=1,
                enchanted_damage_bonus=1,
                end_when_item_not_carried=False,
            ),
        )
    if name == 'Shield':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='reaction',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Shield',
                    duration=DurationSpec(duration_type=EffectDurationType.UNTIL_START_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                    armor_class_bonus=5,
                )
            ),
        )
    if name == 'Shield of Faith':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Shield of Faith',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    armor_class_bonus=2,
                )
            ),
        )

    if name == 'Animal Friendship':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
                creature_type_filter='beast',
            ),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Animal Friendship',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=14400, anchor=DurationAnchor.SOURCE),
                            replace_existing_same_name_from_source=True,
                            end_on_damage_from_source_side=True,
                            on_start=(ConditionEffectDef(condition_type=ConditionType.CHARMED),),
                            information_payloads=(
                                InformationPayloadDefinition(
                                    kind=InformationPayloadKind.DETECTION,
                                    title='Animal Friendship',
                                    detail='The beast is charmed by the caster for the spell duration unless the caster or an ally damages it.',
                                    tags=('animal-friendship', 'charmed', 'beast'),
                                    observer_filter=PersistentObserverFilter(),
                                    share_mode=InformationShareMode.DM_ONLY,
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    if name == 'Charm Person':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
                creature_type_filter='humanoid',
            ),
            effect=SaveGateEffect(
                ability=Ability.WIS,
                dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                advantage_when_target_hostile_to_source=True,
                on_failure=(
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Charm Person',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                            replace_existing_same_name_from_source=True,
                            end_on_damage_from_source_side=True,
                            on_start=(ConditionEffectDef(condition_type=ConditionType.CHARMED),),
                            information_payloads=(
                                InformationPayloadDefinition(
                                    kind=InformationPayloadKind.DETECTION,
                                    title='Charm Person',
                                    detail='The humanoid is charmed by the caster and regards them as friendly until the spell ends or the caster or allies damage it. When the spell ends, the target knows it was charmed.',
                                    tags=('charm-person', 'charmed', 'friendly'),
                                    observer_filter=PersistentObserverFilter(),
                                    share_mode=InformationShareMode.DM_ONLY,
                                ),
                            ),
                        )
                    ),
                ),
            ),
        )
    if name == 'Create or Destroy Water':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=30,
                point_must_be_visible=True,
                requires_line_of_effect=False,
            ),
            effect=CreateOrDestroyWaterEffectDef(),
        )
    if name == 'Disguise Self':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=ParameterizedActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Disguise Self',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    replace_existing_same_name_from_source=True,
                ),
                metadata_parameter_keys=('form', 'description'),
            ),
        )
    if name == 'Find Familiar':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=10,
                requires_line_of_effect=False,
                point_must_be_visible=True,
                requires_unoccupied_point=True,
            ),
            effect=SummonCompanionEffectDef(
                name='Find Familiar',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=14400, anchor=DurationAnchor.SOURCE),
                summon_kind='familiar',
                form_parameter_key='form',
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Goodberry':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=GrantInventoryItemEffectDef(item_id='goodberry', quantity=10),
        )
    if name == 'Grease':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.AREA,
                range_ft=60,
                affinity=TargetAffinity.ANY,
                area_shape=AreaShape.CUBE,
                area_size_ft=10,
                area_origin_mode=AreaOriginMode.SELECTED_POINT,
                point_must_be_visible=True,
                requires_line_of_effect=False,
            ),
            effect=CompositeEffect(
                effects=(
                    SaveGateEffect(
                        ability=Ability.DEX,
                        dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                        on_failure=(ConditionEffectDef(condition_type=ConditionType.PRONE),),
                    ),
                    StartActiveEffectDef(
                        active_effect=ActiveEffectDefinition(
                            name='Grease',
                            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE),
                            replace_existing_same_name_from_source=True,
                            persistent_areas=(
                                PersistentAreaDefinition(
                                    name='Grease',
                                    area_shape=AreaShape.CUBE,
                                    area_size_ft=10,
                                    semantic_tags=('grease', 'difficult-terrain'),
                                    difficult_terrain=True,
                                    entry_effects=(
                                        SaveGateEffect(
                                            ability=Ability.DEX,
                                            dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                            on_failure=(ConditionEffectDef(condition_type=ConditionType.PRONE),),
                                        ),
                                    ),
                                    tick_effects=(
                                        ZoneTickDefinition(
                                            timing=TriggerTiming.END_OF_TURN,
                                            effects=(
                                                SaveGateEffect(
                                                    ability=Ability.DEX,
                                                    dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                                                    on_failure=(ConditionEffectDef(condition_type=ConditionType.PRONE),),
                                                ),
                                            ),
                                            applies_to_entering_actor=True,
                                        ),
                                    ),
                                ),
                            ),
                        )
                    ),
                )
            ),
        )
    if name == 'Hex':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=90,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=MarkTargetEffectDef(
                name='Hex',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                concentration=True,
                bonus_damage=DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='necrotic'),
                ability_parameter_key='ability',
                allowed_abilities=(Ability.STR, Ability.DEX, Ability.CON, Ability.INT, Ability.WIS, Ability.CHA),
            ),
        )
    if name == "Hunter's Mark":
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=90,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=MarkTargetEffectDef(
                name="Hunter's Mark",
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                concentration=True,
                bonus_damage=DamageEffectDef(dice_count=1, die_faces=6, bonus=0, damage_type='force'),
                track_skill_names=('Perception', 'Survival'),
            ),
        )
    if name == 'Ice Knife':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=60,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=CompositeEffect(
                effects=(
                    AttackRollGateEffect(
                        attack_kind=AttackExecutionKind.RANGED_SPELL,
                        attack_bonus_source=AttackBonusSource.ACTOR_SPELL_ATTACK,
                        range_ft=60,
                        magical=True,
                        damaging=True,
                        on_hit=(DamageEffectDef(dice_count=1, die_faces=10, bonus=0, damage_type='piercing'),),
                    ),
                    TargetRadiusSaveEffectDef(
                        radius_ft=5,
                        ability=Ability.DEX,
                        dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                        include_primary_target=True,
                        on_failure=(DamageEffectDef(dice_count=2, die_faces=6, bonus=0, damage_type='cold'),),
                    ),
                )
            ),
        )
    if name == 'Identify':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=ItemInspectionEffectDef(name='Identify', item_parameter_key='item', mark_identified=True),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Illusory Script':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
            effect=ParameterizedActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Illusory Script',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=144000, anchor=DurationAnchor.SOURCE),
                    replace_existing_same_name_from_source=True,
                ),
                metadata_parameter_keys=('item', 'description', 'readers'),
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Purify Food and Drink':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=10,
                point_must_be_visible=True,
                requires_line_of_effect=False,
            ),
            effect=PurifyConsumablesEffectDef(),
        )
    if name == 'Sanctuary':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='bonus',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=30,
                affinity=TargetAffinity.ANY,
                requires_target_to_be_seen=True,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Sanctuary',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.TARGET),
                    replace_existing_same_name_from_source=True,
                    incoming_hostile_targeting_save_ability=Ability.WIS,
                    incoming_hostile_targeting_save_dc_source=SaveDcSource.ACTOR_SPELL_SAVE_DC,
                    end_when_target_attacks_or_harmful_casts=True,
                )
            ),
        )
    if name == 'Silent Image':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=60,
                requires_line_of_effect=False,
                point_must_be_visible=True,
            ),
            effect=ParameterizedIllusionEffectDef(
                name='Silent Image',
                duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                concentration=True,
                allowed_templates=(
                    IllusionTemplateId.MINOR_VISUAL_OBJECT,
                    IllusionTemplateId.MINOR_VISUAL_BARRIER,
                    IllusionTemplateId.MINOR_VISUAL_DOOR,
                    IllusionTemplateId.MINOR_VISUAL_SIGN_OR_SIGIL,
                    IllusionTemplateId.MEDIUM_SCENE_DRESSING_ILLUSION,
                    IllusionTemplateId.ILLUSIONARY_LARGE_FACADE,
                ),
            ),
        )
    if name == "Tenser's Floating Disk":
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=30,
                requires_line_of_effect=False,
                point_must_be_visible=True,
                requires_unoccupied_point=True,
            ),
            effect=ParameterizedActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name="Tenser's Floating Disk",
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    replace_existing_same_name_from_source=True,
                    summoned_creatures=(
                        SummonedCreatureDefinition(
                            summon_name="Tenser's Floating Disk",
                            statblock_reference='tenser-floating-disk',
                            semantic_tags=('floating-disk',),
                        ),
                    ),
                ),
                metadata_parameter_keys=('cargo', 'description'),
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )
    if name == 'Unseen Servant':
        return CapabilityDefinition(
            capability_id=capability_id,
            name=name,
            kind=CapabilityKind.SPELL,
            source=source,
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=60,
                requires_line_of_effect=False,
                point_must_be_visible=True,
                requires_unoccupied_point=True,
            ),
            effect=ParameterizedActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Unseen Servant',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=600, anchor=DurationAnchor.SOURCE),
                    replace_existing_same_name_from_source=True,
                    summoned_creatures=(
                        SummonedCreatureDefinition(
                            summon_name='Unseen Servant',
                            statblock_reference='unseen-servant',
                            semantic_tags=('unseen-servant',),
                        ),
                    ),
                ),
                metadata_parameter_keys=('description',),
            ),
            ritual_casting=RitualCastingMetadata(can_cast_as_ritual=True),
        )

    return None






