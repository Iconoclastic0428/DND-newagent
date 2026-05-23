from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class EncounterChoiceProjection:
    option_id: str
    label: str
    detail: str


@dataclass(frozen=True)
class EncounterChoiceGroupProjection:
    group_id: str
    options: tuple[EncounterChoiceProjection, ...]


@dataclass(frozen=True)
class SemanticMapCellProjection:
    x: int
    y: int
    terrain_id: str
    elevation_ft: int
    ceiling_ft: int
    traversable: bool
    occupiable: bool
    movement_cost_feet_per_5ft: int
    difficult_terrain: bool
    lightly_obscured: bool
    lighting: str
    obscurement: str
    blocks_los: bool
    blocks_loe: bool
    base_cover: str
    supported_modes: tuple[str, ...]
    object_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class SemanticBattlefieldProjection:
    map_id: str
    name: str
    width: int
    height: int
    cell_size_feet: int
    spawn_zones: tuple[str, ...]
    object_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    cells: tuple[SemanticMapCellProjection, ...]


@dataclass(frozen=True)
class EncounterActorPositionProjection:
    x: int
    y: int
    z: int


@dataclass(frozen=True)
class EncounterActorPublicProjection:
    actor_id: str
    name: str
    side: str
    status: str
    position: EncounterActorPositionProjection
    tile_terrain_id: str | None
    tile_elevation_ft: int | None
    turn_active: bool
    visibility_state: str = 'visible'
    support_state: str = 'grounded'


@dataclass(frozen=True)
class EncounterActorPrivateProjection:
    current_hit_points: int
    max_hit_points: int
    temp_hit_points: int
    effective_armor_class: int
    remaining_movement_ft: int
    action_available: bool
    bonus_action_available: bool
    reaction_available: bool
    condition_types: tuple[str, ...]
    dying_status: str | None = None
    death_save_successes: int | None = None
    death_save_failures: int | None = None
    stable_recovery_hours_remaining: int | None = None


@dataclass(frozen=True)
class EncounterActorProjection:
    public: EncounterActorPublicProjection
    private_state: EncounterActorPrivateProjection | None = None


@dataclass(frozen=True)
class ControllerEncounterProjection:
    controller_id: str
    role: str
    phase: str
    round_number: int
    active_actor_id: str | None
    initiative_order: tuple[str, ...]
    battlefield: SemanticBattlefieldProjection | None
    actors: tuple[EncounterActorProjection, ...]
    recent_events: tuple[str, ...]
    recent_event_ids: tuple[str, ...]
    waiting_on_labels: tuple[str, ...]
    choice_groups: tuple[EncounterChoiceGroupProjection, ...]
