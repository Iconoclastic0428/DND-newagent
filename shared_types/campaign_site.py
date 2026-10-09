"""Authored site content and deterministic campaign actions (no DM-model state)."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .encounter_models import EncounterState, GridPosition
from .equipment import ObjectInteractionCostMode


@dataclass(frozen=True)
class SiteConversation:
    npc_id: str
    label: str
    text: str
    grants: tuple[str, ...] = ()


@dataclass(frozen=True)
class TownPlace:
    place_id: str
    name: str
    x: float
    y: float
    description: str
    conversations: tuple[SiteConversation, ...]


@dataclass(frozen=True)
class SiteEntrance:
    entrance_id: str
    label: str
    place_id: str
    required_flag: str | None
    positions: tuple[GridPosition, ...]


@dataclass(frozen=True)
class SiteRoom:
    room_id: str
    name: str
    cells: tuple[GridPosition, ...]
    description: str


@dataclass(frozen=True)
class SiteDoor:
    door_id: str
    label: str
    cells: tuple[GridPosition, ...]
    secret: bool = False
    locked: bool = False
    search_dc: int = 15
    lock_dc: int = 10
    force_dc: int = 20
    key_flag: str | None = None


@dataclass(frozen=True)
class SiteMonster:
    actor_id: str
    monster_id: str
    name: str
    position: GridPosition
    conditions: tuple[str, ...] = ()
    prepared_spell_ids: tuple[str, ...] = ()
    spell_slot_counts: tuple[int, ...] = ()


@dataclass(frozen=True)
class SiteEncounter:
    encounter_id: str
    room_id: str
    label: str
    monsters: tuple[SiteMonster, ...]
    trigger_cells: tuple[GridPosition, ...]
    automatic: bool
    resolved_grants: tuple[str, ...]
    bypass_flag: str | None = None


@dataclass(frozen=True)
class SiteInteraction:
    interaction_id: str
    room_id: str
    label: str
    text: str
    grants: tuple[str, ...]
    requires: tuple[str, ...] = ()
    kind: str = 'discover'
    ability: str | None = None
    skill: str | None = None
    dc: int | None = None
    required_open_doors: tuple[str, ...] = ()
    required_living_encounter: str | None = None
    reveals_doors: tuple[str, ...] = ()


@dataclass(frozen=True)
class SiteHazard:
    hazard_id: str
    label: str
    cells: tuple[GridPosition, ...]
    detection_ability: str
    detection_skill: str
    detection_dc: int
    depth_ft: int
    save_dc: int | None = None
    weight_threshold_lb: int = 0
    weight_threshold_inclusive: bool = False
    feature_id: str | None = None


@dataclass(frozen=True)
class CampaignSiteDefinition:
    site_id: str
    town_location_id: str
    dungeon_location_id: str
    town_image: str
    town_width_px: int
    town_height_px: int
    battlefield_path: str
    arrival_text: str
    places: dict[str, TownPlace]
    entrances: dict[str, SiteEntrance]
    rooms: dict[str, SiteRoom]
    doors: dict[str, SiteDoor]
    encounters: dict[str, SiteEncounter]
    interactions: dict[str, SiteInteraction]
    hazards: dict[str, SiteHazard]
    chapter_id: str
    arrival_scene_id: str
    dungeon_scene_id: str
    arrival_goals: tuple[str, ...]
    arrival_open_loops: tuple[str, ...]
    return_grants: tuple[tuple[str, str], ...]


class SiteAction(str, Enum):
    ARRIVE = 'arrive'
    VISIT = 'visit'
    TALK = 'talk'
    ENTER = 'enter'
    LEAVE = 'leave'
    SEARCH = 'search'
    OPEN = 'open'
    CLOSE = 'close'
    PICK_LOCK = 'pick-lock'
    FORCE = 'force'
    INTERACT = 'interact'
    ENGAGE = 'engage'
    RESOLVE_COMBAT = 'resolve-combat'
    OBSERVE = 'observe'
    SET_WEIGHT = 'weight'


@dataclass(frozen=True)
class CampaignSiteIntent:
    actor_id: str
    action: SiteAction
    target_id: str | None = None
    weight_lb: float | None = None
    cost_mode: ObjectInteractionCostMode = ObjectInteractionCostMode.FREE


@dataclass(frozen=True)
class CampaignSiteProgress:
    site_id: str
    arrived: bool = False
    in_dungeon: bool = False
    place_id: str | None = None
    flags: frozenset[str] = frozenset()
    discovered_doors: frozenset[str] = frozenset()
    unlocked_doors: frozenset[str] = frozenset()
    opened_doors: frozenset[str] = frozenset()
    visited_rooms: frozenset[str] = frozenset()
    resolved_encounters: frozenset[str] = frozenset()
    completed_interactions: frozenset[str] = frozenset()
    detected_hazards: frozenset[str] = frozenset()
    triggered_hazards: frozenset[str] = frozenset()
    active_encounter_id: str | None = None


@dataclass(frozen=True)
class CampaignSiteProgressedEvent:
    intent: CampaignSiteIntent
    progress: CampaignSiteProgress
    public_text: str


@dataclass(frozen=True)
class SiteCheckResolvedEvent:
    actor_id: str
    target_id: str
    ability: str
    skill: str | None
    dc: int
    roll: int
    total: int
    success: bool
    random_counter_used: int


@dataclass
class CampaignSiteState:
    progress: CampaignSiteProgress
    # Scene snapshots preserve authoritative actors, objects and geometry between visits.
    scenes: dict[str, EncounterState] = field(default_factory=dict)
    pending_movement: SiteMovementWatch | None = None


@dataclass(frozen=True)
class SiteMovementWatch:
    actor_id: str
    destination: GridPosition
    edge_position: GridPosition
    hazard_id: str | None


@dataclass(frozen=True)
class SiteMovementWatchSetEvent:
    watch: SiteMovementWatch | None


@dataclass(frozen=True)
class SiteSceneActivatedEvent:
    previous_scene_id: str
    scene_id: str
    scene: EncounterState
    party_positions: tuple[tuple[str, GridPosition], ...]


@dataclass(frozen=True)
class SiteDoorChangedEvent:
    door_id: str
    opened: bool


@dataclass(frozen=True)
class SiteCombatEndedEvent:
    encounter_id: str


@dataclass(frozen=True)
class SiteHazardTriggeredEvent:
    hazard_id: str


@dataclass(frozen=True)
class SiteEdgeCaughtEvent:
    actor_id: str
    position: GridPosition


@dataclass(frozen=True)
class SiteActorWeightSetEvent:
    actor_id: str
    weight_lb: float


@dataclass(frozen=True)
class CampaignSiteResolution:
    encounter_state: EncounterState
    site_state: CampaignSiteState
    events: tuple[object, ...]
    public_text: tuple[str, ...]
