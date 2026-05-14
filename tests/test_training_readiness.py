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
from training.readiness_report import (
    build_training_readiness_report,
    render_training_readiness_markdown,
    write_training_readiness_markdown,
    write_training_readiness_report,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainingReadinessReportTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-readiness-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_training_readiness_report_passes_with_manifests_quality_and_history(self) -> None:
        dataset_dir = self._tempdir / 'dataset'
        dataset_dir.mkdir(parents=True)
        transitions = dataset_dir / 'combined_training_transitions.jsonl'
        self._write_jsonl(transitions, [self._transition_row('sample-1')])
        manifest_path = write_dataset_manifest(
            dataset_type='combined_training_transitions',
            dataset_path=transitions,
            record_count=1,
            source_paths=[self._tempdir / 'batch_report.json'],
            context={'source_batch_count': 1, 'policies': ['scripted']},
        )
        quality = validate_transition_dataset(transitions)
        quality_path = write_dataset_quality_report(quality, dataset_dir / 'combined_training_transitions.quality.json')
        collection_path = dataset_dir / 'dataset_collection_report.json'
        collection_path.write_text(
            json.dumps({
                'collection_id': 'collection-test',
                'transition_path': str(transitions),
                'transition_manifest_path': str(manifest_path),
                'transition_quality_path': str(quality_path),
                'transition_quality_status': 'pass',
                'transition_count': 1,
            }),
            encoding='utf-8',
        )
        benchmark_root = self._tempdir / 'benchmarks'
        benchmark_root.mkdir()
        (benchmark_root / 'benchmark_history.jsonl').write_text(
            json.dumps({
                'benchmark_id': 'benchmark-test',
                'scenario_id': 'lmop_first_combat',
                'created_at': '2026-05-13T00:00:00Z',
                'seed_count': 1,
                'policies': [{'label': 'scripted'}],
            })
            + '\n',
            encoding='utf-8',
        )
        raw_batch_dataset = benchmark_root / 'batch' / 'training_transitions.jsonl'
        raw_batch_dataset.parent.mkdir(parents=True)
        self._write_jsonl(raw_batch_dataset, [self._transition_row('raw-sample')])
        write_dataset_manifest(
            dataset_type='training_transitions',
            dataset_path=raw_batch_dataset,
            record_count=1,
            source_paths=[],
        )

        report = build_training_readiness_report([dataset_dir, benchmark_root])

        self.assertEqual(report['status'], 'ready')
        self.assertEqual(report['blocker_count'], 0)
        self.assertEqual(report['warning_count'], 0)
        self.assertEqual(report['dataset_count'], 1)
        self.assertEqual([dataset['dataset_name'] for dataset in report['datasets']], ['combined_training_transitions.jsonl'])
        self.assertEqual(report['total_record_count'], 1)
        self.assertEqual(report['datasets'][0]['manifest_status'], 'present')
        self.assertEqual(report['datasets'][0]['quality_status'], 'pass')
        self.assertEqual(report['benchmark_history']['entry_count'], 1)
        markdown = render_training_readiness_markdown(report)
        self.assertIn('Status: **ready**', markdown)
        self.assertIn('combined_training_transitions', markdown)

    def test_training_readiness_report_warns_without_quality_or_history(self) -> None:
        dataset_dir = self._tempdir / 'dataset'
        dataset_dir.mkdir(parents=True)
        transitions = dataset_dir / 'combined_training_transitions.jsonl'
        self._write_jsonl(transitions, [self._transition_row('sample-1')])
        write_dataset_manifest(
            dataset_type='combined_training_transitions',
            dataset_path=transitions,
            record_count=1,
            source_paths=[],
        )

        report = build_training_readiness_report([dataset_dir])

        self.assertEqual(report['status'], 'needs_attention')
        self.assertEqual(report['blocker_count'], 0)
        self.assertEqual(
            {issue['code'] for issue in report['issues']},
            {'missing_quality_report', 'missing_benchmark_history'},
        )

    def test_training_readiness_report_recommends_non_dominant_runtime_mode_coverage(self) -> None:
        dataset_dir = self._tempdir / 'dataset'
        dataset_dir.mkdir(parents=True)
        preferences = dataset_dir / 'combined_preference_pairs.jsonl'
        rows = [
            self._preference_row(f'pair-{index}', runtime_mode='combat')
            for index in range(20)
        ]
        rows.append(self._preference_row('pair-story', runtime_mode='storytelling'))
        self._write_jsonl(preferences, rows)
        manifest_path = write_dataset_manifest(
            dataset_type='combined_preference_pairs',
            dataset_path=preferences,
            record_count=len(rows),
            source_paths=[],
        )
        quality = validate_preference_dataset(preferences)
        quality_path = write_dataset_quality_report(quality, dataset_dir / 'combined_preference_pairs.quality.json')
        (dataset_dir / 'dataset_collection_report.json').write_text(
            json.dumps({
                'preference_path': str(preferences),
                'preference_manifest_path': str(manifest_path),
                'preference_quality_path': str(quality_path),
            }),
            encoding='utf-8',
        )
        (dataset_dir / 'benchmark_history.jsonl').write_text(
            json.dumps({'benchmark_id': 'benchmark-test', 'scenario_id': 'lmop_first_combat'})
            + '\n',
            encoding='utf-8',
        )

        report = build_training_readiness_report([dataset_dir])

        self.assertEqual(report['status'], 'needs_attention')
        self.assertEqual(report['datasets'][0]['quality_status'], 'warn')
        self.assertIn('runtime_mode_imbalance', report['datasets'][0]['quality_issues'][0]['code'])
        self.assertTrue(any('non-combat preference examples' in item for item in report['recommendations']))
        self.assertIn('## Recommendations', render_training_readiness_markdown(report))

    def test_training_readiness_report_blocks_failed_quality_and_empty_dataset(self) -> None:
        dataset_dir = self._tempdir / 'dataset'
        dataset_dir.mkdir(parents=True)
        transitions = dataset_dir / 'combined_training_transitions.jsonl'
        transitions.write_text('', encoding='utf-8')
        manifest_path = write_dataset_manifest(
            dataset_type='combined_training_transitions',
            dataset_path=transitions,
            record_count=0,
            source_paths=[],
        )
        quality = validate_transition_dataset(transitions)
        quality_path = write_dataset_quality_report(quality, dataset_dir / 'combined_training_transitions.quality.json')
        (dataset_dir / 'dataset_collection_report.json').write_text(
            json.dumps({
                'transition_path': str(transitions),
                'transition_manifest_path': str(manifest_path),
                'transition_quality_path': str(quality_path),
            }),
            encoding='utf-8',
        )

        report = build_training_readiness_report([dataset_dir])

        self.assertEqual(report['status'], 'blocked')
        self.assertIn('quality_failed', {issue['code'] for issue in report['issues']})
        self.assertIn('empty_dataset', {issue['code'] for issue in report['issues']})

    def test_write_training_readiness_outputs_json_and_markdown(self) -> None:
        report = build_training_readiness_report([self._tempdir])
        json_path = write_training_readiness_report(report, self._tempdir / 'readiness.json')
        markdown_path = write_training_readiness_markdown(report, self._tempdir / 'readiness.md')

        saved = json.loads(json_path.read_text(encoding='utf-8'))
        markdown = markdown_path.read_text(encoding='utf-8')
        self.assertEqual(saved['status'], 'blocked')
        self.assertIn('# Training Readiness Report', markdown)

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
            'action': '/endturn player-1',
            'reward': 0.1,
            'action_reward': 0.1,
            'terminal_reward': 0.0,
            'observation': {'summary_lines': ['test']},
            'available_actions': [],
            'reward_channels': {'validity': 0.1},
        }

    def _preference_row(self, pair_id: str, *, runtime_mode: str) -> dict:
        return {
            'pair_id': pair_id,
            'prompt': 'Choose a useful action.',
            'chosen': '/attack',
            'rejected': '/wait',
            'chosen_reward': 0.2,
            'rejected_reward': 0.0,
            'reward_gap': 0.2,
            'chosen_metadata': {},
            'rejected_metadata': {},
            'runtime_mode': runtime_mode,
            'acting_actor_id': 'player-1',
            'scenario_id': 'lmop_first_combat',
        }


if __name__ == '__main__':
    unittest.main()
