from __future__ import annotations

from dataclasses import dataclass

from rules_engine.encounter_math import roll_damage
from rules_engine.rng import seeded_random
from shared_types.adjudication import (
    ActionCostRecommendation,
    ActionCostType,
    AdjudicationBranch,
    AdjudicationCheckRequest,
    AdjudicationIllusionSpec,
    AdjudicationModeSwitchRecommendation,
    AdjudicationOperation,
    AdjudicationOperationType,
    AdjudicationPlan,
    AdjudicationType,
    ContestParticipantRequest,
    ContestTieRule,
    PendingAdjudicationResolutionState,
)
from shared_types.battlefield import CoverLevel, RelocationType, TraversalMode
from shared_types.capabilities import ActiveEffectDefinition, CapabilityDefinition, CapabilityKind, DurationSpec, EffectDurationType, IllusionActualProperties, IllusionApparentProperties, IllusionDefinition, IllusionModality, IllusionRevealPolicy, IllusionSubtype, PersistentObserverFilter, PersistentObserverMode, StartActiveEffectDef, TargetSelectionKind, TargetingSpec
from shared_types.effects import (
    CheckRequest,
    ConditionApplication,
    DamageEffect,
    EffectOutcome,
    EffectResolutionBranch,
    ForcedMovementEffect,
    ForcedMovementMode,
    HazardResolutionRequest,
    ResolutionContext,
    SaveRequest,
)
from shared_types.encounter_events import (
    AdjudicatedActionResolvedEvent,
    CoverStateModifiedEvent,
    DMCheckIssuedEvent,
    DMContestIssuedEvent,
    DMModeSwitchRecommendedEvent,
    DMSaveIssuedEvent,
    DamageAppliedEvent,
    DamageRolledEvent,
    HealingAppliedEvent,
    ImprovisedObjectCreatedEvent,
    ImprovisedObjectDestroyedEvent,
    PositionChangedEvent,
    RelocationResolvedEvent,
    ResourceSpentEvent,
    TeleportResolvedEvent,
    TerrainEffectCreatedEvent,
)
from shared_types.encounter_intents import AttackIntent
from shared_types.encounter_models import GridPosition, RuntimeActorState
from shared_types.errors import EncounterClarificationRequiredError, EncounterValidationError
from shared_types.storytelling import (
    EnterCombatPlan,
    ExitCombatPlan,
    ModeSwitchAction,
    ModeSwitchDecision,
    RuntimeMode,
    StoryCheckRequestState,
    StoryTranscriptEntry,
    StoryTranscriptVisibility,
)

from .improvised_templates import get_template_definition


@dataclass(frozen=True)
class AdjudicationExecutionResult:
    transcript_entries: tuple[StoryTranscriptEntry, ...] = ()
    scene_state_notes: tuple[str, ...] = ()
    terrain_change_lines: tuple[str, ...] = ()
    pending_check: StoryCheckRequestState | None = None
    pending_adjudication: PendingAdjudicationResolutionState | None = None
    mode_switch_decision: ModeSwitchDecision | None = None
    clarification_error: EncounterClarificationRequiredError | None = None
    outcome: str = ''


class EncounterAdjudicationRuntime:
    _SUPPORTED_OPERATION_TYPES = {
        AdjudicationOperationType.MOVE_ACTOR,
        AdjudicationOperationType.APPLY_CONDITION,
        AdjudicationOperationType.REMOVE_CONDITION,
        AdjudicationOperationType.APPLY_DAMAGE,
        AdjudicationOperationType.APPLY_HEALING,
        AdjudicationOperationType.CREATE_IMPROVISED_OBJECT,
        AdjudicationOperationType.DESTROY_OBJECT,
        AdjudicationOperationType.CREATE_TEMPORARY_TERRAIN_EFFECT,
        AdjudicationOperationType.CREATE_ILLUSION,
        AdjudicationOperationType.MODIFY_COVER_STATE,
        AdjudicationOperationType.TRIGGER_FORCED_MOVEMENT,
        AdjudicationOperationType.TRIGGER_HAZARD,
        AdjudicationOperationType.RECOMMEND_ENTER_COMBAT,
        AdjudicationOperationType.RECOMMEND_EXIT_COMBAT,
        AdjudicationOperationType.UPDATE_SCENE_STATE_NOTE,
    }

    def __init__(self, *, kernel) -> None:
        self.kernel = kernel

    def allowed_operation_types(self) -> tuple[str, ...]:
        return tuple(operation.value for operation in sorted(self._SUPPORTED_OPERATION_TYPES, key=lambda item: item.value))

    def validate_plan(self, state, *, runtime_mode: RuntimeMode, controller_id: str, actor_id: str, plan: AdjudicationPlan) -> AdjudicationPlan:
        actor = self.kernel._require_actor(state, actor_id)
        if runtime_mode == RuntimeMode.COMBAT and state.active_actor_id != actor_id:
            raise EncounterValidationError('Improvised combat adjudication is only available for the active actor.')
        if plan.check_request is not None:
            self._validate_check_request(state, actor_id=actor_id, request=plan.check_request)
        if plan.save_request is not None:
            self._validate_save_request(state, request=plan.save_request)
        if plan.contest_request is not None:
            self._validate_contest_request(state, request=plan.contest_request)
        if plan.attack_request is not None:
            self._validate_attack_request(state, runtime_mode=runtime_mode, actor_id=actor_id, plan=plan)
        if plan.action_cost_recommendation is not None:
            self._validate_action_cost(actor, runtime_mode=runtime_mode, cost=plan.action_cost_recommendation, adjudication_type=plan.adjudication_type)
        for template_id in plan.improvised_objects_to_create + plan.terrain_changes_to_create:
            get_template_definition(template_id)
        for operation in plan.operation_plan:
            self._validate_operation(state, default_actor_id=actor_id, operation=operation)
        for branch in (plan.on_success, plan.on_failure, plan.on_partial):
            if branch is None:
                continue
            for operation in branch.operations:
                self._validate_operation(state, default_actor_id=actor_id, operation=operation)
        recommendation = plan.mode_switch_recommendation
        if recommendation is not None:
            for participant_id in recommendation.participant_ids:
                self.kernel._require_actor(state, participant_id)
            if recommendation.action == recommendation.action.ENTER_COMBAT:
                if not recommendation.participant_ids or not recommendation.scene_id or not recommendation.location_id or not recommendation.battlefield_map_id:
                    raise EncounterValidationError('Enter-combat recommendations require participants, scene_id, location_id, and battlefield_map_id.')
        return plan

    def execute_plan(self, state, *, runtime_mode: RuntimeMode, controller_id: str, actor_id: str, plan: AdjudicationPlan) -> AdjudicationExecutionResult:
        self.validate_plan(state, runtime_mode=runtime_mode, controller_id=controller_id, actor_id=actor_id, plan=plan)
        if plan.adjudication_type == AdjudicationType.CLARIFICATION_REQUIRED:
            question = plan.clarification_request.question_to_player if plan.clarification_request is not None else 'Clarification required.'
            return AdjudicationExecutionResult(clarification_error=EncounterClarificationRequiredError(question), outcome='clarification')

        transcript_entries: list[StoryTranscriptEntry] = []
        scene_state_notes: list[str] = []
        terrain_change_lines: list[str] = []
        actor = self.kernel._require_actor(state, actor_id)
        self._apply_action_cost(state, actor=actor, cost=plan.action_cost_recommendation, adjudication_type=plan.adjudication_type)
        self._execute_operations(
            state,
            source_actor_id=actor_id,
            operations=plan.operation_plan,
            transcript_entries=transcript_entries,
            scene_state_notes=scene_state_notes,
            terrain_change_lines=terrain_change_lines,
            default_target_actor_id=self._default_target_actor_id(plan),
        )

        if plan.adjudication_type == AdjudicationType.ABILITY_CHECK:
            pending_check, pending_adjudication = self._open_pending_check(actor_id=actor_id, plan=plan)
            state.event_log.append(
                DMCheckIssuedEvent(
                    request_id=pending_check.request_id,
                    actor_id=actor_id,
                    ability=pending_check.check_request.ability,
                    skill_name=pending_check.check_request.skill_name,
                    dc=pending_check.check_request.dc,
                )
            )
            return AdjudicationExecutionResult(
                transcript_entries=tuple(transcript_entries),
                scene_state_notes=tuple(scene_state_notes),
                terrain_change_lines=tuple(terrain_change_lines),
                pending_check=pending_check,
                pending_adjudication=pending_adjudication,
                outcome='pending-check',
            )

        if plan.adjudication_type == AdjudicationType.SAVING_THROW:
            self._resolve_save_plan(state, source_actor_id=actor_id, plan=plan, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines)
            outcome = 'resolved'
        elif plan.adjudication_type == AdjudicationType.CONTEST:
            self._resolve_contest_plan(state, plan=plan, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines)
            outcome = 'resolved'
        elif plan.adjudication_type == AdjudicationType.ATTACK_ROLL:
            request = plan.attack_request
            prior_event_count = len(state.event_log)
            self.kernel.dispatch(state, AttackIntent(actor_id=request.attacker_id, attack_id=request.attack_id, target_id=request.target_id))
            recent_events = state.event_log[prior_event_count:]
            hit = any(event.__class__.__name__ == 'AttackHitEvent' and getattr(event, 'target_id', None) == request.target_id for event in recent_events)
            self._apply_branch(state, source_actor_id=actor_id, branch=(plan.on_success if hit else plan.on_failure), transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=request.target_id)
            outcome = 'hit' if hit else 'miss'
        elif plan.adjudication_type == AdjudicationType.IMPOSSIBLE:
            self._apply_branch(state, source_actor_id=actor_id, branch=plan.on_failure, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=self._default_target_actor_id(plan))
            outcome = 'impossible'
        elif plan.adjudication_type == AdjudicationType.PARTIAL_ONLY:
            self._apply_branch(state, source_actor_id=actor_id, branch=(plan.on_partial or plan.on_success), transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=self._default_target_actor_id(plan))
            outcome = 'partial'
        else:
            self._apply_branch(state, source_actor_id=actor_id, branch=plan.on_success, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=self._default_target_actor_id(plan))
            outcome = 'success'

        state.event_log.append(AdjudicatedActionResolvedEvent(actor_id=actor_id, adjudication_type=plan.adjudication_type, outcome=outcome))
        mode_switch = self._mode_switch_decision_from_plan(plan)
        if mode_switch is not None:
            state.event_log.append(DMModeSwitchRecommendedEvent(recommendation=plan.mode_switch_recommendation))
        return AdjudicationExecutionResult(transcript_entries=tuple(transcript_entries), scene_state_notes=tuple(scene_state_notes), terrain_change_lines=tuple(terrain_change_lines), mode_switch_decision=mode_switch, outcome=outcome)

    def resolve_pending_check(self, state, *, pending: PendingAdjudicationResolutionState, success: bool) -> AdjudicationExecutionResult:
        transcript_entries: list[StoryTranscriptEntry] = []
        scene_state_notes: list[str] = []
        terrain_change_lines: list[str] = []
        branch = pending.on_success if success else pending.on_failure
        self._apply_branch(state, source_actor_id=pending.actor_id, branch=branch, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines)
        outcome = 'success' if success else 'failure'
        state.event_log.append(AdjudicatedActionResolvedEvent(actor_id=pending.actor_id, adjudication_type=AdjudicationType.ABILITY_CHECK, outcome=outcome))
        return AdjudicationExecutionResult(transcript_entries=tuple(transcript_entries), scene_state_notes=tuple(scene_state_notes), terrain_change_lines=tuple(terrain_change_lines), mode_switch_decision=self._mode_switch_decision_from_recommendation(pending.mode_switch_recommendation), outcome=outcome)
    def _validate_check_request(self, state, *, actor_id: str, request: AdjudicationCheckRequest) -> None:
        self.kernel._require_actor(state, request.actor_id)
        if request.actor_id != actor_id:
            raise EncounterValidationError('Improvised checks must target the acting actor in this slice.')
        if request.advantage_state != request.advantage_state.NORMAL:
            raise EncounterValidationError('Explicit check advantage_state is not supported in improvised adjudication yet.')

    def _validate_save_request(self, state, *, request) -> None:
        for target_actor_id in request.target_actor_ids:
            self.kernel._require_actor(state, target_actor_id)
        if request.advantage_state != request.advantage_state.NORMAL:
            raise EncounterValidationError('Explicit save advantage_state is not supported in improvised adjudication yet.')

    def _validate_contest_request(self, state, *, request) -> None:
        self._validate_contest_participant(state, request.actor_a)
        self._validate_contest_participant(state, request.actor_b)

    def _validate_contest_participant(self, state, participant: ContestParticipantRequest) -> None:
        self.kernel._require_actor(state, participant.actor_id)
        if participant.advantage_state != participant.advantage_state.NORMAL:
            raise EncounterValidationError('Explicit contest advantage_state is not supported in improvised adjudication yet.')

    def _validate_attack_request(self, state, *, runtime_mode: RuntimeMode, actor_id: str, plan: AdjudicationPlan) -> None:
        request = plan.attack_request
        if request is None:
            raise EncounterValidationError('attack_roll adjudication requires attack_request.')
        if runtime_mode != RuntimeMode.COMBAT:
            raise EncounterValidationError('Attack-roll improvised adjudication is only supported during combat in this slice.')
        if request.attacker_id != actor_id:
            raise EncounterValidationError('Improvised attack adjudication must be issued by the acting actor.')
        actor = self.kernel._require_actor(state, request.attacker_id)
        self.kernel._require_actor(state, request.target_id)
        if request.attack_id is None or request.attack_id not in actor.attacks:
            raise EncounterValidationError('Attack-roll improvised adjudication requires a valid attack_id on the acting actor.')

    def _validate_action_cost(self, actor: RuntimeActorState, *, runtime_mode: RuntimeMode, cost: ActionCostRecommendation, adjudication_type: AdjudicationType) -> None:
        if runtime_mode != RuntimeMode.COMBAT or adjudication_type == AdjudicationType.ATTACK_ROLL:
            return
        if cost.cost_type == ActionCostType.NONE:
            return
        if cost.cost_type == ActionCostType.ACTION and not actor.action_available:
            raise EncounterValidationError('The acting actor has no action available for this improvised combat action.')
        if cost.cost_type == ActionCostType.BONUS_ACTION and not actor.bonus_action_available:
            raise EncounterValidationError('The acting actor has no bonus action available for this improvised combat action.')
        if cost.cost_type == ActionCostType.REACTION and not actor.reaction_available:
            raise EncounterValidationError('The acting actor has no reaction available for this improvised combat action.')
        if cost.cost_type == ActionCostType.OBJECT_INTERACTION and not actor.remaining_free_object_interaction:
            raise EncounterValidationError('The acting actor has already used its free object interaction this turn.')
        if cost.cost_type == ActionCostType.MOVEMENT and (cost.movement_cost_ft <= 0 or actor.remaining_movement_ft < cost.movement_cost_ft):
            raise EncounterValidationError('The acting actor does not have enough movement remaining for this improvised combat action.')

    def _validate_operation(self, state, *, default_actor_id: str, operation: AdjudicationOperation) -> None:
        if operation.operation_type not in self._SUPPORTED_OPERATION_TYPES:
            raise EncounterValidationError(f'Unsupported adjudication operation type: {operation.operation_type.value}.')
        actor_id = operation.actor_id or default_actor_id
        if operation.operation_type == AdjudicationOperationType.UPDATE_SCENE_STATE_NOTE:
            if not operation.note:
                raise EncounterValidationError('update_scene_state_note requires a non-empty note.')
            return
        if operation.operation_type in {AdjudicationOperationType.CREATE_IMPROVISED_OBJECT, AdjudicationOperationType.CREATE_TEMPORARY_TERRAIN_EFFECT}:
            if operation.template_id is None or operation.x is None or operation.y is None:
                raise EncounterValidationError(f'{operation.operation_type.value} requires template_id, x, and y.')
            get_template_definition(operation.template_id)
            self.kernel.battlefield_rules.get_tile(state.battlefield, operation.x, operation.y)
            return
        if operation.operation_type == AdjudicationOperationType.CREATE_ILLUSION:
            if operation.illusion_spec is None or operation.x is None or operation.y is None:
                raise EncounterValidationError('create_illusion requires illusion_spec plus x and y coordinates.')
            if operation.duration_rounds is None or operation.duration_rounds <= 0:
                raise EncounterValidationError('create_illusion requires a positive duration_rounds value in this slice.')
            self.kernel.battlefield_rules.get_tile(state.battlefield, operation.x, operation.y)
            for observer_id in operation.illusion_spec.target_observer_ids:
                self.kernel._require_actor(state, observer_id)
            return
        if operation.operation_type == AdjudicationOperationType.DESTROY_OBJECT:
            if not operation.object_id:
                raise EncounterValidationError('destroy_object requires object_id.')
            return
        if operation.operation_type == AdjudicationOperationType.MODIFY_COVER_STATE:
            if not operation.actor_id or not operation.target_actor_id or operation.cover_level is None:
                raise EncounterValidationError('modify_cover_state requires actor_id, target_actor_id, and cover_level.')
            self.kernel._require_actor(state, operation.actor_id)
            self.kernel._require_actor(state, operation.target_actor_id)
            return
        self.kernel._require_actor(state, actor_id)
        if operation.target_actor_id is not None:
            self.kernel._require_actor(state, operation.target_actor_id)
        if operation.operation_type == AdjudicationOperationType.MOVE_ACTOR:
            if operation.x is None or operation.y is None:
                raise EncounterValidationError('move_actor requires x and y coordinates.')
            return
        if operation.operation_type in {AdjudicationOperationType.APPLY_CONDITION, AdjudicationOperationType.REMOVE_CONDITION} and operation.condition_type is None:
            raise EncounterValidationError(f'{operation.operation_type.value} requires condition_type.')
        if operation.operation_type == AdjudicationOperationType.APPLY_DAMAGE:
            if operation.damage_dice_count is None or operation.damage_die_faces is None or operation.damage_type is None:
                raise EncounterValidationError('apply_damage requires damage dice and damage_type.')
            return
        if operation.operation_type == AdjudicationOperationType.APPLY_HEALING:
            if operation.healing_dice_count is None or operation.healing_die_faces is None:
                raise EncounterValidationError('apply_healing requires healing dice.')
            return
        if operation.operation_type == AdjudicationOperationType.TRIGGER_FORCED_MOVEMENT:
            if operation.target_actor_id is None:
                raise EncounterValidationError('trigger_forced_movement requires target_actor_id.')
            if operation.forced_movement_distance_ft is None and operation.displacement is None:
                raise EncounterValidationError('trigger_forced_movement requires forced_movement_distance_ft or displacement.')
            return
        if operation.operation_type == AdjudicationOperationType.TRIGGER_HAZARD:
            if operation.target_actor_id is None:
                raise EncounterValidationError('trigger_hazard requires target_actor_id.')
            if operation.damage_dice_count is None and operation.condition_type is None and operation.forced_movement_distance_ft is None and operation.displacement is None:
                raise EncounterValidationError('trigger_hazard requires a damage, condition, or forced movement payload.')
            return

    def _apply_action_cost(self, state, *, actor: RuntimeActorState, cost: ActionCostRecommendation | None, adjudication_type: AdjudicationType) -> None:
        if cost is None or adjudication_type == AdjudicationType.ATTACK_ROLL or cost.cost_type == ActionCostType.NONE:
            return
        if cost.cost_type == ActionCostType.ACTION:
            self.kernel._apply_event(state, ResourceSpentEvent(actor_id=actor.actor_id, resource='action', reason=cost.reason or 'improvised-adjudication'))
        elif cost.cost_type == ActionCostType.BONUS_ACTION:
            self.kernel._apply_event(state, ResourceSpentEvent(actor_id=actor.actor_id, resource='bonus', reason=cost.reason or 'improvised-adjudication'))
        elif cost.cost_type == ActionCostType.REACTION:
            self.kernel._apply_event(state, ResourceSpentEvent(actor_id=actor.actor_id, resource='reaction', reason=cost.reason or 'improvised-adjudication'))
        elif cost.cost_type == ActionCostType.OBJECT_INTERACTION:
            self.kernel._apply_event(state, ResourceSpentEvent(actor_id=actor.actor_id, resource='object', reason=cost.reason or 'improvised-adjudication'))
        elif cost.cost_type == ActionCostType.MOVEMENT and cost.movement_cost_ft > 0:
            self.kernel._apply_event(state, ResourceSpentEvent(actor_id=actor.actor_id, resource='movement', reason=cost.reason or 'improvised-adjudication', amount=cost.movement_cost_ft))

    def _open_pending_check(self, *, actor_id: str, plan: AdjudicationPlan) -> tuple[StoryCheckRequestState, PendingAdjudicationResolutionState]:
        request = plan.check_request
        prompt = f'Roll {self._check_label(request)}.'
        request_id = f'adjudication-check:{actor_id}:{request.dc}:{len(plan.action_summary)}'
        story_request = StoryCheckRequestState(
            request_id=request_id,
            actor_id=request.actor_id,
            prompt=prompt,
            reason=request.reason,
            check_request=CheckRequest(
                context=ResolutionContext(effect_id=request_id, source_actor_id=None, target_actor_id=request.actor_id, reason=request.reason),
                ability=request.ability,
                dc=request.dc,
                skill_name=request.skill_name,
                requires_sight=request.requires_sight,
                requires_hearing=request.requires_hearing,
                interacting_with_actor_id=request.interacting_with_actor_id,
            ),
        )
        pending = PendingAdjudicationResolutionState(
            plan_id=request_id,
            actor_id=actor_id,
            action_summary=plan.action_summary,
            reasoning_summary_for_dm=plan.reasoning_summary_for_dm,
            check_request=request,
            on_success=plan.on_success,
            on_failure=plan.on_failure,
            on_partial=plan.on_partial,
            mode_switch_recommendation=plan.mode_switch_recommendation,
        )
        return story_request, pending
    def _resolve_save_plan(self, state, *, source_actor_id: str, plan: AdjudicationPlan, transcript_entries: list[StoryTranscriptEntry], scene_state_notes: list[str], terrain_change_lines: list[str]) -> None:
        request = plan.save_request
        state.event_log.append(DMSaveIssuedEvent(source_actor_id=source_actor_id, target_actor_ids=request.target_actor_ids, ability=request.save_ability, dc=request.dc))
        for target_actor_id in request.target_actor_ids:
            resolution, _events = self.kernel.resolve_save_consumer(
                state,
                SaveRequest(
                    context=ResolutionContext(effect_id=f'adjudication-save:{source_actor_id}:{target_actor_id}:{state.random_counter}', source_actor_id=source_actor_id, target_actor_id=target_actor_id, reason=request.reason),
                    ability=request.save_ability,
                    dc=request.dc,
                ),
                apply=True,
            )
            if resolution.branch == EffectResolutionBranch.SUCCESS:
                branch = plan.on_success
            elif resolution.branch == EffectResolutionBranch.PARTIAL_SUCCESS:
                branch = plan.on_partial or plan.on_failure
            else:
                branch = plan.on_failure
            self._apply_branch(state, source_actor_id=source_actor_id, branch=branch, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=target_actor_id)

    def _resolve_contest_plan(self, state, *, plan: AdjudicationPlan, transcript_entries: list[StoryTranscriptEntry], scene_state_notes: list[str], terrain_change_lines: list[str]) -> None:
        request = plan.contest_request
        state.event_log.append(DMContestIssuedEvent(actor_a_id=request.actor_a.actor_id, actor_b_id=request.actor_b.actor_id, reason=request.reason))
        result_a = self._contest_check_resolution(state, request.actor_a, request.reason)
        result_b = self._contest_check_resolution(state, request.actor_b, request.reason)
        if result_a.result.total > result_b.result.total:
            branch = plan.on_success
        elif result_b.result.total > result_a.result.total:
            branch = plan.on_failure
        else:
            if request.tie_rule == ContestTieRule.NO_CHANGE:
                branch = plan.on_partial
            elif request.tie_rule == ContestTieRule.DEFENDER_WINS:
                branch = plan.on_failure
            else:
                branch = plan.on_success
        self._apply_branch(state, source_actor_id=request.actor_a.actor_id, branch=branch, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=request.actor_b.actor_id)

    def _contest_check_resolution(self, state, participant: ContestParticipantRequest, reason: str):
        actor = self.kernel._require_actor(state, participant.actor_id)
        skill_bonus = actor.skill_bonuses.get(participant.skill_name, actor.ability_modifiers[participant.ability]) if participant.skill_name else actor.ability_modifiers[participant.ability]
        flat_modifier = skill_bonus - actor.ability_modifiers[participant.ability]
        resolution, _events = self.kernel.resolve_check_consumer(
            state,
            CheckRequest(
                context=ResolutionContext(effect_id=f'adjudication-contest:{participant.actor_id}:{state.random_counter}', source_actor_id=None, target_actor_id=participant.actor_id, reason=reason),
                ability=participant.ability,
                dc=0,
                skill_name=participant.skill_name,
                flat_modifier=flat_modifier,
            ),
            apply=True,
        )
        return resolution

    def _apply_branch(self, state, *, source_actor_id: str, branch: AdjudicationBranch | None, transcript_entries: list[StoryTranscriptEntry], scene_state_notes: list[str], terrain_change_lines: list[str], default_target_actor_id: str | None = None) -> None:
        if branch is None:
            return
        if branch.public_text:
            transcript_entries.append(StoryTranscriptEntry(speaker='DM', text=branch.public_text, visibility=StoryTranscriptVisibility.PUBLIC))
        if branch.dm_note:
            transcript_entries.append(StoryTranscriptEntry(speaker='DM', text=branch.dm_note, visibility=StoryTranscriptVisibility.DM_ONLY))
        self._execute_operations(state, source_actor_id=source_actor_id, operations=branch.operations, transcript_entries=transcript_entries, scene_state_notes=scene_state_notes, terrain_change_lines=terrain_change_lines, default_target_actor_id=default_target_actor_id)

    def _execute_operations(self, state, *, source_actor_id: str, operations: tuple[AdjudicationOperation, ...], transcript_entries: list[StoryTranscriptEntry], scene_state_notes: list[str], terrain_change_lines: list[str], default_target_actor_id: str | None = None) -> None:
        for operation in operations:
            actor_id = operation.actor_id or source_actor_id
            target_actor_id = operation.target_actor_id or default_target_actor_id
            if operation.operation_type == AdjudicationOperationType.UPDATE_SCENE_STATE_NOTE:
                scene_state_notes.append(operation.note)
            elif operation.operation_type == AdjudicationOperationType.CREATE_IMPROVISED_OBJECT:
                feature_id = operation.object_id or f'improv-object:{actor_id}:{operation.template_id.value}:{operation.x}:{operation.y}:{len(state.event_log)}'
                anchor = GridPosition(operation.x, operation.y, operation.z or self.kernel.battlefield_rules.get_tile(state.battlefield, operation.x, operation.y).elevation_ft)
                self.kernel._apply_event(state, ImprovisedObjectCreatedEvent(feature_id=feature_id, template_id=operation.template_id.value, anchor=anchor))
                terrain_change_lines.append(operation.note or f'Created improvised object {operation.template_id.value}.')
            elif operation.operation_type == AdjudicationOperationType.CREATE_TEMPORARY_TERRAIN_EFFECT:
                feature_id = operation.terrain_effect_id or f'improv-terrain:{actor_id}:{operation.template_id.value}:{operation.x}:{operation.y}:{len(state.event_log)}'
                anchor = GridPosition(operation.x, operation.y, operation.z or self.kernel.battlefield_rules.get_tile(state.battlefield, operation.x, operation.y).elevation_ft)
                self.kernel._apply_event(state, TerrainEffectCreatedEvent(feature_id=feature_id, template_id=operation.template_id.value, anchor=anchor))
                terrain_change_lines.append(operation.note or f'Created terrain effect {operation.template_id.value}.')
            elif operation.operation_type == AdjudicationOperationType.CREATE_ILLUSION:
                self._execute_create_illusion(state, source_actor_id=actor_id, operation=operation)
                terrain_change_lines.append(operation.note or f'Created illusion {operation.illusion_spec.template_id.value}.')
            elif operation.operation_type == AdjudicationOperationType.DESTROY_OBJECT:
                self.kernel._apply_event(state, ImprovisedObjectDestroyedEvent(feature_id=operation.object_id))
                terrain_change_lines.append(operation.note or f'Removed improvised object {operation.object_id}.')
            elif operation.operation_type == AdjudicationOperationType.APPLY_CONDITION:
                self.kernel._apply_event(state, self.kernel._condition_added_event_from_application(target_actor_id=(target_actor_id or actor_id), application=ConditionApplication(condition_type=operation.condition_type, source_label=(operation.source_label or operation.note or 'Improvised adjudication'), source_actor_id=actor_id)))
            elif operation.operation_type == AdjudicationOperationType.REMOVE_CONDITION:
                self.kernel._apply_event(state, self.kernel._condition_removed_event_for_type(actor_id=(target_actor_id or actor_id), condition_type=operation.condition_type))
            elif operation.operation_type == AdjudicationOperationType.APPLY_DAMAGE:
                self._apply_damage(state, source_actor_id=actor_id, target_actor_id=(target_actor_id or actor_id), operation=operation)
            elif operation.operation_type == AdjudicationOperationType.APPLY_HEALING:
                self._apply_healing(state, source_actor_id=actor_id, target_actor_id=(target_actor_id or actor_id), operation=operation)
            elif operation.operation_type == AdjudicationOperationType.MODIFY_COVER_STATE:
                self.kernel._apply_event(state, CoverStateModifiedEvent(attacker_id=operation.actor_id, target_id=operation.target_actor_id, cover_level=operation.cover_level))
            elif operation.operation_type == AdjudicationOperationType.MOVE_ACTOR:
                mover = self.kernel._require_actor(state, target_actor_id or actor_id)
                from_position = mover.position
                destination = GridPosition(operation.x, operation.y, mover.position.z if operation.z is None else operation.z)
                self.kernel._apply_event(state, TeleportResolvedEvent(actor_id=mover.actor_id, spell_id='improvised-move', from_position=from_position, to_position=destination, distance_ft=self.kernel.battlefield_rules.get_distance3d(from_position, destination)))
                self.kernel._apply_event(state, RelocationResolvedEvent(actor_id=mover.actor_id, from_position=from_position, to_position=destination, relocation_type=RelocationType.TELEPORT, movement_mode=TraversalMode.TELEPORT))
                self.kernel._apply_event(state, PositionChangedEvent(actor_id=mover.actor_id, from_position=from_position, to_position=destination, relocation_type=RelocationType.TELEPORT, movement_mode=TraversalMode.TELEPORT))
            elif operation.operation_type == AdjudicationOperationType.TRIGGER_FORCED_MOVEMENT:
                effect = ForcedMovementEffect(
                    context=ResolutionContext(effect_id=f'adjudication-forced:{actor_id}:{target_actor_id}:{len(state.event_log)}', source_actor_id=actor_id, target_actor_id=(target_actor_id or actor_id), reason=operation.note or 'Improvised forced movement'),
                    mode=ForcedMovementMode(operation.forced_movement_mode or ForcedMovementMode.REPOSITION.value),
                    distance_ft=(operation.forced_movement_distance_ft or 0),
                    vector=operation.displacement,
                )
                self.kernel.apply_forced_movement(state, effect, apply=True)
            elif operation.operation_type == AdjudicationOperationType.TRIGGER_HAZARD:
                damage = DamageEffect(dice_count=operation.damage_dice_count, die_faces=operation.damage_die_faces, bonus=operation.damage_bonus, damage_type=operation.damage_type) if operation.damage_dice_count is not None and operation.damage_die_faces is not None and operation.damage_type is not None else None
                conditions = (ConditionApplication(condition_type=operation.condition_type, source_actor_id=actor_id, source_label=(operation.source_label or operation.note or 'Improvised hazard')),) if operation.condition_type is not None else ()
                forced = ForcedMovementEffect(context=ResolutionContext(effect_id=f'adjudication-hazard:{actor_id}:{target_actor_id}:{len(state.event_log)}', source_actor_id=actor_id, target_actor_id=(target_actor_id or actor_id), reason=operation.note or 'Improvised hazard'), mode=ForcedMovementMode(operation.forced_movement_mode or ForcedMovementMode.REPOSITION.value), distance_ft=(operation.forced_movement_distance_ft or 0), vector=operation.displacement) if operation.forced_movement_distance_ft is not None or operation.displacement is not None else None
                request = HazardResolutionRequest(context=ResolutionContext(effect_id=f'adjudication-hazard:{actor_id}:{target_actor_id}:{len(state.event_log)}', source_actor_id=actor_id, target_actor_id=(target_actor_id or actor_id), reason=operation.note or 'Improvised hazard'), failure_outcome=EffectOutcome(damage=damage, conditions=conditions, forced_movement=forced, damage_divisor=operation.damage_divisor))
                self.kernel.resolve_hazard(state, request, apply=True)
            elif operation.operation_type == AdjudicationOperationType.RECOMMEND_ENTER_COMBAT:
                scene_state_notes.append(operation.note or 'Combat entry recommended.')
            elif operation.operation_type == AdjudicationOperationType.RECOMMEND_EXIT_COMBAT:
                scene_state_notes.append(operation.note or 'Combat exit recommended.')
    def _execute_create_illusion(self, state, *, source_actor_id: str, operation: AdjudicationOperation) -> None:
        actor = self.kernel._require_actor(state, source_actor_id)
        illusion_spec = operation.illusion_spec
        if illusion_spec is None or operation.x is None or operation.y is None:
            raise EncounterValidationError('create_illusion requires illusion_spec plus x and y coordinates.')
        anchor_tile = self.kernel.battlefield_rules.get_tile(state.battlefield, operation.x, operation.y)
        anchor = GridPosition(operation.x, operation.y, operation.z or anchor_tile.elevation_ft)
        observer_filter = (
            PersistentObserverFilter(
                observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
                observer_actor_ids=illusion_spec.target_observer_ids,
            )
            if illusion_spec.target_observer_ids
            else PersistentObserverFilter(observer_mode=PersistentObserverMode.ALL_VALID_OBSERVERS)
        )
        reveal_policy = self._illusion_reveal_policy(illusion_spec)
        illusion_definition = self._illusion_definition_from_spec(illusion_spec, observer_filter=observer_filter, reveal_policy=reveal_policy)
        active_effect = ActiveEffectDefinition(
            name=illusion_spec.display_name or illusion_spec.template_id.value,
            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=operation.duration_rounds),
            concentration=False,
            illusions=(illusion_definition,),
        )
        capability = CapabilityDefinition(
            capability_id=f'adjudication-illusion:{source_actor_id}:{illusion_spec.template_id.value}',
            name=illusion_spec.display_name or illusion_spec.template_id.value,
            kind=CapabilityKind.SPELL,
            source='ADJUDICATION',
            action_cost='none',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=0, requires_line_of_effect=False),
            effect=StartActiveEffectDef(active_effect=active_effect),
        )
        for event in self.kernel.effect_executor.execute_capability(state, actor=actor, capability=capability, point=anchor):
            self.kernel._apply_event(state, event)

    def _illusion_reveal_policy(self, illusion_spec: AdjudicationIllusionSpec) -> IllusionRevealPolicy:
        mapping = {
            None: IllusionRevealPolicy.ON_STUDY_SUCCESS,
            'study': IllusionRevealPolicy.ON_STUDY_SUCCESS,
            'physical': IllusionRevealPolicy.ON_PHYSICAL_INTERACTION,
            'passive': IllusionRevealPolicy.ON_PASSIVE_NOTICE,
            'any': IllusionRevealPolicy.ON_ANY_INTERACTION,
        }
        try:
            return mapping[illusion_spec.reveal_policy]
        except KeyError as exc:
            raise EncounterValidationError(f'Unsupported illusion reveal policy: {illusion_spec.reveal_policy}.') from exc

    def _illusion_definition_from_spec(self, illusion_spec: AdjudicationIllusionSpec, *, observer_filter: PersistentObserverFilter, reveal_policy: IllusionRevealPolicy) -> IllusionDefinition:
        template_defaults = {
            'minor_visual_object': (IllusionSubtype.SMALL_STATIC_VISUAL, IllusionModality.VISUAL, 5, 5, 5, False),
            'minor_visual_barrier': (IllusionSubtype.SMALL_STATIC_VISUAL, IllusionModality.VISUAL, 5, 5, 5, True),
            'minor_visual_door': (IllusionSubtype.SMALL_STATIC_VISUAL, IllusionModality.VISUAL, 5, 5, 5, False),
            'minor_visual_sign_or_sigil': (IllusionSubtype.SMALL_STATIC_VISUAL, IllusionModality.VISUAL, 5, 5, 5, False),
            'minor_sound_source': (IllusionSubtype.SMALL_SENSORY, IllusionModality.AUDITORY, 5, 5, 5, False),
            'medium_scene_dressing_illusion': (IllusionSubtype.ENVIRONMENTAL, IllusionModality.MIXED, 10, 10, 10, False),
            'observer_specific_visual_overlay': (IllusionSubtype.OBSERVER_SPECIFIC, IllusionModality.OBSERVER_SPECIFIC_OVERLAY, 5, 5, 5, False),
            'illusionary_large_facade': (IllusionSubtype.ENVIRONMENTAL, IllusionModality.VISUAL, 20, 20, 20, True),
        }
        subtype, modality, width_ft, depth_ft, height_ft, default_blocker = template_defaults[illusion_spec.template_id.value]
        semantic_tags = illusion_spec.semantic_tags or (illusion_spec.display_name.lower().replace(' ', '-'),)
        return IllusionDefinition(
            template_id=illusion_spec.template_id,
            subtype=subtype,
            modality=modality,
            display_name=illusion_spec.display_name or illusion_spec.template_id.value,
            display_description=illusion_spec.display_description or illusion_spec.display_name or illusion_spec.template_id.value,
            width_ft=width_ft,
            depth_ft=depth_ft,
            height_ft=height_ft,
            semantic_tags=semantic_tags,
            observer_filter=observer_filter,
            apparent_properties=IllusionApparentProperties(
                apparent_cover=illusion_spec.apparent_cover,
                apparent_blocker=(illusion_spec.apparent_blocker or default_blocker),
                apparent_door=(illusion_spec.template_id.value == 'minor_visual_door'),
                apparent_opening=(illusion_spec.template_id.value == 'minor_visual_door'),
                apparent_object_category=(illusion_spec.template_id.value),
            ),
            actual_properties=IllusionActualProperties(),
            reveal_policies=(reveal_policy,),
            reveal_to_all_on_interaction=False,
        )
    def _apply_damage(self, state, *, source_actor_id: str, target_actor_id: str, operation: AdjudicationOperation) -> None:
        target = self.kernel._require_actor(state, target_actor_id)
        rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=operation.damage_dice_count, die_faces=operation.damage_die_faces, bonus=operation.damage_bonus)
        if operation.damage_divisor > 1:
            total //= operation.damage_divisor
        hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = self.kernel._damage_preview(state, target, total, damage_type=operation.damage_type)
        for event in effect_events:
            self.kernel._apply_event(state, event)
        self.kernel._apply_event(state, DamageRolledEvent(actor_id=source_actor_id, attack_id=None, target_id=target_actor_id, damage_rolls=rolls, damage_total=total, damage_type=operation.damage_type, random_counter_used=state.random_counter))
        self.kernel._apply_event(state, DamageAppliedEvent(source_actor_id=source_actor_id, target_id=target_actor_id, damage_total=total, applied_damage_total=applied_damage_total, target_hit_points_after=hit_points_after, target_temp_hit_points_after=temp_hit_points_after, damage_type=operation.damage_type))

    def _apply_healing(self, state, *, source_actor_id: str, target_actor_id: str, operation: AdjudicationOperation) -> None:
        target = self.kernel._require_actor(state, target_actor_id)
        rolls, total = roll_damage(seeded_random(self.kernel.seed, state.random_counter), dice_count=operation.healing_dice_count, die_faces=operation.healing_die_faces, bonus=operation.healing_bonus)
        self.kernel._apply_event(state, DamageRolledEvent(actor_id=source_actor_id, attack_id=None, target_id=target_actor_id, damage_rolls=rolls, damage_total=total, damage_type='healing', random_counter_used=state.random_counter))
        self.kernel._apply_event(state, HealingAppliedEvent(source_actor_id=source_actor_id, target_id=target_actor_id, healing_total=total, target_hit_points_after=min(target.max_hit_points, target.current_hit_points + total)))

    def _default_target_actor_id(self, plan: AdjudicationPlan) -> str | None:
        if plan.attack_request is not None:
            return plan.attack_request.target_id
        if plan.save_request is not None and len(plan.save_request.target_actor_ids) == 1:
            return plan.save_request.target_actor_ids[0]
        if plan.contest_request is not None:
            return plan.contest_request.actor_b.actor_id
        return None

    def _check_label(self, request: AdjudicationCheckRequest) -> str:
        labels = {'STR': 'Strength', 'DEX': 'Dexterity', 'CON': 'Constitution', 'INT': 'Intelligence', 'WIS': 'Wisdom', 'CHA': 'Charisma'}
        ability_label = labels.get(request.ability.value, request.ability.value)
        return f'{ability_label} ({request.skill_name})' if request.skill_name else ability_label

    def _mode_switch_decision_from_plan(self, plan: AdjudicationPlan) -> ModeSwitchDecision | None:
        return self._mode_switch_decision_from_recommendation(plan.mode_switch_recommendation)

    def _mode_switch_decision_from_recommendation(self, recommendation: AdjudicationModeSwitchRecommendation | None) -> ModeSwitchDecision | None:
        if recommendation is None:
            return None
        if recommendation.action == recommendation.action.ENTER_COMBAT:
            return ModeSwitchDecision(
                decision_type=ModeSwitchAction.ENTER_COMBAT,
                reason=recommendation.reason,
                enter_combat_plan=EnterCombatPlan(reason=recommendation.reason, participant_ids=recommendation.participant_ids, scene_id=recommendation.scene_id, location_id=recommendation.location_id, ambush=recommendation.ambush, battlefield_map_id=recommendation.battlefield_map_id),
                confidence=1.0,
                raw_response_text='',
            )
        return ModeSwitchDecision(
            decision_type=ModeSwitchAction.EXIT_COMBAT,
            reason=recommendation.reason,
            exit_combat_plan=ExitCombatPlan(reason=recommendation.reason),
            confidence=1.0,
            raw_response_text='',
        )








