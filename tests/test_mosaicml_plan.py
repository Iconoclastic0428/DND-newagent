from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.mosaicml_plan import (
    MOSAICML_TRAINING_PLAN_SCHEMA_VERSION,
    MosaicMLPlanError,
    build_mosaicml_training_plan,
    render_mosaicml_plan_markdown,
)
from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class MosaicMLPlanTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.mosaicml-plan-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_mosaicml_plan_records_gpu_handoff_and_baseline_targets(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report()

        plan = build_mosaicml_training_plan(
            recipe_path,
            baseline_report_path=baseline_path,
            output_dir=self._tempdir / 'plans',
            plan_name='unit-mosaic',
            gpu_type='a100',
            container_image='custom/image:latest',
        )

        self.assertEqual(plan['schema_version'], MOSAICML_TRAINING_PLAN_SCHEMA_VERSION)
        self.assertEqual(plan['platform']['name'], 'mosaicml')
        self.assertEqual(plan['platform']['accelerator'], 'gpu')
        self.assertEqual(plan['platform']['gpu_type'], 'a100')
        self.assertEqual(plan['platform']['container_image'], 'custom/image:latest')
        self.assertEqual(plan['recipe_id'], 'recipe-one')
        self.assertEqual(plan['baseline']['overall_eval']['accuracy'], 0.7)
        self.assertEqual(plan['objectives'][0]['objective'], 'supervised_action_prediction')
        self.assertEqual(plan['improvement_targets'][0]['field'], 'scenario_id')
        self.assertEqual(plan['improvement_targets'][0]['value'], 'lmop_first_combat')
        self.assertEqual(plan['improvement_targets'][0]['accuracy'], 0.25)
        self.assertIn('train_policy_mosaicml.py', plan['launch']['planned_command'])
        self.assertTrue(Path(plan['plan_path']).exists())
        self.assertTrue(Path(plan['markdown_path']).exists())
        markdown = render_mosaicml_plan_markdown(plan)
        self.assertIn('MosaicML Training Plan', markdown)
        self.assertIn('lmop_first_combat', markdown)

    def test_mosaicml_plan_rejects_invalid_baseline_schema(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report(schema_version='wrong')

        with self.assertRaises(MosaicMLPlanError):
            build_mosaicml_training_plan(
                recipe_path,
                baseline_report_path=baseline_path,
                output_dir=self._tempdir / 'plans',
            )

    def _write_recipe(self) -> Path:
        recipe_path = self._tempdir / 'training_recipe.json'
        recipe_path.write_text(
            json.dumps({
                'schema_version': TRAINING_RECIPE_SCHEMA_VERSION,
                'recipe_id': 'recipe-one',
                'objectives': [
                    {
                        'objective': 'supervised_action_prediction',
                        'weight': 0.6,
                        'dataset_path': 'runs/datasets/latest/combined_training_transitions.jsonl',
                        'dataset_type': 'combined_training_transitions',
                        'record_count': 10,
                        'quality_status': 'pass',
                        'target': 'action',
                        'input_fields': ['observation', 'available_actions', 'runtime_mode', 'agent_id'],
                    },
                    {
                        'objective': 'preference_ranking',
                        'weight': 0.4,
                        'dataset_path': 'runs/datasets/latest/combined_preference_pairs.jsonl',
                        'dataset_type': 'combined_preference_pairs',
                        'record_count': 4,
                        'quality_status': 'pass',
                        'target': 'chosen_over_rejected',
                        'input_fields': ['prompt', 'chosen', 'rejected', 'reward_gap'],
                    },
                ],
            }),
            encoding='utf-8',
        )
        return recipe_path

    def _write_baseline_report(self, *, schema_version: str = SUPERVISED_BASELINE_SCHEMA_VERSION) -> Path:
        baseline_path = self._tempdir / 'supervised_baseline_report.json'
        baseline_path.write_text(
            json.dumps({
                'schema_version': schema_version,
                'run_id': 'baseline-one',
                'recipe_id': 'recipe-one',
                'split': {
                    'strategy': 'hash',
                    'total_records': 14,
                    'train_records': 11,
                    'eval_records': 3,
                },
                'metrics': {
                    'eval': {
                        'record_count': 3,
                        'correct_count': 2,
                        'accuracy': 0.7,
                        'negative_log_likelihood': 1.2,
                    },
                    'breakdowns': {
                        'eval': {
                            'runtime_mode': {
                                'combat': {
                                    'record_count': 2,
                                    'correct_count': 1,
                                    'accuracy': 0.5,
                                    'negative_log_likelihood': 1.6,
                                },
                                'storytelling': {
                                    'record_count': 1,
                                    'correct_count': 1,
                                    'accuracy': 1.0,
                                    'negative_log_likelihood': 0.2,
                                },
                            },
                            'scenario_id': {
                                'lmop_first_combat': {
                                    'record_count': 2,
                                    'correct_count': 0,
                                    'accuracy': 0.25,
                                    'negative_log_likelihood': 2.1,
                                },
                            },
                        },
                    },
                },
            }),
            encoding='utf-8',
        )
        return baseline_path


if __name__ == '__main__':
    unittest.main()
