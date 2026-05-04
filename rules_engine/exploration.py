from __future__ import annotations

from dataclasses import dataclass, replace
import re

from shared_types.encounter_events import (
    D20TestRolledEvent,
    DiscoveryRevealedEvent,
    DowntimeProjectCompletedEvent,
    DowntimeProjectProgressedEvent,
    DowntimeProjectStartedEvent,
    ExplorationProcedureCompletedEvent,
    ExplorationProcedureProgressedEvent,
    ExplorationProcedureStartedEvent,
    ExplorationStateProjectionUpdatedEvent,
    MarchingOrderUpdatedEvent,
    NPCStanceChangedEvent,
    PuzzleProgressedEvent,
    PuzzleSolvedEvent,
    SocialInfluenceAttemptedEvent,
    SocialInfluenceResolvedEvent,
    StoryCheckResolvedEvent,
    ToolUseDeclaredEvent,
    ToolUseResolvedEvent,
    TimeAdvancedEvent,
    TrapDetectedEvent,
    TrapDisarmedEvent,
    TrapTriggeredEvent,
    WatchOrderUpdatedEvent,
)
from shared_types.encounter_models import ActorSide, EncounterState, RuntimeActorState
from shared_types.effects import CheckRequest
from shared_types.errors import EncounterValidationError
from shared_types.exploration import (
    AbandonPuzzleIntent,
    AssignExplorationRoleIntent,
    AttemptPuzzleIntent,
    AttemptSocialInfluenceIntent,
    AttemptTrapIntent,
    BypassTrapIntent,
    CancelDowntimeProjectIntent,
    DowntimeActivityDefinition,
    DowntimeProjectState,
    DowntimeProjectStatus,
    ExplorationMode,
    ExplorationRole,
    ExplorationState,
    MarchPosition,
    MarchingOrderEntry,
    NpcAttitude,
    NpcInfluenceProfile,
    NpcInfluenceState,
    PendingExplorationCheckKind,
    PendingExplorationCheckState,
    ProcedureAttemptKind,
    ProcedureCategory,
    ProcedureCheckOption,
    ProcedureDefinition,
    ProcedureOutcome,
    ProcedureProgressState,
    ProcedureStatus,
    PuzzleDefinition,
    PuzzleRuntimeState,
    PuzzleStatus,
    SetCampStateIntent,
    SetMarchingOrderIntent,
    SetWatchOrderIntent,
    SocialApproachDefinition,
    SocialApproachType,
    SocialOutcome,
    StartDowntimeProjectIntent,
    TrapDefinition,
    TrapRuntimeState,
    TrapStatus,
    TriggerTrapIntent,
    WatchAssignment,
    WorkDowntimeProjectIntent,
    unique_strings,
)
from shared_types.models import Ability, slugify
from shared_types.rest import RestActivityType
from shared_types.storytelling import SpellcastingReactionCategory, SpellcastingWitnessReaction

from .exploration_declarations import (
    ExplorationDeclarationPrompt,
    interpret_declaration as interpret_exploration_declaration,
    resolve_pending_exploration_check as apply_pending_exploration_check,
)


@dataclass(frozen=True)
class ProcedureAttemptResult:
    progress: ProcedureProgressState
    outcome: ProcedureOutcome
    summary: str
    revealed_clues: tuple[str, ...]
    events: tuple[object, ...]


@dataclass(frozen=True)
class PreparedProcedureCheck:
    definition: ProcedureDefinition
    progress: ProcedureProgressState
    option: ProcedureCheckOption
    canonical_tool_name: str | None
    request_prefix: str
    interacting_with_actor_id: str | None
    progress_multiplier: int


@dataclass(frozen=True)
class ExplorationDeclarationPrompt:
    pending_state: PendingExplorationCheckState
    prompt: str
    reason: str
    ability: Ability
    skill_name: str | None
    dc: int
    interacting_with_actor_id: str | None


class ExplorationProcedureEngine:
    def __init__(self, *, kernel, campaign_id: str = 'lmop') -> None:
        self.kernel = kernel
        self.campaign_id = campaign_id
        self.social_profiles = {profile.npc_id: profile for profile in _lmop_social_profiles()}
        self.trap_definitions = {definition.trap_id: definition for definition in _lmop_trap_definitions()}
        self.puzzle_definitions = {definition.puzzle_id: definition for definition in _lmop_puzzle_definitions()}
        self.downtime_activities = {definition.activity_id: definition for definition in _lmop_downtime_activities()}

    def initial_state(
        self,
        *,
        encounter_state: EncounterState,
        actor_ids: tuple[str, ...],
        current_scene_id: str | None,
        current_location_id: str | None,
        current_travel_map_id: str | None = None,
        travel_active: bool = False,
    ) -> tuple[ExplorationState, list[object]]:
        marching_order = self._default_marching_order(actor_ids)
        watch_order = tuple(WatchAssignment(actor_id=actor_id, shift_index=index) for index, actor_id in enumerate(actor_ids))
        npc_states = {
            npc_id: NpcInfluenceState(
                npc_id=profile.npc_id,
                display_name=profile.display_name,
                attitude=profile.base_attitude,
                current_stance=profile.base_stance,
            )
            for npc_id, profile in self.social_profiles.items()
        }
        traps = {
            trap_id: TrapRuntimeState(trap_id=definition.trap_id, title=definition.title, status=TrapStatus.HIDDEN)
            for trap_id, definition in self.trap_definitions.items()
        }
        puzzles = {
            puzzle_id: PuzzleRuntimeState(puzzle_id=definition.puzzle_id, title=definition.title)
            for puzzle_id, definition in self.puzzle_definitions.items()
        }
        state = ExplorationState(
            mode=ExplorationMode.SCENE,
            marching_order=marching_order,
            watch_order=watch_order,
            current_scene_id=current_scene_id,
            current_location_id=current_location_id,
            current_travel_map_id=current_travel_map_id,
            npc_states=npc_states,
            traps=traps,
            puzzles=puzzles,
        )
        return self.sync_context(
            state,
            encounter_state=encounter_state,
            current_scene_id=current_scene_id,
            current_location_id=current_location_id,
            current_travel_map_id=current_travel_map_id,
            travel_active=travel_active,
        )

    def sync_context(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        current_scene_id: str | None,
        current_location_id: str | None,
        current_travel_map_id: str | None,
        travel_active: bool,
    ) -> tuple[ExplorationState, list[object]]:
        puzzles = dict(state.puzzles)
        for puzzle_id, definition in self.puzzle_definitions.items():
            if not self._definition_matches_context(definition.scene_id, definition.location_id, current_scene_id, current_location_id):
                continue
            runtime = puzzles[puzzle_id]
            if definition.player_visible and not runtime.visible_to_party:
                puzzles[puzzle_id] = replace(runtime, visible_to_party=True)
        updated = replace(
            state,
            mode=self._mode_for_state(state, travel_active=travel_active),
            current_scene_id=current_scene_id,
            current_location_id=current_location_id,
            current_travel_map_id=current_travel_map_id,
            puzzles=puzzles,
        )
        updated, passive_events = self.refresh_passive_discovery(updated, encounter_state=encounter_state)
        events = list(passive_events)
        events.append(self._projection_event(updated))
        return updated, events

    def set_marching_order(self, state: ExplorationState, *, encounter_state: EncounterState, intent: SetMarchingOrderIntent) -> tuple[ExplorationState, list[object]]:
        actor_ids = self._validate_party_actor_ids(encounter_state, intent.actor_ids)
        entries = self._default_marching_order(actor_ids)
        updated = replace(state, marching_order=entries)
        updated, passive_events = self.refresh_passive_discovery(updated, encounter_state=encounter_state)
        return updated, [MarchingOrderUpdatedEvent(entries=entries), *passive_events, self._projection_event(updated)]

    def set_watch_order(self, state: ExplorationState, *, encounter_state: EncounterState, intent: SetWatchOrderIntent) -> tuple[ExplorationState, list[object]]:
        actor_ids = self._validate_party_actor_ids(encounter_state, intent.actor_ids)
        assignments = tuple(WatchAssignment(actor_id=actor_id, shift_index=index) for index, actor_id in enumerate(actor_ids))
        updated = replace(state, watch_order=assignments)
        return updated, [WatchOrderUpdatedEvent(assignments=assignments), self._projection_event(updated)]

    def assign_role(self, state: ExplorationState, *, encounter_state: EncounterState, intent: AssignExplorationRoleIntent) -> tuple[ExplorationState, list[object]]:
        actor_ids = self._validate_party_actor_ids(encounter_state, intent.actor_ids, allow_empty=True)
        roles = state.role_assignments
        if intent.role == ExplorationRole.NAVIGATOR:
            roles = replace(roles, navigator_actor_id=(actor_ids[0] if actor_ids else None))
        elif intent.role == ExplorationRole.SCOUT:
            roles = replace(roles, scout_actor_id=(actor_ids[0] if actor_ids else None))
        elif intent.role == ExplorationRole.LOOKOUT:
            roles = replace(roles, lookout_actor_ids=actor_ids)
        elif intent.role == ExplorationRole.SEARCH:
            roles = replace(roles, searching_actor_ids=actor_ids)
        elif intent.role == ExplorationRole.STUDY:
            roles = replace(roles, studying_actor_ids=actor_ids)
        elif intent.role == ExplorationRole.SNEAK:
            roles = replace(roles, sneaking_actor_ids=actor_ids)
        else:
            raise EncounterValidationError('Unknown exploration role assignment.')
        updated = replace(state, role_assignments=roles)
        updated, passive_events = self.refresh_passive_discovery(updated, encounter_state=encounter_state)
        return updated, [*passive_events, self._projection_event(updated)]

    def set_camp_state(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: SetCampStateIntent,
        travel_active: bool,
    ) -> tuple[ExplorationState, list[object]]:
        updated = replace(
            state,
            camp_active=intent.active,
            camp_started_at_seconds=(encounter_state.clock_seconds if intent.active else None),
        )
        updated = replace(updated, mode=self._mode_for_state(updated, travel_active=travel_active))
        return updated, [self._projection_event(updated)]

    def interpret_declaration(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        actor_id: str,
        declaration: str,
    ) -> ExplorationDeclarationPrompt | None:
        return interpret_exploration_declaration(
            self,
            state,
            encounter_state=encounter_state,
            actor_id=actor_id,
            declaration=declaration,
        )

    def resolve_pending_exploration_check(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        pending,
        check_request,
        d20_result,
        random_counter_used: int,
    ) -> tuple[ExplorationState, list[object]]:
        return apply_pending_exploration_check(
            self,
            state,
            encounter_state=encounter_state,
            pending=pending,
            check_request=check_request,
            d20_result=d20_result,
            random_counter_used=random_counter_used,
        )

    def attempt_social_influence(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: AttemptSocialInfluenceIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        profile = self._require_social_profile(intent.npc_id, state)
        approach = next((item for item in profile.approaches if item.approach == intent.approach), None)
        if approach is None:
            raise EncounterValidationError(f'{profile.display_name} does not support {intent.approach.value} in this scene.')
        resolution = self.kernel.resolve_ability_check(
            encounter_state,
            actor_id=actor.actor_id,
            ability=approach.ability,
            dc=approach.dc,
            skill_name=approach.skill_name,
            interacting_with_actor_id=(intent.npc_id if intent.npc_id in encounter_state.actors else None),
        )
        outcome = self._procedure_outcome(total=resolution.result.total, dc=approach.dc, partial_margin=approach.partial_margin)
        npc_states = dict(state.npc_states)
        current = npc_states[intent.npc_id]
        updated_npc = self._apply_social_outcome(current, profile, approach, outcome)
        npc_states[intent.npc_id] = updated_npc
        updated = replace(state, npc_states=npc_states)
        events: list[object] = [
            D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used),
            StoryCheckResolvedEvent(
                request_id=f'social:{intent.npc_id}:{intent.approach.value}:{resolution.random_counter_used}',
                actor_id=actor.actor_id,
                scene_id=state.current_scene_id,
                ability=approach.ability,
                skill_name=approach.skill_name,
                dc=approach.dc,
                selected_roll=resolution.result.selected_roll,
                total=resolution.result.total,
                success=(outcome != ProcedureOutcome.FAILURE),
                interacting_with_actor_id=(intent.npc_id if intent.npc_id in encounter_state.actors else None),
            ),
            SocialInfluenceAttemptedEvent(
                actor_id=actor.actor_id,
                npc_id=intent.npc_id,
                approach=intent.approach,
                dc=approach.dc,
                selected_roll=resolution.result.selected_roll,
                total=resolution.result.total,
                random_counter_used=resolution.random_counter_used,
            ),
            SocialInfluenceResolvedEvent(
                actor_id=actor.actor_id,
                npc_id=intent.npc_id,
                approach=intent.approach,
                outcome=self._social_outcome(outcome),
                summary=updated_npc.last_summary,
            ),
        ]
        if updated_npc.attitude != current.attitude or updated_npc.current_stance != current.current_stance:
            events.append(
                NPCStanceChangedEvent(
                    npc_id=intent.npc_id,
                    old_attitude=current.attitude,
                    new_attitude=updated_npc.attitude,
                    current_stance=updated_npc.current_stance,
                    summary=updated_npc.last_summary,
                )
            )
        newly_revealed = tuple(topic for topic in updated_npc.revealed_topics if topic not in current.revealed_topics)
        if newly_revealed:
            updated = self._merge_discoveries(updated, newly_revealed)
            for topic in newly_revealed:
                events.append(
                    DiscoveryRevealedEvent(
                        discovery_id=f'npc-topic:{intent.npc_id}:{slugify(topic)}',
                        text=topic,
                        source_category=ProcedureCategory.DISCOVERY,
                        actor_id=actor.actor_id,
                        public=True,
                    )
                )
        events.append(self._projection_event(updated))
        return updated, events

    def attempt_trap(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: AttemptTrapIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        definition = self._require_trap_definition(intent.trap_id, state)
        runtime = state.traps[intent.trap_id]
        traps = dict(state.traps)
        if intent.attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
            if definition.detect_procedure is None:
                raise EncounterValidationError('This trap does not define a detect procedure.')
            result = self._resolve_procedure_attempt(
                encounter_state=encounter_state,
                actor=actor,
                definition=definition.detect_procedure,
                progress=(runtime.detect_progress or self._initial_progress(definition.detect_procedure)),
                attempt_kind=intent.attempt_kind,
                tool_name=intent.tool_name,
                progress_multiplier=1,
                request_prefix=f'trap-detect:{definition.trap_id}',
                interacting_with_actor_id=None,
            )
            status = runtime.status
            visible = runtime.visible_to_party
            detected_by = runtime.detected_by_actor_ids
            if result.progress.status == ProcedureStatus.COMPLETED:
                status = TrapStatus.DETECTED
                visible = True
                detected_by = unique_strings(runtime.detected_by_actor_ids + (actor.actor_id,))
            traps[intent.trap_id] = replace(
                runtime,
                status=status,
                visible_to_party=visible,
                detected_by_actor_ids=detected_by,
                detect_progress=result.progress,
                last_summary=(definition.revealed_summary if status == TrapStatus.DETECTED else result.summary),
            )
            updated = replace(state, traps=traps)
            updated = self._merge_discoveries(updated, result.revealed_clues)
            events = list(result.events)
            if status == TrapStatus.DETECTED:
                events.append(
                    TrapDetectedEvent(
                        trap_id=definition.trap_id,
                        title=definition.title,
                        actor_id=actor.actor_id,
                        passive=False,
                        status=status,
                        summary=definition.revealed_summary,
                    )
                )
            events.append(self._projection_event(updated))
            return updated, events
        if intent.attempt_kind not in {ProcedureAttemptKind.DISARM, ProcedureAttemptKind.TOOL_USE}:
            raise EncounterValidationError('Trap attempts only support search, study, or disarm in this runtime.')
        if runtime.status not in {TrapStatus.DETECTED, TrapStatus.TRIGGERED}:
            raise EncounterValidationError('A trap must be detected or triggered before it can be disarmed.')
        if definition.disarm_procedure is None:
            raise EncounterValidationError('This trap does not define a disarm procedure.')
        result = self._resolve_procedure_attempt(
            encounter_state=encounter_state,
            actor=actor,
            definition=definition.disarm_procedure,
            progress=(runtime.disarm_progress or self._initial_progress(definition.disarm_procedure)),
            attempt_kind=intent.attempt_kind,
            tool_name=intent.tool_name,
            progress_multiplier=1,
            request_prefix=f'trap-disarm:{definition.trap_id}',
            interacting_with_actor_id=None,
        )
        trap_state = replace(
            runtime,
            status=(TrapStatus.DISARMED if result.progress.status == ProcedureStatus.COMPLETED else runtime.status),
            visible_to_party=True,
            disarmed_by_actor_id=(actor.actor_id if result.progress.status == ProcedureStatus.COMPLETED else runtime.disarmed_by_actor_id),
            disarm_progress=result.progress,
            last_summary=(definition.revealed_summary if result.progress.status == ProcedureStatus.COMPLETED else result.summary),
        )
        traps[intent.trap_id] = trap_state
        updated = replace(state, traps=traps)
        updated = self._merge_discoveries(updated, result.revealed_clues)
        events = list(result.events)
        if trap_state.status == TrapStatus.DISARMED:
            events.append(TrapDisarmedEvent(trap_id=definition.trap_id, title=definition.title, actor_id=actor.actor_id, summary=definition.revealed_summary))
        events.append(self._projection_event(updated))
        return updated, events

    def trigger_trap(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: TriggerTrapIntent,
    ) -> tuple[ExplorationState, list[object]]:
        definition = self._require_trap_definition(intent.trap_id, state)
        actor_id = intent.actor_id or self.exposed_actor_id(state)
        actor = self._require_party_actor(encounter_state, actor_id)
        runtime = state.traps[intent.trap_id]
        visible = runtime.visible_to_party or definition.reveal_on_trigger
        trap_state = replace(
            runtime,
            status=TrapStatus.TRIGGERED,
            visible_to_party=visible,
            triggered_by_actor_id=actor.actor_id,
            last_summary=definition.trigger_summary,
        )
        traps = dict(state.traps)
        traps[intent.trap_id] = trap_state
        updated = replace(state, traps=traps)
        updated = self._merge_discoveries(updated, (definition.trigger_summary,))
        return updated, [
            TrapTriggeredEvent(trap_id=definition.trap_id, title=definition.title, actor_id=actor.actor_id, summary=definition.trigger_summary),
            self._projection_event(updated),
        ]

    def bypass_trap(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: BypassTrapIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        definition = self._require_trap_definition(intent.trap_id, state)
        runtime = state.traps[intent.trap_id]
        if runtime.status not in {TrapStatus.DETECTED, TrapStatus.TRIGGERED, TrapStatus.BYPASSED}:
            raise EncounterValidationError('A trap must be detected or triggered before it can be bypassed safely.')
        bypassed = unique_strings(runtime.bypassed_by_actor_ids + (actor.actor_id,))
        status = TrapStatus.BYPASSED if set(bypassed) >= set(self.party_actor_ids(encounter_state)) else runtime.status
        traps = dict(state.traps)
        traps[intent.trap_id] = replace(runtime, bypassed_by_actor_ids=bypassed, status=status, visible_to_party=True, last_summary=f'{actor.name} bypasses {definition.title}.')
        updated = replace(state, traps=traps)
        return updated, [self._projection_event(updated)]

    def attempt_puzzle(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: AttemptPuzzleIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        definition = self._require_puzzle_definition(intent.puzzle_id, state)
        runtime = state.puzzles[intent.puzzle_id]
        puzzles = dict(state.puzzles)
        if intent.attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
            if definition.study_procedure is None:
                raise EncounterValidationError('This puzzle does not define a study procedure.')
            result = self._resolve_procedure_attempt(
                encounter_state=encounter_state,
                actor=actor,
                definition=definition.study_procedure,
                progress=(runtime.study_progress or self._initial_progress(definition.study_procedure)),
                attempt_kind=intent.attempt_kind,
                tool_name=intent.tool_name,
                progress_multiplier=1,
                request_prefix=f'puzzle-study:{definition.puzzle_id}',
                interacting_with_actor_id=None,
            )
            puzzles[intent.puzzle_id] = replace(runtime, status=PuzzleStatus.IN_PROGRESS, visible_to_party=True, study_progress=result.progress, last_summary=result.summary)
            updated = replace(state, puzzles=puzzles)
            updated = self._merge_discoveries(updated, result.revealed_clues)
            events = list(result.events)
            events.append(PuzzleProgressedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, status=PuzzleStatus.IN_PROGRESS, summary=result.summary))
            events.append(self._projection_event(updated))
            return updated, events
        if intent.attempt_kind != ProcedureAttemptKind.SOLVE:
            raise EncounterValidationError('Puzzles support search, study, or solve in this runtime.')
        if definition.solve_procedure is None:
            raise EncounterValidationError('This puzzle does not define a solve procedure.')
        result = self._resolve_procedure_attempt(
            encounter_state=encounter_state,
            actor=actor,
            definition=definition.solve_procedure,
            progress=(runtime.solve_progress or self._initial_progress(definition.solve_procedure)),
            attempt_kind=intent.attempt_kind,
            tool_name=intent.tool_name,
            progress_multiplier=1,
            request_prefix=f'puzzle-solve:{definition.puzzle_id}',
            interacting_with_actor_id=None,
        )
        solved = result.progress.status == ProcedureStatus.COMPLETED
        status = PuzzleStatus.SOLVED if solved else PuzzleStatus.IN_PROGRESS
        puzzles[intent.puzzle_id] = replace(runtime, status=status, visible_to_party=True, solve_progress=result.progress, last_summary=result.summary)
        updated = replace(state, puzzles=puzzles)
        updated = self._merge_discoveries(updated, result.revealed_clues)
        events = list(result.events)
        if solved:
            events.append(PuzzleSolvedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, summary=result.summary))
        else:
            events.append(PuzzleProgressedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, status=status, summary=result.summary))
        events.append(self._projection_event(updated))
        return updated, events

    def abandon_puzzle(self, state: ExplorationState, *, intent: AbandonPuzzleIntent) -> tuple[ExplorationState, list[object]]:
        definition = self._require_puzzle_definition(intent.puzzle_id, state)
        puzzles = dict(state.puzzles)
        runtime = puzzles[intent.puzzle_id]
        puzzles[intent.puzzle_id] = replace(runtime, status=PuzzleStatus.ABANDONED, visible_to_party=True, last_summary=f'The party sets aside {definition.title} for now.')
        updated = replace(state, puzzles=puzzles)
        return updated, [self._projection_event(updated)]

    def start_downtime_project(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: StartDowntimeProjectIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        activity = self._require_downtime_activity(intent.activity_id, state)
        project_id = f'{activity.activity_id}:{actor.actor_id}'
        if project_id in state.downtime_projects and state.downtime_projects[project_id].status == DowntimeProjectStatus.IN_PROGRESS:
            raise EncounterValidationError('That downtime project is already in progress for the actor.')
        projects = dict(state.downtime_projects)
        projects[project_id] = DowntimeProjectState(
            project_id=project_id,
            activity_id=activity.activity_id,
            actor_id=actor.actor_id,
            title=activity.title,
            progress_state=(self._initial_progress(activity.work_procedure) if activity.work_procedure is not None else None),
            elapsed_hours=0,
            last_summary=activity.summary,
        )
        updated = replace(state, downtime_projects=projects, mode=ExplorationMode.DOWNTIME)
        return updated, [DowntimeProjectStartedEvent(project_id=project_id, activity_id=activity.activity_id, actor_id=actor.actor_id, title=activity.title), self._projection_event(updated)]

    def work_downtime_project(
        self,
        state: ExplorationState,
        *,
        encounter_state: EncounterState,
        intent: WorkDowntimeProjectIntent,
    ) -> tuple[ExplorationState, list[object]]:
        actor = self._require_party_actor(encounter_state, intent.actor_id)
        if intent.hours <= 0:
            raise EncounterValidationError('Downtime work requires at least one hour.')
        project = state.downtime_projects.get(intent.project_id)
        if project is None:
            raise EncounterValidationError('Unknown downtime project id.')
        if project.actor_id != actor.actor_id:
            raise EncounterValidationError('Only the owning actor may work that downtime project.')
        if project.status != DowntimeProjectStatus.IN_PROGRESS:
            raise EncounterValidationError('That downtime project is no longer in progress.')
        activity = self._require_downtime_activity(project.activity_id, state)
        if activity.work_procedure is None:
            raise EncounterValidationError('This downtime activity does not define a work procedure.')
        result = self._resolve_procedure_attempt(
            encounter_state=encounter_state,
            actor=actor,
            definition=activity.work_procedure,
            progress=(project.progress_state or self._initial_progress(activity.work_procedure)),
            attempt_kind=ProcedureAttemptKind.WORK,
            tool_name=intent.tool_name,
            progress_multiplier=intent.hours,
            request_prefix=f'downtime:{project.project_id}',
            interacting_with_actor_id=None,
        )
        completed = result.progress.status == ProcedureStatus.COMPLETED
        projects = dict(state.downtime_projects)
        projects[intent.project_id] = replace(
            project,
            status=(DowntimeProjectStatus.COMPLETED if completed else DowntimeProjectStatus.IN_PROGRESS),
            progress_state=result.progress,
            elapsed_hours=project.elapsed_hours + intent.hours,
            last_summary=result.summary,
        )
        updated = replace(state, downtime_projects=projects)
        updated = replace(updated, mode=self._mode_for_state(updated, travel_active=False))
        updated = self._merge_discoveries(updated, result.revealed_clues)
        project_state = projects[intent.project_id]
        events = [self._time_advance_event(hours=intent.hours), *result.events]
        if completed:
            events.append(DowntimeProjectCompletedEvent(project_id=project.project_id, activity_id=project.activity_id, actor_id=actor.actor_id, elapsed_hours=project_state.elapsed_hours, summary=result.summary))
        else:
            events.append(DowntimeProjectProgressedEvent(project_id=project.project_id, activity_id=project.activity_id, actor_id=actor.actor_id, status=project_state.status, elapsed_hours=project_state.elapsed_hours, summary=result.summary))
        events.append(self._projection_event(updated))
        return updated, events

    def cancel_downtime_project(self, state: ExplorationState, *, intent: CancelDowntimeProjectIntent) -> tuple[ExplorationState, list[object]]:
        project = state.downtime_projects.get(intent.project_id)
        if project is None:
            raise EncounterValidationError('Unknown downtime project id.')
        projects = dict(state.downtime_projects)
        projects[intent.project_id] = replace(project, status=DowntimeProjectStatus.CANCELLED, last_summary=f'{project.title} is set aside for now.')
        updated = replace(state, downtime_projects=projects)
        updated = replace(updated, mode=self._mode_for_state(updated, travel_active=False))
        return updated, [self._projection_event(updated)]

    def refresh_passive_discovery(self, state: ExplorationState, *, encounter_state: EncounterState) -> tuple[ExplorationState, list[object]]:
        traps = dict(state.traps)
        known_discoveries = state.known_discoveries
        events: list[object] = []
        for trap_id, definition in self.trap_definitions.items():
            if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
                continue
            if definition.passive_notice_dc is None:
                continue
            runtime = traps[trap_id]
            if runtime.status not in {TrapStatus.HIDDEN, TrapStatus.DETECTABLE}:
                continue
            for actor_id in self.discovery_priority_actor_ids(state):
                actor = encounter_state.actors.get(actor_id)
                if actor is None or actor.side != ActorSide.PLAYER or not actor.is_conscious:
                    continue
                if actor.passive_perception < definition.passive_notice_dc:
                    continue
                traps[trap_id] = replace(
                    runtime,
                    status=TrapStatus.DETECTED,
                    visible_to_party=True,
                    detected_by_actor_ids=unique_strings(runtime.detected_by_actor_ids + (actor.actor_id,)),
                    last_summary=definition.revealed_summary,
                )
                known_discoveries = unique_strings(known_discoveries + (definition.revealed_summary,))
                events.append(TrapDetectedEvent(trap_id=definition.trap_id, title=definition.title, actor_id=actor.actor_id, passive=True, status=TrapStatus.DETECTED, summary=definition.revealed_summary))
                events.append(DiscoveryRevealedEvent(discovery_id=f'trap:{definition.trap_id}:noticed', text=definition.revealed_summary, source_category=ProcedureCategory.TRAP, actor_id=actor.actor_id, public=True))
                break
        return replace(state, traps=traps, known_discoveries=known_discoveries), events

    def active_watch_shift_index(self, state: ExplorationState, *, encounter_state: EncounterState) -> int | None:
        if not state.camp_active or state.camp_started_at_seconds is None or not state.watch_order:
            return None
        shift_count = max(assignment.shift_index for assignment in state.watch_order) + 1
        elapsed = max(0, encounter_state.clock_seconds - state.camp_started_at_seconds)
        return int((elapsed // state.watch_shift_seconds) % max(shift_count, 1))

    def active_watchers(self, state: ExplorationState, *, encounter_state: EncounterState) -> tuple[str, ...]:
        active_shift = self.active_watch_shift_index(state, encounter_state=encounter_state)
        if active_shift is None:
            return ()
        return tuple(assignment.actor_id for assignment in state.watch_order if assignment.shift_index == active_shift)

    def exposed_actor_id(self, state: ExplorationState) -> str:
        if state.role_assignments.scout_actor_id:
            return state.role_assignments.scout_actor_id
        if not state.marching_order:
            raise EncounterValidationError('No marching order is configured for the party.')
        return sorted(state.marching_order, key=lambda item: item.ordinal)[0].actor_id

    def discovery_priority_actor_ids(self, state: ExplorationState) -> tuple[str, ...]:
        ordered: list[str] = []
        if state.role_assignments.scout_actor_id is not None:
            ordered.append(state.role_assignments.scout_actor_id)
        ordered.extend(entry.actor_id for entry in sorted(state.marching_order, key=lambda item: item.ordinal))
        ordered.extend(state.role_assignments.lookout_actor_ids)
        ordered.extend(state.role_assignments.searching_actor_ids)
        return tuple(unique_strings(tuple(ordered)))

    def party_actor_ids(self, encounter_state: EncounterState) -> tuple[str, ...]:
        return tuple(actor_id for actor_id, actor in encounter_state.actors.items() if actor.side == ActorSide.PLAYER)

    def visible_npc_states(self, state: ExplorationState) -> tuple[NpcInfluenceState, ...]:
        return tuple(
            state.npc_states[npc_id]
            for npc_id, profile in sorted(self.social_profiles.items(), key=lambda item: item[1].display_name)
            if self._definition_matches_context_any(profile.scene_ids, profile.location_ids, state.current_scene_id, state.current_location_id)
        )

    def apply_spellcasting_reactions(
        self,
        state: ExplorationState,
        *,
        reactions: tuple[SpellcastingWitnessReaction, ...],
    ) -> tuple[ExplorationState, list[object]]:
        if not reactions:
            return state, []
        npc_states = dict(state.npc_states)
        events: list[object] = []
        changed = False
        for reaction in reactions:
            current = npc_states.get(reaction.witness_id)
            profile = self.social_profiles.get(reaction.witness_id)
            if current is None or profile is None:
                continue
            updated = self._apply_spellcasting_reaction(current, profile, reaction)
            npc_states[reaction.witness_id] = updated
            changed = True
            if updated.attitude != current.attitude or updated.current_stance != current.current_stance:
                events.append(
                    NPCStanceChangedEvent(
                        npc_id=reaction.witness_id,
                        old_attitude=current.attitude,
                        new_attitude=updated.attitude,
                        current_stance=updated.current_stance,
                        summary=updated.last_summary,
                    )
                )
        if not changed:
            return state, []
        updated_state = replace(state, npc_states=npc_states)
        events.append(self._projection_event(updated_state))
        return updated_state, events

    def visible_trap_states(self, state: ExplorationState, *, dm_view: bool) -> tuple[tuple[TrapDefinition, TrapRuntimeState], ...]:
        visible: list[tuple[TrapDefinition, TrapRuntimeState]] = []
        for trap_id, definition in sorted(self.trap_definitions.items(), key=lambda item: item[1].title):
            if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
                continue
            runtime = state.traps[trap_id]
            if not dm_view and not runtime.visible_to_party:
                continue
            visible.append((definition, runtime))
        return tuple(visible)

    def visible_puzzle_states(self, state: ExplorationState, *, dm_view: bool) -> tuple[tuple[PuzzleDefinition, PuzzleRuntimeState], ...]:
        visible: list[tuple[PuzzleDefinition, PuzzleRuntimeState]] = []
        for puzzle_id, definition in sorted(self.puzzle_definitions.items(), key=lambda item: item[1].title):
            if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
                continue
            runtime = state.puzzles[puzzle_id]
            if not dm_view and not runtime.visible_to_party and not definition.player_visible:
                continue
            visible.append((definition, runtime))
        return tuple(visible)

    def visible_downtime_projects(self, state: ExplorationState, *, actor_ids: tuple[str, ...], dm_view: bool) -> tuple[DowntimeProjectState, ...]:
        projects = []
        for project in state.downtime_projects.values():
            if dm_view or project.actor_id in actor_ids:
                projects.append(project)
        return tuple(sorted(projects, key=lambda item: (item.actor_id, item.project_id)))

    def available_downtime_activities(self, state: ExplorationState) -> tuple[DowntimeActivityDefinition, ...]:
        return tuple(
            activity
            for activity in sorted(self.downtime_activities.values(), key=lambda item: item.title)
            if self._definition_matches_context(activity.scene_id, activity.location_id, state.current_scene_id, state.current_location_id)
        )

    def _default_marching_order(self, actor_ids: tuple[str, ...]) -> tuple[MarchingOrderEntry, ...]:
        entries: list[MarchingOrderEntry] = []
        total = len(actor_ids)
        for index, actor_id in enumerate(actor_ids):
            if total == 1:
                position = MarchPosition.SCOUT
            elif index == 0:
                position = MarchPosition.SCOUT
            elif index == 1:
                position = MarchPosition.FRONT
            elif index == total - 1:
                position = MarchPosition.REAR
            else:
                position = MarchPosition.CENTER
            entries.append(MarchingOrderEntry(actor_id=actor_id, position=position, ordinal=index))
        return tuple(entries)

    def _mode_for_state(self, state: ExplorationState, *, travel_active: bool) -> ExplorationMode:
        if state.camp_active:
            return ExplorationMode.CAMP
        if any(project.status == DowntimeProjectStatus.IN_PROGRESS for project in state.downtime_projects.values()):
            return ExplorationMode.DOWNTIME
        if travel_active:
            return ExplorationMode.TRAVEL
        return ExplorationMode.SCENE

    def _projection_event(self, state: ExplorationState) -> ExplorationStateProjectionUpdatedEvent:
        return ExplorationStateProjectionUpdatedEvent(mode=state.mode.value, scene_id=state.current_scene_id, location_id=state.current_location_id)

    def _require_party_actor(self, encounter_state: EncounterState, actor_id: str) -> RuntimeActorState:
        actor = encounter_state.actors.get(actor_id)
        if actor is None or actor.side != ActorSide.PLAYER:
            raise EncounterValidationError(f'Unknown party actor: {actor_id}.')
        return actor

    def _validate_party_actor_ids(self, encounter_state: EncounterState, actor_ids: tuple[str, ...], *, allow_empty: bool = False) -> tuple[str, ...]:
        if not actor_ids and not allow_empty:
            raise EncounterValidationError('At least one party actor id is required.')
        seen: set[str] = set()
        ordered: list[str] = []
        for actor_id in actor_ids:
            if actor_id in seen:
                raise EncounterValidationError('Party actor selections may not include duplicates.')
            self._require_party_actor(encounter_state, actor_id)
            seen.add(actor_id)
            ordered.append(actor_id)
        return tuple(ordered)

    def _require_social_profile(self, npc_id: str, state: ExplorationState) -> NpcInfluenceProfile:
        profile = self.social_profiles.get(npc_id)
        if profile is None:
            raise EncounterValidationError(f'Unknown NPC influence profile: {npc_id}.')
        if not self._definition_matches_context_any(profile.scene_ids, profile.location_ids, state.current_scene_id, state.current_location_id):
            raise EncounterValidationError(f'{profile.display_name} is not an active social target in the current scene or location.')
        return profile

    def _require_trap_definition(self, trap_id: str, state: ExplorationState) -> TrapDefinition:
        definition = self.trap_definitions.get(trap_id)
        if definition is None:
            raise EncounterValidationError(f'Unknown trap id: {trap_id}.')
        if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
            raise EncounterValidationError(f'{definition.title} is not active in the current scene or location.')
        return definition

    def _require_puzzle_definition(self, puzzle_id: str, state: ExplorationState) -> PuzzleDefinition:
        definition = self.puzzle_definitions.get(puzzle_id)
        if definition is None:
            raise EncounterValidationError(f'Unknown puzzle id: {puzzle_id}.')
        if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
            raise EncounterValidationError(f'{definition.title} is not active in the current scene or location.')
        return definition

    def _require_downtime_activity(self, activity_id: str, state: ExplorationState) -> DowntimeActivityDefinition:
        definition = self.downtime_activities.get(activity_id)
        if definition is None:
            raise EncounterValidationError(f'Unknown downtime activity id: {activity_id}.')
        if not self._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id):
            raise EncounterValidationError(f'{definition.title} is not available in the current scene or location.')
        return definition

    def _definition_matches_context(self, scene_id: str | None, location_id: str | None, current_scene_id: str | None, current_location_id: str | None) -> bool:
        scene_match = scene_id is None or scene_id == current_scene_id
        location_match = location_id is None or location_id == current_location_id
        return scene_match and location_match

    def _definition_matches_context_any(self, scene_ids: tuple[str, ...], location_ids: tuple[str, ...], current_scene_id: str | None, current_location_id: str | None) -> bool:
        scene_match = (not scene_ids) or (current_scene_id in scene_ids)
        location_match = (not location_ids) or (current_location_id in location_ids)
        return scene_match and location_match

    def _initial_progress(self, definition: ProcedureDefinition | None) -> ProcedureProgressState:
        if definition is None:
            raise EncounterValidationError('A progress definition is required.')
        return ProcedureProgressState(
            procedure_id=definition.procedure_id,
            title=definition.title,
            category=definition.category,
            status=ProcedureStatus.NOT_STARTED,
            progress_points=0,
            required_progress_points=definition.required_progress_points,
            attempt_count=0,
            failure_count=0,
            revealed_clues=(),
            last_summary=definition.summary,
        )

    def _resolve_procedure_attempt(
        self,
        *,
        encounter_state: EncounterState,
        actor: RuntimeActorState,
        definition: ProcedureDefinition,
        progress: ProcedureProgressState,
        attempt_kind: ProcedureAttemptKind,
        tool_name: str | None,
        progress_multiplier: int,
        request_prefix: str,
        interacting_with_actor_id: str | None,
    ) -> ProcedureAttemptResult:
        option, canonical_tool_name = self._select_procedure_option(actor, definition, attempt_kind, tool_name)
        resolution = self.kernel.resolve_ability_check(
            encounter_state,
            actor_id=actor.actor_id,
            ability=option.ability,
            dc=option.dc,
            skill_name=option.skill_name,
            interacting_with_actor_id=interacting_with_actor_id,
        )
        outcome = self._procedure_outcome(total=resolution.result.total, dc=option.dc, partial_margin=option.partial_margin)
        revealed = self._revealed_clues_for_outcome(option, outcome)
        newly_revealed = tuple(clue for clue in revealed if clue not in set(progress.revealed_clues))
        merged_clues = unique_strings(progress.revealed_clues + newly_revealed)
        progress_gain = self._progress_for_outcome(option, outcome) * max(1, progress_multiplier)
        total_progress = progress.progress_points + progress_gain
        status = ProcedureStatus.IN_PROGRESS
        if total_progress >= progress.required_progress_points:
            status = ProcedureStatus.COMPLETED
        elif outcome == ProcedureOutcome.FAILURE and not definition.repeatable:
            status = ProcedureStatus.FAILED
        summary = self._procedure_summary(definition, option, outcome, newly_revealed, completed=(status == ProcedureStatus.COMPLETED))
        new_progress = replace(
            progress,
            status=status,
            progress_points=total_progress,
            attempt_count=progress.attempt_count + 1,
            failure_count=progress.failure_count + (1 if outcome == ProcedureOutcome.FAILURE else 0),
            revealed_clues=merged_clues,
            last_summary=summary,
        )
        events: list[object] = []
        if progress.status == ProcedureStatus.NOT_STARTED:
            events.append(ExplorationProcedureStartedEvent(procedure_id=definition.procedure_id, title=definition.title, category=definition.category, actor_id=actor.actor_id, summary=definition.summary))
        if canonical_tool_name is not None:
            events.append(ToolUseDeclaredEvent(actor_id=actor.actor_id, tool_name=canonical_tool_name, target_id=definition.procedure_id, target_category=definition.category))
        events.append(D20TestRolledEvent(actor_id=actor.actor_id, result=resolution.result, random_counter_used=resolution.random_counter_used))
        events.append(StoryCheckResolvedEvent(request_id=f'{request_prefix}:{resolution.random_counter_used}', actor_id=actor.actor_id, scene_id=definition.scene_id, ability=option.ability, skill_name=option.skill_name, dc=option.dc, selected_roll=resolution.result.selected_roll, total=resolution.result.total, success=(outcome != ProcedureOutcome.FAILURE), interacting_with_actor_id=interacting_with_actor_id))
        if canonical_tool_name is not None:
            events.append(ToolUseResolvedEvent(actor_id=actor.actor_id, tool_name=canonical_tool_name, target_id=definition.procedure_id, target_category=definition.category, outcome=outcome, summary=summary))
        events.append(ExplorationProcedureProgressedEvent(procedure_id=definition.procedure_id, title=definition.title, category=definition.category, actor_id=actor.actor_id, status=new_progress.status, progress_points=new_progress.progress_points, required_progress_points=new_progress.required_progress_points, summary=summary))
        if new_progress.status == ProcedureStatus.COMPLETED:
            events.append(ExplorationProcedureCompletedEvent(procedure_id=definition.procedure_id, title=definition.title, category=definition.category, actor_id=actor.actor_id, summary=summary))
        for clue in newly_revealed:
            events.append(DiscoveryRevealedEvent(discovery_id=f'{definition.procedure_id}:{slugify(clue)}', text=clue, source_category=definition.category, actor_id=actor.actor_id, public=definition.player_visible))
        return ProcedureAttemptResult(progress=new_progress, outcome=outcome, summary=summary, revealed_clues=newly_revealed, events=tuple(events))

    def _select_procedure_option(self, actor: RuntimeActorState, definition: ProcedureDefinition, attempt_kind: ProcedureAttemptKind, tool_name: str | None) -> tuple[ProcedureCheckOption, str | None]:
        options = [option for option in definition.attempt_options if option.attempt_kind == attempt_kind]
        if not options:
            raise EncounterValidationError(f'{definition.title} does not support the {attempt_kind.value} procedure.')
        canonical_tool_name = None
        if tool_name is not None:
            canonical_tool_name = self._resolve_tool_name(tool_name, options)
            options = [option for option in options if option.tool_name is None or option.tool_name == canonical_tool_name]
            if not options:
                valid = ', '.join(sorted(option.tool_name or 'no-tool' for option in definition.attempt_options if option.attempt_kind == attempt_kind))
                raise EncounterValidationError(f'{definition.title} does not support {tool_name!r} for {attempt_kind.value}. Valid tools: {valid}.')
        elif options and all(option.tool_name is not None for option in options):
            valid = ', '.join(sorted(option.tool_name for option in options if option.tool_name is not None))
            raise EncounterValidationError(f'{definition.title} requires an explicit tool choice for {attempt_kind.value}. Valid tools: {valid}.')
        option = options[0]
        if option.tool_name is not None and canonical_tool_name is None:
            canonical_tool_name = option.tool_name
        if option.tool_name is not None and option.requires_tool_proficiency and not self._actor_has_tool_proficiency(actor, option.tool_name):
            raise EncounterValidationError(f'{actor.name} is not proficient with {option.tool_name}.')
        return option, canonical_tool_name

    def _resolve_tool_name(self, tool_name: str, options: list[ProcedureCheckOption]) -> str:
        normalized = slugify(tool_name)
        valid_names = {option.tool_name for option in options if option.tool_name is not None}
        for name in valid_names:
            if slugify(name) == normalized:
                return name
        valid = ', '.join(sorted(valid_names)) or 'none'
        raise EncounterValidationError(f'Unknown tool {tool_name!r} for this procedure. Valid tools: {valid}.')

    def _actor_has_tool_proficiency(self, actor: RuntimeActorState, tool_name: str) -> bool:
        record = actor.character_record
        if record is None:
            return False
        names = list(record.tool_proficiencies)
        for selection in record.proficiency_selections:
            if getattr(selection.category, 'value', '') == 'tool':
                names.append(selection.name)
        wanted = slugify(tool_name)
        return any(slugify(name) == wanted for name in names)


    def _procedure_outcome(self, *, total: int, dc: int, partial_margin: int) -> ProcedureOutcome:
        if total >= dc:
            return ProcedureOutcome.SUCCESS
        if partial_margin > 0 and total >= (dc - partial_margin):
            return ProcedureOutcome.PARTIAL
        return ProcedureOutcome.FAILURE

    def _social_outcome(self, outcome: ProcedureOutcome) -> SocialOutcome:
        if outcome == ProcedureOutcome.SUCCESS:
            return SocialOutcome.SUCCESS
        if outcome == ProcedureOutcome.PARTIAL:
            return SocialOutcome.PARTIAL
        return SocialOutcome.FAILURE

    def _progress_for_outcome(self, option: ProcedureCheckOption, outcome: ProcedureOutcome) -> int:
        if outcome == ProcedureOutcome.SUCCESS:
            return option.progress_on_success
        if outcome == ProcedureOutcome.PARTIAL:
            return option.progress_on_partial
        return option.progress_on_failure

    def _revealed_clues_for_outcome(self, option: ProcedureCheckOption, outcome: ProcedureOutcome) -> tuple[str, ...]:
        if outcome == ProcedureOutcome.SUCCESS:
            return option.revealed_clues_on_success
        if outcome == ProcedureOutcome.PARTIAL:
            return option.revealed_clues_on_partial
        return option.revealed_clues_on_failure

    def _procedure_summary(
        self,
        definition: ProcedureDefinition,
        option: ProcedureCheckOption,
        outcome: ProcedureOutcome,
        newly_revealed: tuple[str, ...],
        *,
        completed: bool,
    ) -> str:
        check_label = option.skill_name or option.ability.value.title()
        if outcome == ProcedureOutcome.SUCCESS:
            summary = f'{definition.title}: {check_label} succeeds.'
        elif outcome == ProcedureOutcome.PARTIAL:
            summary = f'{definition.title}: {check_label} makes partial progress.'
        else:
            summary = option.failure_note or f'{definition.title}: {check_label} fails to make headway.'
        if newly_revealed:
            summary = f"{summary} Learned: {'; '.join(newly_revealed)}."
        if completed and definition.completion_note:
            summary = f'{summary} {definition.completion_note}'.strip()
        elif completed:
            summary = f'{summary} {definition.title} is completed.'.strip()
        return summary


    def _apply_spellcasting_reaction(
        self,
        current: NpcInfluenceState,
        profile: NpcInfluenceProfile,
        reaction: SpellcastingWitnessReaction,
    ) -> NpcInfluenceState:
        trust = current.trust
        hostility = current.hostility
        leverage = current.leverage
        obligation = current.obligation
        fear = current.fear
        interest = current.interest
        category = reaction.reaction_category
        if category == SpellcastingReactionCategory.CURIOUS:
            interest += 1
        elif category == SpellcastingReactionCategory.MILDLY_WARY:
            hostility += 1
        elif category == SpellcastingReactionCategory.SOCIALLY_DISAPPROVING:
            hostility += 1
            trust -= 1
        elif category == SpellcastingReactionCategory.SUSPICIOUS:
            hostility += 1
            fear += 1
            trust -= 1
        elif category == SpellcastingReactionCategory.ALARMED:
            hostility += 2
            fear += 2
        elif category == SpellcastingReactionCategory.CONFRONTATIONAL:
            hostility += 2
            fear += 1
        elif category == SpellcastingReactionCategory.HOSTILE:
            hostility += 4
        elif category == SpellcastingReactionCategory.ESCALATES_TO_MODE_SWITCH_CANDIDATE:
            hostility += 3
            fear += 1
        attitude = self._attitude_from_metrics(
            profile.base_attitude,
            trust=trust,
            hostility=hostility,
            leverage=leverage,
            obligation=obligation,
            fear=fear,
            interest=interest,
        )
        stance = self._stance_from_attitude(
            profile,
            attitude=attitude,
            trust=trust,
            hostility=hostility,
            leverage=leverage,
            obligation=obligation,
            fear=fear,
            interest=interest,
        )
        return replace(
            current,
            attitude=attitude,
            current_stance=stance,
            trust=trust,
            hostility=hostility,
            leverage=leverage,
            obligation=obligation,
            fear=fear,
            interest=interest,
            last_summary=reaction.summary,
        )

    def _apply_social_outcome(
        self,
        current: NpcInfluenceState,
        profile: NpcInfluenceProfile,
        approach: SocialApproachDefinition,
        outcome: ProcedureOutcome,
    ) -> NpcInfluenceState:
        if outcome == ProcedureOutcome.SUCCESS:
            trust_delta = approach.trust_on_success
            hostility_delta = approach.hostility_on_success
            leverage_delta = approach.leverage_on_success
            obligation_delta = approach.obligation_on_success
            fear_delta = approach.fear_on_success
            interest_delta = approach.interest_on_success
            summary = approach.success_summary or f'{profile.display_name} responds well.'
            revealed_topics = approach.revealed_topics_on_success
        elif outcome == ProcedureOutcome.PARTIAL:
            trust_delta = approach.trust_on_partial
            hostility_delta = approach.hostility_on_partial
            leverage_delta = approach.leverage_on_partial
            obligation_delta = approach.obligation_on_partial
            fear_delta = approach.fear_on_partial
            interest_delta = approach.interest_on_partial
            summary = approach.partial_summary or f'{profile.display_name} yields a little, but stays guarded.'
            revealed_topics = approach.revealed_topics_on_partial
        else:
            trust_delta = approach.trust_on_failure
            hostility_delta = approach.hostility_on_failure
            leverage_delta = approach.leverage_on_failure
            obligation_delta = approach.obligation_on_failure
            fear_delta = approach.fear_on_failure
            interest_delta = approach.interest_on_failure
            summary = approach.failure_summary or f'{profile.display_name} rejects the attempt.'
            revealed_topics = approach.revealed_topics_on_failure
        trust = current.trust + trust_delta
        hostility = current.hostility + hostility_delta
        leverage = current.leverage + leverage_delta
        obligation = current.obligation + obligation_delta
        fear = current.fear + fear_delta
        interest = current.interest + interest_delta
        attitude = self._attitude_from_metrics(profile.base_attitude, trust=trust, hostility=hostility, leverage=leverage, obligation=obligation, fear=fear, interest=interest)
        stance = self._stance_from_attitude(profile, attitude=attitude, trust=trust, hostility=hostility, leverage=leverage, obligation=obligation, fear=fear, interest=interest)
        topics = unique_strings(current.revealed_topics + revealed_topics)
        return replace(
            current,
            attitude=attitude,
            current_stance=stance,
            trust=trust,
            hostility=hostility,
            leverage=leverage,
            obligation=obligation,
            fear=fear,
            interest=interest,
            revealed_topics=topics,
            last_summary=summary,
        )

    def _attitude_from_metrics(
        self,
        base_attitude: NpcAttitude,
        *,
        trust: int,
        hostility: int,
        leverage: int,
        obligation: int,
        fear: int,
        interest: int,
    ) -> NpcAttitude:
        base_score = {
            NpcAttitude.FRIENDLY: 2,
            NpcAttitude.COOPERATIVE: 1,
            NpcAttitude.RESERVED: 0,
            NpcAttitude.WARY: -1,
            NpcAttitude.HOSTILE: -2,
        }[base_attitude]
        score = base_score + trust + leverage + obligation + interest - hostility - max(0, fear // 2)
        if hostility >= 4:
            return NpcAttitude.HOSTILE
        if score >= 4:
            return NpcAttitude.FRIENDLY
        if score >= 2:
            return NpcAttitude.COOPERATIVE
        if score >= 0:
            return NpcAttitude.RESERVED
        if score >= -2:
            return NpcAttitude.WARY
        return NpcAttitude.HOSTILE

    def _stance_from_attitude(
        self,
        profile: NpcInfluenceProfile,
        *,
        attitude: NpcAttitude,
        trust: int,
        hostility: int,
        leverage: int,
        obligation: int,
        fear: int,
        interest: int,
    ) -> str:
        if attitude == NpcAttitude.FRIENDLY:
            return 'Open, forthcoming, and ready to help.'
        if attitude == NpcAttitude.COOPERATIVE:
            if leverage > 0 or obligation > 0:
                return 'Cautiously cooperative, willing to bargain in good faith.'
            return 'Cautiously cooperative.'
        if attitude == NpcAttitude.WARY:
            if fear > 0:
                return 'Guarded and off-balance, watching for the next move.'
            return 'Guarded and reluctant.'
        if attitude == NpcAttitude.HOSTILE:
            return 'Closed off and openly hostile to further pressure.'
        if trust > 0 and interest > 0:
            return 'Reserved, but listening closely.'
        if hostility > 0:
            return 'Reserved and clearly irritated.'
        return profile.base_stance

    def _merge_discoveries(self, state: ExplorationState, discoveries: tuple[str, ...]) -> ExplorationState:
        if not discoveries:
            return state
        return replace(state, known_discoveries=unique_strings(state.known_discoveries + discoveries))

    def _time_advance_event(self, *, hours: int) -> TimeAdvancedEvent:
        return TimeAdvancedEvent(elapsed_seconds=hours * 60 * 60, activity_type=RestActivityType.LIGHT_ACTIVITY)


def _lmop_social_profiles() -> tuple[NpcInfluenceProfile, ...]:
    return (
        NpcInfluenceProfile(
            npc_id='gundren-rockseeker',
            display_name='Gundren Rockseeker',
            base_attitude=NpcAttitude.RESERVED,
            base_stance='Eager to hire the party, but protective of the full truth.',
            scene_ids=('scene-waterdeep-gundren-briefing',),
            location_ids=('waterdeep',),
            approaches=(
                SocialApproachDefinition(
                    approach=SocialApproachType.PERSUADE,
                    ability=Ability.CHA,
                    skill_name='Persuasion',
                    dc=14,
                    trust_on_success=1,
                    obligation_on_success=1,
                    interest_on_success=1,
                    trust_on_partial=1,
                    interest_on_partial=1,
                    hostility_on_failure=1,
                    success_summary='Gundren relaxes and offers a little more of the truth about the road job.',
                    partial_summary='Gundren softens, but only gives away a sliver of what he knows.',
                    failure_summary='Gundren hardens and insists on the contract as stated.',
                    revealed_topics_on_success=('Gundren is racing toward something important in Phandalin.',),
                    revealed_topics_on_partial=('Gundren is more eager than a simple wagon contract would justify.',),
                ),
                SocialApproachDefinition(
                    approach=SocialApproachType.BARGAIN,
                    ability=Ability.CHA,
                    skill_name='Persuasion',
                    dc=13,
                    leverage_on_success=1,
                    obligation_on_success=1,
                    interest_on_success=1,
                    leverage_on_partial=1,
                    hostility_on_failure=1,
                    success_summary='Gundren responds to the bargaining and starts talking terms instead of deflecting.',
                    partial_summary='Gundren entertains the bargain, but stays stubborn on the important parts.',
                    failure_summary='Gundren shuts down the bargaining attempt and keeps the purse strings tight.',
                    revealed_topics_on_success=('Gundren may be persuaded to adjust terms if the party proves useful first.',),
                ),
                SocialApproachDefinition(
                    approach=SocialApproachType.REQUEST_FAVOR,
                    ability=Ability.CHA,
                    skill_name='Persuasion',
                    dc=14,
                    trust_on_success=1,
                    obligation_on_success=2,
                    obligation_on_partial=1,
                    hostility_on_failure=1,
                    success_summary='Gundren agrees to a small favor and treats the party more like partners.',
                    partial_summary='Gundren hears the request, but only leaves the door cracked open.',
                    failure_summary='Gundren refuses the favor outright and resents being pressed.',
                    revealed_topics_on_success=('Sildar may be able to smooth over practical concerns if the party proves dependable.',),
                ),
                SocialApproachDefinition(
                    approach=SocialApproachType.DECEIVE,
                    ability=Ability.CHA,
                    skill_name='Deception',
                    dc=15,
                    leverage_on_success=1,
                    trust_on_partial=-1,
                    hostility_on_failure=2,
                    success_summary='Gundren buys the story for now, though he keeps the conversation moving.',
                    partial_summary='Gundren does not fully buy the story, but he lets the exchange continue.',
                    failure_summary='Gundren catches the lie and grows visibly suspicious.',
                ),
            ),
        ),
        NpcInfluenceProfile(
            npc_id='sildar-hallwinter',
            display_name='Sildar Hallwinter',
            base_attitude=NpcAttitude.COOPERATIVE,
            base_stance='Courteous, practical, and inclined to keep the job moving.',
            scene_ids=('scene-waterdeep-gundren-briefing', 'scene-02-trail-aftermath'),
            location_ids=('waterdeep', 'triboar-trail'),
            approaches=(
                SocialApproachDefinition(
                    approach=SocialApproachType.APPEAL,
                    ability=Ability.CHA,
                    skill_name='Persuasion',
                    dc=12,
                    trust_on_success=1,
                    obligation_on_success=1,
                    interest_on_success=1,
                    trust_on_partial=1,
                    hostility_on_failure=1,
                    success_summary='Sildar responds to the appeal with practical support and clearer expectations.',
                    partial_summary='Sildar offers limited help while keeping his focus on the mission.',
                    failure_summary='Sildar listens, but declines to intervene.',
                    revealed_topics_on_success=('Sildar views the escort as the start of a larger civic duty around Phandalin.',),
                ),
                SocialApproachDefinition(
                    approach=SocialApproachType.REQUEST_FAVOR,
                    ability=Ability.CHA,
                    skill_name='Persuasion',
                    dc=13,
                    obligation_on_success=2,
                    obligation_on_partial=1,
                    hostility_on_failure=1,
                    success_summary='Sildar agrees to lean on his standing to help the party.',
                    partial_summary='Sildar is willing to help, but only within narrow limits.',
                    failure_summary='Sildar refuses to overstep his role in the arrangement.',
                ),
                SocialApproachDefinition(
                    approach=SocialApproachType.INTIMIDATE,
                    ability=Ability.CHA,
                    skill_name='Intimidation',
                    dc=15,
                    fear_on_success=1,
                    hostility_on_partial=1,
                    hostility_on_failure=2,
                    success_summary='Sildar stiffens and yields the point, but the exchange leaves a mark.',
                    partial_summary='Sildar does not back down, and the tone turns colder.',
                    failure_summary='Sildar rejects the pressure and grows openly disapproving.',
                ),
            ),
        ),
    )


def _lmop_trap_definitions() -> tuple[TrapDefinition, ...]:
    return (
        TrapDefinition(
            trap_id='triboar-snare-line',
            title='Goblin Snare Line',
            hidden_summary='A taut snare line is concealed among brush and wagon ruts.',
            revealed_summary='A goblin snare line is hidden across the road, ready to yank the lead traveler off balance.',
            trigger_summary='The lead traveler catches the hidden snare line and the rig snaps taut across the road.',
            passive_notice_dc=13,
            scene_id='scene-00-high-road-journey',
            location_id='high-road',
            detect_procedure=ProcedureDefinition(
                procedure_id='trap-detect:triboar-snare-line',
                title='Detect Goblin Snare Line',
                category=ProcedureCategory.TRAP,
                summary='Scan the roadside brush and wagon ruts for a concealed snare line.',
                required_progress_points=1,
                scene_id='scene-00-high-road-journey',
                location_id='high-road',
                attempt_options=(
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.SEARCH,
                        ability=Ability.WIS,
                        skill_name='Perception',
                        dc=13,
                        progress_on_success=1,
                        progress_on_partial=1,
                        revealed_clues_on_success=('The brush is bent around a concealed snare line.',),
                        revealed_clues_on_partial=('Something has been tied off in the brush beside the road.',),
                    ),
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.STUDY,
                        ability=Ability.INT,
                        skill_name='Investigation',
                        dc=13,
                        progress_on_success=1,
                        revealed_clues_on_success=('The wagon ruts hide a cut line stretched at ankle height.',),
                    ),
                ),
                clue_pool=(
                    'The roadside brush has been bent aside by a careful hand.',
                    'A thin line crosses the wagon path at ankle height.',
                ),
                completion_note='The party can now avoid or disarm the line before it snaps.',
            ),
            disarm_procedure=ProcedureDefinition(
                procedure_id='trap-disarm:triboar-snare-line',
                title='Disarm Goblin Snare Line',
                category=ProcedureCategory.TOOL_USE,
                summary='Work the hidden line loose without setting it off.',
                required_progress_points=1,
                scene_id='scene-00-high-road-journey',
                location_id='high-road',
                attempt_options=(
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.DISARM,
                        ability=Ability.DEX,
                        skill_name='Sleight of Hand',
                        dc=12,
                        tool_name="Thieves' Tools",
                        requires_tool_proficiency=True,
                        progress_on_success=1,
                        revealed_clues_on_success=('The tension line can be cut and rewound safely.',),
                        failure_note='The line resists careful hands and threatens to spring early.',
                    ),
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.TOOL_USE,
                        ability=Ability.DEX,
                        skill_name='Sleight of Hand',
                        dc=12,
                        tool_name="Thieves' Tools",
                        requires_tool_proficiency=True,
                        progress_on_success=1,
                        revealed_clues_on_success=('The knotwork is simple once the catches are exposed.',),
                    ),
                ),
                completion_note='The snare line is neutralized and no longer threatens the march.',
            ),
            reveal_on_trigger=True,
            consequence_note='Triggering the line can expose the marching order and invite an ambush.',
        ),
    )


def _lmop_puzzle_definitions() -> tuple[PuzzleDefinition, ...]:
    return (
        PuzzleDefinition(
            puzzle_id='trail-aftermath-clues',
            title='Trail Aftermath Clues',
            summary='Read the ambush site well enough to find the hidden trail toward Cragmaw Hideout.',
            scene_id='scene-02-trail-aftermath',
            location_id='triboar-trail',
            player_visible=True,
            study_procedure=ProcedureDefinition(
                procedure_id='puzzle-study:trail-aftermath-clues',
                title='Study The Ambush Site',
                category=ProcedureCategory.PUZZLE,
                summary='Search the aftermath for drag marks, goblin craft, and the true direction of travel.',
                required_progress_points=2,
                scene_id='scene-02-trail-aftermath',
                location_id='triboar-trail',
                attempt_options=(
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.SEARCH,
                        ability=Ability.WIS,
                        skill_name='Perception',
                        dc=12,
                        progress_on_success=1,
                        progress_on_partial=1,
                        revealed_clues_on_success=('Boot and paw prints overlap where captives were dragged away.',),
                        revealed_clues_on_partial=('Scuffed earth shows that something heavy was dragged off the road.',),
                    ),
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.STUDY,
                        ability=Ability.INT,
                        skill_name='Investigation',
                        dc=12,
                        progress_on_success=1,
                        progress_on_partial=1,
                        revealed_clues_on_success=('The trail intentionally doubles back before turning toward the hills.',),
                        revealed_clues_on_partial=('The ambushers tried to hide the real trail under loose brush.',),
                    ),
                ),
                clue_pool=(
                    'Drag marks lead away from the road under broken branches.',
                    'Goblin-made arrows and boot prints point toward a concealed side trail.',
                ),
                completion_note='The party has enough clues to follow the hidden Cragmaw trail.',
            ),
            solve_procedure=ProcedureDefinition(
                procedure_id='puzzle-solve:trail-aftermath-clues',
                title='Follow The Hidden Trail',
                category=ProcedureCategory.PUZZLE,
                summary='Put the clues together and identify the concealed route to the hideout.',
                required_progress_points=1,
                scene_id='scene-02-trail-aftermath',
                location_id='triboar-trail',
                attempt_options=(
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.SOLVE,
                        ability=Ability.WIS,
                        skill_name='Survival',
                        dc=13,
                        progress_on_success=1,
                        progress_on_partial=1,
                        revealed_clues_on_success=('The hidden Cragmaw trail peels north into the wooded rise.',),
                        revealed_clues_on_partial=('A likely path leads into the brush, but the party must move carefully.',),
                    ),
                ),
                completion_note='The party can now move from the ambush site toward Cragmaw Hideout.',
            ),
        ),
    )


def _lmop_downtime_activities() -> tuple[DowntimeActivityDefinition, ...]:
    return (
        DowntimeActivityDefinition(
            activity_id='copy-wagon-ledger',
            title="Copy Gundren's Wagon Ledger",
            summary='Spend quiet time copying and organizing the wagon manifest for later reference.',
            scene_id='scene-waterdeep-gundren-briefing',
            location_id='waterdeep',
            work_procedure=ProcedureDefinition(
                procedure_id='downtime:copy-wagon-ledger',
                title='Copy Wagon Ledger',
                category=ProcedureCategory.DOWNTIME,
                summary='Work through the wagon manifest and preserve the details for the road ahead.',
                required_progress_points=2,
                scene_id='scene-waterdeep-gundren-briefing',
                location_id='waterdeep',
                attempt_options=(
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.WORK,
                        ability=Ability.INT,
                        skill_name='Investigation',
                        dc=11,
                        progress_on_success=1,
                        progress_on_partial=1,
                        revealed_clues_on_success=("The ledger confirms Barthen's Provisions as the delivery point in Phandalin.",),
                        revealed_clues_on_partial=("The manifest ties the cargo to Gundren's operation in Phandalin.",),
                    ),
                    ProcedureCheckOption(
                        attempt_kind=ProcedureAttemptKind.WORK,
                        ability=Ability.DEX,
                        skill_name=None,
                        dc=11,
                        tool_name="Calligrapher's Supplies",
                        progress_on_success=1,
                        revealed_clues_on_success=('A clean copied ledger makes the delivery terms easy to reference later.',),
                    ),
                ),
                completion_note='The party has a reliable copy of the cargo details and delivery terms.',
            ),
            time_slice_hours=1,
        ),
    )
