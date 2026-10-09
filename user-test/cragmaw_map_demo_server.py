from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from session_server.bootstrap import build_cragmaw_hideout_map_demo_session
from session_server.web_server import SessionWebServer
from shared_types.battlefield import CoverLevel, LightingLevel
from shared_types.capabilities import ActiveEffectDefinition, CreatedObjectDefinition, DurationAnchor, DurationSpec, EffectDurationType
from shared_types.encounter_events import ActiveEffectStartedEvent, CreatedObjectSpawnedEvent
from shared_types.encounter_models import ActiveEffectState, CreatedObjectState, GridPosition, PersistentEffectFamily, PersistentEffectState, RuntimeSpellState
from shared_types.errors import ContentLoadError, EncounterError
from shared_types.web_ui import WebControllerGrant


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the Cragmaw Hideout map/vision manual demo server.')
    parser.add_argument('--host', default='127.0.0.1', help='Host interface for HTTP and WebSocket listeners.')
    parser.add_argument('--http-port', type=int, default=8001, help='HTTP port for the static frontend. Use 0 for ephemeral.')
    parser.add_argument('--ws-port', type=int, default=8768, help='WebSocket port for realtime updates. Use 0 for ephemeral.')
    parser.add_argument('--base-url', help='Optional override for the 5etools mirror base URL.')
    parser.add_argument('--session-id', default='cragmaw-map-demo', help='Stable session id exposed to the browser.')
    parser.add_argument(
        '--vision-fixture',
        choices=('none', 'light-fog-crate'),
        default='none',
        help='Optional manual-test fixture for dynamic light, heavy obscurement, and a created physical blocker.',
    )
    return parser.parse_args()


def _controller_grants(session, *, session_id: str) -> tuple[WebControllerGrant, ...]:
    grants: list[WebControllerGrant] = []
    for controller_id, binding in session.control_runtime.controllers.items():
        grants.append(
            WebControllerGrant(
                session_id=session_id,
                controller_id=controller_id,
                controller_token=f'{controller_id}-token',
                role=binding.role,
                label=binding.label,
            )
        )
    return tuple(grants)


def _runtime_spell_from_record(option_id: str, record) -> RuntimeSpellState:
    return RuntimeSpellState(
        option_id=option_id,
        name=record.name,
        source=record.source,
        action_cost=record.action_cost,
        range_ft=record.range_ft,
        remaining_uses=None,
        level=record.level,
        casting_time_seconds=record.casting_time_seconds,
        perceptibility=record.perceptibility,
        material_component_cost_cp=record.material_component_cost_cp,
        material_component_consumed=record.material_component_consumed,
        material_component_item_keywords=record.material_component_item_keywords,
        material_component_focus_tags=record.material_component_focus_tags,
        can_cast_as_ritual=record.can_cast_as_ritual,
        ritual_additional_cast_seconds=record.ritual_additional_cast_seconds,
        effect_type=record.effect_type,
        max_uses=None,
        concentration=record.concentration,
        capability=record.capability,
        runtime_support=record.runtime_support,
    )


def _grant_catalog_spell(session, *, actor_id: str, option_id: str, name: str, source: str) -> None:
    record = next(
        (spell for spell in session.runtime_services.encounter_catalog.spells.values() if spell.name == name and spell.source == source),
        None,
    )
    if record is None:
        raise RuntimeError(f'Manual vision fixture requires {name} [{source}] in the encounter catalog.')
    session.state.actors[actor_id].spells[option_id] = _runtime_spell_from_record(option_id, record)


def _grant_manual_darkvision_fixture(session, *, actor_id: str, radius_ft: int) -> None:
    effect_id = f'manual-vision-fixture-darkvision:{actor_id}'
    effect = ActiveEffectState(
        effect_instance_id=effect_id,
        capability_id='manual-vision-fixture-darkvision',
        name='Manual Vision Fixture Darkvision',
        source_actor_id=actor_id,
        target_actor_ids=(actor_id,),
        definition=ActiveEffectDefinition(
            name='Manual Vision Fixture Darkvision',
            duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=4800, anchor=DurationAnchor.SOURCE),
            concentration=False,
            darkvision_radius_ft=radius_ft,
        ),
        remaining_rounds=4800,
    )
    session.command_interface.kernel._apply_event(session.state, ActiveEffectStartedEvent(effect=effect))


def apply_light_fog_crate_fixture(session) -> None:
    battlefield = session.state.battlefield
    battlefield.vision_time_of_day = 'night'
    battlefield.vision_night_radius_ft = 60
    actor = session.state.actors['player-1']

    session.state, _ = session.command_interface.execute(session.state, '/cast player-1 light 13 17')
    actor.action_available = True
    _grant_catalog_spell(session, actor_id='player-1', option_id='fog-cloud', name='Fog Cloud', source='XPHB')
    session.state, _ = session.command_interface.execute(session.state, '/cast player-1 fog-cloud 12 14')
    _grant_manual_darkvision_fixture(session, actor_id='player-1', radius_ft=60)

    for position, tile in tuple(battlefield.tiles.items()):
        if tile.traversable:
            battlefield.tiles[position] = replace(tile, lighting=LightingLevel.DARKNESS)

    definition = CreatedObjectDefinition(
        name='Wooden Crate',
        feature_type='crate',
        blocks_los=True,
        blocks_loe=True,
        cover_provided=CoverLevel.TOTAL,
        semantic_tags=('crate', 'wooden-crate', 'manual-vision-fixture'),
    )
    persistent = PersistentEffectState(
        persistent_effect_id='manual-vision-fixture-crate:persistent',
        family=PersistentEffectFamily.CREATED_OBJECT,
        source_effect_id='manual-vision-fixture-crate:effect',
        source_capability_id='manual-vision-fixture-crate',
        source_actor_id='player-1',
        anchor_position=GridPosition(15, 17, 0),
    )
    created_object = CreatedObjectState(
        persistent=persistent,
        object_id='manual-vision-fixture-crate',
        definition=definition,
        cells=(GridPosition(15, 17, 0),),
        linked_feature_id='manual-vision-fixture-crate:feature',
    )
    session.command_interface.kernel._apply_event(session.state, CreatedObjectSpawnedEvent(created_object=created_object))


def main() -> int:
    args = parse_args()
    try:
        session = build_cragmaw_hideout_map_demo_session(base_url=args.base_url)
        if args.vision_fixture == 'light-fog-crate':
            apply_light_fog_crate_fixture(session)
        server = SessionWebServer(
            session=session,
            session_id=args.session_id,
            controller_grants=_controller_grants(session, session_id=args.session_id),
            http_host=args.host,
            http_port=args.http_port,
            websocket_host=args.host,
            websocket_port=args.ws_port,
            automation_api_enabled=True,
            mirror_base_url=args.base_url,
        )
        server.serve_forever()
        return 0
    except (ContentLoadError, EncounterError, RuntimeError, ValueError) as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
