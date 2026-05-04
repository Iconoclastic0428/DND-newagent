from __future__ import annotations

import copy
import http.client
import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

from dm_agent.memory import DmMemoryWriter
from session_server.bootstrap import (
    build_default_character_record,
    build_default_encounter_session,
    build_goblin_ambush_encounter_session,
    build_lmop_story_demo_session_from_records,
)
from session_server.storytelling_session import StorytellingSession
from session_server.web_server import SessionWebServer
from shared_types.capabilities import ActiveEffectDefinition, CapabilityDefinition, CapabilityKind, CompositeEffect, DurationSpec, EffectDurationType, TargetAffinity, TargetSelectionKind, TargetingSpec
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.encounter_control import ControllerPrompt, ControllerRole, PromptOption, PromptRecipient
from shared_types.encounter_events import StoryActionDeclaredEvent, StoryCheckResolvedEvent
from shared_types.encounter_models import ActiveEffectState, DyingState, DyingStateStatus, RuntimeCapabilityState
from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.models import Ability
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL
from tests.test_storytelling_session import QueueTransport
from shared_types.storytelling import RuntimeMode, StoryCheckRequestState, StoryRuntimeState
from shared_types.web_ui import WebControllerGrant

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from story_demo_system_server import build_full_story_demo_manual_session
from web_story_demo_live_runner import run_live_web_story_script


class SessionWebServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._servers: list[SessionWebServer] = []
        self._temp_dirs: list[Path] = []

    def tearDown(self) -> None:
        for server in reversed(self._servers):
            server.shutdown()
        for temp_dir in reversed(self._temp_dirs):
            shutil.rmtree(temp_dir, ignore_errors=True)

    def _start_server(self, session, *, session_id: str = 'test-session', automation_api_enabled: bool = False) -> SessionWebServer:
        story_session = getattr(session, 'story_session', None)
        if story_session is None and hasattr(session, 'validate_controller') and hasattr(session, 'view_for_controller') and not hasattr(session, 'state'):
            controller_ids = ('dm', 'player-1-controller', 'player-2-controller', 'player-3-controller', 'player-4-controller')
            grants = tuple(
                WebControllerGrant(
                    session_id=session_id,
                    controller_id=controller_id,
                    controller_token=f'{controller_id}-token',
                    role=session.validate_controller(controller_id).role,
                    label=session.validate_controller(controller_id).label,
                )
                for controller_id in controller_ids
            )
        else:
            if hasattr(session, 'encounter_session'):
                control_runtime = session.encounter_session.control_runtime
            else:
                control_runtime = session.control_runtime
            grants = tuple(
                WebControllerGrant(
                    session_id=session_id,
                    controller_id=controller_id,
                    controller_token=f'{controller_id}-token',
                    role=binding.role,
                    label=binding.label,
                )
                for controller_id, binding in control_runtime.controllers.items()
            )
        server = SessionWebServer(
            session=session,
            session_id=session_id,
            controller_grants=grants,
            http_host='127.0.0.1',
            http_port=0,
            websocket_host='127.0.0.1',
            websocket_port=0,
            automation_api_enabled=automation_api_enabled,
        )
        server.start()
        self._servers.append(server)
        return server

    def _request(self, server: SessionWebServer, path: str) -> tuple[int, str]:
        status, _headers, body = self._request_with_headers(server, path)
        return status, body

    def _request_with_headers(self, server: SessionWebServer, path: str) -> tuple[int, dict[str, str], str]:
        conn = http.client.HTTPConnection('127.0.0.1', server.http_port, timeout=10)
        conn.request('GET', path)
        response = conn.getresponse()
        body = response.read().decode('utf-8')
        headers = {key.lower(): value for key, value in response.getheaders()}
        status = response.status
        conn.close()
        return status, headers, body

    def _post_json(self, server: SessionWebServer, path: str, payload: dict[str, object]) -> tuple[int, dict[str, str], str]:
        body = json.dumps(payload)
        conn = http.client.HTTPConnection('127.0.0.1', server.http_port, timeout=10)
        conn.request('POST', path, body=body, headers={'Content-Type': 'application/json; charset=utf-8'})
        response = conn.getresponse()
        response_body = response.read().decode('utf-8')
        headers = {key.lower(): value for key, value in response.getheaders()}
        status = response.status
        conn.close()
        return status, headers, response_body

    def _connect_and_join(self, server: SessionWebServer, controller_id: str):
        ws = connect(f'ws://127.0.0.1:{server.websocket_port}')
        ws.send(
            json.dumps(
                {
                    'type': 'join',
                    'session_id': server.session_id,
                    'controller_id': controller_id,
                    'controller_token': f'{controller_id}-token',
                }
            )
        )
        joined = json.loads(ws.recv(timeout=5))
        view = json.loads(ws.recv(timeout=5))
        prompt = None
        try:
            maybe = json.loads(ws.recv(timeout=0.2))
            if maybe.get('type') == 'prompt':
                prompt = maybe
            else:
                raise AssertionError(f'Unexpected websocket message: {maybe}')
        except TimeoutError:
            prompt = None
        return ws, joined, view, prompt

    def _recv_until(self, ws, expected_type: str, *, timeout: float = 5.0):
        while True:
            message = json.loads(ws.recv(timeout=timeout))
            if message.get('type') == expected_type:
                return message

    def _build_story_session(self) -> StorytellingSession:
        encounter_session = build_default_encounter_session()
        memory_root = Path('tests/.tmp/web-server/story-memory')
        shutil.rmtree(memory_root, ignore_errors=True)
        memory_root.mkdir(parents=True, exist_ok=True)
        self._temp_dirs.append(memory_root)
        campaign_root = Path('campaigns/lmop')
        memory_writer = DmMemoryWriter(memory_root, campaign_id='lmop')
        story_state = StoryRuntimeState(
            campaign_id='lmop',
            current_scene_id='scene-waterdeep-gundren-briefing',
            runtime_mode=RuntimeMode.STORYTELLING,
            current_chapter_id='chapter-01',
            canonical_location_id='waterdeep',
            open_loops=('Hear Gundren out.',),
            current_party_goals=('Take the job.',),
            recent_summary='Gundren is making the offer.',
            pending_check=StoryCheckRequestState(
                request_id='story-check-player-1',
                controller_id='player-1-controller',
                actor_id='player-1',
                prompt="Roll Wisdom (Insight) to gauge Gundren's urgency.",
                reason='Sizing up Gundren before accepting the job.',
                check_request=CheckRequest(
                    context=ResolutionContext(
                        effect_id='story-check-player-1',
                        source_actor_id=None,
                        target_actor_id='player-1',
                        reason='Sizing up Gundren before accepting the job.',
                    ),
                    ability=Ability.WIS,
                    dc=12,
                    skill_name='Insight',
                    interacting_with_actor_id='monster-skeleton-1',
                ),
            ),
        )
        return StorytellingSession(
            encounter_session=encounter_session,
            story_state=story_state,
            campaign_root=campaign_root,
            memory_writer=memory_writer,
            dm_runtime=None,
        )

    def _build_full_story_demo_session(self):
        temp_root = REPO_ROOT / '.web-server-demo-tests' / uuid4().hex
        temp_root.mkdir(parents=True, exist_ok=False)
        self._temp_dirs.append(temp_root)
        env_path = temp_root / '.env'
        env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        return build_full_story_demo_manual_session(base_url=LOCAL_MIRROR_BASE_URL, env_path=env_path)


    def _timing_order_prompt(self, *, controller_id: str = 'player-1-controller', label: str = 'Player 1', actor_id: str = 'player-1') -> ControllerPrompt:
        return ControllerPrompt(
            prompt_id=f'timing:{actor_id}:start-of-turn',
            prompt_kind='timing-order',
            prompt='Choose the next start-of-turn effect to resolve.',
            recipients=(
                PromptRecipient(
                    controller_id=controller_id,
                    role=ControllerRole.PLAYER if controller_id != 'dm' else ControllerRole.DM,
                    label=label,
                    actor_ids=(actor_id,),
                ),
            ),
            options=(
                PromptOption(option_id='effect-expire', label='Bless expires', detail='active-effect-expire', actor_id=actor_id),
                PromptOption(option_id='effect-trigger', label='Regeneration trigger', detail='active-effect-trigger', actor_id=actor_id),
            ),
        )
    def _build_story_demo_story_session(self):
        temp_root = REPO_ROOT / '.web-server-story-card-tests' / uuid4().hex
        temp_root.mkdir(parents=True, exist_ok=False)
        self._temp_dirs.append(temp_root)
        env_path = temp_root / '.env'
        env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        base_record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        player_records = []
        for index in range(1, 5):
            record = copy.deepcopy(base_record)
            record.record_id = f'level-1-character-p{index}'
            player_records.append(record)
        return build_lmop_story_demo_session_from_records(
            player_records=tuple(player_records),
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=env_path,
        )

    def test_config_and_static_assets_do_not_leak_llm_secrets(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        status, config_headers, config_body = self._request_with_headers(server, '/config.json')
        self.assertEqual(status, 200)
        self.assertEqual(config_headers.get('cache-control'), 'no-store, max-age=0')
        config = json.loads(config_body)
        self.assertEqual(config['sessionId'], server.session_id)
        self.assertTrue(config['portalPages'])
        self.assertNotIn('OPENAI_API_KEY', config_body)
        self.assertNotIn('OPENAI_BASE_URL', config_body)
        self.assertNotIn('OPENAI_RESPONSES_MODEL', config_body)

        status, app_headers, app_body = self._request_with_headers(server, '/app.js')
        self.assertEqual(status, 200)
        self.assertEqual(app_headers.get('cache-control'), 'no-store, max-age=0')
        self.assertNotIn('OPENAI_API_KEY', app_body)
        self.assertNotIn('OPENAI_BASE_URL', app_body)
        self.assertNotIn('OPENAI_RESPONSES_MODEL', app_body)

    def test_websocket_join_separates_dm_and_player_views(self) -> None:
        session = build_goblin_ambush_encounter_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        server = self._start_server(session)

        player_ws, player_joined, player_view_message, _ = self._connect_and_join(server, 'player-1-controller')
        dm_ws, dm_joined, dm_view_message, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        self.assertEqual(player_joined['type'], 'joined')
        self.assertEqual(dm_joined['type'], 'joined')
        self.assertEqual(player_view_message['type'], 'view')
        self.assertEqual(dm_view_message['type'], 'view')

        player_view = player_view_message['view']
        dm_view = dm_view_message['view']
        self.assertEqual(player_view['runtime_mode'], 'combat')
        self.assertEqual(dm_view['runtime_mode'], 'combat')
        self.assertTrue(any(group['group_id'] == 'actions' for group in player_view['action_groups']))
        self.assertEqual(dm_view['action_groups'], [])

        player_tokens = {token['actor_id']: token for token in player_view['map']['tokens']}
        dm_tokens = {token['actor_id']: token for token in dm_view['map']['tokens']}
        self.assertIsNone(player_tokens['monster-skeleton-1']['hit_points'])
        self.assertIsNotNone(dm_tokens['monster-skeleton-1']['hit_points'])
        self.assertTrue(player_tokens['player-1']['is_owner'])

    def test_inspect_preview_and_move_proposal_broadcast_authoritative_results(self) -> None:
        session = build_goblin_ambush_encounter_session()
        session.system_execute('/encounter start')
        session.execute_for_controller('dm', '/endturn monster-skeleton-1')
        session.execute_for_controller('dm', '/endturn monster-mage-1')
        server = self._start_server(session)

        player_ws, _joined, _view_message, _ = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, _dm_view_message, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        player_ws.send(json.dumps({'type': 'inspect_cell', 'x': 15, 'y': 16, 'z': 0}))
        inspection = self._recv_until(player_ws, 'inspection')
        self.assertEqual(inspection['inspection']['position'], {'x': 15, 'y': 16, 'z': 0})
        self.assertIn('terrain_id', inspection['inspection'])
        self.assertIn('traversal_views', inspection['inspection'])

        player_ws.send(json.dumps({'type': 'preview_move', 'x': 15, 'y': 16, 'z': 0, 'mode': 'walk'}))
        preview = self._recv_until(player_ws, 'path_preview')
        self.assertEqual(preview['preview']['actor_id'], 'player-1')
        self.assertTrue(preview['preview']['outcome'].startswith('reachable_'))

        player_ws.send(json.dumps({'type': 'move_proposal', 'x': 15, 'y': 16, 'z': 0, 'mode': 'walk'}))
        player_view = self._recv_until(player_ws, 'view')['view']
        dm_view = self._recv_until(dm_ws, 'view')['view']
        player_token = next(token for token in player_view['map']['tokens'] if token['actor_id'] == 'player-1')
        dm_token = next(token for token in dm_view['map']['tokens'] if token['actor_id'] == 'player-1')
        self.assertEqual(player_token['position'], {'x': 15, 'y': 16, 'z': 0})
        self.assertEqual(dm_token['position'], {'x': 15, 'y': 16, 'z': 0})

    def test_timing_order_prompt_projects_over_websocket_and_normalizes_single_selection(self) -> None:
        session = build_default_encounter_session()
        prompt = self._timing_order_prompt()
        submitted: list[tuple[str, object]] = []
        session.prompt_for_controller = lambda controller_id: prompt if controller_id == 'player-1-controller' else None
        session.respond_to_prompt = lambda controller_id, option_ids: submitted.append((controller_id, option_ids))
        server = self._start_server(session)

        player_ws, _joined, view_message, prompt_message = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, _dm_view, dm_prompt = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        self.assertIsNone(dm_prompt)
        self.assertEqual(view_message['view']['prompt']['prompt_kind'], 'timing-order')
        self.assertIsNotNone(prompt_message)
        self.assertEqual(prompt_message['prompt']['prompt_kind'], 'timing-order')
        self.assertEqual([option['option_id'] for option in prompt_message['prompt']['options']], ['effect-expire', 'effect-trigger'])

        player_ws.send(json.dumps({'type': 'reaction', 'option_ids': ['effect-expire', 'effect-trigger']}))
        error = self._recv_until(player_ws, 'error')
        self.assertIn('Timing-order prompt responses may choose only one option.', error['message'])
        self.assertEqual(submitted, [])

        player_ws.send(json.dumps({'type': 'reaction', 'option_ids': ['effect-trigger']}))
        self._recv_until(player_ws, 'view')
        self.assertEqual(submitted, [('player-1-controller', 'effect-trigger')])

    def test_automation_api_normalizes_prompt_response_and_updates_prompt_state(self) -> None:
        session = build_default_encounter_session()
        prompt = self._timing_order_prompt()
        submitted: list[tuple[str, object]] = []
        prompt_open = {'active': True}

        def _prompt_for_controller(controller_id: str):
            if controller_id != 'player-1-controller' or not prompt_open['active']:
                return None
            return prompt

        def _respond_to_prompt(controller_id: str, option_ids: object) -> None:
            submitted.append((controller_id, option_ids))
            prompt_open['active'] = False

        session.prompt_for_controller = _prompt_for_controller
        session.respond_to_prompt = _respond_to_prompt
        server = self._start_server(session, automation_api_enabled=True)

        status, _headers, body = self._post_json(
            server,
            '/automation/prompt-response',
            {'controller_id': 'player-1-controller', 'option_ids': ['effect-trigger']},
        )
        self.assertEqual(status, 200)
        payload = json.loads(body)
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['option_ids'], 'effect-trigger')
        self.assertIsNone(payload['prompt'])
        self.assertEqual(submitted, [('player-1-controller', 'effect-trigger')])

    def test_story_prompt_and_check_resolution_flow_over_websocket(self) -> None:
        session = self._build_story_session()
        server = self._start_server(session)

        player_ws, _joined, view_message, prompt_message = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, _dm_view, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        self.assertEqual(view_message['view']['runtime_mode'], 'storytelling')
        self.assertIsNotNone(prompt_message)
        self.assertEqual(prompt_message['prompt']['prompt_kind'], 'story-check')
        self.assertIn('Wisdom (Insight)', prompt_message['prompt']['text'])

        player_ws.send(json.dumps({'type': 'command', 'text': '/check'}))
        echo_message = self._recv_until(player_ws, 'echo')
        self.assertEqual(echo_message['entry']['category'], 'check')
        self.assertIn('Resolving the pending check', echo_message['entry']['text'])
        player_view = self._recv_until(player_ws, 'view')['view']
        dm_view = self._recv_until(dm_ws, 'view')['view']
        self.assertTrue(any('Recent check results:' in line for line in player_view['summary_lines']))
        self.assertTrue(any('Recent check results:' in line for line in dm_view['summary_lines']))
        self.assertTrue(any(entry['category'] == 'check' for entry in player_view['chat_entries']))

    def test_story_chat_projection_includes_player_declarations_and_checks(self) -> None:
        session = self._build_story_session()
        session.state.event_log.append(
            StoryActionDeclaredEvent(
                controller_id='player-1-controller',
                actor_id='player-1',
                declaration='I ask Gundren what he is hiding from us.',
            )
        )
        session.state.event_log.append(
            StoryCheckResolvedEvent(
                request_id='story-check-player-1',
                actor_id='player-1',
                scene_id='scene-waterdeep-gundren-briefing',
                ability=Ability.WIS,
                skill_name='Insight',
                dc=12,
                selected_roll=14,
                total=17,
                success=True,
                interacting_with_actor_id='monster-skeleton-1',
            )
        )
        server = self._start_server(session)

        player_ws, _joined, player_view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, dm_view_message, _dm_prompt = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        player_entries = player_view_message['view']['chat_entries']
        dm_entries = dm_view_message['view']['chat_entries']
        self.assertTrue(any(entry['category'] == 'player' and 'I ask Gundren what he is hiding from us.' in entry['text'] for entry in player_entries))
        self.assertTrue(any(entry['category'] == 'check' and 'Wisdom (Insight): die 14, total 17 vs DC 12 (success).' in entry['text'] for entry in player_entries))
        self.assertTrue(any(entry['category'] == 'player' for entry in dm_entries))
        self.assertTrue(any(entry['category'] == 'check' for entry in dm_entries))


    def test_story_spellcast_updates_story_chat_and_spell_uses_over_websocket(self) -> None:
        session = self._build_story_demo_story_session()
        session.dm_runtime.client.transport = QueueTransport(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren notices the healing spell but reads it as practical help instead of a threat.",'
                        '"witness_reactions":['
                        '{"witness_id":"gundren-rockseeker","reaction_category":"notices_but_ignores","summary":"Gundren tolerates the healing magic.","public_text":"Keep the magic practical and we will have no quarrel.","private_note":"He stays focused on the job offer."}'
                        '],'
                        '"scene_note":"Witnessed healing magic does not escalate the briefing.",'
                        '"dm_note":"No escalation from the witnessed cure spell.",'
                        '"escalation":{"recommended":false,"reason":"","mode_switch_decision":null}'
                        '}'
                    )
                }
            ]
        )
        server = self._start_server(session)

        player_ws, _joined, _view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        player_ws.send(json.dumps({'type': 'command', 'text': '/cast player-1 cure-wounds player-1'}))
        self._recv_until(player_ws, 'echo')
        view = self._recv_until(player_ws, 'view')['view']
        chat_entries = view['chat_entries']
        self.assertTrue(any(entry['text'] == 'Casts Cure Wounds.' for entry in chat_entries))
        self.assertTrue(any('Gundren notices the healing spell' in entry['text'] for entry in chat_entries))
        card = next(item for item in view['character_cards'] if item['actor_id'] == 'player-1')
        spells = {spell['spell_id']: spell for spell in card['spells']}
        self.assertEqual(spells['cure-wounds']['remaining_uses'], 0)

    def test_full_story_demo_wrapper_projects_character_creation_and_portals(self) -> None:
        session = self._build_full_story_demo_session()
        server = self._start_server(session, session_id='lmop-web-demo')

        status, config_body = self._request(server, '/config.json')
        self.assertEqual(status, 200)
        config = json.loads(config_body)
        portal_pages = {item['controllerId']: item for item in config['portalPages']}
        self.assertEqual(portal_pages['player-1-controller']['path'], '/?portal=player-1-controller&autoconnect=1')
        self.assertEqual(portal_pages['player-4-controller']['path'], '/?portal=player-4-controller&autoconnect=1')
        self.assertEqual(portal_pages['dm']['path'], '/?portal=dm&autoconnect=1')

        player_ws, _joined, player_view_message, prompt = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, dm_view_message, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        self.assertIsNone(prompt)
        player_view = player_view_message['view']
        dm_view = dm_view_message['view']
        self.assertEqual(player_view['runtime_mode'], 'character-creation')
        self.assertEqual(dm_view['runtime_mode'], 'character-creation')
        self.assertIsNone(player_view['map'])
        self.assertTrue(any('Demo phase: create your character' in line for line in player_view['summary_lines']))
        self.assertTrue(any('Demo phase: waiting for four player characters' in line for line in dm_view['summary_lines']))
        create_group = next(group for group in player_view['action_groups'] if group['group_id'] == 'create-flow')
        begin_choice = create_group['choices'][0]
        self.assertEqual(begin_choice['command_insert_text'], '/create begin')
        self.assertEqual(dm_view['action_groups'], [])



    def test_character_creation_action_groups_include_full_create_command_helpers(self) -> None:
        session = self._build_full_story_demo_session()
        server = self._start_server(session, session_id='lmop-create-command-helper-demo')

        player_ws, _joined, _player_view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        player_ws.send(json.dumps({'type': 'command', 'text': '/create begin'}))
        species_view = self._recv_until(player_ws, 'view')['view']
        species_group = next(group for group in species_view['action_groups'] if group['group_id'] == 'species')
        human_choice = next(choice for choice in species_group['choices'] if choice['option_id'] == 'human')
        self.assertEqual(human_choice['command_insert_text'], '/create choose species human')
        self.assertIsNone(human_choice['command_prefix'])

        player_ws.send(json.dumps({'type': 'command', 'text': '/create choose species human'}))
        self._recv_until(player_ws, 'view')
        player_ws.send(json.dumps({'type': 'command', 'text': '/create choose class bard'}))
        skill_view = self._recv_until(player_ws, 'view')['view']
        skill_group = next(group for group in skill_view['action_groups'] if group['group_id'] == 'class-skills')
        first_skill_choice = skill_group['choices'][0]
        self.assertTrue(first_skill_choice['command_insert_text'].startswith('/create choose class-skills '))
        self.assertEqual(first_skill_choice['command_prefix'], '/create choose class-skills')

    def test_storytelling_character_card_shows_only_owned_player_card_and_dm_can_inspect_all(self) -> None:
        session = self._build_story_demo_story_session()
        server = self._start_server(session, session_id='lmop-character-card-demo')

        player_ws, _joined, player_view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, dm_view_message, _dm_prompt = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        player_cards = player_view_message['view']['character_cards']
        dm_cards = dm_view_message['view']['character_cards']
        self.assertEqual(player_view_message['view']['runtime_mode'], 'storytelling')
        self.assertEqual(len(player_cards), 1)
        self.assertEqual(player_cards[0]['actor_id'], 'player-1')
        self.assertEqual(player_cards[0]['class_name'], 'Wizard')
        self.assertEqual(player_cards[0]['species_name'], 'Aasimar')
        self.assertEqual(player_cards[0]['background_name'], 'Acolyte')
        self.assertEqual(player_cards[0]['spellcasting_ability'], 'Intelligence')
        self.assertTrue(any(spell['name'] == 'Fire Bolt' for spell in player_cards[0]['cantrips']))
        self.assertTrue(any(spell['name'] == 'Magic Missile' for spell in player_cards[0]['spells']))
        self.assertEqual({card['actor_id'] for card in dm_cards}, {'player-1', 'player-2', 'player-3', 'player-4'})

    def test_character_card_surfaces_dying_state_to_owner_and_dm(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        player_ws, _joined, _view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, _dm_view_message, _dm_prompt = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        with server._state_lock:
            actor = session.state.actors['player-1']
            actor.current_hit_points = 0
            actor.dying_state = DyingState(
                status=DyingStateStatus.AT_0_HP_UNCONSCIOUS,
                death_save_successes=1,
                death_save_failures=2,
            )
            actor.condition_instances = (
                ConditionInstance(instance_id='zero-hit-points-unconscious:player-1', condition_type=ConditionType.UNCONSCIOUS, source_label='zero-hit-points'),
            )
            server._broadcast_updates()

        player_card = self._recv_until(player_ws, 'view')['view']['character_cards'][0]
        dm_card = self._recv_until(dm_ws, 'view')['view']['character_cards'][0]
        self.assertEqual(player_card['dying_status'], 'at-0-hp-unconscious')
        self.assertEqual(player_card['death_save_successes'], 1)
        self.assertEqual(player_card['death_save_failures'], 2)
        self.assertIn('Unconscious', player_card['conditions'])
        self.assertEqual(dm_card['dying_status'], 'at-0-hp-unconscious')
        self.assertEqual(dm_card['death_save_successes'], 1)
        self.assertEqual(dm_card['death_save_failures'], 2)

    def test_character_card_updates_over_websocket_after_authoritative_state_change(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        player_ws, _joined, _view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        with server._state_lock:
            actor = session.state.actors['player-1']
            actor.current_hit_points = 3
            actor.temp_hit_points = 2
            actor.remaining_movement_ft = 10
            actor.action_available = False
            actor.bonus_action_available = False
            actor.reaction_available = True
            actor.condition_instances = (
                ConditionInstance(instance_id='prone-1', condition_type=ConditionType.PRONE, source_label='test'),
            )
            actor.concentrating_effect_id = 'shield-of-faith-test'
            session.state.active_effects['shield-of-faith-test'] = ActiveEffectState(
                effect_instance_id='shield-of-faith-test',
                capability_id='shield-of-faith',
                name='Shield of Faith',
                source_actor_id='player-1',
                target_actor_ids=('player-1',),
                definition=ActiveEffectDefinition(
                    name='Shield of Faith',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10),
                    concentration=True,
                    armor_class_bonus=2,
                ),
                remaining_rounds=9,
            )
            actor.capabilities['test-resource'] = RuntimeCapabilityState(
                option_id='test-resource',
                name='Second Wind',
                source='XPHB',
                kind=CapabilityKind.CLASS_FEATURE,
                action_cost='bonus',
                remaining_uses=1,
                capability=CapabilityDefinition(
                    capability_id='test-resource',
                    name='Second Wind',
                    kind=CapabilityKind.CLASS_FEATURE,
                    source='XPHB',
                    action_cost='bonus',
                    targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
                    effect=CompositeEffect(effects=()),
                ),
            )
            server._broadcast_updates()

        updated_view = self._recv_until(player_ws, 'view')['view']
        card = updated_view['character_cards'][0]
        self.assertEqual(card['current_hit_points'], 3)
        self.assertEqual(card['temp_hit_points'], 2)
        self.assertEqual(card['movement_remaining_ft'], 10)
        self.assertFalse(card['action_available'])
        self.assertFalse(card['bonus_action_available'])
        self.assertIn('Prone', card['conditions'])
        self.assertEqual(card['concentration_effect_name'], 'Shield of Faith')
        self.assertTrue(any(effect['name'] == 'Shield of Faith' for effect in card['effects']))
        self.assertTrue(any(resource['label'] == 'Second Wind' and resource['remaining_uses'] == 1 for resource in card['resources']))


    def test_character_card_projects_hit_dice_and_spell_slots(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        player_ws, _joined, view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        card = view_message['view']['character_cards'][0]
        self.assertTrue(any(resource['label'].startswith('Hit Dice') for resource in card['resources']))
        self.assertTrue(any(resource['label'] == 'Level 1 Spell Slots' for resource in card['resources']))

    def test_character_card_rest_resources_update_over_websocket(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        player_ws, _joined, _view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        with server._state_lock:
            actor = session.state.actors['player-1']
            actor.remaining_hit_dice = 0
            if 'spell-slot-1' in actor.resource_pools:
                actor.resource_pools['spell-slot-1'].current = 0
            server._broadcast_updates()

        updated_view = self._recv_until(player_ws, 'view')['view']
        card = updated_view['character_cards'][0]
        self.assertTrue(any(resource['label'].startswith('Hit Dice') and resource['remaining_uses'] == 0 for resource in card['resources']))
        self.assertTrue(any(resource['label'] == 'Level 1 Spell Slots' and resource['remaining_uses'] == 0 for resource in card['resources']))

    def test_story_websocket_projects_travel_map_with_player_dm_visibility_split(self) -> None:
        session = self._build_story_demo_story_session()
        server = self._start_server(session)

        player_ws, _player_joined, player_view_message, _ = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, dm_view_message, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        player_view = player_view_message['view']
        dm_view = dm_view_message['view']
        self.assertEqual(player_view['runtime_mode'], 'storytelling')
        self.assertIsNone(player_view['map'])
        self.assertIsNotNone(player_view['travel'])
        self.assertGreater(len(dm_view['travel']['hexes']), len(player_view['travel']['hexes']))
        player_landmarks = {landmark['landmark_id'] for landmark in player_view['travel']['landmarks']}
        dm_landmarks = {landmark['landmark_id'] for landmark in dm_view['travel']['landmarks']}
        self.assertNotIn('ambush-horses', player_landmarks)
        self.assertIn('ambush-horses', dm_landmarks)
        self.assertEqual(player_view['travel']['current_party_coord'], {'q': 0, 'r': 0})

    def test_story_websocket_supports_travel_inspection_route_preview_and_advancement(self) -> None:
        session = self._build_story_demo_story_session()
        server = self._start_server(session)

        player_ws, _player_joined, _player_view_message, _ = self._connect_and_join(server, 'player-1-controller')
        dm_ws, _dm_joined, _dm_view_message, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(player_ws.close)
        self.addCleanup(dm_ws.close)

        player_ws.send(json.dumps({'type': 'inspect_travel_hex', 'q': 1, 'r': 0}))
        inspection = self._recv_until(player_ws, 'inspection')
        self.assertEqual(inspection['inspection']['coord'], {'q': 1, 'r': 0})
        self.assertEqual(inspection['inspection']['terrain_id'], 'road')

        player_ws.send(json.dumps({'type': 'travel_route_preview', 'q': 6, 'r': 0}))
        preview = self._recv_until(player_ws, 'path_preview')
        self.assertEqual(preview['preview']['destination'], {'q': 6, 'r': 0})
        self.assertEqual(preview['preview']['destination_label'], 'Phandalin')

        player_ws.send(json.dumps({'type': 'travel_plan_route', 'q': 6, 'r': 0}))
        planned_view = self._recv_until(player_ws, 'view')['view']
        self.assertEqual(planned_view['travel']['status'], 'route-planned')
        self.assertEqual(planned_view['travel']['planned_route']['destination_label'], 'Phandalin')
        self._recv_until(dm_ws, 'view')

        player_ws.send(json.dumps({'type': 'travel_advance', 'steps': 5}))
        player_view = self._recv_until(player_ws, 'view')['view']
        dm_view = self._recv_until(dm_ws, 'view')['view']
        self.assertEqual(player_view['travel']['status'], 'interrupted')
        self.assertEqual(player_view['travel']['current_party_coord'], {'q': 5, 'r': 0})
        self.assertIsNotNone(player_view['travel']['pending_hook'])
        self.assertIsNone(player_view['travel']['pending_hook']['battlefield_map_id'])
        self.assertEqual(dm_view['travel']['pending_hook']['battlefield_map_id'], 'goblin-ambush-triboar-trail')
        self.assertEqual(player_view['current_scene_id'], 'scene-triboar-goblin-ambush')


    def test_same_controller_reconnect_replaces_old_websocket(self) -> None:
        session = build_default_encounter_session()
        server = self._start_server(session)

        first_ws, _joined, _view, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(first_ws.close)
        second_ws, second_joined, _second_view, _ = self._connect_and_join(server, 'dm')
        self.addCleanup(second_ws.close)

        self.assertEqual(second_joined['controllerId'], 'dm')
        with self.assertRaises(ConnectionClosed):
            first_ws.recv(timeout=1)

    def test_automation_api_projects_state_and_injects_browser_visible_input(self) -> None:
        session = self._build_full_story_demo_session()
        server = self._start_server(session, session_id='lmop-web-demo', automation_api_enabled=True)

        player_ws, _joined, _view_message, _prompt = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)

        status, _headers, state_body = self._request_with_headers(server, '/automation/state?controller_id=player-1-controller')
        self.assertEqual(status, 200)
        state_payload = json.loads(state_body)
        self.assertTrue(state_payload['ok'])
        self.assertEqual(state_payload['view']['runtime_mode'], 'character-creation')

        status, _headers, input_body = self._post_json(
            server,
            '/automation/input',
            {'controller_id': 'player-1-controller', 'text': '/create begin'},
        )
        self.assertEqual(status, 200)
        input_payload = json.loads(input_body)
        self.assertTrue(input_payload['ok'])
        self.assertEqual(input_payload['view']['runtime_mode'], 'character-creation')

        echo_message = self._recv_until(player_ws, 'echo')
        self.assertEqual(echo_message['entry']['text'], '/create begin')
        player_view = self._recv_until(player_ws, 'view')['view']
        species_group = next(group for group in player_view['action_groups'] if group['group_id'] == 'species')
        self.assertTrue(any(choice['option_id'] == 'human' for choice in species_group['choices']))

    def test_live_web_runner_executes_prompt_aware_script_against_running_server(self) -> None:
        session = self._build_story_session()
        server = self._start_server(session, automation_api_enabled=True)

        player_ws, _joined, _view_message, prompt_message = self._connect_and_join(server, 'player-1-controller')
        self.addCleanup(player_ws.close)
        self.assertIsNotNone(prompt_message)
        self.assertEqual(prompt_message['prompt']['prompt_kind'], 'story-check')

        script_path = self._temp_dirs[-1] / 'live-web-script.json'
        script_path.write_text(
            json.dumps(
                {
                    'script_id': 'prompt-aware-check',
                    'result_controller_id': 'player-1-controller',
                    'steps': [
                        {
                            'type': 'wait_for_prompt',
                            'controller_id': 'player-1-controller',
                            'prompt_kind': 'story-check',
                            'contains': ['Wisdom (Insight)'],
                            'timeout_seconds': 2.0,
                        },
                        {
                            'type': 'command_if_prompt',
                            'controller_id': 'player-1-controller',
                            'prompt_kind': 'story-check',
                            'input': '/check',
                        },
                        {
                            'type': 'wait_for_view',
                            'controller_id': 'player-1-controller',
                            'runtime_mode': 'storytelling',
                            'contains': ['Recent check results:'],
                            'timeout_seconds': 2.0,
                        },
                    ],
                }
            ),
            encoding='utf-8',
        )

        result = run_live_web_story_script(script_path, base_url=f'http://127.0.0.1:{server.http_port}')
        self.assertEqual(result.script_id, 'prompt-aware-check')
        self.assertEqual(result.commands_sent, 1)
        self.assertEqual(result.skipped_steps, 0)
        self.assertEqual(result.final_runtime_mode, 'storytelling')

        echo_message = self._recv_until(player_ws, 'echo')
        self.assertEqual(echo_message['entry']['category'], 'check')
        updated_view = self._recv_until(player_ws, 'view')['view']
        self.assertTrue(any('Recent check results:' in line for line in updated_view['summary_lines']))


if __name__ == '__main__':
    unittest.main()










