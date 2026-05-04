from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shared_types.battlefield import (
    BattlefieldEdge,
    BattlefieldFeature,
    BattlefieldGridSpec,
    BattlefieldIntegrationHints,
    BattlefieldState,
    BattlefieldTile,
    CoverLevel,
    LightingLevel,
    ObscurementLevel,
    EdgeTransitionType,
    EdgeTraversalRequirement,
    ElevationTransitionRule,
    TraversalMode,
    edge_key,
)
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterError
from shared_types.visibility import LightLevel


DEFAULT_GOBLIN_AMBUSH_MAP_PATH = Path('data/maps/goblin_ambush_triboar_trail_map.json')


@dataclass(frozen=True)
class _TerrainType:
    terrain_id: str
    traversable: bool
    occupiable: bool
    movement_cost_feet_per_5ft: int
    difficult_terrain: bool
    lightly_obscured: bool
    lighting: LightingLevel
    obscurement: ObscurementLevel
    blocks_los: bool
    blocks_loe: bool
    base_cover: CoverLevel
    ceiling_ft: int
    supported_modes: tuple[TraversalMode, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class _FeatureAsset:
    feature_id: str
    feature_type: str
    cells: tuple[GridPosition, ...]
    elevation_ft: int
    traversable: bool
    occupiable: bool
    light_level: LightLevel
    obscurement: ObscurementLevel
    blocks_los: bool
    blocks_loe: bool
    cover_provided: CoverLevel
    bottom_ft: int
    top_ft: int
    movement_cost_override_feet_per_5ft: int | None
    rotation_deg: int | None
    tags: tuple[str, ...]


@dataclass(frozen=True)
class _EdgeOverride:
    a: GridPosition
    b: GridPosition
    transition_type: EdgeTransitionType
    traversal_requirement: EdgeTraversalRequirement
    height_change_ft: int
    extra_movement_cost_feet: int
    extra_movement_cost_with_climb_speed_feet: int | None
    blocks_los: bool
    blocks_loe: bool


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise EncounterError(message)


def _cover_level(value: str) -> CoverLevel:
    mapping = {
        'none': CoverLevel.NONE,
        'half': CoverLevel.HALF,
        'three-quarters': CoverLevel.THREE_QUARTERS,
        'three_quarters': CoverLevel.THREE_QUARTERS,
        'total': CoverLevel.TOTAL,
    }
    if value not in mapping:
        raise EncounterError(f'Unknown cover level in battlefield asset: {value!r}.')
    return mapping[value]


def _light_level(value: str | None) -> LightLevel:
    mapping = {
        None: LightLevel.BRIGHT,
        'bright': LightLevel.BRIGHT,
        'dim': LightLevel.DIM,
        'darkness': LightLevel.DARKNESS,
    }
    if value not in mapping:
        raise EncounterError(f'Unknown light level in battlefield asset: {value!r}.')
    return mapping[value]


def _lighting_level(value: str | None) -> LightingLevel:
    return LightingLevel(_light_level(value).value)


def _obscurement_level(value: str | None, *, lightly_obscured: bool = False) -> ObscurementLevel:
    mapping = {
        None: (ObscurementLevel.LIGHT if lightly_obscured else ObscurementLevel.NONE),
        'none': ObscurementLevel.NONE,
        'light': ObscurementLevel.LIGHT,
        'lightly-obscured': ObscurementLevel.LIGHT,
        'lightly_obscured': ObscurementLevel.LIGHT,
        'heavy': ObscurementLevel.HEAVY,
        'heavily-obscured': ObscurementLevel.HEAVY,
        'heavily_obscured': ObscurementLevel.HEAVY,
    }
    if value not in mapping:
        raise EncounterError(f'Unknown obscurement level in battlefield asset: {value!r}.')
    return mapping[value]


def _position(cell: list[int] | tuple[int, ...]) -> GridPosition:
    _require(len(cell) >= 2, f'Battlefield cells must have at least two coordinates, got {cell!r}.')
    z = int(cell[2]) if len(cell) >= 3 else 0
    return GridPosition(int(cell[0]), int(cell[1]), z)


def _traversal_modes(values: list[str]) -> tuple[TraversalMode, ...]:
    modes = tuple(TraversalMode(str(value)) for value in values)
    _require(bool(modes), 'Battlefield terrain types must declare at least one supported traversal mode.')
    return modes


def _terrain_type(terrain_id: str, payload: dict, *, default_ceiling_ft: int) -> _TerrainType:
    return _TerrainType(
        terrain_id=terrain_id,
        traversable=bool(payload['traversable']),
        occupiable=bool(payload['occupiable']),
        movement_cost_feet_per_5ft=int(payload['movementCostFeetPer5Ft']),
        difficult_terrain=bool(payload['difficultTerrain']),
        lightly_obscured=bool(payload['lightlyObscured']),
        lighting=_lighting_level(payload.get('lighting') or payload.get('lightLevel') or 'bright'),
        obscurement=_obscurement_level(str(payload.get('obscurement', ('light' if bool(payload['lightlyObscured']) else 'none')))),
        blocks_los=bool(payload['blocksLOS']),
        blocks_loe=bool(payload['blocksLOE']),
        base_cover=_cover_level(payload['baseCover']),
        ceiling_ft=int(payload.get('ceilingFt', default_ceiling_ft)),
        supported_modes=_traversal_modes(payload['movementModes']),
        tags=tuple(str(tag) for tag in payload.get('tags', [])),
    )


def _feature_asset(payload: dict) -> _FeatureAsset:
    return _FeatureAsset(
        feature_id=str(payload['id']),
        feature_type=str(payload['type']),
        cells=tuple(_position(cell) for cell in payload['cells']),
        elevation_ft=int(payload['elevationFt']),
        traversable=bool(payload['traversable']),
        occupiable=bool(payload.get('occupiable', False)),
        light_level=_light_level(payload.get('lightLevel') or payload.get('lighting')), 
        obscurement=_obscurement_level(payload.get('obscurement'), lightly_obscured=bool(payload.get('lightlyObscured', False))),
        blocks_los=bool(payload['blocksLOS']),
        blocks_loe=bool(payload['blocksLOE']),
        cover_provided=_cover_level(payload['coverProvided']),
        bottom_ft=int(payload['bottomFt']),
        top_ft=int(payload['topFt']),
        movement_cost_override_feet_per_5ft=(None if payload.get('movementCostOverrideFeetPer5Ft') is None else int(payload['movementCostOverrideFeetPer5Ft'])),
        rotation_deg=(None if payload.get('rotationDeg') is None else int(payload['rotationDeg'])),
        tags=tuple(str(tag) for tag in payload.get('tags', [])),
    )


def _edge_override(payload: dict) -> _EdgeOverride:
    return _EdgeOverride(
        a=_position(payload['a']),
        b=_position(payload['b']),
        transition_type=EdgeTransitionType(str(payload['transitionType'])),
        traversal_requirement=EdgeTraversalRequirement(str(payload['traversalRequirement'])),
        height_change_ft=int(payload['heightChangeFt']),
        extra_movement_cost_feet=int(payload['extraMovementCostFeet']),
        extra_movement_cost_with_climb_speed_feet=(None if payload.get('extraMovementCostFeetWithClimbSpeed') is None else int(payload['extraMovementCostFeetWithClimbSpeed'])),
        blocks_los=bool(payload['blocksLOS']),
        blocks_loe=bool(payload['blocksLOE']),
    )


def _max_cover(left: CoverLevel, right: CoverLevel) -> CoverLevel:
    ranking = {
        CoverLevel.NONE: 0,
        CoverLevel.HALF: 1,
        CoverLevel.THREE_QUARTERS: 2,
        CoverLevel.TOTAL: 3,
    }
    return left if ranking[left] >= ranking[right] else right


def load_battlefield_state_from_json(path: str | Path = DEFAULT_GOBLIN_AMBUSH_MAP_PATH) -> BattlefieldState:
    asset_path = Path(path)
    try:
        payload = json.loads(asset_path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError as exc:
        raise EncounterError(f'Battlefield asset was not found: {asset_path}') from exc
    except json.JSONDecodeError as exc:
        raise EncounterError(f'Battlefield asset contains invalid JSON: {asset_path}: {exc}') from exc

    _require(payload.get('schemaVersion') == '2.0.0', 'Unsupported battlefield asset schema version.')
    grid_payload = payload['grid']
    bounds = grid_payload['playableBounds']
    grid = BattlefieldGridSpec(
        cell_size_feet=int(grid_payload['cellSizeFeet']),
        width=int(grid_payload['width']),
        height=int(grid_payload['height']),
        origin=str(grid_payload['origin']),
        coordinates=str(grid_payload['coordinates']),
        min_x=int(bounds['minX']),
        min_y=int(bounds['minY']),
        max_x=int(bounds['maxX']),
        max_y=int(bounds['maxY']),
    )

    defaults = payload['defaults']
    default_ceiling_ft = int(defaults['airspaceTopFt'])
    terrain_types = {terrain_id: _terrain_type(terrain_id, terrain_payload, default_ceiling_ft=default_ceiling_ft) for terrain_id, terrain_payload in payload['terrainTypes'].items()}
    default_terrain_id = str(defaults['terrain'])
    _require(default_terrain_id in terrain_types, f'Unknown default terrain type: {default_terrain_id!r}.')
    default_terrain = terrain_types[default_terrain_id]
    default_elevation_ft = int(defaults['elevationFt'])

    tiles: dict[GridPosition, BattlefieldTile] = {}
    for y in range(grid.min_y, grid.max_y + 1):
        for x in range(grid.min_x, grid.max_x + 1):
            position = GridPosition(x, y)
            tiles[position] = BattlefieldTile(
                position=position,
                terrain_id=default_terrain.terrain_id,
                elevation_ft=default_elevation_ft,
                ceiling_ft=default_terrain.ceiling_ft,
                traversable=default_terrain.traversable,
                occupiable=default_terrain.occupiable,
                movement_cost_feet_per_5ft=default_terrain.movement_cost_feet_per_5ft,
                difficult_terrain=default_terrain.difficult_terrain,
                lightly_obscured=default_terrain.lightly_obscured,
                lighting=default_terrain.lighting,
                obscurement=default_terrain.obscurement,
                blocks_los=default_terrain.blocks_los,
                blocks_loe=default_terrain.blocks_loe,
                base_cover=default_terrain.base_cover,
                supported_modes=default_terrain.supported_modes,
                tags=default_terrain.tags,
            )

    region_ids: list[str] = []
    for region in payload.get('terrainRegions', []):
        region_ids.append(str(region['id']))
        terrain_id = str(region['terrain'])
        _require(terrain_id in terrain_types, f'Unknown terrain region type: {terrain_id!r}.')
        terrain = terrain_types[terrain_id]
        elevation_ft = int(region['elevationFt'])
        for cell in region['cells']:
            position = _position(cell).horizontal()
            _require(position in tiles, f'Terrain region references out-of-bounds cell {position}.')
            tiles[position] = BattlefieldTile(
                position=position,
                terrain_id=terrain.terrain_id,
                elevation_ft=elevation_ft,
                ceiling_ft=terrain.ceiling_ft,
                traversable=terrain.traversable,
                occupiable=terrain.occupiable,
                movement_cost_feet_per_5ft=terrain.movement_cost_feet_per_5ft,
                difficult_terrain=terrain.difficult_terrain,
                lightly_obscured=terrain.lightly_obscured,
                lighting=terrain.lighting,
                obscurement=terrain.obscurement,
                blocks_los=terrain.blocks_los,
                blocks_loe=terrain.blocks_loe,
                base_cover=terrain.base_cover,
                supported_modes=terrain.supported_modes,
                tags=terrain.tags,
            )

    features: dict[str, BattlefieldFeature] = {}
    object_ids: list[str] = []
    blocker_ids: list[str] = []
    for feature_payload in payload.get('objects', []):
        feature = _feature_asset(feature_payload)
        object_ids.append(feature.feature_id)
        features[feature.feature_id] = BattlefieldFeature(
            feature_id=feature.feature_id,
            feature_type=feature.feature_type,
            cells=tuple(cell.horizontal() for cell in feature.cells),
            elevation_ft=feature.elevation_ft,
            traversable=feature.traversable,
            occupiable=feature.occupiable,
            light_level=feature.light_level,
            obscurement=feature.obscurement,
            blocks_los=feature.blocks_los,
            blocks_loe=feature.blocks_loe,
            cover_provided=feature.cover_provided,
            bottom_ft=feature.bottom_ft,
            top_ft=feature.top_ft,
            movement_cost_override_feet_per_5ft=feature.movement_cost_override_feet_per_5ft,
            rotation_deg=feature.rotation_deg,
            tags=feature.tags,
        )
    for feature_payload in payload.get('blockers', []):
        feature = _feature_asset(feature_payload)
        blocker_ids.append(feature.feature_id)
        features[feature.feature_id] = BattlefieldFeature(
            feature_id=feature.feature_id,
            feature_type=feature.feature_type,
            cells=tuple(cell.horizontal() for cell in feature.cells),
            elevation_ft=feature.elevation_ft,
            traversable=feature.traversable,
            occupiable=feature.occupiable,
            light_level=feature.light_level,
            obscurement=feature.obscurement,
            blocks_los=feature.blocks_los,
            blocks_loe=feature.blocks_loe,
            cover_provided=feature.cover_provided,
            bottom_ft=feature.bottom_ft,
            top_ft=feature.top_ft,
            movement_cost_override_feet_per_5ft=feature.movement_cost_override_feet_per_5ft,
            rotation_deg=feature.rotation_deg,
            tags=feature.tags,
        )

    for feature in features.values():
        for position in feature.cells:
            _require(position in tiles, f'Battlefield feature {feature.feature_id!r} references out-of-bounds cell {position}.')
            base_tile = tiles[position]
            movement_cost = feature.movement_cost_override_feet_per_5ft or base_tile.movement_cost_feet_per_5ft
            blocks_surface = feature.bottom_ft <= base_tile.elevation_ft < feature.top_ft
            tiles[position] = BattlefieldTile(
                position=position,
                terrain_id=base_tile.terrain_id,
                elevation_ft=base_tile.elevation_ft,
                ceiling_ft=base_tile.ceiling_ft,
                traversable=base_tile.traversable and (feature.traversable or not blocks_surface),
                occupiable=base_tile.occupiable and (feature.occupiable or not blocks_surface),
                movement_cost_feet_per_5ft=movement_cost,
                difficult_terrain=base_tile.difficult_terrain or movement_cost > grid.cell_size_feet,
                lightly_obscured=(base_tile.lightly_obscured or feature.obscurement == ObscurementLevel.LIGHT),
                lighting=(base_tile.lighting if base_tile.light_level.value == 'darkness' else LightingLevel(feature.light_level.value)),
                obscurement=(feature.obscurement if feature.obscurement != ObscurementLevel.NONE else base_tile.obscurement),
                blocks_los=base_tile.blocks_los,
                blocks_loe=base_tile.blocks_loe,
                base_cover=_max_cover(base_tile.base_cover, feature.cover_provided),
                supported_modes=base_tile.supported_modes,
                object_ids=base_tile.object_ids + ((feature.feature_id,) if feature.feature_id in object_ids else ()),
                blocker_ids=base_tile.blocker_ids + ((feature.feature_id,) if feature.feature_id in blocker_ids else ()),
                tags=tuple(dict.fromkeys((*base_tile.tags, *feature.tags))),
            )

    spatial_rules = payload['spatialRules']
    default_edge_rule_payload = spatial_rules['defaultElevationTransitionRule']
    default_edge_rule = ElevationTransitionRule(
        threshold_feet=int(default_edge_rule_payload['thresholdFeet']),
        transition_type=EdgeTransitionType(str(default_edge_rule_payload['transitionType'])),
        traversal_requirement=EdgeTraversalRequirement(str(default_edge_rule_payload['traversalRequirement'])),
        effect=str(default_edge_rule_payload['effect']),
        movement=str(default_edge_rule_payload['movement']),
        extra_movement_cost_feet=int(default_edge_rule_payload['extraMovementCostFeet']),
        extra_movement_cost_with_climb_speed_feet=(None if default_edge_rule_payload.get('extraMovementCostFeetWithClimbSpeed') is None else int(default_edge_rule_payload['extraMovementCostFeetWithClimbSpeed'])),
        blocks_diagonal_corner_cutting=bool(default_edge_rule_payload['blocksDiagonalCornerCutting']),
        cover_from_low_to_high=_cover_level(default_edge_rule_payload['coverFromLowToHigh']),
        cover_from_high_to_low=_cover_level(default_edge_rule_payload['coverFromHighToLow']),
    )

    edges: dict[tuple[GridPosition, GridPosition], BattlefieldEdge] = {}
    for override_payload in payload.get('edgeOverrides', []):
        override = _edge_override(override_payload)
        key = edge_key(override.a.horizontal(), override.b.horizontal())
        edges[key] = BattlefieldEdge(
            cells=key,
            transition_type=override.transition_type,
            traversal_requirement=override.traversal_requirement,
            height_change_ft=override.height_change_ft,
            extra_movement_cost_feet=override.extra_movement_cost_feet,
            extra_movement_cost_with_climb_speed_feet=override.extra_movement_cost_with_climb_speed_feet,
            blocks_los=override.blocks_los,
            blocks_loe=override.blocks_loe,
        )

    spawn_zones = {
        str(zone_id): tuple(_position(cell) for cell in zone_payload['cells'])
        for zone_id, zone_payload in payload.get('spawnZones', {}).items()
    }
    integration_payload = payload['integrationHints']
    integration_hints = BattlefieldIntegrationHints(
        battlefield_state_key=str(integration_payload['battlefieldStateKey']),
        recommended_queries=tuple(str(query) for query in integration_payload.get('recommendedQueries', [])),
        public_sync_fields=tuple(str(field_name) for field_name in integration_payload.get('publicSyncFields', [])),
    )
    difficult_positions = frozenset(position for position, tile in tiles.items() if tile.difficult_terrain)
    return BattlefieldState(
        map_id=str(payload['mapId']),
        name=str(payload['name']),
        grid=grid,
        tiles=tiles,
        base_tiles=dict(tiles),
        features=features,
        edges=edges,
        spawn_zones=spawn_zones,
        integration_hints=integration_hints,
        default_elevation_transition_rule=default_edge_rule,
        terrain_region_ids=tuple(region_ids),
        object_ids=tuple(object_ids),
        blocker_ids=tuple(blocker_ids),
        known_dynamic_overlays=('actor_positions',),
        dynamic_feature_ids=(),
        difficult_terrain_positions=difficult_positions,
        default_airspace_top_ft=default_ceiling_ft,
    )
