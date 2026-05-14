from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_policy_benchmark import run_policy_benchmark, run_policy_benchmark_from_manifest
from session_server.bootstrap import build_default_character_record
from shared_types.character_record_io import save_character_party
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class PolicyBenchmarkTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.policy-benchmark-tests' / uuid4().hex
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

    def test_policy_benchmark_runs_batches_and_writes_comparison(self) -> None:
        report = run_policy_benchmark(
            episodes=1,
            output_dir=self._tempdir / 'benchmarks',
            policies=('scripted', 'random=random-legal'),
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
            baseline_seed=5,
            seeds=(5, 6),
            max_combat_turns=120,
        )

        benchmark_path = Path(report['benchmark_path'])
        comparison_path = Path(report['comparison_path'])
        markdown_summary_path = Path(report['markdown_summary_path'])
        self.assertTrue(benchmark_path.exists())
        self.assertTrue(comparison_path.exists())
        self.assertTrue(markdown_summary_path.exists())
        saved = json.loads(benchmark_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['episodes_per_seed'], 1)
        self.assertEqual(saved['episodes_per_policy'], 2)
        self.assertEqual(saved['baseline_seed'], 5)
        self.assertEqual(saved['seed_count'], 2)
        self.assertEqual(saved['seeds'], [5, 6])
        self.assertEqual(saved['markdown_summary_path'], str(markdown_summary_path))
        self.assertEqual(len(saved['batch_reports']), 2)
        self.assertEqual(len(saved['seed_batch_reports']), 4)
        self.assertEqual(saved['comparison']['comparison_count'], 2)
        self.assertEqual(saved['comparison']['benchmark_metadata']['seed_count'], 2)
        self.assertEqual([row['label'] for row in saved['comparison']['rows']], ['scripted', 'random'])
        self.assertIn(saved['comparison']['diagnostics']['winner_label'], {'scripted', 'random'})
        self.assertEqual(len(saved['comparison']['diagnostics']['policy_notes']), 2)
        markdown = markdown_summary_path.read_text(encoding='utf-8')
        self.assertIn('# Policy Benchmark Summary', markdown)
        self.assertIn('Seeds: 5, 6', markdown)
        self.assertIn('## Leaderboard', markdown)
        for batch in saved['batch_reports']:
            self.assertEqual(batch['seed_count'], 2)
            self.assertIn('avg_reward_stddev', batch)
            self.assertEqual(batch['success_rate'], 1.0)
            for report_path in batch['report_paths']:
                self.assertTrue(Path(report_path).exists())

    def test_policy_benchmark_runs_from_manifest(self) -> None:
        default_party_path = self._tempdir / 'saved-party.json'
        alternate_party_path = self._tempdir / 'alternate-party.json'
        self._write_saved_party(default_party_path)
        self._write_saved_party(alternate_party_path)
        manifest_path = self._tempdir / 'benchmark-manifest.json'
        manifest_path.write_text(
            json.dumps({
                'episodes': 1,
                'output_dir': 'manifest-benchmarks',
                'scenario_id': 'lmop_first_combat',
                'env_path': '.env',
                'base_url': LOCAL_MIRROR_BASE_URL,
                'max_combat_turns': 120,
                'seeds': [7],
                'character_loadouts': {
                    'default-party': 'saved-party.json',
                    'alternate-party': 'alternate-party.json',
                },
                'character_loadout_scenarios': [
                    'default-party',
                    {'label': 'alternate-party', 'character_loadout': 'alternate-party'},
                ],
                'policies': [
                    'scripted',
                    {'label': 'random', 'policy': 'random-legal'},
                ],
            }),
            encoding='utf-8',
        )

        report = run_policy_benchmark_from_manifest(manifest_path)

        benchmark_path = Path(report['benchmark_path'])
        self.assertTrue(benchmark_path.exists())
        saved = json.loads(benchmark_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['manifest_path'], str(manifest_path))
        self.assertEqual(saved['seed_count'], 1)
        self.assertEqual(saved['seeds'], [7])
        self.assertEqual(saved['character_loadout_count'], 2)
        self.assertEqual(saved['episodes_per_policy'], 2)
        self.assertEqual(
            [loadout['label'] for loadout in saved['character_loadouts']],
            ['default-party', 'alternate-party'],
        )
        self.assertEqual([batch['label'] for batch in saved['batch_reports']], ['scripted', 'random'])
        self.assertEqual(len(saved['seed_batch_reports']), 4)
        for batch in saved['batch_reports']:
            self.assertEqual(batch['loadout_count'], 2)
            self.assertEqual(batch['character_loadout_labels'], ['default-party', 'alternate-party'])
            self.assertEqual(
                batch['character_load_paths'],
                [str(default_party_path), str(alternate_party_path)],
            )
        self.assertEqual(saved['seed_batch_reports'][0]['character_loadout_label'], 'default-party')
        self.assertEqual(saved['seed_batch_reports'][0]['character_load_path'], str(default_party_path))
        self.assertEqual(saved['seed_batch_reports'][1]['character_loadout_label'], 'alternate-party')
        self.assertEqual(saved['seed_batch_reports'][1]['character_load_path'], str(alternate_party_path))
        self.assertEqual(saved['comparison']['benchmark_metadata']['loadout_count'], 2)
        self.assertTrue(Path(saved['markdown_summary_path']).exists())

    def _write_saved_party(self, path: Path) -> None:
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        save_character_party(
            path,
            {
                'player-1-controller': record,
                'player-2-controller': record,
                'player-3-controller': record,
                'player-4-controller': record,
            },
        )


if __name__ == '__main__':
    unittest.main()
