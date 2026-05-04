from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from unittest.mock import MagicMock, patch
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from web_story_demo_live_runner import AutomationHttpClient, run_live_web_story_script
from story_demo_replay import run_story_demo_script
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class StoryDemoReplayScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.story-demo-replay-tests' / uuid4().hex
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

    def test_friendly_full_run_script_executes(self) -> None:
        result = run_story_demo_script(
            REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts' / 'lmop-friendly-full-run.json',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
        )
        self.assertEqual(result.script_id, 'lmop-friendly-full-run')
        self.assertEqual(result.final_runtime_mode, 'combat')
        self.assertEqual(result.final_scene_id, 'scene-triboar-goblin-ambush')
        self.assertEqual(result.remaining_llm_payloads, 0)
        self.assertEqual(result.llm_requests, 3)

    def test_unfriendly_full_run_script_executes(self) -> None:
        result = run_story_demo_script(
            REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts' / 'lmop-unfriendly-full-run.json',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
        )
        self.assertEqual(result.script_id, 'lmop-unfriendly-full-run')
        self.assertEqual(result.final_runtime_mode, 'combat')
        self.assertEqual(result.final_scene_id, 'scene-triboar-goblin-ambush')
        self.assertEqual(result.remaining_llm_payloads, 0)
        self.assertEqual(result.llm_requests, 2)

    def test_live_web_runner_uses_configured_request_timeout(self) -> None:
        client = AutomationHttpClient('http://127.0.0.1:8000', request_timeout_seconds=180.0)
        response = MagicMock()
        response.read.return_value = b'{"ok": true, "view": {}, "prompt": null}'
        response_context = MagicMock()
        response_context.__enter__.return_value = response
        response_context.__exit__.return_value = False
        with patch('web_story_demo_live_runner.urllib_request.urlopen', return_value=response_context) as mocked_urlopen:
            payload = client.submit('player-1-controller', '/create begin')
        self.assertTrue(payload['ok'])
        mocked_urlopen.assert_called_once()
        self.assertEqual(mocked_urlopen.call_args.kwargs['timeout'], 180.0)

    def test_live_web_runner_can_disable_request_timeout(self) -> None:
        client = AutomationHttpClient('http://127.0.0.1:8000', request_timeout_seconds=None)
        response = MagicMock()
        response.read.return_value = b'{"ok": true, "view": {}, "prompt": null}'
        response_context = MagicMock()
        response_context.__enter__.return_value = response
        response_context.__exit__.return_value = False
        with patch('web_story_demo_live_runner.urllib_request.urlopen', return_value=response_context) as mocked_urlopen:
            payload = client.state('player-1-controller')
        self.assertTrue(payload['ok'])
        mocked_urlopen.assert_called_once()
        self.assertNotIn('timeout', mocked_urlopen.call_args.kwargs)

    def test_live_web_runner_resolves_view_templates_and_applies_post_delay(self) -> None:
        script_path = self._tempdir / 'templated-live-web-script.json'
        script_path.write_text(
            json.dumps(
                {
                    'script_id': 'templated-live-web-script',
                    'result_controller_id': 'player-1-controller',
                    'steps': [
                        {
                            'type': 'command_if_view',
                            'controller_id': 'dm',
                            'runtime_mode': 'combat',
                            'active_actor_side': 'monster',
                            'input': '/endturn {active_actor_id}',
                            'post_delay_seconds': 0.2,
                        },
                        {
                            'type': 'command_if_view',
                            'controller_id': 'player-1-controller',
                            'runtime_mode': 'combat',
                            'active_actor_id': 'player-1',
                            'input': '/cast {active_actor_id} magic-missile {first_enemy_actor_id}',
                            'post_delay_seconds': 0.2,
                        },
                        {
                            'type': 'command_if_view',
                            'controller_id': 'player-1-controller',
                            'runtime_mode': 'demo-complete',
                            'current_scene_id': 'scene-demo-complete',
                            'input': '/endturn {active_actor_id}',
                        },
                    ],
                }
            ),
            encoding='utf-8',
        )

        class _FakeAutomationClient:
            instances: list['_FakeAutomationClient'] = []

            def __init__(self, base_url: str, *, request_timeout_seconds=None) -> None:
                self.base_url = base_url
                self.request_timeout_seconds = request_timeout_seconds
                self.submissions: list[tuple[str, str]] = []
                self.states: dict[str, dict[str, object]] = {
                    'dm': {
                        'ok': True,
                        'view': {
                            'runtime_mode': 'combat',
                            'active_actor_id': 'monster-goblin-1',
                            'current_scene_id': 'scene-triboar-goblin-ambush',
                            'summary_lines': [],
                            'map': {
                                'tokens': [
                                    {'actor_id': 'monster-goblin-1', 'side': 'monster', 'status': 'ready'},
                                    {'actor_id': 'player-1', 'side': 'player', 'status': 'ready'},
                                ]
                            },
                        },
                        'prompt': None,
                    },
                    'player-1-controller': {
                        'ok': True,
                        'view': {
                            'runtime_mode': 'combat',
                            'active_actor_id': 'player-1',
                            'current_scene_id': 'scene-triboar-goblin-ambush',
                            'summary_lines': [],
                            'map': {
                                'tokens': [
                                    {'actor_id': 'player-1', 'side': 'player', 'status': 'ready'},
                                    {'actor_id': 'monster-goblin-dead', 'side': 'monster', 'status': 'dead'},
                                    {'actor_id': 'monster-goblin-4', 'side': 'monster', 'status': 'ready'},
                                ]
                            },
                        },
                        'prompt': None,
                    },
                }
                self.__class__.instances.append(self)

            def state(self, controller_id: str) -> dict[str, object]:
                return self.states[controller_id]

            def submit(self, controller_id: str, text: str) -> dict[str, object]:
                self.submissions.append((controller_id, text))
                snapshot = self.states[controller_id]
                if controller_id == 'player-1-controller':
                    snapshot = {
                        'ok': True,
                        'view': {
                            **snapshot['view'],
                            'runtime_mode': 'demo-complete',
                            'summary_lines': ['The party survived the goblin ambush.'],
                        },
                        'prompt': None,
                    }
                    self.states[controller_id] = snapshot
                return snapshot

        with patch('web_story_demo_live_runner.AutomationHttpClient', _FakeAutomationClient), patch(
            'web_story_demo_live_runner.time.sleep'
        ) as mocked_sleep:
            result = run_live_web_story_script(script_path, base_url='http://127.0.0.1:8000')

        fake_client = _FakeAutomationClient.instances[-1]
        self.assertEqual(
            fake_client.submissions,
            [
                ('dm', '/endturn monster-goblin-1'),
                ('player-1-controller', '/cast player-1 magic-missile monster-goblin-4'),
            ],
        )
        self.assertEqual([call.args for call in mocked_sleep.call_args_list], [(0.2,), (0.2,)])
        self.assertEqual(result.commands_sent, 2)
        self.assertEqual(result.skipped_steps, 1)
        self.assertEqual(result.final_runtime_mode, 'demo-complete')


if __name__ == '__main__':
    unittest.main()
