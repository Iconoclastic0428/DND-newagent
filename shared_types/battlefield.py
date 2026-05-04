from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .visibility import LightLevel, LightingLevel, ObscurementLevel

if TYPE_CHECKING:
    from .encounter_models import GridPosition


class CoverLevel(str, Enum):
    NONE = 'none'
    HALF = 'half'
    THREE_QUARTERS = 'three-quarters'
    TOTAL = 'total'


class EdgeTransitionType(str, Enum):
    FLAT = 'flat'
    SLOPE = 'slope'
    RAMP = 'ramp'
    DIFFICULT_SLOPE = 'difficult_slope'
    CLIMBABLE_LEDGE = 'climbable_ledge'
    IMPASSABLE_FACE = 'impassable_face'
    DROP = 'drop'
    BLOCKED = 'blocked'


class EdgeTraversalRequirement(str, Enum):
    NONE = 'none'
    CLIMB = 'climb'
    CLIMB_SPEED = 'climb_speed'
    SPECIAL = 'special'
    BLOCKED = 'blocked'


class TraversalMode(str, Enum):
    WALK = 'walk'
    CRAWL = 'crawl'
    CLIMB = 'climb'
    SWIM = 'swim'
    FLY = 'fly'
    TELEPORT = 'teleport'


class RelocationType(str, Enum):
    PATH = 'path'
    TELEPORT = 'teleport'


class SupportStateType(str, Enum):
    GROUNDED = 'grounded'
    CLIMBING = 'climbing'
    SWIMMING = 'swimming'
    FLYING = 'flying'
    HOVERING = 'hovering'
    UNSUPPORTED = 'unsupported'
    FALLING = 'falling'


class LandingSurfaceType(str, Enum):
    SOLID = 'solid'
    LIQUID = 'liquid'
    NONE = 'none'


class FallReason(str, Enum):
    UNSUPPORTED_RELOCATION = 'unsupported-relocation'
    PRONE_WHILE_FLYING = 'prone-while-flying'
    INCAPACITATED_WHILE_FLYING = 'incapacitated-while-flying'
    FLY_SPEED_ZERO = 'fly-speed-zero'
    FORCED_RELOCATION = 'forced-relocation'
    STATE_CHANGE = 'state-change'


class MovementIntentMode(str, Enum):
    SAME_PLANE = 'same-plane'
    ALLOW_ELEVATION = 'allow-elevation'
    ALLOW_CLIMB = 'allow-climb'
    ALLOW_FLY = 'allow-fly'


class MovementPreviewOutcome(str, Enum):
    REACHABLE_SAME_PLANE = 'reachable_same_plane'
    REACHABLE_WITH_SLOPE = 'reachable_with_slope'
    REACHABLE_WITH_CLIMB = 'reachable_with_climb'
    REACHABLE_WITH_FLY = 'reachable_with_fly'
    UNREACHABLE_BLOCKED = 'unreachable_blocked'
    UNREACHABLE_BLOCKED_AIRSPACE = 'unreachable_blocked_airspace'
    UNREACHABLE_NO_TRAVERSABLE_EDGE = 'unreachable_no_traversable_edge'
    UNREACHABLE_INSUFFICIENT_MOVEMENT = 'unreachable_insufficient_movement'
    UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION = 'unreachable_requires_vertical_confirmation'


class UnreachableReason(str, Enum):
    OUTSIDE_BATTLEFIELD = 'outside_battlefield'
    DESTINATION_OCCUPIED = 'destination_occupied'
    DESTINATION_BLOCKED = 'destination_blocked'
    DESTINATION_BLOCKED_AIRSPACE = 'destination_blocked_airspace'
    SPEED_ZERO = 'speed_zero'
    NO_SAME_PLANE_PATH = 'no_same_plane_path'
    NO_TRAVERSABLE_EDGE = 'no_traversable_edge'
    IMPASSABLE_EDGE = 'impassable_edge'
    REQUIRES_VERTICAL_CONFIRMATION = 'requires_vertical_confirmation'
    REQUIRES_CLIMB = 'requires_climb'
    REQUIRES_CLIMB_SPEED = 'requires_climb_speed'
    REQUIRES_FLY = 'requires_fly'
    AMBIGUOUS_ALTITUDE = 'ambiguous_altitude'
    INSUFFICIENT_MOVEMENT = 'insufficient_movement'
    INSUFFICIENT_CLEARANCE = 'insufficient_clearance'


@dataclass(frozen=True)
class BattlefieldGridSpec:
    cell_size_feet: int
    width: int
    height: int
    origin: str
    coordinates: str
    min_x: int
    min_y: int
    max_x: int
    max_y: int


@dataclass(frozen=True)
class OccupiedVolume:
    x: int
    y: int
    z: int
    width_cells: int = 1
    depth_cells: int = 1
    height_ft: int = 5

    @property
    def top_z(self) -> int:
        return self.z + self.height_ft

    def intersects(self, other: 'OccupiedVolume') -> bool:
        horizontal_overlap = not (
            self.x + self.width_cells <= other.x
            or other.x + other.width_cells <= self.x
            or self.y + self.depth_cells <= other.y
            or other.y + other.depth_cells <= self.y
        )
        vertical_overlap = not (self.top_z <= other.z or other.top_z <= self.z)
        return horizontal_overlap and vertical_overlap


@dataclass(frozen=True)
class BattlefieldTile:
    position: 'GridPosition'
    terrain_id: str
    elevation_ft: int
    ceiling_ft: int
    traversable: bool
    occupiable: bool
    movement_cost_feet_per_5ft: int
    difficult_terrain: bool
    lightly_obscured: bool
    lighting: LightingLevel = LightingLevel.BRIGHT
    obscurement: ObscurementLevel = ObscurementLevel.NONE
    blocks_los: bool = False
    blocks_loe: bool = False
    base_cover: CoverLevel = CoverLevel.NONE
    supported_modes: tuple[TraversalMode, ...] = (TraversalMode.WALK, TraversalMode.CLIMB, TraversalMode.FLY)
    object_ids: tuple[str, ...] = ()
    blocker_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    @property
    def light_level(self) -> LightLevel:
        return LightLevel(self.lighting.value)

    @property
    def heavily_obscured(self) -> bool:
        return self.obscurement == ObscurementLevel.HEAVY

    @property
    def airspace_bottom_ft(self) -> int:
        return self.elevation_ft


@dataclass(frozen=True)
class BattlefieldFeature:
    feature_id: str
    feature_type: str
    cells: tuple['GridPosition', ...]
    elevation_ft: int
    traversable: bool
    occupiable: bool
    light_level: LightLevel = LightLevel.BRIGHT
    obscurement: ObscurementLevel = ObscurementLevel.NONE
    blocks_los: bool = False
    blocks_loe: bool = False
    cover_provided: CoverLevel = CoverLevel.NONE
    bottom_ft: int = 0
    top_ft: int = 0
    movement_cost_override_feet_per_5ft: int | None = None
    rotation_deg: int | None = None
    tags: tuple[str, ...] = ()

    @property
    def heavily_obscured(self) -> bool:
        return self.obscurement == ObscurementLevel.HEAVY

    def volumes(self) -> tuple[OccupiedVolume, ...]:
        return tuple(
            OccupiedVolume(x=cell.x, y=cell.y, z=self.bottom_ft, width_cells=1, depth_cells=1, height_ft=max(0, self.top_ft - self.bottom_ft))
            for cell in self.cells
        )


@dataclass(frozen=True)
class ElevationTransitionRule:
    threshold_feet: int
    transition_type: EdgeTransitionType
    traversal_requirement: EdgeTraversalRequirement
    effect: str
    movement: str
    extra_movement_cost_feet: int
    extra_movement_cost_with_climb_speed_feet: int | None
    blocks_diagonal_corner_cutting: bool
    cover_from_low_to_high: CoverLevel
    cover_from_high_to_low: CoverLevel


@dataclass(frozen=True)
class BattlefieldEdge:
    cells: tuple['GridPosition', 'GridPosition']
    transition_type: EdgeTransitionType
    traversal_requirement: EdgeTraversalRequirement
    height_change_ft: int
    extra_movement_cost_feet: int
    extra_movement_cost_with_climb_speed_feet: int | None
    blocks_los: bool
    blocks_loe: bool
    cover_from_low_to_high: CoverLevel = CoverLevel.NONE
    cover_from_high_to_low: CoverLevel = CoverLevel.NONE
    blocks_diagonal_corner_cutting: bool = False

    @property
    def requires_climb(self) -> bool:
        return self.traversal_requirement in {EdgeTraversalRequirement.CLIMB, EdgeTraversalRequirement.CLIMB_SPEED}


@dataclass(frozen=True)
class BattlefieldIntegrationHints:
    battlefield_state_key: str
    recommended_queries: tuple[str, ...]
    public_sync_fields: tuple[str, ...]


@dataclass(frozen=True)
class MovementSegment:
    from_position: 'GridPosition'
    to_position: 'GridPosition'
    start_elevation_ft: int
    end_elevation_ft: int
    transition_type: EdgeTransitionType
    traversal_requirement: EdgeTraversalRequirement
    traversal_mode: TraversalMode
    movement_cost_ft: int
    requires_climb: bool
    used_climb_speed: bool


@dataclass(frozen=True)
class MovementPlan:
    path: tuple['GridPosition', ...]
    segments: tuple[MovementSegment, ...]
    total_cost_ft: int
    destination_elevation_ft: int
    includes_elevation_change: bool
    requires_climb: bool
    requires_fly: bool = False


@dataclass(frozen=True)
class SpeedBudget:
    mode: TraversalMode
    speed_ft: int
    spent_ft: int
    dash_bonus_ft: int = 0

    @property
    def total_budget_ft(self) -> int:
        return max(0, self.speed_ft + self.dash_bonus_ft)

    @property
    def remaining_ft(self) -> int:
        return max(0, self.total_budget_ft - self.spent_ft)


@dataclass(frozen=True)
class RelocationEffect:
    relocation_type: RelocationType
    movement_mode: TraversalMode
    range_ft: int | None
    requires_visible_destination: bool
    requires_unoccupied_destination: bool
    requires_line_of_effect: bool
    consumes_movement: bool


@dataclass(frozen=True)
class RelocationResult:
    relocation_type: RelocationType
    movement_mode: TraversalMode
    destination: 'GridPosition'
    distance_ft: int
    range_ft: int | None
    movement_cost_ft: int
    within_range: bool
    destination_visible: bool
    destination_unoccupied: bool
    destination_legal: bool
    detail: str = ''


@dataclass(frozen=True)
class SupportStateEvaluation:
    actor_id: str
    position: 'GridPosition'
    support_state: SupportStateType
    supported: bool
    requires_fall: bool
    landing_surface_type: LandingSurfaceType = LandingSurfaceType.NONE
    reason: FallReason | None = None
    detail: str = ''


@dataclass(frozen=True)
class LandingResult:
    actor_id: str
    start_position: 'GridPosition'
    landing_position: 'GridPosition'
    landing_surface_type: LandingSurfaceType
    distance_ft: int
    blocked_descent: bool = False
    liquid_reaction_available: bool = False
    detail: str = ''


@dataclass(frozen=True)
class FallResolution:
    actor_id: str
    reason: FallReason
    start_position: 'GridPosition'
    landing_position: 'GridPosition'
    landing_surface_type: LandingSurfaceType
    distance_ft: int
    damage_dice_count: int


@dataclass(frozen=True)
class MovementPreview:
    outcome: MovementPreviewOutcome
    destination: 'GridPosition'
    target_elevation_ft: int
    movement_intent_mode: MovementIntentMode
    total_cost_ft: int | None
    requires_climb: bool
    requires_fly: bool
    climb_speed_available: bool
    normal_movement_allowed: bool
    unreachable_reason: UnreachableReason | None = None
    plan: MovementPlan | None = None
    same_plane_plan: MovementPlan | None = None
    suggested_plan: MovementPlan | None = None
    blocking_segment: MovementSegment | None = None
    detail: str = ''


@dataclass
class BattlefieldState:
    map_id: str = ''
    name: str = ''
    grid: BattlefieldGridSpec | None = None
    tiles: dict['GridPosition', BattlefieldTile] = field(default_factory=dict)
    base_tiles: dict['GridPosition', BattlefieldTile] = field(default_factory=dict)
    features: dict[str, BattlefieldFeature] = field(default_factory=dict)
    edges: dict[tuple['GridPosition', 'GridPosition'], BattlefieldEdge] = field(default_factory=dict)
    spawn_zones: dict[str, tuple['GridPosition', ...]] = field(default_factory=dict)
    integration_hints: BattlefieldIntegrationHints | None = None
    default_elevation_transition_rule: ElevationTransitionRule | None = None
    terrain_region_ids: tuple[str, ...] = ()
    object_ids: tuple[str, ...] = ()
    blocker_ids: tuple[str, ...] = ()
    known_dynamic_overlays: tuple[str, ...] = ()
    dynamic_feature_ids: tuple[str, ...] = ()
    difficult_terrain_positions: frozenset['GridPosition'] = frozenset()
    cover_by_pair: dict[tuple[str, str], CoverLevel] = field(default_factory=dict)
    default_airspace_top_ft: int = 40

    @property
    def has_authored_map(self) -> bool:
        return self.grid is not None and bool(self.tiles)


def edge_key(a: 'GridPosition', b: 'GridPosition') -> tuple['GridPosition', 'GridPosition']:
    first = (a.x, a.y)
    second = (b.x, b.y)
    return (a, b) if first <= second else (b, a)
