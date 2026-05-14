from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.dataset_manifest import write_dataset_manifest
from training.dataset_quality import (
    validate_preference_dataset,
    validate_transition_dataset,
    write_dataset_quality_report,
)
from training.training_smoke import (
    TRAINING_SMOKE_SCHEMA_VERSION,
    TrainingSmokeError,
    build_training_smoke_report,
    render_training_smoke_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainingSmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-smoke-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_training_smoke_report_records_ready_dataset_handoff(self) -> None:
        dataset_dir = self._write_ready_dataset_dir()

        report = build_training_smoke_report(
            [dataset_dir],
            output_dir=self._tempdir / 'runs',
            run_name='unit-smoke',
            transition_sample_limit=1,
            preference_sample_limit=1,
        )

        self.assertEqual(report['schema_version'], TRAINING_SMOKE_SCHEMA_VERSION)
        self.assertEqual(report['run_mode'], 'dry_run')
        self.assertEqual(report['readiness']['status'], 'ready')
        self.assertEqual(report['readiness']['blocker_count'], 0)
        self.assertEqual(report['readiness']['warning_count'], 0)
        self.assertEqual(len(report['datasets']), 2)
        self.assertEqual(report['samples']['transition_count'], 1)
        self.assertEqual(report['samples']['preference_count'], 1)
        self.assertEqual(report['samples']['transitions'][0]['sample_id'], 'sample-1')
        self.assertEqual(report['samples']['preferences'][0]['pair_id'], 'pair-1')
        self.assertTrue(Path(report['report_path']).exists())
        self.assertTrue(Path(report['markdown_path']).exists())
        markdown = render_training_smoke_markdown(report)
        self.assertIn('Training Smoke Report', markdown)
        self.assertIn('Readiness: **ready**', markdown)

    def test_training_smoke_blocks_when_readiness_is_not_ready(self) -> None:
        dataset_dir = self._tempdir / 'empty'
        dataset_dir.mkdir()

        with self.assertRaises(TrainingSmokeError):
            build_training_smoke_report([dataset_dir], output_dir=self._tempdir / 'runs')

    def test_training_smoke_can_write_not_ready_report_when_allowed(self) -> None:
        dataset_dir = self._tempdir / 'empty'
        dataset_dir.mkdir()

        report = build_training_smoke_report(
            [dataset_dir],
            output_dir=self._tempdir / 'runs',
            allow_not_ready=True,
        )

        self.assertEqual(report['readiness']['status'], 'blocked')
        self.assertTrue(any(check['status'] == 'fail' for check in report['checks']))
        self.assertTrue(Path(report['report_path']).exists())

    def _write_ready_dataset_dir(self) -> Path:
        dataset_dir = self._tempdir / 'dataset'
        dataset_dir.mkdir(parents=True)
        transitions = dataset_dir / 'combined_training_transitions.jsonl'
        preferences = dataset_dir / 'combined_preference_pairs.jsonl'
        self._write_jsonl(transitions, [self._transition_row('sample-1'), self._transition_row('sample-2')])
        self._write_jsonl(preferences, [self._preference_row('pair-1'), self._preference_row('pair-2')])
        transition_manifest = write_dataset_manifest(
            dataset_type='combined_training_transitions',
            dataset_path=transitions,
            record_count=2,
            source_paths=['batch-one/training_transitions.jsonl'],
        )
        preference_manifest = write_dataset_manifest(
            dataset_type='combined_preference_pairs',
            dataset_path=preferences,
            record_count=2,
            source_paths=['batch-one/preference_pairs.jsonl'],
        )
        transition_quality = validate_transition_dataset(transitions)
        preference_quality = validate_preference_dataset(preferences)
        transition_quality_path = write_dataset_quality_report(
            transition_quality,
            dataset_dir / 'combined_training_transitions.quality.json',
        )
        preference_quality_path = write_dataset_quality_report(
            preference_quality,
            dataset_dir / 'combined_preference_pairs.quality.json',
        )
        (dataset_dir / 'dataset_collection_report.json').write_text(
            json.dumps({
                'transition_path': str(transitions),
                'transition_manifest_path': str(transition_manifest),
                'transition_quality_path': str(transition_quality_path),
                'preference_path': str(preferences),
                'preference_manifest_path': str(preference_manifest),
                'preference_quality_path': str(preference_quality_path),
            }),
            encoding='utf-8',
        )
        (dataset_dir / 'benchmark_history.jsonl').write_text(
            json.dumps({
                'benchmark_id': 'benchmark-one',
                'scenario_id': 'lmop_first_combat',
                'created_at': '2026-05-13T00:00:00Z',
                'seed_count': 1,
                'policies': ['scripted'],
            }) + '\n',
            encoding='utf-8',
        )
        return dataset_dir

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )

    def _transition_row(self, sample_id: str) -> dict:
        return {
            'sample_id': sample_id,
            'agent_id': 'player-1-controller',
            'source': 'baseline',
            'runtime_mode': 'combat',
            'action': '/attack monster-goblin-1',
            'reward': 0.2,
            'action_reward': 0.2,
            'terminal_reward': 0.0,
            'observation': {'summary_lines': ['test']},
            'available_actions': [],
            'reward_channels': {'offense': 0.2},
        }

    def _preference_row(self, pair_id: str) -> dict:
        return {
            'pair_id': pair_id,
            'prompt': 'Choose a useful action.',
            'chosen': '/attack monster-goblin-1',
            'rejected': '/wait',
            'chosen_reward': 0.2,
            'rejected_reward': 0.0,
            'reward_gap': 0.2,
            'chosen_metadata': {'reward_channels': {'offense': 0.2}},
            'rejected_metadata': {'reward_channels': {'validity': 0.0}},
            'scenario_id': 'lmop_first_combat',
            'runtime_mode': 'combat',
        }


if __name__ == '__main__':
    unittest.main()
