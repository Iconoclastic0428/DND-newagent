from __future__ import annotations

from shared_types.adjudication import ImprovisedTemplateDefinition, ImprovisedTemplateId
from shared_types.battlefield import BattlefieldFeature, BattlefieldState, CoverLevel
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError


_TEMPLATE_REGISTRY: dict[ImprovisedTemplateId, ImprovisedTemplateDefinition] = {
    ImprovisedTemplateId.OVERTURNED_TABLE_COVER: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.OVERTURNED_TABLE_COVER,
        feature_type='improvised-object',
        cover_provided=CoverLevel.HALF,
        traversable=False,
        occupiable=False,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=5,
        tags=('temporary', 'cover'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.FRAGILE_OBSTACLE_SMALL: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.FRAGILE_OBSTACLE_SMALL,
        feature_type='improvised-object',
        cover_provided=CoverLevel.HALF,
        traversable=False,
        occupiable=False,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=5,
        tags=('temporary', 'fragile'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.FLAMMABLE_OIL_SPILL_SMALL: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.FLAMMABLE_OIL_SPILL_SMALL,
        feature_type='terrain-effect',
        cover_provided=CoverLevel.NONE,
        traversable=True,
        occupiable=True,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=1,
        movement_cost_override_feet_per_5ft=10,
        tags=('temporary', 'difficult-terrain', 'flammable'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.UNSTABLE_RUBBLE_PATCH: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.UNSTABLE_RUBBLE_PATCH,
        feature_type='terrain-effect',
        cover_provided=CoverLevel.NONE,
        traversable=True,
        occupiable=True,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=2,
        movement_cost_override_feet_per_5ft=10,
        tags=('temporary', 'difficult-terrain', 'unstable'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.IMPROVISED_BRIDGE_OR_PLANK: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.IMPROVISED_BRIDGE_OR_PLANK,
        feature_type='terrain-effect',
        cover_provided=CoverLevel.NONE,
        traversable=True,
        occupiable=True,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=1,
        tags=('temporary', 'bridge'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.LOOSE_DEBRIS_DIFFICULT_TERRAIN: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.LOOSE_DEBRIS_DIFFICULT_TERRAIN,
        feature_type='terrain-effect',
        cover_provided=CoverLevel.NONE,
        traversable=True,
        occupiable=True,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=1,
        movement_cost_override_feet_per_5ft=10,
        tags=('temporary', 'difficult-terrain', 'debris'),
        footprint=((0, 0),),
    ),
    ImprovisedTemplateId.BALL_BEARINGS_PATCH: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.BALL_BEARINGS_PATCH,
        feature_type='terrain-effect',
        cover_provided=CoverLevel.NONE,
        traversable=True,
        occupiable=True,
        blocks_los=False,
        blocks_loe=False,
        bottom_offset_ft=0,
        top_offset_ft=1,
        tags=('temporary', 'hazard', 'ball-bearings'),
        footprint=((0, 0), (1, 0), (0, 1), (1, 1)),
    ),
    ImprovisedTemplateId.HANGING_OBJECT_DROP_HAZARD: ImprovisedTemplateDefinition(
        template_id=ImprovisedTemplateId.HANGING_OBJECT_DROP_HAZARD,
        feature_type='improvised-object',
        cover_provided=CoverLevel.NONE,
        traversable=False,
        occupiable=False,
        blocks_los=True,
        blocks_loe=True,
        bottom_offset_ft=5,
        top_offset_ft=15,
        tags=('temporary', 'hazard', 'overhead'),
        is_blocker=True,
        footprint=((0, 0),),
    ),
}


def list_template_ids() -> tuple[str, ...]:
    return tuple(template.value for template in ImprovisedTemplateId)


def get_template_definition(template_id: ImprovisedTemplateId) -> ImprovisedTemplateDefinition:
    try:
        return _TEMPLATE_REGISTRY[template_id]
    except KeyError as exc:
        raise EncounterValidationError(f'Unsupported improvised template: {template_id.value}.') from exc


def instantiate_template_feature(
    battlefield: BattlefieldState,
    *,
    feature_id: str,
    template_id: ImprovisedTemplateId,
    anchor: GridPosition,
) -> BattlefieldFeature:
    template = get_template_definition(template_id)
    base_tile = battlefield.tiles.get(GridPosition(anchor.x, anchor.y)) or battlefield.base_tiles.get(GridPosition(anchor.x, anchor.y))
    if base_tile is None:
        raise EncounterValidationError(
            f'Cannot place improvised template {template_id.value} outside the battlefield at ({anchor.x}, {anchor.y}).'
        )
    cells = tuple(
        GridPosition(anchor.x + dx, anchor.y + dy, anchor.z or base_tile.elevation_ft)
        for dx, dy in template.footprint
    )
    bottom_ft = base_tile.elevation_ft + template.bottom_offset_ft
    top_ft = base_tile.elevation_ft + template.top_offset_ft
    return BattlefieldFeature(
        feature_id=feature_id,
        feature_type=template.feature_type,
        cells=cells,
        elevation_ft=base_tile.elevation_ft,
        traversable=template.traversable,
        occupiable=template.occupiable,
        blocks_los=template.blocks_los,
        blocks_loe=template.blocks_loe,
        cover_provided=template.cover_provided,
        bottom_ft=bottom_ft,
        top_ft=top_ft,
        movement_cost_override_feet_per_5ft=template.movement_cost_override_feet_per_5ft,
        tags=template.tags,
    )


def recompute_dynamic_battlefield_state(battlefield: BattlefieldState) -> None:
    static_difficult = {
        position
        for position, tile in battlefield.base_tiles.items()
        if tile.difficult_terrain
    }
    dynamic_difficult = {
        GridPosition(cell.x, cell.y)
        for feature_id in battlefield.dynamic_feature_ids
        for cell in battlefield.features.get(feature_id, BattlefieldFeature('', '', (), 0, True, True, False, False, CoverLevel.NONE, 0, 0)).cells
        if feature_id in battlefield.features
        and (
            battlefield.features[feature_id].movement_cost_override_feet_per_5ft is not None
            or 'difficult-terrain' in {tag.lower() for tag in battlefield.features[feature_id].tags}
        )
    }
    battlefield.difficult_terrain_positions = frozenset(static_difficult.union(dynamic_difficult))
    battlefield.known_dynamic_overlays = tuple(sorted(feature_id for feature_id in battlefield.dynamic_feature_ids if feature_id in battlefield.features))
