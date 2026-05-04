from __future__ import annotations

from dataclasses import dataclass

from .encounter_control import ControllerRole
from .encounter_models import EncounterPhase


@dataclass(frozen=True)
class WebCoordinate:
    x: int
    y: int
    z: int = 0


@dataclass(frozen=True)
class WebHexCoordinate:
    q: int
    r: int


@dataclass(frozen=True)
class WebActionChoiceView:
    group_id: str
    option_id: str
    label: str
    detail: str
    execution_kind: str
    target_kind: str
    target_affinity: str | None = None
    command_hint: str | None = None
    command_insert_text: str | None = None
    command_prefix: str | None = None


@dataclass(frozen=True)
class WebActionGroupView:
    group_id: str
    label: str
    choices: tuple[WebActionChoiceView, ...]


@dataclass(frozen=True)
class WebPromptOptionView:
    option_id: str
    label: str
    detail: str
    actor_id: str | None = None


@dataclass(frozen=True)
class WebPromptView:
    prompt_id: str
    prompt_kind: str
    text: str
    options: tuple[WebPromptOptionView, ...]


@dataclass(frozen=True)
class WebChatEntryView:
    entry_id: str
    speaker: str
    text: str
    category: str
    visibility: str


@dataclass(frozen=True)
class WebCharacterSpeedView:
    mode_id: str
    label: str
    speed_ft: int


@dataclass(frozen=True)
class WebCharacterAbilityView:
    ability_id: str
    label: str
    score: int
    modifier: int
    save_bonus: int
    save_proficient: bool


@dataclass(frozen=True)
class WebCharacterSkillView:
    skill_id: str
    label: str
    bonus: int
    proficient: bool


@dataclass(frozen=True)
class WebCharacterAttackView:
    attack_id: str
    name: str
    attack_kind: str
    to_hit_bonus: int
    damage_text: str
    reach_ft: int | None = None
    range_ft: int | None = None
    long_range_ft: int | None = None


@dataclass(frozen=True)
class WebCharacterSpellView:
    spell_id: str
    name: str
    level: int
    selection_kind: str
    source_label: str
    remaining_uses: int | None = None


@dataclass(frozen=True)
class WebCharacterResourceView:
    resource_id: str
    label: str
    detail: str
    remaining_uses: int | None = None


@dataclass(frozen=True)
class WebCharacterEffectView:
    effect_id: str
    name: str
    summary: str
    remaining_rounds: int | None = None
    concentration: bool = False


@dataclass(frozen=True)
class WebCharacterItemView:
    item_id: str
    label: str
    quantity: int
    state_label: str | None = None


@dataclass(frozen=True)
class WebCharacterCardView:
    actor_id: str
    character_id: str | None
    name: str
    avatar_label: str
    class_name: str | None
    level: int | None
    species_name: str | None
    background_name: str | None
    proficiency_bonus: int | None
    current_hit_points: int | None
    max_hit_points: int | None
    temp_hit_points: int | None
    armor_class: int | None
    initiative_bonus: int | None
    movement_remaining_ft: int | None
    free_object_interaction_available: bool | None = None
    dying_status: str | None = None
    death_save_successes: int | None = None
    death_save_failures: int | None = None
    stable_recovery_hours_remaining: int | None = None
    active_turn: bool = False
    action_available: bool | None = None
    bonus_action_available: bool | None = None
    reaction_available: bool | None = None
    spellcasting_ability: str | None = None
    spell_save_dc: int | None = None
    spell_attack_bonus: int | None = None
    passive_perception: int | None = None
    concentration_effect_name: str | None = None
    origin_feats: tuple[str, ...] = ()
    feat_summaries: tuple[str, ...] = ()
    tool_proficiencies: tuple[str, ...] = ()
    main_hand_label: str | None = None
    off_hand_label: str | None = None
    armor_label: str | None = None
    speeds: tuple[WebCharacterSpeedView, ...] = ()
    abilities: tuple[WebCharacterAbilityView, ...] = ()
    skills: tuple[WebCharacterSkillView, ...] = ()
    conditions: tuple[str, ...] = ()
    effects: tuple[WebCharacterEffectView, ...] = ()
    attacks: tuple[WebCharacterAttackView, ...] = ()
    cantrips: tuple[WebCharacterSpellView, ...] = ()
    spells: tuple[WebCharacterSpellView, ...] = ()
    resources: tuple[WebCharacterResourceView, ...] = ()
    items: tuple[WebCharacterItemView, ...] = ()


@dataclass(frozen=True)
class WebTokenView:
    actor_id: str
    name: str
    side: str
    position: WebCoordinate
    occupied_height_ft: int
    support_state: str
    status: str
    is_active: bool
    is_owner: bool
    visibility_state: str = 'visible'
    hit_points: int | None = None
    max_hit_points: int | None = None
    temp_hit_points: int | None = None
    armor_class: int | None = None
    movement_remaining_ft: int | None = None
    action_available: bool | None = None
    bonus_action_available: bool | None = None
    reaction_available: bool | None = None
    visible_conditions: tuple[str, ...] = ()


@dataclass(frozen=True)
class WebMapCellView:
    position: WebCoordinate
    terrain_id: str
    elevation_ft: int
    ceiling_ft: int
    traversable: bool
    occupiable: bool
    movement_cost_feet_per_5ft: int
    difficult_terrain: bool
    lighting: str
    obscurement: str
    blocks_los: bool
    blocks_loe: bool
    base_cover: str
    supported_modes: tuple[str, ...]
    object_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    tags: tuple[str, ...]
    apparent_blocked: bool = False
    apparent_cover: str | None = None
    apparent_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WebMapFeatureView:
    feature_id: str
    feature_type: str
    cells: tuple[WebCoordinate, ...]
    elevation_ft: int
    bottom_ft: int
    top_ft: int
    traversable: bool
    occupiable: bool
    blocks_los: bool
    blocks_loe: bool
    cover_provided: str
    tags: tuple[str, ...]
    display_name: str | None = None
    display_description: str | None = None
    apparent_only: bool = False
    observer_state: str | None = None
    apparent_blocker: bool = False
    apparent_cover: str | None = None
    actual_blocker: bool = False
    actual_cover: bool = False


@dataclass(frozen=True)
class WebMapGridView:
    width: int
    height: int
    cell_size_feet: int
    min_x: int
    min_y: int
    max_x: int
    max_y: int


@dataclass(frozen=True)
class WebMapView:
    map_id: str | None
    name: str
    grid: WebMapGridView | None
    cells: tuple[WebMapCellView, ...]
    features: tuple[WebMapFeatureView, ...]
    tokens: tuple[WebTokenView, ...]


@dataclass(frozen=True)
class WebTravelLandmarkView:
    landmark_id: str
    name: str
    coord: WebHexCoordinate
    description: str
    location_id: str | None
    scene_id: str | None
    tags: tuple[str, ...]
    hidden: bool = False


@dataclass(frozen=True)
class WebTravelRouteView:
    destination: WebHexCoordinate
    destination_label: str
    path: tuple[WebHexCoordinate, ...]
    estimated_cost_units: int
    estimated_minutes: int


@dataclass(frozen=True)
class WebTravelHookView:
    hook_id: str
    hook_type: str
    summary: str
    coord: WebHexCoordinate | None
    location_id: str | None
    scene_id: str | None
    battlefield_map_id: str | None
    interrupts_travel: bool


@dataclass(frozen=True)
class WebTravelHexView:
    coord: WebHexCoordinate
    terrain_id: str
    travel_cost_units: int
    route_kind: str | None
    traversable: bool
    discovered: bool
    current_party: bool = False
    on_planned_route: bool = False
    landmark_ids: tuple[str, ...] = ()
    location_id: str | None = None
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WebTravelMapView:
    map_id: str
    name: str
    region_id: str
    coordinate_system: str
    hex_scale_miles: int
    dm_view: bool
    current_party_coord: WebHexCoordinate
    pace: str
    status: str
    elapsed_minutes: int
    hexes: tuple[WebTravelHexView, ...]
    landmarks: tuple[WebTravelLandmarkView, ...]
    planned_route: WebTravelRouteView | None = None
    pending_hook: WebTravelHookView | None = None


@dataclass(frozen=True)
class WebCellTraversalView:
    mode_id: str
    outcome: str
    detail: str
    total_cost_ft: int | None
    target_elevation_ft: int
    requires_climb: bool
    requires_fly: bool


@dataclass(frozen=True)
class WebTeleportLegalityView:
    capability_id: str
    capability_name: str
    legal: bool
    detail: str
    range_ft: int | None
    distance_ft: int


@dataclass(frozen=True)
class WebCellInspectionView:
    position: WebCoordinate
    terrain_id: str
    elevation_ft: int
    ceiling_ft: int
    traversable: bool
    occupiable: bool
    movement_cost_feet_per_5ft: int
    difficult_terrain: bool
    lighting: str
    obscurement: str
    blocks_los: bool
    blocks_loe: bool
    base_cover: str
    supported_modes: tuple[str, ...]
    object_ids: tuple[str, ...]
    blocker_ids: tuple[str, ...]
    tags: tuple[str, ...]
    feature_ids: tuple[str, ...]
    edge_summaries: tuple[str, ...]
    traversal_views: tuple[WebCellTraversalView, ...]
    teleport_views: tuple[WebTeleportLegalityView, ...]
    apparent_blocked: bool = False
    apparent_cover: str | None = None
    apparent_tags: tuple[str, ...] = ()
    feature_summaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class WebTravelHexInspectionView:
    coord: WebHexCoordinate
    terrain_id: str
    travel_cost_units: int
    route_kind: str | None
    discovered: bool
    traversable: bool
    location_id: str | None
    landmark_ids: tuple[str, ...]
    tags: tuple[str, ...]
    reachable_by_known_route: bool


@dataclass(frozen=True)
class WebPathPreviewView:
    actor_id: str
    destination: WebCoordinate
    outcome: str
    detail: str
    total_cost_ft: int | None
    target_elevation_ft: int
    requires_climb: bool
    requires_fly: bool
    path: tuple[WebCoordinate, ...]


@dataclass(frozen=True)
class WebTravelRoutePreviewView:
    destination: WebHexCoordinate
    destination_label: str
    path: tuple[WebHexCoordinate, ...]
    estimated_cost_units: int
    estimated_minutes: int


@dataclass(frozen=True)
class WebSessionView:
    session_id: str
    controller_id: str
    controller_label: str
    role: ControllerRole
    runtime_mode: str
    encounter_phase: EncounterPhase | None
    current_scene_id: str | None
    current_location_id: str | None
    round_number: int | None
    active_actor_id: str | None
    initiative_order: tuple[str, ...]
    owned_actor_ids: tuple[str, ...]
    party_goals: tuple[str, ...]
    open_loops: tuple[str, ...]
    summary_lines: tuple[str, ...]
    action_groups: tuple[WebActionGroupView, ...]
    prompt: WebPromptView | None
    map: WebMapView | None
    travel: WebTravelMapView | None
    chat_entries: tuple[WebChatEntryView, ...]
    character_cards: tuple[WebCharacterCardView, ...] = ()


@dataclass(frozen=True)
class WebControllerGrant:
    session_id: str
    controller_id: str
    controller_token: str
    role: ControllerRole
    label: str

