from __future__ import annotations

from dataclasses import dataclass, replace
import re

from shared_types.effects import CheckRequest
from shared_types.encounter_events import (
    D20TestRolledEvent,
    DiscoveryRevealedEvent,
    ExplorationProcedureCompletedEvent,
    ExplorationProcedureProgressedEvent,
    ExplorationProcedureStartedEvent,
    NPCStanceChangedEvent,
    PuzzleProgressedEvent,
    PuzzleSolvedEvent,
    SocialInfluenceAttemptedEvent,
    SocialInfluenceResolvedEvent,
    StoryCheckResolvedEvent,
    ToolUseDeclaredEvent,
    ToolUseResolvedEvent,
    TrapDetectedEvent,
    TrapDisarmedEvent,
)
from shared_types.encounter_models import EncounterState
from shared_types.errors import EncounterValidationError
from shared_types.exploration import (
    ExplorationState,
    NpcAttitude,
    PendingExplorationCheckKind,
    PendingExplorationCheckState,
    ProcedureAttemptKind,
    ProcedureCategory,
    ProcedureCheckOption,
    ProcedureDefinition,
    ProcedureOutcome,
    ProcedureProgressState,
    ProcedureStatus,
    PuzzleStatus,
    SocialApproachDefinition,
    SocialApproachType,
    TrapStatus,
    unique_strings,
)
from shared_types.models import Ability, slugify


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


def interpret_declaration(engine, state: ExplorationState, *, encounter_state: EncounterState, actor_id: str, declaration: str) -> ExplorationDeclarationPrompt | None:
    engine._require_party_actor(encounter_state, actor_id)
    normalized = slugify(declaration)
    if not normalized:
        return None
    social_match = _match_social_declaration(engine, state, normalized=normalized)
    if social_match is not None:
        return _begin_social_prompt(engine, state, encounter_state=encounter_state, actor_id=actor_id, npc_id=social_match[0], approach=social_match[1], declaration=declaration)
    trap_match = _match_trap_declaration(engine, state, declaration=declaration, normalized=normalized)
    if trap_match is not None:
        return _begin_trap_prompt(engine, state, encounter_state=encounter_state, actor_id=actor_id, trap_id=trap_match[0], attempt_kind=trap_match[1], declaration=declaration, tool_name=trap_match[2])
    puzzle_match = _match_puzzle_declaration(engine, state, declaration=declaration, normalized=normalized)
    if puzzle_match is not None:
        return _begin_puzzle_prompt(engine, state, encounter_state=encounter_state, actor_id=actor_id, puzzle_id=puzzle_match[0], attempt_kind=puzzle_match[1], declaration=declaration, tool_name=puzzle_match[2])
    return None


def resolve_pending_exploration_check(engine, state: ExplorationState, *, encounter_state: EncounterState, pending: PendingExplorationCheckState, check_request: CheckRequest, d20_result, random_counter_used: int) -> tuple[ExplorationState, list[object]]:
    if pending.kind == PendingExplorationCheckKind.SOCIAL:
        return _resolve_social_prompt(engine, state, encounter_state=encounter_state, pending=pending, check_request=check_request, d20_result=d20_result, random_counter_used=random_counter_used)
    if pending.kind == PendingExplorationCheckKind.TRAP:
        return _resolve_trap_prompt(engine, state, encounter_state=encounter_state, pending=pending, check_request=check_request, d20_result=d20_result, random_counter_used=random_counter_used)
    if pending.kind == PendingExplorationCheckKind.PUZZLE:
        return _resolve_puzzle_prompt(engine, state, encounter_state=encounter_state, pending=pending, check_request=check_request, d20_result=d20_result, random_counter_used=random_counter_used)
    raise EncounterValidationError('Unknown pending exploration check kind.')


def _begin_social_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, actor_id: str, npc_id: str, approach: SocialApproachType, declaration: str) -> ExplorationDeclarationPrompt:
    engine._require_party_actor(encounter_state, actor_id)
    profile = engine._require_social_profile(npc_id, state)
    current = state.npc_states[npc_id]
    approach_definition = next((item for item in profile.approaches if item.approach == approach), None)
    if approach_definition is None:
        raise EncounterValidationError(f'{profile.display_name} does not support {approach.value} in this scene.')
    dc = _social_dc_for_declaration(current, approach_definition, declaration)
    prompt = f'Roll {_format_check_label(approach_definition.ability, approach_definition.skill_name)} to {approach.value.replace("_", " ")} with {profile.display_name}.'
    return ExplorationDeclarationPrompt(
        pending_state=PendingExplorationCheckState(actor_id=actor_id, declaration=declaration, kind=PendingExplorationCheckKind.SOCIAL, attempt_kind=ProcedureAttemptKind.STUDY, npc_id=npc_id, approach=approach),
        prompt=prompt,
        reason=declaration,
        ability=approach_definition.ability,
        skill_name=approach_definition.skill_name,
        dc=dc,
        interacting_with_actor_id=(npc_id if npc_id in encounter_state.actors else None),
    )


def _resolve_social_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, pending: PendingExplorationCheckState, check_request: CheckRequest, d20_result, random_counter_used: int) -> tuple[ExplorationState, list[object]]:
    if pending.npc_id is None or pending.approach is None:
        raise EncounterValidationError('Pending social resolution is missing NPC or approach data.')
    actor = engine._require_party_actor(encounter_state, pending.actor_id)
    profile = engine._require_social_profile(pending.npc_id, state)
    approach = next((item for item in profile.approaches if item.approach == pending.approach), None)
    if approach is None:
        raise EncounterValidationError(f'{profile.display_name} does not support {pending.approach.value} in this scene.')
    outcome = engine._procedure_outcome(total=d20_result.total, dc=check_request.dc, partial_margin=approach.partial_margin)
    npc_states = dict(state.npc_states)
    current = npc_states[pending.npc_id]
    updated_npc = engine._apply_social_outcome(current, profile, approach, outcome)
    npc_states[pending.npc_id] = updated_npc
    updated = replace(state, npc_states=npc_states)
    events: list[object] = [
        D20TestRolledEvent(actor_id=actor.actor_id, result=d20_result, random_counter_used=random_counter_used),
        StoryCheckResolvedEvent(request_id=f'social:{pending.npc_id}:{pending.approach.value}:{random_counter_used}', actor_id=actor.actor_id, scene_id=state.current_scene_id, ability=check_request.ability, skill_name=check_request.skill_name, dc=check_request.dc, selected_roll=d20_result.selected_roll, total=d20_result.total, success=(outcome != ProcedureOutcome.FAILURE), interacting_with_actor_id=check_request.interacting_with_actor_id),
        SocialInfluenceAttemptedEvent(actor_id=actor.actor_id, npc_id=pending.npc_id, approach=pending.approach, dc=check_request.dc, selected_roll=d20_result.selected_roll, total=d20_result.total, random_counter_used=random_counter_used),
        SocialInfluenceResolvedEvent(actor_id=actor.actor_id, npc_id=pending.npc_id, approach=pending.approach, outcome=engine._social_outcome(outcome), summary=updated_npc.last_summary),
    ]
    if updated_npc.attitude != current.attitude or updated_npc.current_stance != current.current_stance:
        events.append(NPCStanceChangedEvent(npc_id=pending.npc_id, old_attitude=current.attitude, new_attitude=updated_npc.attitude, current_stance=updated_npc.current_stance, summary=updated_npc.last_summary))
    newly_revealed = tuple(topic for topic in updated_npc.revealed_topics if topic not in current.revealed_topics)
    if newly_revealed:
        updated = engine._merge_discoveries(updated, newly_revealed)
        for topic in newly_revealed:
            events.append(DiscoveryRevealedEvent(discovery_id=f'npc-topic:{pending.npc_id}:{slugify(topic)}', text=topic, source_category=ProcedureCategory.DISCOVERY, actor_id=actor.actor_id, public=True))
    events.append(engine._projection_event(updated))
    return updated, events

def _begin_trap_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, actor_id: str, trap_id: str, attempt_kind: ProcedureAttemptKind, declaration: str, tool_name: str | None) -> ExplorationDeclarationPrompt:
    actor = engine._require_party_actor(encounter_state, actor_id)
    definition = engine._require_trap_definition(trap_id, state)
    runtime = state.traps[trap_id]
    if attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
        if definition.detect_procedure is None:
            raise EncounterValidationError('This trap does not define a detect procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.detect_procedure, progress=(runtime.detect_progress or engine._initial_progress(definition.detect_procedure)), attempt_kind=attempt_kind, tool_name=tool_name, progress_multiplier=1, request_prefix=f'trap-detect:{definition.trap_id}', interacting_with_actor_id=None)
        detail = 'search the area for hidden dangers' if runtime.status in {TrapStatus.HIDDEN, TrapStatus.DETECTABLE} else f'{attempt_kind.value} {definition.title}'
    else:
        if runtime.status not in {TrapStatus.DETECTED, TrapStatus.TRIGGERED}:
            raise EncounterValidationError('A trap must be detected or triggered before it can be disarmed.')
        if definition.disarm_procedure is None:
            raise EncounterValidationError('This trap does not define a disarm procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.disarm_procedure, progress=(runtime.disarm_progress or engine._initial_progress(definition.disarm_procedure)), attempt_kind=attempt_kind, tool_name=tool_name, progress_multiplier=1, request_prefix=f'trap-disarm:{definition.trap_id}', interacting_with_actor_id=None)
        detail = f'disarm {definition.title}'
    return ExplorationDeclarationPrompt(
        pending_state=PendingExplorationCheckState(actor_id=actor_id, declaration=declaration, kind=PendingExplorationCheckKind.TRAP, attempt_kind=attempt_kind, trap_id=trap_id, tool_name=prepared.canonical_tool_name),
        prompt=_procedure_prompt_text(prepared, detail=detail),
        reason=declaration,
        ability=prepared.option.ability,
        skill_name=prepared.option.skill_name,
        dc=prepared.option.dc,
        interacting_with_actor_id=None,
    )


def _resolve_trap_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, pending: PendingExplorationCheckState, check_request: CheckRequest, d20_result, random_counter_used: int) -> tuple[ExplorationState, list[object]]:
    if pending.trap_id is None:
        raise EncounterValidationError('Pending trap resolution is missing trap data.')
    actor = engine._require_party_actor(encounter_state, pending.actor_id)
    definition = engine._require_trap_definition(pending.trap_id, state)
    runtime = state.traps[pending.trap_id]
    traps = dict(state.traps)
    if pending.attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
        if definition.detect_procedure is None:
            raise EncounterValidationError('This trap does not define a detect procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.detect_procedure, progress=(runtime.detect_progress or engine._initial_progress(definition.detect_procedure)), attempt_kind=pending.attempt_kind, tool_name=pending.tool_name, progress_multiplier=1, request_prefix=f'trap-detect:{definition.trap_id}', interacting_with_actor_id=None)
        result = _apply_prepared_procedure_check(engine, actor=actor, prepared=prepared, d20_result=d20_result, random_counter_used=random_counter_used, dc_override=check_request.dc)
        status = runtime.status
        visible = runtime.visible_to_party
        detected_by = runtime.detected_by_actor_ids
        if result.progress.status == ProcedureStatus.COMPLETED:
            status = TrapStatus.DETECTED
            visible = True
            detected_by = unique_strings(runtime.detected_by_actor_ids + (actor.actor_id,))
        traps[pending.trap_id] = replace(runtime, status=status, visible_to_party=visible, detected_by_actor_ids=detected_by, detect_progress=result.progress, last_summary=(definition.revealed_summary if status == TrapStatus.DETECTED else result.summary))
        updated = replace(state, traps=traps)
        updated = engine._merge_discoveries(updated, result.revealed_clues)
        events = list(result.events)
        if status == TrapStatus.DETECTED:
            events.append(TrapDetectedEvent(trap_id=definition.trap_id, title=definition.title, actor_id=actor.actor_id, passive=False, status=status, summary=definition.revealed_summary))
        events.append(engine._projection_event(updated))
        return updated, events
    if definition.disarm_procedure is None:
        raise EncounterValidationError('This trap does not define a disarm procedure.')
    prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.disarm_procedure, progress=(runtime.disarm_progress or engine._initial_progress(definition.disarm_procedure)), attempt_kind=pending.attempt_kind, tool_name=pending.tool_name, progress_multiplier=1, request_prefix=f'trap-disarm:{definition.trap_id}', interacting_with_actor_id=None)
    result = _apply_prepared_procedure_check(engine, actor=actor, prepared=prepared, d20_result=d20_result, random_counter_used=random_counter_used, dc_override=check_request.dc)
    trap_state = replace(runtime, status=(TrapStatus.DISARMED if result.progress.status == ProcedureStatus.COMPLETED else runtime.status), visible_to_party=True, disarmed_by_actor_id=(actor.actor_id if result.progress.status == ProcedureStatus.COMPLETED else runtime.disarmed_by_actor_id), disarm_progress=result.progress, last_summary=(definition.revealed_summary if result.progress.status == ProcedureStatus.COMPLETED else result.summary))
    traps[pending.trap_id] = trap_state
    updated = replace(state, traps=traps)
    updated = engine._merge_discoveries(updated, result.revealed_clues)
    events = list(result.events)
    if trap_state.status == TrapStatus.DISARMED:
        events.append(TrapDisarmedEvent(trap_id=definition.trap_id, title=definition.title, actor_id=actor.actor_id, summary=definition.revealed_summary))
    events.append(engine._projection_event(updated))
    return updated, events


def _begin_puzzle_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, actor_id: str, puzzle_id: str, attempt_kind: ProcedureAttemptKind, declaration: str, tool_name: str | None) -> ExplorationDeclarationPrompt:
    actor = engine._require_party_actor(encounter_state, actor_id)
    definition = engine._require_puzzle_definition(puzzle_id, state)
    runtime = state.puzzles[puzzle_id]
    if attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
        if definition.study_procedure is None:
            raise EncounterValidationError('This puzzle does not define a study procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.study_procedure, progress=(runtime.study_progress or engine._initial_progress(definition.study_procedure)), attempt_kind=attempt_kind, tool_name=tool_name, progress_multiplier=1, request_prefix=f'puzzle-study:{definition.puzzle_id}', interacting_with_actor_id=None)
        detail = f'study {definition.title}'
    else:
        if definition.solve_procedure is None:
            raise EncounterValidationError('This puzzle does not define a solve procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.solve_procedure, progress=(runtime.solve_progress or engine._initial_progress(definition.solve_procedure)), attempt_kind=attempt_kind, tool_name=tool_name, progress_multiplier=1, request_prefix=f'puzzle-solve:{definition.puzzle_id}', interacting_with_actor_id=None)
        detail = f'solve {definition.title}'
    return ExplorationDeclarationPrompt(
        pending_state=PendingExplorationCheckState(actor_id=actor_id, declaration=declaration, kind=PendingExplorationCheckKind.PUZZLE, attempt_kind=attempt_kind, puzzle_id=puzzle_id, tool_name=prepared.canonical_tool_name),
        prompt=_procedure_prompt_text(prepared, detail=detail),
        reason=declaration,
        ability=prepared.option.ability,
        skill_name=prepared.option.skill_name,
        dc=prepared.option.dc,
        interacting_with_actor_id=None,
    )


def _resolve_puzzle_prompt(engine, state: ExplorationState, *, encounter_state: EncounterState, pending: PendingExplorationCheckState, check_request: CheckRequest, d20_result, random_counter_used: int) -> tuple[ExplorationState, list[object]]:
    if pending.puzzle_id is None:
        raise EncounterValidationError('Pending puzzle resolution is missing puzzle data.')
    actor = engine._require_party_actor(encounter_state, pending.actor_id)
    definition = engine._require_puzzle_definition(pending.puzzle_id, state)
    runtime = state.puzzles[pending.puzzle_id]
    puzzles = dict(state.puzzles)
    if pending.attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY}:
        if definition.study_procedure is None:
            raise EncounterValidationError('This puzzle does not define a study procedure.')
        prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.study_procedure, progress=(runtime.study_progress or engine._initial_progress(definition.study_procedure)), attempt_kind=pending.attempt_kind, tool_name=pending.tool_name, progress_multiplier=1, request_prefix=f'puzzle-study:{definition.puzzle_id}', interacting_with_actor_id=None)
        result = _apply_prepared_procedure_check(engine, actor=actor, prepared=prepared, d20_result=d20_result, random_counter_used=random_counter_used, dc_override=check_request.dc)
        puzzles[pending.puzzle_id] = replace(runtime, status=PuzzleStatus.IN_PROGRESS, visible_to_party=True, study_progress=result.progress, last_summary=result.summary)
        updated = replace(state, puzzles=puzzles)
        updated = engine._merge_discoveries(updated, result.revealed_clues)
        events = list(result.events)
        events.append(PuzzleProgressedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, status=PuzzleStatus.IN_PROGRESS, summary=result.summary))
        events.append(engine._projection_event(updated))
        return updated, events
    if definition.solve_procedure is None:
        raise EncounterValidationError('This puzzle does not define a solve procedure.')
    prepared = _prepare_procedure_check(engine, actor=actor, definition=definition.solve_procedure, progress=(runtime.solve_progress or engine._initial_progress(definition.solve_procedure)), attempt_kind=pending.attempt_kind, tool_name=pending.tool_name, progress_multiplier=1, request_prefix=f'puzzle-solve:{definition.puzzle_id}', interacting_with_actor_id=None)
    result = _apply_prepared_procedure_check(engine, actor=actor, prepared=prepared, d20_result=d20_result, random_counter_used=random_counter_used, dc_override=check_request.dc)
    solved = result.progress.status == ProcedureStatus.COMPLETED
    status = PuzzleStatus.SOLVED if solved else PuzzleStatus.IN_PROGRESS
    puzzles[pending.puzzle_id] = replace(runtime, status=status, visible_to_party=True, solve_progress=result.progress, last_summary=result.summary)
    updated = replace(state, puzzles=puzzles)
    updated = engine._merge_discoveries(updated, result.revealed_clues)
    events = list(result.events)
    if solved:
        events.append(PuzzleSolvedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, summary=result.summary))
    else:
        events.append(PuzzleProgressedEvent(puzzle_id=definition.puzzle_id, title=definition.title, actor_id=actor.actor_id, status=status, summary=result.summary))
    events.append(engine._projection_event(updated))
    return updated, events

def _prepare_procedure_check(engine, *, actor, definition: ProcedureDefinition, progress: ProcedureProgressState, attempt_kind: ProcedureAttemptKind, tool_name: str | None, progress_multiplier: int, request_prefix: str, interacting_with_actor_id: str | None) -> PreparedProcedureCheck:
    option, canonical_tool_name = engine._select_procedure_option(actor, definition, attempt_kind, tool_name)
    return PreparedProcedureCheck(definition=definition, progress=progress, option=option, canonical_tool_name=canonical_tool_name, request_prefix=request_prefix, interacting_with_actor_id=interacting_with_actor_id, progress_multiplier=progress_multiplier)


def _apply_prepared_procedure_check(engine, *, actor, prepared: PreparedProcedureCheck, d20_result, random_counter_used: int, dc_override: int | None = None):
    option = prepared.option
    dc = dc_override if dc_override is not None else option.dc
    outcome = engine._procedure_outcome(total=d20_result.total, dc=dc, partial_margin=option.partial_margin)
    revealed = engine._revealed_clues_for_outcome(option, outcome)
    newly_revealed = tuple(clue for clue in revealed if clue not in set(prepared.progress.revealed_clues))
    merged_clues = unique_strings(prepared.progress.revealed_clues + newly_revealed)
    progress_gain = engine._progress_for_outcome(option, outcome) * max(1, prepared.progress_multiplier)
    total_progress = prepared.progress.progress_points + progress_gain
    status = ProcedureStatus.IN_PROGRESS
    if total_progress >= prepared.progress.required_progress_points:
        status = ProcedureStatus.COMPLETED
    elif outcome == ProcedureOutcome.FAILURE and not prepared.definition.repeatable:
        status = ProcedureStatus.FAILED
    summary = engine._procedure_summary(prepared.definition, option, outcome, newly_revealed, completed=(status == ProcedureStatus.COMPLETED))
    new_progress = replace(prepared.progress, status=status, progress_points=total_progress, attempt_count=prepared.progress.attempt_count + 1, failure_count=prepared.progress.failure_count + (1 if outcome == ProcedureOutcome.FAILURE else 0), revealed_clues=merged_clues, last_summary=summary)
    events: list[object] = []
    if prepared.progress.status == ProcedureStatus.NOT_STARTED:
        events.append(ExplorationProcedureStartedEvent(procedure_id=prepared.definition.procedure_id, title=prepared.definition.title, category=prepared.definition.category, actor_id=actor.actor_id, summary=prepared.definition.summary))
    if prepared.canonical_tool_name is not None:
        events.append(ToolUseDeclaredEvent(actor_id=actor.actor_id, tool_name=prepared.canonical_tool_name, target_id=prepared.definition.procedure_id, target_category=prepared.definition.category))
    events.append(D20TestRolledEvent(actor_id=actor.actor_id, result=d20_result, random_counter_used=random_counter_used))
    events.append(StoryCheckResolvedEvent(request_id=f'{prepared.request_prefix}:{random_counter_used}', actor_id=actor.actor_id, scene_id=prepared.definition.scene_id, ability=option.ability, skill_name=option.skill_name, dc=dc, selected_roll=d20_result.selected_roll, total=d20_result.total, success=(outcome != ProcedureOutcome.FAILURE), interacting_with_actor_id=prepared.interacting_with_actor_id))
    if prepared.canonical_tool_name is not None:
        events.append(ToolUseResolvedEvent(actor_id=actor.actor_id, tool_name=prepared.canonical_tool_name, target_id=prepared.definition.procedure_id, target_category=prepared.definition.category, outcome=outcome, summary=summary))
    events.append(ExplorationProcedureProgressedEvent(procedure_id=prepared.definition.procedure_id, title=prepared.definition.title, category=prepared.definition.category, actor_id=actor.actor_id, status=new_progress.status, progress_points=new_progress.progress_points, required_progress_points=new_progress.required_progress_points, summary=summary))
    if new_progress.status == ProcedureStatus.COMPLETED:
        events.append(ExplorationProcedureCompletedEvent(procedure_id=prepared.definition.procedure_id, title=prepared.definition.title, category=prepared.definition.category, actor_id=actor.actor_id, summary=summary))
    for clue in newly_revealed:
        events.append(DiscoveryRevealedEvent(discovery_id=f'{prepared.definition.procedure_id}:{slugify(clue)}', text=clue, source_category=prepared.definition.category, actor_id=actor.actor_id, public=prepared.definition.player_visible))
    from rules_engine.exploration import ProcedureAttemptResult
    return ProcedureAttemptResult(progress=new_progress, outcome=outcome, summary=summary, revealed_clues=newly_revealed, events=tuple(events))

def _match_social_declaration(engine, state: ExplorationState, *, normalized: str) -> tuple[str, SocialApproachType] | None:
    if not _mentions_any(normalized, ('bargain', 'deal', 'terms', 'price', 'prepay', 'advance', 'coin', 'payment', 'convince', 'persuade', 'appeal', 'favor', 'deceive', 'bluff', 'lie', 'pretend', 'intimidate', 'threaten', 'spare', 'grant', 'lend', 'allow us', 'let us', 'hear us out', 'accept', 'agree')):
        return None
    matches: list[tuple[str, SocialApproachType]] = []
    for npc_state in engine.visible_npc_states(state):
        if not _declaration_mentions_npc(normalized, npc_state.display_name, npc_state.npc_id):
            continue
        profile = engine.social_profiles[npc_state.npc_id]
        approach = _social_approach_from_declaration(normalized, profile)
        if approach is not None:
            matches.append((npc_state.npc_id, approach))
    if not matches:
        return None
    unique_matches = list(dict.fromkeys(matches))
    if len(unique_matches) > 1:
        raise EncounterValidationError('Clarify which NPC you are trying to influence.')
    return unique_matches[0]


def _match_trap_declaration(engine, state: ExplorationState, *, declaration: str, normalized: str) -> tuple[str, ProcedureAttemptKind, str | None] | None:
    if not _mentions_any(normalized, ('trap', 'snare', 'wire', 'line', 'danger', 'hazard', 'search', 'look', 'check', 'scan', 'study', 'investigate', 'inspect', 'examine', 'disarm', 'disable', 'cut')):
        return None
    attempt_kind = _trap_attempt_kind_from_declaration(normalized)
    if attempt_kind is None:
        return None
    candidates = [definition for definition in engine.trap_definitions.values() if engine._definition_matches_context(definition.scene_id, definition.location_id, state.current_scene_id, state.current_location_id)]
    if not candidates:
        return None
    if len(candidates) > 1:
        raise EncounterValidationError('Clarify which trap or hazard you are trying to examine.')
    definition = candidates[0]
    procedure = definition.detect_procedure if attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY} else definition.disarm_procedure
    return definition.trap_id, attempt_kind, _extract_tool_name_from_declaration(declaration, definition=procedure)


def _match_puzzle_declaration(engine, state: ExplorationState, *, declaration: str, normalized: str) -> tuple[str, ProcedureAttemptKind, str | None] | None:
    if not _mentions_any(normalized, ('puzzle', 'clue', 'trail', 'tracks', 'search', 'look', 'check', 'study', 'investigate', 'inspect', 'examine', 'solve', 'follow', 'figure', 'work out')):
        return None
    attempt_kind = _puzzle_attempt_kind_from_declaration(normalized)
    if attempt_kind is None:
        return None
    candidates = [definition for definition, runtime in engine.visible_puzzle_states(state, dm_view=True) if runtime.visible_to_party or definition.player_visible]
    if not candidates:
        return None
    if len(candidates) > 1:
        raise EncounterValidationError('Clarify which clue or puzzle you are trying to work on.')
    definition = candidates[0]
    procedure = definition.study_procedure if attempt_kind in {ProcedureAttemptKind.SEARCH, ProcedureAttemptKind.STUDY} else definition.solve_procedure
    return definition.puzzle_id, attempt_kind, _extract_tool_name_from_declaration(declaration, definition=procedure)


def _declaration_mentions_npc(normalized: str, display_name: str, npc_id: str) -> bool:
    tokens = [slugify(display_name), slugify(npc_id)]
    for token in tokens:
        if token and token in normalized:
            return True
        for part in token.split('-'):
            if len(part) >= 4 and part in normalized:
                return True
    return False


def _social_approach_from_declaration(normalized: str, profile) -> SocialApproachType | None:
    supported = {approach.approach for approach in profile.approaches}
    checks = (
        (SocialApproachType.BARGAIN, ('bargain', 'deal', 'terms', 'price', 'prepay', 'advance', 'coin', 'payment', 'supplies')),
        (SocialApproachType.REQUEST_FAVOR, ('favor', 'help us out', 'do us a favor', 'spare', 'grant', 'lend', 'allow us', 'let us')),
        (SocialApproachType.INTIMIDATE, ('intimidate', 'threaten', 'or else', 'warning')),
        (SocialApproachType.DECEIVE, ('deceive', 'bluff', 'lie', 'pretend', 'fake')),
        (SocialApproachType.APPEAL, ('appeal', 'duty', 'honor', 'justice')),
        (SocialApproachType.PERSUADE, ('persuade', 'convince', 'accept', 'agree', 'listen', 'hear us out')),
    )
    for approach, terms in checks:
        if approach in supported and _mentions_any(normalized, terms):
            return approach
    if SocialApproachType.PERSUADE in supported and _mentions_any(normalized, ('would you', 'could you', 'can you', 'please')) and _mentions_any(normalized, ('give', 'grant', 'spare', 'lend', 'allow', 'let us', 'accept', 'agree', 'listen')):
        return SocialApproachType.PERSUADE
    return None


def _trap_attempt_kind_from_declaration(normalized: str) -> ProcedureAttemptKind | None:
    if _mentions_any(normalized, ('disarm', 'disable', 'cut', 'unhook')):
        return ProcedureAttemptKind.DISARM
    if _mentions_any(normalized, ('study', 'investigate', 'inspect', 'examine')):
        return ProcedureAttemptKind.STUDY
    if _mentions_any(normalized, ('search', 'look', 'check', 'scan')):
        return ProcedureAttemptKind.SEARCH
    return None


def _puzzle_attempt_kind_from_declaration(normalized: str) -> ProcedureAttemptKind | None:
    if _mentions_any(normalized, ('solve', 'follow', 'figure', 'work out')):
        return ProcedureAttemptKind.SOLVE
    if _mentions_any(normalized, ('study', 'investigate', 'inspect', 'examine')):
        return ProcedureAttemptKind.STUDY
    if _mentions_any(normalized, ('search', 'look', 'check')):
        return ProcedureAttemptKind.SEARCH
    return None


def _extract_tool_name_from_declaration(declaration: str, *, definition: ProcedureDefinition | None) -> str | None:
    if definition is None:
        return None
    normalized = slugify(declaration)
    compact = re.sub(r'[^a-z0-9]', '', declaration.lower())
    for option in definition.attempt_options:
        if option.tool_name is None:
            continue
        candidate = slugify(option.tool_name)
        if candidate in normalized:
            return option.tool_name
        if re.sub(r'[^a-z0-9]', '', option.tool_name.lower()) in compact:
            return option.tool_name
    return None


def _mentions_any(normalized: str, terms: tuple[str, ...]) -> bool:
    haystack = normalized.replace('-', ' ')
    return any(term in haystack for term in terms)


def _format_check_label(ability: Ability, skill_name: str | None) -> str:
    labels = {Ability.STR: 'Strength', Ability.DEX: 'Dexterity', Ability.CON: 'Constitution', Ability.INT: 'Intelligence', Ability.WIS: 'Wisdom', Ability.CHA: 'Charisma'}
    base = labels.get(ability, ability.value)
    return f'{base} ({skill_name})' if skill_name else base


def _procedure_prompt_text(prepared: PreparedProcedureCheck, *, detail: str) -> str:
    label = _format_check_label(prepared.option.ability, prepared.option.skill_name)
    if prepared.canonical_tool_name is not None:
        return f'Use {prepared.canonical_tool_name} and roll {label} to {detail}.'
    return f'Roll {label} to {detail}.'


def _social_dc_for_declaration(current, approach: SocialApproachDefinition, declaration: str) -> int:
    dc = approach.dc
    normalized = slugify(declaration)
    if current.attitude == NpcAttitude.FRIENDLY:
        dc -= 2
    elif current.attitude == NpcAttitude.COOPERATIVE:
        dc -= 1
    elif current.attitude == NpcAttitude.HOSTILE:
        dc += 1
    if _mentions_any(normalized, ('because', 'since', 'in return', 'we will', 'we can', 'so that', 'if you')):
        dc -= 1
    if current.trust + current.obligation + current.leverage >= 3:
        dc -= 1
    return max(5, dc)
