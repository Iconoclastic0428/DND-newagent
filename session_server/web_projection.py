from __future__ import annotations

from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any

from shared_types.battlefield import CoverLevel, MovementIntentMode
from shared_types.encounter_control import ControllerRole
from shared_types.encounter_events import (
    StoryActionDeclaredEvent,
    StoryCheckResolvedEvent,
    HostileEscalationTriggeredEvent,
    ReinforcementScheduledEvent,
    ReinforcementEnteredEvent,
    CombatStartedFromStorySceneEvent,
    StoryModeSpellcastIgnoredEvent,
    StoryModeSpellcastDeclaredEvent,
    StoryModeSpellcastCausedSuspicionEvent,
    StoryTranscriptAppendedEvent,
)
from shared_types.encounter_models import ActorSide, DyingStateStatus, GridPosition
from shared_types.errors import EncounterPermissionError, EncounterValidationError
from shared_types.models import ABILITY_ORDER, Ability, ItemRecord, ProficiencyCategory, slugify
from shared_types.visibility import ObserverVisibilityState
from shared_types.storytelling import RuntimeMode, StoryTranscriptVisibility
from shared_types.travel import HexCoord
from shared_types.web_session import (
    WebActorProjection,
    WebBattlefieldProjection,
    WebChoiceProjection,
    WebControllerIdentity,
    WebEncounterProjection,
    WebPromptProjection,
    WebSessionProjection,
    WebStoryCheckResultProjection,
    WebStoryProjection,
    WebTileProjection,
    WebTranscriptEntryProjection,
)
from shared_types.web_ui import (
    WebActionChoiceView,
    WebActionGroupView,
    WebCellInspectionView,
    WebCellTraversalView,
    WebCharacterAbilityView,
    WebCharacterAttackView,
    WebCharacterCardView,
    WebCharacterEffectView,
    WebCharacterItemView,
    WebCharacterResourceView,
    WebCharacterSkillView,
    WebCharacterSpeedView,
    WebCharacterSpellView,
    WebChatEntryView,
    WebCoordinate,
    WebHexCoordinate,
    WebMapCellView,
    WebMapFeatureView,
    WebMapGridView,
    WebMapView,
    WebPathPreviewView,
    WebTravelHexInspectionView,
    WebTravelHexView,
    WebTravelHookView,
    WebTravelLandmarkView,
    WebTravelMapView,
    WebTravelRoutePreviewView,
    WebTravelRouteView,
    WebPromptOptionView,
    WebPromptView,
    WebSessionView,
    WebTeleportLegalityView,
    WebTokenView,
)

from .encounter_session import _recent_event_lines
from encounter_runtime.equipment import derived_stowed_counts
from encounter_runtime.visibility import controller_can_see_position, controller_visibility_state
from encounter_runtime.persistent_effects import illusion_observer_state, illusion_projects_apparent_state, illusion_visible_to_observer, persistent_area_contains_position


def to_jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: to_jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [to_jsonable(item) for item in value]
    return value


def project_story_session_view(session, controller_id: str, *, session_id: str) -> WebSessionView:
    binding = session.encounter_session.control_runtime.validate_controller(controller_id)
    view = session.view_for_controller(controller_id)
    prompt = session.prompt_for_controller(controller_id)
    encounter_phase = session.state.phase if session.story_state.runtime_mode == RuntimeMode.COMBAT else None
    round_number = session.state.round_number if session.story_state.runtime_mode == RuntimeMode.COMBAT else None
    active_actor_id = session.state.active_actor_id if session.story_state.runtime_mode == RuntimeMode.COMBAT else None
    initiative_order = session.state.initiative_order if session.story_state.runtime_mode == RuntimeMode.COMBAT else ()
    return WebSessionView(
        session_id=session_id,
        controller_id=controller_id,
        controller_label=binding.label,
        role=binding.role,
        runtime_mode=session.story_state.runtime_mode.value,
        encounter_phase=encounter_phase,
        current_scene_id=session.story_state.current_scene_id,
        current_location_id=session.story_state.canonical_location_id,
        round_number=round_number,
        active_actor_id=active_actor_id,
        initiative_order=initiative_order,
        owned_actor_ids=_owned_actor_ids(session, controller_id),
        party_goals=tuple(session.story_state.current_party_goals),
        open_loops=tuple(session.story_state.open_loops),
        summary_lines=tuple(view.summary_lines),
        action_groups=_project_action_groups(view.available_choices),
        prompt=_project_ui_prompt(prompt),
        map=(_project_map(session, controller_id) if session.story_state.runtime_mode == RuntimeMode.COMBAT else None),
        travel=_project_travel_map(session, controller_id, binding.role),
        chat_entries=_project_story_chat_entries(session, controller_id),
        character_cards=_project_character_cards(session, controller_id, binding.role),
    )



def project_encounter_session_view(session, controller_id: str, *, session_id: str) -> WebSessionView:
    binding = session.control_runtime.validate_controller(controller_id)
    view = session.view_for_controller(controller_id)
    prompt = session.prompt_for_controller(controller_id)
    return WebSessionView(
        session_id=session_id,
        controller_id=controller_id,
        controller_label=binding.label,
        role=binding.role,
        runtime_mode='combat',
        encounter_phase=session.state.phase,
        current_scene_id=None,
        current_location_id=None,
        round_number=session.state.round_number,
        active_actor_id=session.state.active_actor_id,
        initiative_order=session.state.initiative_order,
        owned_actor_ids=_owned_actor_ids(session, controller_id),
        party_goals=(),
        open_loops=(),
        summary_lines=tuple(view.summary_lines),
        action_groups=_project_action_groups(view.available_choices),
        prompt=_project_ui_prompt(prompt),
        map=_project_map(session, controller_id),
        travel=None,
        chat_entries=_project_encounter_chat_entries(session, controller_id),
        character_cards=_project_character_cards(session, controller_id, binding.role),
    )




def project_manual_demo_wrapper_view(session, controller_id: str, *, session_id: str) -> WebSessionView:
    binding = session.validate_controller(controller_id)
    view = session.view_for_controller(controller_id)
    return WebSessionView(
        session_id=session_id,
        controller_id=controller_id,
        controller_label=binding.label,
        role=binding.role,
        runtime_mode=_manual_demo_runtime_mode(session),
        encounter_phase=None,
        current_scene_id=None,
        current_location_id=None,
        round_number=None,
        active_actor_id=None,
        initiative_order=(),
        owned_actor_ids=(),
        party_goals=(),
        open_loops=(),
        summary_lines=tuple(view.summary_lines),
        action_groups=_manual_demo_action_groups(session, view.available_choices),
        prompt=None,
        map=None,
        travel=None,
        chat_entries=(),
        character_cards=(),
    )
def inspect_cell(session, controller_id: str, *, x: int, y: int, z: int | None = None) -> WebCellInspectionView:
    rules = _kernel_for_session(session).battlefield_rules
    battlefield = session.state.battlefield
    binding = _control_runtime(session).validate_controller(controller_id)
    tile = rules.get_tile(battlefield, x, y)
    target_z = tile.elevation_ft if z is None else z
    position = GridPosition(x, y, target_z)
    if not _controller_can_inspect_position(session, controller_id, position):
        raise EncounterPermissionError('That cell is not currently visible to this controller.')
    actor = _preview_actor(session, controller_id)
    traversal_views: list[WebCellTraversalView] = []
    if actor is not None:
        for mode_label, mode in (
            ('walk', MovementIntentMode.SAME_PLANE),
            ('elevation', MovementIntentMode.ALLOW_ELEVATION),
            ('climb', MovementIntentMode.ALLOW_CLIMB),
            ('fly', MovementIntentMode.ALLOW_FLY),
        ):
            try:
                preview = rules.preview_move(session.state, actor, position, movement_intent_mode=mode)
                traversal_views.append(
                    WebCellTraversalView(
                        mode_id=mode_label,
                        outcome=preview.outcome.value,
                        detail=preview.detail,
                        total_cost_ft=preview.total_cost_ft,
                        target_elevation_ft=preview.target_elevation_ft,
                        requires_climb=preview.requires_climb,
                        requires_fly=preview.requires_fly,
                    )
                )
            except EncounterValidationError as exc:
                traversal_views.append(
                    WebCellTraversalView(
                        mode_id=mode_label,
                        outcome='invalid',
                        detail=str(exc),
                        total_cost_ft=None,
                        target_elevation_ft=target_z,
                        requires_climb=False,
                        requires_fly=False,
                    )
                )
    persistent_features, apparent_overlays = _persistent_feature_projection(session, controller_id, binding.role)
    feature_ids = tuple(
        feature.feature_id
        for feature in battlefield.features.values()
        if any(cell.x == x and cell.y == y for cell in feature.cells)
    )
    persistent_feature_summaries = tuple(
        filter(
            None,
            (
                f"{feature.display_name or feature.feature_id}: {feature.display_description}" if feature.display_description else (feature.display_name or feature.feature_id)
                for feature in persistent_features
                if any(cell.x == x and cell.y == y for cell in feature.cells)
            ),
        )
    )
    overlay = apparent_overlays.get((x, y, target_z), {'blocked': False, 'cover': None, 'tags': ()})
    edge_summaries = _edge_summaries(session, position)
    return WebCellInspectionView(
        position=WebCoordinate(x=x, y=y, z=target_z),
        terrain_id=tile.terrain_id,
        elevation_ft=tile.elevation_ft,
        ceiling_ft=tile.ceiling_ft,
        traversable=tile.traversable,
        occupiable=tile.occupiable,
        movement_cost_feet_per_5ft=tile.movement_cost_feet_per_5ft,
        difficult_terrain=tile.difficult_terrain,
        lighting=tile.lighting.value,
        obscurement=tile.obscurement.value,
        blocks_los=tile.blocks_los,
        blocks_loe=tile.blocks_loe,
        base_cover=tile.base_cover.value,
        supported_modes=tuple(mode.value for mode in tile.supported_modes),
        object_ids=tile.object_ids + _ground_item_ids_at(session, x=x, y=y),
        blocker_ids=tile.blocker_ids,
        tags=tile.tags,
        feature_ids=feature_ids,
        edge_summaries=edge_summaries,
        traversal_views=tuple(traversal_views),
        teleport_views=(),
        apparent_blocked=bool(overlay['blocked']) if binding.role != ControllerRole.DM else False,
        apparent_cover=(overlay['cover'] if binding.role != ControllerRole.DM else None),
        apparent_tags=(tuple(overlay['tags']) if binding.role != ControllerRole.DM else ()),
        feature_summaries=persistent_feature_summaries,
    )

def preview_path(session, controller_id: str, *, x: int, y: int, z: int | None = None, mode: str = 'walk') -> WebPathPreviewView:
    actor = _combat_active_owned_actor(session, controller_id)
    if actor is None:
        raise EncounterPermissionError('Path preview requires the controller to own the active combat actor.')
    rules = _kernel_for_session(session).battlefield_rules
    tile = rules.get_tile(session.state.battlefield, x, y)
    target_z = tile.elevation_ft if z is None else z
    destination = GridPosition(x, y, target_z)
    if not _controller_can_inspect_position(session, controller_id, destination):
        raise EncounterPermissionError('That destination is not currently visible to this controller.')
    preview = rules.preview_move(session.state, actor, destination, movement_intent_mode=_movement_intent_mode(mode))
    plan = preview.plan or preview.suggested_plan
    path = tuple(_coord(point) for point in (plan.path if plan is not None else ()))
    return WebPathPreviewView(
        actor_id=actor.actor_id,
        destination=WebCoordinate(x=x, y=y, z=target_z),
        outcome=preview.outcome.value,
        detail=preview.detail,
        total_cost_ft=preview.total_cost_ft,
        target_elevation_ft=preview.target_elevation_ft,
        requires_climb=preview.requires_climb,
        requires_fly=preview.requires_fly,
        path=path,
    )





def inspect_travel_hex(session, controller_id: str, *, q: int, r: int) -> WebTravelHexInspectionView:
    if not hasattr(session, 'travel_inspect_hex'):
        raise EncounterPermissionError('This session does not expose a travel hex map.')
    inspection = session.travel_inspect_hex(controller_id, q=q, r=r)
    return WebTravelHexInspectionView(
        coord=_hex_coord(inspection.coord),
        terrain_id=inspection.terrain.value,
        travel_cost_units=inspection.travel_cost_units,
        route_kind=inspection.route_kind,
        discovered=inspection.discovered,
        traversable=inspection.traversable,
        location_id=inspection.location_id,
        landmark_ids=inspection.landmark_ids,
        tags=inspection.tags,
        reachable_by_known_route=inspection.reachable_by_known_route,
    )



def preview_travel_route(session, controller_id: str, *, q: int | None = None, r: int | None = None, destination_location_id: str | None = None) -> WebTravelRoutePreviewView:
    if not hasattr(session, 'travel_preview_route'):
        raise EncounterPermissionError('This session does not expose travel route previews.')
    preview = session.travel_preview_route(controller_id, q=q, r=r, destination_location_id=destination_location_id)
    return WebTravelRoutePreviewView(
        destination=_hex_coord(preview.destination),
        destination_label=preview.destination_label,
        path=tuple(_hex_coord(coord) for coord in preview.path),
        estimated_cost_units=preview.estimated_cost_units,
        estimated_minutes=preview.estimated_minutes,
    )


def project_encounter_session_projection(session, controller_id: str, *, session_id: str) -> WebSessionProjection:
    binding = session.control_runtime.validate_controller(controller_id)
    view = session.view_for_controller(controller_id)
    prompt = session.prompt_for_controller(controller_id)
    projection = view.projection
    encounter = None
    if projection is not None:
        battlefield = None
        if projection.battlefield is not None:
            battlefield = WebBattlefieldProjection(
                map_id=projection.battlefield.map_id,
                name=projection.battlefield.name,
                width=projection.battlefield.width,
                height=projection.battlefield.height,
                cell_size_feet=projection.battlefield.cell_size_feet,
                object_count=len(projection.battlefield.object_ids),
                blocker_count=len(projection.battlefield.blocker_ids),
                spawn_zone_ids=projection.battlefield.spawn_zones,
            )
        encounter = WebEncounterProjection(
            phase=projection.phase,
            round_number=projection.round_number,
            active_actor_id=projection.active_actor_id,
            initiative_order=projection.initiative_order,
            actors=tuple(
                WebActorProjection(
                    actor_id=actor.public.actor_id,
                    name=actor.public.name,
                    side=actor.public.side,
                    x=actor.public.position.x,
                    y=actor.public.position.y,
                    z=actor.public.position.z,
                    status=actor.public.status,
                    turn_active=actor.public.turn_active,
                    private_visible=(actor.private_state is not None),
                    tile=(
                        WebTileProjection(
                            terrain_id=actor.public.tile_terrain_id,
                            elevation_ft=actor.public.tile_elevation_ft,
                        )
                        if actor.public.tile_terrain_id is not None and actor.public.tile_elevation_ft is not None
                        else None
                    ),
                    current_hit_points=(actor.private_state.current_hit_points if actor.private_state is not None else None),
                    max_hit_points=(actor.private_state.max_hit_points if actor.private_state is not None else None),
                    temp_hit_points=(actor.private_state.temp_hit_points if actor.private_state is not None else None),
                    armor_class=(actor.private_state.effective_armor_class if actor.private_state is not None else None),
                    remaining_movement_ft=(actor.private_state.remaining_movement_ft if actor.private_state is not None else None),
                    action_available=(actor.private_state.action_available if actor.private_state is not None else None),
                    bonus_action_available=(actor.private_state.bonus_action_available if actor.private_state is not None else None),
                    reaction_available=(actor.private_state.reaction_available if actor.private_state is not None else None),
                )
                for actor in projection.actors
            ),
            recent_event_lines=projection.recent_events,
            battlefield=battlefield,
        )
    return WebSessionProjection(
        session_kind='encounter',
        state_version=len(session.state.event_log),
        controller=WebControllerIdentity(controller_id=controller_id, role=binding.role, label=binding.label),
        summary_lines=tuple(view.summary_lines),
        available_choices={
            group_id: tuple(WebChoiceProjection(option_id=choice.option_id, label=choice.label, detail=choice.detail) for choice in choices)
            for group_id, choices in view.available_choices.items()
        },
        prompt=_project_session_prompt(prompt),
        encounter=encounter,
    )



def project_story_session_projection(session, controller_id: str, *, session_id: str) -> WebSessionProjection:
    binding = session.encounter_session.control_runtime.validate_controller(controller_id)
    view = session.view_for_controller(controller_id)
    prompt = session.prompt_for_controller(controller_id)
    pending = session.story_state.pending_check
    waiting_label = None
    pending_actor_id = None
    pending_check_text = None
    if pending is not None:
        pending_check_text = pending.prompt
        pending_actor_id = pending.actor_id
        if pending.controller_id is not None:
            waiting_binding = session.encounter_session.control_runtime.controllers.get(pending.controller_id)
            if waiting_binding is not None:
                waiting_label = waiting_binding.label
    transcript_entries = tuple(
        WebTranscriptEntryProjection(speaker=entry.speaker, text=entry.text, visibility=entry.visibility.value)
        for entry in session.story_state.transcript_entries
        if (entry.visibility != StoryTranscriptVisibility.DM_ONLY or binding.role == ControllerRole.DM)
        and (entry.visibility != StoryTranscriptVisibility.PRIVATE_CONTROLLERS or binding.role == ControllerRole.DM or controller_id in entry.controller_ids)
    )
    recent_check_results = _recent_story_check_result_projections(session, controller_id, binding.role)
    story = WebStoryProjection(
        runtime_mode=session.story_state.runtime_mode.value,
        current_scene_id=session.story_state.current_scene_id,
        current_location_id=session.story_state.canonical_location_id,
        party_goals=tuple(session.story_state.current_party_goals),
        open_loops=tuple(session.story_state.open_loops),
        party_actor_ids=tuple(actor_id for actor_id, actor in session.state.actors.items() if actor.side == ActorSide.PLAYER),
        transcript_entries=transcript_entries,
        recent_check_results=recent_check_results,
        pending_check_text=pending_check_text,
        pending_check_actor_id=pending_actor_id,
        waiting_on_label=waiting_label,
    )
    encounter = None
    if session.story_state.runtime_mode == RuntimeMode.COMBAT:
        encounter_projection = session.encounter_session.view_for_controller(controller_id).projection
        if encounter_projection is not None:
            battlefield = None
            if encounter_projection.battlefield is not None:
                battlefield = WebBattlefieldProjection(
                    map_id=encounter_projection.battlefield.map_id,
                    name=encounter_projection.battlefield.name,
                    width=encounter_projection.battlefield.width,
                    height=encounter_projection.battlefield.height,
                    cell_size_feet=encounter_projection.battlefield.cell_size_feet,
                    object_count=len(encounter_projection.battlefield.object_ids),
                    blocker_count=len(encounter_projection.battlefield.blocker_ids),
                    spawn_zone_ids=encounter_projection.battlefield.spawn_zones,
                )
            encounter = WebEncounterProjection(
                phase=encounter_projection.phase,
                round_number=encounter_projection.round_number,
                active_actor_id=encounter_projection.active_actor_id,
                initiative_order=encounter_projection.initiative_order,
                actors=tuple(
                    WebActorProjection(
                        actor_id=actor.public.actor_id,
                        name=actor.public.name,
                        side=actor.public.side,
                        x=actor.public.position.x,
                        y=actor.public.position.y,
                        z=actor.public.position.z,
                        status=actor.public.status,
                        turn_active=actor.public.turn_active,
                        private_visible=(actor.private_state is not None),
                        tile=(
                            WebTileProjection(
                                terrain_id=actor.public.tile_terrain_id,
                                elevation_ft=actor.public.tile_elevation_ft,
                            )
                            if actor.public.tile_terrain_id is not None and actor.public.tile_elevation_ft is not None
                            else None
                        ),
                        current_hit_points=(actor.private_state.current_hit_points if actor.private_state is not None else None),
                        max_hit_points=(actor.private_state.max_hit_points if actor.private_state is not None else None),
                        temp_hit_points=(actor.private_state.temp_hit_points if actor.private_state is not None else None),
                        armor_class=(actor.private_state.effective_armor_class if actor.private_state is not None else None),
                        remaining_movement_ft=(actor.private_state.remaining_movement_ft if actor.private_state is not None else None),
                        action_available=(actor.private_state.action_available if actor.private_state is not None else None),
                        bonus_action_available=(actor.private_state.bonus_action_available if actor.private_state is not None else None),
                        reaction_available=(actor.private_state.reaction_available if actor.private_state is not None else None),
                    )
                    for actor in encounter_projection.actors
                ),
                recent_event_lines=encounter_projection.recent_events,
                battlefield=battlefield,
            )
    return WebSessionProjection(
        session_kind='storytelling',
        state_version=len(session.state.event_log),
        controller=WebControllerIdentity(controller_id=controller_id, role=binding.role, label=binding.label),
        summary_lines=tuple(view.summary_lines),
        available_choices={
            group_id: tuple(WebChoiceProjection(option_id=choice.option_id, label=choice.label, detail=choice.detail) for choice in choices)
            for group_id, choices in view.available_choices.items()
        },
        prompt=_project_session_prompt(prompt),
        story=story,
        encounter=encounter,
    )


class AuthoritativeSessionAdapter:
    def __init__(self, session) -> None:
        self.session = session
        self.session_id = f'session-{id(session)}'

    def validate_controller(self, controller_id: str):
        if hasattr(self.session, 'validate_controller'):
            return self.session.validate_controller(controller_id)
        return self.session.control_runtime.validate_controller(controller_id)

    def projection_for_controller(self, controller_id: str) -> WebSessionProjection:
        self.validate_controller(controller_id)
        if hasattr(self.session, 'story_state'):
            return project_story_session_projection(self.session, controller_id, session_id=self.session_id)
        return project_encounter_session_projection(self.session, controller_id, session_id=self.session_id)

    def submit_command(self, controller_id: str, command: str) -> None:
        self.validate_controller(controller_id)
        if hasattr(self.session, 'handle_input'):
            self.session.handle_input(controller_id, command)
            return
        self.session.execute_for_controller(controller_id, command)

    def submit_reaction(self, controller_id: str, option_ids: list[str] | str | None) -> None:
        self.validate_controller(controller_id)
        if hasattr(self.session, 'encounter_session'):
            self.session.encounter_session.respond_to_prompt(controller_id, option_ids)
            return
        self.session.respond_to_prompt(controller_id, option_ids)



def _coord(position) -> WebCoordinate:
    return WebCoordinate(x=position.x, y=position.y, z=getattr(position, 'z', 0))


def _hex_coord(coord: HexCoord) -> WebHexCoordinate:
    return WebHexCoordinate(q=coord.q, r=coord.r)


def _ground_item_ids_at(session, *, x: int, y: int) -> tuple[str, ...]:
    return tuple(
        ground_item.ground_item_id
        for ground_item in sorted(session.state.ground_items.values(), key=lambda item: item.ground_item_id)
        if ground_item.position.x == x and ground_item.position.y == y
    )


def _control_runtime(session):
    if hasattr(session, 'encounter_session'):
        return session.encounter_session.control_runtime
    return session.control_runtime



def _kernel_for_session(session):
    return _control_runtime(session).kernel



def _owned_actor_ids(session, controller_id: str) -> tuple[str, ...]:
    control_runtime = _control_runtime(session)
    return tuple(actor_id for actor_id in session.state.actors if control_runtime.actor_controllers.get(actor_id) == controller_id)



def _observer_actor_ids(session, controller_id: str) -> tuple[str, ...]:
    owned_actor_ids = _owned_actor_ids(session, controller_id)
    shared_actor_ids = tuple(
        actor.shared_senses_actor_id
        for actor_id in owned_actor_ids
        for actor in (session.state.actors.get(actor_id),)
        if actor is not None and actor.shared_senses_actor_id is not None and actor.shared_senses_actor_id in session.state.actors
    )
    if shared_actor_ids:
        return tuple(dict.fromkeys(shared_actor_ids))
    return owned_actor_ids



def _active_or_owned_actor(session, controller_id: str):
    control_runtime = _control_runtime(session)
    active_actor_id = session.state.active_actor_id
    if active_actor_id is not None and control_runtime.actor_controllers.get(active_actor_id) == controller_id:
        return session.state.actors[active_actor_id]
    owned_actor_ids = _owned_actor_ids(session, controller_id)
    if owned_actor_ids:
        return session.state.actors[owned_actor_ids[0]]
    return None



def _combat_active_owned_actor(session, controller_id: str):
    control_runtime = _control_runtime(session)
    active_actor_id = session.state.active_actor_id
    if active_actor_id is None:
        return None
    if control_runtime.actor_controllers.get(active_actor_id) != controller_id:
        return None
    return session.state.actors[active_actor_id]



def _preview_actor(session, controller_id: str):
    return _active_or_owned_actor(session, controller_id)


def _controller_can_inspect_position(session, controller_id: str, position: GridPosition) -> bool:
    binding = _control_runtime(session).validate_controller(controller_id)
    if binding.role == ControllerRole.DM:
        return True
    observer_actor_ids = _observer_actor_ids(session, controller_id)
    return controller_can_see_position(session.state, observer_actor_ids, position)


def _required_prompt_kind(prompt) -> str:
    prompt_kind = getattr(prompt, 'prompt_kind', None)
    if not isinstance(prompt_kind, str) or not prompt_kind:
        raise EncounterValidationError('Projected prompts must declare a non-empty `prompt_kind`.')
    return prompt_kind


def _project_ui_prompt(prompt) -> WebPromptView | None:
    if prompt is None:
        return None
    return WebPromptView(
        prompt_id=prompt.prompt_id,
        prompt_kind=_required_prompt_kind(prompt),
        text=prompt.prompt,
        options=tuple(
            WebPromptOptionView(
                option_id=option.option_id,
                label=option.label,
                detail=option.detail,
                actor_id=getattr(option, 'actor_id', None),
            )
            for option in getattr(prompt, 'options', ())
        ),
    )



def _project_session_prompt(prompt) -> WebPromptProjection | None:
    if prompt is None:
        return None
    return WebPromptProjection(
        prompt_id=prompt.prompt_id,
        prompt_kind=_required_prompt_kind(prompt),
        text=prompt.prompt,
        options=tuple(
            WebChoiceProjection(
                option_id=option.option_id,
                label=option.label,
                detail=option.detail,
                actor_id=getattr(option, 'actor_id', None),
            )
            for option in getattr(prompt, 'options', ())
        ),
    )





def _manual_demo_runtime_mode(session) -> str:
    if getattr(session, 'story_session', None) is None:
        return 'character-creation'
    return 'demo-complete'


def _manual_demo_action_groups(session, available_choices: dict[str, tuple]) -> tuple[WebActionGroupView, ...]:
    if getattr(session, 'story_session', None) is None:
        return _project_creation_choice_groups(available_choices)
    return ()


def _creation_choice_command_insert_text(group_id: str, option_id: str) -> str | None:
    if group_id == 'create-flow' and option_id == 'begin':
        return '/create begin'
    if group_id == 'species':
        return f'/create choose species {option_id}'
    if group_id == 'class':
        return f'/create choose class {option_id}'
    if group_id == 'class-skills':
        return f'/create choose class-skills {option_id}'
    if group_id == 'background':
        return f'/create choose background {option_id}'
    if group_id.startswith('choice:'):
        return f'/create choose choice {group_id.split(':', 1)[1]} {option_id}'
    if group_id == 'ability-method':
        if option_id == 'roll':
            return '/create ability generate roll'
        if option_id == 'point-buy':
            return '/create ability generate point-buy 15 14 13 12 10 8'
    if group_id == 'ability-array':
        return f'/create ability choose {option_id}'
    if group_id == 'background-asi':
        return f'/create background-asi choose {option_id}'
    if group_id == 'background-equipment':
        if option_id == 'gold':
            return '/create equipment background gold'
        return f'/create equipment background package {option_id}'
    if group_id == 'class-equipment':
        if option_id == 'wealth':
            return '/create equipment class wealth'
        return f'/create equipment class package {option_id}'
    if group_id == 'items':
        return f'/create equipment buy {option_id} 1'
    return None


def _creation_choice_command_prefix(group_id: str) -> str | None:
    if group_id == 'class-skills':
        return '/create choose class-skills'
    if group_id.startswith('choice:'):
        return f"/create choose choice {group_id.split(':', 1)[1]}"
    return None


def _project_creation_choice_groups(available_choices: dict[str, tuple]) -> tuple[WebActionGroupView, ...]:
    groups: list[WebActionGroupView] = []
    for group_id, choices in available_choices.items():
        projected_choices: list[WebActionChoiceView] = []
        for choice in choices:
            command_insert_text = _creation_choice_command_insert_text(group_id, choice.option_id)
            projected_choices.append(
                WebActionChoiceView(
                    group_id=group_id,
                    option_id=choice.option_id,
                    label=choice.label,
                    detail=choice.detail,
                    execution_kind='creation-choice',
                    target_kind='none',
                    command_hint=(command_insert_text or 'Use this option id in your next /create command.'),
                    command_insert_text=command_insert_text,
                    command_prefix=_creation_choice_command_prefix(group_id),
                )
            )
        groups.append(WebActionGroupView(group_id=group_id, label=group_id, choices=tuple(projected_choices)))
    return tuple(groups)


def _advancement_choice_command_insert_text(group_id: str, option_id: str) -> str | None:
    if not group_id.startswith('levelup:'):
        return None
    _, actor_id, choice_id = group_id.split(':', 2)
    if choice_id == 'class-selection':
        return f'/levelup class {actor_id} {option_id}'
    return f'/levelup choose {actor_id} {choice_id} {option_id}'


def _advancement_choice_command_prefix(group_id: str) -> str | None:
    if not group_id.startswith('levelup:'):
        return None
    _, actor_id, choice_id = group_id.split(':', 2)
    if choice_id == 'class-selection':
        return f'/levelup class {actor_id}'
    return f'/levelup choose {actor_id} {choice_id}'


def _project_action_groups(available_choices: dict[str, tuple]) -> tuple[WebActionGroupView, ...]:
    groups: list[WebActionGroupView] = []
    for group_id, choices in available_choices.items():
        projected_choices: list[WebActionChoiceView] = []
        for choice in choices:
            execution_kind = 'command'
            target_kind = 'none'
            command_hint = None
            command_insert_text = None
            command_prefix = None
            if group_id == 'attacks':
                execution_kind = 'attack'
                target_kind = 'creature'
            elif group_id == 'reactions':
                execution_kind = 'reaction'
            elif group_id == 'actions':
                execution_kind = 'action'
            elif group_id == 'bonus_actions':
                execution_kind = 'bonus-action'
            elif group_id.startswith('levelup:'):
                command_insert_text = _advancement_choice_command_insert_text(group_id, choice.option_id)
                command_prefix = _advancement_choice_command_prefix(group_id)
                command_hint = command_insert_text or 'Use this option id in your next /levelup command.'
            projected_choices.append(
                WebActionChoiceView(
                    group_id=group_id,
                    option_id=choice.option_id,
                    label=choice.label,
                    detail=choice.detail,
                    execution_kind=execution_kind,
                    target_kind=target_kind,
                    command_hint=command_hint,
                    command_insert_text=command_insert_text,
                    command_prefix=command_prefix,
                )
            )
        groups.append(WebActionGroupView(group_id=group_id, label=group_id.replace('_', ' ').title(), choices=tuple(projected_choices)))
    return tuple(groups)




def _cover_rank(cover_value: str | None) -> int:
    mapping = {
        CoverLevel.NONE.value: 0,
        CoverLevel.HALF.value: 1,
        CoverLevel.THREE_QUARTERS.value: 2,
        CoverLevel.TOTAL.value: 3,
    }
    return mapping.get(cover_value or CoverLevel.NONE.value, 0)


def _merge_cover(current: str | None, proposed: str | None) -> str | None:
    if proposed is None:
        return current
    if current is None or _cover_rank(proposed) > _cover_rank(current):
        return proposed
    return current


def _persistent_area_cells(session, area) -> tuple[GridPosition, ...]:
    return tuple(
        GridPosition(tile.position.x, tile.position.y, tile.elevation_ft)
        for tile in session.state.battlefield.tiles.values()
        if persistent_area_contains_position(area, GridPosition(tile.position.x, tile.position.y, tile.elevation_ft))
    )


def _persistent_feature_projection(session, controller_id: str, role: ControllerRole) -> tuple[tuple[WebMapFeatureView, ...], dict[tuple[int, int, int], dict[str, object]]]:
    observer_actor_ids = _observer_actor_ids(session, controller_id)
    features: list[WebMapFeatureView] = []
    overlays: dict[tuple[int, int, int], dict[str, object]] = {}

    def overlay_for(cell: GridPosition) -> dict[str, object]:
        key = (cell.x, cell.y, cell.z)
        if key not in overlays:
            overlays[key] = {'blocked': False, 'cover': None, 'tags': set()}
        return overlays[key]

    for illusion in session.state.illusions.values():
        observer_id = next((actor_id for actor_id in observer_actor_ids if illusion_visible_to_observer(session.state, illusion, actor_id)), None)
        if role != ControllerRole.DM and observer_id is None:
            continue
        observer_state = None if observer_id is None else illusion_observer_state(illusion, observer_id)
        observer_status = 'dm-visible' if role == ControllerRole.DM else observer_state.status.value
        features.append(
            WebMapFeatureView(
                feature_id=illusion.illusion_id,
                feature_type='illusion',
                cells=tuple(_coord(cell) for cell in illusion.cells),
                elevation_ft=illusion.cells[0].z if illusion.cells else (illusion.persistent.anchor_position.z if illusion.persistent.anchor_position is not None else 0),
                bottom_ft=illusion.persistent.anchor_position.z if illusion.persistent.anchor_position is not None else 0,
                top_ft=(illusion.persistent.anchor_position.z if illusion.persistent.anchor_position is not None else 0) + illusion.definition.height_ft,
                traversable=not illusion.definition.actual_properties.actual_blocker,
                occupiable=not illusion.definition.actual_properties.actual_blocker,
                blocks_los=illusion.definition.actual_properties.actual_blocker,
                blocks_loe=illusion.definition.actual_properties.actual_blocker,
                cover_provided=(CoverLevel.HALF.value if illusion.definition.actual_properties.actual_cover else CoverLevel.NONE.value),
                tags=illusion.definition.semantic_tags,
                display_name=illusion.definition.display_name,
                display_description=illusion.definition.display_description,
                apparent_only=True,
                observer_state=observer_status,
                apparent_blocker=illusion.definition.apparent_properties.apparent_blocker,
                apparent_cover=illusion.definition.apparent_properties.apparent_cover.value,
                actual_blocker=illusion.definition.actual_properties.actual_blocker,
                actual_cover=illusion.definition.actual_properties.actual_cover,
            )
        )
        if role == ControllerRole.DM or observer_state is None or not illusion_projects_apparent_state(observer_state):
            continue
        for cell in illusion.cells:
            overlay = overlay_for(cell)
            overlay['blocked'] = overlay['blocked'] or illusion.definition.apparent_properties.apparent_blocker
            overlay['cover'] = _merge_cover(overlay['cover'], illusion.definition.apparent_properties.apparent_cover.value)
            overlay['tags'].update(illusion.definition.semantic_tags)

    for area in session.state.persistent_areas.values():
        cells = _persistent_area_cells(session, area)
        if not cells:
            continue
        if role != ControllerRole.DM and not any(_controller_can_inspect_position(session, controller_id, cell) for cell in cells):
            continue
        features.append(
            WebMapFeatureView(
                feature_id=area.area_id,
                feature_type='persistent-area',
                cells=tuple(_coord(cell) for cell in cells),
                elevation_ft=area.origin.z,
                bottom_ft=area.origin.z,
                top_ft=area.origin.z + area.definition.area_size_ft,
                traversable=True,
                occupiable=True,
                blocks_los=False,
                blocks_loe=False,
                cover_provided=CoverLevel.NONE.value,
                tags=area.definition.semantic_tags,
                display_name=area.definition.name,
                display_description=', '.join(area.definition.semantic_tags),
                apparent_only=area.definition.apparent_only,
                observer_state=('dm-visible' if role == ControllerRole.DM else 'visible'),
                apparent_blocker=(area.definition.apparent_only and area.definition.blocks_vision),
                apparent_cover=None,
                actual_blocker=False,
                actual_cover=False,
            )
        )
        if role == ControllerRole.DM or not area.definition.apparent_only:
            continue
        for cell in cells:
            overlay = overlay_for(cell)
            overlay['blocked'] = overlay['blocked'] or area.definition.blocks_vision
            overlay['tags'].update(area.definition.semantic_tags)

    normalized_overlays = {
        key: {
            'blocked': bool(value['blocked']),
            'cover': value['cover'],
            'tags': tuple(sorted(value['tags'])),
        }
        for key, value in overlays.items()
    }
    return tuple(features), normalized_overlays


def _project_travel_map(session, controller_id: str, role: ControllerRole) -> WebTravelMapView | None:
    state = getattr(session.story_state, 'travel_state', None)
    travel_engine = getattr(session, 'travel_engine', None)
    if state is None or travel_engine is None:
        return None
    travel_map = travel_engine.travel_map
    dm_view = role == ControllerRole.DM
    route_coords = set(state.planned_route.path if state.planned_route is not None else ())
    discovered_hexes = set(state.discovered_hexes)
    discovered_landmarks = set(state.discovered_landmark_ids)
    known_locations = set(state.known_location_ids)
    hexes = []
    for cell in sorted(travel_map.cells, key=lambda item: (item.coord.r, item.coord.q)):
        discovered = cell.coord in discovered_hexes
        if not dm_view and not discovered:
            continue
        visible_landmark_ids = tuple(
            landmark.landmark_id
            for landmark in sorted(travel_map.landmarks, key=lambda item: item.landmark_id)
            if landmark.coord == cell.coord and (dm_view or landmark.landmark_id in discovered_landmarks)
        )
        location_id = cell.location_id
        if not dm_view and location_id is not None and location_id not in known_locations and not discovered:
            location_id = None
        hexes.append(
            WebTravelHexView(
                coord=_hex_coord(cell.coord),
                terrain_id=cell.terrain.value,
                travel_cost_units=max(1, cell.travel_cost_units + cell.route_cost_adjustment_units),
                route_kind=cell.route_kind,
                traversable=cell.traversable,
                discovered=discovered,
                current_party=cell.coord == state.party_coord,
                on_planned_route=cell.coord in route_coords,
                landmark_ids=visible_landmark_ids,
                location_id=location_id,
                tags=(cell.tags if dm_view or discovered else ()),
            )
        )
    landmarks = []
    for landmark in sorted(travel_map.landmarks, key=lambda item: (item.coord.r, item.coord.q, item.landmark_id)):
        if not dm_view and landmark.landmark_id not in discovered_landmarks:
            continue
        landmarks.append(
            WebTravelLandmarkView(
                landmark_id=landmark.landmark_id,
                name=landmark.name,
                coord=_hex_coord(landmark.coord),
                description=landmark.description,
                location_id=landmark.location_id,
                scene_id=landmark.scene_id,
                tags=landmark.tags,
                hidden=(landmark.hidden if dm_view else False),
            )
        )
    route_view = None
    if state.planned_route is not None:
        route_view = WebTravelRouteView(
            destination=_hex_coord(state.planned_route.destination),
            destination_label=state.planned_route.destination_label,
            path=tuple(_hex_coord(coord) for coord in state.planned_route.path),
            estimated_cost_units=state.planned_route.estimated_cost_units,
            estimated_minutes=state.planned_route.estimated_minutes,
        )
    pending_hook = None
    if state.pending_hook is not None:
        pending_hook = WebTravelHookView(
            hook_id=state.pending_hook.hook_id,
            hook_type=state.pending_hook.hook_type.value,
            summary=state.pending_hook.summary,
            coord=(_hex_coord(state.pending_hook.coord) if state.pending_hook.coord is not None else None),
            location_id=state.pending_hook.location_id,
            scene_id=state.pending_hook.scene_id,
            battlefield_map_id=(state.pending_hook.battlefield_map_id if dm_view else None),
            interrupts_travel=state.pending_hook.interrupts_travel,
        )
    return WebTravelMapView(
        map_id=travel_map.map_id,
        name=travel_map.name,
        region_id=travel_map.region_id,
        coordinate_system=travel_map.coord_system.value,
        hex_scale_miles=travel_map.hex_scale_miles,
        dm_view=dm_view,
        current_party_coord=_hex_coord(state.party_coord),
        pace=state.pace.value,
        status=state.status.value,
        elapsed_minutes=state.elapsed_minutes,
        hexes=tuple(hexes),
        landmarks=tuple(landmarks),
        planned_route=route_view,
        pending_hook=pending_hook,
    )


def _project_map(session, controller_id: str) -> WebMapView | None:
    battlefield = session.state.battlefield
    if battlefield.grid is None:
        return None
    binding = _control_runtime(session).validate_controller(controller_id)
    persistent_features, apparent_overlays = _persistent_feature_projection(session, controller_id, binding.role)
    sorted_tiles = sorted(battlefield.tiles.values(), key=lambda item: (item.position.y, item.position.x))
    cells = []
    for tile in sorted_tiles:
        position = GridPosition(tile.position.x, tile.position.y, tile.elevation_ft)
        inspectable = _controller_can_inspect_position(session, controller_id, position)
        overlay = apparent_overlays.get((tile.position.x, tile.position.y, tile.elevation_ft), {'blocked': False, 'cover': None, 'tags': ()})
        cells.append(
            WebMapCellView(
                position=WebCoordinate(x=tile.position.x, y=tile.position.y, z=tile.elevation_ft),
                terrain_id=tile.terrain_id,
                elevation_ft=tile.elevation_ft,
                ceiling_ft=tile.ceiling_ft,
                traversable=tile.traversable,
                occupiable=tile.occupiable,
                movement_cost_feet_per_5ft=tile.movement_cost_feet_per_5ft,
                difficult_terrain=tile.difficult_terrain,
                lighting=tile.lighting.value,
                obscurement=tile.obscurement.value,
                blocks_los=tile.blocks_los,
                blocks_loe=tile.blocks_loe,
                base_cover=tile.base_cover.value,
                supported_modes=tuple(mode.value for mode in tile.supported_modes),
                object_ids=((tile.object_ids + _ground_item_ids_at(session, x=tile.position.x, y=tile.position.y)) if inspectable else ()),
                blocker_ids=(tile.blocker_ids if inspectable else ()),
                tags=(tile.tags if inspectable else ()),
                apparent_blocked=bool(overlay['blocked']) if binding.role != ControllerRole.DM else False,
                apparent_cover=(overlay['cover'] if binding.role != ControllerRole.DM else None),
                apparent_tags=(tuple(overlay['tags']) if binding.role != ControllerRole.DM else ()),
            )
        )
    actual_features = tuple(
        WebMapFeatureView(
            feature_id=feature.feature_id,
            feature_type=feature.feature_type,
            cells=tuple(_coord(cell) for cell in feature.cells),
            elevation_ft=feature.elevation_ft,
            bottom_ft=feature.bottom_ft,
            top_ft=feature.top_ft,
            traversable=feature.traversable,
            occupiable=feature.occupiable,
            blocks_los=feature.blocks_los,
            blocks_loe=feature.blocks_loe,
            cover_provided=feature.cover_provided.value,
            tags=feature.tags,
        )
        for feature in battlefield.features.values()
        if binding.role == ControllerRole.DM or any(_controller_can_inspect_position(session, controller_id, GridPosition(cell.x, cell.y, feature.elevation_ft)) for cell in feature.cells)
    )
    features = actual_features + persistent_features
    actor_ids = session.state.initiative_order or tuple(session.state.actors.keys())
    projected_tokens = [_project_token(session, controller_id, binding.role, actor_id) for actor_id in actor_ids]
    tokens = tuple(token for token in projected_tokens if token is not None)
    return WebMapView(
        map_id=battlefield.map_id,
        name=battlefield.name,
        grid=WebMapGridView(
            width=battlefield.grid.width,
            height=battlefield.grid.height,
            cell_size_feet=battlefield.grid.cell_size_feet,
            min_x=battlefield.grid.min_x,
            min_y=battlefield.grid.min_y,
            max_x=battlefield.grid.max_x,
            max_y=battlefield.grid.max_y,
        ),
        cells=tuple(cells),
        features=features,
        tokens=tokens,
    )

def _project_token_status(actor) -> str:
    if actor.dying_state.status == DyingStateStatus.DEAD:
        return 'dead'
    if actor.dying_state.status == DyingStateStatus.STABLE_AT_0_HP:
        return 'stable'
    if actor.current_hit_points == 0 or actor.dying_state.status == DyingStateStatus.AT_0_HP_UNCONSCIOUS:
        return 'unconscious'
    return 'active'


def _project_token(session, controller_id: str, role: ControllerRole, actor_id: str) -> WebTokenView | None:
    control_runtime = _control_runtime(session)
    actor = session.state.actors[actor_id]
    owner_controller_id = control_runtime.controller_for_actor(actor_id)
    is_owner = owner_controller_id == controller_id
    sees_private = is_owner or role == ControllerRole.DM
    visibility_state = ObserverVisibilityState.VISIBLE
    if role != ControllerRole.DM and not is_owner:
        visibility_state = controller_visibility_state(session.state, _observer_actor_ids(session, controller_id), actor)
        if visibility_state == ObserverVisibilityState.HIDDEN:
            return None
    status = _project_token_status(actor)
    if actor.actor_id == session.state.active_actor_id:
        status = f'{status}-turn'
    conditions = tuple(instance.condition_type.value for instance in actor.condition_instances) if sees_private else ()
    label = actor.name if visibility_state == ObserverVisibilityState.VISIBLE or sees_private else 'Unseen contact'
    return WebTokenView(
        actor_id=actor.actor_id,
        name=label,
        side=(actor.side.value if visibility_state == ObserverVisibilityState.VISIBLE or sees_private else 'unknown'),
        position=_coord(actor.position),
        occupied_height_ft=actor.occupied_height_ft,
        support_state=actor.support_state.value,
        status=status,
        is_active=actor.actor_id == session.state.active_actor_id,
        is_owner=is_owner,
        visibility_state=visibility_state.value,
        hit_points=(actor.current_hit_points if sees_private else None),
        max_hit_points=(actor.max_hit_points if sees_private else None),
        temp_hit_points=(actor.temp_hit_points if sees_private else None),
        armor_class=(actor.effective_armor_class if sees_private else None),
        movement_remaining_ft=(actor.remaining_movement_ft if sees_private else None),
        action_available=(actor.action_available if sees_private else None),
        bonus_action_available=(actor.bonus_action_available if sees_private else None),
        reaction_available=(actor.reaction_available if sees_private else None),
        visible_conditions=conditions,
    )




def _project_character_cards(session, controller_id: str, role: ControllerRole) -> tuple[WebCharacterCardView, ...]:
    if role == ControllerRole.DM:
        actor_ids = [
            actor_id
            for actor_id, actor in session.state.actors.items()
            if actor.side == ActorSide.PLAYER and actor.character_record is not None
        ]
    else:
        actor_ids = [
            actor_id
            for actor_id in _owned_actor_ids(session, controller_id)
            if session.state.actors[actor_id].character_record is not None
        ]
    actor_ids.sort()
    return tuple(_project_character_card(session, actor_id, role=role) for actor_id in actor_ids)


def _project_character_item_label(item: ItemRecord, *, identified: bool) -> str:
    if identified or not item.is_magical:
        return item.name
    if item.armor_category is not None:
        return 'Unidentified magical armor'
    if item.weapon_category is not None:
        return 'Unidentified magical weapon'
    lowered_tags = {tag.casefold() for tag in item.tags}
    if 'potion' in lowered_tags:
        return 'Unidentified magical potion'
    if 'scroll' in lowered_tags:
        return 'Unidentified magical scroll'
    return 'Unidentified magical item'


def _project_character_item_passive_summary(item: ItemRecord) -> str | None:
    parts: list[str] = []
    if item.weapon_category is not None:
        weapon_bits = [f'Weapon: {item.weapon_category}']
        if item.weapon_damage_dice_count is not None and item.weapon_damage_die_faces is not None and item.weapon_damage_type is not None:
            weapon_bits.append(f'{item.weapon_damage_dice_count}d{item.weapon_damage_die_faces} {item.weapon_damage_type}')
        if item.weapon_properties:
            weapon_bits.append(f"Properties: {', '.join(item.weapon_properties)}")
        parts.append('; '.join(weapon_bits))
    if item.armor_category is not None:
        armor_bits = [f'Armor: {item.armor_category.value}']
        if item.armor_base_ac is not None:
            armor_bits.append(f'AC {item.armor_base_ac}')
        if item.armor_dex_cap is not None:
            armor_bits.append(f'DEX cap {item.armor_dex_cap}')
        parts.append('; '.join(armor_bits))
    if parts:
        return '; '.join(parts)
    if item.is_magical:
        return 'Unidentified magical item' + (f"; Tags: {', '.join(item.tags)}" if item.tags else '')
    if item.tags:
        return f"Tags: {', '.join(item.tags)}"
    return None


def _project_character_item_view_text(item: ItemRecord, *, identified: bool, role: ControllerRole) -> tuple[str, str | None]:
    label = _project_character_item_label(item, identified=(identified or role == ControllerRole.DM))
    state_label = None
    if not identified and role != ControllerRole.DM and item.is_magical:
        state_label = _project_character_item_passive_summary(item)
    return label, state_label


def _project_equipped_item_label(
    item_catalog: dict[str, ItemRecord],
    item_id: str | None,
    *,
    identified_item_ids: frozenset[str],
    role: ControllerRole,
) -> str | None:
    if item_id is None:
        return None
    item = item_catalog.get(item_id)
    if item is None:
        return _humanize_label(item_id) or item_id
    label, _ = _project_character_item_view_text(item, identified=(item_id in identified_item_ids), role=role)
    return label


def _project_attack_label(attack, item_catalog: dict[str, ItemRecord], identified_item_ids: frozenset[str], role: ControllerRole) -> str:
    if attack.source_item_id is None:
        return attack.name
    item = item_catalog.get(attack.source_item_id)
    if item is None:
        return attack.name
    if role == ControllerRole.DM or attack.source_item_id in identified_item_ids or not item.is_magical:
        return attack.name
    return _project_character_item_label(item, identified=False)


def _project_character_card(session, actor_id: str, *, role: ControllerRole) -> WebCharacterCardView:
    actor = session.state.actors[actor_id]
    record = actor.character_record
    if record is None:
        raise EncounterValidationError(f'Player actor {actor_id!r} is missing its CharacterRecord for web character-card projection.')
    proficient_skills = {skill.title() for skill in (record.class_skill_proficiencies + record.background_skill_proficiencies)}
    tool_proficiencies = list(record.tool_proficiencies)
    for selection in record.proficiency_selections:
        if selection.category == ProficiencyCategory.SKILL:
            proficient_skills.add(selection.name.title())
        elif selection.category == ProficiencyCategory.TOOL and selection.name not in tool_proficiencies:
            tool_proficiencies.append(selection.name)
    skill_views = tuple(
        WebCharacterSkillView(
            skill_id=slugify(skill_name),
            label=skill_name,
            bonus=bonus,
            proficient=(skill_name in proficient_skills),
        )
        for skill_name, bonus in sorted(actor.skill_bonuses.items(), key=lambda item: item[0])
    )
    ability_views = tuple(
        WebCharacterAbilityView(
            ability_id=ability.value,
            label=_ability_label(ability),
            score=actor.ability_scores.get(ability, 0),
            modifier=actor.ability_modifiers.get(ability, 0),
            save_bonus=actor.saving_throw_bonuses.get(ability, actor.ability_modifiers.get(ability, 0)),
            save_proficient=(ability in record.saving_throw_proficiencies),
        )
        for ability in ABILITY_ORDER
    )
    item_catalog = _kernel_for_session(session).item_catalog
    held_counts: dict[str, int] = {}
    for held_item_id in actor.held_item_ids:
        held_counts[held_item_id] = held_counts.get(held_item_id, 0) + 1
    stowed_counts = derived_stowed_counts(actor, item_catalog)
    item_ids = {item_id for item_id, quantity in actor.carried_item_counts.items() if quantity > 0}
    if actor.equipped_armor_item_id is not None:
        item_ids.add(actor.equipped_armor_item_id)
    if actor.main_hand_item_id is not None:
        item_ids.add(actor.main_hand_item_id)
    if actor.off_hand_item_id is not None:
        item_ids.add(actor.off_hand_item_id)
    identified_item_ids = actor.identified_item_ids
    attack_views = tuple(
        WebCharacterAttackView(
            attack_id=attack.attack_id,
            name=_project_attack_label(attack, item_catalog, identified_item_ids, role),
            attack_kind=attack.attack_kind.value,
            to_hit_bonus=attack.to_hit_bonus,
            damage_text=_attack_damage_text(attack),
            reach_ft=attack.reach_ft,
            range_ft=attack.range_ft,
            long_range_ft=attack.long_range_ft,
        )
        for attack in sorted(actor.attacks.values(), key=lambda item: item.name)
    )
    cantrip_views, spell_views = _project_character_spell_views(actor, record)
    resource_views = tuple(sorted(_project_character_resources(actor), key=lambda item: item.label))
    item_views = []
    for item_id in sorted(item_ids, key=_humanize_label):
        item = item_catalog.get(item_id)
        if item is None:
            label = _humanize_label(item_id) or item_id
            passive_summary = None
        else:
            label, passive_summary = _project_character_item_view_text(item, identified=(item_id in identified_item_ids), role=role)
        state_label = '; '.join(
            part for part in (
                passive_summary,
                ('main hand' if actor.main_hand_item_id == item_id else None),
                ('off hand' if actor.off_hand_item_id == item_id else None),
                ('armor slot' if actor.equipped_armor_item_id == item_id else None),
                (f'stowed {stowed_counts[item_id]}' if stowed_counts.get(item_id, 0) > 0 else None),
            )
            if part is not None
        ) or None
        item_views.append(
            WebCharacterItemView(
                item_id=item_id,
                label=label,
                quantity=actor.carried_item_counts.get(item_id, 0),
                state_label=state_label,
            )
        )
    item_views = tuple(item_views)
    main_hand_label = _project_equipped_item_label(item_catalog, actor.main_hand_item_id, identified_item_ids=identified_item_ids, role=role)
    off_hand_label = _project_equipped_item_label(item_catalog, actor.off_hand_item_id, identified_item_ids=identified_item_ids, role=role)
    armor_label = _project_equipped_item_label(item_catalog, actor.equipped_armor_item_id, identified_item_ids=identified_item_ids, role=role)
    effect_views = _project_character_effects(session, actor)
    spellcasting_ability = actor.spellcasting_ability
    if spellcasting_ability is None:
        spellcasting_ability = next((selection.spellcasting_ability for selection in record.spell_selections if selection.spellcasting_ability is not None), None)
    passive_perception = 10 + actor.skill_bonuses.get('Perception', actor.ability_modifiers.get(Ability.WIS, 0))
    origin_feats = tuple(str(feat) for feat in record.origin_feats)
    feat_summaries = tuple(_format_feat_summary(feat) for feat in record.feat_grants)
    concentration_effect_name = None
    if actor.concentrating_effect_id is not None:
        active = session.state.active_effects.get(actor.concentrating_effect_id)
        concentration_effect_name = active.name if active is not None else actor.concentrating_effect_id
    return WebCharacterCardView(
        actor_id=actor.actor_id,
        character_id=record.record_id,
        name=actor.name,
        avatar_label=_avatar_label(actor.name),
        class_name=_humanize_label(record.class_id),
        level=record.level,
        species_name=_humanize_label(record.species_id),
        background_name=_humanize_label(record.background_id),
        proficiency_bonus=actor.proficiency_bonus,
        current_hit_points=actor.current_hit_points,
        max_hit_points=actor.max_hit_points,
        temp_hit_points=actor.temp_hit_points,
        armor_class=actor.effective_armor_class,
        initiative_bonus=actor.initiative_bonus,
        movement_remaining_ft=actor.remaining_movement_ft,
        free_object_interaction_available=actor.remaining_free_object_interaction,
        dying_status=(None if actor.dying_state.status == DyingStateStatus.ALIVE else actor.dying_state.status.value),
        death_save_successes=(actor.dying_state.death_save_successes if actor.uses_death_saves else None),
        death_save_failures=(actor.dying_state.death_save_failures if actor.uses_death_saves else None),
        stable_recovery_hours_remaining=actor.dying_state.stable_recovery_hours_remaining,
        active_turn=(actor.actor_id == session.state.active_actor_id),
        action_available=actor.action_available,
        bonus_action_available=actor.bonus_action_available,
        reaction_available=actor.reaction_available,
        spellcasting_ability=(_ability_label(spellcasting_ability) if spellcasting_ability is not None else None),
        spell_save_dc=actor.spell_save_dc,
        spell_attack_bonus=actor.spell_attack_bonus,
        passive_perception=passive_perception,
        concentration_effect_name=concentration_effect_name,
        origin_feats=origin_feats,
        feat_summaries=feat_summaries,
        tool_proficiencies=tuple(tool_proficiencies),
        main_hand_label=main_hand_label,
        off_hand_label=off_hand_label,
        armor_label=armor_label,
        speeds=_project_character_speeds(actor),
        abilities=ability_views,
        skills=skill_views,
        conditions=tuple(_condition_label(instance.condition_type.value) for instance in actor.condition_instances),
        effects=effect_views,
        attacks=attack_views,
        cantrips=cantrip_views,
        spells=spell_views,
        resources=resource_views,
        items=item_views,
    )


def _project_character_speeds(actor) -> tuple[WebCharacterSpeedView, ...]:
    speeds = [WebCharacterSpeedView(mode_id='walk', label='Walk', speed_ft=actor.speed_ft)]
    if actor.climb_speed_ft > 0:
        speeds.append(WebCharacterSpeedView(mode_id='climb', label='Climb', speed_ft=actor.climb_speed_ft))
    if actor.swim_speed_ft > 0:
        speeds.append(WebCharacterSpeedView(mode_id='swim', label='Swim', speed_ft=actor.swim_speed_ft))
    if actor.fly_speed_ft > 0:
        speeds.append(WebCharacterSpeedView(mode_id='fly', label='Fly', speed_ft=actor.fly_speed_ft))
    return tuple(speeds)


def _project_character_spell_views(actor, record) -> tuple[tuple[WebCharacterSpellView, ...], tuple[WebCharacterSpellView, ...]]:
    runtime_spell_by_name = {spell.name.strip().lower(): spell for spell in actor.spells.values()}
    cantrips: list[WebCharacterSpellView] = []
    spells: list[WebCharacterSpellView] = []
    for selection in sorted(record.spell_selections, key=lambda item: (item.spell_level, item.spell_name, item.selection_kind.value, item.source.source_name)):
        runtime_spell = runtime_spell_by_name.get(selection.spell_name.strip().lower())
        view = WebCharacterSpellView(
            spell_id=selection.spell_id,
            name=selection.spell_name,
            level=selection.spell_level,
            selection_kind=selection.selection_kind.value,
            source_label=selection.source.source_name,
            remaining_uses=(runtime_spell.remaining_uses if runtime_spell is not None else None),
        )
        if selection.spell_level == 0:
            cantrips.append(view)
        else:
            spells.append(view)
    return tuple(cantrips), tuple(spells)


def _project_character_resources(actor) -> tuple[WebCharacterResourceView, ...]:
    resources: list[WebCharacterResourceView] = [
        WebCharacterResourceView(
            resource_id='free-object-interaction',
            label='Free Object Interaction',
            detail=('available this turn' if actor.remaining_free_object_interaction else 'already spent this turn'),
            remaining_uses=(1 if actor.remaining_free_object_interaction else 0),
        )
    ]
    if actor.total_hit_dice > 0 and actor.hit_die_faces > 0:
        resources.append(
            WebCharacterResourceView(
                resource_id='hit-dice',
                label=f'Hit Dice (d{actor.hit_die_faces})',
                detail=f'{actor.remaining_hit_dice}/{actor.total_hit_dice} remaining',
                remaining_uses=actor.remaining_hit_dice,
            )
        )
    for pool in actor.resource_pools.values():
        resources.append(
            WebCharacterResourceView(
                resource_id=pool.resource_id,
                label=pool.label,
                detail=f'{pool.current}/{pool.maximum}; {pool.detail}'.strip('; '),
                remaining_uses=pool.current,
            )
        )
    for capability in actor.capabilities.values():
        if capability.remaining_uses is None:
            continue
        max_suffix = f'/{capability.max_uses}' if capability.max_uses is not None else ''
        resources.append(
            WebCharacterResourceView(
                resource_id=capability.option_id,
                label=capability.name,
                detail=f'{capability.kind.value}; {capability.action_cost}; {capability.remaining_uses}{max_suffix}',
                remaining_uses=capability.remaining_uses,
            )
        )
    for spell in actor.spells.values():
        if spell.remaining_uses is None:
            continue
        max_suffix = f'/{spell.max_uses}' if spell.max_uses is not None else ''
        resources.append(
            WebCharacterResourceView(
                resource_id=spell.option_id,
                label=spell.name,
                detail=f'spell; {spell.action_cost}; {spell.remaining_uses}{max_suffix}',
                remaining_uses=spell.remaining_uses,
            )
        )
    return tuple(resources)


def _project_character_effects(session, actor) -> tuple[WebCharacterEffectView, ...]:
    views: list[WebCharacterEffectView] = []
    for effect in session.state.active_effects.values():
        if actor.actor_id not in effect.target_actor_ids and actor.concentrating_effect_id != effect.effect_instance_id:
            continue
        views.append(
            WebCharacterEffectView(
                effect_id=effect.effect_instance_id,
                name=effect.name,
                summary=_active_effect_summary(effect),
                remaining_rounds=effect.remaining_rounds,
                concentration=(actor.concentrating_effect_id == effect.effect_instance_id),
            )
        )
    views.sort(key=lambda item: item.name)
    return tuple(views)


def _active_effect_summary(effect) -> str:
    parts: list[str] = []
    if effect.definition.armor_class_bonus:
        parts.append(f'AC +{effect.definition.armor_class_bonus}')
    if effect.definition.damage_resistances:
        parts.append(f'resists {", ".join(effect.definition.damage_resistances)}')
    if effect.definition.speed_override_ft is not None:
        parts.append(f'speed max {effect.definition.speed_override_ft} ft')
    if effect.definition.melee_attack_damage_bonus:
        parts.append(f'melee damage +{effect.definition.melee_attack_damage_bonus}')
    if effect.definition.cannot_cast_spells:
        parts.append('cannot cast spells')
    if not parts:
        parts.append('active effect')
    return '; '.join(parts)


def _attack_damage_text(attack) -> str:
    if attack.damage_dice_count > 0 and attack.damage_die_faces > 0:
        base = f'{attack.damage_dice_count}d{attack.damage_die_faces}'
        if attack.damage_bonus > 0:
            base = f'{base}+{attack.damage_bonus}'
        elif attack.damage_bonus < 0:
            base = f'{base}{attack.damage_bonus}'
        return f'{base} {attack.damage_type}'
    return f'{max(1, attack.damage_bonus)} {attack.damage_type}'


def _format_feat_summary(feat) -> str:
    metadata = dict(feat.fixed_metadata)
    spell_list_class_id = metadata.get('spell_list_class_id')
    if spell_list_class_id:
        return f'{feat.feat_name} ({_humanize_label(spell_list_class_id)})'
    return feat.feat_name


def _ability_label(ability: Ability) -> str:
    labels = {
        Ability.STR: 'Strength',
        Ability.DEX: 'Dexterity',
        Ability.CON: 'Constitution',
        Ability.INT: 'Intelligence',
        Ability.WIS: 'Wisdom',
        Ability.CHA: 'Charisma',
    }
    return labels[ability]


def _condition_label(raw_value: str) -> str:
    return raw_value.replace('-', ' ').title()


def _humanize_label(raw_value: str | None) -> str | None:
    if raw_value is None:
        return None
    cleaned = raw_value.replace('_', '-').strip('- ')
    tokens = [token for token in cleaned.split('-') if token]
    if not tokens:
        return raw_value
    words: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if index + 1 < len(tokens) and tokens[index + 1] == 's':
            words.append(f"{token.title()}'s")
            index += 2
            continue
        words.append(token.title())
        index += 1
    return ' '.join(words)


def _avatar_label(name: str) -> str:
    tokens = [token for token in name.replace('-', ' ').split() if token]
    if not tokens:
        return '?'
    return ''.join(token[0].upper() for token in tokens[:2])
def _project_story_chat_entries(session, controller_id: str) -> tuple[WebChatEntryView, ...]:
    role = session.encounter_session.control_runtime.validate_controller(controller_id).role
    owned_actor_ids = set(_owned_actor_ids(session, controller_id))
    entries: list[WebChatEntryView] = []
    for index, event in enumerate(session.state.event_log[-160:]):
        if isinstance(event, StoryActionDeclaredEvent):
            if role != ControllerRole.DM and event.controller_id != controller_id:
                continue
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-action:{index}:{event.controller_id}',
                    speaker=_controller_label(session, event.controller_id),
                    text=event.declaration,
                    category='player',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, StoryModeSpellcastDeclaredEvent):
            if role != ControllerRole.DM and event.actor_id not in owned_actor_ids:
                continue
            actor = session.state.actors.get(event.actor_id)
            spell = actor.spells.get(event.spell_id) if actor is not None else None
            spell_label = spell.name if spell is not None else event.spell_id
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-spell:{index}:{event.actor_id}:{event.spell_id}',
                    speaker=_actor_label(session, event.actor_id),
                    text=f'Casts {spell_label}.',
                    category='player-command',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, StoryModeSpellcastIgnoredEvent):
            if role != ControllerRole.DM and event.actor_id not in owned_actor_ids:
                continue
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-spell-ignored:{index}:{event.actor_id}:{event.spell_id}',
                    speaker='System',
                    text=event.reason,
                    category='system',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, StoryModeSpellcastCausedSuspicionEvent):
            if role != ControllerRole.DM:
                continue
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-spell-suspicion:{index}:{event.witness_id}:{event.spell_id}',
                    speaker='System',
                    text=f'{event.witness_id} reacts as {event.reaction_category.value}.',
                    category='system',
                    visibility='private',
                )
            )
            continue
        if isinstance(event, HostileEscalationTriggeredEvent):
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-hostile-escalation:{index}:{event.decision.hostile_actor_id}',
                    speaker='System',
                    text=event.decision.reason,
                    category='system',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, ReinforcementScheduledEvent):
            visibility = 'public' if event.schedule.public_visible else 'private'
            if visibility == 'private' and role != ControllerRole.DM:
                continue
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-reinforcement:{index}:{event.schedule.reinforcement_id}',
                    speaker='System',
                    text=f"Reinforcement scheduled: {event.schedule.label} in {event.schedule.rounds_until_arrival} rounds.",
                    category='system',
                    visibility=visibility,
                )
            )
            continue
        if isinstance(event, ReinforcementEnteredEvent):
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-reinforcement-entered:{index}:{event.reinforcement_id}',
                    speaker='System',
                    text=f"Reinforcement arrived: {event.reinforcement_id} enters from {event.entry_zone_id}.",
                    category='system',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, CombatStartedFromStorySceneEvent):
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-combat-start:{index}:{event.scene_id}',
                    speaker='System',
                    text=event.reason,
                    category='system',
                    visibility='public',
                )
            )
            continue
        if isinstance(event, StoryTranscriptAppendedEvent):
            for transcript_index, entry in enumerate(event.entries):
                if entry.visibility == StoryTranscriptVisibility.DM_ONLY and role != ControllerRole.DM:
                    continue
                if entry.visibility == StoryTranscriptVisibility.PRIVATE_CONTROLLERS and role != ControllerRole.DM and controller_id not in entry.controller_ids:
                    continue
                entries.append(
                    WebChatEntryView(
                        entry_id=f'story-transcript:{index}:{transcript_index}',
                        speaker=entry.speaker,
                        text=entry.text,
                        category='story',
                        visibility=entry.visibility.value,
                    )
                )
            continue
        if isinstance(event, StoryCheckResolvedEvent):
            if role != ControllerRole.DM and event.actor_id not in owned_actor_ids:
                continue
            entries.append(
                WebChatEntryView(
                    entry_id=f'story-check:{index}:{event.request_id}',
                    speaker=_actor_label(session, event.actor_id),
                    text=_story_check_chat_text(session, event),
                    category='check',
                    visibility='public',
                )
            )
    if session.story_state.runtime_mode == RuntimeMode.COMBAT:
        entries += list(_project_encounter_chat_entries(session.encounter_session, controller_id))
    return tuple(entries[-80:])


def _project_encounter_chat_entries(session, controller_id: str) -> tuple[WebChatEntryView, ...]:
    view = session.view_for_controller(controller_id)
    recent_event_lines = view.projection.recent_events if view.projection is not None else ()
    binding = session.control_runtime.validate_controller(controller_id)
    owned_actor_ids = set(_owned_actor_ids(session, controller_id))
    entries: list[WebChatEntryView] = []
    for index, text in enumerate(recent_event_lines):
        entries.append(
            WebChatEntryView(
                entry_id=f'encounter:{index}',
                speaker='System',
                text=text,
                category='combat',
                visibility='public',
            )
        )
    payload_index = 0
    for payload in session.state.informational_payloads.values():
        share_mode = payload.definition.share_mode.value
        visible = binding.role == ControllerRole.DM
        if not visible:
            if share_mode == 'party-broadcast':
                visible = True
            elif share_mode == 'observer-only':
                if payload.persistent.observer_mode.value == 'all-valid-observers':
                    visible = payload.persistent.source_actor_id in owned_actor_ids
                else:
                    visible = bool(owned_actor_ids.intersection(payload.persistent.observer_actor_ids))
        if not visible:
            continue
        entries.append(
            WebChatEntryView(
                entry_id=f'payload:{payload.payload_id}:{payload_index}',
                speaker='Senses',
                text=f'{payload.definition.title}: {payload.definition.detail}',
                category='system',
                visibility=('private' if share_mode != 'party-broadcast' else 'public'),
            )
        )
        payload_index += 1
    return tuple(entries)

def _recent_story_check_result_projections(session, controller_id: str, role: ControllerRole) -> tuple[WebStoryCheckResultProjection, ...]:
    owned_actor_ids = set(_owned_actor_ids(session, controller_id))
    visible_events: list[StoryCheckResolvedEvent] = []
    for event in session.state.event_log[-20:]:
        if not isinstance(event, StoryCheckResolvedEvent):
            continue
        if role != ControllerRole.DM and event.actor_id not in owned_actor_ids:
            continue
        visible_events.append(event)
    projections: list[WebStoryCheckResultProjection] = []
    for event in visible_events[-5:]:
        projections.append(
            WebStoryCheckResultProjection(
                actor_id=event.actor_id,
                actor_label=_actor_label(session, event.actor_id),
                check_label=_story_check_label(event),
                selected_roll=event.selected_roll,
                total=event.total,
                dc=event.dc,
                success=event.success,
                opposed_actor_label=_actor_label(session, event.interacting_with_actor_id) if event.interacting_with_actor_id is not None else None,
            )
        )
    return tuple(projections)


def _story_check_label(event: StoryCheckResolvedEvent) -> str:
    ability_names = {
        'STR': 'Strength',
        'DEX': 'Dexterity',
        'CON': 'Constitution',
        'INT': 'Intelligence',
        'WIS': 'Wisdom',
        'CHA': 'Charisma',
    }
    ability_value = getattr(event.ability, 'value', str(event.ability))
    ability_label = ability_names.get(ability_value, ability_value)
    if event.skill_name:
        return f'{ability_label} ({event.skill_name})'
    return ability_label


def _actor_label(session, actor_id: str | None) -> str:
    if actor_id is None:
        return ''
    actor = session.state.actors.get(actor_id)
    if actor is not None:
        return actor.name
    pretty = actor_id.replace('-', ' ').replace('_', ' ').strip()
    return pretty.title() if pretty else actor_id



def _story_check_chat_text(session, event: StoryCheckResolvedEvent) -> str:
    outcome = 'success' if event.success else 'failure'
    text = (
        f'{_story_check_label(event)}: die {event.selected_roll}, total {event.total} '
        f'vs DC {event.dc} ({outcome}).'
    )
    opposed_actor_label = _actor_label(session, event.interacting_with_actor_id) if event.interacting_with_actor_id is not None else None
    if opposed_actor_label:
        return f'{text} Opposed interaction: {opposed_actor_label}.'
    return text


def _controller_label(session, controller_id: str) -> str:
    binding = session.encounter_session.control_runtime.controllers.get(controller_id)
    if binding is not None:
        return binding.label
    pretty = controller_id.replace('-', ' ').replace('_', ' ').strip()
    return pretty.title() if pretty else controller_id
def _movement_intent_mode(mode: str) -> MovementIntentMode:
    normalized = mode.strip().lower()
    mapping = {
        'walk': MovementIntentMode.SAME_PLANE,
        'same-plane': MovementIntentMode.SAME_PLANE,
        'elevation': MovementIntentMode.ALLOW_ELEVATION,
        'climb': MovementIntentMode.ALLOW_CLIMB,
        'fly': MovementIntentMode.ALLOW_FLY,
    }
    try:
        return mapping[normalized]
    except KeyError as exc:
        raise EncounterValidationError(f'Unknown movement preview mode: {mode}.') from exc



def _edge_summaries(session, position: GridPosition) -> tuple[str, ...]:
    battlefield = session.state.battlefield
    rules = _kernel_for_session(session).battlefield_rules
    summaries: list[str] = []
    for dx, dy, label in ((1, 0, 'east'), (-1, 0, 'west'), (0, 1, 'south'), (0, -1, 'north')):
        neighbor_xy = GridPosition(position.x + dx, position.y + dy)
        try:
            neighbor_tile = rules.get_tile(battlefield, neighbor_xy.x, neighbor_xy.y)
        except EncounterValidationError:
            continue
        edge = rules.get_edge_transition(battlefield, position, GridPosition(neighbor_xy.x, neighbor_xy.y, neighbor_tile.elevation_ft))
        summaries.append(
            f'{label}: {edge.transition_type.value}; requirement {edge.traversal_requirement.value}; height {edge.height_change_ft} ft'
        )
    return tuple(summaries)

















