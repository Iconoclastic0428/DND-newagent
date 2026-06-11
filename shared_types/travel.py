from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class HexCoordinateSystem(str, Enum):
    AXIAL = 'axial'


class HexTerrainType(str, Enum):
    CITY = 'city'
    ROAD = 'road'
    TRAIL = 'trail'
    FOREST = 'forest'
    HILLS = 'hills'
    PLAINS = 'plains'
    SETTLEMENT = 'settlement'
    WILDS = 'wilds'


class TravelPace(str, Enum):
    CAUTIOUS = 'cautious'
    NORMAL = 'normal'
    FAST = 'fast'


class TravelStatus(str, Enum):
    IDLE = 'idle'
    ROUTE_PLANNED = 'route-planned'
    IN_PROGRESS = 'in-progress'
    INTERRUPTED = 'interrupted'


class TravelHookType(str, Enum):
    RANDOM_ENCOUNTER_CANDIDATE = 'random_encounter_candidate'
    STORY_ENCOUNTER_CANDIDATE = 'story_encounter_candidate'
    SIDE_QUEST_HOOK = 'side_quest_hook'
    LANDMARK_DISCOVERED = 'landmark_discovered'
    LOCATION_REACHED = 'location_reached'
    TRAVEL_HAZARD_CANDIDATE = 'travel_hazard_candidate'
    SCENE_TRANSITION_CANDIDATE = 'scene_transition_candidate'


class TravelHookTrigger(str, Enum):
    ENTER_HEX = 'enter-hex'
    ROUTE_COMPLETE = 'route-complete'
    LANDMARK_DISCOVERED = 'landmark-discovered'
    LOCATION_REACHED = 'location-reached'


@dataclass(frozen=True)
class HexCoord:
    q: int
    r: int

    def neighbor(self, direction: tuple[int, int]) -> 'HexCoord':
        dq, dr = direction
        return HexCoord(self.q + dq, self.r + dr)


@dataclass(frozen=True)
class HexRenderCoord:
    col: int
    row: int

    def as_tuple(self) -> tuple[int, int]:
        return (self.col, self.row)


@dataclass(frozen=True)
class TravelMapGridBounds:
    min_col: int
    min_row: int
    max_col: int
    max_row: int

    def as_tuple(self) -> tuple[int, int, int, int]:
        return (self.min_col, self.min_row, self.max_col, self.max_row)

    @property
    def cell_count(self) -> int:
        return (self.max_col - self.min_col + 1) * (self.max_row - self.min_row + 1)


@dataclass(frozen=True)
class TravelMapImageSpec:
    url: str
    width_px: int
    height_px: int
    grid_type: str
    grid_size_px: int
    grid_offset_x_px: int
    grid_offset_y_px: int
    grid_scale: int = 1
    units: str = ''
    source_internal_path: str = ''
    grid_bounds: TravelMapGridBounds | None = None

    @property
    def effective_grid_size_px(self) -> int:
        return self.grid_size_px // self.grid_scale

    @property
    def grid_cell_count(self) -> int:
        return 0 if self.grid_bounds is None else self.grid_bounds.cell_count


AXIAL_DIRECTIONS: tuple[tuple[int, int], ...] = (
    (1, 0),
    (1, -1),
    (0, -1),
    (-1, 0),
    (-1, 1),
    (0, 1),
)


@dataclass(frozen=True)
class TravelPaceProfile:
    pace: TravelPace
    minutes_per_cost_unit: int
    discovery_radius: int
    navigation_modifier: int
    encounter_modifier: int


PACE_PROFILES: dict[TravelPace, TravelPaceProfile] = {
    TravelPace.CAUTIOUS: TravelPaceProfile(
        pace=TravelPace.CAUTIOUS,
        minutes_per_cost_unit=75,
        discovery_radius=1,
        navigation_modifier=1,
        encounter_modifier=-1,
    ),
    TravelPace.NORMAL: TravelPaceProfile(
        pace=TravelPace.NORMAL,
        minutes_per_cost_unit=60,
        discovery_radius=1,
        navigation_modifier=0,
        encounter_modifier=0,
    ),
    TravelPace.FAST: TravelPaceProfile(
        pace=TravelPace.FAST,
        minutes_per_cost_unit=45,
        discovery_radius=0,
        navigation_modifier=-1,
        encounter_modifier=1,
    ),
}


@dataclass(frozen=True)
class HexCellDefinition:
    coord: HexCoord
    terrain: HexTerrainType
    travel_cost_units: int
    render_coord: HexRenderCoord | None = None
    route_kind: str | None = None
    route_cost_adjustment_units: int = 0
    landmark_ids: tuple[str, ...] = ()
    location_id: str | None = None
    tags: tuple[str, ...] = ()
    discovered_by_default: bool = False
    traversable: bool = True


@dataclass(frozen=True)
class HexLandmarkDefinition:
    landmark_id: str
    name: str
    coord: HexCoord
    description: str = ''
    location_id: str | None = None
    scene_id: str | None = None
    tags: tuple[str, ...] = ()
    hidden: bool = False
    revealed_by_default: bool = False
    discovery_radius: int = 0


@dataclass(frozen=True)
class TravelHookDefinition:
    hook_id: str
    hook_type: TravelHookType
    trigger: TravelHookTrigger
    summary: str
    coord: HexCoord | None = None
    location_id: str | None = None
    landmark_id: str | None = None
    scene_id: str | None = None
    battlefield_map_id: str | None = None
    tags: tuple[str, ...] = ()
    once: bool = True
    interrupts_travel: bool = False
    suggested_open_loops: tuple[str, ...] = ()
    suggested_party_goals: tuple[str, ...] = ()
    suggested_visible_npc_ids: tuple[str, ...] | None = None


@dataclass(frozen=True)
class HexMapDefinition:
    map_id: str
    campaign_id: str
    region_id: str
    name: str
    coord_system: HexCoordinateSystem = HexCoordinateSystem.AXIAL
    hex_scale_miles: int = 6
    background_image: TravelMapImageSpec | None = None
    cells: tuple[HexCellDefinition, ...] = ()
    landmarks: tuple[HexLandmarkDefinition, ...] = ()
    hooks: tuple[TravelHookDefinition, ...] = ()


@dataclass(frozen=True)
class PlannedTravelRoute:
    destination: HexCoord
    destination_label: str
    path: tuple[HexCoord, ...]
    estimated_cost_units: int
    estimated_minutes: int


@dataclass(frozen=True)
class TravelHexInspection:
    coord: HexCoord
    terrain: HexTerrainType
    travel_cost_units: int
    route_kind: str | None
    discovered: bool
    traversable: bool
    location_id: str | None
    landmark_ids: tuple[str, ...]
    tags: tuple[str, ...]
    reachable_by_known_route: bool


@dataclass(frozen=True)
class TravelState:
    map_id: str
    party_coord: HexCoord
    discovered_hexes: tuple[HexCoord, ...] = ()
    discovered_landmark_ids: tuple[str, ...] = ()
    known_location_ids: tuple[str, ...] = ()
    pace: TravelPace = TravelPace.NORMAL
    status: TravelStatus = TravelStatus.IDLE
    planned_route: PlannedTravelRoute | None = None
    elapsed_minutes: int = 0
    pending_hook: TravelHookDefinition | None = None
    triggered_hook_ids: tuple[str, ...] = ()
    current_scene_id: str | None = None
    current_location_id: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class PlanTravelRouteIntent:
    controller_id: str
    destination: HexCoord | None = None
    destination_location_id: str | None = None


@dataclass(frozen=True)
class SetTravelPaceIntent:
    controller_id: str
    pace: TravelPace


@dataclass(frozen=True)
class AdvanceTravelIntent:
    controller_id: str
    steps: int = 1


@dataclass(frozen=True)
class ResumeTravelIntent:
    controller_id: str


def unique_coords(coords: tuple[HexCoord, ...]) -> tuple[HexCoord, ...]:
    seen: set[tuple[int, int]] = set()
    ordered: list[HexCoord] = []
    for coord in coords:
        key = (coord.q, coord.r)
        if key in seen:
            continue
        seen.add(key)
        ordered.append(coord)
    return tuple(ordered)


def unique_strings(values: tuple[str, ...]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)
