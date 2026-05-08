from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .battlefield import CoverLevel, ObscurementLevel
from .conditions import ConditionType
from .d20 import D20RollMode
from .models import Ability


class CapabilityKind(str, Enum):
    ATTACK = 'attack'
    SPELL = 'spell'
    CLASS_FEATURE = 'class-feature'
    SPECIES_TRAIT = 'species-trait'
    FEAT = 'feat'
    ITEM = 'item'
    MONSTER_ACTION = 'monster-action'
    MONSTER_TRAIT = 'monster-trait'


class TargetSelectionKind(str, Enum):
    SELF = 'self'
    CREATURE = 'creature'
    POINT = 'point'
    AREA = 'area'


class TargetAffinity(str, Enum):
    ANY = 'any'
    SELF_ONLY = 'self-only'
    ALLY = 'ally'
    ENEMY = 'enemy'


class AreaShape(str, Enum):
    LINE = 'line'
    CONE = 'cone'
    CUBE = 'cube'
    SPHERE = 'sphere'


class AreaOriginMode(str, Enum):
    SELF = 'self'
    SELECTED_POINT = 'selected-point'
    SOURCE_DIRECTION = 'source-direction'
    TARGET = 'target'


class AttackExecutionKind(str, Enum):
    MELEE_WEAPON = 'melee-weapon'
    RANGED_WEAPON = 'ranged-weapon'
    MELEE_SPELL = 'melee-spell'
    RANGED_SPELL = 'ranged-spell'


class AttackBonusSource(str, Enum):
    ACTOR_SPELL_ATTACK = 'actor-spell-attack'
    ACTOR_ABILITY_MODIFIER = 'actor-ability-modifier'
    FLAT = 'flat'


class HealingBonusSource(str, Enum):
    FLAT = 'flat'
    ACTOR_LEVEL = 'actor-level'
    ACTOR_SPELLCASTING_MODIFIER = 'actor-spellcasting-modifier'


class SaveDcSource(str, Enum):
    ACTOR_SPELL_SAVE_DC = 'actor-spell-save-dc'
    FLAT = 'flat'


class EffectDurationType(str, Enum):
    INSTANT = 'instant'
    UNTIL_START_OF_NEXT_TURN = 'until-start-of-next-turn'
    UNTIL_END_OF_NEXT_TURN = 'until-end-of-next-turn'
    ROUNDS = 'rounds'


class DurationAnchor(str, Enum):
    SOURCE = 'source'
    TARGET = 'target'


class TriggerTiming(str, Enum):
    START_OF_TURN = 'start-of-turn'
    END_OF_TURN = 'end-of-turn'


class TriggerActorScope(str, Enum):
    SOURCE = 'source'
    EACH_TARGET = 'each-target'


class ForcedMovementMode(str, Enum):
    PUSH = 'push'
    PULL = 'pull'
    REPOSITION = 'reposition'


class ForcedMovementVectorMode(str, Enum):
    AWAY_FROM_SOURCE = 'away-from-source'
    TOWARD_SOURCE = 'toward-source'
    FIXED_VECTOR = 'fixed-vector'


class PersistentObserverMode(str, Enum):
    ALL_VALID_OBSERVERS = 'all-valid-observers'
    SELECTED_OBSERVERS = 'selected-observers'
    TARGETS_ONLY = 'targets-only'


class IllusionModality(str, Enum):
    VISUAL = 'visual'
    AUDITORY = 'auditory'
    MIXED = 'mixed'
    OBSERVER_SPECIFIC_OVERLAY = 'observer-specific-overlay'


class IllusionSubtype(str, Enum):
    SMALL_STATIC_VISUAL = 'small-static-visual'
    SMALL_SENSORY = 'small-sensory'
    ENVIRONMENTAL = 'environmental'
    OBSERVER_SPECIFIC = 'observer-specific'
    ANCHORED_AREA = 'anchored-area'


class IllusionRevealPolicy(str, Enum):
    ON_PHYSICAL_INTERACTION = 'on-physical-interaction'
    ON_STUDY_SUCCESS = 'on-study-success'
    ON_PASSIVE_NOTICE = 'on-passive-notice'
    ON_ANY_INTERACTION = 'on-any-interaction'


class IllusionInteractionKind(str, Enum):
    PHYSICAL_INTERACTION = 'physical-interaction'
    STUDY_SUCCESS = 'study-success'
    PASSIVE_NOTICE = 'passive-notice'


class IllusionTemplateId(str, Enum):
    MINOR_VISUAL_OBJECT = 'minor_visual_object'
    MINOR_VISUAL_BARRIER = 'minor_visual_barrier'
    MINOR_VISUAL_DOOR = 'minor_visual_door'
    MINOR_VISUAL_SIGN_OR_SIGIL = 'minor_visual_sign_or_sigil'
    MINOR_SOUND_SOURCE = 'minor_sound_source'
    MEDIUM_SCENE_DRESSING_ILLUSION = 'medium_scene_dressing_illusion'
    OBSERVER_SPECIFIC_VISUAL_OVERLAY = 'observer_specific_visual_overlay'
    ILLUSIONARY_LARGE_FACADE = 'illusionary_large_facade'


class HeldConjurationKind(str, Enum):
    DANCING_LIGHTS = 'dancing-lights'
    MAGE_HAND = 'mage-hand'
    PRODUCE_FLAME = 'produce-flame'


class InformationPayloadKind(str, Enum):
    DETECTION = 'detection'
    DIVINATION = 'divination'


class DetectionSenseKind(str, Enum):
    MAGIC = 'magic'
    POISON_AND_DISEASE = 'poison-and-disease'
    EVIL_AND_GOOD = 'evil-and-good'


class InformationShareMode(str, Enum):
    DM_ONLY = 'dm-only'
    OBSERVER_ONLY = 'observer-only'
    PARTY_BROADCAST = 'party-broadcast'


@dataclass(frozen=True)
class TargetingSpec:
    selection_kind: TargetSelectionKind
    range_ft: int | None = None
    affinity: TargetAffinity = TargetAffinity.ANY
    requires_target_to_be_seen: bool = False
    requires_line_of_effect: bool = True
    requires_unoccupied_point: bool = False
    creature_type_filter: str | None = None
    area_shape: AreaShape | None = None
    area_size_ft: int | None = None
    area_origin_mode: AreaOriginMode = AreaOriginMode.SELECTED_POINT
    point_must_be_visible: bool = False
    max_targets: int | None = 1


@dataclass(frozen=True)
class DurationSpec:
    duration_type: EffectDurationType
    rounds: int | None = None
    anchor: DurationAnchor = DurationAnchor.SOURCE


@dataclass(frozen=True)
class DiceModifierSpec:
    dice_count: int = 1
    die_faces: int = 4


class EffectDefinition:
    pass


@dataclass(frozen=True)
class CompositeEffect(EffectDefinition):
    effects: tuple[EffectDefinition, ...]


@dataclass(frozen=True)
class DamageEffectDef(EffectDefinition):
    dice_count: int
    die_faces: int
    bonus: int
    damage_type: str
    damage_divisor: int = 1
    double_dice_on_critical_hit: bool = True
    scale_with_cantrip_level: bool = False


@dataclass(frozen=True)
class MissingHitPointsDamageEffectDef(EffectDefinition):
    dice_count: int
    undamaged_die_faces: int
    damaged_die_faces: int
    bonus: int
    damage_type: str
    scale_with_cantrip_level: bool = False


@dataclass(frozen=True)
class HealingEffectDef(EffectDefinition):
    dice_count: int
    die_faces: int
    bonus: int
    bonus_source: HealingBonusSource = HealingBonusSource.FLAT


@dataclass(frozen=True)
class SpendHitDiceHealingEffectDef(EffectDefinition):
    count_parameter_key: str = 'count'
    minimum_count: int = 1
    maximum_count: int = 1
    bonus_source: HealingBonusSource = HealingBonusSource.FLAT
    apply_constitution_modifier_per_die: bool = False
    spend_all_requested_dice: bool = True
    slot_level_parameter_key: str = 'slot-level'
    base_slot_level: int = 2
    bonus_maximum_count_per_slot_level: int = 0


@dataclass(frozen=True)
class TemporaryHitPointsEffectDef(EffectDefinition):
    dice_count: int = 0
    die_faces: int = 0
    bonus: int = 0
    bonus_source: HealingBonusSource = HealingBonusSource.FLAT


@dataclass(frozen=True)
class StabilizeEffectDef(EffectDefinition):
    pass


@dataclass(frozen=True)
class ChosenSkillBonusEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    bonus: DiceModifierSpec = DiceModifierSpec()
    concentration: bool = True
    skill_parameter_key: str = 'skill'
    allowed_skill_names: tuple[str, ...] = ()

@dataclass(frozen=True)
class ChosenAbilityCheckAdvantageEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = True
    ability_parameter_key: str = 'ability'
    allowed_abilities: tuple[Ability, ...] = ()
    per_target_ability_parameter_key: str | None = None



@dataclass(frozen=True)
class ParameterizedIllusionEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = False
    template_parameter_key: str = 'template'
    label_parameter_key: str = 'label'
    description_parameter_key: str = 'description'
    allowed_templates: tuple[IllusionTemplateId, ...] = (
        IllusionTemplateId.MINOR_VISUAL_OBJECT,
        IllusionTemplateId.MINOR_VISUAL_BARRIER,
        IllusionTemplateId.MINOR_VISUAL_DOOR,
        IllusionTemplateId.MINOR_VISUAL_SIGN_OR_SIGIL,
        IllusionTemplateId.MINOR_SOUND_SOURCE,
    )


@dataclass(frozen=True)
class ParameterizedActiveEffectDef(EffectDefinition):
    active_effect: ActiveEffectDefinition
    metadata_parameter_keys: tuple[str, ...] = ()
    required_metadata_parameter_keys: tuple[str, ...] = ()
    extra_metadata: tuple[tuple[str, str], ...] = ()
    slot_level_parameter_key: str | None = None
    base_slot_level: int = 2
    bonus_max_hit_points_per_slot_level: int = 0


@dataclass(frozen=True)
class GrantInventoryItemEffectDef(EffectDefinition):
    item_id: str
    quantity: int


@dataclass(frozen=True)
class MarkTargetEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = False
    replace_existing_same_name_from_source: bool = True
    bonus_damage: DamageEffectDef | None = None
    ability_parameter_key: str | None = None
    allowed_abilities: tuple[Ability, ...] = ()
    track_skill_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class SummonCompanionEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = False
    summon_kind: str = 'familiar'
    form_parameter_key: str = 'form'


@dataclass(frozen=True)
class ItemInspectionEffectDef(EffectDefinition):
    name: str
    item_parameter_key: str = 'item'
    mark_identified: bool = False


@dataclass(frozen=True)
class CreateOrDestroyWaterEffectDef(EffectDefinition):
    mode_parameter_key: str = 'mode'
    container_parameter_key: str = 'container'
    description_parameter_key: str = 'description'


@dataclass(frozen=True)
class PurifyConsumablesEffectDef(EffectDefinition):
    pass


@dataclass(frozen=True)
class ConditionRemovalEffectDef(EffectDefinition):
    name: str
    allowed_condition_types: tuple[ConditionType, ...] = ()
    condition_parameter_key: str = 'condition'
    name: str
    allowed_condition_types: tuple[ConditionType, ...] = ()
    condition_parameter_key: str = 'condition'


@dataclass(frozen=True)
class ChosenDamageReductionEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    reduction: DiceModifierSpec = DiceModifierSpec()
    concentration: bool = True
    damage_type_parameter_key: str = 'damage-type'
    allowed_damage_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChosenWeaponEnchantmentEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = False
    item_parameter_key: str = 'item'
    allowed_item_ids: tuple[str, ...] = ()
    allowed_name_fragments: tuple[str, ...] = ()
    requires_weapon: bool = True
    requires_melee: bool = False
    requires_held: bool = True
    attack_ability: Ability | None = None
    damage_ability: Ability | None = None
    damage_dice_count: int | None = None
    damage_die_faces: int | None = None
    scaled_damage_tiers: tuple[tuple[int, int, int], ...] = ()
    damage_type_parameter_key: str | None = None
    allowed_damage_types: tuple[str, ...] = ()
    enchanted_attack_bonus: int = 0
    enchanted_damage_bonus: int = 0
    end_when_item_not_carried: bool = False
    slot_level_parameter_key: str | None = None
    base_slot_level: int = 2
    scaled_enchanted_bonus_tiers: tuple[tuple[int, int], ...] = ()
    select_item_from_target_actor: bool = False


@dataclass(frozen=True)
class InstantWeaponStrikeEffectDef(EffectDefinition):
    name: str
    item_parameter_key: str = 'item'
    damage_type_parameter_key: str | None = None
    allowed_damage_types: tuple[str, ...] = ()
    attack_ability: Ability | None = None
    damage_ability: Ability | None = None
    requires_proficiency: bool = False
    scale_with_cantrip_level: bool = False
    scaled_bonus_damage_die_faces: int | None = None
    scaled_bonus_damage_type: str | None = None


@dataclass(frozen=True)
class RecursiveSpellAttackEffectDef(EffectDefinition):
    name: str
    attack_kind: AttackExecutionKind
    attack_bonus_source: AttackBonusSource
    range_ft: int | None = None
    reach_ft: int | None = None
    magical: bool = True
    damaging: bool = True
    base_dice_count: int = 1
    damage_die_faces: int = 8
    damage_type_parameter_key: str = 'damage-type'
    allowed_damage_types: tuple[str, ...] = ()
    scale_with_cantrip_level: bool = False


@dataclass(frozen=True)
class HeldConjurationEffectDef(EffectDefinition):
    name: str
    kind: HeldConjurationKind
    duration: DurationSpec
    concentration: bool = False
    mode_parameter_key: str = 'mode'
    form_parameter_key: str = 'form'
    description_parameter_key: str = 'description'
    action_parameter_key: str = 'action'
    scale_with_cantrip_level: bool = False


@dataclass(frozen=True)
class FriendsEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    concentration: bool = True


@dataclass(frozen=True)
class DashEffectDef(EffectDefinition):
    use_bonus_action_speed: bool = False


@dataclass(frozen=True)
class CommandWordEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    command_parameter_key: str = 'word'
    allowed_commands: tuple[str, ...] = ('approach', 'drop', 'flee', 'grovel', 'halt')


@dataclass(frozen=True)
class DetectionScanEffectDef(EffectDefinition):
    name: str
    sense_kind: DetectionSenseKind
    duration: DurationSpec
    concentration: bool = False
    mode_parameter_key: str = 'mode'


@dataclass(frozen=True)
class AlarmWardEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    mode_parameter_key: str = 'mode'
    form_parameter_key: str = 'form'
    exclude_parameter_key: str = 'exclude'


@dataclass(frozen=True)
class AlarmTriggerEffectDef(EffectDefinition):
    mode: str = 'mental'


@dataclass(frozen=True)
class ForcedReactionMoveEffectDef(EffectDefinition):
    use_speed_ft: bool = True
    requires_reaction: bool = True


@dataclass(frozen=True)
class ConditionEffectDef(EffectDefinition):
    condition_type: ConditionType
    source_label: str | None = None


@dataclass(frozen=True)
class ParameterizedConditionEffectDef(EffectDefinition):
    name: str
    duration: DurationSpec
    condition_parameter_key: str = 'condition'
    allowed_condition_types: tuple[ConditionType, ...] = ()
    concentration: bool = True
    source_label: str | None = None
    replace_existing_same_name_from_source: bool = True
    ongoing_triggers: tuple[OngoingTriggerDefinition, ...] = ()
    split_targets_individually: bool = False
    concentration_anchor_name: str | None = None


@dataclass(frozen=True)
class ParameterizedDamageEffectDef(EffectDefinition):
    name: str
    base_dice_count: int
    die_faces: int
    bonus: int = 0
    damage_type: str = 'force'
    damage_divisor: int = 1
    double_dice_on_critical_hit: bool = True
    slot_level_parameter_key: str = 'slot-level'
    base_slot_level: int = 2
    bonus_dice_per_slot_level: int = 1
    bonus_die_faces_per_slot_level: int = 0
    bonus_per_slot_level: int = 0


@dataclass(frozen=True)
class ParameterizedTargetCountGateEffectDef(EffectDefinition):
    name: str
    base_target_count: int = 1
    targets_per_extra_slot_level: int = 1
    slot_level_parameter_key: str = 'slot-level'
    base_slot_level: int = 2


@dataclass(frozen=True)
class ForcedMovementEffectDef(EffectDefinition):
    mode: ForcedMovementMode
    distance_ft: int
    vector_mode: ForcedMovementVectorMode = ForcedMovementVectorMode.AWAY_FROM_SOURCE
    fixed_dx: int = 0
    fixed_dy: int = 0
    fixed_dz: int = 0


@dataclass(frozen=True)
class TeleportEffectDef(EffectDefinition):
    requires_visible_destination: bool = True
    requires_unoccupied_destination: bool = True
    requires_line_of_effect: bool = False


@dataclass(frozen=True)
class CreateTerrainEffectDef(EffectDefinition):
    template_id: str


@dataclass(frozen=True)
class AttackRollGateEffect(EffectDefinition):
    attack_kind: AttackExecutionKind
    attack_bonus_source: AttackBonusSource
    flat_attack_bonus: int = 0
    attack_ability: Ability | None = None
    include_proficiency: bool = False
    reach_ft: int | None = None
    range_ft: int | None = None
    long_range_ft: int | None = None
    magical: bool = False
    damaging: bool = True
    on_hit: tuple[EffectDefinition, ...] = ()
    on_miss: tuple[EffectDefinition, ...] = ()


@dataclass(frozen=True)
class TargetRadiusSaveEffectDef(EffectDefinition):
    radius_ft: int
    ability: Ability
    dc_source: SaveDcSource
    flat_dc: int | None = None
    on_success: tuple[EffectDefinition, ...] = ()
    on_failure: tuple[EffectDefinition, ...] = ()
    include_primary_target: bool = True


@dataclass(frozen=True)
class SaveGateEffect(EffectDefinition):
    ability: Ability
    dc_source: SaveDcSource
    flat_dc: int | None = None
    roll_mode: D20RollMode = D20RollMode.NORMAL
    advantage_for_target_sizes: tuple[str, ...] = ()
    advantage_when_target_hostile_to_source: bool = False
    on_success: tuple[EffectDefinition, ...] = ()
    on_failure: tuple[EffectDefinition, ...] = ()
    on_partial_success: tuple[EffectDefinition, ...] = ()
    partial_success_margin: int | None = None


@dataclass(frozen=True)
class GroupSaveGateEffectDef(EffectDefinition):
    ability: Ability
    dc_source: SaveDcSource
    flat_dc: int | None = None
    roll_mode: D20RollMode = D20RollMode.NORMAL
    advantage_when_target_hostile_to_source: bool = False
    on_success: tuple[EffectDefinition, ...] = ()
    on_failure: tuple[EffectDefinition, ...] = ()
    failure_active_effect: ActiveEffectDefinition | None = None
    success_active_effect: ActiveEffectDefinition | None = None


@dataclass(frozen=True)
class ConditionalCreatureTypeDamageEffectDef(EffectDefinition):
    base_damage: DamageEffectDef
    bonus_damage: DamageEffectDef | None = None
    creature_types: tuple[str, ...] = ()


@dataclass(frozen=True)
class ChainingSpellAttackEffectDef(EffectDefinition):
    name: str
    attack_kind: AttackExecutionKind
    attack_bonus_source: AttackBonusSource
    flat_attack_bonus: int = 0
    range_ft: int | None = None
    reach_ft: int | None = None
    magical: bool = True
    damaging: bool = True
    base_dice_count: int = 3
    damage_die_faces: int = 8
    damage_type_parameter_key: str = 'damage-type'
    allowed_damage_types: tuple[str, ...] = ()
    chain_parameter_key: str = 'jump-target'
    chain_range_ft: int = 30
    max_additional_targets: int = 1
    duplicate_threshold: int = 2


@dataclass(frozen=True)
class CheckGateEffect(EffectDefinition):
    ability: Ability
    skill_name: str | None
    dc_source: SaveDcSource
    flat_dc: int | None = None
    requires_sight: bool = False
    requires_hearing: bool = False
    on_success: tuple[EffectDefinition, ...] = ()
    on_failure: tuple[EffectDefinition, ...] = ()
    on_partial_success: tuple[EffectDefinition, ...] = ()
    partial_success_margin: int | None = None


@dataclass(frozen=True)
class OngoingTriggerDefinition:
    timing: TriggerTiming
    actor_scope: TriggerActorScope
    save_ability: Ability | None = None
    save_dc_source: SaveDcSource = SaveDcSource.FLAT
    flat_dc: int | None = None
    save_roll_mode: D20RollMode = D20RollMode.NORMAL
    on_trigger: tuple[EffectDefinition, ...] = ()
    on_success: tuple[EffectDefinition, ...] = ()
    on_failure: tuple[EffectDefinition, ...] = ()
    end_effect_on_success: bool = False
    end_effect_on_failure: bool = False


@dataclass(frozen=True)
class PersistentObserverFilter:
    observer_mode: PersistentObserverMode = PersistentObserverMode.ALL_VALID_OBSERVERS
    observer_actor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CreatedObjectDefinition:
    name: str
    feature_type: str
    footprint: tuple[tuple[int, int], ...] = ((0, 0),)
    bottom_offset_ft: int = 0
    top_offset_ft: int = 5
    traversable: bool = False
    occupiable: bool = False
    blocks_los: bool = False
    blocks_loe: bool = False
    cover_provided: CoverLevel = CoverLevel.NONE
    physical: bool = True
    inventory_eligible: bool = False
    interaction_allowed: bool = True
    semantic_tags: tuple[str, ...] = ()
    apparent_label: str | None = None


@dataclass(frozen=True)
class IllusionApparentProperties:
    apparent_cover: CoverLevel = CoverLevel.NONE
    apparent_blocker: bool = False
    apparent_door: bool = False
    apparent_opening: bool = False
    apparent_object_category: str | None = None


@dataclass(frozen=True)
class IllusionActualProperties:
    actual_blocker: bool = False
    actual_support: bool = False
    actual_cover: bool = False
    actual_interaction: bool = False


@dataclass(frozen=True)
class IllusionDefinition:
    template_id: IllusionTemplateId
    subtype: IllusionSubtype
    modality: IllusionModality
    display_name: str
    display_description: str
    width_ft: int = 5
    depth_ft: int = 5
    height_ft: int = 5
    semantic_tags: tuple[str, ...] = ()
    observer_filter: PersistentObserverFilter = PersistentObserverFilter()
    apparent_properties: IllusionApparentProperties = IllusionApparentProperties()
    actual_properties: IllusionActualProperties = IllusionActualProperties()
    reveal_policies: tuple[IllusionRevealPolicy, ...] = (IllusionRevealPolicy.ON_STUDY_SUCCESS,)
    reveal_to_all_on_interaction: bool = False


@dataclass(frozen=True)
class InformationPayloadDefinition:
    kind: InformationPayloadKind
    title: str
    detail: str
    tags: tuple[str, ...] = ()
    observer_filter: PersistentObserverFilter = PersistentObserverFilter()
    share_mode: InformationShareMode = InformationShareMode.OBSERVER_ONLY


@dataclass(frozen=True)
class SummonedCreatureDefinition:
    summon_name: str
    statblock_reference: str | None = None
    semantic_tags: tuple[str, ...] = ()
    observer_filter: PersistentObserverFilter = PersistentObserverFilter()


@dataclass(frozen=True)
class ZoneTickDefinition:
    timing: TriggerTiming
    effects: tuple[EffectDefinition, ...] = ()
    applies_to_entering_actor: bool = False
    applies_to_exiting_actor: bool = False


@dataclass(frozen=True)
class PersistentAreaDefinition:
    name: str
    area_shape: AreaShape
    area_size_ft: int
    semantic_tags: tuple[str, ...] = ()
    observer_filter: PersistentObserverFilter = PersistentObserverFilter()
    entry_effects: tuple[EffectDefinition, ...] = ()
    exit_effects: tuple[EffectDefinition, ...] = ()
    tick_effects: tuple[ZoneTickDefinition, ...] = ()
    apparent_only: bool = False
    blocks_vision: bool = False
    difficult_terrain: bool = False
    obscurement_level: ObscurementLevel | None = None
    bright_light_radius_ft: int = 0
    dim_light_radius_ft: int = 0
    relative_origins: tuple[tuple[int, int, int], ...] = ((0, 0, 0),)


@dataclass(frozen=True)
class RitualCastingMetadata:
    can_cast_as_ritual: bool = False
    additional_cast_seconds: int = 600
    no_slot_cost: bool = True
    non_combat_only: bool = True


@dataclass(frozen=True)
class ActiveEffectDefinition:
    name: str
    duration: DurationSpec
    concentration: bool = False
    replace_existing_same_name_from_source: bool = False
    armor_class_bonus: int = 0
    armor_class_minimum: int = 0
    max_hit_points_bonus: int = 0
    armor_class_base_override: int | None = None
    armor_class_base_add_dex_modifier: bool = False
    end_when_armor_equipped: bool = False
    damage_resistances: tuple[str, ...] = ()
    damage_reduction_damage_types: tuple[str, ...] = ()
    damage_reduction_once_per_turn: DiceModifierSpec | None = None
    ability_check_advantage_abilities: tuple[Ability, ...] = ()
    ability_check_disadvantage_abilities: tuple[Ability, ...] = ()
    saving_throw_advantage_abilities: tuple[Ability, ...] = ()
    melee_attack_damage_bonus: int = 0
    melee_weapon_attack_bonus_damage: DamageEffectDef | None = None
    weapon_attack_bonus_damage: DamageEffectDef | None = None
    marked_target_bonus_damage: DamageEffectDef | None = None
    marked_target_skill_advantage_names: tuple[str, ...] = ()
    incoming_hostile_targeting_save_ability: Ability | None = None
    incoming_hostile_targeting_save_dc_source: SaveDcSource | None = None
    incoming_hostile_targeting_save_flat_dc: int | None = None
    attack_roll_bonus: DiceModifierSpec | None = None
    attack_roll_penalty: DiceModifierSpec | None = None
    saving_throw_bonus: DiceModifierSpec | None = None
    saving_throw_penalty: DiceModifierSpec | None = None
    spell_save_dc_bonus: int = 0
    spell_attack_roll_advantage: bool = False
    end_on_next_d20_test: bool = False
    cannot_cast_spells: bool = False
    speed_override_ft: int | None = None
    speed_bonus_ft: int = 0
    speed_penalty_ft: int = 0
    incoming_attack_roll_penalty: DiceModifierSpec | None = None
    attackers_have_advantage: bool = False
    end_on_next_incoming_attack_roll: bool = False
    next_attack_roll_disadvantage: bool = False
    next_saving_throw_penalty: DiceModifierSpec | None = None
    ability_check_bonus_skill_name: str | None = None
    ability_check_bonus: DiceModifierSpec | None = None
    healing_blocked: bool = False
    blocks_opportunity_attacks: bool = False
    cannot_take_reactions: bool = False
    can_dash_as_bonus_action: bool = False
    understand_all_languages: bool = False
    can_communicate_with_beasts: bool = False
    darkvision_radius_ft: int = 0
    blindsight_radius_ft: int = 0
    truesight_radius_ft: int = 0
    attackers_rely_on_sight_have_disadvantage: bool = False
    fall_speed_override_ft: int | None = None
    prevent_falling_damage: bool = False
    attack_roll_disadvantage_against_other_targets_except_source: bool = False
    cannot_willingly_move_beyond_source_ft: int | None = None
    suppress_invisible_benefits: bool = False
    granted_condition_immunities: tuple[ConditionType, ...] = ()
    protected_from_creature_types: tuple[str, ...] = ()
    protected_condition_types: tuple[ConditionType, ...] = ()
    start_of_turn_temp_hit_points: int = 0
    start_of_turn_temp_hit_points_bonus_source: HealingBonusSource = HealingBonusSource.FLAT
    retaliatory_melee_hit_damage: DamageEffectDef | None = None
    retaliatory_requires_temp_hit_points: bool = False
    bright_light_radius_ft: int = 0
    dim_light_radius_ft: int = 0
    jump_replacement_distance_ft: int = 0
    jump_replacement_movement_cost_ft: int = 0
    enchanted_item_id: str | None = None
    enchanted_attack_ability: Ability | None = None
    enchanted_damage_ability: Ability | None = None
    enchanted_damage_dice_count: int | None = None
    enchanted_damage_die_faces: int | None = None
    enchanted_damage_type_override: str | None = None
    enchanted_attack_bonus: int = 0
    enchanted_damage_bonus: int = 0
    end_when_enchanted_item_not_carried: bool = False
    max_distance_from_source_ft: int | None = None
    end_if_target_out_of_range_ft: int | None = None
    end_if_target_has_total_cover: bool = False
    end_when_source_effect_name_missing: str | None = None
    end_on_damage_from_source_side: bool = False
    end_when_target_attacks_or_harmful_casts: bool = False
    end_when_target_casts_spell: bool = False
    end_when_target_deals_damage: bool = False
    on_start: tuple[EffectDefinition, ...] = ()
    on_end: tuple[EffectDefinition, ...] = ()
    ongoing_triggers: tuple[OngoingTriggerDefinition, ...] = ()
    summoned_creatures: tuple[SummonedCreatureDefinition, ...] = ()
    created_objects: tuple[CreatedObjectDefinition, ...] = ()
    illusions: tuple[IllusionDefinition, ...] = ()
    information_payloads: tuple[InformationPayloadDefinition, ...] = ()
    persistent_areas: tuple[PersistentAreaDefinition, ...] = ()


@dataclass(frozen=True)
class StartActiveEffectDef(EffectDefinition):
    active_effect: ActiveEffectDefinition
    split_targets_individually: bool = False
    concentration_anchor_name: str | None = None


@dataclass(frozen=True)
class CapabilityDefinition:
    capability_id: str
    name: str
    kind: CapabilityKind
    source: str
    action_cost: str
    targeting: TargetingSpec
    effect: EffectDefinition
    ritual_casting: RitualCastingMetadata | None = None

