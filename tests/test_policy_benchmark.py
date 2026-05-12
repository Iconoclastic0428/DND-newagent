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

from run_policy_benchmark import run_policy_benchmark
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
            max_combat_turns=120,
        )

        benchmark_path = Path(report['benchmark_path'])
        comparison_path = Path(report['comparison_path'])
        self.assertTrue(benchmark_path.exists())
        self.assertTrue(comparison_path.exists())
        saved = json.loads(benchmark_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['episodes_per_policy'], 1)
        self.assertEqual(saved['baseline_seed'], 5)
        self.assertEqual(len(saved['batch_reports']), 2)
        self.assertEqual(saved['comparison']['comparison_count'], 2)
        self.assertEqual([row['label'] for row in saved['comparison']['rows']], ['scripted', 'random'])
        self.assertIn(saved['comparison']['diagnostics']['winner_label'], {'scripted', 'random'})
        self.assertEqual(len(saved['comparison']['diagnostics']['policy_notes']), 2)
        for batch in saved['batch_reports']:
            self.assertTrue(Path(batch['report_path']).exists())
            self.assertEqual(batch['success_rate'], 1.0)


if __name__ == '__main__':
    unittest.main()
