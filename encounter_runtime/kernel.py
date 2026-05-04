
from __future__ import annotations

import copy
from dataclasses import replace

from shared_types.battlefield import BattlefieldFeature, CoverLevel, FallReason, LandingSurfaceType, MovementIntentMode, MovementPreviewOutcome, OccupiedVolume, RelocationEffect, RelocationType, SupportStateType, TraversalMode
from shared_types.capabilities import ActiveEffectDefinition, CapabilityKind, DurationAnchor, DurationSpec, EffectDurationType, IllusionInteractionKind, SaveDcSource, StartActiveEffectDef, TargetAffinity, TargetSelectionKind, TriggerTiming
from shared_types.effects import ConditionApplication, CheckRequest, EffectOutcome, EffectResolutionBranch, ForcedMovementEffect, ForcedMovementResult, HazardResolutionRequest, HazardResolutionResult, LiquidEntryMitigationChoice, ResolutionContext, SaveRequest
from shared_types.equipment import AttackInteractionTiming, EnvironmentObjectAction, EquipmentSlot, GroundItemState, ObjectInteractionCostMode, ObjectInteractionKind
from shared_types.spellcasting import SpellRuntimeSupportMode

from shared_types.adjudication import ImprovisedTemplateId
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
from shared_types.encounter_events import (
    ActionDeclaredEvent,
    ActiveEffectEndedEvent,
    ActiveEffectStartedEvent,
    ActiveEffectTickedEvent,
    CreatedCreatureRemovedEvent,
    CreatedCreatureSpawnedEvent,
    CreatedObjectRemovedEvent,
    CreatedObjectSpawnedEvent,
    DetectionPayloadProducedEvent,
    DivinationPayloadProducedEvent,
    IllusionCreatedEvent,
    IllusionDisbelievedByObserverEvent,
    IllusionInteractedWithEvent,
    IllusionRevealedToObserverEvent,
    PersistentAreaCreatedEvent,
    PersistentAreaEndedEvent,
    PersistentAreaTickedEvent,
    PersistentEffectEndedEvent,
    PersistentEffectStartedEvent,
    RitualCastCompletedEvent,
    RitualCastStartedEvent,
    AreaResolvedEvent,
    ArmorClassAdjustedEvent,
    ActionEffectEvent,
    ActionValidatedEvent,
    ActorHiddenEvent,
    ActorRevealedEvent,
    CheckRolledEvent,
    HideAttemptedEvent,
    PassiveNoticeTriggeredEvent,
    SearchAttemptedEvent,
    StudyAttemptedEvent,
    VisibilityStateChangedEvent,
    ForcedMovementStepResolvedEvent,
    HazardResolvedEvent,
    HazardTriggeredEvent,
    LiquidEntryDetectedEvent,
    AttackDeclaredEvent,
    AttackRollRequestedEvent,
    AttackHitEvent,
    AttackMissedEvent,
    AttackRolledEvent,
    CapabilityDeclaredEvent,
    CapabilityRechargeRolledEvent,
    CapabilityHitEvent,
    CapabilityMissedEvent,
    ConcentrationBrokenEvent,
    ConcentrationEndedEvent,
    ConcentrationStartedEvent,
    ConditionAddedEvent,
    ConditionRemovedEvent,
    ContestRolledEvent,
    D20TestRolledEvent,
    EffectRollAppliedEvent,
    DamageAppliedEvent,
    DeathSaveFailedEvent,
    DeathSaveNaturalOneEvent,
    DeathSaveNaturalTwentyEvent,
    DeathSaveRequestedEvent,
    DeathSaveRolledEvent,
    DeathSaveSucceededEvent,
    DiedEvent,
    ForcedMovementAppliedEvent,
    CoverStateModifiedEvent,
    ImprovisedObjectCreatedEvent,
    ImprovisedObjectDestroyedEvent,
    TerrainEffectCreatedEvent,
    TerrainEffectEndedEvent,
    HealedFromZeroEvent,
    HealingAppliedEvent,
    HitPointsDroppedToZeroEvent,
    InstantDeathTriggeredEvent,
    DamageRolledEvent,
    SneakAttackAppliedEvent,
    EncounterCompletedEvent,
    FallDamageAppliedEvent,
    FallDamageRolledEvent,
    FallDistanceComputedEvent,
    FallLandedEvent,
    FallStartedEvent,
    EncounterStartedEvent,
    MoveDeclaredEvent,
    MovementModeSelectedEvent,
    MovementSpentEvent,
    MountedActorEvent,
    DismountedActorEvent,
    SharedSensesStartedEvent,
    SharedSensesEndedEvent,
    PositionChangedEvent,
    ProneAppliedFromFallEvent,
    EndOfTurnTriggersQueuedEvent,
    ReadiedActionIgnoredEvent,
    ReadiedSpellDissipatedEvent,
    ReactionRejectedEvent,
    ReactionResolvedEvent,
    ReactionSubmittedEvent,
    ReadyDeclaredEvent,
    ReadyExpiredEvent,
    ReadyTriggeredEvent,
    SimultaneousEffectsDetectedEvent,
    SimultaneousEffectsOrderedEvent,
    SurpriseStateComputedEvent,
    StartOfTurnTriggersQueuedEvent,
    TriggerResolutionCompletedEvent,
    TurnInterruptedEvent,
    TurnResumedEvent,
    ReactionChosenEvent,
    ReactionWindowOpenedEvent,
    RelocationResolvedEvent,
    ResourceSpentEvent,
    ResourcePoolSpentEvent,
    ResourcePoolRecoveredEvent,
    ResourceRecoveredFromRestEvent,
    RestDeniedEvent,
    RestLockoutAppliedEvent,
    SaveRolledEvent,
    SpellCastEvent,
    SpellSlotsRecoveredFromRestEvent,
    StableBrokenByDamageEvent,
    StabilizedEvent,
    TargetsResolvedEvent,
    TemporaryHitPointsAppliedEvent,
    TemporaryHitPointsReceivedAtZeroEvent,
    StoodFromProneEvent,
    LongRestCompletedEvent,
    LongRestInterruptedEvent,
    LongRestResumedEvent,
    LongRestStartedEvent,
    ShortRestCompletedEvent,
    ShortRestInterruptedEvent,
    ShortRestStartedEvent,
    HitPointDieSpentEvent,
    HitPointDiceRestoredEvent,
    HitPointMaximumAdjustedEvent,
    HitPointsRecoveredFromRestEvent,
    ItemChargesRecoveredFromRestEvent,
    ExhaustionReducedFromRestEvent,
    TimeAdvancedEvent,
    SupportStateEvaluatedEvent,
    AirborneStateChangedEvent,
    TeleportDeclaredEvent,
    TeleportResolvedEvent,
    TurnEndedEvent,
    UnconsciousAtZeroAppliedEvent,
    AmmunitionConsumedEvent,
    AmmunitionMissingEvent,
    ArmorDoffedEvent,
    ArmorDonnedEvent,
    EnvironmentObjectUsedEvent,
    GroundItemCreatedEvent,
    GroundItemRemovedEvent,
    ImprovisedWeaponUsedEvent,
    ItemDrawnEvent,
    ItemDroppedEvent,
    ItemPickedUpEvent,
    ItemConsumedEvent,
    ItemGrantedEvent,
    ItemTransferredEvent,
    InventoryItemReplacedEvent,
    ItemIdentifiedEvent,
    ConsumablesPurifiedEvent,
    ItemStowedEvent,
    ObjectInteractionUsedEvent,
    ShieldDoffedEvent,
    ShieldDonnedEvent,
    UtilizeActionUsedEvent,
    WeaponEquippedEvent,
    WeaponUnequippedEvent,
)
from shared_types.encounter_intents import (
    AttackIntent,
    ReadyIntent,
    CastSpellIntent,
    UseCapabilityIntent,
    AdvanceTimeIntent,
    ChooseReactionIntent,
    ChooseTimingOrderIntent,
    ResolveIllusionInteractionIntent,
    StartRitualCastIntent,
    ContinueTimingIntent,
    DismountActorIntent,
    EndTurnIntent,
    MountActorIntent,
    ShareFamiliarSensesIntent,
    EquipItemIntent,
    EncounterIntent,
    GrappleIntent,
    MoveActorIntent,
    ObjectInteractionIntent,
    ShoveIntent,
    StandFromProneIntent,
    StartEncounterIntent,
    TakeCombatActionIntent,
    SpendHitPointDieIntent,
    ResumeRestIntent,
    StartLongRestIntent,
    StartShortRestIntent,
    UseImprovisedWeaponIntent,
)
from shared_types.encounter_models import (
    ActiveEffectState,
    ActorSide,
    AttackKind,
    AttackProfile,
    AttackUsageKind,
    CombatActionType,
    DyingStateStatus,
    EncounterPhase,
    EncounterSnapshot,
    EncounterState,
    GridPosition,
    PendingAttackState,
    PendingFallState,
    PendingReadyTriggerState,
    PendingResolutionKind,
    PendingResolutionState,
    PendingTimingQueueState,
    ReadyResponseKind,
    ReadyResponseState,
    ReadyTriggerKind,
    ReadyTriggerState,
    TimingEntryKind,
    TimingEntryState,
    PendingMovementState,
    ReactionTriggerType,
    ReactionWindowState,
    ReadiedActionState,
    RitualCastingState,
    RuntimeActorState,
    ShoveOutcome,
    SpellEffectType,
)
from shared_types.errors import EncounterMovementPreviewError, EncounterValidationError
from shared_types.models import Ability, ChoiceView, ItemRecord, slugify
from shared_types.rest import RestActivityType, RestInterruptionReason, RestRecoveryMode, RestState, RestStateStatus, RestType
from shared_types.visibility import ObserverVisibilityState

from rules_engine.encounter_math import grid_distance_ft, roll_damage
from rules_engine.rng import seeded_random
from rules_engine.starter_content import build_item_capability

from .battlefield import BattlefieldRules
from .effect_execution import EncounterEffectExecutor
from .equipment import (
    actor_is_trained_with_armor,
    add_carried_item,
    append_held_item,
    armor_doff_time_seconds,
    default_unarmed_attack,
    armor_don_time_seconds,
    can_hold_item,
    carried_quantity,
    clear_equipped_items,
    compute_equipped_armor_class,
    equip_item_to_slot,
    first_available_hand_slot,
    free_hands,
    hand_slot_for_item,
    hands_used,
    is_item_held,
    item_is_armor,
    item_is_shield,
    item_is_weapon,
    refresh_actor_equipment_state,
    supported_actor_weight_lb,
    required_hand_count,
    remove_carried_item,
    remove_held_item,
    stowed_quantity,
)
from .improvised_templates import instantiate_template_feature, recompute_dynamic_battlefield_state
from .persistent_effects import persistent_area_contains_position, update_illusion_observer_state
from .consumers import EncounterEffectConsumers
from .capabilities import (
    action_spell_choices,
    available_standard_action_choices,
    bonus_action_choices,
    discover_damage_reactions,
    discover_fall_reactions,
    discover_hit_reactions,
    discover_leave_reach_reactions,
    discover_post_hit_reactions,
    discover_ready_reactions,
    feature_action_choices,
    item_action_choices,
)
from .conditions import (
    add_condition,
    apply_damage_modifiers,
    can_take_actions,
    can_take_bonus_actions,
    can_take_reactions,
    get_ability_check_modifiers_or_auto_fail,
    get_attack_roll_modifiers,
    get_condition_state,
    get_dragged_targets,
    get_effective_speed,
    get_initiative_modifiers,
    get_saving_throw_modifiers_or_auto_fail,
    has_condition,
    remove_condition,
    validate_frightened_movement,
    validate_hostile_targeting,
)
from .d20_engine import D20TestEngine, merge_roll_mode
from .visibility import assess_visibility, passive_perception_for_actor, supports_hiding_from_observer


class EncounterKernel:
    def __init__(self, *, seed: str, item_catalog: dict[str, ItemRecord] | None = None, monster_runtime: object | None = None) -> None:
        self.seed = seed
        self.item_catalog = dict(item_catalog or {})
        self.monster_runtime = monster_runtime
        self.d20_engine = D20TestEngine(seed=seed)
        self.battlefield_rules = BattlefieldRules()
        self.effect_consumers = EncounterEffectConsumers(kernel=self)
        self.effect_executor = EncounterEffectExecutor(kernel=self)

    def new_state(self, actors: dict[str, RuntimeActorState], battlefield=None) -> EncounterState:
        state = EncounterState(actors=actors)
        if battlefield is not None:
            state.battlefield = battlefield
        return state

    def snapshot(self, state: EncounterState) -> EncounterSnapshot:
        active_label = state.active_actor_id or 'pending'
        initiative_text = ', '.join(state.initiative_order) or 'pending'
        summary_lines = [
            f'Phase: {state.phase.value}',
            f'Round: {state.round_number or 0}',
            f'Active actor: {active_label}',
            f'Initiative: {initiative_text}',
            f'Clock: {state.clock_seconds} seconds elapsed',
        ]
        if state.pending_reaction_window is not None:
            summary_lines.append(
                f'Reaction window: {state.pending_reaction_window.trigger_type.value} for {state.pending_reaction_window.pending_actor_id}'
            )
            summary_lines.append(f'Reaction prompt: {state.pending_reaction_window.prompt}')
        for actor_id in state.initiative_order or tuple(state.actors):
            actor = state.actors[actor_id]
            condition_text = ', '.join(sorted(condition.value for condition in get_condition_state(actor).effective_types)) or 'none'
            dying_text = ''
            if actor.dying_state.status != DyingStateStatus.ALIVE:
                dying_text = f'; Dying {actor.dying_state.status.value}; Death saves {actor.dying_state.death_save_successes}/{actor.dying_state.death_save_failures}'
            held_text = ','.join(actor.held_item_ids) if actor.held_item_ids else 'none'
            armor_text = actor.worn_armor_item_id or 'none'
            shield_text = actor.worn_shield_item_id or 'none'
            summary_lines.append(
                f"{actor.actor_id}: {actor.name} [{actor.side.value}] HP {actor.current_hit_points}/{actor.max_hit_points}; Temp {actor.temp_hit_points}; AC {actor.effective_armor_class}; Pos ({actor.position.x},{actor.position.y},{actor.position.z}); Move {actor.remaining_movement_ft}; Action {'yes' if actor.action_available else 'no'}; Bonus {'yes' if actor.bonus_action_available else 'no'}; Reaction {'yes' if actor.reaction_available else 'no'}; Object {'yes' if actor.remaining_free_object_interaction else 'no'}; Held {held_text}; Armor {armor_text}; Shield {shield_text}; Disengage {'yes' if actor.disengage_active else 'no'}; Dodge {'yes' if actor.dodge_active else 'no'}; Hidden {'yes' if actor.hidden else 'no'}; Conditions {condition_text}{dying_text}"
            )
        available_choices: dict[str, tuple[ChoiceView, ...]] = {}
        if state.pending_reaction_window is not None:
            available_choices['reactions'] = tuple(
                ChoiceView(option_id=option.option_id, label=option.label, detail=option.detail)
                for option in state.pending_reaction_window.options
            ) + (ChoiceView(option_id='decline', label='Decline', detail='do not use a reaction'),)
            return EncounterSnapshot(phase=state.phase, summary_lines=tuple(summary_lines), available_choices=available_choices)
        if state.active_actor_id is not None and state.active_actor_id in state.actors and state.phase == EncounterPhase.IN_PROGRESS:
            actor = state.actors[state.active_actor_id]
            if can_take_actions(actor):
                available_choices['actions'] = available_standard_action_choices(actor)
                available_choices['attacks'] = tuple(
                    ChoiceView(option_id=attack.attack_id, label=attack.name, detail=f'+{attack.to_hit_bonus} to hit')
                    for attack in actor.attacks.values()
                    if self._attack_is_available_choice(actor, attack)
                )
                magic_choices = action_spell_choices(actor)
                if magic_choices:
                    available_choices['magic'] = magic_choices
                feature_choices = feature_action_choices(actor)
                if feature_choices:
                    available_choices['features'] = feature_choices
                item_choices = item_action_choices(actor)
                if item_choices:
                    available_choices['items'] = item_choices
            if has_condition(actor, ConditionType.PRONE):
                available_choices['movement'] = (ChoiceView(option_id='stand', label='Stand', detail='movement; costs half speed'),)
            derived_bonus_choices = bonus_action_choices(actor) if can_take_bonus_actions(actor) else ()
            if derived_bonus_choices:
                available_choices['bonus_actions'] = derived_bonus_choices
        return EncounterSnapshot(phase=state.phase, summary_lines=tuple(summary_lines), available_choices=available_choices)

    def dispatch(self, state: EncounterState, intent: EncounterIntent) -> EncounterState:
        if state.pending_reaction_window is not None and not isinstance(intent, ChooseReactionIntent):
            raise EncounterValidationError('A reaction window is open and must be resolved before other combat actions continue.')
        if state.pending_timing_queue is not None and not isinstance(intent, (ChooseTimingOrderIntent, ContinueTimingIntent, ChooseReactionIntent)):
            raise EncounterValidationError('A timing-resolution queue is active and must be resolved before other combat actions continue.')
        events = self._resolve_intent(state, intent)
        for event in events:
            self._apply_event(state, event)
        return state

    def resolve_save_consumer(self, state: EncounterState, request: SaveRequest, *, apply: bool = False):
        return self.effect_consumers.resolve_save(state, request, apply=apply)

    def resolve_check_consumer(self, state: EncounterState, request: CheckRequest, *, apply: bool = False):
        return self.effect_consumers.resolve_check(state, request, apply=apply)

    def apply_forced_movement(self, state: EncounterState, effect: ForcedMovementEffect, *, liquid_choice: LiquidEntryMitigationChoice | None = None, apply: bool = True) -> tuple[ForcedMovementResult, list[object]]:
        return self.effect_consumers.apply_forced_movement(state, effect, liquid_choice=liquid_choice, apply=apply)

    def resolve_hazard(self, state: EncounterState, request: HazardResolutionRequest, *, liquid_choice: LiquidEntryMitigationChoice | None = None, apply: bool = True) -> tuple[HazardResolutionResult, list[object]]:
        return self.effect_consumers.resolve_hazard(state, request, liquid_choice=liquid_choice, apply=apply)

    def resolve_saving_throw(self, state: EncounterState, *, actor_id: str, ability: Ability, dc: int, flat_modifier: int = 0, roll_mode: D20RollMode = D20RollMode.NORMAL):
        actor = self._require_actor(state, actor_id)
        modifiers = get_saving_throw_modifiers_or_auto_fail(actor, ability)
        request = D20TestRequest(
            request_id=f'save:{actor_id}:{ability.value}:{state.random_counter}',
            test_type=D20TestType.SAVING_THROW,
            actor_id=actor_id,
            ability=ability,
            flat_modifier=actor.saving_throw_bonuses[ability] + modifiers.modifier + flat_modifier,
            roll_mode=self._combine_roll_modes(merge_roll_mode(advantage=modifiers.advantage, disadvantage=modifiers.disadvantage), roll_mode),
            dc=dc,
            auto_fail=modifiers.auto_fail,
        )
        return self.d20_engine.resolve(request, random_counter=state.random_counter)

    def _combine_roll_modes(self, base_mode: D20RollMode, requested_mode: D20RollMode) -> D20RollMode:
        return merge_roll_mode(
            advantage=(base_mode == D20RollMode.ADVANTAGE or requested_mode == D20RollMode.ADVANTAGE),
            disadvantage=(base_mode == D20RollMode.DISADVANTAGE or requested_mode == D20RollMode.DISADVANTAGE),
        )

    def evaluate_support_state(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        position: GridPosition | None = None,
        reason: FallReason = FallReason.STATE_CHANGE,
    ):
        actor = self._require_actor(state, actor_id)
        return self.battlefield_rules.evaluate_support_state(state, actor, position=position, default_reason=reason)

    def reconcile_support_state(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        reason: FallReason = FallReason.STATE_CHANGE,
        liquid_choice: LiquidEntryMitigationChoice | None = None,
    ) -> list[object]:
        events = self._support_reconciliation_events(state, actor_id=actor_id, reason=reason, liquid_choice=liquid_choice)
        for event in events:
            self._apply_event(state, event)
        return events

    def resolve_ability_check(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        ability: Ability,
        dc: int,
        flat_modifier: int = 0,
        requires_sight: bool = False,
        requires_hearing: bool = False,
        interacting_with_actor_id: str | None = None,
        skill_name: str | None = None,
        roll_mode: D20RollMode = D20RollMode.NORMAL,
    ):
        actor = self._require_actor(state, actor_id)
        modifiers = get_ability_check_modifiers_or_auto_fail(
            actor,
            ability,
            encounter_state=state,
            requires_sight=requires_sight,
            requires_hearing=requires_hearing,
            interacting_with_actor_id=interacting_with_actor_id,
            skill_name=skill_name,
        )
        base_modifier = actor.ability_modifiers[ability]
        if skill_name is not None:
            base_modifier = actor.skill_bonuses.get(skill_name, base_modifier)
        request = D20TestRequest(
            request_id=f'check:{actor_id}:{ability.value}:{state.random_counter}',
            test_type=D20TestType.ABILITY_CHECK,
            actor_id=actor_id,
            ability=ability,
            flat_modifier=base_modifier + modifiers.modifier + flat_modifier,
            roll_mode=self._combine_roll_modes(merge_roll_mode(advantage=modifiers.advantage, disadvantage=modifiers.disadvantage), roll_mode),
            dc=dc,
            auto_fail=modifiers.auto_fail,
        )
        return self.d20_engine.resolve(request, random_counter=state.random_counter)

    def _opposing_observers(self, state: EncounterState, actor: RuntimeActorState) -> tuple[RuntimeActorState, ...]:
        return tuple(
            other
            for other in state.actors.values()
            if other.actor_id != actor.actor_id and other.side != actor.side and other.is_conscious
        )

    def _post_reveal_visibility_state(
        self,
        state: EncounterState,
        *,
        observer: RuntimeActorState,
        target: RuntimeActorState,
        hidden_from_actor_ids: frozenset[str] | None = None,
    ) -> ObserverVisibilityState:
        preview_target = replace(
            target,
            hidden=bool(hidden_from_actor_ids),
            hidden_from_actor_ids=(hidden_from_actor_ids or frozenset()),
        )
        return assess_visibility(state, observer, preview_target).visibility_state

    def _visibility_reconciliation_events(self, state: EncounterState) -> list[object]:
        events: list[object] = []
        for target in state.actors.values():
            if not target.hidden or target.stealth_check_total is None or not target.hidden_from_actor_ids:
                continue
            for observer_id in tuple(target.hidden_from_actor_ids):
                observer = state.actors.get(observer_id)
                if observer is None or not observer.is_conscious:
                    continue
                if not supports_hiding_from_observer(state, target, observer):
                    next_hidden_from = frozenset(target.hidden_from_actor_ids - {observer_id})
                    events.append(ActorRevealedEvent(actor_id=target.actor_id, observer_id=observer_id, reason='visibility-conditions-changed'))
                    events.append(VisibilityStateChangedEvent(observer_id=observer_id, target_id=target.actor_id, visibility_state=self._post_reveal_visibility_state(state, observer=observer, target=target, hidden_from_actor_ids=next_hidden_from)))
                    continue
                passive_score = passive_perception_for_actor(observer)
                if passive_score >= target.stealth_check_total:
                    next_hidden_from = frozenset(target.hidden_from_actor_ids - {observer_id})
                    events.append(PassiveNoticeTriggeredEvent(observer_id=observer_id, target_id=target.actor_id, passive_score=passive_score, stealth_dc=target.stealth_check_total, noticed=True))
                    events.append(ActorRevealedEvent(actor_id=target.actor_id, observer_id=observer_id, reason='passive-perception'))
                    events.append(VisibilityStateChangedEvent(observer_id=observer_id, target_id=target.actor_id, visibility_state=self._post_reveal_visibility_state(state, observer=observer, target=target, hidden_from_actor_ids=next_hidden_from)))
        return events

    def _resolve_hide_action(self, state: EncounterState, actor: RuntimeActorState, events: list[object]) -> list[object]:
        observers = self._opposing_observers(state, actor)
        if not observers:
            raise EncounterValidationError('Hide requires at least one opposing observer to hide from.')
        if not any(supports_hiding_from_observer(state, actor, observer) for observer in observers):
            raise EncounterValidationError('The acting actor lacks concealment and cannot Hide here.')
        resolution = self.resolve_ability_check(state, actor_id=actor.actor_id, ability=Ability.DEX, dc=0, skill_name='Stealth')
        check_total = resolution.result.total
        events.append(D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used))
        hidden_from: list[str] = []
        for observer in observers:
            passive_score = passive_perception_for_actor(observer)
            noticed = passive_score >= check_total
            events.append(PassiveNoticeTriggeredEvent(observer_id=observer.actor_id, target_id=actor.actor_id, passive_score=passive_score, stealth_dc=check_total, noticed=noticed))
            if supports_hiding_from_observer(state, actor, observer) and not noticed:
                hidden_from.append(observer.actor_id)
                visibility_state = ObserverVisibilityState.HIDDEN
            else:
                visibility_state = self._post_reveal_visibility_state(state, observer=observer, target=actor, hidden_from_actor_ids=frozenset())
            events.append(VisibilityStateChangedEvent(observer_id=observer.actor_id, target_id=actor.actor_id, visibility_state=visibility_state))
        hidden_from_ids = tuple(sorted(hidden_from))
        events.append(
            HideAttemptedEvent(
                actor_id=actor.actor_id,
                skill_name='Stealth',
                check_total=check_total,
                hidden_from_actor_ids=hidden_from_ids,
                success=bool(hidden_from_ids),
                random_counter_used=resolution.random_counter_used,
            )
        )
        if hidden_from_ids:
            events.append(ActorHiddenEvent(actor_id=actor.actor_id, stealth_check_total=check_total, hidden_from_actor_ids=hidden_from_ids))
        else:
            events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason='hide-failed'))
        return events

    def _resolve_discovery_action(
        self,
        state: EncounterState,
        actor: RuntimeActorState,
        events: list[object],
        *,
        action_type: CombatActionType,
        ability: Ability,
        skill_name: str,
    ) -> list[object]:
        resolution = self.resolve_ability_check(state, actor_id=actor.actor_id, ability=ability, dc=0, skill_name=skill_name, requires_sight=True)
        check_total = resolution.result.total
        events.append(D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used))
        discovered_actor_ids: list[str] = []
        for target in state.actors.values():
            if actor.actor_id not in target.hidden_from_actor_ids or target.stealth_check_total is None:
                continue
            if check_total < target.stealth_check_total:
                continue
            discovered_actor_ids.append(target.actor_id)
            next_hidden_from = frozenset(target.hidden_from_actor_ids - {actor.actor_id})
            events.append(ActorRevealedEvent(actor_id=target.actor_id, observer_id=actor.actor_id, reason=action_type.value))
            events.append(VisibilityStateChangedEvent(observer_id=actor.actor_id, target_id=target.actor_id, visibility_state=self._post_reveal_visibility_state(state, observer=actor, target=target, hidden_from_actor_ids=next_hidden_from)))
        discovered_tuple = tuple(sorted(discovered_actor_ids))
        if action_type == CombatActionType.SEARCH:
            events.append(
                SearchAttemptedEvent(
                    actor_id=actor.actor_id,
                    skill_name=skill_name,
                    check_total=check_total,
                    discovered_actor_ids=discovered_tuple,
                    random_counter_used=resolution.random_counter_used,
                )
            )
        else:
            events.append(
                StudyAttemptedEvent(
                    actor_id=actor.actor_id,
                    skill_name=skill_name,
                    check_total=check_total,
                    discovered_actor_ids=discovered_tuple,
                    random_counter_used=resolution.random_counter_used,
                )
            )
        return events

    def _resolve_intent(self, state: EncounterState, intent: EncounterIntent) -> list[object]:
        if isinstance(intent, StartEncounterIntent):
            return self._resolve_start(state, intent)
        if isinstance(intent, MoveActorIntent):
            return self._resolve_move(state, intent)
        if isinstance(intent, MountActorIntent):
            return self._resolve_mount_actor(state, intent)
        if isinstance(intent, DismountActorIntent):
            return self._resolve_dismount_actor(state, intent)
        if isinstance(intent, ShareFamiliarSensesIntent):
            return self._resolve_share_familiar_senses(state, intent)
        if isinstance(intent, StandFromProneIntent):
            return self._resolve_stand_from_prone(state, intent)
        if isinstance(intent, TakeCombatActionIntent):
            return self._resolve_standard_action(state, intent)
        if isinstance(intent, AttackIntent):
            return self._resolve_attack_action(state, actor_id=intent.actor_id, attack_id=intent.attack_id, target_id=intent.target_id, attack_interaction=intent.attack_interaction)
        if isinstance(intent, CastSpellIntent):
            return self._resolve_cast_spell(state, intent)
        if isinstance(intent, UseCapabilityIntent):
            return self._resolve_use_capability(state, intent)
        if isinstance(intent, ObjectInteractionIntent):
            return self._resolve_object_interaction(state, intent)
        if isinstance(intent, EquipItemIntent):
            return self._resolve_equip_item(state, intent)
        if isinstance(intent, UseImprovisedWeaponIntent):
            return self._resolve_use_improvised_weapon(state, intent)
        if isinstance(intent, GrappleIntent):
            return self._resolve_grapple(state, intent)
        if isinstance(intent, ShoveIntent):
            return self._resolve_shove(state, intent)
        if isinstance(intent, ReadyIntent):
            return self._resolve_ready_action(state, intent)
        if isinstance(intent, ChooseTimingOrderIntent):
            return self._resolve_choose_timing_order(state, intent)
        if isinstance(intent, ContinueTimingIntent):
            return self._resolve_continue_timing_queue(state, intent)
        if isinstance(intent, ResolveIllusionInteractionIntent):
            return self._resolve_illusion_interaction(state, intent)
        if isinstance(intent, StartRitualCastIntent):
            return self._resolve_start_ritual_cast(state, intent)
        if isinstance(intent, ChooseReactionIntent):
            return self._resolve_reaction_choice(state, intent)
        if isinstance(intent, EndTurnIntent):
            return self._resolve_end_turn(state, intent)
        if isinstance(intent, StartShortRestIntent):
            return self._resolve_start_short_rest(state, intent)
        if isinstance(intent, StartLongRestIntent):
            return self._resolve_start_long_rest(state, intent)
        if isinstance(intent, ResumeRestIntent):
            return self._resolve_resume_rest(state, intent)
        if isinstance(intent, SpendHitPointDieIntent):
            return self._resolve_spend_hit_point_die(state, intent)
        if isinstance(intent, AdvanceTimeIntent):
            return self._resolve_advance_time(state, intent)
        raise EncounterValidationError('Unknown encounter intent.')

    def _roll_initiative_for_participants(
        self,
        state: EncounterState,
        *,
        participant_actor_ids: tuple[str, ...],
        surprised_actor_ids: tuple[str, ...] = (),
    ) -> tuple[dict[str, int], dict[str, int], tuple[str, ...], int]:
        initiative_rolls: dict[str, int] = {}
        initiative_totals: dict[str, int] = {}
        surprised = set(surprised_actor_ids)
        random_counter_used = state.random_counter
        for actor_id in participant_actor_ids:
            actor = state.actors[actor_id]
            modifiers = get_initiative_modifiers(actor)
            request = D20TestRequest(
                request_id=f'initiative:{actor_id}:{random_counter_used}',
                test_type=D20TestType.ABILITY_CHECK,
                actor_id=actor_id,
                ability=Ability.DEX,
                flat_modifier=actor.initiative_bonus + modifiers.modifier,
                roll_mode=merge_roll_mode(
                    advantage=modifiers.advantage,
                    disadvantage=(modifiers.disadvantage or actor_id in surprised),
                ),
            )
            resolution = self.d20_engine.resolve(request, random_counter=random_counter_used)
            initiative_rolls[actor_id] = resolution.result.selected_roll
            initiative_totals[actor_id] = resolution.result.total
        order = tuple(
            actor_id
            for actor_id, _ in sorted(
                initiative_totals.items(),
                key=lambda item: (-item[1], -state.actors[item[0]].initiative_bonus, item[0]),
            )
        )
        return initiative_rolls, initiative_totals, order, random_counter_used

    def insert_reinforcement_into_initiative(
        self,
        state: EncounterState,
        *,
        actor_id: str,
    ) -> tuple[int, int, tuple[str, ...], int]:
        if actor_id not in state.actors:
            raise EncounterValidationError(f'Unknown reinforcement actor: {actor_id}.')
        initiative_rolls, initiative_totals, order, random_counter_used = self._roll_initiative_for_participants(
            state,
            participant_actor_ids=(actor_id,),
        )
        actor = state.actors[actor_id]
        actor.initiative_roll = initiative_rolls[actor_id]
        actor.initiative_total = initiative_totals[actor_id]
        existing = [participant for participant in state.initiative_order if participant != actor_id]
        existing.append(actor_id)
        existing.sort(key=lambda participant_id: (-state.actors[participant_id].initiative_total, -state.actors[participant_id].initiative_bonus, participant_id))
        state.initiative_order = tuple(existing)
        return initiative_rolls[actor_id], initiative_totals[actor_id], state.initiative_order, random_counter_used

    def _resolve_start(self, state: EncounterState, intent: StartEncounterIntent) -> list[object]:
        if state.phase != EncounterPhase.READY:
            raise EncounterValidationError('Encounter has already started.')
        participant_actor_ids = intent.participant_actor_ids or tuple(state.actors)
        if len(participant_actor_ids) < 2:
            raise EncounterValidationError('Encounter requires at least two actors.')
        missing = [actor_id for actor_id in participant_actor_ids if actor_id not in state.actors]
        if missing:
            raise EncounterValidationError(f'Encounter start references unknown actors: {", ".join(missing)}.')
        initiative_rolls, initiative_totals, order, random_counter_used = self._roll_initiative_for_participants(
            state,
            participant_actor_ids=participant_actor_ids,
            surprised_actor_ids=intent.surprised_actor_ids,
        )
        events: list[object] = []
        if intent.surprised_actor_ids:
            events.append(SurpriseStateComputedEvent(surprised_actor_ids=intent.surprised_actor_ids, reason='Encounter start surprise evaluation.'))
        events.append(EncounterStartedEvent(initiative_order=order, initiative_rolls=initiative_rolls, initiative_totals=initiative_totals, random_counter_used=random_counter_used, first_actor_id=order[0]))
        return events

    def _resolve_move(self, state: EncounterState, intent: MoveActorIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        self._require_conscious(actor)
        destination_z = actor.position.z if intent.z is None else intent.z
        destination = GridPosition(intent.x, intent.y, destination_z)
        validate_frightened_movement(actor, state, destination)
        for effect in state.active_effects.values():
            if actor.actor_id not in effect.target_actor_ids or effect.definition.cannot_willingly_move_beyond_source_ft is None:
                continue
            source = state.actors.get(effect.source_actor_id)
            if source is None:
                continue
            if self.battlefield_rules.get_distance3d(destination, source.position) > effect.definition.cannot_willingly_move_beyond_source_ft:
                raise EncounterValidationError('The actor cannot willingly move farther from the source of the effect.')
        if self.battlefield_rules.max_remaining_movement_ft(actor) <= 0:
            raise EncounterValidationError('The actor cannot move because it has no remaining speed.')
        preview = self.battlefield_rules.preview_move(state, actor, destination, movement_intent_mode=intent.movement_intent_mode)
        if preview.outcome == MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION:
            raise EncounterMovementPreviewError(preview)
        if preview.outcome not in {
            MovementPreviewOutcome.REACHABLE_SAME_PLANE,
            MovementPreviewOutcome.REACHABLE_WITH_SLOPE,
            MovementPreviewOutcome.REACHABLE_WITH_CLIMB,
            MovementPreviewOutcome.REACHABLE_WITH_FLY,
        } or preview.plan is None:
            raise EncounterValidationError(preview.detail)
        legality = self.battlefield_rules.movement_legality(state, actor, destination, movement_intent_mode=intent.movement_intent_mode)
        movement_cost, remaining_after, movement_mode, movement_spent_after = self._resolve_path_budget(state, actor, legality.plan)
        pending_movement = PendingMovementState(
            actor_id=actor.actor_id,
            from_position=actor.position,
            to_position=destination,
            distance_ft=movement_cost,
            remaining_movement_ft_after=remaining_after,
            movement_mode=movement_mode,
            movement_spent_ft_after=movement_spent_after,
            consume_turn_movement=True,
        )
        reaction_options = self._sorted_reaction_options(
            discover_leave_reach_reactions(
                state,
                moving_actor_id=actor.actor_id,
                from_position=actor.position,
                to_position=destination,
                path=legality.path,
            )
        )
        events: list[object] = [
            MoveDeclaredEvent(actor_id=actor.actor_id, from_position=actor.position, to_position=destination),
            MovementModeSelectedEvent(
                actor_id=actor.actor_id,
                movement_mode=movement_mode,
                movement_cost_ft=movement_cost,
                remaining_movement_ft_after=remaining_after,
            ),
        ]
        if reaction_options:
            window = ReactionWindowState(
                trigger_id=f'move:{actor.actor_id}:{state.random_counter}:{destination.x}:{destination.y}:{destination.z}',
                trigger_type=ReactionTriggerType.LEAVE_REACH,
                pending_actor_id=actor.actor_id,
                prompt='A creature is leaving reach. Choose a legal reaction or decline.',
                options=reaction_options,
                pending_movement=pending_movement,
                resume_state=PendingResolutionState(
                    kind=PendingResolutionKind.COMPLETE_MOVEMENT,
                    pending_movement=pending_movement,
                ),
            )
            events.append(ReactionWindowOpenedEvent(window=window))
            return events
        events.extend(
            [
                MovementSpentEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    distance_ft=movement_cost,
                    remaining_movement_ft=remaining_after,
                    movement_mode=movement_mode,
                    movement_spent_ft=movement_spent_after,
                    consume_turn_movement=True,
                ),
                RelocationResolvedEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    relocation_type=RelocationType.PATH,
                    movement_mode=movement_mode,
                ),
                PositionChangedEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    relocation_type=RelocationType.PATH,
                    movement_mode=movement_mode,
                ),
            ]
        )
        self._append_ready_trigger_window_if_any(
            state,
            events,
            trigger_actor_id=actor.actor_id,
            from_position=actor.position,
            to_position=destination,
        )
        return events

    def _resolve_stand_from_prone(self, state: EncounterState, intent: StandFromProneIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        self._require_conscious(actor)
        if not has_condition(actor, ConditionType.PRONE):
            raise EncounterValidationError('The actor is not prone.')
        legality = self.battlefield_rules.stand_legality(actor, effective_speed_ft=get_effective_speed(actor))
        return [
            MoveDeclaredEvent(actor_id=actor.actor_id, from_position=actor.position, to_position=actor.position),
            ConditionRemovedEvent(actor_id=actor.actor_id, condition_type=ConditionType.PRONE),
            StoodFromProneEvent(actor_id=actor.actor_id, movement_cost_ft=legality.movement_cost_ft, remaining_movement_ft=legality.remaining_movement_ft_after, movement_spent_ft=self._starting_movement_spent(actor) + legality.movement_cost_ft),
        ]

    def _resolve_standard_action(self, state: EncounterState, intent: TakeCombatActionIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        self._require_conscious(actor)
        action_type = intent.action_type
        resource_mode = intent.resource_mode if action_type == CombatActionType.DASH else 'action'
        if resource_mode == 'bonus':
            if action_type != CombatActionType.DASH:
                raise EncounterValidationError('Only Dash can currently use a bonus-action resource mode.')
            if not actor.can_dash_as_bonus_action:
                raise EncounterValidationError('The actor cannot currently Dash as a bonus action.')
            self._require_bonus_action_permission(actor)
        else:
            self._require_action_permission(actor)
        if action_type in {CombatActionType.ATTACK, CombatActionType.MAGIC, CombatActionType.GRAPPLE, CombatActionType.SHOVE}:
            raise EncounterValidationError('Use the dedicated typed intent for this combat action.')
        spend_resource = 'bonus' if resource_mode == 'bonus' else 'action'
        events = [ActionDeclaredEvent(actor_id=actor.actor_id, action_type=action_type, target_id=intent.target_id, detail=intent.attack_id), ActionValidatedEvent(actor_id=actor.actor_id, action_type=action_type), ResourceSpentEvent(actor_id=actor.actor_id, resource=spend_resource, reason=action_type.value)]
        if action_type == CombatActionType.DASH:
            dash_bonus_after = actor.dash_bonus_ft + get_effective_speed(actor)
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, remaining_movement_ft=actor.remaining_movement_ft + get_effective_speed(actor), dash_bonus_ft=dash_bonus_after))
            return events
        if action_type == CombatActionType.DISENGAGE:
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, disengage_active=True))
            return events
        if action_type == CombatActionType.DODGE:
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, dodge_active=True))
            return events
        if action_type == CombatActionType.HELP:
            if intent.target_id is None:
                raise EncounterValidationError('Help requires a target actor id.')
            target = self._require_target(state, intent.target_id)
            if grid_distance_ft(actor.position, target.position) > 5:
                raise EncounterValidationError('Help requires the target to be within 5 feet.')
            sleep_events = self._sleep_end_events(state, actor_id=target.actor_id, reason='woken')
            if sleep_events:
                events.extend(sleep_events)
                return events
            if target.side != actor.side or target.actor_id == actor.actor_id:
                raise EncounterValidationError('Help requires another allied target.')
            if target.uses_death_saves and target.current_hit_points == 0:
                if target.dying_state.status == DyingStateStatus.DEAD:
                    raise EncounterValidationError('A dead creature cannot be stabilized.')
                if target.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
                    raise EncounterValidationError('The target is already stable at 0 HP.')
                check_request = CheckRequest(
                    context=ResolutionContext(
                        effect_id=f'stabilize:{actor.actor_id}:{target.actor_id}:{state.random_counter}',
                        source_actor_id=actor.actor_id,
                        target_actor_id=actor.actor_id,
                        reason=f'Stabilize {target.actor_id}',
                    ),
                    ability=Ability.WIS,
                    dc=10,
                    skill_name='Medicine',
                )
                resolution, check_events = self.resolve_check_consumer(state, check_request, apply=False)
                events.extend(check_events)
                if resolution.branch.value == 'success':
                    check_roll_event = next(event for event in check_events if isinstance(event, CheckRolledEvent))
                    recovery_counter = check_roll_event.random_counter_used + 1
                    recovery_hours = seeded_random(self.seed, recovery_counter).randint(1, 4)
                    events.append(
                        StabilizedEvent(
                            actor_id=target.actor_id,
                            reason='medicine-check',
                            stabilized_by_actor_id=actor.actor_id,
                            recovery_hours=recovery_hours,
                            random_counter_used=recovery_counter,
                        )
                    )
                return events
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, help_target_id=target.actor_id))
            return events
        if action_type == CombatActionType.HIDE:
            return self._resolve_hide_action(state, actor, events)
        if action_type == CombatActionType.READY:
            raise EncounterValidationError('Use the dedicated typed Ready intent for readied responses.')

        if action_type == CombatActionType.SEARCH:
            return self._resolve_discovery_action(state, actor, events, action_type=action_type, ability=Ability.WIS, skill_name='Perception')
        if action_type == CombatActionType.STUDY:
            return self._resolve_discovery_action(state, actor, events, action_type=action_type, ability=Ability.INT, skill_name='Investigation')
        if action_type == CombatActionType.UTILIZE:
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type))
            return events
        raise EncounterValidationError('Unsupported standard combat action for this deterministic slice.')

    def _chain_resume_states(self, first: PendingResolutionState | None, second: PendingResolutionState | None) -> PendingResolutionState | None:
        if first is None:
            return second
        if first.next_resume is None:
            return replace(first, next_resume=second)
        return replace(first, next_resume=self._chain_resume_states(first.next_resume, second))

    def _synthetic_readied_spell_effect(self, *, actor: RuntimeActorState, spell, effect_id: str) -> ActiveEffectState:
        return ActiveEffectState(
            effect_instance_id=effect_id,
            capability_id=spell.option_id,
            name=f'Readied {spell.name}',
            source_actor_id=actor.actor_id,
            target_actor_ids=(),
            definition=ActiveEffectDefinition(
                name=f'Readied {spell.name}',
                duration=DurationSpec(duration_type=EffectDurationType.UNTIL_START_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                concentration=True,
            ),
            started_round_number=0,
            started_turn_actor_id=actor.actor_id,
            duration_anchor_actor_id=actor.actor_id,
        )

    def _resolve_ready_action(self, state: EncounterState, intent: ReadyIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        self._require_conscious(actor)
        self._require_action_permission(actor)
        trigger_actor = self._require_target(state, intent.trigger_actor_id)
        if intent.trigger_kind != ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW:
            raise EncounterValidationError('Unsupported ready trigger kind in this deterministic slice.')
        events: list[object] = [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.READY, target_id=trigger_actor.actor_id, detail=intent.response_kind.value),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.READY),
            ResourceSpentEvent(actor_id=actor.actor_id, resource='action', reason='ready'),
        ]
        detail = ''
        response = ReadyResponseState(response_kind=intent.response_kind)
        if intent.response_kind == ReadyResponseKind.ATTACK:
            if intent.attack_id is None:
                raise EncounterValidationError('Readied attacks require an attack id.')
            attack = actor.attacks.get(intent.attack_id)
            if attack is None:
                raise EncounterValidationError('The chosen readied attack is not available to the actor.')
            self._validate_attack_equipment(actor, attack, spend_resource='reaction')
            response = ReadyResponseState(response_kind=ReadyResponseKind.ATTACK, attack_id=attack.attack_id, target_actor_id=trigger_actor.actor_id)
            detail = f'{attack.name} when {trigger_actor.name} comes into range'
        elif intent.response_kind == ReadyResponseKind.MOVE:
            if intent.x is None or intent.y is None:
                raise EncounterValidationError('Readied movement requires a deterministic destination.')
            destination = GridPosition(intent.x, intent.y, actor.position.z if intent.z is None else intent.z)
            preview_actor = copy.deepcopy(actor)
            preview_actor.movement_spent_ft = 0
            preview_actor.remaining_movement_ft = preview_actor.max_path_speed_ft
            preview = self.battlefield_rules.preview_move(state, preview_actor, destination, movement_intent_mode=intent.movement_intent_mode)
            if preview.plan is None or preview.outcome not in {
                MovementPreviewOutcome.REACHABLE_SAME_PLANE,
                MovementPreviewOutcome.REACHABLE_WITH_SLOPE,
                MovementPreviewOutcome.REACHABLE_WITH_CLIMB,
                MovementPreviewOutcome.REACHABLE_WITH_FLY,
            }:
                raise EncounterValidationError('The chosen readied movement destination is not reachable within Speed.')
            response = ReadyResponseState(response_kind=ReadyResponseKind.MOVE, destination=destination, movement_intent_mode=intent.movement_intent_mode)
            detail = f'move to ({destination.x},{destination.y},{destination.z}) when {trigger_actor.name} moves'
        elif intent.response_kind == ReadyResponseKind.SPELL:
            if intent.spell_id is None:
                raise EncounterValidationError('Readied spells require a spell id.')
            spell = actor.spells.get(intent.spell_id)
            if spell is None or spell.capability is None:
                raise EncounterValidationError('That spell is not available to be readied.')
            if spell.remaining_uses is not None and spell.remaining_uses <= 0:
                raise EncounterValidationError('That spell has no remaining uses.')
            if spell.resource_pool_id is not None:
                pool = actor.resource_pools.get(spell.resource_pool_id)
                if pool is None:
                    raise EncounterValidationError(f'That spell references missing resource pool {spell.resource_pool_id!r}.')
                if pool.current <= 0:
                    raise EncounterValidationError('The acting actor has no spell slots remaining for that spell level.')
            if spell.action_cost != 'action':
                raise EncounterValidationError('Only spells with a casting time of an action can be readied.')
            if spell.capability.targeting.selection_kind != TargetSelectionKind.CREATURE:
                raise EncounterValidationError('This deterministic slice supports readying only creature-targeted spells.')
            if actor.hidden:
                events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=CombatActionType.READY.value))
                events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=CombatActionType.READY, hidden=False))
            if actor.concentrating_effect_id is not None:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=actor.concentrating_effect_id, reason='replaced'))
            effect_id = f'readied-spell:{actor.actor_id}:{spell.option_id}:{state.random_counter}'
            hold_effect = ActiveEffectState(
                effect_instance_id=effect_id,
                capability_id=spell.option_id,
                name=f'Readied {spell.name}',
                source_actor_id=actor.actor_id,
                target_actor_ids=(),
                definition=ActiveEffectDefinition(
                    name=f'Readied {spell.name}',
                    duration=DurationSpec(duration_type=EffectDurationType.UNTIL_START_OF_NEXT_TURN, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                ),
                started_round_number=state.round_number,
                started_turn_actor_id=actor.actor_id,
                duration_anchor_actor_id=actor.actor_id,
            )
            events.append(
                SpellCastEvent(
                    actor_id=actor.actor_id,
                    spell_id=spell.option_id,
                    action_cost=spell.action_cost,
                    from_position=actor.position,
                    target_id=trigger_actor.actor_id,
                    remaining_uses=(None if spell.remaining_uses is None else spell.remaining_uses - 1),
                    resource_pool_id=spell.resource_pool_id,
                    resource_pool_current_after=(None if spell.resource_pool_id is None else actor.resource_pools[spell.resource_pool_id].current - 1),
                )
            )
            events.append(ActiveEffectStartedEvent(effect=hold_effect))
            events.append(ConcentrationStartedEvent(actor_id=actor.actor_id, effect_instance_id=effect_id))
            response = ReadyResponseState(response_kind=ReadyResponseKind.SPELL, spell_id=spell.option_id, target_actor_id=trigger_actor.actor_id)
            detail = f'{spell.name} when {trigger_actor.name} comes into range'
            ready_state = ReadiedActionState(trigger=ReadyTriggerState(trigger_kind=intent.trigger_kind, trigger_actor_id=trigger_actor.actor_id), response=response, declared_round_number=state.round_number, concentration_effect_id=effect_id)
            events.append(ReadyDeclaredEvent(actor_id=actor.actor_id, ready_state=ready_state, detail=detail))
            return events
        elif intent.response_kind == ReadyResponseKind.CAPABILITY:
            if intent.capability_id is None:
                raise EncounterValidationError('Readied capabilities require a capability id.')
            runtime_capability = actor.capabilities.get(intent.capability_id)
            if runtime_capability is None:
                raise EncounterValidationError('That capability is not available to be readied.')
            if runtime_capability.remaining_uses is not None and runtime_capability.remaining_uses <= 0:
                raise EncounterValidationError('That capability has no remaining uses.')
            if runtime_capability.action_cost != 'action':
                raise EncounterValidationError('Only action capabilities can be readied in this deterministic slice.')
            if runtime_capability.capability.targeting.selection_kind != TargetSelectionKind.CREATURE:
                raise EncounterValidationError('This deterministic slice supports readying only creature-targeted capabilities.')
            if actor.hidden:
                events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=CombatActionType.READY.value))
                events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=CombatActionType.READY, hidden=False))
            events.append(CapabilityDeclaredEvent(actor_id=actor.actor_id, capability_id=runtime_capability.capability.capability_id, capability_name=runtime_capability.capability.name, action_cost=runtime_capability.capability.action_cost, target_id=trigger_actor.actor_id, runtime_option_id=runtime_capability.option_id, remaining_uses=(None if runtime_capability.remaining_uses is None else runtime_capability.remaining_uses - 1)))
            response = ReadyResponseState(response_kind=ReadyResponseKind.CAPABILITY, capability_id=runtime_capability.option_id, target_actor_id=trigger_actor.actor_id)
            detail = f'{runtime_capability.capability.name} when {trigger_actor.name} comes into range'
        else:
            raise EncounterValidationError('Unsupported ready response kind.')
        ready_state = ReadiedActionState(trigger=ReadyTriggerState(trigger_kind=intent.trigger_kind, trigger_actor_id=trigger_actor.actor_id), response=response, declared_round_number=state.round_number)
        events.append(ReadyDeclaredEvent(actor_id=actor.actor_id, ready_state=ready_state, detail=detail))
        return events

    def _append_ready_trigger_window_if_any(self, state: EncounterState, events: list[object], *, trigger_actor_id: str, from_position: GridPosition | None, to_position: GridPosition, resume_state: PendingResolutionState | None = None) -> None:
        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        reaction_options = self._sorted_reaction_options(discover_ready_reactions(preview, trigger_actor_id=trigger_actor_id))
        if not reaction_options:
            if resume_state is not None:
                events.extend(self._resume_pending_resolution(preview, resume_state))
            return
        events.append(
            ReactionWindowOpenedEvent(
                window=ReactionWindowState(
                    trigger_id=f'ready:{trigger_actor_id}:{state.random_counter}:{to_position.x}:{to_position.y}:{to_position.z}',
                    trigger_type=ReactionTriggerType.READY_TRIGGER,
                    pending_actor_id=trigger_actor_id,
                    prompt='A readied trigger occurred. Choose a legal reaction or decline.',
                    options=reaction_options,
                    pending_ready_trigger=PendingReadyTriggerState(
                        trigger_actor_id=trigger_actor_id,
                        from_position=from_position,
                        to_position=to_position,
                    ),
                    resume_state=resume_state,
                )
            )
        )

    def _sorted_reaction_options(self, options: tuple[ReactionOption, ...] | list[ReactionOption]) -> tuple[ReactionOption, ...]:
        return tuple(sorted(tuple(options), key=lambda option: (option.actor_id, option.option_id)))

    def _ready_continuation_state(self, window: ReactionWindowState, responded_actor_ids: tuple[str, ...]) -> PendingResolutionState:
        return PendingResolutionState(
            kind=PendingResolutionKind.CONTINUE_REACTION_WINDOW,
            reaction_window=replace(window, responded_actor_ids=responded_actor_ids),
            next_resume=window.resume_state,
        )

    def _rebuild_reaction_window(
        self,
        state: EncounterState,
        window: ReactionWindowState,
        responded_actor_ids: tuple[str, ...],
    ) -> ReactionWindowState | None:
        if window.trigger_type == ReactionTriggerType.LEAVE_REACH:
            pending_movement = window.pending_movement
            if pending_movement is None:
                return None
            moving_actor = state.actors.get(pending_movement.actor_id)
            if moving_actor is None or moving_actor.is_dead or moving_actor.current_hit_points <= 0:
                return None
            options = self._sorted_reaction_options(
                discover_leave_reach_reactions(
                    state,
                    moving_actor_id=pending_movement.actor_id,
                    from_position=pending_movement.from_position,
                    to_position=pending_movement.to_position,
                )
            )
        elif window.trigger_type == ReactionTriggerType.HIT_DETECTED:
            pending_attack = window.pending_attack
            if pending_attack is None:
                return None
            target = state.actors.get(pending_attack.target_id)
            if target is None or target.is_dead:
                return None
            options = self._sorted_reaction_options(discover_hit_reactions(state, target_id=pending_attack.target_id))
        elif window.trigger_type == ReactionTriggerType.DAMAGE_TAKEN:
            pending_attack = window.pending_attack
            if pending_attack is None:
                return None
            target = state.actors.get(pending_attack.target_id)
            if target is None or target.is_dead:
                return None
            options = self._sorted_reaction_options(
                discover_damage_reactions(state, target_id=pending_attack.target_id, source_actor_id=pending_attack.actor_id)
            )
        elif window.trigger_type == ReactionTriggerType.POST_HIT_TRIGGER:
            pending_attack = window.pending_attack
            if pending_attack is None:
                return None
            attacker = state.actors.get(pending_attack.actor_id)
            target = state.actors.get(pending_attack.target_id)
            if attacker is None or attacker.is_dead or target is None or target.is_dead:
                return None
            options = self._sorted_reaction_options(discover_post_hit_reactions(state, pending_attack=pending_attack))
        elif window.trigger_type == ReactionTriggerType.READY_TRIGGER:
            pending_ready_trigger = window.pending_ready_trigger
            if pending_ready_trigger is None:
                return None
            trigger_actor = state.actors.get(pending_ready_trigger.trigger_actor_id)
            if trigger_actor is None or trigger_actor.is_dead:
                return None
            options = self._sorted_reaction_options(
                discover_ready_reactions(state, trigger_actor_id=pending_ready_trigger.trigger_actor_id)
            )
        elif window.trigger_type == ReactionTriggerType.FALL_DETECTED:
            pending_fall = None if window.resume_state is None else window.resume_state.pending_fall
            if pending_fall is None:
                return None
            falling_actor = state.actors.get(pending_fall.actor_id)
            if falling_actor is None or falling_actor.is_dead:
                return None
            options = self._sorted_reaction_options(
                discover_fall_reactions(
                    state,
                    falling_actor_id=pending_fall.actor_id,
                    from_position=pending_fall.from_position,
                )
            )
        else:
            raise EncounterValidationError('Unsupported reaction trigger type for window rebuild.')
        filtered_options = tuple(
            option for option in options if option.actor_id not in responded_actor_ids
        )
        if not filtered_options:
            return None
        return replace(window, options=filtered_options, responded_actor_ids=responded_actor_ids)

    def _resolve_readied_movement_response(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        trigger_actor_id: str,
        destination: GridPosition,
        movement_intent_mode: MovementIntentMode,
        resume_state: PendingResolutionState | None,
    ) -> list[object]:
        preview_actor = copy.deepcopy(actor)
        preview_actor.movement_spent_ft = 0
        preview_actor.remaining_movement_ft = preview_actor.max_path_speed_ft
        preview = self.battlefield_rules.preview_move(
            state,
            preview_actor,
            destination,
            movement_intent_mode=movement_intent_mode,
        )
        if preview.plan is None or preview.outcome not in {
            MovementPreviewOutcome.REACHABLE_SAME_PLANE,
            MovementPreviewOutcome.REACHABLE_WITH_SLOPE,
            MovementPreviewOutcome.REACHABLE_WITH_CLIMB,
            MovementPreviewOutcome.REACHABLE_WITH_FLY,
        }:
            raise EncounterValidationError('The readied movement destination is no longer reachable.')
        legality = self.battlefield_rules.movement_legality(
            state,
            preview_actor,
            destination,
            movement_intent_mode=movement_intent_mode,
        )
        movement_cost, _, movement_mode, _ = self._resolve_path_budget(state, preview_actor, legality.plan)
        pending_movement = PendingMovementState(
            actor_id=actor.actor_id,
            from_position=actor.position,
            to_position=destination,
            distance_ft=movement_cost,
            remaining_movement_ft_after=actor.remaining_movement_ft,
            movement_mode=movement_mode,
            movement_spent_ft_after=actor.movement_spent_ft,
            consume_turn_movement=False,
        )
        reaction_options = self._sorted_reaction_options(
            discover_leave_reach_reactions(
                state,
                moving_actor_id=actor.actor_id,
                from_position=actor.position,
                to_position=destination,
                path=legality.path,
            )
        )
        events: list[object] = [
            ResourceSpentEvent(actor_id=actor.actor_id, resource='reaction', reason='ready-move'),
        ]
        if reaction_options:
            events.append(
                ReactionWindowOpenedEvent(
                    window=ReactionWindowState(
                        trigger_id=f'move:{actor.actor_id}:ready:{state.random_counter}:{destination.x}:{destination.y}:{destination.z}',
                        trigger_type=ReactionTriggerType.LEAVE_REACH,
                        pending_actor_id=actor.actor_id,
                        prompt='A creature is leaving reach. Choose a legal reaction or decline.',
                        options=reaction_options,
                        pending_movement=pending_movement,
                        resume_state=self._chain_resume_states(
                            PendingResolutionState(
                                kind=PendingResolutionKind.COMPLETE_MOVEMENT,
                                pending_movement=pending_movement,
                            ),
                            resume_state,
                        ),
                    )
                )
            )
            return events
        events.extend(
            [
                MovementSpentEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    distance_ft=movement_cost,
                    remaining_movement_ft=actor.remaining_movement_ft,
                    movement_mode=movement_mode,
                    movement_spent_ft=actor.movement_spent_ft,
                    consume_turn_movement=False,
                ),
                RelocationResolvedEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    relocation_type=RelocationType.PATH,
                    movement_mode=movement_mode,
                ),
                PositionChangedEvent(
                    actor_id=actor.actor_id,
                    from_position=actor.position,
                    to_position=destination,
                    relocation_type=RelocationType.PATH,
                    movement_mode=movement_mode,
                ),
            ]
        )
        self._append_ready_trigger_window_if_any(
            state,
            events,
            trigger_actor_id=actor.actor_id,
            from_position=actor.position,
            to_position=destination,
            resume_state=resume_state,
        )
        return events

    def _resolve_readied_reaction(
        self,
        state: EncounterState,
        *,
        option: ReactionOption,
        trigger_actor_id: str,
        resume_state: PendingResolutionState | None,
    ) -> list[object]:
        actor = self._require_actor(state, option.actor_id)
        self._require_reaction_permission(actor)
        readied_action = actor.readied_action
        if readied_action is None:
            raise EncounterValidationError('The actor no longer has a readied response to use.')
        events: list[object] = [
            ReadyTriggeredEvent(
                actor_id=actor.actor_id,
                trigger_actor_id=trigger_actor_id,
                response_kind=readied_action.response.response_kind.value,
            )
        ]
        if readied_action.response.response_kind == ReadyResponseKind.ATTACK:
            if readied_action.response.attack_id is None:
                raise EncounterValidationError('The readied attack payload is incomplete.')
            events.extend(
                self._resolve_attack_action(
                    state,
                    actor_id=actor.actor_id,
                    attack_id=readied_action.response.attack_id,
                    target_id=readied_action.response.target_actor_id or trigger_actor_id,
                    action_type=CombatActionType.READY,
                    spend_resource='reaction',
                    allow_hit_reactions=True,
                    require_turn=False,
                    resume_state=resume_state,
                )
            )
            return events
        if readied_action.response.response_kind == ReadyResponseKind.MOVE:
            destination = readied_action.response.destination
            if destination is None:
                raise EncounterValidationError('The readied movement payload is incomplete.')
            events.extend(
                self._resolve_readied_movement_response(
                    state,
                    actor=actor,
                    trigger_actor_id=trigger_actor_id,
                    destination=destination,
                    movement_intent_mode=readied_action.response.movement_intent_mode,
                    resume_state=resume_state,
                )
            )
            return events
        preview_state = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview_state, event)
        preview_actor = preview_state.actors[actor.actor_id]
        if readied_action.response.response_kind == ReadyResponseKind.SPELL:
            spell_id = readied_action.response.spell_id
            if spell_id is None:
                raise EncounterValidationError('The readied spell payload is incomplete.')
            if readied_action.concentration_effect_id is not None and readied_action.concentration_effect_id in preview_state.active_effects:
                end_events = self.effect_executor.end_active_effect(
                    preview_state,
                    effect_id=readied_action.concentration_effect_id,
                    reason='ready-triggered',
                )
                events.extend(end_events)
                for event in end_events:
                    self._apply_event(preview_state, event)
                preview_actor = preview_state.actors[actor.actor_id]
            spell = preview_actor.spells.get(spell_id)
            if spell is None or spell.capability is None:
                raise EncounterValidationError('The readied spell is no longer available.')
            events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource='reaction', reason='ready-spell'))
            spell_events = self.effect_executor.execute_spell(
                preview_state,
                actor=preview_actor,
                spell=spell,
                target_id=readied_action.response.target_actor_id or trigger_actor_id,
            )
            events.extend(spell_events)
            return events
        if readied_action.response.response_kind == ReadyResponseKind.CAPABILITY:
            capability_id = readied_action.response.capability_id
            if capability_id is None:
                raise EncounterValidationError('The readied capability payload is incomplete.')
            runtime_capability = preview_actor.capabilities.get(capability_id)
            if runtime_capability is None:
                raise EncounterValidationError('The readied capability is no longer available.')
            events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource='reaction', reason='ready-capability'))
            capability_events = self.effect_executor.execute_capability(
                preview_state,
                actor=preview_actor,
                capability=runtime_capability.capability,
                target_id=readied_action.response.target_actor_id or trigger_actor_id,
                runtime_capability=runtime_capability,
            )
            events.extend(capability_events)
            return events
        raise EncounterValidationError('Unsupported readied response kind.')

    def _concentration_damage_events(self, state: EncounterState, *, actor_id: str, damage_total: int) -> list[object]:
        actor = self._require_actor(state, actor_id)
        if damage_total <= 0 or actor.concentrating_effect_id is None:
            return []
        if actor.is_dead or actor.current_hit_points <= 0 or has_condition(actor, ConditionType.INCAPACITATED):
            return []
        save_request = SaveRequest(
            context=ResolutionContext(
                effect_id=f'concentration:{actor.actor_id}:{state.random_counter}',
                source_actor_id=actor.actor_id,
                target_actor_id=actor.actor_id,
                reason='Maintain Concentration',
            ),
            ability=Ability.CON,
            dc=max(10, damage_total // 2),
        )
        resolution, events = self.resolve_save_consumer(state, save_request, apply=False)
        if resolution.branch != EffectResolutionBranch.SUCCESS:
            events.append(
                ConcentrationBrokenEvent(
                    actor_id=actor.actor_id,
                    effect_id=actor.concentrating_effect_id,
                    reason='damage',
                )
            )
        return events

    def _resume_pending_resolution(self, state: EncounterState, resume_state: PendingResolutionState | None) -> list[object]:
        if resume_state is None:
            return []
        if resume_state.kind == PendingResolutionKind.COMPLETE_MOVEMENT:
            if resume_state.pending_movement is None:
                raise EncounterValidationError('Pending movement resolution is missing its movement payload.')
            movement = resume_state.pending_movement
            events = [
                MovementSpentEvent(actor_id=movement.actor_id, from_position=movement.from_position, to_position=movement.to_position, distance_ft=movement.distance_ft, remaining_movement_ft=movement.remaining_movement_ft_after, movement_mode=movement.movement_mode, movement_spent_ft=movement.movement_spent_ft_after, consume_turn_movement=movement.consume_turn_movement),
                RelocationResolvedEvent(actor_id=movement.actor_id, from_position=movement.from_position, to_position=movement.to_position, relocation_type=RelocationType.PATH, movement_mode=movement.movement_mode),
                PositionChangedEvent(actor_id=movement.actor_id, from_position=movement.from_position, to_position=movement.to_position, relocation_type=RelocationType.PATH, movement_mode=movement.movement_mode),
            ]
            self._append_ready_trigger_window_if_any(state, events, trigger_actor_id=movement.actor_id, from_position=movement.from_position, to_position=movement.to_position, resume_state=resume_state.next_resume)
            return events
        if resume_state.kind == PendingResolutionKind.FINALIZE_ATTACK:
            if resume_state.pending_attack is None:
                raise EncounterValidationError('Pending attack resolution is missing its attack payload.')
            post_hit_options = self._sorted_reaction_options(discover_post_hit_reactions(state, pending_attack=resume_state.pending_attack))
            if post_hit_options:
                window = ReactionWindowState(
                    trigger_id=f'post-hit:{resume_state.pending_attack.actor_id}:{resume_state.pending_attack.target_id}:{resume_state.pending_attack.attack_id}:{state.random_counter}',
                    trigger_type=ReactionTriggerType.POST_HIT_TRIGGER,
                    pending_actor_id=resume_state.pending_attack.actor_id,
                    prompt='A post-hit spell trigger is available. Choose a legal option or decline.',
                    options=post_hit_options,
                    pending_attack=resume_state.pending_attack,
                    resume_state=self._chain_resume_states(
                        PendingResolutionState(
                            kind=PendingResolutionKind.APPLY_ATTACK_DAMAGE,
                            pending_attack=resume_state.pending_attack,
                        ),
                        resume_state.next_resume,
                    ),
                )
                return [ReactionWindowOpenedEvent(window=window)]
            events, _ = self._finalize_pending_attack(state, resume_state.pending_attack, armor_class_bonus=0, damage_counter=state.random_counter)
            if resume_state.next_resume is not None:
                preview = copy.deepcopy(state)
                for event in events:
                    self._apply_event(preview, event)
                events.extend(self._resume_pending_resolution(preview, resume_state.next_resume))
            return events
        if resume_state.kind == PendingResolutionKind.APPLY_ATTACK_DAMAGE:
            if resume_state.pending_attack is None:
                raise EncounterValidationError('Pending attack damage resolution is missing its attack payload.')
            events, _ = self._finalize_pending_attack(state, resume_state.pending_attack, armor_class_bonus=0, damage_counter=state.random_counter)
            if resume_state.next_resume is not None:
                preview = copy.deepcopy(state)
                for event in events:
                    self._apply_event(preview, event)
                events.extend(self._resume_pending_resolution(preview, resume_state.next_resume))
            return events
        if resume_state.kind == PendingResolutionKind.CONTINUE_REACTION_WINDOW:
            if resume_state.reaction_window is None:
                raise EncounterValidationError('Reaction-window continuation is missing its window payload.')
            updated_window = self._rebuild_reaction_window(state, resume_state.reaction_window, resume_state.reaction_window.responded_actor_ids)
            if updated_window is not None:
                return [ReactionWindowOpenedEvent(window=updated_window)]
            return self._resume_pending_resolution(state, resume_state.next_resume)
        if resume_state.kind == PendingResolutionKind.COMPLETE_FALL:
            if resume_state.pending_fall is None:
                raise EncounterValidationError('Pending fall resolution is missing its fall payload.')
            events = self._complete_fall_events(state, pending_fall=resume_state.pending_fall)
            if resume_state.next_resume is not None:
                preview = copy.deepcopy(state)
                for event in events:
                    self._apply_event(preview, event)
                events.extend(self._resume_pending_resolution(preview, resume_state.next_resume))
            return events
        if resume_state.kind == PendingResolutionKind.CONTINUE_TIMING_QUEUE:
            if resume_state.timing_queue is None:
                raise EncounterValidationError('Timing continuation is missing its queue payload.')
            return [self._timing_queue_event_for_state(resume_state.timing_queue)]
        raise EncounterValidationError('Unsupported pending resolution kind.')

    def _timing_queue_event_for_state(self, queue: PendingTimingQueueState):
        if queue.phase == TriggerTiming.START_OF_TURN:
            return StartOfTurnTriggersQueuedEvent(queue=queue)
        return EndOfTurnTriggersQueuedEvent(queue=queue)

    def _collect_start_of_turn_entries(self, state: EncounterState, *, actor_id: str) -> tuple[TimingEntryState, ...]:
        actor = self._require_actor(state, actor_id)
        entries: list[TimingEntryState] = []
        if actor.readied_action is not None:
            entries.append(TimingEntryState(entry_id=f'start:ready-expire:{actor.actor_id}', actor_id=actor.actor_id, phase=TriggerTiming.START_OF_TURN, kind=TimingEntryKind.READY_EXPIRE, label='Expire Ready'))
        if actor.shared_senses_actor_id is not None:
            entries.append(TimingEntryState(entry_id=f'start:shared-senses-expire:{actor.actor_id}', actor_id=actor.actor_id, phase=TriggerTiming.START_OF_TURN, kind=TimingEntryKind.SHARED_SENSES_EXPIRE, label='Expire Shared Senses'))
        if actor.eligible_for_death_saves:
            entries.append(TimingEntryState(entry_id=f'start:death-save:{actor.actor_id}', actor_id=actor.actor_id, phase=TriggerTiming.START_OF_TURN, kind=TimingEntryKind.DEATH_SAVE, label='Death Save'))
        if not actor.is_dead and any(capability.recharge_min_roll is not None and capability.remaining_uses == 0 for capability in actor.capabilities.values()):
            entries.append(TimingEntryState(entry_id=f'start:recharge:{actor.actor_id}', actor_id=actor.actor_id, phase=TriggerTiming.START_OF_TURN, kind=TimingEntryKind.CAPABILITY_RECHARGE, label='Recharge'))
        entries.extend(self.effect_executor.collect_turn_boundary_entries(state, actor_id=actor_id, timing=TriggerTiming.START_OF_TURN))
        return tuple(entries)

    def _collect_end_of_turn_entries(self, state: EncounterState, *, actor_id: str) -> tuple[TimingEntryState, ...]:
        return self.effect_executor.collect_turn_boundary_entries(state, actor_id=actor_id, timing=TriggerTiming.END_OF_TURN)

    def _queue_events_for_state(self, queue: PendingTimingQueueState) -> list[object]:
        events: list[object] = [self._timing_queue_event_for_state(queue)]
        if len(queue.entries) > 1:
            events.append(SimultaneousEffectsDetectedEvent(actor_id=queue.actor_id, phase=queue.phase, entry_ids=tuple(entry.entry_id for entry in queue.entries)))
        return events

    def _timing_entry_auto_resolves(self, entry: TimingEntryState) -> bool:
        return entry.kind in {
            TimingEntryKind.ACTIVE_EFFECT_EXPIRE,
            TimingEntryKind.ACTIVE_EFFECT_TRIGGER,
            TimingEntryKind.PERSISTENT_AREA_TICK,
        }

    def _queue_or_auto_resolve_timing_queue(self, state: EncounterState, queue: PendingTimingQueueState) -> list[object]:
        if len(queue.entries) != 1 or not self._timing_entry_auto_resolves(queue.entries[0]):
            return self._queue_events_for_state(queue)
        events = self._queue_events_for_state(queue)
        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        events.extend(self._resolve_timing_queue_entry(preview, queue=queue, entry=queue.entries[0], ordered=False))
        return events

    def _resolve_timing_entry_events(self, state: EncounterState, entry: TimingEntryState) -> list[object]:
        if entry.kind == TimingEntryKind.SHARED_SENSES_EXPIRE:
            actor = self._require_actor(state, entry.actor_id)
            if actor.shared_senses_actor_id is None:
                return []
            return [SharedSensesEndedEvent(actor_id=actor.actor_id, familiar_actor_id=actor.shared_senses_actor_id, reason='start-of-turn')]
        if entry.kind == TimingEntryKind.READY_EXPIRE:
            actor = self._require_actor(state, entry.actor_id)
            events: list[object] = [ReadyExpiredEvent(actor_id=actor.actor_id, reason=entry.phase.value)]
            if actor.readied_action is not None and actor.readied_action.response.response_kind == ReadyResponseKind.SPELL and actor.readied_action.response.spell_id is not None:
                events.append(ReadiedSpellDissipatedEvent(actor_id=actor.actor_id, spell_id=actor.readied_action.response.spell_id, reason='ready-expired'))
            if actor.readied_action is not None and actor.readied_action.concentration_effect_id is not None and actor.readied_action.concentration_effect_id in state.active_effects:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=actor.readied_action.concentration_effect_id, reason='ready-expired'))
            return events
        if entry.kind == TimingEntryKind.DEATH_SAVE:
            preview = copy.deepcopy(state)
            return self._resolve_start_of_turn_death_save_events(preview, actor_id=entry.actor_id)
        if entry.kind == TimingEntryKind.CAPABILITY_RECHARGE:
            preview = copy.deepcopy(state)
            return self._resolve_capability_recharge_events(preview, actor_id=entry.actor_id)
        return self.effect_executor.resolve_turn_boundary_entry(state, entry)

    def _resolve_timing_queue_entry(self, state: EncounterState, *, queue: PendingTimingQueueState, entry: TimingEntryState, ordered: bool) -> list[object]:
        events: list[object] = []
        if ordered and len(queue.entries) > 1:
            remaining_ids = tuple(item.entry_id for item in queue.entries if item.entry_id != entry.entry_id)
            events.append(SimultaneousEffectsOrderedEvent(actor_id=queue.actor_id, phase=queue.phase, chosen_entry_id=entry.entry_id, remaining_entry_ids=remaining_ids))
        entry_events = self._resolve_timing_entry_events(state, entry)
        events.extend(entry_events)
        events.append(TriggerResolutionCompletedEvent(actor_id=queue.actor_id, phase=queue.phase, entry_id=entry.entry_id))
        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        remaining_entries = tuple(item for item in queue.entries if item.entry_id != entry.entry_id)
        cleared_queue = replace(queue, entries=())
        if queue.phase == TriggerTiming.START_OF_TURN:
            if remaining_entries:
                events.extend(self._queue_or_auto_resolve_timing_queue(preview, replace(queue, entries=remaining_entries)))
            else:
                events.append(self._timing_queue_event_for_state(cleared_queue))
            return events
        if remaining_entries:
            events.extend(self._queue_or_auto_resolve_timing_queue(preview, replace(queue, entries=remaining_entries)))
            return events
        events.append(self._timing_queue_event_for_state(cleared_queue))
        if queue.next_actor_id is None or queue.next_round_number is None:
            raise EncounterValidationError('End-of-turn timing queues require next-actor turn metadata.')
        turn_event = TurnEndedEvent(actor_id=queue.actor_id, next_actor_id=queue.next_actor_id, round_number=queue.next_round_number)
        events.append(turn_event)
        self._apply_event(preview, turn_event)
        start_entries = self._collect_start_of_turn_entries(preview, actor_id=queue.next_actor_id)
        if start_entries:
            start_queue = PendingTimingQueueState(actor_id=queue.next_actor_id, phase=TriggerTiming.START_OF_TURN, entries=start_entries)
            events.extend(self._queue_or_auto_resolve_timing_queue(preview, start_queue))
        return events

    def _resolve_choose_timing_order(self, state: EncounterState, intent: ChooseTimingOrderIntent) -> list[object]:
        queue = state.pending_timing_queue
        if queue is None:
            raise EncounterValidationError('There is no active timing-order choice.')
        if queue.actor_id != intent.actor_id:
            raise EncounterValidationError('The chosen actor does not own the active timing-order choice.')
        selected = next((entry for entry in queue.entries if entry.entry_id == intent.entry_id), None)
        if selected is None:
            raise EncounterValidationError('The chosen timing entry is not legal for the active queue.')
        return self._resolve_timing_queue_entry(state, queue=queue, entry=selected, ordered=True)

    def _resolve_continue_timing_queue(self, state: EncounterState, intent: ContinueTimingIntent) -> list[object]:
        queue = state.pending_timing_queue
        if queue is None:
            raise EncounterValidationError('There is no active timing queue to continue.')
        if queue.actor_id != intent.actor_id:
            raise EncounterValidationError('The chosen actor does not own the active timing queue.')
        if not queue.entries:
            raise EncounterValidationError('The active timing queue is already empty.')
        if len(queue.entries) > 1:
            raise EncounterValidationError('A simultaneous timing choice is required before the queue can continue.')
        return self._resolve_timing_queue_entry(state, queue=queue, entry=queue.entries[0], ordered=False)


    def _resolve_illusion_interaction(self, state: EncounterState, intent: ResolveIllusionInteractionIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        self._require_conscious(actor)
        illusion = state.illusions.get(intent.illusion_id)
        if illusion is None:
            raise EncounterValidationError('Unknown illusion.')
        if not illusion.persistent.observer_actor_ids and illusion.persistent.observer_mode.value == 'selected-observers':
            raise EncounterValidationError('The illusion has no valid observers configured.')
        updated = update_illusion_observer_state(illusion, observer_id=actor.actor_id, interaction_kind=intent.interaction_kind)
        events: list[object] = [
            IllusionInteractedWithEvent(
                illusion_id=illusion.illusion_id,
                observer_id=actor.actor_id,
                interaction_kind=intent.interaction_kind.value,
            )
        ]
        observer_ids = set(illusion.observer_states) | set(updated.observer_states)
        observer_ids.add(actor.actor_id)
        for observer_id in sorted(observer_ids):
            before_status = illusion.observer_states.get(observer_id).status.value if observer_id in illusion.observer_states else 'intended'
            after_status = updated.observer_states.get(observer_id).status.value if observer_id in updated.observer_states else 'intended'
            if before_status == after_status:
                continue
            if before_status in {'intended', 'unaware'} and after_status in {'suspects', 'pierced', 'disbelieved'}:
                events.append(IllusionRevealedToObserverEvent(illusion_id=illusion.illusion_id, observer_id=observer_id))
            if after_status == 'disbelieved':
                events.append(IllusionDisbelievedByObserverEvent(illusion_id=illusion.illusion_id, observer_id=observer_id))
        return events

    def _resolve_start_ritual_cast(self, state: EncounterState, intent: StartRitualCastIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        self._require_conscious(actor)
        capability = None
        capability_id = intent.capability_id
        spell_id = intent.spell_id
        if spell_id is not None:
            spell = actor.spells.get(spell_id)
            if spell is None or spell.capability is None:
                raise EncounterValidationError('The chosen spell does not expose a ritual-capable executable definition.')
            capability = spell.capability
            capability_id = capability.capability_id
        else:
            runtime_capability = actor.capabilities.get(intent.capability_id)
            if runtime_capability is None:
                runtime_capability = next((item for item in actor.capabilities.values() if item.capability.capability_id == intent.capability_id), None)
            if runtime_capability is None:
                raise EncounterValidationError('Unknown ritual-capable capability.')
            capability = runtime_capability.capability
            capability_id = capability.capability_id
        ritual = capability.ritual_casting
        if ritual is None or not ritual.can_cast_as_ritual:
            raise EncounterValidationError('That capability cannot be cast as a ritual.')
        if ritual.non_combat_only and state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Ritual casting is not legal during combat.')
        if any(existing.actor_id == actor.actor_id for existing in state.ritual_casts.values()):
            raise EncounterValidationError('That actor is already performing a ritual cast.')
        ritual_id = f'ritual:{actor.actor_id}:{capability_id}:{len(state.event_log)}'
        return [
            RitualCastStartedEvent(
                ritual=RitualCastingState(
                    ritual_id=ritual_id,
                    actor_id=actor.actor_id,
                    capability_id=capability_id,
                    total_seconds=ritual.additional_cast_seconds,
                    remaining_seconds=ritual.additional_cast_seconds,
                    no_slot_cost=ritual.no_slot_cost,
                    spell_id=spell_id,
                )
            )
        ]
    def _require_item_record(self, item_id: str) -> ItemRecord:
        item = self.item_catalog.get(item_id)
        if item is None:
            raise EncounterValidationError(f'Unknown item: {item_id}.')
        return item

    def _next_ground_item_id(self, state: EncounterState, item_id: str) -> str:
        index = len(state.ground_items) + 1
        candidate = f'ground-item-{item_id}-{index}'
        while candidate in state.ground_items:
            index += 1
            candidate = f'ground-item-{item_id}-{index}'
        return candidate

    def _resolve_interaction_actor(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        cost_mode: ObjectInteractionCostMode,
        allow_attack_timing: bool,
    ) -> RuntimeActorState:
        if state.phase == EncounterPhase.IN_PROGRESS:
            actor = self._require_active_actor(state, actor_id)
        else:
            actor = self._require_actor(state, actor_id)
        self._require_conscious(actor)
        if cost_mode == ObjectInteractionCostMode.ATTACK and not allow_attack_timing:
            raise EncounterValidationError('Attack-timed weapon interactions are only legal inside the Attack action.')
        if state.phase == EncounterPhase.IN_PROGRESS:
            if cost_mode == ObjectInteractionCostMode.FREE and not actor.remaining_free_object_interaction:
                raise EncounterValidationError('The actor has already used its free object interaction this turn.')
            if cost_mode == ObjectInteractionCostMode.UTILIZE:
                self._require_action_permission(actor)
        elif cost_mode == ObjectInteractionCostMode.ATTACK:
            raise EncounterValidationError('Attack-timed interactions are only legal during encounter turns.')
        return actor

    def _interaction_cost_events(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        interaction_kind: ObjectInteractionKind,
        cost_mode: ObjectInteractionCostMode,
    ) -> list[object]:
        if state.phase != EncounterPhase.IN_PROGRESS:
            return []
        if cost_mode == ObjectInteractionCostMode.FREE:
            return [ResourceSpentEvent(actor_id=actor.actor_id, resource='object', reason=interaction_kind.value)]
        if cost_mode == ObjectInteractionCostMode.UTILIZE:
            return [
                ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.UTILIZE, detail=interaction_kind.value),
                ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.UTILIZE),
                ResourceSpentEvent(actor_id=actor.actor_id, resource='action', reason='utilize'),
                UtilizeActionUsedEvent(actor_id=actor.actor_id, interaction_kind=interaction_kind),
            ]
        return []

    def _actor_can_reach_cells(self, actor: RuntimeActorState, cells: tuple[GridPosition, ...], *, origin_position: GridPosition | None = None, reach_ft: int = 5) -> bool:
        origin = actor.position if origin_position is None else origin_position
        return any(grid_distance_ft(origin, cell) <= reach_ft for cell in cells)

    def _resolve_object_interaction_events(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        interaction_kind: ObjectInteractionKind,
        cost_mode: ObjectInteractionCostMode,
        item_id: str | None = None,
        ground_item_id: str | None = None,
        object_id: str | None = None,
        object_action: EnvironmentObjectAction | None = None,
        source_actor_id: str | None = None,
        origin_position: GridPosition | None = None,
        reach_ft: int = 5,
    ) -> list[object]:
        if interaction_kind in {ObjectInteractionKind.DON_SHIELD, ObjectInteractionKind.DOFF_SHIELD, ObjectInteractionKind.DON_ARMOR, ObjectInteractionKind.DOFF_ARMOR} and cost_mode != ObjectInteractionCostMode.UTILIZE:
            raise EncounterValidationError('Shield and armor don/doff interactions require the Utilize action path.')
        events = self._interaction_cost_events(state, actor=actor, interaction_kind=interaction_kind, cost_mode=cost_mode)
        events.append(
            ObjectInteractionUsedEvent(
                actor_id=actor.actor_id,
                interaction_kind=interaction_kind,
                cost_mode=cost_mode,
                item_id=item_id,
                ground_item_id=ground_item_id,
                object_id=object_id,
                object_action=object_action,
            )
        )
        if interaction_kind == ObjectInteractionKind.DRAW:
            if item_id is None:
                raise EncounterValidationError('Draw requires an item id.')
            item = self._require_item_record(item_id)
            if item_is_armor(item) or item_is_shield(item):
                raise EncounterValidationError('Armor and shields must be donned instead of drawn.')
            if stowed_quantity(actor, item_id) <= 0:
                raise EncounterValidationError("That item is not available to draw from the actor's carried gear.")
            if not can_hold_item(actor, item, self.item_catalog):
                raise EncounterValidationError('The actor does not have enough free hands to draw that item.')
            slot = first_available_hand_slot(actor, item, self.item_catalog)
            if slot is None:
                raise EncounterValidationError('The actor does not have enough free hands to draw that item.')
            events.append(ItemDrawnEvent(actor_id=actor.actor_id, item_id=item_id))
            if item_is_weapon(item):
                events.append(WeaponEquippedEvent(actor_id=actor.actor_id, item_id=item_id, slot=slot))
            return events
        if interaction_kind == ObjectInteractionKind.STOW:
            if item_id is None:
                raise EncounterValidationError('Stow requires an item id.')
            item = self._require_item_record(item_id)
            if not is_item_held(actor, item_id, self.item_catalog):
                raise EncounterValidationError('That item is not currently held.')
            slot = hand_slot_for_item(actor, item_id)
            events.append(ItemStowedEvent(actor_id=actor.actor_id, item_id=item_id))
            if item_is_weapon(item) and slot is not None:
                events.append(WeaponUnequippedEvent(actor_id=actor.actor_id, item_id=item_id, slot=slot))
            return events
        if interaction_kind == ObjectInteractionKind.DROP:
            if item_id is None:
                raise EncounterValidationError('Drop requires an item id.')
            item = self._require_item_record(item_id)
            if not is_item_held(actor, item_id, self.item_catalog):
                raise EncounterValidationError('Only held items can be dropped in this slice.')
            slot = hand_slot_for_item(actor, item_id)
            next_ground_item_id = self._next_ground_item_id(state, item_id)
            events.append(ItemDroppedEvent(actor_id=actor.actor_id, item_id=item_id, quantity=1, ground_item_id=next_ground_item_id, position=actor.position))
            events.append(GroundItemCreatedEvent(ground_item_id=next_ground_item_id, item_id=item_id, quantity=1, position=actor.position))
            if item_is_weapon(item) and slot is not None:
                events.append(WeaponUnequippedEvent(actor_id=actor.actor_id, item_id=item_id, slot=slot))
            return events
        if interaction_kind == ObjectInteractionKind.PICK_UP:
            if ground_item_id is None:
                raise EncounterValidationError('Pick up requires a ground item id.')
            ground_item = state.ground_items.get(ground_item_id)
            if ground_item is None:
                raise EncounterValidationError('That ground item is not present on the battlefield.')
            if not self._actor_can_reach_cells(actor, (ground_item.position,), origin_position=origin_position, reach_ft=reach_ft):
                raise EncounterValidationError('The actor is not close enough to pick up that item.')
            item = self._require_item_record(ground_item.item_id)
            if ground_item.quantity != 1:
                raise EncounterValidationError('Picking up stacked ground items is not supported in this slice.')
            if not can_hold_item(actor, item, self.item_catalog):
                raise EncounterValidationError('The actor does not have enough free hands to pick up that item.')
            slot = first_available_hand_slot(actor, item, self.item_catalog)
            if slot is None:
                raise EncounterValidationError('The actor does not have enough free hands to pick up that item.')
            events.append(GroundItemRemovedEvent(ground_item_id=ground_item.ground_item_id))
            events.append(ItemPickedUpEvent(actor_id=actor.actor_id, item_id=ground_item.item_id, quantity=1, ground_item_id=ground_item.ground_item_id))
            if item_is_weapon(item):
                events.append(WeaponEquippedEvent(actor_id=actor.actor_id, item_id=ground_item.item_id, slot=slot))
            return events
        if interaction_kind == ObjectInteractionKind.TRANSFER:
            if source_actor_id is None or item_id is None:
                raise EncounterValidationError('Transfer requires a source actor id and an item id.')
            source_actor = state.actors.get(source_actor_id)
            if source_actor is None:
                raise EncounterValidationError('The source actor is not present in the encounter state.')
            if source_actor.side != actor.side:
                raise EncounterValidationError('Transfer only supports allied inventory in this slice.')
            if stowed_quantity(source_actor, item_id, self.item_catalog) <= 0:
                raise EncounterValidationError('The source actor is not carrying that transferable item.')
            item = self._require_item_record(item_id)
            events.append(ItemTransferredEvent(source_actor_id=source_actor_id, target_actor_id=actor.actor_id, item_id=item_id, quantity=1, reason='interact-transfer'))
            return events
        if interaction_kind == ObjectInteractionKind.DON_SHIELD:
            if item_id is None:
                raise EncounterValidationError('Don shield requires an item id.')
            item = self._require_item_record(item_id)
            if not item_is_shield(item):
                raise EncounterValidationError('The chosen item is not a shield.')
            if carried_quantity(actor, item_id) <= 0:
                raise EncounterValidationError('The actor is not carrying that shield.')
            if actor.worn_shield_item_id is not None:
                raise EncounterValidationError('The actor is already wielding a shield.')
            if free_hands(actor, self.item_catalog) < 1:
                raise EncounterValidationError('The actor needs a free hand to don a shield.')
            events.append(ShieldDonnedEvent(actor_id=actor.actor_id, item_id=item_id))
            return events
        if interaction_kind == ObjectInteractionKind.DOFF_SHIELD:
            shield_item_id = actor.worn_shield_item_id
            if shield_item_id is None:
                raise EncounterValidationError('The actor is not wielding a shield.')
            if item_id is not None and item_id != shield_item_id:
                raise EncounterValidationError('The chosen shield does not match the currently wielded shield.')
            events.append(ShieldDoffedEvent(actor_id=actor.actor_id, item_id=shield_item_id))
            return events
        if interaction_kind == ObjectInteractionKind.DON_ARMOR:
            if item_id is None:
                raise EncounterValidationError('Don armor requires an item id.')
            item = self._require_item_record(item_id)
            if not item_is_armor(item):
                raise EncounterValidationError('The chosen item is not armor.')
            if carried_quantity(actor, item_id) <= 0:
                raise EncounterValidationError('The actor is not carrying that armor.')
            if actor.worn_armor_item_id is not None:
                raise EncounterValidationError('The actor is already wearing armor.')
            if state.phase == EncounterPhase.IN_PROGRESS:
                raise EncounterValidationError('Armor donning time is too long for this in-combat deterministic slice.')
            events.append(TimeAdvancedEvent(elapsed_seconds=armor_don_time_seconds(item), activity_type=RestActivityType.EXERTION))
            events.append(ArmorDonnedEvent(actor_id=actor.actor_id, item_id=item_id))
            return events
        if interaction_kind == ObjectInteractionKind.DOFF_ARMOR:
            armor_item_id = actor.worn_armor_item_id
            if armor_item_id is None:
                raise EncounterValidationError('The actor is not wearing armor.')
            item = self._require_item_record(armor_item_id)
            if item_id is not None and item_id != armor_item_id:
                raise EncounterValidationError('The chosen armor does not match the currently worn armor.')
            if state.phase == EncounterPhase.IN_PROGRESS:
                raise EncounterValidationError('Armor doffing time is too long for this in-combat deterministic slice.')
            events.append(TimeAdvancedEvent(elapsed_seconds=armor_doff_time_seconds(item), activity_type=RestActivityType.EXERTION))
            events.append(ArmorDoffedEvent(actor_id=actor.actor_id, item_id=armor_item_id))
            return events
        if interaction_kind == ObjectInteractionKind.USE_ENVIRONMENT_OBJECT:
            if object_id is None or object_action is None:
                raise EncounterValidationError('Environment interaction requires an object id and object action.')
            environment_object = state.environment_objects.get(object_id)
            if environment_object is None:
                raise EncounterValidationError('That environment object is not available in the encounter state.')
            if object_action not in environment_object.allowed_actions:
                raise EncounterValidationError('That action is not supported for the chosen environment object.')
            if not self._actor_can_reach_cells(actor, environment_object.position_cells, origin_position=origin_position, reach_ft=reach_ft):
                raise EncounterValidationError('The actor is not close enough to use that environment object.')
            if object_action == EnvironmentObjectAction.OPEN and environment_object.open_state is False:
                events.append(EnvironmentObjectUsedEvent(actor_id=actor.actor_id, object_id=object_id, action=object_action))
                return events
            if object_action == EnvironmentObjectAction.CLOSE and environment_object.open_state is True:
                events.append(EnvironmentObjectUsedEvent(actor_id=actor.actor_id, object_id=object_id, action=object_action))
                return events
            if object_action in {EnvironmentObjectAction.TOGGLE, EnvironmentObjectAction.ACTIVATE, EnvironmentObjectAction.DEACTIVATE}:
                events.append(EnvironmentObjectUsedEvent(actor_id=actor.actor_id, object_id=object_id, action=object_action))
                return events
            raise EncounterValidationError('The requested environment-object state change is not currently legal.')
        raise EncounterValidationError('Unsupported object interaction kind for this deterministic slice.')

    def _resolve_object_interaction(self, state: EncounterState, intent: ObjectInteractionIntent) -> list[object]:
        actor = self._resolve_interaction_actor(state, actor_id=intent.actor_id, cost_mode=intent.cost_mode, allow_attack_timing=False)
        return self._resolve_object_interaction_events(
            state,
            actor=actor,
            interaction_kind=intent.interaction_kind,
            cost_mode=intent.cost_mode,
            item_id=intent.item_id,
            ground_item_id=intent.ground_item_id,
            object_id=intent.object_id,
            object_action=intent.object_action,
            source_actor_id=intent.source_actor_id,
        )

    def _resolve_equip_item(self, state: EncounterState, intent: EquipItemIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        if actor.current_hit_points <= 0:
            raise EncounterValidationError('An unconscious or dying actor cannot change equipment slots.')
        item = self._require_item_record(intent.item_id)
        if carried_quantity(actor, intent.item_id) <= 0:
            raise EncounterValidationError('The actor is not carrying that item.')
        events: list[object] = []
        if intent.slot == EquipmentSlot.ARMOR:
            if not item_is_armor(item):
                raise EncounterValidationError('Only armor can be equipped to the armor slot.')
            if state.phase == EncounterPhase.IN_PROGRESS:
                raise EncounterValidationError('Armor equipping time is too long for this in-combat deterministic slice.')
            if actor.equipped_armor_item_id == intent.item_id:
                raise EncounterValidationError('That armor is already equipped.')
            if actor.equipped_armor_item_id is not None:
                current_armor = self._require_item_record(actor.equipped_armor_item_id)
                events.append(TimeAdvancedEvent(elapsed_seconds=armor_doff_time_seconds(current_armor), activity_type=RestActivityType.EXERTION))
                events.append(ArmorDoffedEvent(actor_id=actor.actor_id, item_id=actor.equipped_armor_item_id))
            events.append(TimeAdvancedEvent(elapsed_seconds=armor_don_time_seconds(item), activity_type=RestActivityType.EXERTION))
            events.append(ArmorDonnedEvent(actor_id=actor.actor_id, item_id=intent.item_id))
            return events
        if item_is_armor(item):
            raise EncounterValidationError('Armor can only be equipped to the armor slot.')
        if intent.slot == EquipmentSlot.MAIN_HAND and item_is_shield(item):
            raise EncounterValidationError('Shields can only be equipped to the off hand.')
        if intent.slot == EquipmentSlot.OFF_HAND and required_hand_count(item) >= 2:
            raise EncounterValidationError('Two-handed weapons cannot be equipped to the off hand.')
        if intent.slot == EquipmentSlot.OFF_HAND:
            main_item = self.item_catalog.get(actor.main_hand_item_id) if actor.main_hand_item_id is not None else None
            if main_item is not None and required_hand_count(main_item) >= 2:
                raise EncounterValidationError('The main-hand item already requires both hands.')
        if intent.slot == EquipmentSlot.MAIN_HAND and required_hand_count(item) >= 2 and actor.off_hand_item_id is not None and actor.off_hand_item_id != intent.item_id:
            raise EncounterValidationError('The off hand must be empty to equip a two-handed weapon.')
        if intent.slot == EquipmentSlot.MAIN_HAND and actor.main_hand_item_id == intent.item_id:
            raise EncounterValidationError('That item is already equipped in the main hand.')
        if intent.slot == EquipmentSlot.OFF_HAND and actor.off_hand_item_id == intent.item_id:
            raise EncounterValidationError('That item is already equipped in the off hand.')
        existing_slot = hand_slot_for_item(actor, intent.item_id)
        if existing_slot is not None and existing_slot != intent.slot:
            if item_is_shield(item):
                events.append(ShieldDoffedEvent(actor_id=actor.actor_id, item_id=intent.item_id))
            else:
                events.append(WeaponUnequippedEvent(actor_id=actor.actor_id, item_id=intent.item_id, slot=existing_slot))
        current_item_id = actor.main_hand_item_id if intent.slot == EquipmentSlot.MAIN_HAND else actor.off_hand_item_id
        if current_item_id is not None and current_item_id != intent.item_id and item_is_weapon(self.item_catalog.get(current_item_id)):
            events.append(WeaponUnequippedEvent(actor_id=actor.actor_id, item_id=current_item_id, slot=intent.slot))
        if current_item_id is not None and current_item_id != intent.item_id and item_is_shield(self.item_catalog.get(current_item_id)):
            events.append(ShieldDoffedEvent(actor_id=actor.actor_id, item_id=current_item_id))
        if item_is_shield(item):
            events.append(ShieldDonnedEvent(actor_id=actor.actor_id, item_id=intent.item_id))
            return events
        events.append(WeaponEquippedEvent(actor_id=actor.actor_id, item_id=intent.item_id, slot=intent.slot))
        return events

    def _preview_attack_interactions(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        attack_interaction,
    ) -> tuple[EncounterState, list[object], list[object]]:
        preview_state = copy.deepcopy(state)
        preview_actor = preview_state.actors[actor_id]
        before_events: list[object] = []
        after_events: list[object] = []
        if attack_interaction is None:
            return preview_state, before_events, after_events
        if attack_interaction.timing == AttackInteractionTiming.BEFORE:
            before_events = self._resolve_object_interaction_events(
                preview_state,
                actor=preview_actor,
                interaction_kind=attack_interaction.interaction_kind,
                cost_mode=ObjectInteractionCostMode.ATTACK,
                item_id=attack_interaction.item_id,
                ground_item_id=attack_interaction.ground_item_id,
            )
            for event in before_events:
                self._apply_event(preview_state, event)
            return preview_state, before_events, after_events
        after_events = self._resolve_object_interaction_events(
            preview_state,
            actor=preview_actor,
            interaction_kind=attack_interaction.interaction_kind,
            cost_mode=ObjectInteractionCostMode.ATTACK,
            item_id=attack_interaction.item_id,
            ground_item_id=attack_interaction.ground_item_id,
        )
        return preview_state, before_events, after_events

    def _attack_meets_hand_requirements(self, actor: RuntimeActorState, attack) -> bool:
        if attack.required_hand_count <= 1:
            return True
        remaining_held = list(actor.held_item_ids)
        if attack.source_item_id is not None:
            try:
                remaining_held.remove(attack.source_item_id)
            except ValueError:
                return False
        return actor.worn_shield_item_id is None and not remaining_held

    def _attack_is_available_choice(self, actor: RuntimeActorState, attack) -> bool:
        if attack.source_item_id is None:
            return True
        try:
            self._validate_attack_equipment(actor, attack, spend_resource='action')
        except EncounterValidationError:
            return False
        return True

    def _validate_attack_equipment(self, actor: RuntimeActorState, attack, *, spend_resource: str) -> None:
        if attack.source_item_id is None:
            return
        item = self._require_item_record(attack.source_item_id)
        if carried_quantity(actor, attack.source_item_id) <= 0:
            raise EncounterValidationError('The actor is not carrying the item required for that attack.')
        if not is_item_held(actor, attack.source_item_id, self.item_catalog):
            raise EncounterValidationError('The required weapon is not currently equipped or held.')
        if hands_used(actor, self.item_catalog) > 2 or not self._attack_meets_hand_requirements(actor, attack):
            raise EncounterValidationError('The actor does not have the required free hands for that weapon use.')
        if attack.ammunition_item_id is not None and carried_quantity(actor, attack.ammunition_item_id) <= 0:
            raise EncounterValidationError('That attack requires ammunition the actor is not carrying.')
        if attack.loading and spend_resource in actor.loading_spent_resources:
            raise EncounterValidationError('That loading weapon has already been fired with this resource.')
        if item_is_shield(item):
            raise EncounterValidationError('Shields cannot be used as weapon attacks in this path.')

    def _attack_side_effect_events(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        target: RuntimeActorState,
        attack,
    ) -> list[object]:
        events: list[object] = []
        if attack.ammunition_item_id is not None:
            if carried_quantity(actor, attack.ammunition_item_id) <= 0:
                raise EncounterValidationError('That attack requires ammunition the actor is not carrying.')
            events.append(AmmunitionConsumedEvent(actor_id=actor.actor_id, weapon_item_id=attack.source_item_id or attack.attack_id, ammunition_item_id=attack.ammunition_item_id, quantity=1))
        if attack.attack_usage_kind == AttackUsageKind.THROWN_WEAPON and attack.source_item_id is not None:
            slot = hand_slot_for_item(actor, attack.source_item_id)
            ground_item_id = self._next_ground_item_id(state, attack.source_item_id)
            events.append(ItemDroppedEvent(actor_id=actor.actor_id, item_id=attack.source_item_id, quantity=1, ground_item_id=ground_item_id, position=target.position))
            events.append(GroundItemCreatedEvent(ground_item_id=ground_item_id, item_id=attack.source_item_id, quantity=1, position=target.position))
            if slot is not None:
                events.append(WeaponUnequippedEvent(actor_id=actor.actor_id, item_id=attack.source_item_id, slot=slot))
        return events

    def _resolve_attack_with_profile(
        self,
        state: EncounterState,
        *,
        actor: RuntimeActorState,
        attack,
        target: RuntimeActorState,
        action_type: CombatActionType,
        spend_resource: str,
        allow_hit_reactions: bool,
        pre_events: list[object] | None = None,
        post_roll_events: list[object] | None = None,
        resume_state: PendingResolutionState | None = None,
    ) -> list[object]:
        legality = self.battlefield_rules.attack_legality(state, actor, target, attack)
        modifiers = self._attack_modifier_state(state, actor, target, distance_ft=legality.distance_ft, long_range_disadvantage=legality.long_range_disadvantage)
        request = D20TestRequest(
            request_id=f'attack:{actor.actor_id}:{attack.attack_id}:{target.actor_id}:{state.random_counter}',
            test_type=D20TestType.ATTACK,
            actor_id=actor.actor_id,
            flat_modifier=attack.to_hit_bonus + modifiers['modifier'],
            roll_mode=merge_roll_mode(advantage=modifiers['advantage'], disadvantage=modifiers['disadvantage']),
            dc=target.effective_armor_class + legality.armor_class_bonus,
        )
        resolution = self.d20_engine.resolve(request, random_counter=state.random_counter)
        events: list[object] = list(pre_events or [])
        events.extend(modifiers.get('effect_events', ()))
        events.extend([
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=action_type, target_id=target.actor_id, detail=attack.attack_id),
            AttackDeclaredEvent(actor_id=actor.actor_id, attack_id=attack.attack_id, target_id=target.actor_id, action_type=action_type, resource=spend_resource),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=action_type),
            ResourceSpentEvent(actor_id=actor.actor_id, resource=spend_resource, reason=action_type.value),
        ])
        if actor.hidden:
            events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=action_type.value))
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, hidden=False))
        sanctuary_allows, sanctuary_events = self._resolve_sanctuary_targeting(state, acting_actor=actor, target=target)
        events.extend(sanctuary_events)
        if not sanctuary_allows:
            events.append(AttackMissedEvent(actor_id=actor.actor_id, attack_id=attack.attack_id, target_id=target.actor_id))
            return events
        events.append(D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used))
        events.append(AttackRolledEvent(actor_id=actor.actor_id, attack_id=attack.attack_id, target_id=target.actor_id, attack_rolls=resolution.result.rolls, attack_total=resolution.result.total, random_counter_used=resolution.random_counter_used))
        events.extend(self._consume_next_incoming_attack_roll_effects(tuple(modifiers.get('consumed_incoming_attack_advantage_effect_ids', ()))))
        events.extend(post_roll_events or [])
        pending_attack = PendingAttackState(
            actor_id=actor.actor_id,
            attack_id=attack.attack_id,
            target_id=target.actor_id,
            attack_rolls=resolution.result.rolls,
            selected_roll=resolution.result.selected_roll,
            attack_total=resolution.result.total,
            target_armor_class_modifier=legality.armor_class_bonus,
            critical_on_hit=(modifiers.get('critical_on_hit', False) or resolution.result.critical_success),
            had_advantage=bool(modifiers.get('advantage', False)),
            had_disadvantage=bool(modifiers.get('disadvantage', False)),
            attack_kind=attack.attack_kind,
            attack_usage_kind=attack.attack_usage_kind,
            source_item_id=attack.source_item_id,
            damage_dice_count=attack.damage_dice_count,
            damage_die_faces=attack.damage_die_faces,
            damage_bonus=attack.damage_bonus,
            damage_type=attack.damage_type,
        )
        if resolution.result.success:
            if allow_hit_reactions:
                reaction_options = self._sorted_reaction_options(discover_hit_reactions(state, target_id=target.actor_id))
                if reaction_options:
                    window = ReactionWindowState(
                        trigger_id=f'hit:{actor.actor_id}:{target.actor_id}:{attack.attack_id}:{state.random_counter}',
                        trigger_type=ReactionTriggerType.HIT_DETECTED,
                        pending_actor_id=target.actor_id,
                        prompt='A hit was detected. Choose a legal reaction or decline.',
                        options=reaction_options,
                        pending_attack=pending_attack,
                        resume_state=self._chain_resume_states(
                            PendingResolutionState(
                                kind=PendingResolutionKind.FINALIZE_ATTACK,
                                pending_attack=pending_attack,
                            ),
                            resume_state,
                        ),
                    )
                    events.append(ReactionWindowOpenedEvent(window=window))
                    return events
            post_hit_options = self._sorted_reaction_options(discover_post_hit_reactions(state, pending_attack=pending_attack))
            if post_hit_options:
                events.append(
                    ReactionWindowOpenedEvent(
                        window=ReactionWindowState(
                            trigger_id=f'post-hit:{actor.actor_id}:{target.actor_id}:{attack.attack_id}:{state.random_counter}',
                            trigger_type=ReactionTriggerType.POST_HIT_TRIGGER,
                            pending_actor_id=actor.actor_id,
                            prompt='A post-hit spell trigger is available. Choose a legal option or decline.',
                            options=post_hit_options,
                            pending_attack=pending_attack,
                            resume_state=self._chain_resume_states(
                                PendingResolutionState(
                                    kind=PendingResolutionKind.APPLY_ATTACK_DAMAGE,
                                    pending_attack=pending_attack,
                                ),
                                resume_state,
                            ),
                        )
                    )
                )
                return events
            hit_events, _ = self._finalize_pending_attack(state, pending_attack, armor_class_bonus=0, damage_counter=state.random_counter + 1)
            events.extend(hit_events)
            return events
        events.append(AttackMissedEvent(actor_id=actor.actor_id, attack_id=attack.attack_id, target_id=target.actor_id))
        return events

    def _resolve_use_improvised_weapon(self, state: EncounterState, intent: UseImprovisedWeaponIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        target = self._require_target(state, intent.target_id)
        self._require_conscious(actor)
        self._require_action_permission(actor)
        if target.is_dead:
            raise EncounterValidationError('The chosen target is already dead.')
        if actor.side == target.side:
            raise EncounterValidationError('Hostile attacks require an opposing target.')
        validate_hostile_targeting(actor, target, is_damaging=True, is_magical=False)
        item: ItemRecord | None = None
        pre_events: list[object] = []
        post_events: list[object] = []
        if intent.item_id is not None:
            item = self._require_item_record(intent.item_id)
            if carried_quantity(actor, intent.item_id) <= 0:
                raise EncounterValidationError('The actor is not carrying that improvised-weapon item.')
            if not is_item_held(actor, intent.item_id):
                raise EncounterValidationError('The improvised item must be held before it can be used as a weapon.')
            if intent.thrown:
                ground_item_id = self._next_ground_item_id(state, intent.item_id)
                post_events.extend([
                    ItemDroppedEvent(actor_id=actor.actor_id, item_id=intent.item_id, quantity=1, ground_item_id=ground_item_id, position=target.position),
                    GroundItemCreatedEvent(ground_item_id=ground_item_id, item_id=intent.item_id, quantity=1, position=target.position, improvised_damage_type=intent.damage_type, equivalent_weapon_item_id=intent.equivalent_weapon_item_id),
                ])
        elif intent.object_id is not None:
            environment_object = state.environment_objects.get(intent.object_id)
            if environment_object is None:
                raise EncounterValidationError('That environment object is not available for improvised weapon use.')
            if not self._actor_can_reach_cells(actor, environment_object.position_cells):
                raise EncounterValidationError('The actor is not close enough to use that object as an improvised weapon.')
        else:
            raise EncounterValidationError('Improvised weapon use requires a carried item or environment object in this deterministic slice.')
        if intent.equivalent_weapon_item_id is not None:
            equivalent_item = self._require_item_record(intent.equivalent_weapon_item_id)
            if not item_is_weapon(equivalent_item):
                raise EncounterValidationError('The equivalent improvised-weapon item must be a weapon.')
            preview_actor = copy.deepcopy(actor)
            preview_actor.carried_item_counts[equivalent_item.record_id] = 1
            append_held_item(preview_actor, equivalent_item.record_id, self.item_catalog)
            refresh_actor_equipment_state(preview_actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            derived = next((candidate for candidate in preview_actor.attacks.values() if candidate.source_item_id == equivalent_item.record_id and ((candidate.attack_usage_kind == AttackUsageKind.THROWN_WEAPON) if intent.thrown else (candidate.attack_usage_kind in {AttackUsageKind.WEAPON_MELEE, AttackUsageKind.WEAPON_RANGED}))), None)
            if derived is None:
                raise EncounterValidationError('Could not derive the equivalent improvised-weapon attack profile.')
            attack = replace(derived, attack_id=f'improvised:{intent.actor_id}:{intent.target_id}:{intent.equivalent_weapon_item_id}', name=f'Improvised {equivalent_item.name}')
        else:
            attack = AttackProfile(
                attack_id=f'improvised:{intent.actor_id}:{intent.target_id}:{intent.damage_type}',
                name='Improvised Weapon',
                attack_kind=(AttackKind.RANGED if intent.thrown else AttackKind.MELEE),
                to_hit_bonus=actor.ability_modifiers[Ability.STR],
                reach_ft=(None if intent.thrown else 5),
                range_ft=(20 if intent.thrown else None),
                long_range_ft=(60 if intent.thrown else None),
                damage_dice_count=1,
                damage_die_faces=4,
                damage_bonus=actor.ability_modifiers[Ability.STR],
                damage_type=intent.damage_type,
                attack_usage_kind=(AttackUsageKind.IMPROVISED_THROWN if intent.thrown else AttackUsageKind.IMPROVISED_MELEE),
                source_item_id=intent.item_id,
                required_hand_count=1,
            )
        pre_events.append(ImprovisedWeaponUsedEvent(actor_id=actor.actor_id, target_id=target.actor_id, item_id=intent.item_id, ground_item_id=intent.ground_item_id, object_id=intent.object_id, thrown=intent.thrown))
        return self._resolve_attack_with_profile(
            state,
            actor=actor,
            attack=attack,
            target=target,
            action_type=CombatActionType.ATTACK,
            spend_resource='action',
            allow_hit_reactions=True,
            pre_events=pre_events,
            post_roll_events=post_events,
        )

    def _resolve_attack_action(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        attack_id: str,
        target_id: str,
        action_type: CombatActionType = CombatActionType.ATTACK,
        spend_resource: str = 'action',
        allow_hit_reactions: bool = True,
        require_turn: bool = True,
        attack_interaction=None,
        resume_state: PendingResolutionState | None = None,
    ) -> list[object]:
        actor = self._require_active_actor(state, actor_id) if require_turn else self._require_actor(state, actor_id)
        target = self._require_target(state, target_id)
        self._require_conscious(actor)
        if target.is_dead:
            raise EncounterValidationError('The chosen target is already dead.')
        if actor.side == target.side:
            raise EncounterValidationError('Hostile attacks require an opposing target.')
        if spend_resource == 'action':
            self._require_action_permission(actor)
        if spend_resource == 'reaction':
            self._require_reaction_permission(actor)
        validate_hostile_targeting(actor, target, is_damaging=True, is_magical=False)
        preview_state, before_events, after_events = self._preview_attack_interactions(state, actor_id=actor_id, attack_interaction=attack_interaction)
        preview_actor = preview_state.actors[actor_id]
        preview_target = preview_state.actors[target_id]
        attack = preview_actor.attacks.get(attack_id)
        if attack is None:
            raise EncounterValidationError('That attack is not available to the acting actor.')
        self._validate_attack_equipment(preview_actor, attack, spend_resource=spend_resource)
        side_effect_events = self._attack_side_effect_events(preview_state, actor=preview_actor, target=preview_target, attack=attack)
        if attack_interaction is not None and attack_interaction.timing == AttackInteractionTiming.AFTER and attack.attack_usage_kind == AttackUsageKind.THROWN_WEAPON and attack_interaction.item_id == attack.source_item_id:
            raise EncounterValidationError("A thrown weapon cannot be stowed or dropped again as the same attack's after-interaction.")
        return self._resolve_attack_with_profile(
            preview_state,
            actor=preview_actor,
            attack=attack,
            target=preview_target,
            action_type=action_type,
            spend_resource=spend_resource,
            allow_hit_reactions=allow_hit_reactions,
            pre_events=before_events,
            post_roll_events=side_effect_events + after_events,
            resume_state=resume_state,
        )

    def _spell_parameter_map(self, parameters: tuple) -> dict[str, str]:
        merged: dict[str, str] = {}
        for parameter in parameters:
            if parameter.key in merged:
                merged[parameter.key] = merged[parameter.key] + '\n' + parameter.value
            else:
                merged[parameter.key] = parameter.value
        return merged

    def _spell_material_candidates(self, actor: RuntimeActorState, spell: RuntimeSpellState) -> tuple[ItemRecord, ...]:
        matches: list[ItemRecord] = []
        keyword_set = {slugify(value) for value in spell.material_component_item_keywords}
        for item_id, quantity in actor.carried_item_counts.items():
            if quantity <= 0:
                continue
            item = self.item_catalog.get(item_id)
            if item is None:
                continue
            if spell.material_component_cost_cp is not None and item.cost_cp < spell.material_component_cost_cp:
                continue
            keyword_match = not keyword_set or slugify(item.record_id) in keyword_set or slugify(item.name) in keyword_set or any(keyword in slugify(item.name) for keyword in keyword_set)
            focus_match = not spell.material_component_focus_tags or any(tag in item.tags for tag in spell.material_component_focus_tags)
            if spell.material_component_focus_tags and spell.material_component_item_keywords:
                valid = keyword_match or focus_match
            elif spell.material_component_focus_tags:
                valid = focus_match
            else:
                valid = keyword_match
            if valid:
                matches.append(item)
        return tuple(matches)

    def _spell_material_events(self, actor: RuntimeActorState, spell: RuntimeSpellState, *, parameters: Mapping[str, str] | None = None) -> list[object]:
        if spell.material_component_cost_cp is None and not spell.material_component_focus_tags and not spell.material_component_item_keywords:
            return []
        candidates = self._spell_material_candidates(actor, spell)
        if not candidates:
            raise EncounterValidationError('The acting actor lacks the required material component for that spell.')
        requested = '' if parameters is None else parameters.get('material', '').strip()
        selected: ItemRecord | None = None
        if requested:
            requested_key = slugify(requested)
            for item in candidates:
                if requested_key in {slugify(item.record_id), slugify(item.name)}:
                    selected = item
                    break
            if selected is None:
                raise EncounterValidationError(f'No legal material component matched --material {requested}.')
        elif len(candidates) == 1:
            selected = candidates[0]
        else:
            labels = ', '.join(sorted(item.record_id for item in candidates))
            raise EncounterValidationError(f'This spell requires --material because multiple legal material components are available: {labels}.')
        if selected is None:
            raise EncounterValidationError('The acting actor lacks the required material component for that spell.')
        if not spell.material_component_consumed:
            return []
        return [ItemConsumedEvent(actor_id=actor.actor_id, item_id=selected.record_id, quantity=1, reason=spell.name)]

    def prepare_story_supported_spellcast_events(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        spell_id: str,
        target_id: str | None = None,
        point: GridPosition | None = None,
        ritual_cast: bool = False,
        parameters: Mapping[str, str] | None = None,
    ) -> list[object]:
        if state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Story-supported spell preparation is only available outside combat.')
        actor = self._require_actor(state, actor_id)
        self._require_conscious(actor)
        spell = actor.spells.get(spell_id)
        if spell is None:
            raise EncounterValidationError('That spell is not available to the acting actor.')
        support = spell.runtime_support
        if support is None or support.support_mode != SpellRuntimeSupportMode.STORY_ADJUDICATED:
            raise EncounterValidationError('That spell does not expose a story-mode support path.')
        if spell.remaining_uses is not None and spell.remaining_uses <= 0:
            raise EncounterValidationError('That spell has no remaining uses.')
        if spell.resource_pool_id is not None:
            pool = actor.resource_pools.get(spell.resource_pool_id)
            if pool is None:
                raise EncounterValidationError(f'That spell references missing resource pool {spell.resource_pool_id!r}.')
            if pool.current <= 0:
                raise EncounterValidationError('The acting actor has no spell slots remaining for that spell level.')
        if actor.cannot_cast_spells:
            raise EncounterValidationError('The acting actor cannot cast spells right now.')
        if spell.action_cost == 'reaction':
            raise EncounterValidationError('Reaction spells must be used through a legal trigger, even in storytelling mode.')
        if ritual_cast:
            if not spell.can_cast_as_ritual:
                raise EncounterValidationError('That spell cannot be cast as a ritual.')
        if target_id is not None:
            self._require_actor(state, target_id)
        if point is not None:
            self.battlefield_rules.get_tile(state.battlefield, point.x, point.y)
        events: list[object] = [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC, target_id=target_id, detail=spell.option_id),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC),
        ]
        events.extend(self._spell_material_events(actor, spell, parameters=parameters))
        if ritual_cast:
            ritual_total_seconds = spell.casting_time_seconds + spell.ritual_additional_cast_seconds
            events.append(
                RitualCastStartedEvent(
                    ritual=RitualCastingState(
                        ritual_id=f'ritual:{actor.actor_id}:{spell.option_id}:{len(state.event_log)}',
                        actor_id=actor.actor_id,
                        capability_id=spell.option_id,
                        total_seconds=ritual_total_seconds,
                        remaining_seconds=ritual_total_seconds,
                        no_slot_cost=True,
                        spell_id=spell.option_id,
                    )
                )
            )
            events.append(TimeAdvancedEvent(elapsed_seconds=ritual_total_seconds, activity_type=RestActivityType.LIGHT_ACTIVITY))
        elif spell.casting_time_seconds > 6:
            events.append(TimeAdvancedEvent(elapsed_seconds=spell.casting_time_seconds, activity_type=RestActivityType.LIGHT_ACTIVITY))
        if actor.hidden and self._spell_reveals_hidden(spell):
            events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=CombatActionType.MAGIC.value))
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC, hidden=False))
        remaining_uses = spell.remaining_uses
        resource_pool_id = None
        resource_pool_current_after = None
        if not ritual_cast:
            remaining_uses = None if spell.remaining_uses is None else spell.remaining_uses - 1
            resource_pool_id = spell.resource_pool_id
            if resource_pool_id is not None:
                resource_pool_current_after = actor.resource_pools[resource_pool_id].current - 1
        events.append(
            SpellCastEvent(
                actor_id=actor.actor_id,
                spell_id=spell.option_id,
                action_cost=spell.action_cost,
                from_position=actor.position,
                to_position=point,
                target_id=target_id,
                remaining_uses=remaining_uses,
                resource_pool_id=resource_pool_id,
                resource_pool_current_after=resource_pool_current_after,
            )
        )
        return events

    def _spell_active_effect(self, state: EncounterState, *, actor_id: str, name: str) -> ActiveEffectState | None:
        matches = [effect for effect in state.active_effects.values() if effect.source_actor_id == actor_id and effect.name == name]
        return matches[-1] if matches else None

    def _normalized_spell_mode(self, state: EncounterState, *, actor: RuntimeActorState, spell: RuntimeSpellState, target_id: str | None, parameters: dict[str, str]) -> str:
        mode = parameters.get('mode', '').strip().casefold()
        active_effect = self._spell_active_effect(state, actor_id=actor.actor_id, name=spell.name)
        if spell.option_id == 'produce-flame' and (mode == 'throw' or (not mode and active_effect is not None and target_id is not None)):
            return 'throw'
        if spell.option_id == 'dancing-lights' and mode == 'move':
            return 'move'
        if spell.option_id == 'mage-hand' and mode in {'move', 'interact', 'command'}:
            return mode
        if spell.option_id == 'witch-bolt' and mode == 'sustain':
            return 'sustain'
        if spell.option_id in {'detect-magic', 'detect-poison-and-disease', 'detect-evil-and-good'} and mode == 'inspect':
            return 'inspect'
        if spell.option_id in {'hex', 'hunter-s-mark'} and mode == 'transfer':
            return 'transfer'
        return 'cast'

    def _spell_command_action_cost(self, spell: RuntimeSpellState, *, normalized_mode: str) -> str:
        if spell.option_id == 'produce-flame' and normalized_mode == 'throw':
            return 'action'
        if spell.option_id == 'dancing-lights' and normalized_mode == 'move':
            return 'bonus'
        if spell.option_id == 'mage-hand' and normalized_mode in {'move', 'interact', 'command'}:
            return 'action'
        if spell.option_id == 'witch-bolt' and normalized_mode == 'sustain':
            return 'bonus'
        if spell.option_id in {'detect-magic', 'detect-poison-and-disease', 'detect-evil-and-good'} and normalized_mode == 'inspect':
            return 'action'
        if spell.option_id in {'hex', 'hunter-s-mark'} and normalized_mode == 'transfer':
            return 'bonus'
        return 'bonus' if spell.action_cost == 'bonus-action' else spell.action_cost

    def _spell_command_emits_cast_event(self, spell: RuntimeSpellState, *, normalized_mode: str) -> bool:
        if spell.option_id == 'produce-flame' and normalized_mode == 'throw':
            return False
        if spell.option_id == 'dancing-lights' and normalized_mode == 'move':
            return False
        if spell.option_id == 'mage-hand' and normalized_mode in {'move', 'interact', 'command'}:
            return False
        if spell.option_id == 'witch-bolt' and normalized_mode == 'sustain':
            return False
        if spell.option_id in {'detect-magic', 'detect-poison-and-disease', 'detect-evil-and-good'} and normalized_mode == 'inspect':
            return False
        if spell.option_id in {'hex', 'hunter-s-mark'} and normalized_mode == 'transfer':
            return False
        return True

    def _spell_is_harmful(self, spell: RuntimeSpellState) -> bool:
        capability = spell.capability
        if capability is None:
            return False
        if capability.targeting.affinity == TargetAffinity.ENEMY:
            return True
        return self.effect_executor._effect_is_damaging(capability.effect)


    def _sanctuary_guard_effect(self, state: EncounterState, *, target_id: str) -> ActiveEffectState | None:
        for effect in state.active_effects.values():
            if target_id not in effect.target_actor_ids:
                continue
            if effect.definition.incoming_hostile_targeting_save_ability is None:
                continue
            return effect
        return None

    def _resolve_sanctuary_targeting(self, state: EncounterState, *, acting_actor: RuntimeActorState, target: RuntimeActorState) -> tuple[bool, list[object]]:
        if acting_actor.side == target.side:
            return True, []
        effect = self._sanctuary_guard_effect(state, target_id=target.actor_id)
        if effect is None:
            return True, []
        ability = effect.definition.incoming_hostile_targeting_save_ability
        if ability is None:
            return True, []
        if effect.definition.incoming_hostile_targeting_save_dc_source == SaveDcSource.FLAT:
            dc = effect.definition.incoming_hostile_targeting_save_flat_dc
            if dc is None:
                raise EncounterValidationError('Sanctuary is missing its flat save DC.')
        else:
            source_actor = self._require_actor(state, effect.source_actor_id)
            if source_actor.spell_save_dc is None:
                raise EncounterValidationError('Sanctuary source actor is missing a spell save DC.')
            dc = source_actor.spell_save_dc
        request = SaveRequest(
            context=ResolutionContext(
                effect_id=effect.effect_instance_id,
                source_actor_id=effect.source_actor_id,
                target_actor_id=acting_actor.actor_id,
                reason=effect.name,
            ),
            ability=ability,
            dc=dc,
        )
        resolution, save_events = self.resolve_save_consumer(state, request, apply=False)
        return resolution.branch.value == 'success', list(save_events)

    def _resolve_cast_spell(self, state: EncounterState, intent: CastSpellIntent) -> list[object]:
        in_combat = state.phase == EncounterPhase.IN_PROGRESS
        actor = self._require_active_actor(state, intent.actor_id) if in_combat else self._require_actor(state, intent.actor_id)
        self._require_conscious(actor)
        spell = actor.spells.get(intent.spell_id)
        if spell is None:
            raise EncounterValidationError('That spell is not available to the acting actor.')
        if spell.remaining_uses is not None and spell.remaining_uses <= 0:
            raise EncounterValidationError('That spell has no remaining uses.')
        if spell.resource_pool_id is not None:
            pool = actor.resource_pools.get(spell.resource_pool_id)
            if pool is None:
                raise EncounterValidationError(f'That spell references missing resource pool {spell.resource_pool_id!r}.')
            if pool.current <= 0:
                raise EncounterValidationError('The acting actor has no spell slots remaining for that spell level.')
        if actor.cannot_cast_spells:
            raise EncounterValidationError('The acting actor cannot cast spells right now.')
        point = None
        if intent.x is not None and intent.y is not None:
            point = GridPosition(intent.x, intent.y, actor.position.z if intent.z is None else intent.z)
        parameters = self._spell_parameter_map(intent.parameters)
        normalized_mode = self._normalized_spell_mode(state, actor=actor, spell=spell, target_id=intent.target_id, parameters=parameters)
        if spell.action_cost == 'reaction' and normalized_mode == 'cast':
            raise EncounterValidationError('Reaction spells must be used through a legal reaction window.')
        if spell.option_id in {'divine-smite', 'hail-of-thorns'} and normalized_mode == 'cast':
            raise EncounterValidationError('That spell must be used through a legal post-hit trigger window.')
        if spell.option_id == 'hellish-rebuke' and normalized_mode == 'cast':
            raise EncounterValidationError('That spell must be used through a legal damage-trigger reaction window.')
        action_cost = self._spell_command_action_cost(spell, normalized_mode=normalized_mode)
        emit_spell_cast_event = self._spell_command_emits_cast_event(spell, normalized_mode=normalized_mode)
        spend_spell_resource = normalized_mode not in {'inspect', 'transfer'}
        if intent.ritual_cast:
            if in_combat:
                raise EncounterValidationError('Ritual casting is only available outside combat.')
            if not spell.can_cast_as_ritual:
                raise EncounterValidationError('That spell cannot be cast as a ritual.')
            if spell.capability is None:
                raise EncounterValidationError('That spell does not expose a ritual-capable executable definition.')
            if normalized_mode != 'cast':
                raise EncounterValidationError('Spell commands cannot be combined with ritual casting.')
        events: list[object] = [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC, target_id=intent.target_id, detail=spell.option_id),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC),
        ]
        if in_combat:
            if action_cost == 'bonus':
                self._require_bonus_action_permission(actor)
            elif action_cost == 'action':
                self._require_action_permission(actor)
            else:
                raise EncounterValidationError(f'Unsupported combat spell action cost: {action_cost}.')
            events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource=action_cost, reason=f'cast:{spell.option_id}'))
        elif intent.ritual_cast:
            ritual_total_seconds = spell.casting_time_seconds + spell.ritual_additional_cast_seconds
            events.append(
                RitualCastStartedEvent(
                    ritual=RitualCastingState(
                        ritual_id=f'ritual:{actor.actor_id}:{spell.option_id}:{len(state.event_log)}',
                        actor_id=actor.actor_id,
                        capability_id=(spell.capability.capability_id if spell.capability is not None else spell.option_id),
                        total_seconds=ritual_total_seconds,
                        remaining_seconds=ritual_total_seconds,
                        no_slot_cost=True,
                        spell_id=spell.option_id,
                    )
                )
            )
            events.append(TimeAdvancedEvent(elapsed_seconds=ritual_total_seconds, activity_type=RestActivityType.LIGHT_ACTIVITY))
        elif spell.casting_time_seconds > 6 and normalized_mode == 'cast':
            events.append(TimeAdvancedEvent(elapsed_seconds=spell.casting_time_seconds, activity_type=RestActivityType.LIGHT_ACTIVITY))
        if spell.option_id == 'witch-bolt' and normalized_mode == 'sustain':
            events.extend(self._resolve_witch_bolt_sustain(state, actor=actor, spell=spell, target_id=intent.target_id))
            return events
        if actor.hidden and self._spell_reveals_hidden(spell):
            events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=CombatActionType.MAGIC.value))
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=CombatActionType.MAGIC, hidden=False))
        events.extend(self._spell_material_events(actor, spell, parameters=parameters))
        if intent.target_id is not None and spell.capability is not None and spell.capability.targeting.selection_kind == TargetSelectionKind.CREATURE and self._spell_is_harmful(spell):
            target = self._require_target(state, intent.target_id)
            sanctuary_allows, sanctuary_events = self._resolve_sanctuary_targeting(state, acting_actor=actor, target=target)
            events.extend(sanctuary_events)
            if not sanctuary_allows:
                if emit_spell_cast_event:
                    remaining_uses = None if spell.remaining_uses is None else spell.remaining_uses - 1
                    resource_pool_id = None
                    resource_pool_current_after = None
                    if spend_spell_resource and not intent.ritual_cast and spell.resource_pool_id is not None:
                        resource_pool_id = spell.resource_pool_id
                        resource_pool_current_after = actor.resource_pools[resource_pool_id].current - 1
                    events.append(
                        SpellCastEvent(
                            actor_id=actor.actor_id,
                            spell_id=spell.option_id,
                            action_cost=action_cost,
                            from_position=actor.position,
                            to_position=(point if spell.capability.targeting.selection_kind == TargetSelectionKind.POINT else None),
                            target_id=intent.target_id,
                            remaining_uses=remaining_uses,
                            resource_pool_id=resource_pool_id,
                            resource_pool_current_after=resource_pool_current_after,
                        )
                    )
                events.append(CapabilityMissedEvent(actor_id=actor.actor_id, capability_id=spell.option_id, target_id=intent.target_id))
                return events
        events.extend(
            self.effect_executor.execute_spell(
                state,
                actor=actor,
                spell=spell,
                target_id=intent.target_id,
                point=point,
                spend_spell_resource=(spend_spell_resource and not intent.ritual_cast),
                parameters=parameters,
                event_action_cost=action_cost,
                emit_spell_cast_event=emit_spell_cast_event,
            )
        )
        return events

    def _resolve_witch_bolt_sustain(self, state: EncounterState, *, actor: RuntimeActorState, spell: RuntimeSpellState, target_id: str | None) -> list[object]:
        effect = self._spell_active_effect(state, actor_id=actor.actor_id, name=spell.name)
        if effect is None:
            raise EncounterValidationError('There is no active Witch Bolt effect to sustain.')
        if len(effect.target_actor_ids) != 1:
            raise EncounterValidationError('The Witch Bolt effect is missing its linked target.')
        linked_target_id = effect.target_actor_ids[0]
        if target_id is not None and target_id != linked_target_id:
            raise EncounterValidationError('Witch Bolt sustain must target the creature already linked by the spell.')
        target = self._require_target(state, linked_target_id)
        if target.is_dead:
            raise EncounterValidationError('The linked Witch Bolt target is already dead.')
        if self.battlefield_rules.get_distance3d(actor.position, target.position) > (spell.range_ft or 60):
            raise EncounterValidationError('The linked Witch Bolt target is out of range.')
        if self.battlefield_rules.get_cover(state, actor, target) == CoverLevel.TOTAL:
            raise EncounterValidationError('The linked Witch Bolt target has total cover.')
        damage_rolls, damage_total = roll_damage(seeded_random(self.seed, state.random_counter), dice_count=1, die_faces=12, bonus=0)
        hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = self._damage_preview(state, target, damage_total, damage_type='lightning')
        return list(effect_events) + [
            DamageRolledEvent(actor_id=actor.actor_id, attack_id=spell.option_id, target_id=target.actor_id, damage_rolls=damage_rolls, damage_total=damage_total, damage_type='lightning', random_counter_used=state.random_counter),
            DamageAppliedEvent(source_actor_id=actor.actor_id, target_id=target.actor_id, damage_total=damage_total, applied_damage_total=applied_damage_total, target_hit_points_after=hit_points_after, target_temp_hit_points_after=temp_hit_points_after, damage_type='lightning', critical_hit=False),
        ]

    def _intent_parameters(self, intent: UseCapabilityIntent) -> dict[str, str]:
        return {parameter.key: parameter.value for parameter in intent.parameters}

    def _require_capability_target_in_range(self, state: EncounterState, *, actor: RuntimeActorState, target: RuntimeActorState, runtime_capability: RuntimeCapabilityState) -> None:
        targeting = runtime_capability.capability.targeting
        if targeting.range_ft is not None and self.battlefield_rules.get_distance3d(actor.position, target.position) > targeting.range_ft:
            raise EncounterValidationError('The chosen target is out of range for that capability.')
        if targeting.requires_target_to_be_seen and not self.battlefield_rules.has_line_of_sight_to_position(state, actor, target.position):
            raise EncounterValidationError('The chosen target cannot currently be seen by the acting actor.')
        if targeting.requires_line_of_effect and not self.battlefield_rules.has_line_of_effect_to_position(state, actor, target.position):
            raise EncounterValidationError('The chosen target is blocked from line of effect.')

    def _resolve_lay_on_hands_capability(self, state: EncounterState, *, actor: RuntimeActorState, runtime_capability: RuntimeCapabilityState, intent: UseCapabilityIntent, action_type: CombatActionType) -> list[object]:
        if intent.target_id is None:
            raise EncounterValidationError('Lay on Hands requires a target creature.')
        target = self._require_target(state, intent.target_id)
        self._require_capability_target_in_range(state, actor=actor, target=target, runtime_capability=runtime_capability)
        pool = actor.resource_pools.get('lay-on-hands')
        if pool is None:
            raise EncounterValidationError('Lay on Hands is missing its healing pool.')
        parameters = self._intent_parameters(intent)
        amount_token = parameters.get('amount')
        remove_condition = parameters.get('remove-condition')
        if bool(amount_token) == bool(remove_condition):
            raise EncounterValidationError('Lay on Hands requires either --amount or --remove-condition.')
        events: list[object] = [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=action_type, target_id=target.actor_id, detail=runtime_capability.option_id),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=action_type),
            CapabilityDeclaredEvent(actor_id=actor.actor_id, capability_id=runtime_capability.capability.capability_id, capability_name=runtime_capability.capability.name, action_cost=runtime_capability.capability.action_cost, target_id=target.actor_id, runtime_option_id=runtime_capability.option_id, remaining_uses=runtime_capability.remaining_uses),
            ResourceSpentEvent(actor_id=actor.actor_id, resource='bonus', reason='use-capability:lay-on-hands'),
        ]
        if remove_condition is not None:
            if remove_condition.strip().casefold() != 'poisoned':
                raise EncounterValidationError('Lay on Hands can only remove the Poisoned condition in this slice.')
            if not has_condition(target, ConditionType.POISONED):
                raise EncounterValidationError('The chosen target is not Poisoned.')
            if pool.current < 5:
                raise EncounterValidationError('Lay on Hands needs 5 points remaining to remove Poisoned.')
            events.append(ResourcePoolSpentEvent(actor_id=actor.actor_id, resource_id='lay-on-hands', amount_spent=5, current_after=pool.current - 5, maximum=pool.maximum, reason='remove-poisoned'))
            events.append(ConditionRemovedEvent(actor_id=target.actor_id, condition_type=ConditionType.POISONED))
            return events
        try:
            amount = int(amount_token or '')
        except ValueError as exc:
            raise EncounterValidationError('Lay on Hands requires an integer --amount value.') from exc
        if amount <= 0:
            raise EncounterValidationError('Lay on Hands healing amount must be positive.')
        if amount > pool.current:
            raise EncounterValidationError('Lay on Hands cannot spend more points than remain in the pool.')
        missing_hit_points = max(0, target.max_hit_points - target.current_hit_points)
        if missing_hit_points <= 0:
            raise EncounterValidationError('The chosen target is already at full Hit Points.')
        if amount > missing_hit_points:
            raise EncounterValidationError('Lay on Hands cannot spend more healing than the target is missing.')
        events.append(ResourcePoolSpentEvent(actor_id=actor.actor_id, resource_id='lay-on-hands', amount_spent=amount, current_after=pool.current - amount, maximum=pool.maximum, reason='healing'))
        events.append(HealingAppliedEvent(source_actor_id=actor.actor_id, target_id=target.actor_id, healing_total=amount, target_hit_points_after=target.current_hit_points + amount))
        return events

    def _resolve_arcane_recovery_capability(self, state: EncounterState, *, actor: RuntimeActorState, runtime_capability: RuntimeCapabilityState, intent: UseCapabilityIntent, action_type: CombatActionType) -> list[object]:
        recovery_pool = actor.resource_pools.get('arcane-recovery')
        if recovery_pool is None:
            raise EncounterValidationError('Arcane Recovery is missing its recovery pool.')
        if recovery_pool.current <= 0:
            raise EncounterValidationError('Arcane Recovery has no remaining uses until the next long rest.')
        if actor.rest_state.status != RestStateStatus.SHORT_REST_COMPLETED:
            raise EncounterValidationError('Arcane Recovery can only be used after completing a short rest.')
        parameters = self._intent_parameters(intent)
        try:
            slot_level = int(parameters.get('slot-level', '1'))
        except ValueError as exc:
            raise EncounterValidationError('Arcane Recovery requires an integer --slot-level value.') from exc
        if slot_level != 1:
            raise EncounterValidationError('Level-1 Arcane Recovery can only restore a 1st-level spell slot.')
        slot_pool = actor.resource_pools.get('spell-slot-1')
        if slot_pool is None:
            raise EncounterValidationError('The acting actor does not have a 1st-level spell slot pool to recover.')
        if slot_pool.current >= slot_pool.maximum:
            raise EncounterValidationError('The acting actor already has all 1st-level spell slots available.')
        return [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=action_type, target_id=actor.actor_id, detail=runtime_capability.option_id),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=action_type),
            CapabilityDeclaredEvent(actor_id=actor.actor_id, capability_id=runtime_capability.capability.capability_id, capability_name=runtime_capability.capability.name, action_cost=runtime_capability.capability.action_cost, target_id=actor.actor_id, runtime_option_id=runtime_capability.option_id, remaining_uses=runtime_capability.remaining_uses),
            ResourcePoolSpentEvent(actor_id=actor.actor_id, resource_id='arcane-recovery', amount_spent=1, current_after=recovery_pool.current - 1, maximum=recovery_pool.maximum, reason='recover-spell-slot'),
            ResourcePoolRecoveredEvent(actor_id=actor.actor_id, resource_id='spell-slot-1', amount_recovered=1, current_after=min(slot_pool.maximum, slot_pool.current + 1), maximum=slot_pool.maximum, reason='arcane-recovery'),
        ]

    def _resolve_use_capability(self, state: EncounterState, intent: UseCapabilityIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        self._require_conscious(actor)
        runtime_capability = actor.capabilities.get(intent.capability_id)
        if runtime_capability is None:
            raise EncounterValidationError('That capability is not available to the acting actor.')
        if runtime_capability.remaining_uses is not None and runtime_capability.remaining_uses <= 0:
            raise EncounterValidationError('That capability has no remaining uses.')
        if runtime_capability.action_cost == 'reaction':
            raise EncounterValidationError('Reaction capabilities must be used through a legal reaction window.')
        if state.phase == EncounterPhase.IN_PROGRESS:
            actor = self._require_active_actor(state, intent.actor_id)
            if runtime_capability.action_cost in {'bonus', 'bonus-action'}:
                self._require_bonus_action_permission(actor)
            elif runtime_capability.action_cost == 'action':
                self._require_action_permission(actor)
            elif runtime_capability.action_cost != 'special':
                raise EncounterValidationError('Unsupported capability action cost in this slice.')
        elif runtime_capability.action_cost != 'special':
            raise EncounterValidationError('Only special noncombat capabilities can be used outside an active encounter.')
        action_type = self._capability_action_type(runtime_capability.kind)
        if runtime_capability.capability.capability_id == 'lay-on-hands':
            return self._resolve_lay_on_hands_capability(state, actor=actor, runtime_capability=runtime_capability, intent=intent, action_type=action_type)
        if runtime_capability.capability.capability_id == 'arcane-recovery':
            return self._resolve_arcane_recovery_capability(state, actor=actor, runtime_capability=runtime_capability, intent=intent, action_type=action_type)
        events: list[object] = [
            ActionDeclaredEvent(actor_id=actor.actor_id, action_type=action_type, target_id=intent.target_id, detail=runtime_capability.option_id),
            ActionValidatedEvent(actor_id=actor.actor_id, action_type=action_type),
        ]
        if runtime_capability.action_cost in {'action', 'bonus', 'bonus-action'}:
            resource_name = 'bonus' if runtime_capability.action_cost == 'bonus-action' else runtime_capability.action_cost
            events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource=resource_name, reason=f'use-capability:{runtime_capability.option_id}'))
        if actor.hidden:
            events.append(ActorRevealedEvent(actor_id=actor.actor_id, reason=action_type.value))
            events.append(ActionEffectEvent(actor_id=actor.actor_id, action_type=action_type, hidden=False))
        point = None
        if intent.x is not None and intent.y is not None:
            point = GridPosition(intent.x, intent.y, actor.position.z if intent.z is None else intent.z)
        events.extend(
            self.effect_executor.execute_capability(
                state,
                actor=actor,
                capability=runtime_capability.capability,
                target_id=intent.target_id,
                point=point,
                runtime_capability=runtime_capability,
                parameters=self._intent_parameters(intent),
            )
        )
        return events

    def _resolve_grapple(self, state: EncounterState, intent: GrappleIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        target = self._require_target(state, intent.target_id)
        self._require_conscious(actor)
        self._require_conscious(target)
        if actor.side == target.side:
            raise EncounterValidationError('Grapple requires an opposing target.')
        self._require_action_permission(actor)
        if grid_distance_ft(actor.position, target.position) > 5:
            raise EncounterValidationError('Grapple requires the target to be within 5 feet.')
        actor_rolls, actor_total, target_rolls, target_total = self._roll_contest(state, actor=actor, actor_ability=Ability.STR, actor_bonus=self._athletics_bonus(actor), target=target, target_ability=Ability.STR, target_bonus=max(self._athletics_bonus(target), self._acrobatics_bonus(target)))
        events: list[object] = [ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.GRAPPLE, target_id=target.actor_id), ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.GRAPPLE), ResourceSpentEvent(actor_id=actor.actor_id, resource='action', reason='grapple'), ContestRolledEvent(actor_id=actor.actor_id, target_id=target.actor_id, contest_type='grapple', actor_rolls=actor_rolls, actor_total=actor_total, target_rolls=target_rolls, target_total=target_total, random_counter_used=state.random_counter)]
        if actor_total >= target_total:
            events.append(ConditionAddedEvent(actor_id=target.actor_id, instance=self._make_condition_instance(target_actor_id=target.actor_id, condition_type=ConditionType.GRAPPLED, source_actor_id=actor.actor_id, source_label='grapple', grappler_actor_id=actor.actor_id)))
        return events

    def _resolve_shove(self, state: EncounterState, intent: ShoveIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        target = self._require_target(state, intent.target_id)
        self._require_conscious(actor)
        self._require_conscious(target)
        if actor.side == target.side:
            raise EncounterValidationError('Shove requires an opposing target.')
        self._require_action_permission(actor)
        if grid_distance_ft(actor.position, target.position) > 5:
            raise EncounterValidationError('Shove requires the target to be within 5 feet.')
        actor_rolls, actor_total, target_rolls, target_total = self._roll_contest(state, actor=actor, actor_ability=Ability.STR, actor_bonus=self._athletics_bonus(actor), target=target, target_ability=Ability.STR, target_bonus=max(self._athletics_bonus(target), self._acrobatics_bonus(target)))
        events: list[object] = [ActionDeclaredEvent(actor_id=actor.actor_id, action_type=CombatActionType.SHOVE, target_id=target.actor_id, detail=intent.outcome.value), ActionValidatedEvent(actor_id=actor.actor_id, action_type=CombatActionType.SHOVE), ResourceSpentEvent(actor_id=actor.actor_id, resource='action', reason='shove'), ContestRolledEvent(actor_id=actor.actor_id, target_id=target.actor_id, contest_type='shove', actor_rolls=actor_rolls, actor_total=actor_total, target_rolls=target_rolls, target_total=target_total, random_counter_used=state.random_counter)]
        if actor_total >= target_total:
            if intent.outcome == ShoveOutcome.PRONE:
                events.append(ConditionAddedEvent(actor_id=target.actor_id, instance=self._make_condition_instance(target_actor_id=target.actor_id, condition_type=ConditionType.PRONE, source_actor_id=actor.actor_id, source_label='shove-prone')))
            else:
                pushed_position = GridPosition(target.position.x + self._step_away(target.position.x, actor.position.x), target.position.y + self._step_away(target.position.y, actor.position.y), target.position.z)
                if not self.battlefield_rules.is_volume_occupiable(state, OccupiedVolume(pushed_position.x, pushed_position.y, pushed_position.z, height_ft=target.occupied_height_ft), target, ignore_actor_id=target.actor_id):
                    raise EncounterValidationError('The shove destination is occupied or blocked.')
                events.append(MovementSpentEvent(actor_id=target.actor_id, from_position=target.position, to_position=pushed_position, distance_ft=5, remaining_movement_ft=target.remaining_movement_ft, movement_mode=TraversalMode.WALK, movement_spent_ft=target.movement_spent_ft))
        return events
    def _resolve_reaction_choice(self, state: EncounterState, intent: ChooseReactionIntent) -> list[object]:
        window = state.pending_reaction_window
        if window is None:
            raise EncounterValidationError('There is no active reaction window.')
        responded_actor_ids = tuple(dict.fromkeys(window.responded_actor_ids + (intent.actor_id,)))
        rebuilt_window = self._rebuild_reaction_window(state, window, window.responded_actor_ids)
        if rebuilt_window is None:
            raise EncounterValidationError('There are no legal reactions remaining for the current trigger window.')
        if intent.actor_id in rebuilt_window.responded_actor_ids:
            raise EncounterValidationError('That actor has already responded to this reaction window.')
        events: list[object] = [
            ReactionSubmittedEvent(trigger_id=rebuilt_window.trigger_id, actor_id=intent.actor_id, option_id=intent.option_id),
            ReactionChosenEvent(trigger_id=rebuilt_window.trigger_id, actor_id=intent.actor_id, option_id=intent.option_id),
        ]
        option_map = {option.option_id: option for option in rebuilt_window.options}
        legal_actor_ids = {option.actor_id for option in rebuilt_window.options}
        continuation = self._ready_continuation_state(rebuilt_window, responded_actor_ids)

        def _resume_or_reopen(preview_state: EncounterState, *, resume_state_override: PendingResolutionState | None = None) -> list[object]:
            follow_up_window = self._rebuild_reaction_window(preview_state, rebuilt_window, responded_actor_ids)
            if follow_up_window is not None:
                if resume_state_override is not None:
                    follow_up_window = replace(follow_up_window, resume_state=resume_state_override)
                return [ReactionWindowOpenedEvent(window=follow_up_window)]
            return self._resume_pending_resolution(preview_state, rebuilt_window.resume_state if resume_state_override is None else resume_state_override)

        if intent.option_id == 'decline':
            if rebuilt_window.trigger_type == ReactionTriggerType.READY_TRIGGER and rebuilt_window.pending_ready_trigger is not None:
                actor = self._require_actor(state, intent.actor_id)
                if actor.readied_action is not None:
                    events.append(ReadiedActionIgnoredEvent(actor_id=intent.actor_id, trigger_actor_id=rebuilt_window.pending_ready_trigger.trigger_actor_id))
            preview = copy.deepcopy(state)
            for event in events:
                self._apply_event(preview, event)
            events.append(ReactionResolvedEvent(trigger_id=rebuilt_window.trigger_id, actor_id=intent.actor_id, option_id=intent.option_id))
            events.extend(_resume_or_reopen(preview))
            return events

        reaction_option = option_map.get(intent.option_id)
        if reaction_option is None or reaction_option.actor_id not in legal_actor_ids or reaction_option.actor_id != intent.actor_id:
            events.append(
                ReactionRejectedEvent(
                    trigger_id=rebuilt_window.trigger_id,
                    actor_id=intent.actor_id,
                    option_id=intent.option_id,
                    reason='revalidation-failed',
                )
            )
            preview = copy.deepcopy(state)
            for event in events:
                self._apply_event(preview, event)
            events.extend(_resume_or_reopen(preview))
            return events

        interrupted_actor_id = state.active_actor_id or rebuilt_window.pending_actor_id
        events.append(TurnInterruptedEvent(actor_id=interrupted_actor_id, reason=rebuilt_window.trigger_type.value))
        try:
            if reaction_option.action_type == CombatActionType.OPPORTUNITY_ATTACK:
                reaction_events = self._resolve_attack_action(
                    state,
                    actor_id=reaction_option.actor_id,
                    attack_id=reaction_option.attack_id or '',
                    target_id=reaction_option.target_id or rebuilt_window.pending_actor_id,
                    action_type=CombatActionType.OPPORTUNITY_ATTACK,
                    spend_resource='reaction',
                    allow_hit_reactions=False,
                    require_turn=False,
                    resume_state=continuation,
                )
            elif reaction_option.action_type == CombatActionType.SHIELD:
                reacting_actor = self._require_actor(state, reaction_option.actor_id)
                spell = reacting_actor.spells.get(reaction_option.spell_id or '')
                if spell is None:
                    raise EncounterValidationError('The reaction spell is no longer available to the reacting actor.')
                reaction_events = [
                    ActionDeclaredEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.SHIELD, target_id=rebuilt_window.pending_actor_id, detail=spell.option_id),
                    ActionValidatedEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.SHIELD),
                    ResourceSpentEvent(actor_id=reacting_actor.actor_id, resource='reaction', reason='shield'),
                ]
                if reacting_actor.hidden:
                    reaction_events.append(ActorRevealedEvent(actor_id=reacting_actor.actor_id, reason=CombatActionType.SHIELD.value))
                    reaction_events.append(ActionEffectEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.SHIELD, hidden=False))
                reaction_events.extend(self.effect_executor.execute_spell(state, actor=reacting_actor, spell=spell, target_id=rebuilt_window.pending_actor_id))
            elif reaction_option.action_type == CombatActionType.MAGIC:
                reacting_actor = self._require_actor(state, reaction_option.actor_id)
                spell = reacting_actor.spells.get(reaction_option.spell_id or '')
                if spell is None:
                    raise EncounterValidationError('The spell is no longer available to the reacting actor.')
                reaction_events = [
                    ActionDeclaredEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.MAGIC, target_id=reaction_option.target_id, detail=spell.option_id),
                    ActionValidatedEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.MAGIC),
                ]
                if reaction_option.resource_to_spend is not None:
                    reaction_events.append(ResourceSpentEvent(actor_id=reacting_actor.actor_id, resource=reaction_option.resource_to_spend, reason=f'cast:{spell.option_id}'))
                if reacting_actor.hidden and self._spell_reveals_hidden(spell):
                    reaction_events.append(ActorRevealedEvent(actor_id=reacting_actor.actor_id, reason=CombatActionType.MAGIC.value))
                    reaction_events.append(ActionEffectEvent(actor_id=reacting_actor.actor_id, action_type=CombatActionType.MAGIC, hidden=False))
                reaction_events.extend(
                    self.effect_executor.execute_spell(
                        state,
                        actor=reacting_actor,
                        spell=spell,
                        target_id=reaction_option.target_id,
                        parameters={key: value for key, value in reaction_option.parameters},
                    )
                )
            elif reaction_option.action_type == CombatActionType.READY:
                if rebuilt_window.pending_ready_trigger is None:
                    raise EncounterValidationError('The reaction window does not carry a ready-trigger payload.')
                reaction_events = self._resolve_readied_reaction(
                    state,
                    option=reaction_option,
                    trigger_actor_id=rebuilt_window.pending_ready_trigger.trigger_actor_id,
                    resume_state=continuation,
                )
            elif reaction_option.action_type == CombatActionType.FEATURE:
                if reaction_option.capability_id != 'sneak-attack':
                    raise EncounterValidationError('Unsupported reaction feature option type.')
                pending_attack = rebuilt_window.pending_attack
                if pending_attack is None or rebuilt_window.resume_state is None:
                    raise EncounterValidationError('Sneak Attack requires a pending hit to resolve against.')
                if pending_attack.sneak_attack_dice_count > 0:
                    raise EncounterValidationError('Sneak Attack has already been applied to this hit.')
                updated_pending_attack = replace(
                    pending_attack,
                    sneak_attack_dice_count=1,
                    sneak_attack_damage_type=(pending_attack.sneak_attack_damage_type or pending_attack.damage_type),
                )
                updated_resume_state = replace(rebuilt_window.resume_state, pending_attack=updated_pending_attack)
                reaction_events = []
                events.extend(reaction_events)
                events.append(ReactionResolvedEvent(trigger_id=rebuilt_window.trigger_id, actor_id=intent.actor_id, option_id=intent.option_id))
                preview = copy.deepcopy(state)
                for event in events:
                    self._apply_event(preview, event)
                events.append(TurnResumedEvent(actor_id=interrupted_actor_id, reason=rebuilt_window.trigger_type.value))
                events.extend(_resume_or_reopen(preview, resume_state_override=updated_resume_state))
                return events
            else:
                raise EncounterValidationError('Unsupported reaction option type.')
        except EncounterValidationError as exc:
            events.append(
                ReactionRejectedEvent(
                    trigger_id=rebuilt_window.trigger_id,
                    actor_id=intent.actor_id,
                    option_id=intent.option_id,
                    reason=str(exc),
                )
            )
            preview = copy.deepcopy(state)
            for event in events:
                self._apply_event(preview, event)
            events.extend(_resume_or_reopen(preview))
            return events

        events.extend(reaction_events)
        events.append(ReactionResolvedEvent(trigger_id=rebuilt_window.trigger_id, actor_id=intent.actor_id, option_id=intent.option_id))
        if any(isinstance(event, ReactionWindowOpenedEvent) for event in reaction_events):
            return events
        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        events.append(TurnResumedEvent(actor_id=interrupted_actor_id, reason=rebuilt_window.trigger_type.value))
        events.extend(_resume_or_reopen(preview))
        return events

    def _resolve_end_turn(self, state: EncounterState, intent: EndTurnIntent) -> list[object]:
        actor = self._require_active_actor(state, intent.actor_id)
        if state.phase != EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Turn order is only available during an active encounter.')
        next_actor_id, next_round_number = self._next_active_actor(state)
        end_entries = self._collect_end_of_turn_entries(state, actor_id=actor.actor_id)
        if end_entries:
            queue = PendingTimingQueueState(
                actor_id=actor.actor_id,
                phase=TriggerTiming.END_OF_TURN,
                entries=end_entries,
                next_actor_id=next_actor_id,
                next_round_number=next_round_number,
            )
            return self._queue_or_auto_resolve_timing_queue(state, queue)
        events: list[object] = [
            TurnEndedEvent(actor_id=actor.actor_id, next_actor_id=next_actor_id, round_number=next_round_number)
        ]
        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        start_entries = self._collect_start_of_turn_entries(preview, actor_id=next_actor_id)
        if start_entries:
            queue = PendingTimingQueueState(
                actor_id=next_actor_id,
                phase=TriggerTiming.START_OF_TURN,
                entries=start_entries,
            )
            events.extend(self._queue_or_auto_resolve_timing_queue(preview, queue))
        return events

    def _finalize_pending_attack(self, state: EncounterState, pending_attack: PendingAttackState, *, armor_class_bonus: int, damage_counter: int) -> tuple[list[object], int]:
        attacker = self._require_actor(state, pending_attack.actor_id)
        target = self._require_target(state, pending_attack.target_id)
        if not self._attack_hits(pending_attack.attack_total, target.effective_armor_class + pending_attack.target_armor_class_modifier + armor_class_bonus, pending_attack.selected_roll):
            return [AttackMissedEvent(actor_id=attacker.actor_id, attack_id=pending_attack.attack_id, target_id=target.actor_id)], target.current_hit_points
        critical_hit = pending_attack.critical_on_hit
        melee_bonus = attacker.melee_attack_damage_bonus if pending_attack.attack_kind != AttackKind.RANGED else 0
        rng = seeded_random(self.seed, damage_counter)
        damage_rolls, damage_total = roll_damage(
            rng,
            dice_count=pending_attack.damage_dice_count * (2 if critical_hit and pending_attack.damage_dice_count > 0 else 1),
            die_faces=pending_attack.damage_die_faces,
            bonus=pending_attack.damage_bonus + melee_bonus,
        )
        hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = self._damage_preview(state, target, damage_total, damage_type=pending_attack.damage_type)
        events: list[object] = list(effect_events) + [
            AttackHitEvent(actor_id=attacker.actor_id, attack_id=pending_attack.attack_id, target_id=target.actor_id),
            DamageRolledEvent(actor_id=attacker.actor_id, attack_id=pending_attack.attack_id, target_id=target.actor_id, damage_rolls=damage_rolls, damage_total=damage_total, damage_type=pending_attack.damage_type, random_counter_used=damage_counter),
            DamageAppliedEvent(source_actor_id=attacker.actor_id, target_id=target.actor_id, damage_total=damage_total, applied_damage_total=applied_damage_total, target_hit_points_after=hit_points_after, target_temp_hit_points_after=temp_hit_points_after, damage_type=pending_attack.damage_type, critical_hit=critical_hit),
        ]
        next_damage_counter = damage_counter + 1

        def _append_damage_events(source_actor: RuntimeActorState, damage_target: RuntimeActorState, effect, *, counter: int) -> int:
            nonlocal events
            roll_count = effect.dice_count * (2 if critical_hit and effect.double_dice_on_critical_hit else 1)
            rolls, total = roll_damage(
                seeded_random(self.seed, counter),
                dice_count=roll_count,
                die_faces=effect.die_faces,
                bonus=effect.bonus,
            )
            extra_hit_points_after, extra_temp_hit_points_after, extra_applied_total, extra_effect_events = self._damage_preview(
                state,
                damage_target,
                total,
                damage_type=effect.damage_type,
            )
            events.extend(extra_effect_events)
            events.append(
                DamageRolledEvent(
                    actor_id=source_actor.actor_id,
                    attack_id=pending_attack.attack_id,
                    target_id=damage_target.actor_id,
                    damage_rolls=rolls,
                    damage_total=total,
                    damage_type=effect.damage_type,
                    random_counter_used=counter,
                )
            )
            events.append(
                DamageAppliedEvent(
                    source_actor_id=source_actor.actor_id,
                    target_id=damage_target.actor_id,
                    damage_total=total,
                    applied_damage_total=extra_applied_total,
                    target_hit_points_after=extra_hit_points_after,
                    target_temp_hit_points_after=extra_temp_hit_points_after,
                    damage_type=effect.damage_type,
                    critical_hit=False,
                )
            )
            return counter + 1

        weapon_attack = pending_attack.source_item_id is not None or pending_attack.attack_usage_kind in {
            AttackUsageKind.WEAPON_MELEE,
            AttackUsageKind.WEAPON_RANGED,
            AttackUsageKind.THROWN_WEAPON,
        }
        melee_weapon_or_unarmed = pending_attack.attack_kind != AttackKind.RANGED and (
            pending_attack.source_item_id is not None or pending_attack.attack_id == 'unarmed-strike' or pending_attack.attack_usage_kind == AttackUsageKind.WEAPON_MELEE
        )
        target_temp_hit_points_before = target.temp_hit_points
        if weapon_attack or melee_weapon_or_unarmed:
            for effect_state in state.active_effects.values():
                if attacker.actor_id not in effect_state.target_actor_ids:
                    continue
                if weapon_attack and effect_state.definition.weapon_attack_bonus_damage is not None:
                    next_damage_counter = _append_damage_events(attacker, target, effect_state.definition.weapon_attack_bonus_damage, counter=next_damage_counter)
                if melee_weapon_or_unarmed and effect_state.definition.melee_weapon_attack_bonus_damage is not None:
                    next_damage_counter = _append_damage_events(attacker, target, effect_state.definition.melee_weapon_attack_bonus_damage, counter=next_damage_counter)
                if weapon_attack and effect_state.definition.marked_target_bonus_damage is not None and dict(effect_state.metadata).get('marked-target-id') == target.actor_id:
                    next_damage_counter = _append_damage_events(attacker, target, effect_state.definition.marked_target_bonus_damage, counter=next_damage_counter)

        if pending_attack.sneak_attack_dice_count > 0:
            sneak_preview = copy.deepcopy(state)
            for event in events:
                self._apply_event(sneak_preview, event)
            sneak_target = self._require_target(sneak_preview, target.actor_id)
            sneak_rolls, sneak_total = roll_damage(
                seeded_random(self.seed, next_damage_counter),
                dice_count=pending_attack.sneak_attack_dice_count * (2 if critical_hit else 1),
                die_faces=6,
                bonus=0,
            )
            sneak_damage_type = pending_attack.sneak_attack_damage_type or pending_attack.damage_type
            sneak_hit_points_after, sneak_temp_hit_points_after, sneak_applied_total, sneak_effect_events = self._damage_preview(
                sneak_preview,
                sneak_target,
                sneak_total,
                damage_type=sneak_damage_type,
            )
            events.extend(sneak_effect_events)
            events.append(
                SneakAttackAppliedEvent(
                    actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    damage_rolls=sneak_rolls,
                    damage_total=sneak_total,
                    damage_type=sneak_damage_type,
                    current_round_number=state.round_number,
                    current_turn_actor_id=state.active_actor_id,
                    random_counter_used=next_damage_counter,
                    critical_hit=critical_hit,
                )
            )
            events.append(
                DamageRolledEvent(
                    actor_id=attacker.actor_id,
                    attack_id=pending_attack.attack_id,
                    target_id=target.actor_id,
                    damage_rolls=sneak_rolls,
                    damage_total=sneak_total,
                    damage_type=sneak_damage_type,
                    random_counter_used=next_damage_counter,
                )
            )
            events.append(
                DamageAppliedEvent(
                    source_actor_id=attacker.actor_id,
                    target_id=target.actor_id,
                    damage_total=sneak_total,
                    applied_damage_total=sneak_applied_total,
                    target_hit_points_after=sneak_hit_points_after,
                    target_temp_hit_points_after=sneak_temp_hit_points_after,
                    damage_type=sneak_damage_type,
                    critical_hit=False,
                )
            )
            next_damage_counter += 1

        if pending_attack.attack_kind != AttackKind.RANGED:
            for effect_state in state.active_effects.values():
                if target.actor_id not in effect_state.target_actor_ids or effect_state.definition.retaliatory_melee_hit_damage is None:
                    continue
                if effect_state.definition.retaliatory_requires_temp_hit_points and target_temp_hit_points_before <= 0:
                    continue
                next_damage_counter = _append_damage_events(target, attacker, effect_state.definition.retaliatory_melee_hit_damage, counter=next_damage_counter)

        preview = copy.deepcopy(state)
        for event in events:
            self._apply_event(preview, event)
        damage_reaction_options = self._sorted_reaction_options(
            discover_damage_reactions(
                preview,
                target_id=target.actor_id,
                source_actor_id=attacker.actor_id,
            )
        )
        if damage_reaction_options:
            events.append(
                ReactionWindowOpenedEvent(
                    window=ReactionWindowState(
                        trigger_id=f'damage:{attacker.actor_id}:{target.actor_id}:{pending_attack.attack_id}:{preview.random_counter}',
                        trigger_type=ReactionTriggerType.DAMAGE_TAKEN,
                        pending_actor_id=target.actor_id,
                        prompt='Damage was taken. Choose a legal reaction or decline.',
                        options=damage_reaction_options,
                        pending_attack=pending_attack,
                    )
                )
            )
        return events, preview.actors[target.actor_id].current_hit_points

    def _roll_contest(self, state: EncounterState, *, actor: RuntimeActorState, actor_ability: Ability, actor_bonus: int, target: RuntimeActorState, target_ability: Ability, target_bonus: int) -> tuple[tuple[int, ...], int, tuple[int, ...], int]:
        actor_resolution = self.resolve_ability_check(state, actor_id=actor.actor_id, ability=actor_ability, dc=0, flat_modifier=actor_bonus - actor.ability_modifiers[actor_ability], skill_name='Athletics')
        target_resolution = self.resolve_ability_check(state, actor_id=target.actor_id, ability=target_ability, dc=0, flat_modifier=target_bonus - target.ability_modifiers[target_ability], skill_name='Athletics')
        actor_total = 0 if actor_resolution.result.auto_fail else actor_resolution.result.total
        target_total = 0 if target_resolution.result.auto_fail else target_resolution.result.total
        return actor_resolution.result.rolls, actor_total, target_resolution.result.rolls, target_total

    def _athletics_bonus(self, actor: RuntimeActorState) -> int:
        return actor.skill_bonuses.get('Athletics', actor.ability_modifiers[Ability.STR])

    def _acrobatics_bonus(self, actor: RuntimeActorState) -> int:
        return actor.skill_bonuses.get('Acrobatics', actor.ability_modifiers[Ability.DEX])

    def _attack_modifier_state(self, state: EncounterState, actor: RuntimeActorState, target: RuntimeActorState, *, distance_ft: int, long_range_disadvantage: bool) -> dict[str, object]:
        modifiers = get_attack_roll_modifiers(actor, target, distance_ft=distance_ft, encounter_state=state)
        attack_modifier, attack_effect_events = self._attack_roll_effect_modifier(state, actor_id=actor.actor_id)
        incoming_modifier, incoming_effect_events = self._incoming_attack_roll_penalty(state, target_actor_id=target.actor_id)
        incoming_advantage, consumed_effect_ids = self._incoming_attack_roll_advantage(state, target_actor_id=target.actor_id)
        protected_disadvantage = any(
            actor.creature_type.casefold() in {value.casefold() for value in effect.definition.protected_from_creature_types}
            for effect in state.active_effects.values()
            if target.actor_id in effect.target_actor_ids and effect.definition.protected_from_creature_types
        )
        compelled_duel_disadvantage = any(
            actor.actor_id in effect.target_actor_ids
            and effect.definition.attack_roll_disadvantage_against_other_targets_except_source
            and target.actor_id != effect.source_actor_id
            for effect in state.active_effects.values()
        )
        return {
            'modifier': modifiers.modifier + attack_modifier + incoming_modifier,
            'advantage': (modifiers.advantage or incoming_advantage),
            'disadvantage': (modifiers.disadvantage or long_range_disadvantage or self._has_next_attack_roll_disadvantage(state, actor.actor_id) or protected_disadvantage or compelled_duel_disadvantage),
            'critical_on_hit': getattr(modifiers, 'critical_on_hit', False),
            'effect_events': attack_effect_events + incoming_effect_events,
            'consumed_incoming_attack_advantage_effect_ids': consumed_effect_ids,
        }

    def _roll_effect_modifier(self, state: EncounterState, *, actor_id: str, effect_instance_id: str, reason: str, dice_count: int, die_faces: int, random_counter: int) -> tuple[int, EffectRollAppliedEvent, int]:
        rolls, total = roll_damage(seeded_random(self.seed, random_counter), dice_count=dice_count, die_faces=die_faces, bonus=0)
        return total, EffectRollAppliedEvent(actor_id=actor_id, effect_instance_id=effect_instance_id, reason=reason, rolls=rolls, total=total, random_counter_used=random_counter), random_counter + 1

    def _attack_roll_effect_modifier(self, state: EncounterState, *, actor_id: str) -> tuple[int, list[object]]:
        modifier = 0
        events: list[object] = []
        random_counter = state.random_counter
        consumed_effect_ids: list[str] = []
        for effect in state.active_effects.values():
            if actor_id not in effect.target_actor_ids:
                continue
            consumed_this_effect = False
            if effect.definition.attack_roll_bonus is not None:
                spec = effect.definition.attack_roll_bonus
                total, event, random_counter = self._roll_effect_modifier(
                    state,
                    actor_id=actor_id,
                    effect_instance_id=effect.effect_instance_id,
                    reason='attack-roll-bonus',
                    dice_count=spec.dice_count,
                    die_faces=spec.die_faces,
                    random_counter=random_counter,
                )
                modifier += total
                events.append(event)
                consumed_this_effect = True
            if effect.definition.attack_roll_penalty is not None:
                spec = effect.definition.attack_roll_penalty
                total, event, random_counter = self._roll_effect_modifier(
                    state,
                    actor_id=actor_id,
                    effect_instance_id=effect.effect_instance_id,
                    reason='attack-roll-penalty',
                    dice_count=spec.dice_count,
                    die_faces=spec.die_faces,
                    random_counter=random_counter,
                )
                modifier -= total
                events.append(replace(event, total=-total))
                consumed_this_effect = True
            if consumed_this_effect and effect.definition.end_on_next_d20_test:
                consumed_effect_ids.append(effect.effect_instance_id)
        for effect_id in dict.fromkeys(consumed_effect_ids):
            events.append(ActiveEffectEndedEvent(effect_instance_id=effect_id, reason='d20-test-consumed'))
        return modifier, events

    def _incoming_attack_roll_penalty(self, state: EncounterState, *, target_actor_id: str) -> tuple[int, list[object]]:
        modifier = 0
        events: list[object] = []
        random_counter = state.random_counter
        for effect in state.active_effects.values():
            if target_actor_id not in effect.target_actor_ids or effect.definition.incoming_attack_roll_penalty is None:
                continue
            spec = effect.definition.incoming_attack_roll_penalty
            total, event, random_counter = self._roll_effect_modifier(
                state,
                actor_id=target_actor_id,
                effect_instance_id=effect.effect_instance_id,
                reason='incoming-attack-roll-penalty',
                dice_count=spec.dice_count,
                die_faces=spec.die_faces,
                random_counter=random_counter,
            )
            modifier -= total
            events.append(replace(event, total=-total))
        return modifier, events

    def _incoming_attack_roll_advantage(self, state: EncounterState, *, target_actor_id: str) -> tuple[bool, tuple[str, ...]]:
        matching = tuple(
            effect.effect_instance_id
            for effect in state.active_effects.values()
            if target_actor_id in effect.target_actor_ids and effect.definition.attackers_have_advantage
        )
        consumed = tuple(
            effect.effect_instance_id
            for effect in state.active_effects.values()
            if target_actor_id in effect.target_actor_ids and effect.definition.attackers_have_advantage and effect.definition.end_on_next_incoming_attack_roll
        )
        return bool(matching), consumed

    def _saving_throw_effect_modifier(self, state: EncounterState, *, actor_id: str) -> tuple[int, list[object]]:
        modifier = 0
        events: list[object] = []
        random_counter = state.random_counter
        consumed_effect_ids: list[str] = []
        for effect in state.active_effects.values():
            if actor_id not in effect.target_actor_ids:
                continue
            consumed_this_effect = False
            if effect.definition.next_saving_throw_penalty is not None:
                spec = effect.definition.next_saving_throw_penalty
                total, event, random_counter = self._roll_effect_modifier(
                    state,
                    actor_id=actor_id,
                    effect_instance_id=effect.effect_instance_id,
                    reason='next-saving-throw-penalty',
                    dice_count=spec.dice_count,
                    die_faces=spec.die_faces,
                    random_counter=random_counter,
                )
                modifier -= total
                events.append(replace(event, total=-total))
                consumed_this_effect = True
            if effect.definition.saving_throw_bonus is not None:
                spec = effect.definition.saving_throw_bonus
                total, event, random_counter = self._roll_effect_modifier(
                    state,
                    actor_id=actor_id,
                    effect_instance_id=effect.effect_instance_id,
                    reason='saving-throw-bonus',
                    dice_count=spec.dice_count,
                    die_faces=spec.die_faces,
                    random_counter=random_counter,
                )
                modifier += total
                events.append(event)
                consumed_this_effect = True
            if effect.definition.saving_throw_penalty is not None:
                spec = effect.definition.saving_throw_penalty
                total, event, random_counter = self._roll_effect_modifier(
                    state,
                    actor_id=actor_id,
                    effect_instance_id=effect.effect_instance_id,
                    reason='saving-throw-penalty',
                    dice_count=spec.dice_count,
                    die_faces=spec.die_faces,
                    random_counter=random_counter,
                )
                modifier -= total
                events.append(replace(event, total=-total))
                consumed_this_effect = True
            if consumed_this_effect and effect.definition.end_on_next_d20_test:
                consumed_effect_ids.append(effect.effect_instance_id)
        for effect_id in dict.fromkeys(consumed_effect_ids):
            events.append(ActiveEffectEndedEvent(effect_instance_id=effect_id, reason='d20-test-consumed'))
        return modifier, events

    def _ability_check_effect_modifier(self, state: EncounterState, *, actor_id: str, skill_name: str | None) -> tuple[int, list[object]]:
        modifier = 0
        events: list[object] = []
        random_counter = state.random_counter
        consumed_effect_ids: list[str] = []
        for effect in state.active_effects.values():
            if actor_id not in effect.target_actor_ids or effect.definition.ability_check_bonus is None:
                continue
            bonus_skill_name = effect.definition.ability_check_bonus_skill_name
            if bonus_skill_name is not None and bonus_skill_name != skill_name:
                continue
            spec = effect.definition.ability_check_bonus
            reason_skill_name = skill_name or 'ability-check'
            total, event, random_counter = self._roll_effect_modifier(
                state,
                actor_id=actor_id,
                effect_instance_id=effect.effect_instance_id,
                reason=f'ability-check-bonus:{reason_skill_name}',
                dice_count=spec.dice_count,
                die_faces=spec.die_faces,
                random_counter=random_counter,
            )
            modifier += total
            events.append(event)
            if effect.definition.end_on_next_d20_test:
                consumed_effect_ids.append(effect.effect_instance_id)
        for effect_id in dict.fromkeys(consumed_effect_ids):
            events.append(ActiveEffectEndedEvent(effect_instance_id=effect_id, reason='d20-test-consumed'))
        return modifier, events

    def _has_next_attack_roll_disadvantage(self, state: EncounterState, actor_id: str) -> bool:
        return any(actor_id in effect.target_actor_ids and effect.definition.next_attack_roll_disadvantage for effect in state.active_effects.values())

    def _healing_blocked(self, state: EncounterState, actor_id: str) -> bool:
        return any(actor_id in effect.target_actor_ids and effect.definition.healing_blocked for effect in state.active_effects.values())

    def _blocks_opportunity_attacks(self, state: EncounterState, actor_id: str) -> bool:
        return any(actor_id in effect.target_actor_ids and effect.definition.blocks_opportunity_attacks for effect in state.active_effects.values())

    def _suppresses_invisible_benefits(self, state: EncounterState, actor_id: str) -> bool:
        return any(actor_id in effect.target_actor_ids and effect.definition.suppress_invisible_benefits for effect in state.active_effects.values())

    def _consume_next_attack_roll_effects(self, state: EncounterState, *, actor_id: str) -> list[object]:
        return [
            ActiveEffectEndedEvent(effect_instance_id=effect.effect_instance_id, reason='next-attack-roll-consumed')
            for effect in state.active_effects.values()
            if actor_id in effect.target_actor_ids and effect.definition.next_attack_roll_disadvantage
        ]

    def _consume_next_incoming_attack_roll_effects(self, effect_ids: tuple[str, ...]) -> list[object]:
        return [
            ActiveEffectEndedEvent(effect_instance_id=effect_id, reason='incoming-attack-roll-consumed')
            for effect_id in effect_ids
        ]

    def _consume_next_saving_throw_effects(self, state: EncounterState, *, actor_id: str) -> list[object]:
        return [
            ActiveEffectEndedEvent(effect_instance_id=effect.effect_instance_id, reason='next-saving-throw-consumed')
            for effect in state.active_effects.values()
            if actor_id in effect.target_actor_ids and effect.definition.next_saving_throw_penalty is not None
        ]

    def _condition_removed_event_for_instance(self, actor_id: str, instance_id: str) -> ConditionRemovedEvent:
        return ConditionRemovedEvent(actor_id=actor_id, instance_id=instance_id)

    def _condition_removed_event_for_type(self, actor_id: str, condition_type: ConditionType) -> ConditionRemovedEvent:
        return ConditionRemovedEvent(actor_id=actor_id, condition_type=condition_type)

    def _shared_senses_condition_instance(self, *, actor_id: str, familiar_actor_id: str, condition_type: ConditionType) -> ConditionInstance:
        return ConditionInstance(
            instance_id=f'shared-senses:{condition_type.value}:{actor_id}:{familiar_actor_id}',
            condition_type=condition_type,
            source_actor_id=familiar_actor_id,
            source_label='find-familiar-shared-senses',
        )

    def _shared_senses_condition_instance_id(self, *, actor_id: str, familiar_actor_id: str, condition_type: ConditionType) -> str:
        return f'shared-senses:{condition_type.value}:{actor_id}:{familiar_actor_id}'

    def _resolve_mount_actor(self, state: EncounterState, intent: MountActorIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        mount = self._require_actor(state, intent.mount_actor_id)
        if actor.actor_id == mount.actor_id:
            raise EncounterValidationError('An actor cannot mount itself.')
        if self.battlefield_rules.get_distance3d(actor.position, mount.position) > 5:
            raise EncounterValidationError('The chosen mount is too far away to mount.')
        if not mount.is_conscious:
            raise EncounterValidationError('The chosen mount is not conscious.')
        events: list[object] = []
        if actor.mounted_on_actor_id is not None and actor.mounted_on_actor_id != mount.actor_id:
            events.append(DismountedActorEvent(actor_id=actor.actor_id, mount_actor_id=actor.mounted_on_actor_id, reason='remount'))
        if actor.mounted_on_actor_id != mount.actor_id:
            events.append(MountedActorEvent(actor_id=actor.actor_id, mount_actor_id=mount.actor_id))
        return events

    def _resolve_dismount_actor(self, state: EncounterState, intent: DismountActorIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        if actor.mounted_on_actor_id is None:
            return []
        return [DismountedActorEvent(actor_id=actor.actor_id, mount_actor_id=actor.mounted_on_actor_id, reason='manual')]

    def _resolve_share_familiar_senses(self, state: EncounterState, intent: ShareFamiliarSensesIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        if intent.familiar_actor_id is None:
            if actor.shared_senses_actor_id is None:
                return []
            return [SharedSensesEndedEvent(actor_id=actor.actor_id, familiar_actor_id=actor.shared_senses_actor_id, reason='manual')]
        familiar = self._require_actor(state, intent.familiar_actor_id)
        if familiar.summon_owner_actor_id != actor.actor_id or familiar.shared_sense_owner_actor_id != actor.actor_id:
            raise EncounterValidationError('The chosen actor is not your familiar.')
        if not familiar.is_conscious:
            raise EncounterValidationError('Your familiar must be conscious to share senses.')
        if self.battlefield_rules.get_distance3d(actor.position, familiar.position) > 100:
            raise EncounterValidationError('Your familiar is too far away to share senses.')
        events: list[object] = []
        if actor.shared_senses_actor_id is not None and actor.shared_senses_actor_id != familiar.actor_id:
            events.append(SharedSensesEndedEvent(actor_id=actor.actor_id, familiar_actor_id=actor.shared_senses_actor_id, reason='replaced'))
        if state.phase == EncounterPhase.IN_PROGRESS:
            if not actor.bonus_action_available:
                raise EncounterValidationError('Sharing senses requires an available bonus action in combat.')
            events.append(ResourceSpentEvent(actor_id=actor.actor_id, resource='bonus', reason='share-familiar-senses'))
        events.append(SharedSensesStartedEvent(actor_id=actor.actor_id, familiar_actor_id=familiar.actor_id))
        events.append(ConditionAddedEvent(actor_id=actor.actor_id, instance=self._shared_senses_condition_instance(actor_id=actor.actor_id, familiar_actor_id=familiar.actor_id, condition_type=ConditionType.BLINDED)))
        events.append(ConditionAddedEvent(actor_id=actor.actor_id, instance=self._shared_senses_condition_instance(actor_id=actor.actor_id, familiar_actor_id=familiar.actor_id, condition_type=ConditionType.DEAFENED)))
        return events

    def _zero_hit_points_unconscious_instance_id(self, actor_id: str) -> str:
        return f'zero-hit-points-unconscious:{actor_id}'

    def _zero_hit_points_unconscious_instance(self, actor_id: str) -> ConditionInstance:
        return ConditionInstance(
            instance_id=self._zero_hit_points_unconscious_instance_id(actor_id),
            condition_type=ConditionType.UNCONSCIOUS,
            source_label='zero-hit-points',
        )

    def _roll_stable_recovery_hours(self, state: EncounterState) -> tuple[int, int]:
        random_counter = state.random_counter
        return seeded_random(self.seed, random_counter).randint(1, 4), random_counter

    def _resolve_start_of_turn_death_save_events(self, state: EncounterState, *, actor_id: str) -> list[object]:
        actor = self._require_actor(state, actor_id)
        if not actor.eligible_for_death_saves:
            return []
        request = D20TestRequest(
            request_id=f'death-save:{actor.actor_id}:{state.random_counter}',
            test_type=D20TestType.DEATH_SAVE,
            actor_id=actor.actor_id,
            dc=10,
        )
        resolution = self.d20_engine.resolve(request, random_counter=state.random_counter)
        events: list[object] = [
            DeathSaveRequestedEvent(actor_id=actor.actor_id, dc=10),
            D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used),
            DeathSaveRolledEvent(
                actor_id=actor.actor_id,
                rolls=resolution.result.rolls,
                selected_roll=resolution.result.selected_roll,
                total=resolution.result.total,
                random_counter_used=resolution.random_counter_used,
            ),
        ]
        roll = resolution.result.selected_roll
        if roll == 1:
            next_failures = min(3, actor.dying_state.death_save_failures + 2)
            events.append(DeathSaveNaturalOneEvent(actor_id=actor.actor_id))
            events.append(DeathSaveFailedEvent(actor_id=actor.actor_id, total_failures=next_failures, failures_added=2, reason='death-save-roll'))
            if next_failures >= 3:
                events.append(DiedEvent(actor_id=actor.actor_id, reason='three-death-save-failures'))
        elif roll == 20:
            events.append(DeathSaveNaturalTwentyEvent(actor_id=actor.actor_id))
            events.append(HealingAppliedEvent(source_actor_id=actor.actor_id, target_id=actor.actor_id, healing_total=1, target_hit_points_after=1))
        elif resolution.result.success:
            next_successes = min(3, actor.dying_state.death_save_successes + 1)
            events.append(DeathSaveSucceededEvent(actor_id=actor.actor_id, total_successes=next_successes))
            if next_successes >= 3:
                recovery_counter = resolution.random_counter_used + 1
                recovery_hours = seeded_random(self.seed, recovery_counter).randint(1, 4)
                events.append(StabilizedEvent(actor_id=actor.actor_id, reason='three-death-save-successes', recovery_hours=recovery_hours, random_counter_used=recovery_counter))
        else:
            next_failures = min(3, actor.dying_state.death_save_failures + 1)
            events.append(DeathSaveFailedEvent(actor_id=actor.actor_id, total_failures=next_failures, failures_added=1, reason='death-save-roll'))
            if next_failures >= 3:
                events.append(DiedEvent(actor_id=actor.actor_id, reason='three-death-save-failures'))
        for event in events:
            self._apply_event(state, event)
        return events

    def _apply_zero_hit_point_damage_followups(
        self,
        state: EncounterState,
        *,
        target_id: str,
        source_actor_id: str | None,
        damage_type: str,
        applied_damage_total: int,
        critical_hit: bool,
        was_at_zero_hit_points: bool,
        previous_hit_points: int,
        previous_temp_hit_points: int,
    ) -> None:
        if applied_damage_total <= 0:
            return
        target = self._require_actor(state, target_id)
        if target.is_dead or target.current_hit_points > 0:
            return
        damage_after_temp = max(0, applied_damage_total - previous_temp_hit_points)
        if target.uses_death_saves:
            if was_at_zero_hit_points:
                if target.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
                    self._apply_event(state, StableBrokenByDamageEvent(actor_id=target.actor_id, source_actor_id=source_actor_id))
                if damage_after_temp >= target.max_hit_points:
                    self._apply_event(state, InstantDeathTriggeredEvent(actor_id=target.actor_id, reason='damage-at-zero-max-hit-points'))
                    self._apply_event(state, DiedEvent(actor_id=target.actor_id, reason='damage-at-zero-max-hit-points'))
                    return
                failures_added = 2 if critical_hit else 1
                next_failures = min(3, target.dying_state.death_save_failures + failures_added)
                self._apply_event(state, DeathSaveFailedEvent(actor_id=target.actor_id, total_failures=next_failures, failures_added=failures_added, reason='damage-at-zero'))
                if next_failures >= 3:
                    self._apply_event(state, DiedEvent(actor_id=target.actor_id, reason='three-death-save-failures'))
                return
            self._apply_event(state, HitPointsDroppedToZeroEvent(actor_id=target.actor_id, source_actor_id=source_actor_id, damage_type=damage_type, damage_to_hit_points=damage_after_temp))
            if damage_after_temp - previous_hit_points >= target.max_hit_points:
                self._apply_event(state, InstantDeathTriggeredEvent(actor_id=target.actor_id, reason='massive-damage'))
                self._apply_event(state, DiedEvent(actor_id=target.actor_id, reason='massive-damage'))
                return
            self._apply_event(state, UnconsciousAtZeroAppliedEvent(actor_id=target.actor_id, source_actor_id=source_actor_id, reason='zero-hit-points'))
            return
        if not was_at_zero_hit_points:
            self._apply_event(state, HitPointsDroppedToZeroEvent(actor_id=target.actor_id, source_actor_id=source_actor_id, damage_type=damage_type, damage_to_hit_points=damage_after_temp))
        self._apply_event(state, DiedEvent(actor_id=target.actor_id, reason='zero-hit-points'))

    def _shield_armor_class_bonus(self, spell) -> int:
        capability = getattr(spell, 'capability', None)
        if capability is None or not isinstance(capability.effect, StartActiveEffectDef):
            return 0
        return capability.effect.active_effect.armor_class_bonus

    def _damage_reduction_effect_events(self, state: EncounterState, *, target_id: str, damage_type: str) -> tuple[int, list[object]]:
        matching_effects: list[ActiveEffectState] = []
        normalized_damage_type = damage_type.casefold()
        for effect in state.active_effects.values():
            if target_id not in effect.target_actor_ids:
                continue
            reduction = effect.definition.damage_reduction_once_per_turn
            if reduction is None:
                continue
            if effect.definition.damage_reduction_damage_types and normalized_damage_type not in {item.casefold() for item in effect.definition.damage_reduction_damage_types}:
                continue
            if state.phase == EncounterPhase.IN_PROGRESS and effect.last_once_per_turn_round_number == state.round_number and effect.last_once_per_turn_turn_actor_id == state.active_actor_id:
                continue
            matching_effects.append(effect)
        if not matching_effects:
            return 0, []
        effect = matching_effects[-1]
        reduction = effect.definition.damage_reduction_once_per_turn
        if reduction is None:
            return 0, []
        total, roll_event, _ = self._roll_effect_modifier(
            state,
            actor_id=target_id,
            effect_instance_id=effect.effect_instance_id,
            reason=f'damage-reduction:{damage_type}',
            dice_count=reduction.dice_count,
            die_faces=reduction.die_faces,
            random_counter=state.random_counter,
        )
        return total, [roll_event]

    def _damage_preview(self, state: EncounterState, target: RuntimeActorState, damage_total: int, *, damage_type: str) -> tuple[int, int, int, list[object]]:
        resolved = apply_damage_modifiers(target, damage_total, damage_type)
        reduction_total = 0
        effect_events: list[object] = []
        if resolved.final_damage > 0:
            reduction_total, effect_events = self._damage_reduction_effect_events(state, target_id=target.actor_id, damage_type=damage_type)
        remaining_damage = max(0, resolved.final_damage - reduction_total)
        temp_hit_points_after = target.temp_hit_points
        if temp_hit_points_after > 0:
            absorbed = min(temp_hit_points_after, remaining_damage)
            temp_hit_points_after -= absorbed
            remaining_damage -= absorbed
        hit_points_after = max(0, target.current_hit_points - remaining_damage)
        applied_damage_total = max(0, resolved.final_damage - reduction_total)
        return hit_points_after, temp_hit_points_after, applied_damage_total, effect_events

    def _target_preview_after_events(self, state: EncounterState, target_id: str, events: list[object]) -> int:
        target = state.actors[target_id]
        hit_points_after = target.current_hit_points
        for event in events:
            if isinstance(event, DamageAppliedEvent) and event.target_id == target_id:
                hit_points_after = event.target_hit_points_after
        return hit_points_after

    def _attack_hits(self, attack_total: int, armor_class: int, selected_roll: int) -> bool:
        return selected_roll == 20 or (selected_roll != 1 and attack_total >= armor_class)

    def _persistent_area_transition_events(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        from_position: GridPosition,
        to_position: GridPosition,
    ) -> list[object]:
        actor = self._require_actor(state, actor_id)
        events: list[object] = []
        for area in tuple(state.persistent_areas.values()):
            was_inside = persistent_area_contains_position(area, from_position)
            is_inside = persistent_area_contains_position(area, to_position)
            if was_inside == is_inside:
                continue
            if any(tag == f'exclude:{actor.actor_id}' for tag in area.definition.semantic_tags):
                continue
            events.extend(
                self.effect_executor.resolve_persistent_area_transition(
                    state,
                    area=area,
                    actor_id=actor.actor_id,
                    entering=is_inside,
                )
            )
        return events

    def _complete_fall_events(
        self,
        state: EncounterState,
        *,
        pending_fall: PendingFallState,
        liquid_choice: LiquidEntryMitigationChoice | None = None,
    ) -> list[object]:
        actor = self._require_actor(state, pending_fall.actor_id)
        final_support_state = SupportStateType.SWIMMING if pending_fall.landing_surface_type == LandingSurfaceType.LIQUID else SupportStateType.GROUNDED
        events: list[object] = [
            FallLandedEvent(
                actor_id=actor.actor_id,
                from_position=pending_fall.from_position,
                to_position=pending_fall.to_position,
                landing_surface_type=pending_fall.landing_surface_type,
            ),
            SupportStateEvaluatedEvent(
                actor_id=actor.actor_id,
                support_state=final_support_state,
                position=pending_fall.to_position,
                detail='The actor has landed.',
            ),
        ]
        if final_support_state != SupportStateType.FALLING:
            events.append(AirborneStateChangedEvent(actor_id=actor.actor_id, from_state=SupportStateType.FALLING, to_state=final_support_state))
        damage_dice_count = min(20, pending_fall.distance_ft // 10)
        damage_prevented = actor.prevent_falling_damage or actor.fall_speed_override_ft is not None
        if pending_fall.landing_surface_type == LandingSurfaceType.LIQUID:
            events.append(LiquidEntryDetectedEvent(actor_id=actor.actor_id, position=pending_fall.to_position))
        if damage_prevented:
            damage_dice_count = 0
        if damage_dice_count > 0:
            rng = seeded_random(self.seed, state.random_counter)
            damage_rolls, damage_total = roll_damage(rng, dice_count=damage_dice_count, die_faces=6, bonus=0)
            mitigated_damage_total = damage_total
            if pending_fall.landing_surface_type == LandingSurfaceType.LIQUID:
                mitigation_resolution, mitigation_events = self.effect_consumers.resolve_liquid_entry_mitigation(state, actor_id=actor.actor_id, choice=liquid_choice, damage_total=damage_total)
                mitigated_damage_total = mitigation_resolution.damage_after
                events.extend(mitigation_events)
            hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = self._damage_preview(state, actor, mitigated_damage_total, damage_type='bludgeoning')
            events.extend(effect_events)
            events.append(FallDamageRolledEvent(actor_id=actor.actor_id, distance_ft=pending_fall.distance_ft, damage_rolls=damage_rolls, damage_total=mitigated_damage_total, random_counter_used=state.random_counter))
            events.append(FallDamageAppliedEvent(actor_id=actor.actor_id, damage_total=mitigated_damage_total, applied_damage_total=applied_damage_total, target_hit_points_after=hit_points_after, target_temp_hit_points_after=temp_hit_points_after, damage_type='bludgeoning'))
            if applied_damage_total > 0:
                condition_state = get_condition_state(actor)
                if ConditionType.PRONE not in condition_state.effective_types:
                    events.append(ProneAppliedFromFallEvent(actor_id=actor.actor_id))
        for effect in tuple(state.active_effects.values()):
            if actor.actor_id in effect.target_actor_ids and effect.name == 'Feather Fall':
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='landed'))
        return events

    def _support_reconciliation_events(
        self,
        state: EncounterState,
        *,
        actor_id: str,
        reason: FallReason,
        liquid_choice: LiquidEntryMitigationChoice | None = None,
    ) -> list[object]:
        actor = self._require_actor(state, actor_id)
        evaluation = self.battlefield_rules.evaluate_support_state(state, actor, default_reason=reason)
        events: list[object] = [
            SupportStateEvaluatedEvent(
                actor_id=actor.actor_id,
                support_state=evaluation.support_state,
                position=evaluation.position,
                detail=evaluation.detail,
            )
        ]
        prior_state = actor.support_state
        if prior_state != evaluation.support_state:
            events.append(AirborneStateChangedEvent(actor_id=actor.actor_id, from_state=prior_state, to_state=evaluation.support_state))
        if not evaluation.requires_fall or evaluation.reason is None:
            return events
        landing = self.battlefield_rules.find_landing_point(state, actor, evaluation.position)
        falling_state = SupportStateType.FALLING
        if evaluation.support_state != falling_state:
            events.append(SupportStateEvaluatedEvent(actor_id=actor.actor_id, support_state=falling_state, position=evaluation.position, detail='The actor is falling.'))
            events.append(AirborneStateChangedEvent(actor_id=actor.actor_id, from_state=evaluation.support_state, to_state=falling_state))
        events.append(FallStartedEvent(actor_id=actor.actor_id, from_position=evaluation.position, reason=evaluation.reason))
        events.append(FallDistanceComputedEvent(actor_id=actor.actor_id, from_position=evaluation.position, to_position=landing.landing_position, distance_ft=landing.distance_ft))
        fall_options = self._sorted_reaction_options(
            discover_fall_reactions(
                state,
                falling_actor_id=actor.actor_id,
                from_position=evaluation.position,
            )
        )
        pending_fall = PendingFallState(
            actor_id=actor.actor_id,
            from_position=evaluation.position,
            to_position=landing.landing_position,
            distance_ft=landing.distance_ft,
            landing_surface_type=landing.landing_surface_type,
        )
        if fall_options:
            events.append(
                ReactionWindowOpenedEvent(
                    window=ReactionWindowState(
                        trigger_id=f'fall:{actor.actor_id}:{state.random_counter}',
                        trigger_type=ReactionTriggerType.FALL_DETECTED,
                        pending_actor_id=actor.actor_id,
                        prompt='A falling creature can be affected by Feather Fall. Choose a legal option or decline.',
                        options=fall_options,
                        resume_state=PendingResolutionState(
                            kind=PendingResolutionKind.COMPLETE_FALL,
                            pending_fall=pending_fall,
                        ),
                    )
                )
            )
            return events
        events.extend(self._complete_fall_events(state, pending_fall=pending_fall, liquid_choice=liquid_choice))
        return events

    def _max_cover_level(self, left, right):
        rank = {'none': 0, 'half': 1, 'three-quarters': 2, 'total': 3}
        return left if rank[left.value] >= rank[right.value] else right

    def _rebuild_battlefield_cell_from_features(self, battlefield, position: GridPosition) -> None:
        base_key = GridPosition(position.x, position.y)
        base_tile = battlefield.base_tiles.get(base_key) or battlefield.tiles.get(base_key)
        if base_tile is None:
            return
        features = [feature for feature in battlefield.features.values() if any(cell.x == position.x and cell.y == position.y for cell in feature.cells)]
        traversable = base_tile.traversable
        occupiable = base_tile.occupiable
        movement_cost = base_tile.movement_cost_feet_per_5ft
        blocks_los = base_tile.blocks_los
        blocks_loe = base_tile.blocks_loe
        cover = base_tile.base_cover
        object_ids = list(base_tile.object_ids)
        blocker_ids = list(base_tile.blocker_ids)
        for feature in features:
            traversable = traversable and feature.traversable
            occupiable = occupiable and feature.occupiable
            blocks_los = blocks_los or feature.blocks_los
            blocks_loe = blocks_loe or feature.blocks_loe
            cover = self._max_cover_level(cover, feature.cover_provided)
            if feature.movement_cost_override_feet_per_5ft is not None:
                movement_cost = max(movement_cost, feature.movement_cost_override_feet_per_5ft)
            if feature.feature_id in battlefield.object_ids and feature.feature_id not in object_ids:
                object_ids.append(feature.feature_id)
            if feature.feature_id in battlefield.blocker_ids and feature.feature_id not in blocker_ids:
                blocker_ids.append(feature.feature_id)
        battlefield.tiles[base_key] = replace(
            base_tile,
            traversable=traversable,
            occupiable=occupiable,
            movement_cost_feet_per_5ft=movement_cost,
            difficult_terrain=(movement_cost > 5),
            blocks_los=blocks_los,
            blocks_loe=blocks_loe,
            base_cover=cover,
            object_ids=tuple(object_ids),
            blocker_ids=tuple(blocker_ids),
        )

    def _rebuild_persistent_area_overlays(self, state: EncounterState) -> None:
        difficult_positions: set[GridPosition] = set()
        for area in state.persistent_areas.values():
            if not area.definition.difficult_terrain:
                continue
            for position in state.battlefield.tiles:
                if persistent_area_contains_position(area, position):
                    difficult_positions.add(position)
        state.battlefield.difficult_terrain_positions = frozenset(difficult_positions)
        if state.battlefield.has_authored_map:
            for position, tile in tuple(state.battlefield.tiles.items()):
                base_tile = state.battlefield.base_tiles.get(position, tile)
                difficult = base_tile.difficult_terrain or position in difficult_positions
                movement_cost = max(base_tile.movement_cost_feet_per_5ft, (10 if difficult else base_tile.movement_cost_feet_per_5ft))
                state.battlefield.tiles[position] = replace(base_tile, difficult_terrain=difficult, movement_cost_feet_per_5ft=movement_cost)

    def _apply_environment_object_projection(self, state: EncounterState, object_id: str) -> None:
        environment_object = state.environment_objects.get(object_id)
        if environment_object is None or environment_object.open_state is None:
            return
        feature = state.battlefield.features.get(environment_object.feature_id)
        if feature is None:
            return
        open_state = environment_object.open_state
        state.battlefield.features[environment_object.feature_id] = replace(
            feature,
            traversable=(environment_object.open_traversable if open_state else environment_object.closed_traversable),
            occupiable=(environment_object.open_occupiable if open_state else environment_object.closed_occupiable),
            blocks_los=(environment_object.open_blocks_los if open_state else environment_object.closed_blocks_los),
            blocks_loe=(environment_object.open_blocks_loe if open_state else environment_object.closed_blocks_loe),
            cover_provided=(environment_object.open_cover_provided if open_state else environment_object.closed_cover_provided),
        )
        for cell in environment_object.position_cells:
            self._rebuild_battlefield_cell_from_features(state.battlefield, cell)

    def _refresh_item_capabilities(self, actor: RuntimeActorState) -> None:
        tracked_item_ids = set(actor.carried_item_counts)
        tracked_item_ids.update(
            capability_id
            for capability_id, capability in actor.capabilities.items()
            if capability.kind == CapabilityKind.ITEM
        )
        for item_id in tracked_item_ids:
            quantity = actor.carried_item_counts.get(item_id, 0)
            item = self.item_catalog.get(item_id)
            runtime = None if item is None else build_item_capability(item, quantity=quantity)
            if runtime is None:
                actor.capabilities.pop(item_id, None)
            else:
                actor.capabilities[item_id] = runtime

    def _apply_event(self, state: EncounterState, event: object) -> None:
        state.event_log.append(event)
        if isinstance(event, SurpriseStateComputedEvent):
            surprised = set(event.surprised_actor_ids)
            for actor_id, actor in state.actors.items():
                actor.surprised = actor_id in surprised
            return
        if isinstance(event, EncounterStartedEvent):
            state.phase = EncounterPhase.IN_PROGRESS
            state.initiative_order = event.initiative_order
            state.round_number = 1
            state.turn_index = 0
            state.active_actor_id = event.first_actor_id
            state.random_counter = event.random_counter_used + 1
            participant_actor_ids = tuple(event.initiative_rolls)
            for actor_id, roll in event.initiative_rolls.items():
                state.actors[actor_id].initiative_roll = roll
                state.actors[actor_id].initiative_total = event.initiative_totals[actor_id]
                self._refresh_turn_resources(state.actors[actor_id], active=(actor_id == event.first_actor_id))
            for actor_id in participant_actor_ids:
                for follow_up in self._interrupt_rest_events(state, actor_id=actor_id, reason=RestInterruptionReason.INITIATIVE):
                    self._apply_event(state, follow_up)
            for actor_id in participant_actor_ids:
                for follow_up in self._support_reconciliation_events(state, actor_id=actor_id, reason=FallReason.STATE_CHANGE):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, ActionEffectEvent):
            actor = state.actors[event.actor_id]
            if event.remaining_movement_ft is not None:
                actor.remaining_movement_ft = event.remaining_movement_ft
            if event.dash_bonus_ft is not None:
                actor.dash_bonus_ft = event.dash_bonus_ft
            if event.disengage_active is not None:
                actor.disengage_active = event.disengage_active
            if event.dodge_active is not None:
                actor.dodge_active = event.dodge_active
            if event.hidden is not None:
                actor.hidden = event.hidden
                if not event.hidden:
                    actor.stealth_check_total = None
                    actor.hidden_from_actor_ids = frozenset()
            if event.help_target_id is not None:
                actor.help_target_id = event.help_target_id
            if event.readied_attack_id is not None and event.readied_target_id is not None:
                actor.readied_action = ReadiedActionState(
                    trigger=ReadyTriggerState(
                        trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW,
                        trigger_actor_id=event.readied_target_id,
                    ),
                    response=ReadyResponseState(
                        response_kind=ReadyResponseKind.ATTACK,
                        attack_id=event.readied_attack_id,
                        target_actor_id=event.readied_target_id,
                    ),
                    declared_round_number=state.round_number,
                )
            self._sync_movement_to_conditions(actor)
            return
        if isinstance(event, AttackDeclaredEvent):
            actor = state.actors[event.actor_id]
            attack = actor.attacks.get(event.attack_id)
            if attack is not None and attack.loading and event.resource is not None:
                actor.loading_spent_resources = frozenset(set(actor.loading_spent_resources) | {event.resource})
            for follow_up in self._friends_end_events_for_attack(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            for follow_up in self._end_effects_on_actor_attack_or_harmful_cast(state, actor_id=event.actor_id, reason='target-attacked'):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ObjectInteractionUsedEvent):
            return
        if isinstance(event, UtilizeActionUsedEvent):
            return
        if isinstance(event, ItemDrawnEvent):
            actor = state.actors[event.actor_id]
            append_held_item(actor, event.item_id, self.item_catalog)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemStowedEvent):
            actor = state.actors[event.actor_id]
            remove_held_item(actor, event.item_id, self.item_catalog)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemDroppedEvent):
            actor = state.actors[event.actor_id]
            remove_held_item(actor, event.item_id, self.item_catalog)
            remove_carried_item(actor, event.item_id, event.quantity)
            self._refresh_item_capabilities(actor)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, GroundItemCreatedEvent):
            state.ground_items[event.ground_item_id] = GroundItemState(
                ground_item_id=event.ground_item_id,
                item_id=event.item_id,
                quantity=event.quantity,
                position=event.position,
                improvised_damage_type=event.improvised_damage_type,
                equivalent_weapon_item_id=event.equivalent_weapon_item_id,
            )
            return
        if isinstance(event, GroundItemRemovedEvent):
            state.ground_items.pop(event.ground_item_id, None)
            return
        if isinstance(event, ItemPickedUpEvent):
            actor = state.actors[event.actor_id]
            add_carried_item(actor, event.item_id, event.quantity)
            append_held_item(actor, event.item_id, self.item_catalog)
            self._refresh_item_capabilities(actor)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemConsumedEvent):
            actor = state.actors[event.actor_id]
            remove_carried_item(actor, event.item_id, event.quantity)
            self._refresh_item_capabilities(actor)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemGrantedEvent):
            actor = state.actors[event.actor_id]
            add_carried_item(actor, event.item_id, event.quantity)
            self._refresh_item_capabilities(actor)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemTransferredEvent):
            source_actor = state.actors[event.source_actor_id]
            target_actor = state.actors[event.target_actor_id]
            remove_carried_item(source_actor, event.item_id, event.quantity)
            add_carried_item(target_actor, event.item_id, event.quantity)
            self._refresh_item_capabilities(source_actor)
            self._refresh_item_capabilities(target_actor)
            refresh_actor_equipment_state(source_actor, self.item_catalog, unarmed_attack=source_actor.attacks.get('unarmed-strike') or default_unarmed_attack(source_actor), active_effects=state.active_effects)
            refresh_actor_equipment_state(target_actor, self.item_catalog, unarmed_attack=target_actor.attacks.get('unarmed-strike') or default_unarmed_attack(target_actor), active_effects=state.active_effects)
            for follow_up in self._floating_disk_load_limit_events(state, disk_actor_id=target_actor.actor_id, reason='floating-disk-overloaded'):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, InventoryItemReplacedEvent):
            actor = state.actors[event.actor_id]
            remove_carried_item(actor, event.old_item_id, event.quantity)
            add_carried_item(actor, event.new_item_id, event.quantity)
            self._refresh_item_capabilities(actor)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ItemIdentifiedEvent):
            actor = state.actors[event.actor_id]
            actor.identified_item_ids = frozenset(set(actor.identified_item_ids) | {event.item_id})
            return
        if isinstance(event, ConsumablesPurifiedEvent):
            actor = state.actors[event.actor_id]
            actor.purified_item_ids = frozenset(set(actor.purified_item_ids) | set(event.item_ids))
            return
        if isinstance(event, ShieldDonnedEvent):
            actor = state.actors[event.actor_id]
            actor.off_hand_item_id = event.item_id
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ShieldDoffedEvent):
            actor = state.actors[event.actor_id]
            if actor.off_hand_item_id == event.item_id:
                actor.off_hand_item_id = None
            actor.worn_shield_item_id = None
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ArmorDonnedEvent):
            actor = state.actors[event.actor_id]
            actor.equipped_armor_item_id = event.item_id
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ArmorDoffedEvent):
            actor = state.actors[event.actor_id]
            if actor.equipped_armor_item_id == event.item_id:
                actor.equipped_armor_item_id = None
            actor.worn_armor_item_id = None
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, AmmunitionConsumedEvent):
            actor = state.actors[event.actor_id]
            remove_carried_item(actor, event.ammunition_item_id, event.quantity)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            return
        if isinstance(event, AmmunitionMissingEvent):
            return
        if isinstance(event, WeaponEquippedEvent):
            actor = state.actors[event.actor_id]
            equip_item_to_slot(actor, event.item_id, slot=event.slot, item_catalog=self.item_catalog)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, WeaponUnequippedEvent):
            actor = state.actors[event.actor_id]
            current_slot = hand_slot_for_item(actor, event.item_id)
            if current_slot == event.slot:
                if event.slot == EquipmentSlot.MAIN_HAND:
                    actor.main_hand_item_id = None
                elif event.slot == EquipmentSlot.OFF_HAND:
                    actor.off_hand_item_id = None
            removed = False
            next_held_items: list[str] = []
            for held_item_id in actor.held_item_ids:
                if not removed and held_item_id == event.item_id:
                    removed = True
                    continue
                next_held_items.append(held_item_id)
            actor.held_item_ids = tuple(next_held_items)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ImprovisedWeaponUsedEvent):
            return
        if isinstance(event, EnvironmentObjectUsedEvent):
            environment_object = state.environment_objects.get(event.object_id)
            if environment_object is None:
                return
            if event.action == EnvironmentObjectAction.OPEN:
                environment_object.open_state = True
            elif event.action == EnvironmentObjectAction.CLOSE:
                environment_object.open_state = False
            elif event.action == EnvironmentObjectAction.TOGGLE and environment_object.open_state is not None:
                environment_object.open_state = not environment_object.open_state
            elif event.action == EnvironmentObjectAction.ACTIVATE and environment_object.open_state is not None:
                environment_object.open_state = True
            elif event.action == EnvironmentObjectAction.DEACTIVATE and environment_object.open_state is not None:
                environment_object.open_state = False
            self._apply_environment_object_projection(state, event.object_id)
            return
        if isinstance(event, ActorHiddenEvent):
            actor = state.actors[event.actor_id]
            actor.hidden = True
            actor.stealth_check_total = event.stealth_check_total
            actor.hidden_from_actor_ids = frozenset(event.hidden_from_actor_ids)
            return
        if isinstance(event, ActorRevealedEvent):
            actor = state.actors[event.actor_id]
            if event.observer_id is None:
                actor.hidden = False
                actor.stealth_check_total = None
                actor.hidden_from_actor_ids = frozenset()
            else:
                actor.hidden_from_actor_ids = frozenset(observer_id for observer_id in actor.hidden_from_actor_ids if observer_id != event.observer_id)
                if not actor.hidden_from_actor_ids:
                    actor.hidden = False
                    actor.stealth_check_total = None
            return
        if isinstance(event, ResourceSpentEvent):
            actor = state.actors[event.actor_id]
            if event.resource == 'action':
                actor.action_available = False
            elif event.resource == 'bonus':
                actor.bonus_action_available = False
            elif event.resource == 'reaction':
                actor.reaction_available = False
            elif event.resource == 'object':
                actor.remaining_free_object_interaction = False
            elif event.resource == 'movement':
                amount = max(0, event.amount)
                actor.movement_spent_ft += amount
                actor.remaining_movement_ft = max(0, actor.remaining_movement_ft - amount)
            return
        if isinstance(event, ResourcePoolSpentEvent):
            actor = state.actors[event.actor_id]
            pool = actor.resource_pools.get(event.resource_id)
            if pool is None:
                raise EncounterValidationError(f'Resource pool {event.resource_id!r} is missing for actor {event.actor_id!r}.')
            pool.current = event.current_after
            return
        if isinstance(event, ResourcePoolRecoveredEvent):
            actor = state.actors[event.actor_id]
            pool = actor.resource_pools.get(event.resource_id)
            if pool is None:
                raise EncounterValidationError(f'Resource pool {event.resource_id!r} is missing for actor {event.actor_id!r}.')
            pool.current = event.current_after
            return
        if isinstance(event, MoveDeclaredEvent):
            return
        if isinstance(event, ForcedMovementStepResolvedEvent):
            actor = state.actors[event.actor_id]
            old_position = actor.position
            actor.position = event.to_position
            for follow_up in self._persistent_area_transition_events(state, actor_id=event.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for follow_up in self._terrain_hazard_events_for_destination(state, actor_id=event.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            for follow_up in self._effect_reconciliation_events(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, MovementSpentEvent):
            actor = state.actors[event.actor_id]
            old_position = actor.position
            actor.position = event.to_position
            if event.consume_turn_movement:
                actor.remaining_movement_ft = event.remaining_movement_ft
                if event.movement_spent_ft is not None:
                    actor.movement_spent_ft = event.movement_spent_ft
            delta_x = event.to_position.x - old_position.x
            delta_y = event.to_position.y - old_position.y
            delta_z = event.to_position.z - old_position.z
            moved_related_ids: list[str] = []
            for dragged_actor in get_dragged_targets(state, actor.actor_id):
                dragged_actor.position = GridPosition(dragged_actor.position.x + delta_x, dragged_actor.position.y + delta_y, dragged_actor.position.z + delta_z)
                moved_related_ids.append(dragged_actor.actor_id)
            for rider in state.actors.values():
                if rider.mounted_on_actor_id != actor.actor_id:
                    continue
                rider.position = GridPosition(rider.position.x + delta_x, rider.position.y + delta_y, rider.position.z + delta_z)
                moved_related_ids.append(rider.actor_id)
            moved_related_ids = list(dict.fromkeys(moved_related_ids))
            for follow_up in self._support_reconciliation_events(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._persistent_area_transition_events(state, actor_id=actor.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for follow_up in self._terrain_hazard_events_for_destination(state, actor_id=actor.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for related_actor_id in moved_related_ids:
                for follow_up in self._support_reconciliation_events(state, actor_id=related_actor_id, reason=FallReason.FORCED_RELOCATION):
                    self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            for related_actor_id in moved_related_ids:
                for follow_up in self._effect_reconciliation_events(state, actor_id=related_actor_id):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, MountedActorEvent):
            actor = state.actors[event.actor_id]
            mount = state.actors[event.mount_actor_id]
            actor.mounted_on_actor_id = mount.actor_id
            old_position = actor.position
            actor.position = mount.position
            for follow_up in self._support_reconciliation_events(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._persistent_area_transition_events(state, actor_id=actor.actor_id, from_position=old_position, to_position=actor.position):
                self._apply_event(state, follow_up)
            for follow_up in self._terrain_hazard_events_for_destination(state, actor_id=actor.actor_id, from_position=old_position, to_position=actor.position):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            for follow_up in self._effect_reconciliation_events(state, actor_id=actor.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, DismountedActorEvent):
            actor = state.actors[event.actor_id]
            if actor.mounted_on_actor_id == event.mount_actor_id:
                actor.mounted_on_actor_id = None
            for follow_up in self._support_reconciliation_events(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, SharedSensesStartedEvent):
            state.actors[event.actor_id].shared_senses_actor_id = event.familiar_actor_id
            return
        if isinstance(event, SharedSensesEndedEvent):
            actor = state.actors[event.actor_id]
            if event.familiar_actor_id is None or actor.shared_senses_actor_id == event.familiar_actor_id:
                actor.shared_senses_actor_id = None
            for condition_type in (ConditionType.BLINDED, ConditionType.DEAFENED):
                instance_id = self._shared_senses_condition_instance_id(actor_id=actor.actor_id, familiar_actor_id=event.familiar_actor_id or '', condition_type=condition_type)
                if any(instance.instance_id == instance_id for instance in actor.condition_instances):
                    self._apply_event(state, self._condition_removed_event_for_instance(actor.actor_id, instance_id))
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, StoodFromProneEvent):
            state.actors[event.actor_id].remaining_movement_ft = event.remaining_movement_ft
            if event.movement_spent_ft is not None:
                state.actors[event.actor_id].movement_spent_ft = event.movement_spent_ft
            for follow_up in self._support_reconciliation_events(state, actor_id=event.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ReactionWindowOpenedEvent):
            state.pending_reaction_window = event.window
            return
        if isinstance(event, (ReactionSubmittedEvent, ReactionChosenEvent)):
            state.pending_reaction_window = None
            return
        if isinstance(event, ReadyDeclaredEvent):
            state.actors[event.actor_id].readied_action = event.ready_state
            return
        if isinstance(event, ReadyExpiredEvent):
            state.actors[event.actor_id].readied_action = None
            return
        if isinstance(event, ReadyTriggeredEvent):
            state.actors[event.actor_id].readied_action = None
            return
        if isinstance(event, ReadiedSpellDissipatedEvent):
            actor = state.actors[event.actor_id]
            if actor.readied_action is not None and actor.readied_action.response.spell_id == event.spell_id:
                actor.readied_action = None
            return
        if isinstance(event, (ReadiedActionIgnoredEvent, ReactionRejectedEvent, ReactionResolvedEvent, TurnInterruptedEvent, TurnResumedEvent, SimultaneousEffectsDetectedEvent, SimultaneousEffectsOrderedEvent, TriggerResolutionCompletedEvent)):
            return
        if isinstance(event, StartOfTurnTriggersQueuedEvent):
            state.pending_timing_queue = event.queue if event.queue.entries else None
            return
        if isinstance(event, EndOfTurnTriggersQueuedEvent):
            state.pending_timing_queue = event.queue if event.queue.entries else None
            return
        if isinstance(event, D20TestRolledEvent):
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, EffectRollAppliedEvent):
            state.random_counter = event.random_counter_used + 1
            effect = state.active_effects.get(event.effect_instance_id)
            if effect is not None and effect.definition.damage_reduction_once_per_turn is not None and event.reason.startswith('damage-reduction:') and state.phase == EncounterPhase.IN_PROGRESS:
                state.active_effects[event.effect_instance_id] = replace(effect, last_once_per_turn_round_number=state.round_number, last_once_per_turn_turn_actor_id=state.active_actor_id)
            return
        if isinstance(event, TimeAdvancedEvent):
            state.clock_seconds += event.elapsed_seconds
            elapsed_minutes = event.elapsed_seconds // 60
            for actor in state.actors.values():
                if actor.dying_state.stable_recovery_minutes_remaining is not None:
                    minutes_remaining = max(0, actor.dying_state.stable_recovery_minutes_remaining - elapsed_minutes)
                    actor.dying_state = replace(actor.dying_state, stable_recovery_minutes_remaining=(minutes_remaining or None))
                    if minutes_remaining == 0 and actor.current_hit_points == 0 and actor.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
                        self._apply_event(state, HitPointsRecoveredFromRestEvent(actor_id=actor.actor_id, amount_recovered=1, current_hit_points_after=1))
                for follow_up in self._time_advance_followup_events(state, actor_id=actor.actor_id, elapsed_seconds=event.elapsed_seconds, activity_type=event.activity_type):
                    self._apply_event(state, follow_up)
            for ritual in tuple(state.ritual_casts.values()):
                remaining_seconds = max(0, ritual.remaining_seconds - event.elapsed_seconds)
                state.ritual_casts[ritual.ritual_id] = replace(ritual, remaining_seconds=remaining_seconds)
                if remaining_seconds == 0:
                    self._apply_event(state, RitualCastCompletedEvent(ritual_id=ritual.ritual_id, actor_id=ritual.actor_id, capability_id=ritual.capability_id))
            return
        if isinstance(event, SaveRolledEvent):
            state.random_counter = event.random_counter_used + 1
            target_actor_id = event.resolution.request.context.target_actor_id
            source_actor_id = event.resolution.request.context.source_actor_id
            if target_actor_id is not None:
                for follow_up in self._consume_next_saving_throw_effects(state, actor_id=target_actor_id):
                    self._apply_event(state, follow_up)
            for follow_up in self._friends_end_events_for_save(state, source_actor_id=source_actor_id, target_actor_id=target_actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, CheckRolledEvent):
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, AttackRolledEvent):
            for follow_up in self._consume_next_attack_roll_effects(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ContestRolledEvent):
            return
        if isinstance(event, DamageRolledEvent):
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, DamageAppliedEvent):
            target = state.actors[event.target_id]
            previous_hit_points = target.current_hit_points
            previous_temp_hit_points = target.temp_hit_points
            was_at_zero_hit_points = previous_hit_points == 0
            target.current_hit_points = event.target_hit_points_after
            target.temp_hit_points = event.target_temp_hit_points_after
            self._apply_zero_hit_point_damage_followups(
                state,
                target_id=target.actor_id,
                source_actor_id=event.source_actor_id,
                damage_type=event.damage_type,
                applied_damage_total=event.applied_damage_total,
                critical_hit=event.critical_hit,
                was_at_zero_hit_points=was_at_zero_hit_points,
                previous_hit_points=previous_hit_points,
                previous_temp_hit_points=previous_temp_hit_points,
            )
            if event.applied_damage_total > 0:
                for follow_up in self._interrupt_rest_events(state, actor_id=target.actor_id, reason=RestInterruptionReason.DAMAGE):
                    self._apply_event(state, follow_up)
                for follow_up in self._concentration_damage_events(state, actor_id=target.actor_id, damage_total=event.applied_damage_total):
                    self._apply_event(state, follow_up)
                for follow_up in self._friends_end_events_for_damage(state, target_id=target.actor_id, source_actor_id=event.source_actor_id):
                    self._apply_event(state, follow_up)
                if event.source_actor_id is not None:
                    for follow_up in self._end_effects_on_actor_deal_damage(state, actor_id=event.source_actor_id, reason='target-dealt-damage'):
                        self._apply_event(state, follow_up)
                for follow_up in self._end_effects_on_source_side_damage(state, target_id=target.actor_id, source_actor_id=event.source_actor_id):
                    self._apply_event(state, follow_up)
                for follow_up in self._sleep_end_events(state, actor_id=target.actor_id, reason='sleep-broken-damage'):
                    self._apply_event(state, follow_up)
                for follow_up in self._hideous_laughter_damage_events(state, actor_id=target.actor_id):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, HitPointsDroppedToZeroEvent):
            return
        if isinstance(event, InstantDeathTriggeredEvent):
            return
        if isinstance(event, UnconsciousAtZeroAppliedEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, status=DyingStateStatus.AT_0_HP_UNCONSCIOUS, death_save_successes=0, death_save_failures=0, stable_recovery_minutes_remaining=None)
            if not any(instance.instance_id == self._zero_hit_points_unconscious_instance_id(actor.actor_id) for instance in actor.condition_instances):
                self._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._zero_hit_points_unconscious_instance(actor.actor_id)))
            return
        if isinstance(event, DeathSaveRequestedEvent):
            return
        if isinstance(event, DeathSaveRolledEvent):
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, DeathSaveSucceededEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, death_save_successes=event.total_successes)
            return
        if isinstance(event, DeathSaveFailedEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, death_save_failures=event.total_failures, status=DyingStateStatus.AT_0_HP_UNCONSCIOUS, stable_recovery_minutes_remaining=None)
            return
        if isinstance(event, DeathSaveNaturalOneEvent):
            return
        if isinstance(event, DeathSaveNaturalTwentyEvent):
            return
        if isinstance(event, ShortRestStartedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.SHORT,
                status=RestStateStatus.SHORT_REST_IN_PROGRESS,
                started_at_seconds=event.started_at_seconds,
                accumulated_rest_seconds=0,
                required_rest_seconds=60 * 60,
            )
            return
        if isinstance(event, ShortRestInterruptedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.SHORT,
                status=RestStateStatus.INTERRUPTED,
                started_at_seconds=actor.rest_state.started_at_seconds,
                accumulated_rest_seconds=event.accumulated_rest_seconds,
                required_rest_seconds=60 * 60,
                last_interruption_reason=event.reason,
            )
            return
        if isinstance(event, ShortRestCompletedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.SHORT,
                status=RestStateStatus.SHORT_REST_COMPLETED,
                started_at_seconds=actor.rest_state.started_at_seconds,
                accumulated_rest_seconds=max(actor.rest_state.accumulated_rest_seconds, 60 * 60),
                required_rest_seconds=60 * 60,
                short_rest_benefits_granted=True,
                hit_dice_window_open=True,
                last_completed_rest_type=RestType.SHORT,
                last_completed_at_seconds=event.completed_at_seconds,
            )
            return
        if isinstance(event, LongRestStartedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.LONG,
                status=RestStateStatus.LONG_REST_IN_PROGRESS,
                started_at_seconds=event.started_at_seconds,
                accumulated_rest_seconds=0,
                required_rest_seconds=event.required_rest_seconds,
            )
            clear_equipped_items(actor, self.item_catalog)
            refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
            return
        if isinstance(event, LongRestInterruptedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.LONG,
                status=RestStateStatus.INTERRUPTED,
                started_at_seconds=actor.rest_state.started_at_seconds,
                accumulated_rest_seconds=event.accumulated_rest_seconds,
                required_rest_seconds=actor.rest_state.required_rest_seconds + (60 * 60),
                sleep_seconds=actor.rest_state.sleep_seconds,
                light_activity_seconds=actor.rest_state.light_activity_seconds,
                interruption_count=event.interruption_count,
                last_interruption_reason=event.reason,
                short_rest_benefits_granted=(actor.rest_state.short_rest_benefits_granted or event.granted_short_rest_benefits),
                hit_dice_window_open=(actor.rest_state.hit_dice_window_open or event.granted_short_rest_benefits),
            )
            return
        if isinstance(event, LongRestResumedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = replace(
                actor.rest_state,
                status=RestStateStatus.LONG_REST_IN_PROGRESS,
                required_rest_seconds=event.required_rest_seconds,
                last_interruption_reason=None,
                exertion_seconds=0,
            )
            return
        if isinstance(event, LongRestCompletedEvent):
            actor = state.actors[event.actor_id]
            actor.rest_state = RestState(
                rest_type=RestType.LONG,
                status=RestStateStatus.LONG_REST_COMPLETED,
                started_at_seconds=actor.rest_state.started_at_seconds,
                accumulated_rest_seconds=actor.rest_state.accumulated_rest_seconds,
                required_rest_seconds=actor.rest_state.required_rest_seconds,
                short_rest_benefits_granted=True,
                last_completed_rest_type=RestType.LONG,
                last_completed_at_seconds=event.completed_at_seconds,
            )
            actor.last_long_rest_completed_at_seconds = event.completed_at_seconds
            self._restore_actor_base_state_for_long_rest(actor, active_effects=state.active_effects)
            return
        if isinstance(event, HitPointDieSpentEvent):
            actor = state.actors[event.actor_id]
            actor.remaining_hit_dice = event.remaining_hit_dice
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, HitPointDiceRestoredEvent):
            state.actors[event.actor_id].remaining_hit_dice = event.remaining_hit_dice
            return
        if isinstance(event, HitPointsRecoveredFromRestEvent):
            actor = state.actors[event.actor_id]
            was_at_zero_hit_points = actor.current_hit_points == 0
            actor.current_hit_points = event.current_hit_points_after
            if was_at_zero_hit_points and actor.current_hit_points > 0:
                self._apply_event(state, HealedFromZeroEvent(actor_id=actor.actor_id, source_actor_id=None, hit_points_after=actor.current_hit_points))
            return
        if isinstance(event, SpellSlotsRecoveredFromRestEvent):
            actor = state.actors[event.actor_id]
            pool = actor.resource_pools.get(event.resource_id)
            if pool is not None:
                pool.current = event.current_after
            return
        if isinstance(event, ResourceRecoveredFromRestEvent):
            actor = state.actors[event.actor_id]
            capability = actor.capabilities.get(event.resource_id)
            if capability is not None:
                actor.capabilities[event.resource_id] = replace(capability, remaining_uses=event.current_after)
                return
            spell = actor.spells.get(event.resource_id)
            if spell is not None:
                actor.spells[event.resource_id] = replace(spell, remaining_uses=event.current_after)
                return
            pool = actor.resource_pools.get(event.resource_id)
            if pool is not None:
                pool.current = event.current_after
            return
        if isinstance(event, ItemChargesRecoveredFromRestEvent):
            actor = state.actors[event.actor_id]
            capability = actor.capabilities.get(event.resource_id)
            if capability is not None:
                actor.capabilities[event.resource_id] = replace(capability, remaining_uses=event.current_after)
                return
            pool = actor.resource_pools.get(event.resource_id)
            if pool is not None:
                pool.current = event.current_after
            return
        if isinstance(event, ExhaustionReducedFromRestEvent):
            return
        if isinstance(event, RestLockoutAppliedEvent):
            state.actors[event.actor_id].last_long_rest_completed_at_seconds = event.available_at_seconds - (16 * 60 * 60)
            return
        if isinstance(event, RestDeniedEvent):
            return
        if isinstance(event, StabilizedEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, status=DyingStateStatus.STABLE_AT_0_HP, death_save_successes=0, death_save_failures=0, stable_recovery_minutes_remaining=(event.recovery_hours * 60))
            if event.random_counter_used is not None:
                state.random_counter = event.random_counter_used + 1
            if not any(instance.instance_id == self._zero_hit_points_unconscious_instance_id(actor.actor_id) for instance in actor.condition_instances):
                self._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._zero_hit_points_unconscious_instance(actor.actor_id)))
            return
        if isinstance(event, StableBrokenByDamageEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, status=DyingStateStatus.AT_0_HP_UNCONSCIOUS, stable_recovery_minutes_remaining=None)
            return
        if isinstance(event, DiedEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, status=DyingStateStatus.DEAD, stable_recovery_minutes_remaining=None)
            zero_hp_instance_id = self._zero_hit_points_unconscious_instance_id(actor.actor_id)
            if any(instance.instance_id == zero_hp_instance_id for instance in actor.condition_instances):
                self._apply_event(state, self._condition_removed_event_for_instance(actor.actor_id, zero_hp_instance_id))
            surviving_sides = {current_actor.side for current_actor in state.actors.values() if self._actor_counts_as_surviving(current_actor)}
            if state.phase == EncounterPhase.IN_PROGRESS and len(surviving_sides) == 1:
                self._apply_event(state, EncounterCompletedEvent(winning_side=next(iter(surviving_sides))))
            return
        if isinstance(event, HealedFromZeroEvent):
            actor = state.actors[event.actor_id]
            actor.dying_state = replace(actor.dying_state, status=DyingStateStatus.ALIVE, death_save_successes=0, death_save_failures=0, stable_recovery_minutes_remaining=None)
            zero_hp_instance_id = self._zero_hit_points_unconscious_instance_id(actor.actor_id)
            if any(instance.instance_id == zero_hp_instance_id for instance in actor.condition_instances):
                self._apply_event(state, self._condition_removed_event_for_instance(actor.actor_id, zero_hp_instance_id))
            return
        if isinstance(event, TemporaryHitPointsAppliedEvent):
            actor = state.actors[event.target_id]
            actor.temp_hit_points = max(actor.temp_hit_points, event.temp_hit_points_total)
            if actor.current_hit_points == 0:
                self._apply_event(state, TemporaryHitPointsReceivedAtZeroEvent(actor_id=actor.actor_id, temp_hit_points_after=actor.temp_hit_points))
            return
        if isinstance(event, TemporaryHitPointsReceivedAtZeroEvent):
            return
        if isinstance(event, SupportStateEvaluatedEvent):
            state.actors[event.actor_id].support_state = event.support_state
            return
        if isinstance(event, AirborneStateChangedEvent):
            return
        if isinstance(event, HazardTriggeredEvent):
            return
        if isinstance(event, HazardResolvedEvent):
            return
        if isinstance(event, LiquidEntryDetectedEvent):
            return
        if isinstance(event, ImprovisedObjectCreatedEvent):
            feature = instantiate_template_feature(state.battlefield, feature_id=event.feature_id, template_id=ImprovisedTemplateId(event.template_id), anchor=event.anchor)
            state.battlefield.features[event.feature_id] = feature
            if event.feature_id not in state.battlefield.dynamic_feature_ids:
                state.battlefield.dynamic_feature_ids = tuple(state.battlefield.dynamic_feature_ids) + (event.feature_id,)
            if event.feature_id not in state.battlefield.object_ids:
                state.battlefield.object_ids = tuple(state.battlefield.object_ids) + (event.feature_id,)
            if (feature.blocks_los or feature.blocks_loe or not feature.occupiable) and event.feature_id not in state.battlefield.blocker_ids:
                state.battlefield.blocker_ids = tuple(state.battlefield.blocker_ids) + (event.feature_id,)
            recompute_dynamic_battlefield_state(state.battlefield)
            return
        if isinstance(event, TerrainEffectCreatedEvent):
            feature = instantiate_template_feature(state.battlefield, feature_id=event.feature_id, template_id=ImprovisedTemplateId(event.template_id), anchor=event.anchor)
            state.battlefield.features[event.feature_id] = feature
            if event.feature_id not in state.battlefield.dynamic_feature_ids:
                state.battlefield.dynamic_feature_ids = tuple(state.battlefield.dynamic_feature_ids) + (event.feature_id,)
            if (feature.blocks_los or feature.blocks_loe or not feature.occupiable) and event.feature_id not in state.battlefield.blocker_ids:
                state.battlefield.blocker_ids = tuple(state.battlefield.blocker_ids) + (event.feature_id,)
            recompute_dynamic_battlefield_state(state.battlefield)
            return
        if isinstance(event, ImprovisedObjectDestroyedEvent):
            state.battlefield.features.pop(event.feature_id, None)
            state.battlefield.dynamic_feature_ids = tuple(feature_id for feature_id in state.battlefield.dynamic_feature_ids if feature_id != event.feature_id)
            state.battlefield.object_ids = tuple(feature_id for feature_id in state.battlefield.object_ids if feature_id != event.feature_id)
            state.battlefield.blocker_ids = tuple(feature_id for feature_id in state.battlefield.blocker_ids if feature_id != event.feature_id)
            recompute_dynamic_battlefield_state(state.battlefield)
            return
        if isinstance(event, TerrainEffectEndedEvent):
            state.battlefield.features.pop(event.feature_id, None)
            state.battlefield.dynamic_feature_ids = tuple(feature_id for feature_id in state.battlefield.dynamic_feature_ids if feature_id != event.feature_id)
            state.battlefield.blocker_ids = tuple(feature_id for feature_id in state.battlefield.blocker_ids if feature_id != event.feature_id)
            recompute_dynamic_battlefield_state(state.battlefield)
            return
        if isinstance(event, CoverStateModifiedEvent):
            state.battlefield.cover_by_pair[(event.attacker_id, event.target_id)] = event.cover_level
            return
        if isinstance(event, TeleportResolvedEvent):
            actor = state.actors[event.actor_id]
            old_position = actor.position
            actor.position = event.to_position
            for follow_up in self._support_reconciliation_events(state, actor_id=event.actor_id, reason=FallReason.UNSUPPORTED_RELOCATION):
                self._apply_event(state, follow_up)
            for follow_up in self._persistent_area_transition_events(state, actor_id=event.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            for follow_up in self._effect_reconciliation_events(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, CapabilityDeclaredEvent):
            if event.runtime_option_id is not None:
                actor = state.actors[event.actor_id]
                capability = actor.capabilities.get(event.runtime_option_id)
                if capability is not None:
                    actor.capabilities[event.runtime_option_id] = replace(capability, remaining_uses=event.remaining_uses)
                    if capability.kind == CapabilityKind.ITEM and capability.source_record_id is not None:
                        item_record = self.item_catalog.get(capability.source_record_id)
                        if item_record is not None and actor.carried_item_counts.get(capability.source_record_id, 0) > 0:
                            actor.carried_item_counts[capability.source_record_id] -= 1
                            if actor.carried_item_counts[capability.source_record_id] <= 0:
                                actor.carried_item_counts.pop(capability.source_record_id, None)
                            self._refresh_item_capabilities(actor)
            return
        if isinstance(event, CapabilityRechargeRolledEvent):
            state.random_counter = event.random_counter_used + 1
            if event.recharged:
                actor = state.actors[event.actor_id]
                capability = actor.capabilities.get(event.capability_id)
                if capability is not None:
                    actor.capabilities[event.capability_id] = replace(capability, remaining_uses=1)
            return
        if isinstance(event, TargetsResolvedEvent):
            return
        if isinstance(event, AreaResolvedEvent):
            return
        if isinstance(event, CapabilityHitEvent):
            if event.capability_id == 'friends' and event.target_id is not None:
                actor = state.actors[event.actor_id]
                actor.friends_targeted_at_seconds[event.target_id] = state.clock_seconds
            return
        if isinstance(event, CapabilityMissedEvent):
            if event.capability_id == 'friends' and event.target_id is not None:
                actor = state.actors[event.actor_id]
                actor.friends_targeted_at_seconds[event.target_id] = state.clock_seconds
            return
        if isinstance(event, AttackRollRequestedEvent):
            for follow_up in self._friends_end_events_for_attack(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            for follow_up in self._end_effects_on_actor_attack_or_harmful_cast(state, actor_id=event.actor_id, reason='target-attacked'):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, SneakAttackAppliedEvent):
            actor = state.actors[event.actor_id]
            actor.last_sneak_attack_round_number = state.round_number
            actor.last_sneak_attack_turn_actor_id = state.active_actor_id
            return
        if isinstance(event, HealingAppliedEvent):
            target = state.actors[event.target_id]
            was_at_zero_hit_points = target.current_hit_points == 0
            target.current_hit_points = event.target_hit_points_after
            if was_at_zero_hit_points and target.current_hit_points > 0:
                self._apply_event(state, HealedFromZeroEvent(actor_id=target.actor_id, source_actor_id=event.source_actor_id, hit_points_after=target.current_hit_points))
            return
        if isinstance(event, ForcedMovementAppliedEvent):
            return
        if isinstance(event, ArmorClassAdjustedEvent):
            state.actors[event.actor_id].armor_class_modifier += event.delta
            return
        if isinstance(event, HitPointMaximumAdjustedEvent):
            actor = state.actors[event.actor_id]
            new_max_hit_points = max(1, actor.max_hit_points + event.delta)
            actor.max_hit_points = new_max_hit_points
            if event.adjust_current_by_same_delta:
                actor.current_hit_points = max(0, min(new_max_hit_points, actor.current_hit_points + event.delta))
            else:
                actor.current_hit_points = min(actor.current_hit_points, new_max_hit_points)
            return
        if isinstance(event, ActiveEffectStartedEvent):
            state.active_effects[event.effect.effect_instance_id] = event.effect
            for actor_id in self._active_effect_actor_ids(event.effect):
                self._recompute_actor_effect_modifiers(state, actor_id)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ActiveEffectTickedEvent):
            return
        if isinstance(event, ActiveEffectEndedEvent):
            effect = state.active_effects.pop(event.effect_instance_id, None)
            if effect is not None:
                affected_actor_ids = tuple(self._active_effect_actor_ids(effect))
                for actor_id in affected_actor_ids:
                    self._recompute_actor_effect_modifiers(state, actor_id)
                source_actor = state.actors.get(effect.source_actor_id)
                if source_actor is not None and source_actor.readied_action is not None and source_actor.readied_action.concentration_effect_id == event.effect_instance_id:
                    self._apply_event(
                        state,
                        ReadiedSpellDissipatedEvent(
                            actor_id=source_actor.actor_id,
                            spell_id=source_actor.readied_action.response.spell_id or source_actor.readied_action.response.capability_id or effect.capability_id,
                            reason=event.reason,
                        ),
                    )
                for actor_id in affected_actor_ids:
                    for follow_up in self._effect_reconciliation_events(state, actor_id=actor_id):
                        self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, PersistentEffectStartedEvent):
            state.persistent_effects[event.persistent_effect.persistent_effect_id] = event.persistent_effect
            return
        if isinstance(event, CreatedCreatureSpawnedEvent):
            creature = event.creature
            linked_actor = self._build_summoned_actor(state, creature)
            if linked_actor is not None:
                state.actors[linked_actor.actor_id] = linked_actor
                creature = replace(creature, linked_actor_id=linked_actor.actor_id)
                if state.phase == EncounterPhase.IN_PROGRESS and 'floating-disk' not in set(creature.definition.semantic_tags):
                    self.insert_reinforcement_into_initiative(state, actor_id=linked_actor.actor_id)
            state.summoned_creatures[creature.summon_id] = creature
            return
        if isinstance(event, CreatedCreatureRemovedEvent):
            creature = state.summoned_creatures.pop(event.summon_id, None)
            linked_actor_id = None if creature is None else creature.linked_actor_id
            if linked_actor_id is not None:
                for owner in state.actors.values():
                    if owner.shared_senses_actor_id == linked_actor_id:
                        self._apply_event(state, SharedSensesEndedEvent(actor_id=owner.actor_id, familiar_actor_id=linked_actor_id, reason=event.reason))
                linked_actor = state.actors.pop(linked_actor_id, None)
                if linked_actor is not None:
                    for rider in state.actors.values():
                        if rider.mounted_on_actor_id == linked_actor_id:
                            rider.mounted_on_actor_id = None
                    for item_id, quantity in tuple(linked_actor.carried_item_counts.items()):
                        if quantity <= 0:
                            continue
                        ground_item_id = self._next_ground_item_id(state, item_id)
                        state.ground_items[ground_item_id] = GroundItemState(ground_item_id=ground_item_id, item_id=item_id, quantity=quantity, position=linked_actor.position)
                state.initiative_order = tuple(actor_id for actor_id in state.initiative_order if actor_id != linked_actor_id)
                if state.active_actor_id == linked_actor_id:
                    state.active_actor_id = state.initiative_order[0] if state.initiative_order else None
            return
        if isinstance(event, CreatedObjectSpawnedEvent):
            created_object = event.created_object
            state.created_objects[created_object.object_id] = created_object
            if created_object.linked_feature_id is not None:
                anchor = created_object.persistent.anchor_position or created_object.cells[0]
                anchor_xy = GridPosition(anchor.x, anchor.y)
                base_tile = state.battlefield.tiles.get(anchor_xy) or state.battlefield.base_tiles.get(anchor_xy)
                elevation_ft = base_tile.elevation_ft if base_tile is not None else anchor.z
                feature = BattlefieldFeature(
                    feature_id=created_object.linked_feature_id,
                    feature_type=created_object.definition.feature_type,
                    cells=created_object.cells,
                    elevation_ft=elevation_ft,
                    traversable=created_object.definition.traversable,
                    occupiable=created_object.definition.occupiable,
                    blocks_los=created_object.definition.blocks_los,
                    blocks_loe=created_object.definition.blocks_loe,
                    cover_provided=created_object.definition.cover_provided,
                    bottom_ft=elevation_ft + created_object.definition.bottom_offset_ft,
                    top_ft=elevation_ft + created_object.definition.top_offset_ft,
                    tags=created_object.definition.semantic_tags,
                )
                state.battlefield.features[feature.feature_id] = feature
                if feature.feature_id not in state.battlefield.dynamic_feature_ids:
                    state.battlefield.dynamic_feature_ids = tuple(state.battlefield.dynamic_feature_ids) + (feature.feature_id,)
                if feature.feature_id not in state.battlefield.object_ids:
                    state.battlefield.object_ids = tuple(state.battlefield.object_ids) + (feature.feature_id,)
                if (feature.blocks_los or feature.blocks_loe or not feature.occupiable) and feature.feature_id not in state.battlefield.blocker_ids:
                    state.battlefield.blocker_ids = tuple(state.battlefield.blocker_ids) + (feature.feature_id,)
                recompute_dynamic_battlefield_state(state.battlefield)
                for follow_up in self._visibility_reconciliation_events(state):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, CreatedObjectRemovedEvent):
            created_object = state.created_objects.pop(event.object_id, None)
            if created_object is not None and created_object.linked_feature_id is not None:
                state.battlefield.features.pop(created_object.linked_feature_id, None)
                state.battlefield.dynamic_feature_ids = tuple(feature_id for feature_id in state.battlefield.dynamic_feature_ids if feature_id != created_object.linked_feature_id)
                state.battlefield.object_ids = tuple(feature_id for feature_id in state.battlefield.object_ids if feature_id != created_object.linked_feature_id)
                state.battlefield.blocker_ids = tuple(feature_id for feature_id in state.battlefield.blocker_ids if feature_id != created_object.linked_feature_id)
                recompute_dynamic_battlefield_state(state.battlefield)
                for follow_up in self._visibility_reconciliation_events(state):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, IllusionCreatedEvent):
            state.illusions[event.illusion.illusion_id] = event.illusion
            return
        if isinstance(event, IllusionInteractedWithEvent):
            illusion = state.illusions.get(event.illusion_id)
            if illusion is not None:
                state.illusions[event.illusion_id] = update_illusion_observer_state(
                    illusion,
                    observer_id=event.observer_id,
                    interaction_kind=IllusionInteractionKind(event.interaction_kind),
                )
            return
        if isinstance(event, IllusionRevealedToObserverEvent):
            return
        if isinstance(event, IllusionDisbelievedByObserverEvent):
            return
        if isinstance(event, DetectionPayloadProducedEvent):
            state.informational_payloads[event.payload.payload_id] = event.payload
            return
        if isinstance(event, DivinationPayloadProducedEvent):
            state.informational_payloads[event.payload.payload_id] = event.payload
            return
        if isinstance(event, PersistentAreaCreatedEvent):
            state.persistent_areas[event.area.area_id] = event.area
            self._rebuild_persistent_area_overlays(state)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, PersistentAreaTickedEvent):
            return
        if isinstance(event, PersistentAreaEndedEvent):
            state.persistent_areas.pop(event.area_id, None)
            self._rebuild_persistent_area_overlays(state)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, RitualCastStartedEvent):
            state.ritual_casts[event.ritual.ritual_id] = event.ritual
            return
        if isinstance(event, RitualCastCompletedEvent):
            state.ritual_casts.pop(event.ritual_id, None)
            return
        if isinstance(event, PersistentEffectEndedEvent):
            state.persistent_effects.pop(event.persistent_effect_id, None)
            state.illusions = {
                illusion_id: illusion
                for illusion_id, illusion in state.illusions.items()
                if illusion.persistent.persistent_effect_id != event.persistent_effect_id
            }
            state.informational_payloads = {
                payload_id: payload
                for payload_id, payload in state.informational_payloads.items()
                if payload.persistent.persistent_effect_id != event.persistent_effect_id
            }
            state.persistent_areas = {
                area_id: area
                for area_id, area in state.persistent_areas.items()
                if area.persistent.persistent_effect_id != event.persistent_effect_id
            }
            state.created_objects = {
                object_id: created_object
                for object_id, created_object in state.created_objects.items()
                if created_object.persistent.persistent_effect_id != event.persistent_effect_id
            }
            state.summoned_creatures = {
                summon_id: summon
                for summon_id, summon in state.summoned_creatures.items()
                if summon.persistent.persistent_effect_id != event.persistent_effect_id
            }
            return
        if isinstance(event, ConcentrationStartedEvent):
            state.actors[event.actor_id].concentrating_effect_id = event.effect_instance_id
            return
        if isinstance(event, ConcentrationEndedEvent):
            actor = state.actors[event.actor_id]
            if actor.concentrating_effect_id == event.effect_instance_id:
                actor.concentrating_effect_id = None
            return
        if isinstance(event, RelocationResolvedEvent):
            return
        if isinstance(event, FallStartedEvent):
            return
        if isinstance(event, FallDistanceComputedEvent):
            return
        if isinstance(event, FallLandedEvent):
            actor = state.actors[event.actor_id]
            old_position = actor.position
            actor.position = event.to_position
            for follow_up in self._persistent_area_transition_events(state, actor_id=event.actor_id, from_position=old_position, to_position=event.to_position):
                self._apply_event(state, follow_up)
            for follow_up in self._effect_reconciliation_events(state, actor_id=event.actor_id):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, FallDamageRolledEvent):
            state.random_counter = event.random_counter_used + 1
            return
        if isinstance(event, FallDamageAppliedEvent):
            target = state.actors[event.actor_id]
            previous_hit_points = target.current_hit_points
            previous_temp_hit_points = target.temp_hit_points
            was_at_zero_hit_points = previous_hit_points == 0
            target.current_hit_points = event.target_hit_points_after
            target.temp_hit_points = event.target_temp_hit_points_after
            self._apply_zero_hit_point_damage_followups(
                state,
                target_id=target.actor_id,
                source_actor_id=None,
                damage_type=event.damage_type,
                applied_damage_total=event.applied_damage_total,
                critical_hit=event.critical_hit,
                was_at_zero_hit_points=was_at_zero_hit_points,
                previous_hit_points=previous_hit_points,
                previous_temp_hit_points=previous_temp_hit_points,
            )
            if event.applied_damage_total > 0:
                for follow_up in self._concentration_damage_events(state, actor_id=target.actor_id, damage_total=event.applied_damage_total):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, ProneAppliedFromFallEvent):
            actor = state.actors[event.actor_id]
            if not has_condition(actor, ConditionType.PRONE):
                self._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=self._make_condition_instance(target_actor_id=actor.actor_id, condition_type=ConditionType.PRONE, source_label='fall-prone')))
            return
        if isinstance(event, SpellCastEvent):
            actor = state.actors[event.actor_id]
            actor.spell_casts_this_turn += 1
            spell_state = actor.spells[event.spell_id]
            actor.spells[event.spell_id] = replace(spell_state, remaining_uses=event.remaining_uses)
            if event.resource_pool_id is not None:
                pool = actor.resource_pools.get(event.resource_pool_id)
                if pool is None:
                    raise EncounterValidationError(f'Spell cast referenced missing resource pool {event.resource_pool_id!r}.')
                if event.resource_pool_current_after is None:
                    raise EncounterValidationError('Spell cast resource updates must include the resulting pool value.')
                pool.current = event.resource_pool_current_after
            if spell_state.level > 0:
                for follow_up in self._interrupt_rest_events(state, actor_id=actor.actor_id, reason=RestInterruptionReason.NON_CANTRIP_SPELL):
                    self._apply_event(state, follow_up)
            for follow_up in self._end_effects_on_actor_spell_cast(state, actor_id=actor.actor_id, reason='target-cast-spell'):
                self._apply_event(state, follow_up)
            if self._spell_is_harmful(spell_state):
                for follow_up in self._end_effects_on_actor_attack_or_harmful_cast(state, actor_id=actor.actor_id, reason='target-cast-harmful-spell'):
                    self._apply_event(state, follow_up)
            return
        if isinstance(event, ConditionAddedEvent):
            actor = state.actors[event.actor_id]
            source_actor = state.actors.get(event.instance.source_actor_id) if event.instance.source_actor_id is not None else None
            if source_actor is not None:
                for effect in state.active_effects.values():
                    if actor.actor_id not in effect.target_actor_ids:
                        continue
                    if event.instance.condition_type not in effect.definition.protected_condition_types:
                        continue
                    protected_types = {value.casefold() for value in effect.definition.protected_from_creature_types}
                    if protected_types and source_actor.creature_type.casefold() in protected_types:
                        return
            mutation = add_condition(actor, event.instance)
            actor.condition_instances = mutation.condition_instances
            if mutation.concentration_broken and actor.concentrating_effect_id is not None:
                self._apply_event(state, ConcentrationBrokenEvent(actor_id=actor.actor_id, effect_id=actor.concentrating_effect_id, reason=event.instance.condition_type.value))
            if event.instance.condition_type == ConditionType.UNCONSCIOUS and actor.held_item_ids:
                held_item_ids = tuple(actor.held_item_ids)
                for held_item_id in held_item_ids:
                    ground_item_id = self._next_ground_item_id(state, held_item_id)
                    self._apply_event(state, ItemDroppedEvent(actor_id=actor.actor_id, item_id=held_item_id, quantity=1, ground_item_id=ground_item_id, position=actor.position))
                    self._apply_event(state, GroundItemCreatedEvent(ground_item_id=ground_item_id, item_id=held_item_id, quantity=1, position=actor.position))
            if mutation.defeated_by_exhaustion:
                actor.current_hit_points = 0
            self._sync_movement_to_conditions(actor)
            for follow_up in self._support_reconciliation_events(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ConditionRemovedEvent):
            actor = state.actors[event.actor_id]
            removal = remove_condition(actor, condition_type=event.condition_type, instance_id=event.instance_id)
            actor.condition_instances = removal.condition_instances
            self._sync_movement_to_conditions(actor)
            for added_instance in removal.added_instances:
                self._apply_event(state, ConditionAddedEvent(actor_id=actor.actor_id, instance=added_instance))
            for follow_up in self._support_reconciliation_events(state, actor_id=actor.actor_id, reason=FallReason.STATE_CHANGE):
                self._apply_event(state, follow_up)
            for follow_up in self._visibility_reconciliation_events(state):
                self._apply_event(state, follow_up)
            return
        if isinstance(event, ConcentrationBrokenEvent):
            actor = state.actors[event.actor_id]
            actor.concentrating_effect_id = None
            for follow_up in self.effect_executor.end_active_effect(state, effect_id=event.effect_id, reason=event.reason):
                self._apply_event(state, follow_up)
            if actor.readied_action is not None and actor.readied_action.concentration_effect_id == event.effect_id and actor.readied_action.response.spell_id is not None:
                self._apply_event(state, ReadiedSpellDissipatedEvent(actor_id=actor.actor_id, spell_id=actor.readied_action.response.spell_id, reason=event.reason))
            return
        if isinstance(event, TurnEndedEvent):
            if event.round_number > state.round_number:
                state.clock_seconds += 6
            state.turn_index = state.initiative_order.index(event.next_actor_id)
            state.round_number = event.round_number
            state.active_actor_id = event.next_actor_id
            for actor_id, actor in state.actors.items():
                self._refresh_turn_resources(actor, active=(actor_id == event.next_actor_id))
            return
        if isinstance(event, EncounterCompletedEvent):
            state.phase = EncounterPhase.COMPLETE
            state.winning_side = event.winning_side
            return


    def _resolve_start_short_rest(self, state: EncounterState, intent: StartShortRestIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        self._validate_rest_start(state, actor, rest_type=RestType.SHORT)
        return [ShortRestStartedEvent(actor_id=actor.actor_id, started_at_seconds=state.clock_seconds)]

    def _resolve_start_long_rest(self, state: EncounterState, intent: StartLongRestIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        self._validate_rest_start(state, actor, rest_type=RestType.LONG)
        return [LongRestStartedEvent(actor_id=actor.actor_id, started_at_seconds=state.clock_seconds, required_rest_seconds=8 * 60 * 60)]

    def _resolve_resume_rest(self, state: EncounterState, intent: ResumeRestIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        if actor.rest_state.status != RestStateStatus.INTERRUPTED or actor.rest_state.rest_type != RestType.LONG:
            raise EncounterValidationError('Only an interrupted long rest can be resumed.')
        if actor.current_hit_points < 1:
            raise EncounterValidationError('A creature must have at least 1 HP to resume a rest.')
        return [LongRestResumedEvent(actor_id=actor.actor_id, resumed_at_seconds=state.clock_seconds, required_rest_seconds=actor.rest_state.required_rest_seconds)]

    def _resolve_spend_hit_point_die(self, state: EncounterState, intent: SpendHitPointDieIntent) -> list[object]:
        actor = self._require_actor(state, intent.actor_id)
        if state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Hit Point Dice can only be spent outside combat.')
        if intent.count <= 0:
            raise EncounterValidationError('Hit Point Die spending requires a positive count.')
        if actor.remaining_hit_dice <= 0:
            raise EncounterValidationError('The actor has no Hit Point Dice remaining.')
        if not actor.rest_state.hit_dice_window_open:
            raise EncounterValidationError('Hit Point Dice can only be spent after completing a short-rest benefit window.')
        if actor.current_hit_points >= actor.max_hit_points:
            raise EncounterValidationError('The actor is already at maximum hit points.')
        spend_count = min(intent.count, actor.remaining_hit_dice)
        events: list[object] = []
        current_hit_points = actor.current_hit_points
        remaining_hit_dice = actor.remaining_hit_dice
        random_counter = state.random_counter
        constitution_modifier = actor.ability_modifiers.get(Ability.CON, 0)
        for _ in range(spend_count):
            if current_hit_points >= actor.max_hit_points:
                break
            roll = seeded_random(self.seed, random_counter).randint(1, actor.hit_die_faces)
            healed_amount = max(1, roll + constitution_modifier)
            hit_points_after = min(actor.max_hit_points, current_hit_points + healed_amount)
            actual_recovered = hit_points_after - current_hit_points
            remaining_hit_dice -= 1
            events.append(
                HitPointDieSpentEvent(
                    actor_id=actor.actor_id,
                    die_faces=actor.hit_die_faces,
                    roll=roll,
                    constitution_modifier=constitution_modifier,
                    hit_points_gained=actual_recovered,
                    remaining_hit_dice=remaining_hit_dice,
                    random_counter_used=random_counter,
                )
            )
            events.append(
                HitPointsRecoveredFromRestEvent(
                    actor_id=actor.actor_id,
                    amount_recovered=actual_recovered,
                    current_hit_points_after=hit_points_after,
                )
            )
            current_hit_points = hit_points_after
            random_counter += 1
        if not events:
            raise EncounterValidationError('No additional Hit Point Dice can be spent right now.')
        return events

    def _resolve_advance_time(self, state: EncounterState, intent: AdvanceTimeIntent) -> list[object]:
        if intent.minutes <= 0:
            raise EncounterValidationError('Time advancement requires a positive number of minutes.')
        if state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Combat time advances through rounds and turns, not manual time advancement.')
        elapsed_seconds = intent.minutes * 60
        if intent.activity_type in {RestActivityType.QUIET, RestActivityType.LIGHT_ACTIVITY}:
            for actor in state.actors.values():
                if actor.rest_state.status != RestStateStatus.LONG_REST_IN_PROGRESS:
                    continue
                proposed_light = actor.rest_state.light_activity_seconds + elapsed_seconds
                if proposed_light > 2 * 60 * 60:
                    raise EncounterValidationError('A long rest cannot include more than 2 hours of light activity.')
        return [TimeAdvancedEvent(elapsed_seconds=elapsed_seconds, activity_type=intent.activity_type)]

    def _validate_rest_start(self, state: EncounterState, actor: RuntimeActorState, *, rest_type: RestType) -> None:
        if state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Rests cannot begin while combat is in progress.')
        if actor.is_dead:
            raise EncounterValidationError('A dead creature cannot start a rest.')
        if actor.current_hit_points < 1:
            raise EncounterValidationError('A creature must have at least 1 HP to start a rest.')
        if actor.rest_state.in_progress:
            raise EncounterValidationError('The actor is already resting.')
        if rest_type == RestType.LONG and actor.last_long_rest_completed_at_seconds is not None:
            available_at = actor.last_long_rest_completed_at_seconds + (16 * 60 * 60)
            if state.clock_seconds < available_at:
                raise EncounterValidationError('The actor must wait 16 hours after the previous long rest before starting another one.')

    def _interrupt_rest_events(self, state: EncounterState, *, actor_id: str, reason: RestInterruptionReason) -> list[object]:
        actor = self._require_actor(state, actor_id)
        rest_state = actor.rest_state
        if not rest_state.in_progress:
            return []
        if rest_state.rest_type == RestType.SHORT:
            return [
                ShortRestInterruptedEvent(
                    actor_id=actor.actor_id,
                    reason=reason,
                    accumulated_rest_seconds=rest_state.accumulated_rest_seconds,
                )
            ]
        granted_short_rest_benefits = rest_state.accumulated_rest_seconds >= (60 * 60) and not rest_state.short_rest_benefits_granted
        events: list[object] = []
        if granted_short_rest_benefits:
            events.extend(self._rest_recovery_events(state, actor.actor_id, rest_type=RestType.SHORT))
        events.append(
            LongRestInterruptedEvent(
                actor_id=actor.actor_id,
                reason=reason,
                accumulated_rest_seconds=rest_state.accumulated_rest_seconds,
                interruption_count=rest_state.interruption_count + 1,
                granted_short_rest_benefits=granted_short_rest_benefits,
            )
        )
        return events

    def _rest_recovery_events(self, state: EncounterState, actor_id: str, *, rest_type: RestType) -> list[object]:
        actor = self._require_actor(state, actor_id)
        events: list[object] = []
        for capability in actor.capabilities.values():
            if capability.remaining_uses is None or capability.max_uses is None:
                continue
            recovered = self._restored_uses(capability.remaining_uses, capability.max_uses, capability.rest_recovery, rest_type=rest_type)
            if recovered == capability.remaining_uses:
                continue
            event_cls = ItemChargesRecoveredFromRestEvent if capability.kind == CapabilityKind.ITEM else ResourceRecoveredFromRestEvent
            if event_cls is ItemChargesRecoveredFromRestEvent:
                events.append(event_cls(actor_id=actor.actor_id, resource_id=capability.option_id, amount_recovered=recovered - capability.remaining_uses, current_after=recovered, maximum=capability.max_uses))
            else:
                events.append(event_cls(actor_id=actor.actor_id, resource_id=capability.option_id, category=capability.kind.value, amount_recovered=recovered - capability.remaining_uses, current_after=recovered, maximum=capability.max_uses))
        for spell in actor.spells.values():
            if spell.remaining_uses is None or spell.max_uses is None:
                continue
            recovered = self._restored_uses(spell.remaining_uses, spell.max_uses, spell.rest_recovery, rest_type=rest_type)
            if recovered == spell.remaining_uses:
                continue
            events.append(ResourceRecoveredFromRestEvent(actor_id=actor.actor_id, resource_id=spell.option_id, category='spell', amount_recovered=recovered - spell.remaining_uses, current_after=recovered, maximum=spell.max_uses))
        for pool in actor.resource_pools.values():
            recovered = self._restored_resource_pool_current(pool.current, pool.maximum, pool.rest_recovery, rest_type=rest_type)
            if recovered == pool.current:
                continue
            if pool.category == 'spell-slot':
                events.append(SpellSlotsRecoveredFromRestEvent(actor_id=actor.actor_id, resource_id=pool.resource_id, current_after=recovered, maximum=pool.maximum))
            elif pool.category == 'item-charge':
                events.append(ItemChargesRecoveredFromRestEvent(actor_id=actor.actor_id, resource_id=pool.resource_id, amount_recovered=recovered - pool.current, current_after=recovered, maximum=pool.maximum))
            else:
                events.append(ResourceRecoveredFromRestEvent(actor_id=actor.actor_id, resource_id=pool.resource_id, category=pool.category, amount_recovered=recovered - pool.current, current_after=recovered, maximum=pool.maximum))
        return events

    def _restored_uses(self, current: int, maximum: int, spec, *, rest_type: RestType) -> int:
        rule = spec.short_rest if rest_type == RestType.SHORT else spec.long_rest
        if rule.mode == RestRecoveryMode.NONE:
            return current
        if rule.mode == RestRecoveryMode.FULL:
            return maximum
        return min(maximum, current + max(0, rule.amount))

    def _restored_resource_pool_current(self, current: int, maximum: int, spec, *, rest_type: RestType) -> int:
        return self._restored_uses(current, maximum, spec, rest_type=rest_type)

    def _effect_reconciliation_events(self, state: EncounterState, *, actor_id: str) -> list[object]:
        actor = self._require_actor(state, actor_id)
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if effect.effect_instance_id not in state.active_effects:
                continue
            if effect.source_actor_id == actor.actor_id and effect.definition.max_distance_from_source_ft is not None and effect.origin_point is not None:
                if self.battlefield_rules.get_distance3d(actor.position, effect.origin_point) > effect.definition.max_distance_from_source_ft:
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='effect-out-of-range'))
                    continue
            if actor.actor_id in effect.target_actor_ids and effect.definition.end_when_enchanted_item_not_carried and effect.definition.enchanted_item_id is not None:
                if not is_item_held(actor, effect.definition.enchanted_item_id, self.item_catalog):
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='enchanted-item-released'))
                    continue
            if actor.actor_id in effect.target_actor_ids and effect.definition.end_when_armor_equipped and actor.equipped_armor_item_id is not None:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='armor-equipped'))
                continue
            if actor.actor_id in effect.target_actor_ids and effect.definition.retaliatory_requires_temp_hit_points and actor.temp_hit_points <= 0:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='temp-hit-points-gone'))
                continue
            if effect.definition.end_when_source_effect_name_missing is not None and actor.actor_id in effect.target_actor_ids:
                if not any(
                    other.effect_instance_id != effect.effect_instance_id
                    and other.source_actor_id == effect.source_actor_id
                    and other.name == effect.definition.end_when_source_effect_name_missing
                    for other in state.active_effects.values()
                ):
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='source-effect-ended'))
                    continue
            if effect.definition.end_if_target_out_of_range_ft is not None and (actor.actor_id in effect.target_actor_ids or effect.source_actor_id == actor.actor_id):
                source = state.actors.get(effect.source_actor_id)
                if source is not None:
                    if any(
                        self.battlefield_rules.get_distance3d(source.position, state.actors[target_id].position) > effect.definition.end_if_target_out_of_range_ft
                        for target_id in effect.target_actor_ids
                        if target_id in state.actors
                    ):
                        events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='target-out-of-range'))
                        continue
            if effect.definition.end_if_target_has_total_cover and (actor.actor_id in effect.target_actor_ids or effect.source_actor_id == actor.actor_id):
                source = state.actors.get(effect.source_actor_id)
                if source is not None:
                    if any(
                        self.battlefield_rules.get_cover(state, source, state.actors[target_id]) == CoverLevel.TOTAL
                        for target_id in effect.target_actor_ids
                        if target_id in state.actors
                    ):
                        events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='target-total-cover'))
                        continue
        for summon in tuple(state.summoned_creatures.values()):
            if summon.linked_actor_id is None:
                continue
            summon_actor = state.actors.get(summon.linked_actor_id)
            if summon_actor is None:
                continue
            if summon_actor.current_hit_points <= 0:
                source_effect = state.active_effects.get(summon.persistent.source_effect_id)
                if source_effect is not None:
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=source_effect.effect_instance_id, reason='summoned-creature-dropped-to-zero'))
                else:
                    events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason='summoned-creature-dropped-to-zero'))
        events.extend(self._shared_senses_reconciliation_events(state, actor_id=actor.actor_id))
        events.extend(self._floating_disk_follow_events(state, owner_actor_id=actor.actor_id))
        return events

    def _matching_monster_id(self, name: str) -> str | None:
        runtime = self.monster_runtime
        if runtime is None:
            return None
        target = slugify(name)
        preferred: str | None = None
        fallback: str | None = None
        for monster_id, record in runtime.monster_catalog.monsters.items():
            if target not in {slugify(record.record_id), slugify(record.name)}:
                continue
            if record.source == 'XMM':
                preferred = monster_id
                break
            if fallback is None:
                fallback = monster_id
        return preferred or fallback

    def _build_summoned_actor(self, state: EncounterState, summon) -> RuntimeActorState | None:
        if summon.linked_actor_id is not None:
            return state.actors.get(summon.linked_actor_id)
        tags = set(summon.definition.semantic_tags)
        source_actor = state.actors[summon.persistent.source_actor_id]
        source_effect = state.active_effects.get(summon.persistent.source_effect_id)
        metadata = {} if source_effect is None else dict(source_effect.metadata)
        actor_id = f'{summon.summon_id}:actor'
        if 'familiar' in tags:
            monster_id = self._matching_monster_id(summon.definition.statblock_reference or summon.definition.summon_name)
            if monster_id is None or self.monster_runtime is None:
                raise EncounterValidationError('Find Familiar could not locate the requested beast form in the local monster catalog.')
            actor = self.monster_runtime.compile_monster(monster_id=monster_id, actor_id=actor_id, position=summon.position)
            actor.side = source_actor.side
            actor.name = f"{source_actor.name}'s Familiar ({summon.definition.summon_name.title()})"
            actor.creature_type = (metadata.get('type', 'celestial').strip().lower() or 'celestial')
            actor.summon_owner_actor_id = source_actor.actor_id
            actor.shared_sense_owner_actor_id = source_actor.actor_id
            actor.attacks = {}
            actor.capabilities = {}
            actor.spells = {}
            actor.resource_pools = {}
            actor.remaining_movement_ft = actor.speed_ft
            return actor
        def _scores(str_score: int, dex_score: int, con_score: int, int_score: int, wis_score: int, cha_score: int):
            scores = {
                Ability.STR: str_score,
                Ability.DEX: dex_score,
                Ability.CON: con_score,
                Ability.INT: int_score,
                Ability.WIS: wis_score,
                Ability.CHA: cha_score,
            }
            modifiers = {ability: (score - 10) // 2 for ability, score in scores.items()}
            return scores, modifiers
        if 'unseen-servant' in tags:
            scores, modifiers = _scores(2, 10, 10, 1, 10, 1)
            return RuntimeActorState(
                actor_id=actor_id,
                name='Unseen Servant',
                side=source_actor.side,
                source_refs=('XPHB', 'spell:unseen-servant'),
                size='M',
                alignment=None,
                creature_type='force',
                armor_class=10,
                max_hit_points=1,
                current_hit_points=1,
                position=summon.position,
                speed_ft=15,
                climb_speed_ft=0,
                summon_owner_actor_id=source_actor.actor_id,
                remaining_movement_ft=15,
                initiative_bonus=modifiers[Ability.DEX],
                proficiency_bonus=2,
                passive_perception=10,
                ability_scores=scores,
                ability_modifiers=modifiers,
                saving_throw_bonuses=dict(modifiers),
                skill_bonuses={},
                attacks={},
                spells={},
                capabilities={},
            )
        if 'floating-disk' in tags:
            scores, modifiers = _scores(10, 10, 10, 1, 10, 1)
            return RuntimeActorState(
                actor_id=actor_id,
                name="Tenser's Floating Disk",
                side=source_actor.side,
                source_refs=('XPHB', 'spell:tenser-s-floating-disk'),
                size='M',
                alignment=None,
                creature_type='force',
                armor_class=10,
                max_hit_points=1,
                current_hit_points=1,
                position=summon.position,
                speed_ft=20,
                climb_speed_ft=0,
                summon_owner_actor_id=source_actor.actor_id,
                occupied_height_ft=1,
                remaining_movement_ft=20,
                initiative_bonus=modifiers[Ability.DEX],
                proficiency_bonus=2,
                passive_perception=10,
                ability_scores=scores,
                ability_modifiers=modifiers,
                saving_throw_bonuses=dict(modifiers),
                skill_bonuses={},
                attacks={},
                spells={},
                capabilities={},
            )
        return None

    def _step_position_toward(self, start: GridPosition, target: GridPosition, *, steps: int) -> GridPosition:
        x, y, z = start.x, start.y, start.z
        remaining = max(0, steps)
        while remaining > 0 and (x, y, z) != (target.x, target.y, target.z):
            if x < target.x:
                x += 1
            elif x > target.x:
                x -= 1
            elif y < target.y:
                y += 1
            elif y > target.y:
                y -= 1
            elif z < target.z:
                z += 5
            elif z > target.z:
                z -= 5
            remaining -= 1
        return GridPosition(x, y, z)

    def _floating_disk_load_limit_events(self, state: EncounterState, *, disk_actor_id: str, reason: str) -> list[object]:
        events: list[object] = []
        summon = next((summon for summon in state.summoned_creatures.values() if summon.linked_actor_id == disk_actor_id and 'floating-disk' in set(summon.definition.semantic_tags)), None)
        if summon is None:
            return events
        if supported_actor_weight_lb(state, disk_actor_id, self.item_catalog) <= 500:
            return events
        source_effect = state.active_effects.get(summon.persistent.source_effect_id)
        if source_effect is not None:
            events.extend(self.effect_executor.end_active_effect(state, effect_id=source_effect.effect_instance_id, reason=reason))
        else:
            events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason=reason))
        return events

    def _shared_senses_reconciliation_events(self, state: EncounterState, *, actor_id: str) -> list[object]:
        events: list[object] = []
        owner_ids: set[str] = set()
        actor = state.actors.get(actor_id)
        if actor is not None and actor.shared_senses_actor_id is not None:
            owner_ids.add(actor.actor_id)
        for owner in state.actors.values():
            if owner.shared_senses_actor_id == actor_id:
                owner_ids.add(owner.actor_id)
        for owner_id in owner_ids:
            owner = state.actors.get(owner_id)
            if owner is None or owner.shared_senses_actor_id is None:
                continue
            familiar = state.actors.get(owner.shared_senses_actor_id)
            reason = None
            if familiar is None:
                reason = 'familiar-missing'
            elif familiar.summon_owner_actor_id != owner.actor_id or familiar.shared_sense_owner_actor_id != owner.actor_id:
                reason = 'familiar-link-broken'
            elif not familiar.is_conscious:
                reason = 'familiar-unconscious'
            elif self.battlefield_rules.get_distance3d(owner.position, familiar.position) > 100:
                reason = 'familiar-out-of-range'
            if reason is not None:
                events.append(SharedSensesEndedEvent(actor_id=owner.actor_id, familiar_actor_id=owner.shared_senses_actor_id, reason=reason))
        return events

    def _floating_disk_follow_events(self, state: EncounterState, *, owner_actor_id: str) -> list[object]:
        events: list[object] = []
        owner = state.actors.get(owner_actor_id)
        if owner is None:
            return events
        for summon in state.summoned_creatures.values():
            if summon.persistent.source_actor_id != owner_actor_id or summon.linked_actor_id is None:
                continue
            if 'floating-disk' not in set(summon.definition.semantic_tags):
                continue
            disk = state.actors.get(summon.linked_actor_id)
            if disk is None:
                continue
            if supported_actor_weight_lb(state, disk.actor_id, self.item_catalog) > 500:
                source_effect = state.active_effects.get(summon.persistent.source_effect_id)
                if source_effect is not None:
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=source_effect.effect_instance_id, reason='floating-disk-overloaded'))
                else:
                    events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason='floating-disk-overloaded'))
                continue
            distance_ft = self.battlefield_rules.get_distance3d(owner.position, disk.position)
            if distance_ft > 100:
                source_effect = state.active_effects.get(summon.persistent.source_effect_id)
                if source_effect is not None:
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=source_effect.effect_instance_id, reason='floating-disk-out-of-range'))
                else:
                    events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason='floating-disk-out-of-range'))
                continue
            if distance_ft <= 20:
                continue
            if abs(owner.position.z - disk.position.z) > 10:
                source_effect = state.active_effects.get(summon.persistent.source_effect_id)
                if source_effect is not None:
                    events.extend(self.effect_executor.end_active_effect(state, effect_id=source_effect.effect_instance_id, reason='floating-disk-elevation-limit'))
                else:
                    events.append(CreatedCreatureRemovedEvent(summon_id=summon.summon_id, reason='floating-disk-elevation-limit'))
                continue
            move_ft = min(20, max(0, distance_ft - 20))
            steps = max(1, (move_ft + 4) // 5)
            destination = self._step_position_toward(disk.position, owner.position, steps=steps)
            if destination == disk.position:
                continue
            travel_ft = self.battlefield_rules.get_distance3d(disk.position, destination)
            events.append(MovementSpentEvent(actor_id=disk.actor_id, from_position=disk.position, to_position=destination, distance_ft=travel_ft, remaining_movement_ft=disk.remaining_movement_ft, movement_mode=TraversalMode.WALK, movement_spent_ft=disk.movement_spent_ft, consume_turn_movement=False))
        return events

    def _named_effects_on_actor(self, state: EncounterState, *, actor_id: str, names: tuple[str, ...]) -> tuple[ActiveEffectState, ...]:
        return tuple(
            effect
            for effect in state.active_effects.values()
            if actor_id in effect.target_actor_ids and effect.name in names
        )

    def _sleep_end_events(self, state: EncounterState, *, actor_id: str, reason: str) -> list[object]:
        events: list[object] = []
        for effect in self._named_effects_on_actor(state, actor_id=actor_id, names=('Sleep', 'Sleep (Drowsy)')):
            events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason=reason))
        return events

    def _hideous_laughter_damage_events(self, state: EncounterState, *, actor_id: str) -> list[object]:
        events: list[object] = []
        for effect in self._named_effects_on_actor(state, actor_id=actor_id, names=("Tasha's Hideous Laughter",)):
            source = state.actors.get(effect.source_actor_id)
            if source is None:
                continue
            request = SaveRequest(
                context=ResolutionContext(
                    effect_id=effect.effect_instance_id,
                    source_actor_id=effect.source_actor_id,
                    target_actor_id=actor_id,
                    reason="Tasha's Hideous Laughter damage save",
                ),
                ability=Ability.WIS,
                dc=source.spell_save_dc,
                roll_mode=D20RollMode.ADVANTAGE,
            )
            resolution, save_events = self.resolve_save_consumer(state, request, apply=False)
            events.extend(save_events)
            if resolution.branch.value == 'success':
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='tasha-damage-save-success'))
        return events

    def _friends_end_events_for_attack(self, state: EncounterState, *, actor_id: str) -> list[object]:
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if effect.name == 'Friends' and effect.source_actor_id == actor_id:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='friends-broken-attack'))
        return events

    def _friends_end_events_for_damage(self, state: EncounterState, *, target_id: str, source_actor_id: str | None) -> list[object]:
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if effect.name != 'Friends':
                continue
            if target_id in effect.target_actor_ids or (source_actor_id is not None and effect.source_actor_id == source_actor_id):
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='friends-broken-damage'))
        return events

    def _friends_end_events_for_save(self, state: EncounterState, *, source_actor_id: str | None, target_actor_id: str | None) -> list[object]:
        if source_actor_id is None or target_actor_id is None or source_actor_id == target_actor_id:
            return []
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if effect.name == 'Friends' and effect.source_actor_id == source_actor_id:
                events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='friends-broken-save'))
        return events

    def _end_effects_on_source_side_damage(self, state: EncounterState, *, target_id: str, source_actor_id: str | None) -> list[object]:
        if source_actor_id is None:
            return []
        source_actor = state.actors.get(source_actor_id)
        if source_actor is None:
            return []
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if target_id not in effect.target_actor_ids or not effect.definition.end_on_damage_from_source_side:
                continue
            effect_source = state.actors.get(effect.source_actor_id)
            if effect_source is None or effect_source.side != source_actor.side:
                continue
            events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason='source-side-damage'))
        return events

    def _end_effects_on_actor_deal_damage(self, state: EncounterState, *, actor_id: str, reason: str) -> list[object]:
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if actor_id not in effect.target_actor_ids or not effect.definition.end_when_target_deals_damage:
                continue
            events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason=reason))
        return events

    def _end_effects_on_actor_spell_cast(self, state: EncounterState, *, actor_id: str, reason: str) -> list[object]:
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if actor_id not in effect.target_actor_ids or not effect.definition.end_when_target_casts_spell:
                continue
            events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason=reason))
        return events

    def _end_effects_on_actor_attack_or_harmful_cast(self, state: EncounterState, *, actor_id: str, reason: str) -> list[object]:
        events: list[object] = []
        for effect in tuple(state.active_effects.values()):
            if actor_id not in effect.target_actor_ids or not effect.definition.end_when_target_attacks_or_harmful_casts:
                continue
            events.extend(self.effect_executor.end_active_effect(state, effect_id=effect.effect_instance_id, reason=reason))
        return events

    def _restore_actor_base_state_for_long_rest(self, actor: RuntimeActorState, *, active_effects: dict[str, ActiveEffectState] | None = None) -> None:
        actor.ability_scores = dict(actor.base_ability_scores)
        actor.ability_modifiers = dict(actor.base_ability_modifiers)
        actor.saving_throw_bonuses = dict(actor.base_saving_throw_bonuses)
        actor.skill_bonuses = dict(actor.base_skill_bonuses)
        if actor.base_initiative_bonus is not None:
            actor.initiative_bonus = actor.base_initiative_bonus
        if actor.base_passive_perception is not None:
            actor.passive_perception = actor.base_passive_perception
        refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=active_effects)
        self._sync_movement_to_conditions(actor)

    def _time_advance_followup_events(self, state: EncounterState, *, actor_id: str, elapsed_seconds: int, activity_type: RestActivityType) -> list[object]:
        actor = self._require_actor(state, actor_id)
        rest_state = actor.rest_state
        if not rest_state.in_progress:
            return []
        if rest_state.rest_type == RestType.SHORT:
            if activity_type == RestActivityType.EXERTION:
                return self._interrupt_rest_events(state, actor_id=actor_id, reason=RestInterruptionReason.EXERTION)
            actor.rest_state = replace(
                rest_state,
                accumulated_rest_seconds=rest_state.accumulated_rest_seconds + elapsed_seconds,
            )
            if actor.rest_state.accumulated_rest_seconds >= 60 * 60:
                events: list[object] = [ShortRestCompletedEvent(actor_id=actor.actor_id, completed_at_seconds=state.clock_seconds)]
                events.extend(self._rest_recovery_events(state, actor.actor_id, rest_type=RestType.SHORT))
                return events
            return []
        if activity_type == RestActivityType.EXERTION:
            actor.rest_state = replace(rest_state, exertion_seconds=rest_state.exertion_seconds + elapsed_seconds)
            if actor.rest_state.exertion_seconds >= 60 * 60:
                return self._interrupt_rest_events(state, actor_id=actor_id, reason=RestInterruptionReason.EXERTION)
            return []
        light_added = elapsed_seconds if activity_type in {RestActivityType.QUIET, RestActivityType.LIGHT_ACTIVITY} else 0
        sleep_added = elapsed_seconds if activity_type == RestActivityType.SLEEP else 0
        actor.rest_state = replace(
            rest_state,
            accumulated_rest_seconds=rest_state.accumulated_rest_seconds + elapsed_seconds,
            sleep_seconds=rest_state.sleep_seconds + sleep_added,
            light_activity_seconds=rest_state.light_activity_seconds + light_added,
            exertion_seconds=0,
        )
        if (
            actor.rest_state.accumulated_rest_seconds >= actor.rest_state.required_rest_seconds
            and actor.rest_state.sleep_seconds >= 6 * 60 * 60
            and actor.rest_state.light_activity_seconds <= 2 * 60 * 60
        ):
            events = [LongRestCompletedEvent(actor_id=actor.actor_id, completed_at_seconds=state.clock_seconds)]
            if actor.current_hit_points < actor.max_hit_points:
                events.append(HitPointsRecoveredFromRestEvent(actor_id=actor.actor_id, amount_recovered=actor.max_hit_points - actor.current_hit_points, current_hit_points_after=actor.max_hit_points))
            if actor.remaining_hit_dice < actor.total_hit_dice:
                events.append(HitPointDiceRestoredEvent(actor_id=actor.actor_id, remaining_hit_dice=actor.total_hit_dice))
            exhaustion_level = get_condition_state(actor).exhaustion_level
            if exhaustion_level > 0:
                events.append(self._condition_removed_event_for_type(actor.actor_id, ConditionType.EXHAUSTION))
                events.append(ExhaustionReducedFromRestEvent(actor_id=actor.actor_id, exhaustion_level_after=exhaustion_level - 1))
            events.extend(self._rest_recovery_events(state, actor.actor_id, rest_type=RestType.LONG))
            events.append(RestLockoutAppliedEvent(actor_id=actor.actor_id, available_at_seconds=state.clock_seconds + (16 * 60 * 60)))
            return events
        return []

    def _require_active_actor(self, state: EncounterState, actor_id: str) -> RuntimeActorState:
        if state.phase != EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Encounter is not in a valid phase for actor actions.')
        actor = state.actors.get(actor_id)
        if actor is None:
            raise EncounterValidationError('Unknown actor.')
        if state.active_actor_id != actor_id:
            raise EncounterValidationError('Only the active actor may act.')
        return actor

    def _require_actor(self, state: EncounterState, actor_id: str) -> RuntimeActorState:
        actor = state.actors.get(actor_id)
        if actor is None:
            raise EncounterValidationError('Unknown actor.')
        return actor

    def _require_target(self, state: EncounterState, actor_id: str) -> RuntimeActorState:
        actor = state.actors.get(actor_id)
        if actor is None:
            raise EncounterValidationError('Unknown target actor.')
        return actor

    def _require_conscious(self, actor: RuntimeActorState) -> None:
        if not actor.is_conscious:
            raise EncounterValidationError('The actor must be conscious to use this combat option.')

    def _spell_reveals_hidden(self, spell: RuntimeSpellState) -> bool:
        profile = spell.perceptibility
        if profile.effect_visible or profile.effect_audible:
            return True
        if profile.componentless_casting:
            return False
        return any(
            (
                profile.has_verbal_component,
                profile.has_somatic_component,
                profile.has_material_component,
                profile.casting_visual_manifestation,
                profile.casting_auditory_manifestation,
            )
        )

    def _require_action_permission(self, actor: RuntimeActorState) -> None:
        if not actor.action_available:
            raise EncounterValidationError('The actor has already used its action this turn.')
        if not can_take_actions(actor):
            raise EncounterValidationError('The actor cannot take actions because of its current conditions.')

    def _require_bonus_action_permission(self, actor: RuntimeActorState) -> None:
        if not actor.bonus_action_available:
            raise EncounterValidationError('The actor has already used its bonus action this turn.')
        if not can_take_bonus_actions(actor):
            raise EncounterValidationError('The actor cannot take bonus actions because of its current conditions.')

    def _require_reaction_permission(self, actor: RuntimeActorState) -> None:
        if not actor.reaction_available:
            raise EncounterValidationError('The actor has already used its reaction.')
        if not can_take_reactions(actor):
            raise EncounterValidationError('The actor cannot take reactions because of its current conditions.')

    def _actor_counts_as_surviving(self, actor: RuntimeActorState) -> bool:
        return actor.current_hit_points > 0 or (actor.uses_death_saves and actor.dying_state.status != DyingStateStatus.DEAD)

    def _next_active_actor(self, state: EncounterState) -> tuple[str, int]:
        if not state.initiative_order:
            raise EncounterValidationError('Encounter initiative has not been established.')
        current_index = state.initiative_order.index(state.active_actor_id)
        round_number = state.round_number
        for step in range(1, len(state.initiative_order) + 1):
            next_index = (current_index + step) % len(state.initiative_order)
            if next_index <= current_index:
                round_number = state.round_number + 1
            next_actor_id = state.initiative_order[next_index]
            if state.actors[next_actor_id].is_turn_eligible:
                return next_actor_id, round_number
        raise EncounterValidationError('No living or dying actors remain to take a turn.')

    def _refresh_turn_resources(self, actor: RuntimeActorState, *, active: bool) -> None:
        if active:
            actor.movement_spent_ft = 0
            actor.dash_bonus_ft = 0
            actor.remaining_movement_ft = self.battlefield_rules.max_remaining_movement_ft(actor)
            actor.action_available = True
            actor.bonus_action_available = True
            actor.reaction_available = True
            actor.remaining_free_object_interaction = True
            actor.dodge_active = False
            actor.disengage_active = False
            actor.help_target_id = None
            actor.spell_casts_this_turn = 0
            actor.loading_spent_resources = frozenset()

    def _capability_action_type(self, kind) -> CombatActionType:
        if kind == CapabilityKind.ITEM:
            return CombatActionType.ITEM
        return CombatActionType.FEATURE

    def _resolve_capability_recharge_events(self, state: EncounterState, *, actor_id: str) -> list[object]:
        actor = self._require_actor(state, actor_id)
        events: list[object] = []
        for capability in actor.capabilities.values():
            if capability.recharge_min_roll is None or capability.remaining_uses != 0:
                continue
            roll = seeded_random(self.seed, state.random_counter).randint(1, 6)
            event = CapabilityRechargeRolledEvent(
                actor_id=actor.actor_id,
                capability_id=capability.option_id,
                roll=roll,
                recharge_min_roll=capability.recharge_min_roll,
                recharged=(roll >= capability.recharge_min_roll),
                random_counter_used=state.random_counter,
            )
            events.append(event)
            self._apply_event(state, event)
        return events

    def _active_effect_actor_ids(self, effect) -> tuple[str, ...]:
        actor_ids = list(effect.target_actor_ids or (effect.source_actor_id,))
        metadata = dict(effect.metadata)
        marked_target_id = metadata.get('marked-target-id')
        if isinstance(marked_target_id, str) and marked_target_id:
            actor_ids.append(marked_target_id)
        return tuple(dict.fromkeys(actor_ids))

    def _recompute_actor_effect_modifiers(self, state: EncounterState, actor_id: str) -> None:
        actor = state.actors[actor_id]
        damage_resistances = set(actor.base_damage_resistances)
        condition_immunities = set(actor.base_condition_immunities)
        ability_advantages: set[Ability] = set()
        ability_disadvantages: set[Ability] = set()
        saving_advantages: set[Ability] = set()
        melee_attack_damage_bonus = 0
        armor_class_minimum = 0
        cannot_cast_spells = False
        cannot_take_reactions = False
        can_dash_as_bonus_action = False
        understand_all_languages = False
        can_communicate_with_beasts = False
        darkvision_radius_ft = 0
        blindsight_radius_ft = 0
        truesight_radius_ft = 0
        fall_speed_override_ft: int | None = None
        prevent_falling_damage = False
        speed_override_ft: int | None = None
        speed_bonus_ft = 0
        speed_penalty_ft = 0
        jump_replacement_distance_ft = 0
        jump_replacement_movement_cost_ft = 0
        for effect in state.active_effects.values():
            metadata = dict(effect.metadata)
            actor_is_direct_target = actor_id in effect.target_actor_ids
            actor_is_marked_target = metadata.get('marked-target-id') == actor_id
            if not actor_is_direct_target and not actor_is_marked_target:
                continue
            if actor_is_direct_target:
                damage_resistances.update(effect.definition.damage_resistances)
                condition_immunities.update(effect.definition.granted_condition_immunities)
                ability_advantages.update(effect.definition.ability_check_advantage_abilities)
                mapped_ability = metadata.get(f'ability-advantage:{actor_id}')
                if isinstance(mapped_ability, str) and mapped_ability:
                    normalized_ability = mapped_ability.strip().upper()
                    try:
                        ability_advantages.add(Ability(normalized_ability))
                    except ValueError:
                        pass
                saving_advantages.update(effect.definition.saving_throw_advantage_abilities)
                armor_class_minimum = max(armor_class_minimum, effect.definition.armor_class_minimum)
                melee_attack_damage_bonus += effect.definition.melee_attack_damage_bonus
                cannot_cast_spells = cannot_cast_spells or effect.definition.cannot_cast_spells
                cannot_take_reactions = cannot_take_reactions or effect.definition.cannot_take_reactions
                can_dash_as_bonus_action = can_dash_as_bonus_action or effect.definition.can_dash_as_bonus_action
                understand_all_languages = understand_all_languages or effect.definition.understand_all_languages
                can_communicate_with_beasts = can_communicate_with_beasts or effect.definition.can_communicate_with_beasts
                darkvision_radius_ft = max(darkvision_radius_ft, effect.definition.darkvision_radius_ft)
                blindsight_radius_ft = max(blindsight_radius_ft, effect.definition.blindsight_radius_ft)
                truesight_radius_ft = max(truesight_radius_ft, effect.definition.truesight_radius_ft)
                prevent_falling_damage = prevent_falling_damage or effect.definition.prevent_falling_damage
                if effect.definition.fall_speed_override_ft is not None:
                    fall_speed_override_ft = effect.definition.fall_speed_override_ft if fall_speed_override_ft is None else min(fall_speed_override_ft, effect.definition.fall_speed_override_ft)
                speed_bonus_ft += effect.definition.speed_bonus_ft
                speed_penalty_ft += effect.definition.speed_penalty_ft
                jump_replacement_distance_ft = max(jump_replacement_distance_ft, effect.definition.jump_replacement_distance_ft)
                if effect.definition.jump_replacement_movement_cost_ft > 0:
                    if jump_replacement_movement_cost_ft == 0:
                        jump_replacement_movement_cost_ft = effect.definition.jump_replacement_movement_cost_ft
                    else:
                        jump_replacement_movement_cost_ft = min(jump_replacement_movement_cost_ft, effect.definition.jump_replacement_movement_cost_ft)
                if effect.definition.speed_override_ft is not None:
                    speed_override_ft = effect.definition.speed_override_ft if speed_override_ft is None else min(speed_override_ft, effect.definition.speed_override_ft)
            if actor_is_direct_target or actor_is_marked_target:
                ability_disadvantages.update(effect.definition.ability_check_disadvantage_abilities)
        if speed_penalty_ft > 0:
            penalized_speed = max(0, actor.speed_ft + speed_bonus_ft - speed_penalty_ft)
            speed_override_ft = penalized_speed if speed_override_ft is None else min(speed_override_ft, penalized_speed)
        actor.damage_resistances = frozenset(damage_resistances)
        actor.condition_immunities = frozenset(condition_immunities)
        actor.granted_condition_immunities = frozenset(condition_immunities.difference(actor.base_condition_immunities))
        actor.ability_check_advantage_abilities = frozenset(ability_advantages)
        actor.ability_check_disadvantage_abilities = frozenset(ability_disadvantages)
        actor.saving_throw_advantage_abilities = frozenset(saving_advantages)
        actor.melee_attack_damage_bonus = melee_attack_damage_bonus
        actor.armor_class_minimum = armor_class_minimum
        actor.cannot_cast_spells = cannot_cast_spells
        actor.cannot_take_reactions = cannot_take_reactions
        actor.can_dash_as_bonus_action = can_dash_as_bonus_action
        actor.understand_all_languages = understand_all_languages
        actor.can_communicate_with_beasts = can_communicate_with_beasts
        actor.darkvision_radius_ft = darkvision_radius_ft
        actor.blindsight_radius_ft = blindsight_radius_ft
        actor.truesight_radius_ft = truesight_radius_ft
        actor.fall_speed_override_ft = fall_speed_override_ft
        actor.prevent_falling_damage = prevent_falling_damage
        actor.speed_override_ft = speed_override_ft
        actor.speed_bonus_ft = speed_bonus_ft
        actor.jump_replacement_distance_ft = jump_replacement_distance_ft
        actor.jump_replacement_movement_cost_ft = jump_replacement_movement_cost_ft
        refresh_actor_equipment_state(actor, self.item_catalog, unarmed_attack=actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor), active_effects=state.active_effects)
        self._sync_movement_to_conditions(actor)
        if actor.cannot_cast_spells and actor.concentrating_effect_id is not None:
            self._apply_event(state, ConcentrationBrokenEvent(actor_id=actor.actor_id, effect_id=actor.concentrating_effect_id, reason='cannot-cast-spells'))

    def _terrain_hazard_events_for_destination(self, state: EncounterState, *, actor_id: str, from_position: GridPosition, to_position: GridPosition) -> list[object]:
        actor = self._require_actor(state, actor_id)
        events: list[object] = []
        for feature_id in state.battlefield.dynamic_feature_ids:
            feature = state.battlefield.features.get(feature_id)
            if feature is None:
                continue
            tags = {tag.lower() for tag in feature.tags}
            if 'ball-bearings' not in tags:
                continue
            if to_position not in feature.cells or from_position in feature.cells:
                continue
            request = HazardResolutionRequest(
                context=ResolutionContext(effect_id=feature_id, source_actor_id=None, target_actor_id=actor.actor_id, reason='Ball Bearings'),
                save_request=SaveRequest(
                    context=ResolutionContext(effect_id=feature_id, source_actor_id=None, target_actor_id=actor.actor_id, reason='Ball Bearings'),
                    ability=Ability.DEX,
                    dc=10,
                ),
                failure_outcome=EffectOutcome(
                    conditions=(ConditionApplication(condition_type=ConditionType.PRONE, source_label='ball-bearings', source_effect_id=feature_id),),
                ),
            )
            _, hazard_events = self.resolve_hazard(state, request, apply=False)
            events.extend(hazard_events)
        return events

    def _fall_deals_damage(self, actor: RuntimeActorState, damage_total: int) -> bool:
        return apply_damage_modifiers(actor, damage_total, 'bludgeoning').final_damage > 0

    def _sync_movement_to_conditions(self, actor: RuntimeActorState) -> None:
        if get_effective_speed(actor) <= 0 and actor.fly_speed_ft <= 0 and actor.climb_speed_ft <= 0 and actor.swim_speed_ft <= 0:
            actor.remaining_movement_ft = 0
        else:
            actor.remaining_movement_ft = max(0, self.battlefield_rules.max_remaining_movement_ft(actor))

    def _spell_relocation_effect(self, spell) -> RelocationEffect | None:
        if spell.effect_type == SpellEffectType.MISTY_STEP:
            return RelocationEffect(
                relocation_type=RelocationType.TELEPORT,
                movement_mode=TraversalMode.TELEPORT,
                range_ft=spell.range_ft,
                requires_visible_destination=True,
                requires_unoccupied_destination=True,
                requires_line_of_effect=False,
                consumes_movement=False,
            )
        return None

    def _remaining_after_spent(self, actor: RuntimeActorState, spent_total: int) -> int:
        return max(0, max(
            self.battlefield_rules.speed_budget_for_mode(actor, TraversalMode.WALK).total_budget_ft - spent_total,
            self.battlefield_rules.speed_budget_for_mode(actor, TraversalMode.CLIMB).total_budget_ft - spent_total,
            self.battlefield_rules.speed_budget_for_mode(actor, TraversalMode.SWIM).total_budget_ft - spent_total,
            self.battlefield_rules.speed_budget_for_mode(actor, TraversalMode.FLY).total_budget_ft - spent_total,
        ))

    def _starting_movement_spent(self, actor: RuntimeActorState) -> int:
        return max(actor.movement_spent_ft, max(0, actor.max_path_speed_ft - actor.remaining_movement_ft))

    def _resolve_path_budget(self, state: EncounterState, actor: RuntimeActorState, plan) -> tuple[int, int, TraversalMode, int]:
        spent_total = self._starting_movement_spent(actor)
        total_cost = 0
        last_mode = TraversalMode.WALK
        dragging = bool(get_dragged_targets(state, actor.actor_id))
        for segment in plan.segments:
            segment_mode = segment.traversal_mode
            segment_cost = segment.movement_cost_ft
            if segment_mode == TraversalMode.WALK and has_condition(actor, ConditionType.PRONE):
                segment_mode = TraversalMode.CRAWL
                segment_cost *= 2
            if dragging:
                segment_cost *= 2
            spent_total += segment_cost
            total_cost += segment_cost
            budget = self.battlefield_rules.speed_budget_for_mode(actor, segment_mode)
            if spent_total > budget.total_budget_ft:
                raise EncounterValidationError(f'The {segment_mode.value} path requires {spent_total} ft of movement, but the actor has only {budget.total_budget_ft} ft available for that mode this turn.')
            last_mode = segment_mode
        return total_cost, self._remaining_after_spent(actor, spent_total), last_mode, spent_total

    def _step_away(self, target_value: int, actor_value: int) -> int:
        if target_value > actor_value:
            return 1
        if target_value < actor_value:
            return -1
        return 1

    def _condition_added_event_from_application(self, *, target_actor_id: str, application: ConditionApplication):
        return ConditionAddedEvent(
            actor_id=target_actor_id,
            instance=self._make_condition_instance(
                target_actor_id=target_actor_id,
                condition_type=application.condition_type,
                source_actor_id=application.source_actor_id,
                source_effect_id=application.source_effect_id,
                source_label=application.source_label,
                charmer_actor_id=application.charmer_actor_id,
                fear_source_actor_id=application.fear_source_actor_id,
            ),
        )

    def _make_condition_instance(self, *, target_actor_id: str, condition_type: ConditionType, source_actor_id: str | None = None, source_effect_id: str | None = None, source_label: str | None = None, charmer_actor_id: str | None = None, fear_source_actor_id: str | None = None, grappler_actor_id: str | None = None) -> ConditionInstance:
        source_token = source_effect_id or source_label or condition_type.value
        return ConditionInstance(
            instance_id=f'{target_actor_id}:{condition_type.value}:{source_actor_id or "none"}:{source_token}:{len(source_token)}',
            condition_type=condition_type,
            source_actor_id=source_actor_id,
            source_effect_id=source_effect_id,
            source_label=source_label,
            charmer_actor_id=charmer_actor_id,
            fear_source_actor_id=fear_source_actor_id,
            grappler_actor_id=grappler_actor_id,
        )







































