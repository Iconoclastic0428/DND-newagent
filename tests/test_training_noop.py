from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.training_noop import (
    TRAINING_RUN_SCHEMA_VERSION,
    TrainingNoOpError,
    render_noop_training_markdown,
    run_noop_training_epoch,
)
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainingNoOpTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-noop-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_noop_training_epoch_accounts_for_recipe_objectives(self) -> None:
        recipe_path = self._write_recipe()

        report = run_noop_training_epoch(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            run_name='unit-noop',
        )

        self.assertEqual(report['schema_version'], TRAINING_RUN_SCHEMA_VERSION)
        self.assertEqual(report['run_mode'], 'noop_epoch')
        self.assertFalse(report['trainer_backend']['updates_model_weights'])
        self.assertEqual(report['totals']['objective_count'], 2)
        self.assertEqual(report['totals']['planned_records'], 5)
        self.assertEqual(report['totals']['observed_records'], 5)
        self.assertEqual(report['totals']['consumed_records'], 5)
        self.assertEqual(report['totals']['failed_objective_count'], 0)
        self.assertEqual({item['status'] for item in report['objectives']}, {'pass'})
        self.assertTrue(Path(report['report_path']).exists())
        self.assertTrue(Path(report['markdown_path']).exists())
        markdown = render_noop_training_markdown(report)
        self.assertIn('No-Op Training Run', markdown)
        self.assertIn('supervised_action_prediction', markdown)

    def test_noop_training_epoch_can_cap_consumed_rows(self) -> None:
        recipe_path = self._write_recipe()

        report = run_noop_training_epoch(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            max_records_per_objective=1,
        )

        self.assertEqual(report['totals']['observed_records'], 5)
        self.assertEqual(report['totals']['consumed_records'], 2)
        self.assertEqual({item['consumed_records'] for item in report['objectives']}, {1})

    def test_noop_training_epoch_rejects_record_mismatch_by_default(self) -> None:
        recipe_path = self._write_recipe(planned_transition_records=99)

        with self.assertRaises(TrainingNoOpError):
            run_noop_training_epoch(recipe_path, output_dir=self._tempdir / 'runs')

    def test_noop_training_epoch_can_record_mismatch_when_allowed(self) -> None:
        recipe_path = self._write_recipe(planned_transition_records=99)

        report = run_noop_training_epoch(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            allow_record_mismatch=True,
        )

        self.assertEqual(report['totals']['failed_objective_count'], 1)
        failed = [item for item in report['objectives'] if item['status'] == 'fail']
        self.assertEqual(failed[0]['planned_records'], 99)
        self.assertEqual(failed[0]['observed_records'], 3)

    def _write_recipe(self, *, planned_transition_records: int = 3) -> Path:
        transition_path = self._tempdir / 'combined_training_transitions.jsonl'
        preference_path = self._tempdir / 'combined_preference_pairs.jsonl'
        self._write_jsonl(transition_path, [{'sample_id': 'one'}, {'sample_id': 'two'}, {'sample_id': 'three'}])
        self._write_jsonl(preference_path, [{'pair_id': 'one'}, {'pair_id': 'two'}])
        recipe_path = self._tempdir / 'training_recipe.json'
        recipe_path.write_text(
            json.dumps({
                'schema_version': TRAINING_RECIPE_SCHEMA_VERSION,
                'recipe_id': 'recipe-one',
                'objectives': [
                    {
                        'objective': 'supervised_action_prediction',
                        'weight': 0.6,
                        'dataset_path': str(transition_path),
                        'dataset_type': 'combined_training_transitions',
                        'record_count': planned_transition_records,
                        'quality_status': 'pass',
                        'target': 'action',
                        'input_fields': ['observation', 'available_actions'],
                    },
                    {
                        'objective': 'preference_ranking',
                        'weight': 0.4,
                        'dataset_path': str(preference_path),
                        'dataset_type': 'combined_preference_pairs',
                        'record_count': 2,
                        'quality_status': 'pass',
                        'target': 'chosen_over_rejected',
                        'input_fields': ['prompt', 'chosen', 'rejected'],
                    },
                ],
            }),
            encoding='utf-8',
        )
        return recipe_path

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )


if __name__ == '__main__':
    unittest.main()
