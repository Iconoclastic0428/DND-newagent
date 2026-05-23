from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import Ability


class ExplorationMode(str, Enum):
    SCENE = 'scene'
    TRAVEL = 'travel'
    CAMP = 'camp'
    DOWNTIME = 'downtime'


class MarchPosition(str, Enum):
    SCOUT = 'scout'
    FRONT = 'front'
    CENTER = 'center'
    REAR = 'rear'


class ExplorationRole(str, Enum):
    NAVIGATOR = 'navigator'
    SCOUT = 'scout'
    LOOKOUT = 'lookout'
    SEARCH = 'search'
    STUDY = 'study'
    SNEAK = 'sneak'


class ProcedureCategory(str, Enum):
    TOOL_USE = 'tool_use'
    TRAP = 'trap'
    PUZZLE = 'puzzle'
    DISCOVERY = 'discovery'
    DOWNTIME = 'downtime'


class ProcedureAttemptKind(str, Enum):
    SEARCH = 'search'
    STUDY = 'study'
    TOOL_USE = 'tool_use'
    SOLVE = 'solve'
    WORK = 'work'
    DISARM = 'disarm'
    BYPASS = 'bypass'


class ProcedureStatus(str, Enum):
    NOT_STARTED = 'not-started'
    IN_PROGRESS = 'in-progress'
    COMPLETED = 'completed'
    FAILED = 'failed'
    ABANDONED = 'abandoned'


class ProcedureOutcome(str, Enum):
    SUCCESS = 'success'
    PARTIAL = 'partial'
    FAILURE = 'failure'


class TrapStatus(str, Enum):
    HIDDEN = 'hidden'
    DETECTABLE = 'detectable'
    DETECTED = 'detected'
    TRIGGERED = 'triggered'
    BYPASSED = 'bypassed'
    DISARMED = 'disarmed'
    RESOLVED = 'resolved'


class PuzzleStatus(str, Enum):
    UNSOLVED = 'unsolved'
    IN_PROGRESS = 'in-progress'
    SOLVED = 'solved'
    ABANDONED = 'abandoned'


class NpcAttitude(str, Enum):
    FRIENDLY = 'friendly'
    COOPERATIVE = 'cooperative'
    RESERVED = 'reserved'
    WARY = 'wary'
    HOSTILE = 'hostile'


class SocialApproachType(str, Enum):
    PERSUADE = 'persuade'
    DECEIVE = 'deceive'
    INTIMIDATE = 'intimidate'
    BARGAIN = 'bargain'
    APPEAL = 'appeal'
    REQUEST_FAVOR = 'request_favor'


class SocialOutcome(str, Enum):
    SUCCESS = 'success'
    PARTIAL = 'partial'
    FAILURE = 'failure'


class DowntimeProjectStatus(str, Enum):
    IN_PROGRESS = 'in-progress'
    COMPLETED = 'completed'
    CANCELLED = 'cancelled'


class PendingExplorationCheckKind(str, Enum):
    SOCIAL = 'social'
    TRAP = 'trap'
    PUZZLE = 'puzzle'


@dataclass(frozen=True)
class MarchingOrderEntry:
    actor_id: str
    position: MarchPosition
    ordinal: int


@dataclass(frozen=True)
class WatchAssignment:
    actor_id: str
    shift_index: int


@dataclass(frozen=True)
class ExplorationRoleAssignments:
    navigator_actor_id: str | None = None
    scout_actor_id: str | None = None
    lookout_actor_ids: tuple[str, ...] = ()
    searching_actor_ids: tuple[str, ...] = ()
    studying_actor_ids: tuple[str, ...] = ()
    sneaking_actor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class ProcedureCheckOption:
    attempt_kind: ProcedureAttemptKind
    ability: Ability
    skill_name: str | None = None
    dc: int = 10
    tool_name: str | None = None
    requires_tool_proficiency: bool = False
    progress_on_success: int = 1
    progress_on_partial: int = 0
    progress_on_failure: int = 0
    partial_margin: int = 2
    revealed_clues_on_success: tuple[str, ...] = ()
    revealed_clues_on_partial: tuple[str, ...] = ()
    revealed_clues_on_failure: tuple[str, ...] = ()
    failure_note: str = ''


@dataclass(frozen=True)
class ProcedureDefinition:
    procedure_id: str
    title: str
    category: ProcedureCategory
    summary: str
    required_progress_points: int = 1
    hidden: bool = False
    player_visible: bool = True
    repeatable: bool = True
    scene_id: str | None = None
    location_id: str | None = None
    attempt_options: tuple[ProcedureCheckOption, ...] = ()
    clue_pool: tuple[str, ...] = ()
    consequence_note: str = ''
    completion_note: str = ''


@dataclass(frozen=True)
class ProcedureProgressState:
    procedure_id: str
    title: str
    category: ProcedureCategory
    status: ProcedureStatus = ProcedureStatus.NOT_STARTED
    progress_points: int = 0
    required_progress_points: int = 1
    attempt_count: int = 0
    failure_count: int = 0
    revealed_clues: tuple[str, ...] = ()
    last_summary: str = ''


@dataclass(frozen=True)
class TrapDefinition:
    trap_id: str
    title: str
    hidden_summary: str
    revealed_summary: str
    trigger_summary: str
    passive_notice_dc: int | None = None
    scene_id: str | None = None
    location_id: str | None = None
    detect_procedure: ProcedureDefinition | None = None
    disarm_procedure: ProcedureDefinition | None = None
    auto_trigger_on_entry: bool = False
    reveal_on_trigger: bool = True
    resettable: bool = False
    consequence_note: str = ''


@dataclass(frozen=True)
class TrapRuntimeState:
    trap_id: str
    title: str
    status: TrapStatus = TrapStatus.HIDDEN
    visible_to_party: bool = False
    detected_by_actor_ids: tuple[str, ...] = ()
    bypassed_by_actor_ids: tuple[str, ...] = ()
    triggered_by_actor_id: str | None = None
    disarmed_by_actor_id: str | None = None
    detect_progress: ProcedureProgressState | None = None
    disarm_progress: ProcedureProgressState | None = None
    last_summary: str = ''


@dataclass(frozen=True)
class PuzzleDefinition:
    puzzle_id: str
    title: str
    summary: str
    scene_id: str | None = None
    location_id: str | None = None
    player_visible: bool = True
    study_procedure: ProcedureDefinition | None = None
    solve_procedure: ProcedureDefinition | None = None


@dataclass(frozen=True)
class PuzzleRuntimeState:
    puzzle_id: str
    title: str
    status: PuzzleStatus = PuzzleStatus.UNSOLVED
    visible_to_party: bool = False
    study_progress: ProcedureProgressState | None = None
    solve_progress: ProcedureProgressState | None = None
    last_summary: str = ''


@dataclass(frozen=True)
class SocialApproachDefinition:
    approach: SocialApproachType
    ability: Ability
    skill_name: str | None
    dc: int
    partial_margin: int = 2
    trust_on_success: int = 0
    hostility_on_success: int = 0
    leverage_on_success: int = 0
    obligation_on_success: int = 0
    fear_on_success: int = 0
    interest_on_success: int = 0
    trust_on_partial: int = 0
    hostility_on_partial: int = 0
    leverage_on_partial: int = 0
    obligation_on_partial: int = 0
    fear_on_partial: int = 0
    interest_on_partial: int = 0
    trust_on_failure: int = 0
    hostility_on_failure: int = 0
    leverage_on_failure: int = 0
    obligation_on_failure: int = 0
    fear_on_failure: int = 0
    interest_on_failure: int = 0
    success_summary: str = ''
    partial_summary: str = ''
    failure_summary: str = ''
    revealed_topics_on_success: tuple[str, ...] = ()
    revealed_topics_on_partial: tuple[str, ...] = ()
    revealed_topics_on_failure: tuple[str, ...] = ()


@dataclass(frozen=True)
class NpcInfluenceProfile:
    npc_id: str
    display_name: str
    base_attitude: NpcAttitude
    base_stance: str
    scene_ids: tuple[str, ...] = ()
    location_ids: tuple[str, ...] = ()
    approaches: tuple[SocialApproachDefinition, ...] = ()


@dataclass(frozen=True)
class NpcInfluenceState:
    npc_id: str
    display_name: str
    attitude: NpcAttitude
    current_stance: str
    trust: int = 0
    hostility: int = 0
    leverage: int = 0
    obligation: int = 0
    fear: int = 0
    interest: int = 0
    revealed_topics: tuple[str, ...] = ()
    last_summary: str = ''


@dataclass(frozen=True)
class DowntimeActivityDefinition:
    activity_id: str
    title: str
    summary: str
    scene_id: str | None = None
    location_id: str | None = None
    work_procedure: ProcedureDefinition | None = None
    time_slice_hours: int = 1


@dataclass(frozen=True)
class DowntimeProjectState:
    project_id: str
    activity_id: str
    actor_id: str
    title: str
    status: DowntimeProjectStatus = DowntimeProjectStatus.IN_PROGRESS
    progress_state: ProcedureProgressState | None = None
    elapsed_hours: int = 0
    last_summary: str = ''


@dataclass(frozen=True)
class PendingExplorationCheckState:
    actor_id: str
    declaration: str
    kind: PendingExplorationCheckKind
    attempt_kind: ProcedureAttemptKind
    npc_id: str | None = None
    approach: SocialApproachType | None = None
    trap_id: str | None = None
    puzzle_id: str | None = None
    tool_name: str | None = None


@dataclass
class ExplorationState:
    mode: ExplorationMode = ExplorationMode.SCENE
    marching_order: tuple[MarchingOrderEntry, ...] = ()
    watch_order: tuple[WatchAssignment, ...] = ()
    role_assignments: ExplorationRoleAssignments = field(default_factory=ExplorationRoleAssignments)
    camp_active: bool = False
    camp_started_at_seconds: int | None = None
    watch_shift_seconds: int = 2 * 60 * 60
    current_scene_id: str | None = None
    current_location_id: str | None = None
    current_travel_map_id: str | None = None
    known_discoveries: tuple[str, ...] = ()
    traps: dict[str, TrapRuntimeState] = field(default_factory=dict)
    puzzles: dict[str, PuzzleRuntimeState] = field(default_factory=dict)
    npc_states: dict[str, NpcInfluenceState] = field(default_factory=dict)
    downtime_projects: dict[str, DowntimeProjectState] = field(default_factory=dict)


@dataclass(frozen=True)
class SetMarchingOrderIntent:
    controller_id: str
    actor_ids: tuple[str, ...]


@dataclass(frozen=True)
class SetWatchOrderIntent:
    controller_id: str
    actor_ids: tuple[str, ...]


@dataclass(frozen=True)
class AssignExplorationRoleIntent:
    controller_id: str
    role: ExplorationRole
    actor_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SetCampStateIntent:
    controller_id: str
    active: bool


@dataclass(frozen=True)
class AttemptTrapIntent:
    controller_id: str
    actor_id: str
    trap_id: str
    attempt_kind: ProcedureAttemptKind
    tool_name: str | None = None


@dataclass(frozen=True)
class TriggerTrapIntent:
    controller_id: str
    trap_id: str
    actor_id: str | None = None
    safe: bool = False


@dataclass(frozen=True)
class BypassTrapIntent:
    controller_id: str
    actor_id: str
    trap_id: str
    party_wide: bool = False


@dataclass(frozen=True)
class AttemptPuzzleIntent:
    controller_id: str
    actor_id: str
    puzzle_id: str
    attempt_kind: ProcedureAttemptKind
    tool_name: str | None = None


@dataclass(frozen=True)
class AbandonPuzzleIntent:
    controller_id: str
    puzzle_id: str


@dataclass(frozen=True)
class AttemptSocialInfluenceIntent:
    controller_id: str
    actor_id: str
    npc_id: str
    approach: SocialApproachType


@dataclass(frozen=True)
class StartDowntimeProjectIntent:
    controller_id: str
    actor_id: str
    activity_id: str


@dataclass(frozen=True)
class WorkDowntimeProjectIntent:
    controller_id: str
    actor_id: str
    project_id: str
    hours: int
    tool_name: str | None = None


@dataclass(frozen=True)
class CancelDowntimeProjectIntent:
    controller_id: str
    project_id: str


def unique_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return tuple(ordered)
