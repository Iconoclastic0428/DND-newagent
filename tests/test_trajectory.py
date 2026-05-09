from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

from dm_agent.client import LLMClient
from dm_agent.config import LLMConfig
from session_server.llm_player import LLMPlayerAgent
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL
from tests.test_storytelling_session import QueueTransport
from training.trajectory import TrajectoryRecorder

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from story_demo_system_server import build_full_story_demo_manual_session


class TrajectoryRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.trajectory-tests' / uuid4().hex
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

    def test_full_story_demo_records_story_turn_jsonl(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_gundren_briefing',
            episode_id='episode-test',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren gives the party the practical terms.",'
                        '"transcript_entries":[{"speaker":"Gundren Rockseeker","text":"Ten gold each when the wagon reaches Phandalin.","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        '"memory_note":"The party asked about payment."'
                        '}'
                    )
                }
            ]),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )

        session.handle_input('player-1-controller', "What's the pay?")

        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        record_types = [record['record_type'] for record in records]
        self.assertIn('episode_started', record_types)
        self.assertIn('story_started', record_types)
        turn = next(record for record in records if record['record_type'] == 'turn')
        self.assertEqual(turn['scenario_id'], 'lmop_gundren_briefing')
        self.assertEqual(turn['agent_id'], 'player-1-controller')
        self.assertEqual(turn['role'], 'player')
        self.assertEqual(turn['source'], 'human')
        self.assertEqual(turn['raw_text'], "What's the pay?")
        self.assertEqual(turn['parsed_action']['kind'], 'natural_language')
        self.assertEqual(turn['runtime_mode'], 'storytelling')
        self.assertEqual(turn['state_before']['scene_id'], 'scene-waterdeep-gundren-briefing')
        self.assertGreater(turn['state_after']['transcript_count'], turn['state_before']['transcript_count'])
        self.assertTrue(turn['observation']['summary_lines'])
        self.assertEqual(turn['reward_components'], {})

    def test_full_llm_party_autopump_records_each_player_once(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_full_llm_party',
            episode_id='episode-full-llm-party',
        )
        agents = tuple(
            LLMPlayerAgent(
                controller_id=f'player-{index}-controller',
                client=LLMClient(
                    LLMConfig(api_key='test-key', base_url='https://example.invalid/v1', responses_model=f'player-{index}-model'),
                    transport=QueueTransport([
                        {
                            'output_text': json.dumps(
                                {
                                    'command': f'/say Player {index} is ready to continue.',
                                    'reason': 'Keep the party moving.',
                                }
                            )
                        }
                    ]),
                ),
                label=f'test-player-{index}',
            )
            for index in range(1, 5)
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([
                {
                    'output_text': (
                        '{'
                        f'"public_narration":"The DM acknowledges player {index}.",'
                        '"transcript_entries":[],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        f'"memory_note":"Player {index} acted."'
                        '}'
                    )
                }
                for index in range(1, 5)
            ]),
            precreate_characters=True,
            llm_player_agents=agents,
            llm_player_autopump=True,
            llm_player_max_actions_per_pump=4,
            trajectory_recorder=recorder,
        )

        actions = session.pump_llm_players(max_actions=4)

        self.assertEqual(
            actions,
            (
                ('player-1-controller', '/say Player 1 is ready to continue.'),
                ('player-2-controller', '/say Player 2 is ready to continue.'),
                ('player-3-controller', '/say Player 3 is ready to continue.'),
                ('player-4-controller', '/say Player 4 is ready to continue.'),
            ),
        )
        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        llm_turns = [record for record in records if record['record_type'] == 'turn' and record['source'] == 'llm_player']
        self.assertEqual([record['agent_id'] for record in llm_turns], [f'player-{index}-controller' for index in range(1, 5)])
        self.assertTrue(all(record['parsed_action']['kind'] == 'command' for record in llm_turns))


if __name__ == '__main__':
    unittest.main()
