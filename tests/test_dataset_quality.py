from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.dataset_quality import validate_preference_dataset, validate_transition_dataset, write_dataset_quality_report


REPO_ROOT = Path(__file__).resolve().parents[1]


class DatasetQualityTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.dataset-quality-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_validate_transition_dataset_passes_clean_rows(self) -> None:
        path = self._tempdir / 'transitions.jsonl'
        self._write_jsonl(path, [
            {
                'sample_id': 'episode-1:1',
                'agent_id': 'player-1-controller',
                'source': 'human',
                'runtime_mode': 'combat',
                'action': '/endturn player-1',
                'reward': 0.01,
                'action_reward': 0.01,
                'terminal_reward': 0.0,
                'observation': {'summary_lines': ['test']},
                'available_actions': [],
                'reward_channels': {'validity': 0.01},
            },
        ])

        report = validate_transition_dataset(path)

        self.assertEqual(report['status'], 'pass')
        self.assertEqual(report['record_count'], 1)
        self.assertEqual(report['counts']['source_counts'], {'human': 1})

    def test_validate_transition_dataset_fails_duplicate_and_missing_reward(self) -> None:
        path = self._tempdir / 'bad-transitions.jsonl'
        self._write_jsonl(path, [
            {'sample_id': 'dup', 'agent_id': 'player-1-controller', 'source': 'human', 'runtime_mode': 'combat', 'action': '/do x', 'reward': 1.0, 'action_reward': 1.0, 'terminal_reward': 0.0, 'observation': {}, 'reward_channels': {}},
            {'sample_id': 'dup', 'agent_id': 'player-2-controller', 'source': 'human', 'runtime_mode': 'combat', 'action': '/do y', 'action_reward': 0.0, 'terminal_reward': 0.0, 'observation': {}, 'reward_channels': {}},
        ])

        report = validate_transition_dataset(path)

        self.assertEqual(report['status'], 'fail')
        self.assertGreaterEqual(report['fail_count'], 2)
        self.assertIn('duplicate_id', {issue['code'] for issue in report['issues']})
        self.assertIn('missing_required_number', {issue['code'] for issue in report['issues']})

    def test_validate_preference_dataset_fails_non_positive_gap_and_empty_prompt(self) -> None:
        path = self._tempdir / 'bad-pairs.jsonl'
        self._write_jsonl(path, [
            {
                'pair_id': 'pair-1',
                'prompt': '',
                'chosen': '/attack',
                'rejected': '/wait',
                'chosen_reward': 0.1,
                'rejected_reward': 0.2,
                'reward_gap': -0.1,
                'chosen_metadata': {},
                'rejected_metadata': {},
            },
        ])

        report = validate_preference_dataset(path)

        self.assertEqual(report['status'], 'fail')
        self.assertIn('non_positive_reward_gap', {issue['code'] for issue in report['issues']})
        self.assertIn('missing_required_string', {issue['code'] for issue in report['issues']})

    def test_write_dataset_quality_report(self) -> None:
        path = self._tempdir / 'empty.jsonl'
        path.write_text('', encoding='utf-8')
        report = validate_transition_dataset(path)
        report_path = write_dataset_quality_report(report, self._tempdir / 'quality.json')

        saved = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['status'], 'fail')
        self.assertEqual(saved['issues'][0]['code'], 'empty_dataset')

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )


if __name__ == '__main__':
    unittest.main()
