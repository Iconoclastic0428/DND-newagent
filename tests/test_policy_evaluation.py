from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.evaluation import load_transition_records, summarize_policy_evaluation, write_policy_evaluation_report


REPO_ROOT = Path(__file__).resolve().parents[1]


class PolicyEvaluationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.policy-evaluation-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_summarize_policy_evaluation_groups_agents_sources_and_channels(self) -> None:
        transitions = [
            {
                'sample_id': 'episode-1:1',
                'episode_id': 'episode-1',
                'agent_id': 'player-1-controller',
                'source': 'llm_player',
                'runtime_mode': 'combat',
                'reward': 0.31,
                'action_reward': 0.31,
                'terminal_reward': 0.0,
                'reward_channels': {'validity': 0.01, 'offense': 0.3},
                'error': None,
                'done': False,
            },
            {
                'sample_id': 'episode-1:2',
                'episode_id': 'episode-1',
                'agent_id': 'player-2-controller',
                'source': 'human',
                'runtime_mode': 'combat',
                'reward': -1.0,
                'action_reward': -1.0,
                'terminal_reward': 0.0,
                'reward_channels': {'validity': -1.0},
                'error': 'bad command',
                'done': False,
            },
            {
                'sample_id': 'episode-1:3',
                'episode_id': 'episode-1',
                'agent_id': 'player-1-controller',
                'source': 'llm_player',
                'runtime_mode': 'combat',
                'reward': 1.61,
                'action_reward': 0.11,
                'terminal_reward': 1.5,
                'reward_channels': {'validity': 0.01, 'support': 0.1, 'terminal': 1.5},
                'error': None,
                'done': True,
                'success': True,
            },
        ]

        report = summarize_policy_evaluation(
            transitions,
            episode_summaries=[{'success': True, 'total_reward': 0.92}],
        )

        self.assertEqual(report['transition_count'], 3)
        self.assertEqual(report['episode_count'], 1)
        self.assertEqual(report['success_rate'], 1.0)
        self.assertEqual(report['invalid_transition_count'], 1)
        self.assertAlmostEqual(report['invalid_transition_rate'], 1 / 3)
        self.assertAlmostEqual(report['total_reward'], 0.92)
        self.assertEqual(report['reward_by_channel'], {'validity': -0.98, 'offense': 0.3, 'support': 0.1, 'terminal': 1.5})
        self.assertEqual(report['action_count_by_agent']['player-1-controller'], 2)
        self.assertEqual(report['action_count_by_source']['llm_player'], 2)
        player_1 = report['per_agent']['player-1-controller']
        self.assertEqual(player_1['action_count'], 2)
        self.assertEqual(player_1['invalid_action_count'], 0)
        self.assertAlmostEqual(player_1['total_reward'], 1.92)
        self.assertEqual(player_1['reward_by_channel'], {'validity': 0.02, 'offense': 0.3, 'support': 0.1, 'terminal': 1.5})
        self.assertEqual(report['agent_leaderboard'][0]['agent_id'], 'player-1-controller')

    def test_write_and_load_policy_evaluation_report(self) -> None:
        transitions_path = self._tempdir / 'transitions.jsonl'
        transitions_path.write_text(
            json.dumps({'sample_id': 'episode-1:1', 'agent_id': 'player-1-controller', 'reward': 1.0, 'reward_channels': {'support': 1.0}}) + '\n',
            encoding='utf-8',
        )
        transitions = load_transition_records(transitions_path)
        report = summarize_policy_evaluation(transitions)
        output_path = self._tempdir / 'policy_evaluation.json'

        write_policy_evaluation_report(report, output_path)

        saved = json.loads(output_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['transition_count'], 1)
        self.assertEqual(saved['reward_by_channel'], {'support': 1.0})


if __name__ == '__main__':
    unittest.main()
