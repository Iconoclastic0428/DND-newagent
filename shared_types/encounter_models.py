from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .battlefield import BattlefieldState, CoverLevel, MovementIntentMode, OccupiedVolume, SupportStateType, TraversalMode
from .capabilities import (
    ActiveEffectDefinition,
    AreaShape,
    CapabilityDefinition,
    CapabilityKind,
    CreatedObjectDefinition,
    IllusionActualProperties,
    IllusionDefinition,
    IllusionModality,
    IllusionRevealPolicy,
    IllusionSubtype,
    IllusionTemplateId,
    InformationPayloadDefinition,
    InformationPayloadKind,
    InformationShareMode,
    PersistentAreaDefinition,
    PersistentObserverMode,
    SummonedCreatureDefinition,
    TriggerTiming,
    ZoneTickDefinition,
)
from .conditions import ConditionInstance, ConditionType
from .equipment import AmmunitionRecoveryPolicy, EnvironmentObjectState, GroundItemState
from .models import Ability, CharacterRecord, ChoiceView
from .spellcasting import SpellPerceptibilityProfile, SpellRuntimeSupportProfile
from .rest import RestRecoverySpec, RestState, RuntimeResourcePoolState


class ActorSide(str, Enum):
    PLAYER = 'player'
    MONSTER = 'monster'


class ZeroHitPointsBehavior(str, Enum):
    DIE = 'die'
    DEATH_SAVES = 'death-saves'


class EncounterPhase(str, Enum):
    READY = 'ready'
    IN_PROGRESS = 'in-progress'
    COMPLETE = 'complete'


class AttackKind(str, Enum):
    MELEE = 'melee'
    RANGED = 'ranged'
    MELEE_OR_RANGED = 'melee-or-ranged'


class AttackUsageKind(str, Enum):
    NATURAL = 'natural'
    WEAPON_MELEE = 'weapon-melee'
    WEAPON_RANGED = 'weapon-ranged'
    THROWN_WEAPON = 'thrown-weapon'
    IMPROVISED_MELEE = 'improvised-melee'
    IMPROVISED_THROWN = 'improvised-thrown'


class CombatActionType(str, Enum):
    ATTACK = 'attack'
    MAGIC = 'magic'
    FEATURE = 'feature'
    ITEM = 'item'
    DASH = 'dash'
    DISENGAGE = 'disengage'
    DODGE = 'dodge'
    HELP = 'help'
    HIDE = 'hide'
    READY = 'ready'
    SEARCH = 'search'
    STUDY = 'study'
    UTILIZE = 'utilize'
    END_TURN = 'endturn'
    GRAPPLE = 'grapple'
    SHOVE = 'shove'
    OPPORTUNITY_ATTACK = 'opportunity-attack'
    SHIELD = 'shield'


class SpellEffectType(str, Enum):
    MISTY_STEP = 'misty-step'
    SHIELD = 'shield'
    MAGIC_MISSILE = 'magic-missile'


class ReactionTriggerType(str, Enum):
    LEAVE_REACH = 'leave-reach'
    HIT_DETECTED = 'hit-detected'
    DAMAGE_TAKEN = 'damage-taken'
    FALL_DETECTED = 'fall-detected'
    POST_HIT_TRIGGER = 'post-hit-trigger'
    READY_TRIGGER = 'ready-trigger'


class ReadyTriggerKind(str, Enum):
    TARGET_IN_RESPONSE_WINDOW = 'target-in-response-window'


class ReadyResponseKind(str, Enum):
    ATTACK = 'attack'
    MOVE = 'move'
    SPELL = 'spell'
    CAPABILITY = 'capability'


class TimingEntryKind(str, Enum):
    DEATH_SAVE = 'death-save'
    CAPABILITY_RECHARGE = 'capability-recharge'
    ACTIVE_EFFECT_EXPIRE = 'active-effect-expire'
    ACTIVE_EFFECT_TRIGGER = 'active-effect-trigger'
    PERSISTENT_AREA_TICK = 'persistent-area-tick'
    READY_EXPIRE = 'ready-expire'
    SHARED_SENSES_EXPIRE = 'shared-senses-expire'


class PendingResolutionKind(str, Enum):
    COMPLETE_MOVEMENT = 'complete-movement'
    FINALIZE_ATTACK = 'finalize-attack'
    APPLY_ATTACK_DAMAGE = 'apply-attack-damage'
    COMPLETE_FALL = 'complete-fall'
    CONTINUE_REACTION_WINDOW = 'continue-reaction-window'
    CONTINUE_TIMING_QUEUE = 'continue-timing-queue'

class ShoveOutcome(str, Enum):
    PRONE = 'prone'
    PUSH = 'push'


class DyingStateStatus(str, Enum):
    ALIVE = 'alive'
    AT_0_HP_UNCONSCIOUS = 'at-0-hp-unconscious'
    STABLE_AT_0_HP = 'stable-at-0-hp'
    DEAD = 'dead'
    KNOCKOUT_NONLETHAL = 'knockout-nonlethal'


class PersistentEffectFamily(str, Enum):
    SUMMONED_CREATURE = 'summoned-creature'
    CREATED_OBJECT = 'created-object'
    ILLUSION = 'illusion'
    INFORMATION_PAYLOAD = 'information-payload'
    PERSISTENT_AREA = 'persistent-area'


class IllusionObserverStatus(str, Enum):
    UNAWARE = 'unaware'
    INTENDED = 'intended'
    SUSPECTS = 'suspects'
    DISBELIEVED = 'disbelieved'
    PIERCED = 'pierced'


@dataclass(frozen=True)
class DyingState:
    status: DyingStateStatus = DyingStateStatus.ALIVE
    death_save_successes: int = 0
    death_save_failures: int = 0
    stable_recovery_minutes_remaining: int | None = None

    @property
    def stable_recovery_hours_remaining(self) -> int | None:
        if self.stable_recovery_minutes_remaining is None:
            return None
        hours, remainder = divmod(self.stable_recovery_minutes_remaining, 60)
        return hours if remainder == 0 else hours + 1


@dataclass(frozen=True)
class EncounterPolicy:
    allowed_core_sources: frozenset[str] = frozenset({'XPHB', 'XMM'})
    allow_homebrew: bool = False
    allowed_monster_sources: frozenset[str] = frozenset()
    allowed_spell_sources: frozenset[str] = frozenset({'XPHB'})
    allow_first_party_monster_extensions: bool = True
    allow_first_party_spell_extensions: bool = True

    def allows_monster_source(self, source: str, *, homebrew: bool, official: bool, first_party: bool) -> bool:
        if homebrew and not self.allow_homebrew:
            return False
        if not official:
            return False
        if source == 'PHB':
            return False
        if self.allowed_monster_sources:
            return source in self.allowed_monster_sources
        if source in self.allowed_core_sources:
            return True
        return self.allow_first_party_monster_extensions and first_party

    def allows_spell_source(self, source: str, *, homebrew: bool, official: bool, first_party: bool) -> bool:
        if homebrew and not self.allow_homebrew:
            return False
        if not official:
            return False
        if source == 'PHB':
            return False
        if self.allowed_spell_sources:
            return source in self.allowed_spell_sources
        if source in self.allowed_core_sources:
            return True
        return self.allow_first_party_spell_extensions and first_party


@dataclass(frozen=True)
class GridPosition:
    x: int
    y: int
    z: int = 0

    def horizontal(self) -> 'GridPosition':
        return GridPosition(self.x, self.y, 0)


@dataclass(frozen=True)
class AttackProfile:
    attack_id: str
    name: str
    attack_kind: AttackKind
    to_hit_bonus: int
    reach_ft: int | None
    range_ft: int | None
    long_range_ft: int | None
    damage_dice_count: int
    damage_die_faces: int
    damage_bonus: int
    damage_type: str
    is_finesse: bool = False
    source_item_id: str | None = None
    attack_usage_kind: AttackUsageKind = AttackUsageKind.NATURAL
    ammunition_item_id: str | None = None
    required_hand_count: int = 0
    loading: bool = False


@dataclass(frozen=True)
class SpellRecord:
    record_id: str
    name: str
    source: str
    official: bool
    homebrew: bool
    action_cost: str
    range_ft: int | None
    concentration: bool
    level: int = 0
    casting_time_seconds: int = 6
    perceptibility: SpellPerceptibilityProfile = SpellPerceptibilityProfile()
    material_component_cost_cp: int | None = None
    material_component_consumed: bool = False
    material_component_item_keywords: tuple[str, ...] = ()
    material_component_focus_tags: tuple[str, ...] = ()
    can_cast_as_ritual: bool = False
    ritual_additional_cast_seconds: int = 600
    effect_type: SpellEffectType | None = None
    capability: CapabilityDefinition | None = None
    runtime_support: SpellRuntimeSupportProfile | None = None


@dataclass(frozen=True)
class SpellOption:
    option_id: str
    spell_record_id: str
    uses_per_day: int | None
    action_cost_override: str | None = None


@dataclass(frozen=True)
class MonsterRecord:
    record_id: str
    name: str
    source: str
    official: bool
    homebrew: bool
    size: str
    alignment: str | None
    creature_type: str
    armor_class: int
    max_hit_points: int
    hit_point_formula: str
    speed_ft: int
    climb_speed_ft: int
    proficiency_bonus: int
    ability_scores: dict[Ability, int]
    save_bonuses: dict[Ability, int]
    skill_bonuses: dict[str, int]
    passive_perception: int
    damage_immunities: tuple[str, ...]
    damage_resistances: tuple[str, ...]
    condition_immunities: tuple[str, ...]
    traits: tuple[str, ...]
    attacks: tuple[AttackProfile, ...]
    spell_options: tuple[SpellOption, ...]
    spellcasting_ability: Ability | None = None
    spell_save_dc: int | None = None
    spell_attack_bonus: int | None = None


@dataclass(frozen=True)
class EncounterContentCatalog:
    monsters: dict[str, MonsterRecord]
    spells: dict[str, SpellRecord]


@dataclass(frozen=True)
class CharacterPlacement:
    actor_id: str
    record: CharacterRecord
    position: GridPosition


@dataclass(frozen=True)
class MonsterPlacement:
    actor_id: str
    monster_id: str
    position: GridPosition


@dataclass(frozen=True)
class RuntimeSpellState:
    option_id: str
    name: str
    source: str
    action_cost: str
    range_ft: int | None
    remaining_uses: int | None
    level: int = 0
    casting_time_seconds: int = 6
    perceptibility: SpellPerceptibilityProfile = field(default_factory=SpellPerceptibilityProfile)
    material_component_cost_cp: int | None = None
    material_component_consumed: bool = False
    material_component_item_keywords: tuple[str, ...] = ()
    material_component_focus_tags: tuple[str, ...] = ()
    can_cast_as_ritual: bool = False
    ritual_additional_cast_seconds: int = 600
    effect_type: SpellEffectType | None = None
    max_uses: int | None = None
    concentration: bool = False
    capability: CapabilityDefinition | None = None
    runtime_support: SpellRuntimeSupportProfile | None = None
    rest_recovery: RestRecoverySpec = field(default_factory=RestRecoverySpec)
    resource_pool_id: str | None = None


@dataclass(frozen=True)
class RuntimeCapabilityState:
    option_id: str
    name: str
    source: str
    kind: CapabilityKind
    action_cost: str
    remaining_uses: int | None
    capability: CapabilityDefinition
    source_record_id: str | None = None
    recharge_min_roll: int | None = None
    max_uses: int | None = None
    rest_recovery: RestRecoverySpec = field(default_factory=RestRecoverySpec)


@dataclass(frozen=True)
class ReadyTriggerState:
    trigger_kind: ReadyTriggerKind
    trigger_actor_id: str


@dataclass(frozen=True)
class ReadyResponseState:
    response_kind: ReadyResponseKind
    attack_id: str | None = None
    spell_id: str | None = None
    capability_id: str | None = None
    destination: GridPosition | None = None
    movement_intent_mode: MovementIntentMode = MovementIntentMode.SAME_PLANE
    target_actor_id: str | None = None


@dataclass(frozen=True)
class ReadiedActionState:
    trigger: ReadyTriggerState
    response: ReadyResponseState
    declared_round_number: int
    concentration_effect_id: str | None = None


@dataclass(frozen=True)
class AppliedConditionRef:
    actor_id: str
    condition_type: ConditionType


@dataclass(frozen=True)
class ActiveEffectState:
    effect_instance_id: str
    capability_id: str
    name: str
    source_actor_id: str
    target_actor_ids: tuple[str, ...]
    definition: ActiveEffectDefinition
    metadata: tuple[tuple[str, str], ...] = ()
    started_round_number: int = 0
    started_turn_actor_id: str | None = None
    duration_anchor_actor_id: str | None = None
    remaining_rounds: int | None = None
    origin_point: GridPosition | None = None
    applied_conditions: tuple[AppliedConditionRef, ...] = ()
    last_once_per_turn_round_number: int | None = None
    last_once_per_turn_turn_actor_id: str | None = None


@dataclass(frozen=True)
class PersistentEffectState:
    persistent_effect_id: str
    family: PersistentEffectFamily
    source_effect_id: str
    source_capability_id: str
    source_actor_id: str
    owner_actor_id: str | None = None
    owner_controller_id: str | None = None
    anchor_position: GridPosition | None = None
    anchor_object_id: str | None = None
    observer_mode: PersistentObserverMode = PersistentObserverMode.ALL_VALID_OBSERVERS
    observer_actor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SummonedCreatureState:
    persistent: PersistentEffectState
    summon_id: str
    definition: SummonedCreatureDefinition
    position: GridPosition
    linked_actor_id: str | None = None


@dataclass(frozen=True)
class CreatedObjectState:
    persistent: PersistentEffectState
    object_id: str
    definition: CreatedObjectDefinition
    cells: tuple[GridPosition, ...]
    linked_feature_id: str | None = None


@dataclass(frozen=True)
class IllusionObserverState:
    observer_id: str
    status: IllusionObserverStatus = IllusionObserverStatus.INTENDED
    currently_perceivable: bool = True
    render_description_override: str | None = None


@dataclass(frozen=True)
class IllusionState:
    persistent: PersistentEffectState
    illusion_id: str
    definition: IllusionDefinition
    cells: tuple[GridPosition, ...]
    observer_states: dict[str, IllusionObserverState] = field(default_factory=dict)


@dataclass(frozen=True)
class InformationalPayloadState:
    persistent: PersistentEffectState
    payload_id: str
    definition: InformationPayloadDefinition


@dataclass(frozen=True)
class PersistentAreaState:
    persistent: PersistentEffectState
    area_id: str
    definition: PersistentAreaDefinition
    origin: GridPosition
    origins: tuple[GridPosition, ...] = ()


@dataclass(frozen=True)
class RitualCastingState:
    ritual_id: str
    actor_id: str
    capability_id: str
    total_seconds: int
    remaining_seconds: int
    no_slot_cost: bool
    spell_id: str | None = None


@dataclass(frozen=True)
class ReactionOption:
    option_id: str
    actor_id: str
    action_type: CombatActionType
    label: str
    detail: str
    attack_id: str | None = None
    spell_id: str | None = None
    capability_id: str | None = None
    target_id: str | None = None
    parameters: tuple[tuple[str, str], ...] = ()
    consumes_reaction: bool = True
    resource_to_spend: str | None = 'reaction'


@dataclass(frozen=True)
class PendingMovementState:
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int
    remaining_movement_ft_after: int
    movement_mode: TraversalMode = TraversalMode.WALK
    movement_spent_ft_after: int | None = None
    consume_turn_movement: bool = True


@dataclass(frozen=True)
class PendingAttackState:
    actor_id: str
    attack_id: str
    target_id: str
    attack_rolls: tuple[int, ...]
    selected_roll: int
    attack_total: int
    target_armor_class_modifier: int = 0
    critical_on_hit: bool = False
    had_advantage: bool = False
    had_disadvantage: bool = False
    attack_kind: AttackKind = AttackKind.MELEE
    attack_usage_kind: AttackUsageKind = AttackUsageKind.NATURAL
    source_item_id: str | None = None
    damage_dice_count: int = 0
    damage_die_faces: int = 0
    damage_bonus: int = 0
    damage_type: str = 'bludgeoning'
    sneak_attack_dice_count: int = 0
    sneak_attack_damage_type: str | None = None


@dataclass(frozen=True)
class PendingReadyTriggerState:
    trigger_actor_id: str
    from_position: GridPosition | None
    to_position: GridPosition


@dataclass(frozen=True)
class PendingFallState:
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int
    landing_surface_type: str


@dataclass(frozen=True)
class TimingEntryState:
    entry_id: str
    actor_id: str
    phase: TriggerTiming
    kind: TimingEntryKind
    label: str
    effect_instance_id: str | None = None
    trigger_index: int | None = None
    trigger_actor_id: str | None = None


@dataclass(frozen=True)
class PendingTimingQueueState:
    actor_id: str
    phase: TriggerTiming
    entries: tuple[TimingEntryState, ...]
    next_actor_id: str | None = None
    next_round_number: int | None = None


@dataclass(frozen=True)
class PendingResolutionState:
    kind: PendingResolutionKind
    pending_movement: PendingMovementState | None = None
    pending_attack: PendingAttackState | None = None
    pending_fall: PendingFallState | None = None
    reaction_window: ReactionWindowState | None = None
    timing_queue: PendingTimingQueueState | None = None
    next_resume: PendingResolutionState | None = None


@dataclass(frozen=True)
class ReactionWindowState:
    trigger_id: str
    trigger_type: ReactionTriggerType
    pending_actor_id: str
    prompt: str
    options: tuple[ReactionOption, ...]
    pending_movement: PendingMovementState | None = None
    pending_attack: PendingAttackState | None = None
    pending_ready_trigger: PendingReadyTriggerState | None = None
    responded_actor_ids: tuple[str, ...] = ()
    resume_state: PendingResolutionState | None = None


@dataclass
class RuntimeActorState:
    actor_id: str
    name: str
    side: ActorSide
    source_refs: tuple[str, ...]
    size: str
    alignment: str | None
    creature_type: str
    armor_class: int
    max_hit_points: int
    current_hit_points: int
    position: GridPosition
    speed_ft: int
    climb_speed_ft: int
    summon_owner_actor_id: str | None = None
    mounted_on_actor_id: str | None = None
    swim_speed_ft: int = 0
    fly_speed_ft: int = 0
    hover: bool = False
    occupied_height_ft: int = 5
    movement_spent_ft: int = 0
    dash_bonus_ft: int = 0
    remaining_movement_ft: int = 0
    initiative_bonus: int = 0
    level: int = 0
    initiative_roll: int | None = None
    initiative_total: int | None = None
    proficiency_bonus: int = 0
    passive_perception: int = 10
    ability_scores: dict[Ability, int] = field(default_factory=dict)
    ability_modifiers: dict[Ability, int] = field(default_factory=dict)
    saving_throw_bonuses: dict[Ability, int] = field(default_factory=dict)
    skill_bonuses: dict[str, int] = field(default_factory=dict)
    base_armor_class: int | None = None
    base_initiative_bonus: int | None = None
    base_passive_perception: int | None = None
    base_ability_scores: dict[Ability, int] = field(default_factory=dict)
    base_ability_modifiers: dict[Ability, int] = field(default_factory=dict)
    base_saving_throw_bonuses: dict[Ability, int] = field(default_factory=dict)
    base_skill_bonuses: dict[str, int] = field(default_factory=dict)
    attacks: dict[str, AttackProfile] = field(default_factory=dict)
    spells: dict[str, RuntimeSpellState] = field(default_factory=dict)
    capabilities: dict[str, RuntimeCapabilityState] = field(default_factory=dict)
    resource_pools: dict[str, RuntimeResourcePoolState] = field(default_factory=dict)
    hit_die_faces: int = 0
    total_hit_dice: int = 0
    remaining_hit_dice: int = 0
    spellcasting_ability: Ability | None = None
    spell_save_dc: int | None = None
    spell_attack_bonus: int | None = None
    damage_immunities: frozenset[str] = frozenset()
    damage_resistances: frozenset[str] = frozenset()
    base_damage_resistances: frozenset[str] = frozenset()
    condition_immunities: frozenset[ConditionType] = frozenset()
    base_condition_immunities: frozenset[ConditionType] = frozenset()
    ability_check_advantage_abilities: frozenset[Ability] = frozenset()
    ability_check_disadvantage_abilities: frozenset[Ability] = frozenset()
    saving_throw_advantage_abilities: frozenset[Ability] = frozenset()
    melee_attack_damage_bonus: int = 0
    cannot_cast_spells: bool = False
    cannot_take_reactions: bool = False
    can_dash_as_bonus_action: bool = False
    understand_all_languages: bool = False
    can_communicate_with_beasts: bool = False
    darkvision_radius_ft: int = 0
    blindsight_radius_ft: int = 0
    truesight_radius_ft: int = 0
    identified_item_ids: frozenset[str] = frozenset()
    purified_item_ids: frozenset[str] = frozenset()
    fall_speed_override_ft: int | None = None
    prevent_falling_damage: bool = False
    speed_override_ft: int | None = None
    speed_bonus_ft: int = 0
    jump_replacement_distance_ft: int = 0
    jump_replacement_movement_cost_ft: int = 0
    action_available: bool = True
    bonus_action_available: bool = True
    reaction_available: bool = True
    remaining_free_object_interaction: bool = True
    dodge_active: bool = False
    disengage_active: bool = False
    hidden: bool = False
    surprised: bool = False
    stealth_check_total: int | None = None
    hidden_from_actor_ids: frozenset[str] = frozenset()
    help_target_id: str | None = None
    readied_action: ReadiedActionState | None = None
    temp_hit_points: int = 0
    armor_class_modifier: int = 0
    armor_class_minimum: int = 0
    spell_casts_this_turn: int = 0
    concentrating_effect_id: str | None = None
    carried_item_counts: dict[str, int] = field(default_factory=dict)
    body_weight_lb: float = 0.0
    main_hand_item_id: str | None = None
    off_hand_item_id: str | None = None
    equipped_armor_item_id: str | None = None
    held_item_ids: tuple[str, ...] = ()
    worn_armor_item_id: str | None = None
    worn_shield_item_id: str | None = None
    loading_spent_resources: frozenset[str] = frozenset()
    can_see_invisible: bool = False
    support_state: SupportStateType = SupportStateType.GROUNDED
    condition_instances: tuple[ConditionInstance, ...] = ()
    story_npc_id: str | None = None
    story_combat_goal: str | None = None
    story_attitude: str | None = None
    story_stance: str | None = None
    story_faction_tags: tuple[str, ...] = ()
    story_authority_tags: tuple[str, ...] = ()
    story_synthesized_source: str | None = None
    story_fallback_archetype: str | None = None
    character_record: CharacterRecord | None = None
    story_context: StoryCombatantContext | None = None
    shared_sense_owner_actor_id: str | None = None
    shared_senses_actor_id: str | None = None
    story_goal: str | None = None
    story_context_tags: tuple[str, ...] = ()
    fallback_synthesized: bool = False
    zero_hit_points_behavior: ZeroHitPointsBehavior = ZeroHitPointsBehavior.DIE
    dying_state: DyingState = field(default_factory=DyingState)
    rest_state: RestState = field(default_factory=RestState)
    last_long_rest_completed_at_seconds: int | None = None
    friends_targeted_at_seconds: dict[str, int] = field(default_factory=dict)
    last_sneak_attack_round_number: int | None = None
    last_sneak_attack_turn_actor_id: str | None = None

    @property
    def is_conscious(self) -> bool:
        return self.current_hit_points > 0

    @property
    def is_dead(self) -> bool:
        return self.dying_state.status == DyingStateStatus.DEAD

    @property
    def uses_death_saves(self) -> bool:
        return self.zero_hit_points_behavior == ZeroHitPointsBehavior.DEATH_SAVES

    @property
    def eligible_for_death_saves(self) -> bool:
        return self.uses_death_saves and self.current_hit_points == 0 and self.dying_state.status == DyingStateStatus.AT_0_HP_UNCONSCIOUS

    @property
    def is_turn_eligible(self) -> bool:
        return not self.is_dead and (
            self.current_hit_points > 0
            or self.dying_state.status in {
                DyingStateStatus.AT_0_HP_UNCONSCIOUS,
                DyingStateStatus.STABLE_AT_0_HP,
                DyingStateStatus.KNOCKOUT_NONLETHAL,
            }
        )

    @property
    def effective_armor_class(self) -> int:
        return max(self.armor_class + self.armor_class_modifier, self.armor_class_minimum)

    @property
    def occupied_volume(self) -> OccupiedVolume:
        return OccupiedVolume(x=self.position.x, y=self.position.y, z=self.position.z, height_ft=self.occupied_height_ft)

    @property
    def max_path_speed_ft(self) -> int:
        base_speed = max(self.speed_ft + self.speed_bonus_ft, self.climb_speed_ft, self.swim_speed_ft, self.fly_speed_ft)
        if self.speed_override_ft is not None:
            base_speed = min(base_speed, self.speed_override_ft)
        if base_speed <= 0:
            return 0
        return base_speed + self.dash_bonus_ft


@dataclass
class EncounterState:
    actors: dict[str, RuntimeActorState] = field(default_factory=dict)
    battlefield: BattlefieldState = field(default_factory=BattlefieldState)
    phase: EncounterPhase = EncounterPhase.READY
    random_counter: int = 0
    round_number: int = 0
    turn_index: int = 0
    active_actor_id: str | None = None
    initiative_order: tuple[str, ...] = ()
    winning_side: ActorSide | None = None
    pending_reaction_window: ReactionWindowState | None = None
    pending_timing_queue: PendingTimingQueueState | None = None
    active_effects: dict[str, ActiveEffectState] = field(default_factory=dict)
    persistent_effects: dict[str, PersistentEffectState] = field(default_factory=dict)
    summoned_creatures: dict[str, SummonedCreatureState] = field(default_factory=dict)
    created_objects: dict[str, CreatedObjectState] = field(default_factory=dict)
    illusions: dict[str, IllusionState] = field(default_factory=dict)
    informational_payloads: dict[str, InformationalPayloadState] = field(default_factory=dict)
    persistent_areas: dict[str, PersistentAreaState] = field(default_factory=dict)
    ritual_casts: dict[str, RitualCastingState] = field(default_factory=dict)
    ground_items: dict[str, GroundItemState] = field(default_factory=dict)
    environment_objects: dict[str, EnvironmentObjectState] = field(default_factory=dict)
    ammunition_recovery_policy: AmmunitionRecoveryPolicy = AmmunitionRecoveryPolicy.EXPENDED_NOT_RECOVERABLE
    clock_seconds: int = 0
    event_log: list[object] = field(default_factory=list)


@dataclass(frozen=True)
class EncounterSnapshot:
    phase: EncounterPhase
    summary_lines: tuple[str, ...]
    available_choices: dict[str, tuple[ChoiceView, ...]]





