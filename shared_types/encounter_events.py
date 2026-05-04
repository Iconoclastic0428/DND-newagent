from __future__ import annotations

from dataclasses import dataclass

from .adjudication import AdjudicationCheckRequest, AdjudicationContestRequest, AdjudicationModeSwitchRecommendation, AdjudicationPlan, AdjudicationSaveRequest, AdjudicationType
from .battlefield import CoverLevel, FallReason, LandingSurfaceType, RelocationType, SupportStateType, TraversalMode
from .capabilities import AreaShape, InformationPayloadKind, TriggerTiming
from .conditions import ConditionInstance, ConditionType
from .d20 import D20TestResult
from .equipment import EnvironmentObjectAction, EquipmentSlot, ObjectInteractionCostMode, ObjectInteractionKind
from .effects import CheckRequest, CheckResolution, EffectResolutionBranch, ForcedMovementEffect, ForcedMovementResult, HazardResolutionRequest, HazardResolutionResult, LiquidEntryMitigationResolution, SaveRequest, SaveResolution
from .encounter_models import (
    ActorSide,
    ActiveEffectState,
    CombatActionType,
    CreatedObjectState,
    GridPosition,
    IllusionState,
    InformationalPayloadState,
    PendingTimingQueueState,
    PersistentAreaState,
    PersistentEffectFamily,
    PersistentEffectState,
    ReadiedActionState,
    ReactionWindowState,
    RitualCastingState,
    SummonedCreatureState,
)
from .models import Ability
from .visibility import ObserverVisibilityState
from .exploration import (
    DowntimeProjectStatus,
    MarchingOrderEntry,
    NpcAttitude,
    ProcedureCategory,
    ProcedureOutcome,
    ProcedureStatus,
    PuzzleStatus,
    SocialApproachType,
    SocialOutcome,
    TrapStatus,
    WatchAssignment,
)
from .hostile_escalation import (
    AdHocEncounterScenePlan,
    CombatTransitionState,
    HostileEscalationDecision,
    ReinforcementPlan,
    SynthesizedCombatantSpec,
)
from .storytelling import (
    EnterCombatPlan,
    ExitCombatPlan,
    ModeSwitchAction,
    RuntimeMode,
    SpellcastingConcernLevel,
    SpellcastingReactionCategory,
    SpellcastingSocialReactionPlan,
    SpellcastingObservationConfidence,
    StoryCheckRequestState,
    StoryModeCastEscalationDecision,
    StoryModeCastResolution,
    StoryTranscriptEntry,
    StoryWitnessKind,
    StorySpellObserverAwareness,
    WitnessObservationPacket,
)
from .rest import RestActivityType, RestInterruptionReason, RestType
from .social import (
    FactionRelationshipState,
    IncidentInterpretationRecord,
    InfluenceRetryCooldown,
    ReputationState,
    SocialIncident,
    SocialPropagationTask,
    WitnessMemoryState,
    WitnessReactionCategory,
)
from .travel import HexCoord, PlannedTravelRoute, TravelHookDefinition, TravelPace, TravelStatus
from .progression import MilestoneRecord, PendingLevelUpRecord, ProgressionMode, XPRewardRecord
from .advancement import (
    AdvancementChoiceCategory,
    AdvancementCommitStatus,
    AdvancementTransaction,
    AdvancementValidationStatus,
    PendingAdvancementChoice,
    ResolvedAdvancementChoice,
)


class EncounterEvent:
    """Marker base type for deterministic encounter state transitions."""


@dataclass(frozen=True)
class SaveRequestedEvent(EncounterEvent):
    request: SaveRequest


@dataclass(frozen=True)
class SaveRolledEvent(EncounterEvent):
    resolution: SaveResolution
    random_counter_used: int


@dataclass(frozen=True)
class SaveSucceededEvent(EncounterEvent):
    resolution: SaveResolution


@dataclass(frozen=True)
class SaveFailedEvent(EncounterEvent):
    resolution: SaveResolution


@dataclass(frozen=True)
class CheckRequestedEvent(EncounterEvent):
    request: CheckRequest


@dataclass(frozen=True)
class CheckRolledEvent(EncounterEvent):
    resolution: CheckResolution
    random_counter_used: int


@dataclass(frozen=True)
class CheckSucceededEvent(EncounterEvent):
    resolution: CheckResolution


@dataclass(frozen=True)
class CheckFailedEvent(EncounterEvent):
    resolution: CheckResolution


@dataclass(frozen=True)
class ForcedMovementStartedEvent(EncounterEvent):
    effect: ForcedMovementEffect
    from_position: GridPosition


@dataclass(frozen=True)
class ForcedMovementStepResolvedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    step_distance_ft: int
    step_index: int


@dataclass(frozen=True)
class ForcedMovementStoppedEvent(EncounterEvent):
    result: ForcedMovementResult


@dataclass(frozen=True)
class HazardTriggeredEvent(EncounterEvent):
    request: HazardResolutionRequest


@dataclass(frozen=True)
class HazardResolvedEvent(EncounterEvent):
    result: HazardResolutionResult


@dataclass(frozen=True)
class LiquidEntryDetectedEvent(EncounterEvent):
    actor_id: str
    position: GridPosition


@dataclass(frozen=True)
class FallMitigationCheckOfferedEvent(EncounterEvent):
    actor_id: str
    reaction_available: bool
    dc: int


@dataclass(frozen=True)
class FallMitigationCheckResolvedEvent(EncounterEvent):
    actor_id: str
    resolution: LiquidEntryMitigationResolution


@dataclass(frozen=True)
class EncounterStartedEvent(EncounterEvent):
    initiative_order: tuple[str, ...]
    initiative_rolls: dict[str, int]
    initiative_totals: dict[str, int]
    random_counter_used: int
    first_actor_id: str


@dataclass(frozen=True)
class MoveDeclaredEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition


@dataclass(frozen=True)
class ActionDeclaredEvent(EncounterEvent):
    actor_id: str
    action_type: CombatActionType
    target_id: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class AttackDeclaredEvent(EncounterEvent):
    actor_id: str
    attack_id: str
    target_id: str
    action_type: CombatActionType
    resource: str | None = None


@dataclass(frozen=True)
class ActionValidatedEvent(EncounterEvent):
    actor_id: str
    action_type: CombatActionType


@dataclass(frozen=True)
class ActionEffectEvent(EncounterEvent):
    actor_id: str
    action_type: CombatActionType
    target_id: str | None = None
    remaining_movement_ft: int | None = None
    dash_bonus_ft: int | None = None
    disengage_active: bool | None = None
    dodge_active: bool | None = None
    hidden: bool | None = None
    help_target_id: str | None = None
    readied_attack_id: str | None = None
    readied_target_id: str | None = None


@dataclass(frozen=True)
class ObjectInteractionUsedEvent(EncounterEvent):
    actor_id: str
    interaction_kind: ObjectInteractionKind
    cost_mode: ObjectInteractionCostMode
    item_id: str | None = None
    ground_item_id: str | None = None
    object_id: str | None = None
    object_action: EnvironmentObjectAction | None = None


@dataclass(frozen=True)
class UtilizeActionUsedEvent(EncounterEvent):
    actor_id: str
    interaction_kind: ObjectInteractionKind


@dataclass(frozen=True)
class WeaponEquippedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    slot: EquipmentSlot


@dataclass(frozen=True)
class WeaponUnequippedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    slot: EquipmentSlot


@dataclass(frozen=True)
class ItemDrawnEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class ItemStowedEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class ItemDroppedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    quantity: int
    ground_item_id: str
    position: GridPosition


@dataclass(frozen=True)
class ItemPickedUpEvent(EncounterEvent):
    actor_id: str
    item_id: str
    quantity: int
    ground_item_id: str


@dataclass(frozen=True)
class ItemConsumedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    quantity: int
    reason: str


@dataclass(frozen=True)
class ItemGrantedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    quantity: int
    reason: str


@dataclass(frozen=True)
class ItemTransferredEvent(EncounterEvent):
    source_actor_id: str
    target_actor_id: str
    item_id: str
    quantity: int
    reason: str


@dataclass(frozen=True)
class InventoryItemReplacedEvent(EncounterEvent):
    actor_id: str
    old_item_id: str
    new_item_id: str
    quantity: int
    reason: str


@dataclass(frozen=True)
class ItemIdentifiedEvent(EncounterEvent):
    actor_id: str
    item_id: str
    reason: str


@dataclass(frozen=True)
class ConsumablesPurifiedEvent(EncounterEvent):
    actor_id: str
    item_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ShieldDonnedEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class ShieldDoffedEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class ArmorDonnedEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class ArmorDoffedEvent(EncounterEvent):
    actor_id: str
    item_id: str


@dataclass(frozen=True)
class AmmunitionConsumedEvent(EncounterEvent):
    actor_id: str
    weapon_item_id: str
    ammunition_item_id: str
    quantity: int


@dataclass(frozen=True)
class AmmunitionMissingEvent(EncounterEvent):
    actor_id: str
    weapon_item_id: str
    ammunition_item_id: str


@dataclass(frozen=True)
class ImprovisedWeaponUsedEvent(EncounterEvent):
    actor_id: str
    target_id: str
    item_id: str | None = None
    ground_item_id: str | None = None
    object_id: str | None = None
    thrown: bool = False


@dataclass(frozen=True)
class GroundItemCreatedEvent(EncounterEvent):
    ground_item_id: str
    item_id: str
    quantity: int
    position: GridPosition
    improvised_damage_type: str | None = None
    equivalent_weapon_item_id: str | None = None


@dataclass(frozen=True)
class GroundItemRemovedEvent(EncounterEvent):
    ground_item_id: str


@dataclass(frozen=True)
class EnvironmentObjectUsedEvent(EncounterEvent):
    actor_id: str
    object_id: str
    action: EnvironmentObjectAction


@dataclass(frozen=True)
class HideAttemptedEvent(EncounterEvent):
    actor_id: str
    skill_name: str
    check_total: int
    hidden_from_actor_ids: tuple[str, ...]
    success: bool
    random_counter_used: int


@dataclass(frozen=True)
class SearchAttemptedEvent(EncounterEvent):
    actor_id: str
    skill_name: str
    check_total: int
    discovered_actor_ids: tuple[str, ...]
    random_counter_used: int


@dataclass(frozen=True)
class StudyAttemptedEvent(EncounterEvent):
    actor_id: str
    skill_name: str
    check_total: int
    discovered_actor_ids: tuple[str, ...]
    random_counter_used: int


@dataclass(frozen=True)
class PassiveNoticeTriggeredEvent(EncounterEvent):
    observer_id: str
    target_id: str
    passive_score: int
    stealth_dc: int
    noticed: bool


@dataclass(frozen=True)
class ActorHiddenEvent(EncounterEvent):
    actor_id: str
    stealth_check_total: int
    hidden_from_actor_ids: tuple[str, ...]


@dataclass(frozen=True)
class ActorRevealedEvent(EncounterEvent):
    actor_id: str
    observer_id: str | None = None
    reason: str = ''


@dataclass(frozen=True)
class VisibilityStateChangedEvent(EncounterEvent):
    observer_id: str
    target_id: str
    visibility_state: ObserverVisibilityState


@dataclass(frozen=True)
class ContestRolledEvent(EncounterEvent):
    actor_id: str
    target_id: str
    contest_type: str
    actor_rolls: tuple[int, ...]
    actor_total: int
    target_rolls: tuple[int, ...]
    target_total: int
    random_counter_used: int


@dataclass(frozen=True)
class ResourceSpentEvent(EncounterEvent):
    actor_id: str
    resource: str
    reason: str
    amount: int = 1


@dataclass(frozen=True)
class ResourcePoolSpentEvent(EncounterEvent):
    actor_id: str
    resource_id: str
    amount_spent: int
    current_after: int
    maximum: int
    reason: str


@dataclass(frozen=True)
class ResourcePoolRecoveredEvent(EncounterEvent):
    actor_id: str
    resource_id: str
    amount_recovered: int
    current_after: int
    maximum: int
    reason: str


@dataclass(frozen=True)
class D20TestRolledEvent(EncounterEvent):
    actor_id: str
    result: D20TestResult
    random_counter_used: int


@dataclass(frozen=True)
class EffectRollAppliedEvent(EncounterEvent):
    actor_id: str
    effect_instance_id: str
    reason: str
    rolls: tuple[int, ...]
    total: int
    random_counter_used: int


@dataclass(frozen=True)
class TimeAdvancedEvent(EncounterEvent):
    elapsed_seconds: int
    activity_type: RestActivityType


@dataclass(frozen=True)
class ShortRestStartedEvent(EncounterEvent):
    actor_id: str
    started_at_seconds: int


@dataclass(frozen=True)
class ShortRestInterruptedEvent(EncounterEvent):
    actor_id: str
    reason: RestInterruptionReason
    accumulated_rest_seconds: int


@dataclass(frozen=True)
class ShortRestCompletedEvent(EncounterEvent):
    actor_id: str
    completed_at_seconds: int


@dataclass(frozen=True)
class LongRestStartedEvent(EncounterEvent):
    actor_id: str
    started_at_seconds: int
    required_rest_seconds: int


@dataclass(frozen=True)
class LongRestInterruptedEvent(EncounterEvent):
    actor_id: str
    reason: RestInterruptionReason
    accumulated_rest_seconds: int
    interruption_count: int
    granted_short_rest_benefits: bool


@dataclass(frozen=True)
class LongRestResumedEvent(EncounterEvent):
    actor_id: str
    resumed_at_seconds: int
    required_rest_seconds: int


@dataclass(frozen=True)
class LongRestCompletedEvent(EncounterEvent):
    actor_id: str
    completed_at_seconds: int


@dataclass(frozen=True)
class HitPointDieSpentEvent(EncounterEvent):
    actor_id: str
    die_faces: int
    roll: int
    constitution_modifier: int
    hit_points_gained: int
    remaining_hit_dice: int
    random_counter_used: int


@dataclass(frozen=True)
class HitPointDiceRestoredEvent(EncounterEvent):
    actor_id: str
    remaining_hit_dice: int


@dataclass(frozen=True)
class HitPointsRecoveredFromRestEvent(EncounterEvent):
    actor_id: str
    amount_recovered: int
    current_hit_points_after: int


@dataclass(frozen=True)
class SpellSlotsRecoveredFromRestEvent(EncounterEvent):
    actor_id: str
    resource_id: str
    current_after: int
    maximum: int


@dataclass(frozen=True)
class ResourceRecoveredFromRestEvent(EncounterEvent):
    actor_id: str
    resource_id: str
    category: str
    amount_recovered: int
    current_after: int
    maximum: int


@dataclass(frozen=True)
class ItemChargesRecoveredFromRestEvent(EncounterEvent):
    actor_id: str
    resource_id: str
    amount_recovered: int
    current_after: int
    maximum: int


@dataclass(frozen=True)
class ExhaustionReducedFromRestEvent(EncounterEvent):
    actor_id: str
    exhaustion_level_after: int


@dataclass(frozen=True)
class RestDeniedEvent(EncounterEvent):
    actor_id: str | None
    rest_type: RestType
    reason: str


@dataclass(frozen=True)
class RestLockoutAppliedEvent(EncounterEvent):
    actor_id: str
    available_at_seconds: int


@dataclass(frozen=True)
class MovementModeSelectedEvent(EncounterEvent):
    actor_id: str
    movement_mode: TraversalMode
    movement_cost_ft: int
    remaining_movement_ft_after: int


@dataclass(frozen=True)
class MovementSpentEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int
    remaining_movement_ft: int
    movement_mode: TraversalMode = TraversalMode.WALK
    movement_spent_ft: int | None = None
    consume_turn_movement: bool = True


@dataclass(frozen=True)
class MountedActorEvent(EncounterEvent):
    actor_id: str
    mount_actor_id: str


@dataclass(frozen=True)
class DismountedActorEvent(EncounterEvent):
    actor_id: str
    mount_actor_id: str
    reason: str


@dataclass(frozen=True)
class SharedSensesStartedEvent(EncounterEvent):
    actor_id: str
    familiar_actor_id: str


@dataclass(frozen=True)
class SharedSensesEndedEvent(EncounterEvent):
    actor_id: str
    familiar_actor_id: str | None
    reason: str


@dataclass(frozen=True)
class ReadyDeclaredEvent(EncounterEvent):
    actor_id: str
    ready_state: ReadiedActionState
    detail: str = ''


@dataclass(frozen=True)
class ReadyExpiredEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class ReadyTriggeredEvent(EncounterEvent):
    actor_id: str
    trigger_actor_id: str
    response_kind: str


@dataclass(frozen=True)
class ReadiedActionIgnoredEvent(EncounterEvent):
    actor_id: str
    trigger_actor_id: str


@dataclass(frozen=True)
class StartOfTurnTriggersQueuedEvent(EncounterEvent):
    queue: PendingTimingQueueState


@dataclass(frozen=True)
class EndOfTurnTriggersQueuedEvent(EncounterEvent):
    queue: PendingTimingQueueState


@dataclass(frozen=True)
class SimultaneousEffectsDetectedEvent(EncounterEvent):
    actor_id: str
    phase: TriggerTiming
    entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class SimultaneousEffectsOrderedEvent(EncounterEvent):
    actor_id: str
    phase: TriggerTiming
    chosen_entry_id: str
    remaining_entry_ids: tuple[str, ...]


@dataclass(frozen=True)
class TurnInterruptedEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class TurnResumedEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class ReactionWindowOpenedEvent(EncounterEvent):
    window: ReactionWindowState


@dataclass(frozen=True)
class ReactionChosenEvent(EncounterEvent):
    trigger_id: str
    actor_id: str
    option_id: str


@dataclass(frozen=True)
class ReactionSubmittedEvent(EncounterEvent):
    trigger_id: str
    actor_id: str
    option_id: str


@dataclass(frozen=True)
class ReactionRejectedEvent(EncounterEvent):
    trigger_id: str
    actor_id: str
    option_id: str
    reason: str


@dataclass(frozen=True)
class ReactionResolvedEvent(EncounterEvent):
    trigger_id: str
    actor_id: str
    option_id: str


@dataclass(frozen=True)
class ReadiedSpellDissipatedEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    reason: str


@dataclass(frozen=True)
class TriggerResolutionCompletedEvent(EncounterEvent):
    actor_id: str
    phase: TriggerTiming
    entry_id: str


@dataclass(frozen=True)
class AttackRollRequestedEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    target_id: str


@dataclass(frozen=True)
class AttackRolledEvent(EncounterEvent):
    actor_id: str
    attack_id: str
    target_id: str
    attack_rolls: tuple[int, ...]
    attack_total: int
    random_counter_used: int


@dataclass(frozen=True)
class AttackHitEvent(EncounterEvent):
    actor_id: str
    attack_id: str
    target_id: str


@dataclass(frozen=True)
class AttackMissedEvent(EncounterEvent):
    actor_id: str
    attack_id: str
    target_id: str


@dataclass(frozen=True)
class DamageRolledEvent(EncounterEvent):
    actor_id: str
    attack_id: str | None
    target_id: str
    damage_rolls: tuple[int, ...]
    damage_total: int
    damage_type: str
    random_counter_used: int


@dataclass(frozen=True)
class DamageAppliedEvent(EncounterEvent):
    source_actor_id: str
    target_id: str
    damage_total: int
    applied_damage_total: int
    target_hit_points_after: int
    target_temp_hit_points_after: int
    damage_type: str
    critical_hit: bool = False
    random_counter_used: int | None = None


@dataclass(frozen=True)
class SneakAttackAppliedEvent(EncounterEvent):
    actor_id: str
    target_id: str
    damage_rolls: tuple[int, ...]
    damage_total: int
    damage_type: str
    current_round_number: int
    current_turn_actor_id: str | None
    random_counter_used: int
    critical_hit: bool = False


@dataclass(frozen=True)
class SupportStateEvaluatedEvent(EncounterEvent):
    actor_id: str
    support_state: SupportStateType
    position: GridPosition
    detail: str = ''


@dataclass(frozen=True)
class AirborneStateChangedEvent(EncounterEvent):
    actor_id: str
    from_state: SupportStateType
    to_state: SupportStateType


@dataclass(frozen=True)
class RelocationResolvedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    relocation_type: RelocationType
    movement_mode: TraversalMode


@dataclass(frozen=True)
class FallStartedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    reason: FallReason


@dataclass(frozen=True)
class FallDistanceComputedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int


@dataclass(frozen=True)
class FallLandedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    landing_surface_type: LandingSurfaceType


@dataclass(frozen=True)
class FallDamageRolledEvent(EncounterEvent):
    actor_id: str
    distance_ft: int
    damage_rolls: tuple[int, ...]
    damage_total: int
    random_counter_used: int


@dataclass(frozen=True)
class FallDamageAppliedEvent(EncounterEvent):
    actor_id: str
    damage_total: int
    applied_damage_total: int
    target_hit_points_after: int
    target_temp_hit_points_after: int
    damage_type: str
    critical_hit: bool = False


@dataclass(frozen=True)
class ProneAppliedFromFallEvent(EncounterEvent):
    actor_id: str


@dataclass(frozen=True)
class TeleportDeclaredEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int


@dataclass(frozen=True)
class TeleportResolvedEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    from_position: GridPosition
    to_position: GridPosition
    distance_ft: int


@dataclass(frozen=True)
class PositionChangedEvent(EncounterEvent):
    actor_id: str
    from_position: GridPosition
    to_position: GridPosition
    relocation_type: RelocationType
    movement_mode: TraversalMode


@dataclass(frozen=True)
class SpellCastEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    action_cost: str
    from_position: GridPosition
    to_position: GridPosition | None = None
    target_id: str | None = None
    remaining_uses: int | None = None
    resource_pool_id: str | None = None
    resource_pool_current_after: int | None = None


@dataclass(frozen=True)
class CapabilityDeclaredEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    capability_name: str
    action_cost: str
    target_id: str | None = None
    point: GridPosition | None = None
    runtime_option_id: str | None = None
    remaining_uses: int | None = None


@dataclass(frozen=True)
class CapabilityRechargeRolledEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    roll: int
    recharge_min_roll: int
    recharged: bool
    random_counter_used: int


@dataclass(frozen=True)
class TargetsResolvedEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    target_ids: tuple[str, ...]


@dataclass(frozen=True)
class AreaResolvedEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    area_shape: AreaShape
    origin: GridPosition
    size_ft: int
    target_ids: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityHitEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    target_id: str


@dataclass(frozen=True)
class CapabilityMissedEvent(EncounterEvent):
    actor_id: str
    capability_id: str
    target_id: str


@dataclass(frozen=True)
class HealingAppliedEvent(EncounterEvent):
    source_actor_id: str
    target_id: str
    healing_total: int
    target_hit_points_after: int


@dataclass(frozen=True)
class HitPointsDroppedToZeroEvent(EncounterEvent):
    actor_id: str
    source_actor_id: str | None
    damage_type: str
    damage_to_hit_points: int


@dataclass(frozen=True)
class InstantDeathTriggeredEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class UnconsciousAtZeroAppliedEvent(EncounterEvent):
    actor_id: str
    source_actor_id: str | None = None
    reason: str = ''


@dataclass(frozen=True)
class DeathSaveRequestedEvent(EncounterEvent):
    actor_id: str
    dc: int


@dataclass(frozen=True)
class DeathSaveRolledEvent(EncounterEvent):
    actor_id: str
    rolls: tuple[int, ...]
    selected_roll: int
    total: int
    random_counter_used: int


@dataclass(frozen=True)
class DeathSaveSucceededEvent(EncounterEvent):
    actor_id: str
    total_successes: int


@dataclass(frozen=True)
class DeathSaveFailedEvent(EncounterEvent):
    actor_id: str
    total_failures: int
    failures_added: int
    reason: str


@dataclass(frozen=True)
class DeathSaveNaturalOneEvent(EncounterEvent):
    actor_id: str


@dataclass(frozen=True)
class DeathSaveNaturalTwentyEvent(EncounterEvent):
    actor_id: str


@dataclass(frozen=True)
class StabilizedEvent(EncounterEvent):
    actor_id: str
    reason: str
    stabilized_by_actor_id: str | None = None
    recovery_hours: int | None = None
    random_counter_used: int | None = None


@dataclass(frozen=True)
class StableBrokenByDamageEvent(EncounterEvent):
    actor_id: str
    source_actor_id: str | None = None
    reason: str = 'damage-at-zero'


@dataclass(frozen=True)
class DiedEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class HealedFromZeroEvent(EncounterEvent):
    actor_id: str
    source_actor_id: str
    hit_points_after: int


@dataclass(frozen=True)
class TemporaryHitPointsAppliedEvent(EncounterEvent):
    source_actor_id: str | None
    target_id: str
    temp_hit_points_total: int


@dataclass(frozen=True)
class TemporaryHitPointsReceivedAtZeroEvent(EncounterEvent):
    actor_id: str
    temp_hit_points_after: int


@dataclass(frozen=True)
class ForcedMovementAppliedEvent(EncounterEvent):
    actor_id: str
    target_id: str
    final_position: GridPosition
    moved_distance_ft: int


@dataclass(frozen=True)
class ArmorClassAdjustedEvent(EncounterEvent):
    actor_id: str
    effect_instance_id: str
    delta: int
    reason: str


@dataclass(frozen=True)
class HitPointMaximumAdjustedEvent(EncounterEvent):
    actor_id: str
    effect_instance_id: str
    delta: int
    adjust_current_by_same_delta: bool = True
    reason: str = ''


@dataclass(frozen=True)
class ActiveEffectStartedEvent(EncounterEvent):
    effect: ActiveEffectState


@dataclass(frozen=True)
class ActiveEffectTickedEvent(EncounterEvent):
    effect_instance_id: str
    actor_id: str
    timing: TriggerTiming
    detail: str = ''


@dataclass(frozen=True)
class ActiveEffectEndedEvent(EncounterEvent):
    effect_instance_id: str
    reason: str


@dataclass(frozen=True)
class PersistentEffectStartedEvent(EncounterEvent):
    persistent_effect: PersistentEffectState


@dataclass(frozen=True)
class PersistentEffectEndedEvent(EncounterEvent):
    persistent_effect_id: str
    family: PersistentEffectFamily
    reason: str


@dataclass(frozen=True)
class CreatedCreatureSpawnedEvent(EncounterEvent):
    creature: SummonedCreatureState


@dataclass(frozen=True)
class CreatedCreatureRemovedEvent(EncounterEvent):
    summon_id: str
    reason: str


@dataclass(frozen=True)
class CreatedObjectSpawnedEvent(EncounterEvent):
    created_object: CreatedObjectState


@dataclass(frozen=True)
class CreatedObjectRemovedEvent(EncounterEvent):
    object_id: str
    reason: str


@dataclass(frozen=True)
class IllusionCreatedEvent(EncounterEvent):
    illusion: IllusionState


@dataclass(frozen=True)
class IllusionRevealedToObserverEvent(EncounterEvent):
    illusion_id: str
    observer_id: str


@dataclass(frozen=True)
class IllusionDisbelievedByObserverEvent(EncounterEvent):
    illusion_id: str
    observer_id: str


@dataclass(frozen=True)
class IllusionInteractedWithEvent(EncounterEvent):
    illusion_id: str
    observer_id: str
    interaction_kind: str


@dataclass(frozen=True)
class DetectionPayloadProducedEvent(EncounterEvent):
    payload: InformationalPayloadState


@dataclass(frozen=True)
class DivinationPayloadProducedEvent(EncounterEvent):
    payload: InformationalPayloadState


@dataclass(frozen=True)
class RitualCastStartedEvent(EncounterEvent):
    ritual: RitualCastingState


@dataclass(frozen=True)
class RitualCastCompletedEvent(EncounterEvent):
    ritual_id: str
    actor_id: str
    capability_id: str


@dataclass(frozen=True)
class PersistentAreaCreatedEvent(EncounterEvent):
    area: PersistentAreaState


@dataclass(frozen=True)
class PersistentAreaTickedEvent(EncounterEvent):
    area_id: str
    timing: TriggerTiming
    actor_ids: tuple[str, ...]


@dataclass(frozen=True)
class PersistentAreaEndedEvent(EncounterEvent):
    area_id: str
    reason: str


@dataclass(frozen=True)
class ConcentrationStartedEvent(EncounterEvent):
    actor_id: str
    effect_instance_id: str


@dataclass(frozen=True)
class ConcentrationEndedEvent(EncounterEvent):
    actor_id: str
    effect_instance_id: str
    reason: str


@dataclass(frozen=True)
class ConditionAddedEvent(EncounterEvent):
    actor_id: str
    instance: ConditionInstance


@dataclass(frozen=True)
class ConditionRemovedEvent(EncounterEvent):
    actor_id: str
    condition_type: ConditionType | None = None
    instance_id: str | None = None


@dataclass(frozen=True)
class ConcentrationBrokenEvent(EncounterEvent):
    actor_id: str
    effect_id: str
    reason: str


@dataclass(frozen=True)
class StoodFromProneEvent(EncounterEvent):
    actor_id: str
    movement_cost_ft: int
    remaining_movement_ft: int
    movement_spent_ft: int | None = None


@dataclass(frozen=True)
class TurnEndedEvent(EncounterEvent):
    actor_id: str
    next_actor_id: str
    round_number: int


@dataclass(frozen=True)
class EncounterCompletedEvent(EncounterEvent):
    winning_side: ActorSide


@dataclass(frozen=True)
class ModeSwitchRequestedEvent(EncounterEvent):
    action: ModeSwitchAction
    from_mode: RuntimeMode
    rationale: str


@dataclass(frozen=True)
class EnterCombatPlannedEvent(EncounterEvent):
    plan: EnterCombatPlan


@dataclass(frozen=True)
class CombatStartedEvent(EncounterEvent):
    participant_actor_ids: tuple[str, ...]
    initiative_order: tuple[str, ...]
    rationale: str


@dataclass(frozen=True)
class CombatEndedEvent(EncounterEvent):
    rationale: str


@dataclass(frozen=True)
class HostileEscalationEvaluatedEvent(EncounterEvent):
    decision: HostileEscalationDecision


@dataclass(frozen=True)
class HostileEscalationTriggeredEvent(EncounterEvent):
    decision: HostileEscalationDecision


@dataclass(frozen=True)
class StoryNPCCombatantSynthesizedEvent(EncounterEvent):
    combatant: SynthesizedCombatantSpec


@dataclass(frozen=True)
class StoryNPCCombatantFallbackUsedEvent(EncounterEvent):
    combatant: SynthesizedCombatantSpec


@dataclass(frozen=True)
class AdHocEncounterSceneSynthesizedEvent(EncounterEvent):
    scene_plan: AdHocEncounterScenePlan


@dataclass(frozen=True)
class ReinforcementScheduledEvent(EncounterEvent):
    schedule: ReinforcementPlan


@dataclass(frozen=True)
class ReinforcementEnteredEvent(EncounterEvent):
    reinforcement_id: str
    actor_ids: tuple[str, ...]
    round_number: int
    entry_zone_id: str


@dataclass(frozen=True)
class StorySceneCommittedToCombatEvent(EncounterEvent):
    context: CombatTransitionState


@dataclass(frozen=True)
class SurpriseEvaluationTriggeredEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class SurpriseStateComputedEvent(EncounterEvent):
    surprised_actor_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class CombatStartedFromStorySceneEvent(EncounterEvent):
    scene_id: str | None
    location_id: str | None
    participant_actor_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class ReturnedToStorytellingEvent(EncounterEvent):
    scene_id: str | None
    rationale: str


@dataclass(frozen=True)
class LLMConfigLoadedEvent(EncounterEvent):
    base_url: str
    model: str


@dataclass(frozen=True)
class LLMRequestIssuedEvent(EncounterEvent):
    purpose: str
    model: str


@dataclass(frozen=True)
class LLMResponseAcceptedEvent(EncounterEvent):
    purpose: str
    response_kind: str


@dataclass(frozen=True)
class AdjudicationRequestedEvent(EncounterEvent):
    controller_id: str
    actor_id: str
    runtime_mode: RuntimeMode
    declaration: str


@dataclass(frozen=True)
class AdjudicationContextBuiltEvent(EncounterEvent):
    actor_id: str
    runtime_mode: RuntimeMode
    scene_id: str | None
    location_id: str | None
    document_ids: tuple[str, ...]


@dataclass(frozen=True)
class AdjudicationPlanReceivedEvent(EncounterEvent):
    actor_id: str
    plan: AdjudicationPlan


@dataclass(frozen=True)
class AdjudicationPlanValidatedEvent(EncounterEvent):
    actor_id: str
    plan: AdjudicationPlan


@dataclass(frozen=True)
class AdjudicationPlanRejectedEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class ClarificationRequestedEvent(EncounterEvent):
    actor_id: str
    question_to_player: str
    missing_parameters: tuple[str, ...]


@dataclass(frozen=True)
class ImprovisedObjectCreatedEvent(EncounterEvent):
    feature_id: str
    template_id: str
    anchor: GridPosition


@dataclass(frozen=True)
class TerrainEffectCreatedEvent(EncounterEvent):
    feature_id: str
    template_id: str
    anchor: GridPosition


@dataclass(frozen=True)
class ImprovisedObjectDestroyedEvent(EncounterEvent):
    feature_id: str


@dataclass(frozen=True)
class TerrainEffectEndedEvent(EncounterEvent):
    feature_id: str


@dataclass(frozen=True)
class CoverStateModifiedEvent(EncounterEvent):
    attacker_id: str
    target_id: str
    cover_level: CoverLevel


@dataclass(frozen=True)
class DMCheckIssuedEvent(EncounterEvent):
    request_id: str
    actor_id: str
    ability: Ability
    skill_name: str | None
    dc: int


@dataclass(frozen=True)
class DMSaveIssuedEvent(EncounterEvent):
    source_actor_id: str
    target_actor_ids: tuple[str, ...]
    ability: Ability
    dc: int


@dataclass(frozen=True)
class DMContestIssuedEvent(EncounterEvent):
    actor_a_id: str
    actor_b_id: str
    reason: str


@dataclass(frozen=True)
class DMModeSwitchRecommendedEvent(EncounterEvent):
    recommendation: AdjudicationModeSwitchRecommendation


@dataclass(frozen=True)
class AdjudicatedActionResolvedEvent(EncounterEvent):
    actor_id: str
    adjudication_type: AdjudicationType
    outcome: str


@dataclass(frozen=True)
class StoryActionDeclaredEvent(EncounterEvent):
    controller_id: str
    actor_id: str
    declaration: str


@dataclass(frozen=True)
class StoryTranscriptAppendedEvent(EncounterEvent):
    entries: tuple[StoryTranscriptEntry, ...]


@dataclass(frozen=True)
class StoryCheckPromptedEvent(EncounterEvent):
    request: StoryCheckRequestState


@dataclass(frozen=True)
class StoryCheckResolvedEvent(EncounterEvent):
    request_id: str
    actor_id: str
    scene_id: str | None
    ability: Ability
    skill_name: str | None
    dc: int
    selected_roll: int
    total: int
    success: bool
    interacting_with_actor_id: str | None = None


@dataclass(frozen=True)
class StorySceneUpdatedEvent(EncounterEvent):
    scene_id: str | None = None
    location_id: str | None = None
    summary: str | None = None


@dataclass(frozen=True)
class StoryModeSpellcastDeclaredEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    scene_id: str | None
    location_id: str | None
    ritual_cast: bool = False
    target_id: str | None = None


@dataclass(frozen=True)
class StoryModeSpellcastValidatedEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    casting_time_seconds: int
    ritual_cast: bool = False


@dataclass(frozen=True)
class StoryModeSpellcastingPerceivedEvent(EncounterEvent):
    observer_id: str
    observer_kind: StoryWitnessKind
    spell_id: str
    confidence: SpellcastingObservationConfidence
    concern_level: SpellcastingConcernLevel


@dataclass(frozen=True)
class StoryModeSpellEffectPerceivedEvent(EncounterEvent):
    observer_id: str
    observer_kind: StoryWitnessKind
    spell_id: str
    awareness: StorySpellObserverAwareness


@dataclass(frozen=True)
class SpellcastingWitnessPacketCreatedEvent(EncounterEvent):
    packet: WitnessObservationPacket


@dataclass(frozen=True)
class SpellcastingSocialReactionResolvedEvent(EncounterEvent):
    plan: SpellcastingSocialReactionPlan

@dataclass(frozen=True)
class SocialIncidentLoggedEvent(EncounterEvent):
    incident: SocialIncident


@dataclass(frozen=True)
class WitnessObservedIncidentEvent(EncounterEvent):
    memory: WitnessMemoryState


@dataclass(frozen=True)
class WitnessArchetypeResolvedEvent(EncounterEvent):
    incident_id: str
    witness_id: str
    archetype_id: str
    label: str


@dataclass(frozen=True)
class NormProfileResolvedEvent(EncounterEvent):
    incident_id: str
    witness_id: str
    norm_ids: tuple[str, ...]


@dataclass(frozen=True)
class IncidentConsequenceTemplateSelectedEvent(EncounterEvent):
    incident_id: str
    template_id: str
    summary: str


@dataclass(frozen=True)
class WitnessReactionEvaluatedEvent(EncounterEvent):
    incident_id: str
    witness_id: str
    reaction_category: WitnessReactionCategory
    summary: str


@dataclass(frozen=True)
class WitnessInterpretationResolvedEvent(EncounterEvent):
    record: IncidentInterpretationRecord


@dataclass(frozen=True)
class SocialConsequenceAppliedEvent(EncounterEvent):
    incident_id: str
    target_kind: str
    target_id: str
    summary: str


@dataclass(frozen=True)
class ImmediateSocialConsequenceAppliedEvent(EncounterEvent):
    incident_id: str
    template_id: str
    target_kind: str
    target_id: str
    summary: str


@dataclass(frozen=True)
class MagicalNormConsultedEvent(EncounterEvent):
    observer_id: str
    norm_id: str
    norm_tags: tuple[str, ...]

@dataclass(frozen=True)
class StoryModeSpellcastIgnoredEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    reason: str


@dataclass(frozen=True)
class StoryModeSpellcastCausedSuspicionEvent(EncounterEvent):
    witness_id: str
    spell_id: str
    reaction_category: SpellcastingReactionCategory


@dataclass(frozen=True)
class StoryModeSpellcastEscalationRecommendedEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    decision: StoryModeCastEscalationDecision


@dataclass(frozen=True)
class StoryModeSpellcastResolvedEvent(EncounterEvent):
    resolution: StoryModeCastResolution


@dataclass(frozen=True)
class StoryModeSpellcastRejectedEvent(EncounterEvent):
    actor_id: str
    spell_id: str
    reason: str


@dataclass(frozen=True)
class HostileEscalationEvaluatedEvent(EncounterEvent):
    decision: HostileEscalationDecision


@dataclass(frozen=True)
class HostileEscalationTriggeredEvent(EncounterEvent):
    decision: HostileEscalationDecision


@dataclass(frozen=True)
class StoryNPCCombatantSynthesizedEvent(EncounterEvent):
    combatant: SynthesizedCombatantSpec


@dataclass(frozen=True)
class StoryNPCCombatantFallbackUsedEvent(EncounterEvent):
    combatant: SynthesizedCombatantSpec


@dataclass(frozen=True)
class AdHocEncounterSceneSynthesizedEvent(EncounterEvent):
    scene_plan: AdHocEncounterScenePlan


@dataclass(frozen=True)
class ReinforcementScheduledEvent(EncounterEvent):
    schedule: ReinforcementPlan


@dataclass(frozen=True)
class ReinforcementEnteredEvent(EncounterEvent):
    reinforcement_id: str
    actor_ids: tuple[str, ...]
    round_number: int
    entry_zone_id: str


@dataclass(frozen=True)
class StorySceneCommittedToCombatEvent(EncounterEvent):
    context: CombatTransitionState


@dataclass(frozen=True)
class SurpriseEvaluationTriggeredEvent(EncounterEvent):
    actor_id: str
    reason: str


@dataclass(frozen=True)
class SurpriseStateComputedEvent(EncounterEvent):
    surprised_actor_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class CombatStartedFromStorySceneEvent(EncounterEvent):
    scene_id: str | None
    location_id: str | None
    participant_actor_ids: tuple[str, ...]
    reason: str


@dataclass(frozen=True)
class HexMapLoadedEvent(EncounterEvent):
    map_id: str
    region_id: str


@dataclass(frozen=True)
class TravelStartedEvent(EncounterEvent):
    map_id: str
    start_coord: HexCoord
    destination: HexCoord | None


@dataclass(frozen=True)
class TravelRoutePlannedEvent(EncounterEvent):
    route: PlannedTravelRoute


@dataclass(frozen=True)
class TravelStepAdvancedEvent(EncounterEvent):
    map_id: str
    from_coord: HexCoord
    to_coord: HexCoord
    minutes_elapsed: int
    total_elapsed_minutes: int


@dataclass(frozen=True)
class TravelInterruptedEvent(EncounterEvent):
    map_id: str
    reason: str
    hook_id: str | None = None


@dataclass(frozen=True)
class TravelResumedEvent(EncounterEvent):
    map_id: str
    current_coord: HexCoord


@dataclass(frozen=True)
class TravelPaceChangedEvent(EncounterEvent):
    old_pace: TravelPace
    new_pace: TravelPace


@dataclass(frozen=True)
class HexDiscoveredEvent(EncounterEvent):
    coord: HexCoord


@dataclass(frozen=True)
class LandmarkDiscoveredEvent(EncounterEvent):
    landmark_id: str
    name: str
    coord: HexCoord


@dataclass(frozen=True)
class LocationReachedEvent(EncounterEvent):
    location_id: str
    name: str
    coord: HexCoord


@dataclass(frozen=True)
class TravelEventHookTriggeredEvent(EncounterEvent):
    hook: TravelHookDefinition


@dataclass(frozen=True)
class TravelModeProjectionUpdatedEvent(EncounterEvent):
    map_id: str
    status: TravelStatus


@dataclass(frozen=True)
class MarchingOrderUpdatedEvent(EncounterEvent):
    entries: tuple[MarchingOrderEntry, ...]


@dataclass(frozen=True)
class WatchOrderUpdatedEvent(EncounterEvent):
    assignments: tuple[WatchAssignment, ...]


@dataclass(frozen=True)
class ExplorationProcedureStartedEvent(EncounterEvent):
    procedure_id: str
    title: str
    category: ProcedureCategory
    actor_id: str
    summary: str


@dataclass(frozen=True)
class ExplorationProcedureProgressedEvent(EncounterEvent):
    procedure_id: str
    title: str
    category: ProcedureCategory
    actor_id: str
    status: ProcedureStatus
    progress_points: int
    required_progress_points: int
    summary: str


@dataclass(frozen=True)
class ExplorationProcedureCompletedEvent(EncounterEvent):
    procedure_id: str
    title: str
    category: ProcedureCategory
    actor_id: str
    summary: str


@dataclass(frozen=True)
class ToolUseDeclaredEvent(EncounterEvent):
    actor_id: str
    tool_name: str
    target_id: str
    target_category: ProcedureCategory


@dataclass(frozen=True)
class ToolUseResolvedEvent(EncounterEvent):
    actor_id: str
    tool_name: str
    target_id: str
    target_category: ProcedureCategory
    outcome: ProcedureOutcome
    summary: str


@dataclass(frozen=True)
class SocialInfluenceAttemptedEvent(EncounterEvent):
    actor_id: str
    npc_id: str
    approach: SocialApproachType
    dc: int
    selected_roll: int
    total: int
    random_counter_used: int


@dataclass(frozen=True)
class SocialInfluenceResolvedEvent(EncounterEvent):
    actor_id: str
    npc_id: str
    approach: SocialApproachType
    outcome: SocialOutcome
    summary: str


@dataclass(frozen=True)
class NPCStanceChangedEvent(EncounterEvent):
    npc_id: str
    old_attitude: NpcAttitude
    new_attitude: NpcAttitude
    current_stance: str
    summary: str

@dataclass(frozen=True)
class NPCAttitudeChangedEvent(EncounterEvent):
    npc_id: str
    old_attitude: NpcAttitude
    new_attitude: NpcAttitude
    summary: str


@dataclass(frozen=True)
class NPCTrustChangedEvent(EncounterEvent):
    npc_id: str
    old_value: int
    new_value: int
    summary: str


@dataclass(frozen=True)
class NPCSuspicionChangedEvent(EncounterEvent):
    npc_id: str
    old_value: int
    new_value: int
    summary: str


@dataclass(frozen=True)
class ReputationChangedEvent(EncounterEvent):
    holder_id: str
    holder_label: str
    summary: str
    suspicion: int
    respect: int
    fear: int
    trust: int


@dataclass(frozen=True)
class FactionRelationshipChangedEvent(EncounterEvent):
    faction_id: str
    faction_label: str
    summary: str
    suspicion: int
    respect: int
    fear: int
    trust: int


@dataclass(frozen=True)
class SocialPropagationScheduledEvent(EncounterEvent):
    task: SocialPropagationTask


@dataclass(frozen=True)
class PropagationChainScheduledEvent(EncounterEvent):
    incident_id: str
    chain_id: str
    target_id: str
    summary: str


@dataclass(frozen=True)
class SocialPropagationExecutedEvent(EncounterEvent):
    task_id: str
    incident_id: str
    target_id: str
    summary: str


@dataclass(frozen=True)
class PropagationChainExecutedEvent(EncounterEvent):
    incident_id: str
    chain_id: str
    target_id: str
    summary: str


@dataclass(frozen=True)
class FactionMemoryUpdatedEvent(EncounterEvent):
    faction_id: str
    summary: str


@dataclass(frozen=True)
class AuthorityAttentionRaisedEvent(EncounterEvent):
    authority_id: str
    location_id: str | None
    summary: str


@dataclass(frozen=True)
class KnownConsequenceProjectionUpdatedEvent(EncounterEvent):
    projection_id: str
    audience: str
    summary: str


@dataclass(frozen=True)
class InfluenceRetryCooldownSetEvent(EncounterEvent):
    cooldown: InfluenceRetryCooldown


@dataclass(frozen=True)
class SocialStateProjectionUpdatedEvent(EncounterEvent):
    scene_id: str | None
    location_id: str | None

@dataclass(frozen=True)
class TrapDetectedEvent(EncounterEvent):
    trap_id: str
    title: str
    actor_id: str | None
    passive: bool
    status: TrapStatus
    summary: str


@dataclass(frozen=True)
class TrapTriggeredEvent(EncounterEvent):
    trap_id: str
    title: str
    actor_id: str | None
    summary: str


@dataclass(frozen=True)
class TrapDisarmedEvent(EncounterEvent):
    trap_id: str
    title: str
    actor_id: str
    summary: str


@dataclass(frozen=True)
class PuzzleProgressedEvent(EncounterEvent):
    puzzle_id: str
    title: str
    actor_id: str
    status: PuzzleStatus
    summary: str


@dataclass(frozen=True)
class PuzzleSolvedEvent(EncounterEvent):
    puzzle_id: str
    title: str
    actor_id: str
    summary: str


@dataclass(frozen=True)
class DiscoveryRevealedEvent(EncounterEvent):
    discovery_id: str
    text: str
    source_category: ProcedureCategory
    actor_id: str | None
    public: bool = True


@dataclass(frozen=True)
class DowntimeProjectStartedEvent(EncounterEvent):
    project_id: str
    activity_id: str
    actor_id: str
    title: str


@dataclass(frozen=True)
class DowntimeProjectProgressedEvent(EncounterEvent):
    project_id: str
    activity_id: str
    actor_id: str
    status: DowntimeProjectStatus
    elapsed_hours: int
    summary: str


@dataclass(frozen=True)
class DowntimeProjectCompletedEvent(EncounterEvent):
    project_id: str
    activity_id: str
    actor_id: str
    elapsed_hours: int
    summary: str


@dataclass(frozen=True)
class ExplorationStateProjectionUpdatedEvent(EncounterEvent):
    mode: str
    scene_id: str | None
    location_id: str | None




@dataclass(frozen=True)
class XPRewardLoggedEvent(EncounterEvent):
    record: XPRewardRecord


@dataclass(frozen=True)
class XPRewardAppliedEvent(EncounterEvent):
    record: XPRewardRecord


@dataclass(frozen=True)
class MilestoneCompletedEvent(EncounterEvent):
    record: MilestoneRecord


@dataclass(frozen=True)
class MilestoneAdvancementGrantedEvent(EncounterEvent):
    record: MilestoneRecord


@dataclass(frozen=True)
class ProgressionEligibilityUpdatedEvent(EncounterEvent):
    actor_id: str
    actor_label: str
    current_level: int
    eligible_level: int
    mode: ProgressionMode
    pending_level_up_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LevelUpQueuedEvent(EncounterEvent):
    record: PendingLevelUpRecord


@dataclass(frozen=True)
class ProgressionProjectionUpdatedEvent(EncounterEvent):
    mode: ProgressionMode
    pending_level_up_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class LevelUpAvailableEvent(EncounterEvent):
    pending_id: str
    actor_id: str
    target_total_level: int


@dataclass(frozen=True)
class AdvancementTransactionStartedEvent(EncounterEvent):
    transaction: AdvancementTransaction


@dataclass(frozen=True)
class AdvancementClassChosenEvent(EncounterEvent):
    transaction_id: str
    actor_id: str
    class_id: str
    target_class_level: int


@dataclass(frozen=True)
class AdvancementValidatedEvent(EncounterEvent):
    transaction_id: str
    actor_id: str
    status: AdvancementValidationStatus
    generated_feature_names: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdvancementChoiceGeneratedEvent(EncounterEvent):
    transaction_id: str
    actor_id: str
    choice: PendingAdvancementChoice


@dataclass(frozen=True)
class AdvancementChoiceResolvedEvent(EncounterEvent):
    transaction_id: str
    actor_id: str
    choice: ResolvedAdvancementChoice


@dataclass(frozen=True)
class AdvancementCommitSucceededEvent(EncounterEvent):
    transaction: AdvancementTransaction


@dataclass(frozen=True)
class AdvancementCommitFailedEvent(EncounterEvent):
    transaction_id: str
    actor_id: str
    status: AdvancementCommitStatus
    reason: str


@dataclass(frozen=True)
class CharacterLevelIncreasedEvent(EncounterEvent):
    actor_id: str
    previous_level: int
    new_level: int


@dataclass(frozen=True)
class ClassLevelIncreasedEvent(EncounterEvent):
    actor_id: str
    class_id: str
    previous_class_level: int
    new_class_level: int


@dataclass(frozen=True)
class HitPointsIncreasedEvent(EncounterEvent):
    actor_id: str
    previous_max_hit_points: int
    new_max_hit_points: int
    gained_hit_points: int


@dataclass(frozen=True)
class ProficiencyBonusUpdatedEvent(EncounterEvent):
    actor_id: str
    previous_proficiency_bonus: int
    new_proficiency_bonus: int


@dataclass(frozen=True)
class FeatureUnlockedEvent(EncounterEvent):
    actor_id: str
    feature_name: str


