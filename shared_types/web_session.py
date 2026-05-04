from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from typing import Any

from .encounter_control import ControllerRole


@dataclass(frozen=True)
class WebControllerIdentity:
    controller_id: str
    role: ControllerRole
    label: str


@dataclass(frozen=True)
class WebChoiceProjection:
    option_id: str
    label: str
    detail: str
    actor_id: str | None = None


@dataclass(frozen=True)
class WebPromptProjection:
    prompt_id: str
    prompt_kind: str
    text: str
    options: tuple[WebChoiceProjection, ...] = ()


@dataclass(frozen=True)
class WebTileProjection:
    terrain_id: str
    elevation_ft: int


@dataclass(frozen=True)
class WebActorProjection:
    actor_id: str
    name: str
    side: str
    x: int
    y: int
    z: int
    status: str
    turn_active: bool
    private_visible: bool
    tile: WebTileProjection | None = None
    current_hit_points: int | None = None
    max_hit_points: int | None = None
    temp_hit_points: int | None = None
    armor_class: int | None = None
    remaining_movement_ft: int | None = None
    action_available: bool | None = None
    bonus_action_available: bool | None = None
    reaction_available: bool | None = None


@dataclass(frozen=True)
class WebBattlefieldProjection:
    map_id: str
    name: str
    width: int
    height: int
    cell_size_feet: int
    object_count: int
    blocker_count: int
    spawn_zone_ids: tuple[str, ...]


@dataclass(frozen=True)
class WebStoryCheckResultProjection:
    actor_id: str
    actor_label: str
    check_label: str
    selected_roll: int
    total: int
    dc: int
    success: bool
    opposed_actor_label: str | None = None


@dataclass(frozen=True)
class WebTranscriptEntryProjection:
    speaker: str
    text: str
    visibility: str


@dataclass(frozen=True)
class WebStoryProjection:
    runtime_mode: str
    current_scene_id: str
    current_location_id: str | None
    party_goals: tuple[str, ...]
    open_loops: tuple[str, ...]
    party_actor_ids: tuple[str, ...]
    transcript_entries: tuple[WebTranscriptEntryProjection, ...]
    recent_check_results: tuple[WebStoryCheckResultProjection, ...]
    pending_check_text: str | None = None
    pending_check_actor_id: str | None = None
    waiting_on_label: str | None = None


@dataclass(frozen=True)
class WebEncounterProjection:
    phase: str
    round_number: int
    active_actor_id: str | None
    initiative_order: tuple[str, ...]
    actors: tuple[WebActorProjection, ...]
    recent_event_lines: tuple[str, ...]
    battlefield: WebBattlefieldProjection | None = None


@dataclass(frozen=True)
class WebSessionProjection:
    session_kind: str
    state_version: int
    controller: WebControllerIdentity
    summary_lines: tuple[str, ...]
    available_choices: dict[str, tuple[WebChoiceProjection, ...]]
    prompt: WebPromptProjection | None = None
    story: WebStoryProjection | None = None
    encounter: WebEncounterProjection | None = None


@dataclass(frozen=True)
class WebJoinResponse:
    reconnect_token: str
    projection: WebSessionProjection


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [to_jsonable(item) for item in value]
    return value
