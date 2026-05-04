from __future__ import annotations

from dataclasses import asdict

from encounter_runtime.control import EncounterControlRuntime
from encounter_runtime.visibility import controller_visibility_state
from shared_types.battlefield import BattlefieldTile
from shared_types.encounter_models import ActorSide, EncounterState, GridPosition
from shared_types.models import ChoiceView
from shared_types.session_projection import (
    ControllerEncounterProjection,
    EncounterActorPositionProjection,
    EncounterActorPrivateProjection,
    EncounterActorProjection,
    EncounterActorPublicProjection,
    EncounterChoiceGroupProjection,
    EncounterChoiceProjection,
    SemanticBattlefieldProjection,
    SemanticMapCellProjection,
)
from shared_types.visibility import ObserverVisibilityState
from shared_types.encounter_models import DyingStateStatus


def projection_to_payload(projection: ControllerEncounterProjection | None) -> dict | None:
    if projection is None:
        return None
    return asdict(projection)


def build_controller_encounter_projection(
    *,
    state: EncounterState,
    control_runtime: EncounterControlRuntime,
    controller_id: str,
    available_choices: dict[str, tuple[ChoiceView, ...]],
    recent_events: tuple[str, ...],
) -> ControllerEncounterProjection:
    binding = control_runtime.validate_controller(controller_id)
    prompt = control_runtime.build_prompt(state)
    waiting_on_labels = tuple(recipient.label for recipient in prompt.recipients) if prompt is not None else ()
    battlefield = _battlefield_projection(state)
    actor_order = state.initiative_order or tuple(state.actors)
    projected_actors = [
        _actor_projection(
            state=state,
            control_runtime=control_runtime,
            controller_id=controller_id,
            actor_id=actor_id,
            dm_view=(binding.role.value == 'dm'),
        )
        for actor_id in actor_order
    ]
    actors = tuple(actor for actor in projected_actors if actor is not None)
    choice_groups = tuple(
        EncounterChoiceGroupProjection(
            group_id=group_id,
            options=tuple(EncounterChoiceProjection(option_id=choice.option_id, label=choice.label, detail=choice.detail) for choice in choices),
        )
        for group_id, choices in available_choices.items()
    )
    return ControllerEncounterProjection(
        controller_id=controller_id,
        role=binding.role.value,
        phase=state.phase.value,
        round_number=state.round_number or 0,
        active_actor_id=state.active_actor_id,
        initiative_order=tuple(state.initiative_order),
        battlefield=battlefield,
        actors=actors,
        recent_events=recent_events,
        waiting_on_labels=waiting_on_labels,
        choice_groups=choice_groups,
    )


def _battlefield_projection(state: EncounterState) -> SemanticBattlefieldProjection | None:
    battlefield = state.battlefield
    if not battlefield.has_authored_map or battlefield.grid is None:
        return None
    ordered_tiles = sorted(battlefield.tiles.values(), key=lambda tile: (tile.position.y, tile.position.x))
    cells = tuple(_cell_projection(tile) for tile in ordered_tiles)
    return SemanticBattlefieldProjection(
        map_id=battlefield.map_id,
        name=battlefield.name,
        width=battlefield.grid.width,
        height=battlefield.grid.height,
        cell_size_feet=battlefield.grid.cell_size_feet,
        spawn_zones=tuple(sorted(battlefield.spawn_zones)),
        object_ids=tuple(battlefield.object_ids),
        blocker_ids=tuple(battlefield.blocker_ids),
        cells=cells,
    )


def _cell_projection(tile: BattlefieldTile) -> SemanticMapCellProjection:
    return SemanticMapCellProjection(
        x=tile.position.x,
        y=tile.position.y,
        terrain_id=tile.terrain_id,
        elevation_ft=tile.elevation_ft,
        ceiling_ft=tile.ceiling_ft,
        traversable=tile.traversable,
        occupiable=tile.occupiable,
        movement_cost_feet_per_5ft=tile.movement_cost_feet_per_5ft,
        difficult_terrain=tile.difficult_terrain,
        lightly_obscured=tile.lightly_obscured,
        lighting=tile.lighting.value,
        obscurement=tile.obscurement.value,
        blocks_los=tile.blocks_los,
        blocks_loe=tile.blocks_loe,
        base_cover=tile.base_cover.value,
        supported_modes=tuple(mode.value for mode in tile.supported_modes),
        object_ids=tuple(tile.object_ids),
        blocker_ids=tuple(tile.blocker_ids),
        tags=tuple(tile.tags),
    )


def _actor_public_status(actor) -> str:
    if actor.dying_state.status == DyingStateStatus.DEAD:
        return 'dead'
    if actor.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
        return 'stable'
    if actor.current_hit_points == 0 or actor.dying_state.status == DyingStateStatus.AT_0_HP_UNCONSCIOUS:
        return 'unconscious'
    return 'active'


def _actor_projection(
    *,
    state: EncounterState,
    control_runtime: EncounterControlRuntime,
    controller_id: str,
    actor_id: str,
    dm_view: bool,
) -> EncounterActorProjection | None:
    actor = state.actors[actor_id]
    owner_controller_id = control_runtime.controller_for_actor(actor_id)
    owns_actor = owner_controller_id == controller_id
    sees_private = owns_actor or (dm_view and actor.side == ActorSide.MONSTER)
    visibility_state = ObserverVisibilityState.VISIBLE
    if not dm_view and not owns_actor:
        observer_actor_ids = tuple(
            owned_actor_id
            for owned_actor_id in (state.initiative_order or tuple(state.actors))
            if control_runtime.controller_for_actor(owned_actor_id) == controller_id
        )
        visibility_state = controller_visibility_state(state, observer_actor_ids, actor)
        if visibility_state == ObserverVisibilityState.HIDDEN:
            return None
    tile = state.battlefield.tiles.get(GridPosition(actor.position.x, actor.position.y)) if state.battlefield.has_authored_map else None
    public = EncounterActorPublicProjection(
        actor_id=actor.actor_id,
        name=(actor.name if visibility_state == ObserverVisibilityState.VISIBLE or owns_actor or dm_view else 'Unseen contact'),
        side=(actor.side.value if visibility_state == ObserverVisibilityState.VISIBLE or owns_actor or dm_view else 'unknown'),
        status=_actor_public_status(actor),
        position=EncounterActorPositionProjection(x=actor.position.x, y=actor.position.y, z=actor.position.z),
        tile_terrain_id=(tile.terrain_id if tile is not None else None),
        tile_elevation_ft=(tile.elevation_ft if tile is not None else None),
        turn_active=(actor.actor_id == state.active_actor_id),
        visibility_state=visibility_state.value,
        support_state=actor.support_state.value,
    )
    private_state = None
    if sees_private:
        private_state = EncounterActorPrivateProjection(
            current_hit_points=actor.current_hit_points,
            max_hit_points=actor.max_hit_points,
            temp_hit_points=actor.temp_hit_points,
            effective_armor_class=actor.effective_armor_class,
            remaining_movement_ft=actor.remaining_movement_ft,
            action_available=actor.action_available,
            bonus_action_available=actor.bonus_action_available,
            reaction_available=actor.reaction_available,
            condition_types=tuple(instance.condition_type.value for instance in actor.condition_instances),
            dying_status=(None if actor.dying_state.status == DyingStateStatus.ALIVE else actor.dying_state.status.value),
            death_save_successes=(actor.dying_state.death_save_successes if actor.uses_death_saves else None),
            death_save_failures=(actor.dying_state.death_save_failures if actor.uses_death_saves else None),
            stable_recovery_hours_remaining=actor.dying_state.stable_recovery_hours_remaining,
        )
    return EncounterActorProjection(public=public, private_state=private_state)
