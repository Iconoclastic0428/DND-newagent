from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Iterable

from encounter_runtime.visibility import position_light_level, position_obscurement
from rules_engine.encounter_math import horizontal_distance_ft
from shared_types.battlefield import BattlefieldState, edge_key
from shared_types.conditions import ConditionType
from shared_types.encounter_models import EncounterState, GridPosition, RuntimeActorState
from shared_types.errors import EncounterValidationError
from shared_types.visibility import LightLevel, ObscurementLevel

from .conditions import get_condition_state
from .persistent_effects import persistent_area_contains_position


_ACTOR_GRID_VISION_CACHE: dict[tuple[object, ...], tuple[tuple[object, ...], 'GridVisionResult']] = {}
_WARMED_ACTOR_GRID_VISION_RESULTS: dict[tuple[object, ...], 'GridVisionResult'] = {}
_MAX_ACTOR_GRID_VISION_CACHE_ENTRIES = 128
_ACTOR_VISION_CONTEXT_CACHE: dict[tuple[object, ...], tuple[tuple[object, ...], 'ActorVisionContext']] = {}
_CoordKey = tuple[int, int]
_CoordEdgeKey = tuple[_CoordKey, _CoordKey]
_LINE_TRACE_CACHE: dict[tuple[int, int, int, int], tuple[tuple[tuple[_CoordEdgeKey, ...], _CoordKey | None], ...]] = {}


@dataclass(frozen=True)
class GridVisionResult:
    origin: GridPosition
    time_of_day: str
    radius_ft: int
    visible_cells: frozenset[GridPosition]
    normal_vision_cells: frozenset[GridPosition] = field(default_factory=frozenset)
    night_vision_cells: frozenset[GridPosition] = field(default_factory=frozenset)


@dataclass(frozen=True)
class ActorVisionContext:
    tile_positions: tuple[GridPosition, ...]
    line_blocking_cells: frozenset[tuple[int, int]]
    heavy_obscurement_cells: frozenset[tuple[int, int]]
    light_by_cell: dict[tuple[int, int], LightLevel]
    los_blocking_edges: frozenset[_CoordEdgeKey]


def normalize_time_of_day(time_of_day: str | None) -> str:
    normalized = (time_of_day or 'day').strip().lower()
    if normalized not in {'day', 'night'}:
        raise EncounterValidationError(f'Unknown vision time of day: {time_of_day!r}.')
    return normalized


def vision_radius_ft(
    battlefield: BattlefieldState,
    *,
    time_of_day: str | None = None,
    day_radius_ft: int | None = None,
    night_radius_ft: int | None = None,
    darkvision_radius_ft: int = 0,
) -> int:
    normalized = normalize_time_of_day(time_of_day or battlefield.vision_time_of_day)
    if normalized == 'day':
        radius = battlefield.vision_day_radius_ft if day_radius_ft is None else int(day_radius_ft)
    else:
        radius = battlefield.vision_night_radius_ft if night_radius_ft is None else int(night_radius_ft)
        radius = max(radius, int(darkvision_radius_ft))
    if radius <= 0:
        raise EncounterValidationError('Vision radius must be positive.')
    return radius


def compute_grid_vision(
    battlefield: BattlefieldState,
    *,
    origin: GridPosition,
    time_of_day: str | None = None,
    day_radius_ft: int | None = None,
    night_radius_ft: int | None = None,
    darkvision_radius_ft: int = 0,
) -> GridVisionResult:
    if battlefield.grid is None or not battlefield.tiles:
        return GridVisionResult(
            origin=origin.horizontal(),
            time_of_day=normalize_time_of_day(time_of_day or battlefield.vision_time_of_day),
            radius_ft=0,
            visible_cells=frozenset(),
        )
    normalized = normalize_time_of_day(time_of_day or battlefield.vision_time_of_day)
    radius = vision_radius_ft(
        battlefield,
        time_of_day=normalized,
        day_radius_ft=day_radius_ft,
        night_radius_ft=night_radius_ft,
        darkvision_radius_ft=darkvision_radius_ft,
    )
    origin_xy = origin.horizontal()
    if origin_xy not in battlefield.tiles:
        raise EncounterValidationError(f'Vision origin ({origin.x}, {origin.y}) is outside the authored battlefield.')

    visible: set[GridPosition] = set()
    for position in battlefield.tiles:
        if horizontal_distance_ft(origin_xy, position) > radius:
            continue
        if _line_blocked_by_wall(battlefield, origin_xy, position):
            continue
        visible.add(position.horizontal())
    return GridVisionResult(
        origin=origin_xy,
        time_of_day=normalized,
        radius_ft=radius,
        visible_cells=frozenset(visible),
        normal_vision_cells=frozenset(visible),
    )


def compute_actor_grid_vision(
    state: EncounterState,
    actor: RuntimeActorState,
    *,
    time_of_day: str | None = None,
) -> GridVisionResult:
    battlefield = state.battlefield
    normalized = normalize_time_of_day(time_of_day or battlefield.vision_time_of_day)
    if battlefield.grid is None or not battlefield.tiles:
        return GridVisionResult(
            origin=actor.position.horizontal(),
            time_of_day=normalized,
            radius_ft=0,
            visible_cells=frozenset(),
        )
    origin_xy = actor.position.horizontal()
    if origin_xy not in battlefield.tiles:
        raise EncounterValidationError(f'Vision origin ({actor.position.x}, {actor.position.y}) is outside the authored battlefield.')

    ambient_radius = vision_radius_ft(battlefield, time_of_day=normalized)
    radius = max(ambient_radius, actor.darkvision_radius_ft, actor.blindsight_radius_ft, actor.truesight_radius_ft)
    lookup_key = _actor_grid_vision_lookup_key(state, actor, normalized, radius)
    warmed_result = _WARMED_ACTOR_GRID_VISION_RESULTS.pop(lookup_key, None)
    if warmed_result is not None:
        return warmed_result
    cache_key, cache_signature = _actor_grid_vision_cache_parts(state, actor, normalized, radius, lookup_key=lookup_key)
    cached = _ACTOR_GRID_VISION_CACHE.get(cache_key)
    if cached is not None:
        cached_signature, cached_result = cached
        if cached_signature == cache_signature:
            return cached_result

    observer_state = get_condition_state(actor)
    if ConditionType.BLINDED in observer_state.effective_types and actor.blindsight_radius_ft <= 0 and actor.truesight_radius_ft <= 0:
        result = GridVisionResult(
            origin=origin_xy,
            time_of_day=normalized,
            radius_ft=radius,
            visible_cells=frozenset({origin_xy}),
            normal_vision_cells=frozenset({origin_xy}),
        )
        _store_actor_grid_vision_cache(cache_key, cache_signature, result)
        return result

    context = _actor_vision_context(state)
    origin_cell_key = (origin_xy.x, origin_xy.y)
    if origin_cell_key in context.line_blocking_cells:
        result = GridVisionResult(
            origin=origin_xy,
            time_of_day=normalized,
            radius_ft=radius,
            visible_cells=frozenset({origin_xy}),
            normal_vision_cells=frozenset({origin_xy}),
        )
        _store_actor_grid_vision_cache(cache_key, cache_signature, result)
        return result
    normal_cells: set[GridPosition] = {origin_xy}
    night_cells: set[GridPosition] = set()
    actor_has_darkvision = actor.darkvision_radius_ft > 0
    for position in context.tile_positions:
        if horizontal_distance_ft(origin_xy, position) > radius:
            continue
        if position.horizontal() == origin_xy:
            continue
        cell_key = (position.x, position.y)
        if _line_blocked_by_context(origin_xy, position, context):
            continue
        if cell_key in context.heavy_obscurement_cells:
            continue
        light_level = context.light_by_cell.get(cell_key, LightLevel.BRIGHT)
        if light_level == LightLevel.DARKNESS:
            if actor_has_darkvision and horizontal_distance_ft(origin_xy, position.horizontal()) <= actor.darkvision_radius_ft:
                night_cells.add(position.horizontal())
            continue
        if actor.blindsight_radius_ft > 0 and horizontal_distance_ft(origin_xy, position.horizontal()) <= actor.blindsight_radius_ft:
            normal_cells.add(position.horizontal())
            continue
        if actor.truesight_radius_ft > 0 and horizontal_distance_ft(origin_xy, position.horizontal()) <= actor.truesight_radius_ft:
            normal_cells.add(position.horizontal())
            continue
        normal_cells.add(position.horizontal())
    visible = normal_cells.union(night_cells)
    result = GridVisionResult(
        origin=origin_xy,
        time_of_day=normalized,
        radius_ft=radius,
        visible_cells=frozenset(visible),
        normal_vision_cells=frozenset(normal_cells),
        night_vision_cells=frozenset(night_cells),
    )
    _store_actor_grid_vision_cache(cache_key, cache_signature, result)
    return result


def compute_grid_vision_for_actors(
    state: EncounterState,
    observer_actor_ids: Iterable[str],
    *,
    time_of_day: str | None = None,
) -> tuple[GridVisionResult, ...]:
    results: list[GridVisionResult] = []
    for actor_id in dict.fromkeys(observer_actor_ids):
        actor = state.actors.get(actor_id)
        if actor is None or not actor.is_conscious:
            continue
        results.append(compute_actor_grid_vision(state, actor, time_of_day=time_of_day))
    return tuple(results)


def warm_actor_grid_vision_traces(
    state: EncounterState,
    actor: RuntimeActorState,
    *,
    time_of_day: str | None = None,
) -> None:
    battlefield = state.battlefield
    normalized = normalize_time_of_day(time_of_day or battlefield.vision_time_of_day)
    if battlefield.grid is None or not battlefield.tiles:
        return
    origin_xy = actor.position.horizontal()
    if origin_xy not in battlefield.tiles:
        return
    ambient_radius = vision_radius_ft(battlefield, time_of_day=normalized)
    radius = max(ambient_radius, actor.darkvision_radius_ft, actor.blindsight_radius_ft, actor.truesight_radius_ft)
    context = _actor_vision_context(state)
    for position in context.tile_positions:
        if horizontal_distance_ft(origin_xy, position) <= radius:
            _line_trace(origin_xy, position)
    result = compute_actor_grid_vision(state, actor, time_of_day=normalized)
    lookup_key = _actor_grid_vision_lookup_key(state, actor, normalized, radius)
    if lookup_key not in _WARMED_ACTOR_GRID_VISION_RESULTS and len(_WARMED_ACTOR_GRID_VISION_RESULTS) >= _MAX_ACTOR_GRID_VISION_CACHE_ENTRIES:
        _WARMED_ACTOR_GRID_VISION_RESULTS.clear()
    _WARMED_ACTOR_GRID_VISION_RESULTS[lookup_key] = result


def visible_cells_for_actors(
    state: EncounterState,
    observer_actor_ids: Iterable[str],
    *,
    time_of_day: str | None = None,
) -> frozenset[GridPosition]:
    visible: set[GridPosition] = set()
    for result in compute_grid_vision_for_actors(state, observer_actor_ids, time_of_day=time_of_day):
        visible.update(result.visible_cells)
    return frozenset(visible)


def awareness_cells_for_actors(
    state: EncounterState,
    observer_actor_ids: Iterable[str],
    *,
    time_of_day: str | None = None,
) -> frozenset[GridPosition]:
    aware: set[GridPosition] = set()
    for actor_id in dict.fromkeys(observer_actor_ids):
        actor = state.actors.get(actor_id)
        if actor is None or not actor.is_conscious:
            continue
        result = compute_grid_vision(
            state.battlefield,
            origin=actor.position,
            time_of_day=time_of_day,
            darkvision_radius_ft=actor.darkvision_radius_ft,
        )
        aware.update(result.visible_cells)
    return frozenset(aware)


def vision_modes_for_actors(
    state: EncounterState,
    observer_actor_ids: Iterable[str],
    *,
    time_of_day: str | None = None,
) -> dict[GridPosition, str]:
    modes: dict[GridPosition, str] = {}
    for result in compute_grid_vision_for_actors(state, observer_actor_ids, time_of_day=time_of_day):
        for position in result.night_vision_cells:
            modes.setdefault(position, 'night')
        for position in result.normal_vision_cells:
            modes[position] = 'normal'
    return modes


def _line_blocked_by_wall(battlefield: BattlefieldState, origin: GridPosition, target: GridPosition) -> bool:
    if origin.x == target.x and origin.y == target.y:
        return False
    steps = max(abs(target.x - origin.x), abs(target.y - origin.y)) * 4
    if steps <= 1:
        return False
    ox, oy = origin.x + 0.5, origin.y + 0.5
    tx, ty = target.x + 0.5, target.y + 0.5
    previous = origin
    for index in range(1, steps):
        ratio = index / steps
        sx = ox + ((tx - ox) * ratio)
        sy = oy + ((ty - oy) * ratio)
        sampled = GridPosition(int(math.floor(sx)), int(math.floor(sy)))
        if _edge_blocks_los_between_cells(battlefield, previous, sampled):
            return True
        previous = sampled
        if sampled == origin or sampled == target:
            continue
        if _cell_blocks_los(battlefield, sampled):
            return True
    return False


def _actor_grid_vision_cache_parts(
    state: EncounterState,
    actor: RuntimeActorState,
    time_of_day: str,
    radius_ft: int,
    *,
    lookup_key: tuple[object, ...] | None = None,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    battlefield = state.battlefield
    if lookup_key is None:
        lookup_key = _actor_grid_vision_lookup_key(state, actor, time_of_day, radius_ft)
    cache_signature = (
        _battlefield_tiles_vision_signature(battlefield),
        _battlefield_features_vision_signature(battlefield),
        _battlefield_edges_vision_signature(battlefield),
        _active_effects_vision_signature(state),
        _persistent_areas_vision_signature(state),
    )
    return lookup_key, cache_signature


def _actor_grid_vision_lookup_key(
    state: EncounterState,
    actor: RuntimeActorState,
    time_of_day: str,
    radius_ft: int,
) -> tuple[object, ...]:
    battlefield = state.battlefield
    return (
        id(state),
        id(battlefield),
        actor.actor_id,
        _actor_visibility_signature(actor),
        time_of_day,
        radius_ft,
        len(state.event_log),
        len(state.active_effects),
        len(state.persistent_areas),
        len(battlefield.tiles),
        len(battlefield.features),
        len(battlefield.edges),
    )


def _actor_vision_context(state: EncounterState) -> ActorVisionContext:
    battlefield = state.battlefield
    lookup_key = (
        id(state),
        id(battlefield),
        len(battlefield.tiles),
        len(battlefield.features),
        len(battlefield.edges),
        len(state.active_effects),
        len(state.persistent_areas),
    )
    signature = (
        _battlefield_tiles_vision_signature(battlefield),
        _battlefield_features_vision_signature(battlefield),
        _battlefield_edges_vision_signature(battlefield),
        _active_effects_vision_signature(state),
        _persistent_areas_vision_signature(state),
    )
    cached = _ACTOR_VISION_CONTEXT_CACHE.get(lookup_key)
    if cached is not None:
        cached_signature, context = cached
        if cached_signature == signature:
            return context

    tile_positions: list[GridPosition] = []
    line_blocking_cells: set[tuple[int, int]] = set()
    heavy_obscurement_cells: set[tuple[int, int]] = set()
    light_by_cell: dict[tuple[int, int], LightLevel] = {}
    for tile in battlefield.tiles.values():
        cell_key = (tile.position.x, tile.position.y)
        tile_positions.append(GridPosition(tile.position.x, tile.position.y, tile.elevation_ft))
        light_by_cell[cell_key] = tile.lighting
        if tile.blocks_los:
            line_blocking_cells.add(cell_key)
        if tile.obscurement == ObscurementLevel.HEAVY:
            heavy_obscurement_cells.add(cell_key)

    for feature in battlefield.features.values():
        for cell in feature.cells:
            cell_key = (cell.x, cell.y)
            if feature.blocks_los:
                line_blocking_cells.add(cell_key)
            if feature.obscurement == ObscurementLevel.HEAVY:
                heavy_obscurement_cells.add(cell_key)
            _apply_light_level(light_by_cell, cell_key, feature.light_level)

    for effect in state.active_effects.values():
        if effect.definition.bright_light_radius_ft <= 0 and effect.definition.dim_light_radius_ft <= 0:
            continue
        for anchor in _active_effect_light_anchors(state, effect):
            _apply_light_radius(
                tile_positions,
                light_by_cell,
                anchor=anchor,
                bright_radius_ft=effect.definition.bright_light_radius_ft,
                dim_radius_ft=effect.definition.dim_light_radius_ft,
            )

    for area in state.persistent_areas.values():
        for position in tile_positions:
            if not persistent_area_contains_position(area, position):
                continue
            cell_key = (position.x, position.y)
            if area.definition.blocks_vision:
                line_blocking_cells.add(cell_key)
            level = area.definition.obscurement_level
            if area.definition.blocks_vision and level is None:
                level = ObscurementLevel.HEAVY
            if level == ObscurementLevel.HEAVY:
                heavy_obscurement_cells.add(cell_key)
        _apply_light_radius(
            tile_positions,
            light_by_cell,
            anchor=area.origin,
            bright_radius_ft=area.definition.bright_light_radius_ft,
            dim_radius_ft=area.definition.dim_light_radius_ft,
        )

    context = ActorVisionContext(
        tile_positions=tuple(tile_positions),
        line_blocking_cells=frozenset(line_blocking_cells),
        heavy_obscurement_cells=frozenset(heavy_obscurement_cells),
        light_by_cell=light_by_cell,
        los_blocking_edges=frozenset(_coord_edge_key((key[0].x, key[0].y), (key[1].x, key[1].y)) for key, edge in battlefield.edges.items() if edge.blocks_los),
    )
    if lookup_key not in _ACTOR_VISION_CONTEXT_CACHE and len(_ACTOR_VISION_CONTEXT_CACHE) >= _MAX_ACTOR_GRID_VISION_CACHE_ENTRIES:
        _ACTOR_VISION_CONTEXT_CACHE.clear()
    _ACTOR_VISION_CONTEXT_CACHE[lookup_key] = (signature, context)
    return context


def _light_priority(level: LightLevel) -> int:
    return {
        LightLevel.DARKNESS: 0,
        LightLevel.DIM: 1,
        LightLevel.BRIGHT: 2,
    }[level]


def _apply_light_level(light_by_cell: dict[tuple[int, int], LightLevel], cell_key: tuple[int, int], level: LightLevel) -> None:
    current = light_by_cell.get(cell_key)
    if current is None or _light_priority(level) > _light_priority(current):
        light_by_cell[cell_key] = level


def _active_effect_light_anchors(state: EncounterState, effect) -> tuple[GridPosition, ...]:
    anchors: list[GridPosition] = []
    if effect.target_actor_ids:
        anchors.extend(state.actors[target_id].position for target_id in effect.target_actor_ids if target_id in state.actors)
    elif effect.origin_point is not None:
        anchors.append(effect.origin_point)
    else:
        source = state.actors.get(effect.source_actor_id)
        if source is not None:
            anchors.append(source.position)
    return tuple(anchors)


def _apply_light_radius(
    tile_positions: Iterable[GridPosition],
    light_by_cell: dict[tuple[int, int], LightLevel],
    *,
    anchor: GridPosition,
    bright_radius_ft: int,
    dim_radius_ft: int,
) -> None:
    if bright_radius_ft <= 0 and dim_radius_ft <= 0:
        return
    for position in tile_positions:
        distance_ft = horizontal_distance_ft(anchor.horizontal(), position.horizontal())
        cell_key = (position.x, position.y)
        if bright_radius_ft > 0 and distance_ft <= bright_radius_ft:
            _apply_light_level(light_by_cell, cell_key, LightLevel.BRIGHT)
            continue
        if dim_radius_ft > 0 and distance_ft <= dim_radius_ft:
            _apply_light_level(light_by_cell, cell_key, LightLevel.DIM)


def _line_blocked_by_context(origin: GridPosition, target: GridPosition, context: ActorVisionContext) -> bool:
    for edge_keys, cell_key in _line_trace(origin, target):
        for edge_key_value in edge_keys:
            if edge_key_value in context.los_blocking_edges:
                return True
        if cell_key is not None and cell_key in context.line_blocking_cells:
            return True
    return False


def _line_trace(origin: GridPosition, target: GridPosition) -> tuple[tuple[tuple[_CoordEdgeKey, ...], _CoordKey | None], ...]:
    cache_key = (origin.x, origin.y, target.x, target.y)
    cached = _LINE_TRACE_CACHE.get(cache_key)
    if cached is not None:
        return cached
    origin_key = (origin.x, origin.y)
    target_key = (target.x, target.y)
    if origin_key == target_key:
        trace: tuple[tuple[tuple[_CoordEdgeKey, ...], _CoordKey | None], ...] = ()
        _LINE_TRACE_CACHE[cache_key] = trace
        return trace
    steps = max(abs(target.x - origin.x), abs(target.y - origin.y)) * 4
    if steps <= 1:
        trace = ()
        _LINE_TRACE_CACHE[cache_key] = trace
        return trace
    ox, oy = origin.x + 0.5, origin.y + 0.5
    tx, ty = target.x + 0.5, target.y + 0.5
    previous = origin_key
    entries: list[tuple[tuple[_CoordEdgeKey, ...], _CoordKey | None]] = []
    for index in range(1, steps):
        ratio = index / steps
        sx = ox + ((tx - ox) * ratio)
        sy = oy + ((ty - oy) * ratio)
        sampled = (int(math.floor(sx)), int(math.floor(sy)))
        cell_key = None if sampled == origin_key or sampled == target_key else sampled
        entries.append((_coord_edge_keys_between_cells(previous, sampled), cell_key))
        previous = sampled
    trace = tuple(entries)
    if len(_LINE_TRACE_CACHE) >= 4096:
        _LINE_TRACE_CACHE.clear()
    _LINE_TRACE_CACHE[cache_key] = trace
    return trace


def _coord_edge_key(a: _CoordKey, b: _CoordKey) -> _CoordEdgeKey:
    return (a, b) if a <= b else (b, a)


def _coord_edge_keys_between_cells(origin: _CoordKey, target: _CoordKey) -> tuple[_CoordEdgeKey, ...]:
    if origin == target:
        return ()
    ox, oy = origin
    tx, ty = target
    pairs: list[tuple[_CoordKey, _CoordKey]] = [(origin, target)]
    if ox != tx and oy != ty:
        via_x = (tx, oy)
        via_y = (ox, ty)
        pairs.extend(
            (
                (origin, via_x),
                (via_x, target),
                (origin, via_y),
                (via_y, target),
            )
        )
    return tuple(_coord_edge_key(a, b) for a, b in pairs)


def _edge_keys_between_cells(origin: GridPosition, target: GridPosition) -> tuple[tuple[GridPosition, GridPosition], ...]:
    if origin.x == target.x and origin.y == target.y:
        return ()
    pairs = [(origin.horizontal(), target.horizontal())]
    if origin.x != target.x and origin.y != target.y:
        via_x = GridPosition(target.x, origin.y)
        via_y = GridPosition(origin.x, target.y)
        pairs.extend(
            (
                (origin.horizontal(), via_x),
                (via_x, target.horizontal()),
                (origin.horizontal(), via_y),
                (via_y, target.horizontal()),
            )
        )
    return tuple(edge_key(a, b) for a, b in pairs)


def _store_actor_grid_vision_cache(
    lookup_key: tuple[object, ...],
    signature: tuple[object, ...],
    result: GridVisionResult,
) -> None:
    if lookup_key not in _ACTOR_GRID_VISION_CACHE and len(_ACTOR_GRID_VISION_CACHE) >= _MAX_ACTOR_GRID_VISION_CACHE_ENTRIES:
        _ACTOR_GRID_VISION_CACHE.clear()
    _ACTOR_GRID_VISION_CACHE[lookup_key] = (signature, result)


def _actor_visibility_signature(actor: RuntimeActorState) -> tuple[object, ...]:
    return (
        _position_signature(actor.position),
        actor.current_hit_points,
        actor.occupied_height_ft,
        actor.darkvision_radius_ft,
        actor.blindsight_radius_ft,
        actor.truesight_radius_ft,
        actor.can_see_invisible,
        tuple(
            (
                condition.instance_id,
                condition.condition_type.value,
                condition.source_actor_id,
                condition.source_effect_id,
                condition.suppressed,
            )
            for condition in actor.condition_instances
        ),
    )


def _battlefield_tiles_vision_signature(battlefield: BattlefieldState) -> tuple[object, ...]:
    return tuple(
        (
            position.x,
            position.y,
            tile.elevation_ft,
            tile.lighting.value,
            tile.obscurement.value,
            tile.blocks_los,
            tile.blocks_loe,
        )
        for position, tile in battlefield.tiles.items()
    )


def _battlefield_features_vision_signature(battlefield: BattlefieldState) -> tuple[object, ...]:
    return tuple(
        (
            feature_id,
            feature.blocks_los,
            feature.blocks_loe,
            feature.light_level.value,
            feature.obscurement.value,
            feature.bottom_ft,
            feature.top_ft,
            tuple(_position_signature(cell) for cell in feature.cells),
        )
        for feature_id, feature in battlefield.features.items()
    )


def _battlefield_edges_vision_signature(battlefield: BattlefieldState) -> tuple[object, ...]:
    return tuple(
        (
            _position_signature(a),
            _position_signature(b),
            edge.blocks_los,
            edge.blocks_loe,
        )
        for (a, b), edge in battlefield.edges.items()
    )


def _active_effects_vision_signature(state: EncounterState) -> tuple[object, ...]:
    return tuple(
        (
            effect_id,
            effect.name,
            effect.source_actor_id,
            effect.target_actor_ids,
            _position_signature(effect.origin_point) if effect.origin_point is not None else None,
            effect.definition.bright_light_radius_ft,
            effect.definition.dim_light_radius_ft,
            _active_effect_anchor_signature(state, effect),
        )
        for effect_id, effect in state.active_effects.items()
    )


def _active_effect_anchor_signature(state: EncounterState, effect) -> tuple[object, ...]:
    if effect.target_actor_ids:
        return tuple(
            (actor_id, _position_signature(state.actors[actor_id].position))
            for actor_id in effect.target_actor_ids
            if actor_id in state.actors
        )
    if effect.origin_point is not None:
        return (('origin', _position_signature(effect.origin_point)),)
    source = state.actors.get(effect.source_actor_id)
    if source is None:
        return ()
    return ((effect.source_actor_id, _position_signature(source.position)),)


def _persistent_areas_vision_signature(state: EncounterState) -> tuple[object, ...]:
    return tuple(
        (
            area_id,
            _position_signature(area.origin),
            tuple(_position_signature(origin) for origin in area.origins),
            area.definition.area_shape.value,
            area.definition.area_size_ft,
            area.definition.blocks_vision,
            area.definition.obscurement_level.value if area.definition.obscurement_level is not None else None,
            area.definition.bright_light_radius_ft,
            area.definition.dim_light_radius_ft,
            area.definition.relative_origins,
        )
        for area_id, area in state.persistent_areas.items()
    )


def _position_signature(position: GridPosition) -> tuple[int, int, int]:
    return (position.x, position.y, position.z)


def _edge_blocks_los_between_cells(battlefield: BattlefieldState, origin: GridPosition, target: GridPosition) -> bool:
    if origin.x == target.x and origin.y == target.y:
        return False
    pairs = [(origin.horizontal(), target.horizontal())]
    if origin.x != target.x and origin.y != target.y:
        via_x = GridPosition(target.x, origin.y)
        via_y = GridPosition(origin.x, target.y)
        pairs.extend(
            (
                (origin.horizontal(), via_x),
                (via_x, target.horizontal()),
                (origin.horizontal(), via_y),
                (via_y, target.horizontal()),
            )
        )
    for a, b in pairs:
        edge = battlefield.edges.get(edge_key(a, b))
        if edge is not None and edge.blocks_los:
            return True
    return False


def _cell_blocks_los(battlefield: BattlefieldState, position: GridPosition) -> bool:
    tile = battlefield.tiles.get(position.horizontal())
    if tile is None:
        return True
    if tile.blocks_los:
        return True
    for feature in battlefield.features.values():
        if not feature.blocks_los:
            continue
        if any(cell.x == position.x and cell.y == position.y for cell in feature.cells):
            return True
    return False


def _blocking_cell_vision_mode(state: EncounterState, actor: RuntimeActorState, position: GridPosition) -> str | None:
    if position_obscurement(state, position) == ObscurementLevel.HEAVY:
        return None
    light_level = position_light_level(state, position)
    if light_level == LightLevel.DARKNESS:
        return 'night' if horizontal_distance_ft(actor.position.horizontal(), position.horizontal()) <= actor.darkvision_radius_ft else None
    return 'normal'
