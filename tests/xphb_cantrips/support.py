from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from session_server import build_lmop_story_demo_session
from session_server.bootstrap import build_default_encounter_session, build_goblin_ambush_encounter_session
from shared_types.battlefield import BattlefieldFeature, BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, LightingLevel, ObscurementLevel, TraversalMode
from shared_types.encounter_models import GridPosition, RuntimeSpellState
from shared_types.equipment import EnvironmentObjectState, EnvironmentObjectAction
from shared_types.models import slugify
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


def set_actor_position(session, actor_id: str, position: GridPosition) -> None:
    session.state.actors[actor_id].position = position


def find_non_one_counter(session, *, actor_id: str = 'player-1') -> int:
    from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType

    for counter in range(50):
        result = session.command_interface.kernel.d20_engine.resolve(
            D20TestRequest(
                request_id=f'probe:{actor_id}:{counter}',
                test_type=D20TestType.ATTACK,
                actor_id=actor_id,
                flat_modifier=0,
                roll_mode=D20RollMode.NORMAL,
                dc=10,
            ),
            random_counter=counter,
        )
        if result.result.selected_roll != 1:
            return counter
    raise AssertionError(f'Could not find a non-natural-1 counter for {actor_id}.')


class QueueTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict] = []

    def _next_payload(self) -> dict:
        if not self.payloads:
            raise AssertionError('No queued LLM payloads remain for this test.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return [{'type': 'response.completed', 'response': self._next_payload()}]


def grant_spell(session, actor_id: str, *, name: str, source: str = 'XPHB', uses: int | None = None) -> str:
    record = next(spell for spell in session.runtime_services.encounter_catalog.spells.values() if spell.name == name and spell.source == source)
    option_id = slugify(record.name)
    session.state.actors[actor_id].spells[option_id] = RuntimeSpellState(
        option_id=option_id,
        name=record.name,
        source=record.source,
        action_cost=record.action_cost,
        range_ft=record.range_ft,
        remaining_uses=uses,
        level=record.level,
        casting_time_seconds=record.casting_time_seconds,
        perceptibility=record.perceptibility,
        can_cast_as_ritual=record.can_cast_as_ritual,
        ritual_additional_cast_seconds=record.ritual_additional_cast_seconds,
        effect_type=record.effect_type,
        material_component_cost_cp=record.material_component_cost_cp,
        material_component_consumed=record.material_component_consumed,
        material_component_item_keywords=record.material_component_item_keywords,
        material_component_focus_tags=record.material_component_focus_tags,
        max_uses=None,
        concentration=record.concentration,
        capability=record.capability,
        runtime_support=record.runtime_support,
    )
    return option_id


def last_request_text(transport: QueueTransport) -> str:
    if not transport.requests:
        raise AssertionError('No LLM requests were recorded.')
    return transport.requests[-1]['payload']['input'][-1]['content'][0]['text']


def grant_item_by_catalog_match(session, actor_id: str, *, required_tags: tuple[str, ...] = (), name_substrings: tuple[str, ...] = (), min_cost_cp: int = 0, quantity: int = 1) -> str:
    for item_id, item in session.command_interface.kernel.item_catalog.items():
        if item.cost_cp < min_cost_cp:
            continue
        if required_tags and not all(tag in item.tags for tag in required_tags):
            continue
        lowered_name = item.name.casefold()
        if name_substrings and not all(fragment.casefold() in lowered_name or fragment.casefold() in item.record_id.casefold() for fragment in name_substrings):
            continue
        session.state.actors[actor_id].carried_item_counts[item_id] = quantity
        return item_id
    raise AssertionError('Could not locate a matching item in the local catalog.')


def adjudication_success_payload(*, action_summary: str, public_text: str, dm_reason: str = 'The request fits the spell text.') -> dict:
    payload = {
        'action_summary': action_summary,
        'doable': True,
        'adjudication_type': 'automatic_success',
        'reasoning_summary_for_dm': dm_reason,
        'clarification_request': None,
        'check_request': None,
        'save_request': None,
        'contest_request': None,
        'attack_request': None,
        'action_cost_recommendation': {'cost_type': 'none', 'movement_cost_ft': 0, 'reason': 'Resolve the utility cantrip in storytelling mode.'},
        'improvised_objects_to_create': [],
        'terrain_changes_to_create': [],
        'operation_plan': [],
        'on_success': {'public_text': public_text, 'dm_note': '', 'operations': []},
        'on_failure': None,
        'on_partial': None,
        'mode_switch_recommendation': None,
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


def spell_reaction_ignore_payload(*, witness_id: str = 'gundren-rockseeker', public_narration: str = 'The witnesses note the cantrip but let it pass.') -> dict:
    payload = {
        'public_narration': public_narration,
        'witness_reactions': [
            {
                'witness_id': witness_id,
                'reaction_category': 'notices_but_ignores',
                'summary': 'The witness notices the spellcasting but sees no reason to intervene.',
                'public_text': 'The magic draws a glance, then the scene moves on.',
                'private_note': 'No escalation follows.'
            }
        ],
        'scene_note': 'Witnessed minor magic causes no meaningful fallout.',
        'dm_note': 'No escalation from the witnessed cantrip.',
        'escalation': {'recommended': False, 'reason': '', 'mode_switch_decision': None},
    }
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


class EncounterCantripTestCase(unittest.TestCase):
    def build_default_session(self):
        return build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def build_goblin_session(self):
        return build_goblin_ambush_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def grant_spell(self, session, name: str, *, actor_id: str = 'player-1', uses: int | None = None) -> str:
        return grant_spell(session, actor_id, name=name, uses=uses)

    def advance_to_actor(self, session, actor_id: str) -> None:
        guard = 0
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        while session.state.active_actor_id != actor_id:
            guard += 1
            if guard > 30:
                raise AssertionError(f'Could not advance to actor {actor_id}.')
            session.state, _ = session.command_interface.execute(session.state, f'/endturn {session.state.active_actor_id}')

    def find_attack_counter(self, session, *, actor_id: str = 'player-1', want_natural_one: bool = False) -> int:
        from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType

        for counter in range(200):
            result = session.command_interface.kernel.d20_engine.resolve(
                D20TestRequest(
                    request_id=f'probe:{actor_id}:{counter}',
                    test_type=D20TestType.ATTACK,
                    actor_id=actor_id,
                    flat_modifier=0,
                    roll_mode=D20RollMode.NORMAL,
                    dc=10,
                ),
                random_counter=counter,
            )
            if want_natural_one:
                if result.result.selected_roll == 1:
                    return counter
            else:
                if result.result.selected_roll != 1:
                    return counter
        raise AssertionError('Could not find a matching deterministic attack counter in the search window.')

    def latest_damage_events(self, session, *, target_id: str | None = None):
        events = [event for event in session.state.event_log if event.__class__.__name__ == 'DamageAppliedEvent']
        if target_id is not None:
            events = [event for event in events if event.target_id == target_id]
        return events

    def grant_material_item(self, session, *, actor_id: str = 'player-1', required_tags: tuple[str, ...] = (), name_substrings: tuple[str, ...] = (), min_cost_cp: int = 0, quantity: int = 1) -> str:
        return grant_item_by_catalog_match(session, actor_id, required_tags=required_tags, name_substrings=name_substrings, min_cost_cp=min_cost_cp, quantity=quantity)

    def build_door_battlefield(self) -> BattlefieldState:
        def _tile(x: int) -> BattlefieldTile:
            return BattlefieldTile(
                position=GridPosition(x, 0),
                terrain_id='stone-floor',
                elevation_ft=0,
                ceiling_ft=20,
                traversable=True,
                occupiable=True,
                movement_cost_feet_per_5ft=5,
                difficult_terrain=False,
                lightly_obscured=False,
                lighting=LightingLevel.BRIGHT,
                obscurement=ObscurementLevel.NONE,
                blocks_los=False,
                blocks_loe=False,
                base_cover=CoverLevel.NONE,
                supported_modes=(TraversalMode.WALK, TraversalMode.CLIMB, TraversalMode.FLY),
            )

        tiles = {
            GridPosition(0, 0): _tile(0),
            GridPosition(1, 0): _tile(1),
            GridPosition(2, 0): _tile(2),
        }
        return BattlefieldState(
            map_id='mage-hand-door-test',
            name='Mage Hand Door Test',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=3,
                height=1,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=2,
                max_y=0,
            ),
            tiles=dict(tiles),
            base_tiles=dict(tiles),
            features={
                'door-feature': BattlefieldFeature(
                    feature_id='door-feature',
                    feature_type='door',
                    cells=(GridPosition(1, 0, 0),),
                    elevation_ft=0,
                    traversable=False,
                    occupiable=False,
                    blocks_los=True,
                    blocks_loe=True,
                    cover_provided=CoverLevel.HALF,
                )
            },
            object_ids=('door-feature',),
            blocker_ids=('door-feature',),
        )

    def attach_door_object(self, session) -> None:
        session.state.environment_objects['door-1'] = EnvironmentObjectState(
            object_id='door-1',
            feature_id='door-feature',
            label='Stone Door',
            allowed_actions=(EnvironmentObjectAction.OPEN, EnvironmentObjectAction.CLOSE, EnvironmentObjectAction.TOGGLE),
            position_cells=(GridPosition(1, 0, 0),),
            open_state=False,
            closed_traversable=False,
            open_traversable=True,
            closed_occupiable=False,
            open_occupiable=True,
            closed_blocks_los=True,
            open_blocks_los=False,
            closed_blocks_loe=True,
            open_blocks_loe=False,
            closed_cover_provided=CoverLevel.HALF,
            open_cover_provided=CoverLevel.NONE,
        )
        session.command_interface.kernel._apply_environment_object_projection(session.state, 'door-1')


class StoryCantripTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.story-cantrip-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def build_story_session(self, payloads: list[dict]):
        transport = QueueTransport(payloads)
        session = build_lmop_story_demo_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=transport,
        )
        return session, transport

    def grant_spell(self, session, name: str, *, actor_id: str = 'player-1', uses: int | None = None) -> str:
        return grant_spell(session.encounter_session, actor_id, name=name, uses=uses)
