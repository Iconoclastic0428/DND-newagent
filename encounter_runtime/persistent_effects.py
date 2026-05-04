from __future__ import annotations

import math
from typing import Iterable

from shared_types.capabilities import (
    AreaShape,
    IllusionInteractionKind,
    IllusionModality,
    IllusionRevealPolicy,
    PersistentObserverMode,
)
from shared_types.encounter_models import (
    GridPosition,
    IllusionObserverState,
    IllusionObserverStatus,
    IllusionState,
    PersistentAreaState,
    PersistentEffectState,
)

from .visibility import can_observer_see_position


def rectangular_cells(anchor: GridPosition, *, width_ft: int, depth_ft: int) -> tuple[GridPosition, ...]:
    width_cells = max(1, math.ceil(width_ft / 5))
    depth_cells = max(1, math.ceil(depth_ft / 5))
    return tuple(
        GridPosition(anchor.x + dx, anchor.y + dy, anchor.z)
        for dy in range(depth_cells)
        for dx in range(width_cells)
    )


def footprint_cells(anchor: GridPosition, footprint: tuple[tuple[int, int], ...]) -> tuple[GridPosition, ...]:
    if not footprint:
        return (anchor,)
    return tuple(GridPosition(anchor.x + dx, anchor.y + dy, anchor.z) for dx, dy in footprint)


def observer_filter_allows(
    persistent: PersistentEffectState,
    *,
    observer_id: str,
    target_actor_ids: Iterable[str] = (),
) -> bool:
    if persistent.observer_mode == PersistentObserverMode.ALL_VALID_OBSERVERS:
        return True
    if persistent.observer_mode == PersistentObserverMode.SELECTED_OBSERVERS:
        return observer_id in persistent.observer_actor_ids
    if persistent.observer_mode == PersistentObserverMode.TARGETS_ONLY:
        return observer_id in tuple(target_actor_ids)
    return False


def illusion_observer_state(illusion: IllusionState, observer_id: str) -> IllusionObserverState:
    return illusion.observer_states.get(observer_id, IllusionObserverState(observer_id=observer_id))


def illusion_projects_apparent_state(observer_state: IllusionObserverState) -> bool:
    return observer_state.status in {IllusionObserverStatus.INTENDED, IllusionObserverStatus.SUSPECTS}


def illusion_visible_to_observer(state, illusion: IllusionState, observer_id: str) -> bool:
    if not observer_filter_allows(illusion.persistent, observer_id=observer_id):
        return False
    observer = state.actors.get(observer_id)
    if observer is None:
        return False
    observer_state = illusion_observer_state(illusion, observer_id)
    if not observer_state.currently_perceivable or observer_state.status == IllusionObserverStatus.UNAWARE:
        return False
    if illusion.definition.modality in {IllusionModality.AUDITORY, IllusionModality.OBSERVER_SPECIFIC_OVERLAY}:
        return True
    return any(can_observer_see_position(state, observer, cell) for cell in illusion.cells)


def update_illusion_observer_state(
    illusion: IllusionState,
    *,
    observer_id: str,
    interaction_kind: IllusionInteractionKind,
) -> IllusionState:
    current = illusion_observer_state(illusion, observer_id)
    status = current.status
    if interaction_kind == IllusionInteractionKind.PASSIVE_NOTICE and IllusionRevealPolicy.ON_PASSIVE_NOTICE in illusion.definition.reveal_policies:
        status = IllusionObserverStatus.SUSPECTS
    if interaction_kind == IllusionInteractionKind.STUDY_SUCCESS and IllusionRevealPolicy.ON_STUDY_SUCCESS in illusion.definition.reveal_policies:
        status = IllusionObserverStatus.PIERCED
    if interaction_kind == IllusionInteractionKind.PHYSICAL_INTERACTION and (
        IllusionRevealPolicy.ON_PHYSICAL_INTERACTION in illusion.definition.reveal_policies
        or IllusionRevealPolicy.ON_ANY_INTERACTION in illusion.definition.reveal_policies
    ):
        status = IllusionObserverStatus.DISBELIEVED
    observer_states = dict(illusion.observer_states)
    observer_states[observer_id] = IllusionObserverState(
        observer_id=observer_id,
        status=status,
        currently_perceivable=current.currently_perceivable,
        render_description_override=current.render_description_override,
    )
    if illusion.definition.reveal_to_all_on_interaction and status in {IllusionObserverStatus.DISBELIEVED, IllusionObserverStatus.PIERCED}:
        for existing_observer_id, existing_state in tuple(observer_states.items()):
            observer_states[existing_observer_id] = IllusionObserverState(
                observer_id=existing_observer_id,
                status=status,
                currently_perceivable=existing_state.currently_perceivable,
                render_description_override=existing_state.render_description_override,
            )
    return IllusionState(
        persistent=illusion.persistent,
        illusion_id=illusion.illusion_id,
        definition=illusion.definition,
        cells=illusion.cells,
        observer_states=observer_states,
    )


def persistent_area_contains_position(area: PersistentAreaState, position: GridPosition) -> bool:
    origins = area.origins or (area.origin,)
    size_ft = area.definition.area_size_ft
    for origin in origins:
        if area.definition.area_shape == AreaShape.SPHERE:
            dx = (position.x - origin.x) * 5
            dy = (position.y - origin.y) * 5
            dz = position.z - origin.z
            if math.sqrt(dx * dx + dy * dy + dz * dz) <= size_ft:
                return True
            continue
        if area.definition.area_shape == AreaShape.CUBE:
            half = size_ft // 2
            if abs((position.x - origin.x) * 5) <= half and abs((position.y - origin.y) * 5) <= half and abs(position.z - origin.z) <= half:
                return True
            continue
        if area.definition.area_shape == AreaShape.LINE:
            if position.x == origin.x and 0 <= (position.y - origin.y) * 5 <= size_ft:
                return True
            continue
        if area.definition.area_shape == AreaShape.CONE:
            dx = (position.x - origin.x) * 5
            dy = (position.y - origin.y) * 5
            if dy >= 0 and dy <= size_ft and abs(dx) <= dy:
                return True
            continue
    return False
