from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

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


if __name__ == '__main__':
    unittest.main()

