from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

from training.trajectory_summary import summarize_batch, summarize_trajectory

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_training_batch import run_batch
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class TrainingBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-batch-tests' / uuid4().hex
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

    def test_summarize_trajectory_counts_rewards_errors_and_terminal_state(self) -> None:
        records = [
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'episode_started',
                'source': 'system',
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'turn',
                'agent_id': 'player-1-controller',
                'source': 'human',
                'reward_components': {'valid_action': 0.01},
                'metadata': {'reward_total': 0.01},
                'state_after': {'runtime_mode': 'combat', 'scene_id': 'scene-1', 'party_hp_current': 10, 'party_hp_max': 20},
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'turn',
                'agent_id': 'player-2-controller',
                'source': 'llm_player',
                'reward_components': {'invalid_action': -1.0},
                'metadata': {'reward_total': -1.0},
                'error': 'bad command',
                'state_after': {'runtime_mode': 'combat', 'scene_id': 'scene-1', 'party_hp_current': 10, 'party_hp_max': 20},
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'episode_completed',
                'runtime_mode': 'demo-complete',
                'source': 'system',
                'reward_components': {'episode_success': 1.0, 'party_survival': 0.5},
                'metadata': {
                    'reward_total': 1.5,
                    'success': True,
                    'winning_side': 'player',
                    'round_number': 2,
                    'party_hp_current': 10,
                    'party_hp_max': 20,
                    'living_party_count': 4,
                    'living_monster_count': 0,
                },
            },
        ]

        summary = summarize_trajectory(records)

        self.assertEqual(summary['episode_id'], 'episode-1')
        self.assertEqual(summary['turn_count'], 2)
        self.assertEqual(summary['invalid_action_count'], 1)
        self.assertEqual(summary['total_reward'], 0.51)
        self.assertTrue(summary['success'])
        self.assertEqual(summary['terminal']['party_hp_ratio'], 0.5)
        self.assertEqual(summary['action_count_by_agent']['player-1-controller'], 1)
        self.assertEqual(summary['action_count_by_source']['llm_player'], 1)
        self.assertEqual(summary['error_messages'], ['bad command'])

    def test_summarize_batch_aggregates_episode_summaries(self) -> None:
        report = summarize_batch([
            {'success': True, 'total_reward': 2.0, 'invalid_action_count': 0, 'turn_count': 10, 'final_party_hp_ratio': 1.0},
            {'success': False, 'total_reward': -1.0, 'invalid_action_count': 2, 'turn_count': 6, 'final_party_hp_ratio': 0.25, 'error_messages': ['timeout']},
        ])

        self.assertEqual(report['episodes'], 2)
        self.assertEqual(report['successes'], 1)
        self.assertEqual(report['success_rate'], 0.5)
        self.assertEqual(report['avg_reward'], 0.5)
        self.assertEqual(report['avg_invalid_actions'], 1.0)
        self.assertEqual(report['avg_turns'], 8.0)
        self.assertEqual(report['avg_party_hp_remaining'], 0.625)
        self.assertEqual(report['common_failure_modes'], [{'message': 'timeout', 'count': 1}])

    def test_single_episode_first_combat_batch_writes_report(self) -> None:
        report = run_batch(
            episodes=1,
            output_dir=self._tempdir / 'batches',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
        )

        report_path = Path(report['report_path'])
        self.assertTrue(report_path.exists())
        saved = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['episodes'], 1)
        self.assertEqual(saved['successes'], 1)
        self.assertEqual(saved['success_rate'], 1.0)
        self.assertGreater(saved['avg_reward'], 1.0)
        self.assertEqual(saved['avg_invalid_actions'], 0.0)
        self.assertEqual(saved['episode_summaries'][0]['final_runtime_mode'], 'demo-complete')


if __name__ == '__main__':
    unittest.main()
