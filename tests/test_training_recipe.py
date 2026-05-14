from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.training_recipe import (
    TRAINING_RECIPE_SCHEMA_VERSION,
    TrainingRecipeError,
    build_training_recipe,
    render_training_recipe_markdown,
)
from training.training_smoke import TRAINING_SMOKE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainingRecipeTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-recipe-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_training_recipe_plans_supervised_and_preference_objectives(self) -> None:
        smoke_path = self._write_smoke_report()

        recipe = build_training_recipe(
            smoke_path,
            output_dir=self._tempdir / 'recipes',
            recipe_name='unit-recipe',
        )

        self.assertEqual(recipe['schema_version'], TRAINING_RECIPE_SCHEMA_VERSION)
        self.assertEqual(recipe['recipe_mode'], 'dry_run_plan')
        self.assertEqual(recipe['smoke_report_path'], str(smoke_path))
        self.assertEqual(recipe['readiness']['status'], 'ready')
        self.assertEqual(recipe['quality_gate']['failed_check_count'], 0)
        objectives = {item['objective']: item for item in recipe['objectives']}
        self.assertEqual(set(objectives), {'supervised_action_prediction', 'preference_ranking'})
        self.assertAlmostEqual(objectives['supervised_action_prediction']['weight'], 0.6)
        self.assertAlmostEqual(objectives['preference_ranking']['weight'], 0.4)
        self.assertEqual(objectives['supervised_action_prediction']['dataset_path'], 'runs/datasets/latest/combined_training_transitions.jsonl')
        self.assertEqual(objectives['preference_ranking']['dataset_path'], 'runs/datasets/latest/combined_preference_pairs.jsonl')
        self.assertTrue(Path(recipe['recipe_path']).exists())
        self.assertTrue(Path(recipe['markdown_path']).exists())
        markdown = render_training_recipe_markdown(recipe)
        self.assertIn('Training Recipe', markdown)
        self.assertIn('supervised_action_prediction', markdown)

    def test_training_recipe_normalizes_custom_weights(self) -> None:
        smoke_path = self._write_smoke_report()

        recipe = build_training_recipe(
            smoke_path,
            output_dir=self._tempdir / 'recipes',
            objective_mix={
                'supervised_action_prediction': 2.0,
                'preference_ranking': 1.0,
            },
        )

        objectives = {item['objective']: item for item in recipe['objectives']}
        self.assertAlmostEqual(objectives['supervised_action_prediction']['weight'], 2.0 / 3.0)
        self.assertAlmostEqual(objectives['preference_ranking']['weight'], 1.0 / 3.0)

    def test_training_recipe_rejects_failed_smoke_report_by_default(self) -> None:
        smoke_path = self._write_smoke_report(readiness_status='blocked', failed=True)

        with self.assertRaises(TrainingRecipeError):
            build_training_recipe(smoke_path, output_dir=self._tempdir / 'recipes')

    def test_training_recipe_can_record_failed_smoke_when_allowed(self) -> None:
        smoke_path = self._write_smoke_report(readiness_status='blocked', failed=True)

        recipe = build_training_recipe(
            smoke_path,
            output_dir=self._tempdir / 'recipes',
            allow_failed_smoke=True,
        )

        self.assertEqual(recipe['readiness']['status'], 'blocked')
        self.assertEqual(recipe['quality_gate']['failed_check_count'], 1)
        self.assertTrue(Path(recipe['recipe_path']).exists())

    def test_training_recipe_rejects_invalid_objective_weights(self) -> None:
        smoke_path = self._write_smoke_report()

        with self.assertRaises(TrainingRecipeError):
            build_training_recipe(
                smoke_path,
                output_dir=self._tempdir / 'recipes',
                objective_mix={
                    'supervised_action_prediction': 0.0,
                    'preference_ranking': 0.0,
                },
            )

    def _write_smoke_report(self, *, readiness_status: str = 'ready', failed: bool = False) -> Path:
        smoke_path = self._tempdir / 'training_smoke_report.json'
        checks = [
            {'status': 'pass', 'message': f'Readiness status is {readiness_status}.'},
            {'status': 'pass', 'message': 'transition dataset has 10 records.'},
            {'status': 'pass', 'message': 'preference dataset has 4 records.'},
        ]
        if failed:
            checks[-1] = {'status': 'fail', 'message': 'Missing preference dataset.'}
        smoke_path.write_text(
            json.dumps({
                'schema_version': TRAINING_SMOKE_SCHEMA_VERSION,
                'run_id': 'smoke-one',
                'readiness': {
                    'status': readiness_status,
                    'total_record_count': 14,
                    'blocker_count': 1 if readiness_status == 'blocked' else 0,
                    'warning_count': 0,
                },
                'checks': checks,
                'datasets': [
                    {
                        'dataset_name': 'combined_training_transitions.jsonl',
                        'dataset_type': 'combined_training_transitions',
                        'dataset_path': 'runs/datasets/latest/combined_training_transitions.jsonl',
                        'record_count': 10,
                        'manifest_path': 'runs/datasets/latest/combined_training_transitions.jsonl.manifest.json',
                        'quality_path': 'runs/datasets/latest/combined_training_transitions.quality.json',
                        'quality_status': 'pass',
                    },
                    {
                        'dataset_name': 'combined_preference_pairs.jsonl',
                        'dataset_type': 'combined_preference_pairs',
                        'dataset_path': 'runs/datasets/latest/combined_preference_pairs.jsonl',
                        'record_count': 4,
                        'manifest_path': 'runs/datasets/latest/combined_preference_pairs.jsonl.manifest.json',
                        'quality_path': 'runs/datasets/latest/combined_preference_pairs.quality.json',
                        'quality_status': 'pass',
                    },
                ],
            }),
            encoding='utf-8',
        )
        return smoke_path


if __name__ == '__main__':
    unittest.main()
