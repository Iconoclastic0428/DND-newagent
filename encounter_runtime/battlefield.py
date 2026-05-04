from __future__ import annotations

from dataclasses import dataclass
import heapq
import math

from shared_types.battlefield import BattlefieldEdge, BattlefieldState, BattlefieldTile, CoverLevel, EdgeTransitionType, EdgeTraversalRequirement, FallReason, LandingResult, LandingSurfaceType, MovementIntentMode, MovementPlan, MovementPreview, MovementPreviewOutcome, MovementSegment, OccupiedVolume, RelocationResult, RelocationType, SpeedBudget, SupportStateEvaluation, SupportStateType, TraversalMode, UnreachableReason, edge_key
from shared_types.conditions import ConditionType
from shared_types.encounter_models import AttackKind, AttackProfile, EncounterState, GridPosition, RuntimeActorState
from shared_types.errors import EncounterValidationError
from rules_engine.encounter_math import grid_distance_ft

from .conditions import get_condition_state, get_effective_speed


@dataclass(frozen=True)
class MovementLegality:
    from_position: GridPosition
    to_position: GridPosition
    path: tuple[GridPosition, ...]
    distance_ft: int
    movement_cost_ft: int
    preview: MovementPreview
    plan: MovementPlan


@dataclass(frozen=True)
class AttackLegality:
    distance_ft: int
    cover_level: CoverLevel
    armor_class_bonus: int
    long_range_disadvantage: bool
    has_line_of_sight: bool
    has_line_of_effect: bool


@dataclass(frozen=True)
class StandLegality:
    movement_cost_ft: int
    remaining_movement_ft_after: int


class BattlefieldRules:
    def get_tile(self, battlefield: BattlefieldState, x: int, y: int) -> BattlefieldTile:
        pos = GridPosition(x, y)
        if battlefield.has_authored_map:
            tile = battlefield.tiles.get(pos)
            if tile is None:
                raise EncounterValidationError(f'The destination ({x}, {y}) is outside the authored battlefield.')
            return tile
        return BattlefieldTile(position=pos, terrain_id='open_ground', elevation_ft=0, ceiling_ft=battlefield.default_airspace_top_ft or 40, traversable=True, occupiable=True, movement_cost_feet_per_5ft=(10 if pos in battlefield.difficult_terrain_positions else 5), difficult_terrain=pos in battlefield.difficult_terrain_positions, lightly_obscured=False, blocks_los=False, blocks_loe=False, base_cover=CoverLevel.NONE)

    def surface_position(self, battlefield: BattlefieldState, x: int, y: int) -> GridPosition:
        tile = self.get_tile(battlefield, x, y)
        return GridPosition(x, y, tile.elevation_ft)

    def get_position3d(self, actor: RuntimeActorState) -> GridPosition:
        return actor.position

    def get_occupied_volume(self, actor: RuntimeActorState) -> OccupiedVolume:
        return actor.occupied_volume

    def get_cell_elevation(self, battlefield: BattlefieldState, cell: GridPosition) -> int:
        return self.get_tile(battlefield, cell.x, cell.y).elevation_ft

    def get_elevation_ft(self, battlefield: BattlefieldState, x: int, y: int) -> int:
        return self.get_tile(battlefield, x, y).elevation_ft

    def get_height_difference(self, battlefield: BattlefieldState, a: GridPosition, b: GridPosition) -> int:
        return self.get_elevation_ft(battlefield, b.x, b.y) - self.get_elevation_ft(battlefield, a.x, a.y)

    def get_distance(self, a: GridPosition, b: GridPosition) -> int:
        return grid_distance_ft(a, b)

    def get_distance3d(self, a: GridPosition, b: GridPosition) -> int:
        return grid_distance_ft(a, b)

    def speed_budget_for_mode(self, actor: RuntimeActorState, mode: TraversalMode) -> SpeedBudget:
        base_speed = 0
        if mode in {TraversalMode.WALK, TraversalMode.CRAWL}:
            base_speed = get_effective_speed(actor)
        elif mode == TraversalMode.CLIMB:
            base_speed = actor.climb_speed_ft if actor.climb_speed_ft > 0 else get_effective_speed(actor)
        elif mode == TraversalMode.SWIM:
            base_speed = actor.swim_speed_ft
        elif mode == TraversalMode.FLY:
            base_speed = actor.fly_speed_ft
        return SpeedBudget(mode=mode, speed_ft=base_speed, spent_ft=actor.movement_spent_ft, dash_bonus_ft=actor.dash_bonus_ft)

    def max_remaining_movement_ft(self, actor: RuntimeActorState) -> int:
        budgets = [
            self.speed_budget_for_mode(actor, TraversalMode.WALK).remaining_ft,
            self.speed_budget_for_mode(actor, TraversalMode.CLIMB).remaining_ft,
            self.speed_budget_for_mode(actor, TraversalMode.SWIM).remaining_ft,
            self.speed_budget_for_mode(actor, TraversalMode.FLY).remaining_ft,
        ]
        return max(budgets, default=0)

    def has_line_of_sight_to_position(self, state: EncounterState, observer: RuntimeActorState, destination: GridPosition) -> bool:
        return self._has_line_between_positions(state, observer.position, observer.occupied_height_ft, destination, for_effect=False)

    def has_line_of_effect_to_position(self, state: EncounterState, observer: RuntimeActorState, destination: GridPosition) -> bool:
        return self._has_line_between_positions(state, observer.position, observer.occupied_height_ft, destination, for_effect=True)

    def teleport_legality(self, state: EncounterState, actor: RuntimeActorState, destination: GridPosition, *, range_ft: int | None, requires_visible_destination: bool, requires_unoccupied_destination: bool, requires_line_of_effect: bool = False) -> RelocationResult:
        distance_ft = self.get_distance3d(actor.position, destination)
        within_range = range_ft is None or distance_ft <= range_ft
        destination_visible = (not requires_visible_destination) or self.has_line_of_sight_to_position(state, actor, destination)
        destination_effective = (not requires_line_of_effect) or self.has_line_of_effect_to_position(state, actor, destination)
        destination_occupiable = self.is_volume_occupiable(state, OccupiedVolume(destination.x, destination.y, destination.z, height_ft=actor.occupied_height_ft), actor, ignore_actor_id=actor.actor_id)
        destination_legal = destination_effective and (destination_occupiable if requires_unoccupied_destination else True)
        if not within_range:
            detail = f'The destination is {distance_ft} ft away, beyond the allowed {range_ft} ft range.'
        elif not destination_visible:
            detail = 'The destination space cannot be seen from the actor''s current position.'
        elif not destination_effective:
            detail = 'The destination space is blocked from the actor''s line of effect.'
        elif requires_unoccupied_destination and not destination_occupiable:
            detail = 'The destination space is occupied or blocked.'
        else:
            detail = 'The teleport destination is legal.'
        return RelocationResult(relocation_type=RelocationType.TELEPORT, movement_mode=TraversalMode.TELEPORT, destination=destination, distance_ft=distance_ft, range_ft=range_ft, movement_cost_ft=0, within_range=within_range, destination_visible=destination_visible, destination_unoccupied=destination_occupiable, destination_legal=(within_range and destination_visible and destination_legal), detail=detail)

    def can_remain_at_position(self, state: EncounterState, actor: RuntimeActorState, position: GridPosition | None = None, *, default_reason: FallReason = FallReason.STATE_CHANGE) -> bool:
        evaluation = self.evaluate_support_state(state, actor, position=position, default_reason=default_reason)
        return evaluation.supported and not evaluation.requires_fall

    def evaluate_support_state(self, state: EncounterState, actor: RuntimeActorState, position: GridPosition | None = None, *, default_reason: FallReason = FallReason.STATE_CHANGE) -> SupportStateEvaluation:
        current_position = actor.position if position is None else position
        tile = self.get_tile(state.battlefield, current_position.x, current_position.y)
        if self._is_supported_surface(state, actor, current_position):
            if self._is_liquid_surface(state, current_position):
                return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.SWIMMING, supported=True, requires_fall=False, landing_surface_type=LandingSurfaceType.LIQUID, detail='The actor is supported by a liquid surface.')
            return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.GROUNDED, supported=True, requires_fall=False, landing_surface_type=LandingSurfaceType.SOLID, detail='The actor is supported by a solid surface.')
        if self._has_climbing_support(state, actor, current_position):
            return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.CLIMBING, supported=True, requires_fall=False, landing_surface_type=LandingSurfaceType.SOLID, detail='The actor is being supported by a climbable surface.')
        if current_position.z > tile.elevation_ft:
            if actor.hover:
                return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.HOVERING, supported=True, requires_fall=False, detail='The actor is hovering and may remain aloft.')
            if self._can_actor_fly(actor):
                return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.FLYING, supported=True, requires_fall=False, detail='The actor may remain aloft with its fly speed.')
            reason = self._derive_fall_reason(actor, default_reason)
            return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.UNSUPPORTED, supported=False, requires_fall=True, reason=reason, detail='The actor is in open air without support and must fall.')
        return SupportStateEvaluation(actor_id=actor.actor_id, position=current_position, support_state=SupportStateType.UNSUPPORTED, supported=False, requires_fall=False, reason=default_reason, detail='The actor cannot remain at that position.')

    def find_landing_point(self, state: EncounterState, actor: RuntimeActorState, start_position: GridPosition) -> LandingResult:
        candidates: list[tuple[int, LandingSurfaceType, GridPosition, str]] = []
        tile = self.get_tile(state.battlefield, start_position.x, start_position.y)
        tile_position = GridPosition(start_position.x, start_position.y, tile.elevation_ft)
        if tile.elevation_ft <= start_position.z and self.is_volume_occupiable(state, OccupiedVolume(tile_position.x, tile_position.y, tile_position.z, height_ft=actor.occupied_height_ft), actor, ignore_actor_id=actor.actor_id):
            candidates.append((tile.elevation_ft, LandingSurfaceType.LIQUID if self._is_liquid_tile(tile) else LandingSurfaceType.SOLID, tile_position, 'tile-surface'))
        for feature in self._features_at(state.battlefield, start_position.x, start_position.y):
            if not feature.occupiable or feature.top_ft > start_position.z:
                continue
            landing_position = GridPosition(start_position.x, start_position.y, feature.top_ft)
            if self.is_volume_occupiable(state, OccupiedVolume(landing_position.x, landing_position.y, landing_position.z, height_ft=actor.occupied_height_ft), actor, ignore_actor_id=actor.actor_id):
                surface_type = LandingSurfaceType.LIQUID if self._feature_is_liquid(feature) else LandingSurfaceType.SOLID
                candidates.append((feature.top_ft, surface_type, landing_position, feature.feature_id))
        if not candidates:
            raise EncounterValidationError("No legal landing surface exists below the actor's current position.")
        candidates.sort(key=lambda item: item[0], reverse=True)
        top_z, surface_type, landing_position, label = candidates[0]
        return LandingResult(actor_id=actor.actor_id, start_position=start_position, landing_position=landing_position, landing_surface_type=surface_type, distance_ft=self.compute_fall_distance(start_position, landing_position), detail=f'Landing surface: {label}.')

    def compute_fall_distance(self, start_position: GridPosition, landing_position: GridPosition) -> int:
        return max(0, start_position.z - landing_position.z)

    def _derive_fall_reason(self, actor: RuntimeActorState, default_reason: FallReason) -> FallReason:
        condition_state = get_condition_state(actor)
        if actor.fly_speed_ft <= 0 and not actor.hover:
            return FallReason.FLY_SPEED_ZERO
        if ConditionType.PRONE in condition_state.effective_types and not actor.hover:
            return FallReason.PRONE_WHILE_FLYING
        if ConditionType.INCAPACITATED in condition_state.effective_types and not actor.hover:
            return FallReason.INCAPACITATED_WHILE_FLYING
        return default_reason

    def _can_actor_fly(self, actor: RuntimeActorState) -> bool:
        if actor.hover:
            return True
        condition_state = get_condition_state(actor)
        if actor.fly_speed_ft <= 0:
            return False
        if ConditionType.PRONE in condition_state.effective_types:
            return False
        if ConditionType.INCAPACITATED in condition_state.effective_types:
            return False
        return True

    def _has_climbing_support(self, state: EncounterState, actor: RuntimeActorState, position: GridPosition) -> bool:
        return False

    def _is_supported_surface(self, state: EncounterState, actor: RuntimeActorState, position: GridPosition) -> bool:
        tile = self.get_tile(state.battlefield, position.x, position.y)
        if position.z == tile.elevation_ft and tile.occupiable:
            return True
        for feature in self._features_at(state.battlefield, position.x, position.y):
            if feature.occupiable and position.z == feature.top_ft:
                return True
        return False

    def is_liquid_position(self, state: EncounterState, position: GridPosition) -> bool:
        return self._is_liquid_surface(state, position)

    def _is_liquid_surface(self, state: EncounterState, position: GridPosition) -> bool:
        tile = self.get_tile(state.battlefield, position.x, position.y)
        if position.z == tile.elevation_ft and self._is_liquid_tile(tile):
            return True
        for feature in self._features_at(state.battlefield, position.x, position.y):
            if feature.occupiable and position.z == feature.top_ft and self._feature_is_liquid(feature):
                return True
        return False

    def _is_liquid_tile(self, tile: BattlefieldTile) -> bool:
        tags = {tag.lower() for tag in tile.tags}
        return 'liquid' in tags or 'water' in tags or ('swim' in {mode.value for mode in tile.supported_modes} and 'walk' not in {mode.value for mode in tile.supported_modes})

    def _feature_is_liquid(self, feature) -> bool:
        tags = {tag.lower() for tag in feature.tags}
        return 'liquid' in tags or 'water' in tags

    def get_edge_transition(self, battlefield: BattlefieldState, a: GridPosition, b: GridPosition) -> BattlefieldEdge:
        key = edge_key(GridPosition(a.x, a.y), GridPosition(b.x, b.y))
        if key in battlefield.edges:
            return battlefield.edges[key]
        diff = self.get_height_difference(battlefield, a, b)
        rule = battlefield.default_elevation_transition_rule
        if rule is None:
            return BattlefieldEdge(cells=key, transition_type=(EdgeTransitionType.FLAT if diff == 0 else EdgeTransitionType.BLOCKED), traversal_requirement=(EdgeTraversalRequirement.NONE if diff == 0 else EdgeTraversalRequirement.BLOCKED), height_change_ft=diff, extra_movement_cost_feet=0, extra_movement_cost_with_climb_speed_feet=None, blocks_los=False, blocks_loe=False)
        if diff == 0:
            return BattlefieldEdge(cells=key, transition_type=EdgeTransitionType.FLAT, traversal_requirement=EdgeTraversalRequirement.NONE, height_change_ft=0, extra_movement_cost_feet=0, extra_movement_cost_with_climb_speed_feet=None, blocks_los=False, blocks_loe=False)
        if abs(diff) >= rule.threshold_feet:
            return BattlefieldEdge(cells=key, transition_type=rule.transition_type, traversal_requirement=rule.traversal_requirement, height_change_ft=diff, extra_movement_cost_feet=rule.extra_movement_cost_feet, extra_movement_cost_with_climb_speed_feet=rule.extra_movement_cost_with_climb_speed_feet, blocks_los=False, blocks_loe=False, cover_from_low_to_high=rule.cover_from_low_to_high, cover_from_high_to_low=rule.cover_from_high_to_low, blocks_diagonal_corner_cutting=rule.blocks_diagonal_corner_cutting)
        return BattlefieldEdge(cells=key, transition_type=EdgeTransitionType.BLOCKED, traversal_requirement=EdgeTraversalRequirement.BLOCKED, height_change_ft=diff, extra_movement_cost_feet=0, extra_movement_cost_with_climb_speed_feet=None, blocks_los=False, blocks_loe=False)

    def does_edge_require_climb(self, battlefield: BattlefieldState, a: GridPosition, b: GridPosition) -> bool:
        return self.get_edge_transition(battlefield, a, b).requires_climb

    def _features_at(self, battlefield: BattlefieldState, x: int, y: int):
        return tuple(f for f in battlefield.features.values() if any(c.x == x and c.y == y for c in f.cells))

    def is_volume_occupiable(self, state: EncounterState, volume: OccupiedVolume, actor: RuntimeActorState, *, ignore_actor_id: str | None = None) -> bool:
        try:
            tile = self.get_tile(state.battlefield, volume.x, volume.y)
        except EncounterValidationError:
            return False
        if volume.z < tile.elevation_ft or volume.top_z > tile.ceiling_ft:
            return False
        for feature in self._features_at(state.battlefield, volume.x, volume.y):
            if feature.occupiable:
                continue
            for fvol in feature.volumes():
                if volume.intersects(fvol):
                    return False
        for other in state.actors.values():
            if other.actor_id == ignore_actor_id or not other.is_conscious:
                continue
            if volume.intersects(other.occupied_volume):
                return False
        return True

    def can_traverse_edge(self, state: EncounterState, actor: RuntimeActorState, origin: GridPosition, destination: GridPosition, *, movement_intent_mode: MovementIntentMode = MovementIntentMode.ALLOW_CLIMB):
        if max(abs(destination.x - origin.x), abs(destination.y - origin.y)) != 1:
            return False, UnreachableReason.NO_TRAVERSABLE_EDGE, None
        try:
            tile = self.get_tile(state.battlefield, destination.x, destination.y)
        except EncounterValidationError:
            return False, UnreachableReason.OUTSIDE_BATTLEFIELD, None
        if not tile.traversable or not tile.occupiable:
            return False, UnreachableReason.DESTINATION_BLOCKED, None
        edge = self.get_edge_transition(state.battlefield, origin, destination)
        seg = self._ground_segment(state, actor, origin, destination, edge)
        if edge.transition_type in {EdgeTransitionType.BLOCKED, EdgeTransitionType.IMPASSABLE_FACE} or edge.traversal_requirement == EdgeTraversalRequirement.BLOCKED:
            return False, UnreachableReason.IMPASSABLE_EDGE, None
        if movement_intent_mode == MovementIntentMode.SAME_PLANE and edge.height_change_ft != 0:
            return False, UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION, seg
        if edge.traversal_requirement == EdgeTraversalRequirement.CLIMB_SPEED and actor.climb_speed_ft <= 0:
            return False, UnreachableReason.REQUIRES_CLIMB_SPEED, seg
        if edge.traversal_requirement == EdgeTraversalRequirement.CLIMB and movement_intent_mode != MovementIntentMode.ALLOW_CLIMB:
            return False, (UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION if movement_intent_mode == MovementIntentMode.SAME_PLANE else UnreachableReason.REQUIRES_CLIMB), seg
        if not self.is_volume_occupiable(state, OccupiedVolume(destination.x, destination.y, tile.elevation_ft, height_ft=actor.occupied_height_ft), actor, ignore_actor_id=actor.actor_id):
            return False, UnreachableReason.DESTINATION_OCCUPIED, seg
        return True, None, seg

    def can_move_between_cells(self, state: EncounterState, actor: RuntimeActorState, origin: GridPosition, destination: GridPosition, *, movement_intent_mode: MovementIntentMode = MovementIntentMode.ALLOW_CLIMB) -> bool:
        ok, _, _ = self.can_traverse_edge(state, actor, origin, destination, movement_intent_mode=movement_intent_mode)
        return ok

    def _ground_neighbors(self, state: EncounterState, actor: RuntimeActorState, pos: GridPosition, mode: MovementIntentMode):
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                try:
                    candidate = self.surface_position(state.battlefield, pos.x + dx, pos.y + dy)
                except EncounterValidationError:
                    continue
                if self.can_move_between_cells(state, actor, pos, candidate, movement_intent_mode=mode):
                    out.append(candidate)
        return tuple(out)

    def _fly_neighbors(self, state: EncounterState, actor: RuntimeActorState, pos: GridPosition):
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-5, 0, 5):
                    if dx == 0 and dy == 0 and dz == 0:
                        continue
                    candidate = GridPosition(pos.x + dx, pos.y + dy, pos.z + dz)
                    if candidate.z < 0:
                        continue
                    if self.is_volume_occupiable(state, OccupiedVolume(candidate.x, candidate.y, candidate.z, height_ft=actor.occupied_height_ft), actor, ignore_actor_id=actor.actor_id):
                        out.append(candidate)
        return tuple(out)

    def _neighbors(self, state: EncounterState, actor: RuntimeActorState, pos: GridPosition, *, mode: MovementIntentMode):
        return self._fly_neighbors(state, actor, pos) if mode == MovementIntentMode.ALLOW_FLY else self._ground_neighbors(state, actor, pos, mode)

    def _step_cost(self, state: EncounterState, actor: RuntimeActorState, origin: GridPosition, dest: GridPosition) -> int:
        if origin.z != self.get_tile(state.battlefield, origin.x, origin.y).elevation_ft or dest.z != self.get_tile(state.battlefield, dest.x, dest.y).elevation_ft:
            return 5
        edge = self.get_edge_transition(state.battlefield, origin, dest)
        return self._ground_segment(state, actor, origin, dest, edge).movement_cost_ft

    def _search(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, dest: GridPosition, *, mode: MovementIntentMode):
        pq = [(0, start.x, start.y, start.z)]
        prev = {start: None}
        best = {start: 0}
        while pq:
            spent, x, y, z = heapq.heappop(pq)
            cur = GridPosition(x, y, z)
            if spent > best[cur]:
                continue
            if cur == dest:
                break
            for nxt in self._neighbors(state, actor, cur, mode=mode):
                if nxt != dest and self._is_destination_occupied(state, actor.actor_id, nxt, actor.occupied_height_ft):
                    continue
                nxt_cost = spent + self._step_cost(state, actor, cur, nxt)
                if nxt_cost < best.get(nxt, 10**9):
                    best[nxt] = nxt_cost
                    prev[nxt] = cur
                    heapq.heappush(pq, (nxt_cost, nxt.x, nxt.y, nxt.z))
        if dest not in best:
            return None
        path = []
        cur = dest
        while cur != start:
            path.append(cur)
            cur = prev[cur]
            if cur is None:
                return None
        path.reverse()
        return self._plan_from_path(state, actor, start, tuple(path))

    def find_path_on_same_plane(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, destination: GridPosition):
        return self._search(state, actor, start, destination, mode=MovementIntentMode.SAME_PLANE)

    def find_best_path_with_elevation(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, destination: GridPosition, *, allow_climb: bool):
        return self._search(state, actor, start, destination, mode=(MovementIntentMode.ALLOW_CLIMB if allow_climb else MovementIntentMode.ALLOW_ELEVATION))

    def find_path3d(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, destination: GridPosition):
        return self._search(state, actor, start, destination, mode=MovementIntentMode.ALLOW_FLY)

    def preview_move(self, state: EncounterState, actor: RuntimeActorState, destination: GridPosition, *, movement_intent_mode: MovementIntentMode) -> MovementPreview:
        if actor.position == destination:
            raise EncounterValidationError('Movement requires a different destination.')
        if actor.remaining_movement_ft <= 0:
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_INSUFFICIENT_MOVEMENT, destination, destination.z, movement_intent_mode, None, False, False, actor.climb_speed_ft > 0, False, UnreachableReason.SPEED_ZERO, detail='The actor cannot move because it has no remaining movement.')
        try:
            tile = self.get_tile(state.battlefield, destination.x, destination.y)
        except EncounterValidationError:
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_BLOCKED, destination, destination.z, movement_intent_mode, None, False, False, actor.climb_speed_ft > 0, False, UnreachableReason.OUTSIDE_BATTLEFIELD, detail='The destination is outside the authored battlefield.')
        same_dest = GridPosition(destination.x, destination.y, actor.position.z)
        surface_dest = GridPosition(destination.x, destination.y, tile.elevation_ft)
        if movement_intent_mode in {MovementIntentMode.ALLOW_ELEVATION, MovementIntentMode.ALLOW_CLIMB} and destination.z == 0 and tile.elevation_ft != 0:
            destination = surface_dest
        same_plane = self.find_path_on_same_plane(state, actor, actor.position, same_dest)
        slope = self.find_best_path_with_elevation(state, actor, actor.position, surface_dest, allow_climb=False)
        climb = self.find_best_path_with_elevation(state, actor, actor.position, surface_dest, allow_climb=True)
        fly = self.find_path3d(state, actor, actor.position, destination) if actor.fly_speed_ft > 0 else None
        if movement_intent_mode == MovementIntentMode.ALLOW_FLY:
            if actor.fly_speed_ft <= 0:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_BLOCKED_AIRSPACE, destination, destination.z, movement_intent_mode, None, False, True, actor.climb_speed_ft > 0, False, UnreachableReason.REQUIRES_FLY, detail='The actor has no fly speed for that move.')
            if fly is None:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_BLOCKED_AIRSPACE, destination, destination.z, movement_intent_mode, None, False, True, actor.climb_speed_ft > 0, False, UnreachableReason.DESTINATION_BLOCKED_AIRSPACE, detail='The destination airspace is blocked or lacks clearance.')
            return self._preview_from_plan(actor, destination, movement_intent_mode, fly, MovementPreviewOutcome.REACHABLE_WITH_FLY)
        if movement_intent_mode == MovementIntentMode.SAME_PLANE:
            if same_plane is not None:
                return self._preview_from_plan(actor, same_dest, movement_intent_mode, same_plane, MovementPreviewOutcome.REACHABLE_SAME_PLANE)
            if slope is not None:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION, surface_dest, surface_dest.z, movement_intent_mode, slope.total_cost_ft, False, False, actor.climb_speed_ft > 0, True, UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION, suggested_plan=slope, blocking_segment=self._first_vertical_segment(slope), detail=f'The destination ({surface_dest.x}, {surface_dest.y}, {surface_dest.z}) requires slope or ramp traversal and costs {slope.total_cost_ft} ft. Re-run with `--allow-elevation`.')
            if climb is not None:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION, surface_dest, surface_dest.z, movement_intent_mode, climb.total_cost_ft, True, False, actor.climb_speed_ft > 0, self._plan_allows_normal_movement(climb), UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION, suggested_plan=climb, blocking_segment=self._first_vertical_segment(climb), detail=f'The destination ({surface_dest.x}, {surface_dest.y}, {surface_dest.z}) requires climbing and costs {climb.total_cost_ft} ft. Re-run with `--allow-climb` or use `/climb`.')
            if fly is not None:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION, destination, destination.z, movement_intent_mode, fly.total_cost_ft, False, True, actor.climb_speed_ft > 0, False, UnreachableReason.REQUIRES_VERTICAL_CONFIRMATION, suggested_plan=fly, blocking_segment=fly.segments[0] if fly.segments else None, detail=f'The destination ({destination.x}, {destination.y}, {destination.z}) requires flying movement and costs {fly.total_cost_ft} ft. Re-run with `--allow-fly` or use `/fly`.')
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_NO_TRAVERSABLE_EDGE, destination, destination.z, movement_intent_mode, None, False, False, actor.climb_speed_ft > 0, False, UnreachableReason.NO_TRAVERSABLE_EDGE, detail='The destination cannot be reached on the current plane.')
        if movement_intent_mode == MovementIntentMode.ALLOW_ELEVATION:
            if destination.z != surface_dest.z:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_BLOCKED_AIRSPACE, destination, destination.z, movement_intent_mode, None, False, True, actor.climb_speed_ft > 0, False, UnreachableReason.REQUIRES_FLY, detail='That altitude is not on a walkable surface. Use `/fly`.')
            if slope is not None:
                outcome = MovementPreviewOutcome.REACHABLE_WITH_SLOPE if slope.includes_elevation_change else MovementPreviewOutcome.REACHABLE_SAME_PLANE
                return self._preview_from_plan(actor, surface_dest, movement_intent_mode, slope, outcome, same_plane_plan=same_plane)
            if climb is not None:
                return MovementPreview(MovementPreviewOutcome.UNREACHABLE_REQUIRES_VERTICAL_CONFIRMATION, surface_dest, surface_dest.z, movement_intent_mode, climb.total_cost_ft, True, False, actor.climb_speed_ft > 0, self._plan_allows_normal_movement(climb), UnreachableReason.REQUIRES_CLIMB, same_plane_plan=same_plane, suggested_plan=climb, blocking_segment=self._first_vertical_segment(climb), detail=f'The destination is reachable only by climbing to {surface_dest.z} ft and costs {climb.total_cost_ft} ft. Use `/climb {actor.actor_id} {destination.x} {destination.y}` or `/move {actor.actor_id} {destination.x} {destination.y} --allow-climb`.')
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_NO_TRAVERSABLE_EDGE, surface_dest, surface_dest.z, movement_intent_mode, None, False, False, actor.climb_speed_ft > 0, False, UnreachableReason.NO_TRAVERSABLE_EDGE, detail='The destination cannot be reached by flat or sloped traversal.')
        if destination.z != surface_dest.z:
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_BLOCKED_AIRSPACE, destination, destination.z, movement_intent_mode, None, False, True, actor.climb_speed_ft > 0, False, UnreachableReason.REQUIRES_FLY, detail='That altitude is not on a walkable or climbable surface. Use `/fly`.')
        if climb is None:
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_NO_TRAVERSABLE_EDGE, surface_dest, surface_dest.z, movement_intent_mode, None, False, False, actor.climb_speed_ft > 0, False, UnreachableReason.NO_TRAVERSABLE_EDGE, detail='The destination cannot be reached from the current position.')
        outcome = MovementPreviewOutcome.REACHABLE_WITH_CLIMB if climb.requires_climb else (MovementPreviewOutcome.REACHABLE_WITH_SLOPE if climb.includes_elevation_change else MovementPreviewOutcome.REACHABLE_SAME_PLANE)
        return self._preview_from_plan(actor, surface_dest, movement_intent_mode, climb, outcome, same_plane_plan=same_plane)

    def movement_legality(self, state: EncounterState, actor: RuntimeActorState, destination: GridPosition, *, movement_intent_mode: MovementIntentMode) -> MovementLegality:
        preview = self.preview_move(state, actor, destination, movement_intent_mode=movement_intent_mode)
        if preview.outcome not in {MovementPreviewOutcome.REACHABLE_SAME_PLANE, MovementPreviewOutcome.REACHABLE_WITH_SLOPE, MovementPreviewOutcome.REACHABLE_WITH_CLIMB, MovementPreviewOutcome.REACHABLE_WITH_FLY} or preview.plan is None:
            raise EncounterValidationError(preview.detail)
        return MovementLegality(actor.position, destination, preview.plan.path, self.get_distance(actor.position, destination), preview.plan.total_cost_ft, preview, preview.plan)

    def stand_legality(self, actor: RuntimeActorState, *, effective_speed_ft: int) -> StandLegality:
        if effective_speed_ft <= 0:
            raise EncounterValidationError('The actor cannot stand because its speed is 0.')
        cost = effective_speed_ft // 2
        if cost <= 0 or actor.remaining_movement_ft < cost:
            raise EncounterValidationError('The actor does not have enough remaining movement to stand from prone.')
        return StandLegality(cost, actor.remaining_movement_ft - cost)

    def has_line_of_sight(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> bool:
        return self._has_line(state, attacker, target, for_effect=False)

    def has_line_of_effect(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> bool:
        return self._has_line(state, attacker, target, for_effect=True)

    def has_line_of_sight3d(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> bool:
        return self.has_line_of_sight(state, attacker, target)

    def has_line_of_effect3d(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> bool:
        return self.has_line_of_effect(state, attacker, target)

    def get_cover(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> CoverLevel:
        explicit = state.battlefield.cover_by_pair.get((attacker.actor_id, target.actor_id))
        if explicit is not None:
            return explicit
        if not state.battlefield.has_authored_map:
            return CoverLevel.NONE
        if not self.has_line_of_effect(state, attacker, target):
            return CoverLevel.TOTAL
        cover = self.get_tile(state.battlefield, target.position.x, target.position.y).base_cover
        for feature in self._features_on_line(state.battlefield, attacker.position, target.position):
            cover = self._max_cover(cover, feature.cover_provided)
            if feature.blocks_loe:
                return CoverLevel.TOTAL
        return self._max_cover(cover, self._elevation_cover(state.battlefield, attacker.position, target.position))

    def get_cover3d(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState) -> CoverLevel:
        return self.get_cover(state, attacker, target)

    def attack_legality(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState, attack: AttackProfile) -> AttackLegality:
        dist = self.get_distance(attacker.position, target.position)
        los = self.has_line_of_sight(state, attacker, target)
        loe = self.has_line_of_effect(state, attacker, target)
        cover = self.get_cover(state, attacker, target)
        if cover == CoverLevel.TOTAL or not loe:
            raise EncounterValidationError('The target has total cover and cannot be attacked from this position.')
        long_dis = False
        if attack.attack_kind == AttackKind.MELEE:
            if dist > (attack.reach_ft or 5):
                raise EncounterValidationError('Target is out of melee range.')
        elif attack.attack_kind == AttackKind.RANGED:
            short = attack.range_ft or 0
            long = attack.long_range_ft or short
            if dist > long:
                raise EncounterValidationError('Target is out of ranged attack distance.')
            long_dis = short > 0 and dist > short
        else:
            melee = attack.reach_ft or 5
            ranged_long = attack.long_range_ft or attack.range_ft or 0
            if dist <= melee:
                long_dis = False
            elif ranged_long > 0 and dist <= ranged_long:
                short = attack.range_ft or ranged_long
                long_dis = dist > short
            else:
                raise EncounterValidationError('Target is out of attack range.')
        return AttackLegality(dist, cover, self.cover_armor_class_bonus(cover), long_dis, los, loe)

    def detect_leaving_reach_triggers(self, observer: RuntimeActorState, *, from_position: GridPosition, path: tuple[GridPosition, ...], reach_ft: int) -> bool:
        prev = self.get_distance(observer.position, from_position)
        for step in path:
            nxt = self.get_distance(observer.position, step)
            if prev <= reach_ft and nxt > reach_ft:
                return True
            prev = nxt
        return False

    def does_movement_trigger_reaction3d(self, observer: RuntimeActorState, *, from_position: GridPosition, path: tuple[GridPosition, ...], reach_ft: int) -> bool:
        return self.detect_leaving_reach_triggers(observer, from_position=from_position, path=path, reach_ft=reach_ft)

    def leaves_reach(self, observer: RuntimeActorState, *, from_position: GridPosition, to_position: GridPosition, reach_ft: int) -> bool:
        return self.detect_leaving_reach_triggers(observer, from_position=from_position, path=(to_position,), reach_ft=reach_ft)

    def get_reachable_cells(self, state: EncounterState, actor: RuntimeActorState) -> dict[GridPosition, int]:
        return {pos: cost for pos, (cost, _) in self._search_costs(state, actor, actor.position, mode=(MovementIntentMode.ALLOW_FLY if actor.fly_speed_ft > 0 and actor.position.z > self.get_tile(state.battlefield, actor.position.x, actor.position.y).elevation_ft else MovementIntentMode.ALLOW_CLIMB), stop=None).items() if cost <= actor.remaining_movement_ft}

    def _search_costs(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, *, mode: MovementIntentMode, stop: GridPosition | None):
        pq = [(0, start.x, start.y, start.z)]
        prev = {start: None}
        best = {start: 0}
        while pq:
            spent, x, y, z = heapq.heappop(pq)
            cur = GridPosition(x, y, z)
            if spent > best[cur]:
                continue
            if stop is not None and cur == stop:
                break
            for nxt in self._neighbors(state, actor, cur, mode=mode):
                if nxt != stop and self._is_destination_occupied(state, actor.actor_id, nxt, actor.occupied_height_ft):
                    continue
                nxt_cost = spent + self._step_cost(state, actor, cur, nxt)
                if nxt_cost < best.get(nxt, 10**9):
                    best[nxt] = nxt_cost
                    prev[nxt] = cur
                    heapq.heappush(pq, (nxt_cost, nxt.x, nxt.y, nxt.z))
        return {position: (cost, prev) for position, cost in best.items()}

    def _plan_from_path(self, state: EncounterState, actor: RuntimeActorState, start: GridPosition, path: tuple[GridPosition, ...]) -> MovementPlan:
        cur = start
        segs = []
        for step in path:
            if cur.z != self.get_tile(state.battlefield, cur.x, cur.y).elevation_ft or step.z != self.get_tile(state.battlefield, step.x, step.y).elevation_ft:
                segs.append(MovementSegment(cur, step, cur.z, step.z, EdgeTransitionType.FLAT, EdgeTraversalRequirement.NONE, TraversalMode.FLY, 5, False, False))
            else:
                edge = self.get_edge_transition(state.battlefield, cur, step)
                segs.append(self._ground_segment(state, actor, cur, step, edge))
            cur = step
        return MovementPlan(path=path, segments=tuple(segs), total_cost_ft=sum(s.movement_cost_ft for s in segs), destination_elevation_ft=(path[-1].z if path else start.z), includes_elevation_change=any(s.from_position.z != s.to_position.z for s in segs), requires_climb=any(s.requires_climb for s in segs), requires_fly=any(s.traversal_mode == TraversalMode.FLY for s in segs))

    def _ground_segment(self, state: EncounterState, actor: RuntimeActorState, origin: GridPosition, dest: GridPosition, edge: BattlefieldEdge) -> MovementSegment:
        tile = self.get_tile(state.battlefield, dest.x, dest.y)
        used_climb = edge.requires_climb and actor.climb_speed_ft > 0 and edge.extra_movement_cost_with_climb_speed_feet is not None
        extra = edge.extra_movement_cost_with_climb_speed_feet if used_climb else edge.extra_movement_cost_feet
        extra = 0 if extra is None else extra
        return MovementSegment(GridPosition(origin.x, origin.y, self.get_cell_elevation(state.battlefield, origin)), GridPosition(dest.x, dest.y, tile.elevation_ft), self.get_cell_elevation(state.battlefield, origin), tile.elevation_ft, edge.transition_type, edge.traversal_requirement, (TraversalMode.CLIMB if edge.requires_climb else TraversalMode.WALK), tile.movement_cost_feet_per_5ft + extra, edge.requires_climb, used_climb)

    def _preview_from_plan(self, actor: RuntimeActorState, destination: GridPosition, movement_intent_mode: MovementIntentMode, plan: MovementPlan, outcome: MovementPreviewOutcome, *, same_plane_plan: MovementPlan | None = None):
        if plan.total_cost_ft > actor.remaining_movement_ft:
            return MovementPreview(MovementPreviewOutcome.UNREACHABLE_INSUFFICIENT_MOVEMENT, destination, plan.destination_elevation_ft, movement_intent_mode, plan.total_cost_ft, plan.requires_climb, plan.requires_fly, actor.climb_speed_ft > 0, self._plan_allows_normal_movement(plan), UnreachableReason.INSUFFICIENT_MOVEMENT, plan=plan, same_plane_plan=same_plane_plan, blocking_segment=(plan.segments[-1] if plan.segments else None), detail=f'The destination costs {plan.total_cost_ft} ft of movement, but the actor has only {actor.remaining_movement_ft} ft remaining.')
        text = 'The destination is reachable on the same plane' if outcome == MovementPreviewOutcome.REACHABLE_SAME_PLANE else ('The destination changes elevation via slope or ramp traversal' if outcome == MovementPreviewOutcome.REACHABLE_WITH_SLOPE else ('The destination is reachable by climbing' if outcome == MovementPreviewOutcome.REACHABLE_WITH_CLIMB else 'The destination is reachable in 3D airspace'))
        return MovementPreview(outcome, destination, plan.destination_elevation_ft, movement_intent_mode, plan.total_cost_ft, plan.requires_climb, plan.requires_fly, actor.climb_speed_ft > 0, self._plan_allows_normal_movement(plan), plan=plan, same_plane_plan=same_plane_plan, suggested_plan=plan, detail=f'{text} for {plan.total_cost_ft} ft of movement.')

    def _plan_allows_normal_movement(self, plan: MovementPlan) -> bool:
        return all(s.traversal_requirement != EdgeTraversalRequirement.CLIMB_SPEED and s.traversal_mode != TraversalMode.FLY for s in plan.segments)

    def _first_vertical_segment(self, plan: MovementPlan):
        for seg in plan.segments:
            if seg.from_position.z != seg.to_position.z:
                return seg
        return None

    def _has_line(self, state: EncounterState, attacker: RuntimeActorState, target: RuntimeActorState, *, for_effect: bool) -> bool:
        return self._has_line_between_positions(state, attacker.position, attacker.occupied_height_ft, target.position, for_effect=for_effect, target_height_ft=target.occupied_height_ft)

    def _has_line_between_positions(self, state: EncounterState, origin: GridPosition, origin_height_ft: int, destination: GridPosition, *, for_effect: bool, target_height_ft: int = 5) -> bool:
        if not state.battlefield.has_authored_map:
            return True
        ax, ay, az = origin.x + 0.5, origin.y + 0.5, origin.z + (origin_height_ft / 2)
        tx, ty, tz = destination.x + 0.5, destination.y + 0.5, destination.z + (target_height_ft / 2)
        steps = max(abs(destination.x - origin.x), abs(destination.y - origin.y), math.ceil(abs(destination.z - origin.z) / 5)) * 4
        if steps <= 1:
            return True
        for i in range(1, steps):
            r = i / steps
            sx, sy, sz = ax + ((tx - ax) * r), ay + ((ty - ay) * r), az + ((tz - az) * r)
            cell = GridPosition(int(math.floor(sx)), int(math.floor(sy)))
            try:
                tile = self.get_tile(state.battlefield, cell.x, cell.y)
            except EncounterValidationError:
                return False
            if tile.blocks_loe if for_effect else tile.blocks_los:
                return False
            for feature in self._features_at(state.battlefield, cell.x, cell.y):
                if feature.bottom_ft <= sz < feature.top_ft and (feature.blocks_loe if for_effect else feature.blocks_los):
                    return False
        return True

    def _features_on_line(self, battlefield: BattlefieldState, origin: GridPosition, dest: GridPosition):
        found = {}
        ox, oy, oz = origin.x + 0.5, origin.y + 0.5, origin.z + 2.5
        dx, dy, dz = dest.x + 0.5, dest.y + 0.5, dest.z + 2.5
        steps = max(abs(dest.x - origin.x), abs(dest.y - origin.y), math.ceil(abs(dest.z - origin.z) / 5)) * 4
        for i in range(1, max(steps, 1)):
            r = i / max(steps, 1)
            sx, sy, sz = ox + ((dx - ox) * r), oy + ((dy - oy) * r), oz + ((dz - oz) * r)
            for feature in self._features_at(battlefield, int(math.floor(sx)), int(math.floor(sy))):
                if feature.bottom_ft <= sz < feature.top_ft:
                    found[feature.feature_id] = feature
        return tuple(found.values())

    def _elevation_cover(self, battlefield: BattlefieldState, attacker: GridPosition, target: GridPosition) -> CoverLevel:
        rule = battlefield.default_elevation_transition_rule
        if rule is None:
            return CoverLevel.NONE
        ae, te = self.get_cell_elevation(battlefield, attacker), self.get_cell_elevation(battlefield, target)
        if abs(te - ae) < rule.threshold_feet:
            return CoverLevel.NONE
        return rule.cover_from_low_to_high if te > ae else rule.cover_from_high_to_low

    def _is_destination_occupied(self, state: EncounterState, actor_id: str, dest: GridPosition, height_ft: int) -> bool:
        volume = OccupiedVolume(dest.x, dest.y, dest.z, height_ft=height_ft)
        return any(other.actor_id != actor_id and other.is_conscious and volume.intersects(other.occupied_volume) for other in state.actors.values())

    def cover_armor_class_bonus(self, cover_level: CoverLevel) -> int:
        return 2 if cover_level == CoverLevel.HALF else (5 if cover_level == CoverLevel.THREE_QUARTERS else 0)

    def _max_cover(self, left: CoverLevel, right: CoverLevel) -> CoverLevel:
        rank = {CoverLevel.NONE: 0, CoverLevel.HALF: 1, CoverLevel.THREE_QUARTERS: 2, CoverLevel.TOTAL: 3}
        return left if rank[left] >= rank[right] else right


def _edge_rule(self, battlefield: BattlefieldState, a: GridPosition, b: GridPosition) -> BattlefieldEdge:
    return self.get_edge_transition(battlefield, a, b)


def _movement_cost_across_edge(self, state: EncounterState, actor: RuntimeActorState, origin: GridPosition, destination: GridPosition) -> int:
    ok, reason, _ = self.can_traverse_edge(state, actor, origin, destination, movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
    if not ok:
        raise EncounterValidationError(f'The actor cannot move across that battlefield edge: {reason.value}.')
    return self._step_cost(state, actor, origin, destination)


def _get_neighbors(self, state: EncounterState, position: GridPosition, actor: RuntimeActorState | None = None, *, movement_intent_mode: MovementIntentMode = MovementIntentMode.ALLOW_CLIMB):
    if actor is None:
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                try:
                    tile = self.get_tile(state.battlefield, position.x + dx, position.y + dy)
                except EncounterValidationError:
                    continue
                if tile.traversable and tile.occupiable:
                    out.append(GridPosition(position.x + dx, position.y + dy, tile.elevation_ft))
        return tuple(out)
    return self._neighbors(state, actor, position, mode=movement_intent_mode)


def _get_movement_cost(self, state: EncounterState, path: tuple[GridPosition, ...], actor: RuntimeActorState) -> int:
    total = 0
    cur = actor.position
    for step in path:
        total += self._step_cost(state, actor, cur, step)
        cur = step
    return total


BattlefieldRules.edge_rule = _edge_rule
BattlefieldRules.movement_cost_across_edge = _movement_cost_across_edge
BattlefieldRules.get_neighbors = _get_neighbors
BattlefieldRules.get_movement_cost = _get_movement_cost
