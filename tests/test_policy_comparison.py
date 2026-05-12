from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.comparison import compare_policy_batches, load_batch_report, write_policy_comparison_report


REPO_ROOT = Path(__file__).resolve().parents[1]


def _batch_report(
    *,
    batch_id: str,
    policy: str,
    success_rate: float,
    avg_reward: float,
    avg_invalid_actions: float,
    offense: float,
    support: float = 0.0,
) -> dict:
    return {
        'batch_id': batch_id,
        'scenario_id': 'lmop_first_combat',
        'policy': policy,
        'episodes': 4,
        'successes': int(success_rate * 4),
        'success_rate': success_rate,
        'avg_reward': avg_reward,
        'avg_invalid_actions': avg_invalid_actions,
        'avg_turns': 20.0,
        'avg_party_hp_remaining': 0.75,
        'transition_count': 40,
        'preference_pair_count': 3,
        'llm_player_controllers': ['player-1-controller'] if policy == 'llm-party' else [],
        'policy_evaluation': {
            'transition_count': 40,
            'invalid_transition_rate': avg_invalid_actions / 10.0,
            'total_reward': avg_reward * 4,
            'avg_reward_per_transition': avg_reward / 10.0,
            'total_action_reward': avg_reward * 3,
            'total_terminal_reward': avg_reward,
            'reward_by_channel': {
                'offense': offense,
                'support': support,
                'validity': 0.4,
            },
            'avg_reward_by_channel': {
                'offense': offense / 40.0,
                'support': support / 40.0,
                'validity': 0.01,
            },
            'action_count_by_source': {'llm_player': 20, 'human': 20} if policy == 'llm-party' else {'human': 40},
            'action_count_by_runtime_mode': {'combat': 12, 'storytelling': 8, 'character-creation': 20},
        },
    }


class PolicyComparisonTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.policy-comparison-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_compare_policy_batches_ranks_and_reports_channel_metrics(self) -> None:
        scripted = _batch_report(
            batch_id='scripted-batch',
            policy='scripted',
            success_rate=1.0,
            avg_reward=4.0,
            avg_invalid_actions=0.0,
            offense=2.5,
        )
        candidate = _batch_report(
            batch_id='candidate-batch',
            policy='llm-party',
            success_rate=0.75,
            avg_reward=5.0,
            avg_invalid_actions=0.25,
            offense=1.5,
            support=2.0,
        )

        report = compare_policy_batches([
            ('scripted', scripted),
            ('candidate-model', candidate),
        ])

        self.assertEqual(report['comparison_count'], 2)
        self.assertEqual(report['scenario_ids'], ['lmop_first_combat'])
        self.assertEqual(report['reward_channels'], ['offense', 'support', 'validity'])
        self.assertEqual(report['leaderboard'][0]['label'], 'scripted')
        self.assertEqual(report['best_by_metric']['success_rate'], 'scripted')
        self.assertEqual(report['best_by_metric']['avg_reward'], 'candidate-model')
        candidate_row = next(row for row in report['rows'] if row['label'] == 'candidate-model')
        self.assertEqual(candidate_row['policy'], 'llm-party')
        self.assertEqual(candidate_row['reward_by_channel']['support'], 2.0)
        self.assertEqual(candidate_row['action_count_by_source']['llm_player'], 20.0)

    def test_load_and_write_policy_comparison_report(self) -> None:
        batch_path = self._tempdir / 'batch_report.json'
        batch = _batch_report(
            batch_id='loaded-batch',
            policy='scripted',
            success_rate=1.0,
            avg_reward=3.0,
            avg_invalid_actions=0.0,
            offense=1.0,
        )
        batch_path.write_text(json.dumps(batch), encoding='utf-8-sig')

        loaded = load_batch_report(batch_path)
        report = compare_policy_batches([('loaded', loaded)])
        output_path = self._tempdir / 'policy_comparison.json'
        write_policy_comparison_report(report, output_path)

        saved = json.loads(output_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['comparison_count'], 1)
        self.assertEqual(saved['rows'][0]['label'], 'loaded')
        self.assertEqual(saved['rows'][0]['report_path'], str(batch_path))


if __name__ == '__main__':
    unittest.main()
