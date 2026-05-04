from __future__ import annotations

import http.client
import json
import queue
import shutil
import threading
import time
from pathlib import Path
import unittest
from uuid import uuid4

from dm_agent.memory import DmMemoryWriter
from session_server.bootstrap import build_default_encounter_session
from session_server.storytelling_session import StorytellingSession
from session_server.web_transport import AuthoritativeWebServer
from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.models import Ability
from shared_types.storytelling import RuntimeMode, StoryCheckRequestState, StoryRuntimeState


class _SSEReader(threading.Thread):
    def __init__(self, *, host: str, port: int, token: str, target_count: int) -> None:
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.token = token
        self.target_count = target_count
        self.events: queue.Queue[tuple[str, dict]] = queue.Queue()
        self.error: Exception | None = None

    def run(self) -> None:
        conn = http.client.HTTPConnection(self.host, self.port, timeout=10)
        try:
            conn.request('GET', f'/api/session/events?reconnect_token={self.token}')
            response = conn.getresponse()
            if response.status != 200:
                self.error = AssertionError(f'SSE status was {response.status}')
                return
            current_event = 'message'
            data_lines: list[str] = []
            seen = 0
            while seen < self.target_count:
                raw_line = response.fp.readline()
                if not raw_line:
                    break
                line = raw_line.decode('utf-8').rstrip('\r\n')
                if not line:
                    if data_lines:
                        payload = json.loads(''.join(data_lines))
                        self.events.put((current_event, payload))
                        seen += 1
                    current_event = 'message'
                    data_lines = []
                    continue
                if line.startswith(':'):
                    continue
                if line.startswith('event:'):
                    current_event = line.split(':', 1)[1].strip()
                    continue
                if line.startswith('data:'):
                    data_lines.append(line.split(':', 1)[1].lstrip())
        except Exception as exc:  # pragma: no cover
            self.error = exc
        finally:
            conn.close()


class WebTransportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._servers: list[AuthoritativeWebServer] = []
        self._temp_dirs: list[Path] = []
        self._temp_root = Path('tests/.tmp/web-transport').resolve()
        self._temp_root.mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        for server in reversed(self._servers):
            server.shutdown()
        for temp_dir in reversed(self._temp_dirs):
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)

    def _start_server(self, session) -> AuthoritativeWebServer:
        server = AuthoritativeWebServer(session=session, host='127.0.0.1', port=0)
        server.start()
        self._servers.append(server)
        return server

    def _request(self, server: AuthoritativeWebServer, method: str, path: str, payload: dict | None = None):
        conn = http.client.HTTPConnection('127.0.0.1', server.port, timeout=10)
        body = None if payload is None else json.dumps(payload)
        headers = {'Content-Type': 'application/json'} if payload is not None else {}
        conn.request(method, path, body=body, headers=headers)
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        data = json.loads(raw.decode('utf-8')) if raw else None
        return response.status, data

    def _join(self, server: AuthoritativeWebServer, controller_id: str) -> tuple[str, dict]:
        status, data = self._request(server, 'POST', '/api/session/join', {'controller_id': controller_id})
        self.assertEqual(status, 200)
        assert data is not None
        self.assertEqual(data['grant']['controller_id'], controller_id)
        return data['grant']['controller_token'], data['view']

    def _build_story_session(self) -> StorytellingSession:
        encounter_session = build_default_encounter_session()
        temp_dir = self._temp_root / f'session-{uuid4().hex}'
        temp_dir.mkdir(parents=True, exist_ok=False)
        self._temp_dirs.append(temp_dir)
        campaign_root = Path('campaigns/lmop')
        memory_writer = DmMemoryWriter(temp_dir, campaign_id='lmop')
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

    def test_join_command_and_reconnect_return_structured_view(self) -> None:
        session = build_default_encounter_session()
        session.system_execute('/encounter start')
        server = self._start_server(session)

        dm_token, dm_view = self._join(server, 'dm')
        self.assertEqual(dm_view['runtime_mode'], 'combat')
        self.assertEqual(dm_view['controller_id'], 'dm')
        self.assertEqual(dm_view['encounter_phase'], 'in-progress')
        self.assertEqual(dm_view['active_actor_id'], 'monster-skeleton-1')

        self._request(server, 'POST', '/api/session/command', {'controller_token': dm_token, 'command': '/endturn monster-skeleton-1'})
        self._request(server, 'POST', '/api/session/command', {'controller_token': dm_token, 'command': '/endturn monster-mage-1'})

        player_token, player_view = self._join(server, 'player-1-controller')
        group_ids = {group['group_id'] for group in player_view['action_groups']}
        self.assertIn('actions', group_ids)
        self.assertIn('attacks', group_ids)

        status, reconnect_payload = self._request(server, 'POST', '/api/session/reconnect', {'controller_token': player_token})
        self.assertEqual(status, 200)
        assert reconnect_payload is not None
        self.assertEqual(reconnect_payload['grant']['controller_token'], player_token)
        self.assertEqual(reconnect_payload['view']['controller_id'], 'player-1-controller')
        reconnect_group_ids = {group['group_id'] for group in reconnect_payload['view']['action_groups']}
        self.assertIn('actions', reconnect_group_ids)

    def test_sse_pushes_updated_view_after_command(self) -> None:
        session = build_default_encounter_session()
        session.system_execute('/encounter start')
        server = self._start_server(session)
        dm_token, initial_view = self._join(server, 'dm')

        reader = _SSEReader(host='127.0.0.1', port=server.port, token=dm_token, target_count=2)
        reader.start()
        time.sleep(0.2)
        self._request(server, 'POST', '/api/session/command', {'controller_token': dm_token, 'command': '/endturn monster-skeleton-1'})
        reader.join(timeout=5)
        if reader.error is not None:
            raise reader.error

        first_event = reader.events.get(timeout=2)
        second_event = reader.events.get(timeout=2)
        self.assertEqual(first_event[0], 'view')
        self.assertEqual(second_event[0], 'view')
        self.assertEqual(first_event[1]['view']['active_actor_id'], initial_view['active_actor_id'])
        self.assertEqual(second_event[1]['view']['active_actor_id'], 'monster-mage-1')

    def test_storytelling_join_exposes_structured_story_prompt(self) -> None:
        session = self._build_story_session()
        server = self._start_server(session)
        token, view = self._join(server, 'player-1-controller')
        self.assertEqual(view['runtime_mode'], 'storytelling')
        self.assertEqual(view['current_scene_id'], 'scene-waterdeep-gundren-briefing')
        self.assertEqual(view['prompt']['prompt_kind'], 'story-check')
        self.assertIn('Wisdom (Insight)', view['prompt']['text'])

        status, payload = self._request(server, 'GET', f'/api/session/view?controller_token={token}')
        self.assertEqual(status, 200)
        assert payload is not None
        self.assertEqual(payload['view']['prompt']['prompt_kind'], 'story-check')


if __name__ == '__main__':
    unittest.main()
