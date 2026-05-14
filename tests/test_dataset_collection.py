from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.dataset_collection import collect_training_datasets


REPO_ROOT = Path(__file__).resolve().parents[1]


class DatasetCollectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.dataset-collection-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_collect_training_datasets_combines_benchmark_batch_outputs(self) -> None:
        benchmark_dir = self._tempdir / 'benchmarks' / 'lmop_first_combat-benchmark-test'
        batch_one = self._write_batch(
            benchmark_dir / 'batches' / 'scripted' / 'default' / 'seed-1' / 'batch-one',
            batch_id='batch-one',
            policy='scripted',
            seed=1,
            transition_rows=[
                {'sample_id': 'episode-1:1', 'reward': 0.1},
                {'sample_id': 'episode-1:2', 'reward': 0.2},
            ],
            preference_rows=[
                {'pair_id': 'pair-1', 'chosen': '/attack', 'rejected': '/wait'},
            ],
        )
        batch_two = self._write_batch(
            benchmark_dir / 'batches' / 'random' / 'default' / 'seed-2' / 'batch-two',
            batch_id='batch-two',
            policy='random-legal',
            seed=2,
            transition_rows=[
                {'sample_id': 'episode-2:1', 'reward': -0.1},
            ],
            preference_rows=[],
        )
        benchmark_report = {
            'benchmark_id': 'lmop_first_combat-benchmark-test',
            'benchmark_path': str(benchmark_dir / 'benchmark_report.json'),
            'git_commit': 'abc123',
            'manifest_path': 'manifest.json',
            'seed_batch_reports': [
                {'report_path': str(batch_one)},
                {'report_path': str(batch_two)},
            ],
        }
        (benchmark_dir / 'benchmark_report.json').write_text(json.dumps(benchmark_report), encoding='utf-8')

        report = collect_training_datasets([benchmark_dir], output_dir=self._tempdir / 'combined')

        self.assertEqual(report['source_batch_count'], 2)
        self.assertEqual(report['transition_count'], 3)
        self.assertEqual(report['preference_pair_count'], 1)
        transition_rows = [
            json.loads(line)
            for line in Path(report['transition_path']).read_text(encoding='utf-8').splitlines()
        ]
        preference_rows = [
            json.loads(line)
            for line in Path(report['preference_path']).read_text(encoding='utf-8').splitlines()
        ]
        self.assertEqual([row['sample_id'] for row in transition_rows], ['episode-1:1', 'episode-1:2', 'episode-2:1'])
        self.assertEqual([row['pair_id'] for row in preference_rows], ['pair-1'])
        transition_manifest = json.loads(Path(report['transition_manifest_path']).read_text(encoding='utf-8'))
        self.assertEqual(transition_manifest['dataset_type'], 'combined_training_transitions')
        self.assertEqual(transition_manifest['record_count'], 3)
        self.assertEqual(transition_manifest['context']['source_batch_count'], 2)
        self.assertEqual(transition_manifest['context']['policies'], ['scripted', 'random-legal'])
        self.assertEqual(transition_manifest['context']['baseline_seeds'], [1, 2])
        self.assertTrue(Path(report['report_path']).exists())

    def test_collect_training_datasets_can_start_from_benchmark_report_file(self) -> None:
        benchmark_dir = self._tempdir / 'benchmarks' / 'benchmark-from-file'
        batch_report = self._write_batch(
            benchmark_dir / 'batches' / 'scripted' / 'default' / 'seed-3' / 'batch-three',
            batch_id='batch-three',
            policy='scripted',
            seed=3,
            transition_rows=[{'sample_id': 'episode-3:1', 'reward': 1.0}],
            preference_rows=[],
        )
        benchmark_report_path = benchmark_dir / 'benchmark_report.json'
        benchmark_report_path.write_text(
            json.dumps({
                'benchmark_id': 'benchmark-from-file',
                'seed_batch_reports': [{'report_path': str(batch_report)}],
            }),
            encoding='utf-8',
        )

        report = collect_training_datasets(
            [benchmark_report_path],
            output_dir=self._tempdir / 'combined-from-file',
            include_preferences=False,
        )

        self.assertEqual(report['source_batch_count'], 1)
        self.assertEqual(report['transition_count'], 1)
        self.assertNotIn('preference_path', report)

    def _write_batch(
        self,
        batch_dir: Path,
        *,
        batch_id: str,
        policy: str,
        seed: int,
        transition_rows: list[dict],
        preference_rows: list[dict],
    ) -> Path:
        batch_dir.mkdir(parents=True, exist_ok=True)
        transition_path = batch_dir / 'training_transitions.jsonl'
        preference_path = batch_dir / 'preference_pairs.jsonl'
        self._write_jsonl(transition_path, transition_rows)
        self._write_jsonl(preference_path, preference_rows)
        report_path = batch_dir / 'batch_report.json'
        report_path.write_text(
            json.dumps({
                'batch_id': batch_id,
                'scenario_id': 'lmop_first_combat',
                'policy': policy,
                'baseline_seed': seed,
                'character_load_path': 'party.json',
                'llm_player_controllers': [],
                'transition_path': str(transition_path),
                'preference_path': str(preference_path),
                'transition_count': len(transition_rows),
                'preference_pair_count': len(preference_rows),
                'success_rate': 1.0,
                'avg_reward': 1.0,
            }),
            encoding='utf-8',
        )
        return report_path

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )


if __name__ == '__main__':
    unittest.main()
