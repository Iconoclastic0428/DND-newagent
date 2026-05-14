from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.supervised_baseline import (
    SUPERVISED_BASELINE_SCHEMA_VERSION,
    SupervisedBaselineError,
    render_supervised_baseline_markdown,
    run_supervised_action_baseline,
)
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class SupervisedBaselineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.supervised-baseline-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_supervised_baseline_writes_metrics_and_model_artifact(self) -> None:
        recipe_path = self._write_recipe()

        report = run_supervised_action_baseline(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            run_name='unit-baseline',
            holdout_fraction=0.25,
        )

        self.assertEqual(report['schema_version'], SUPERVISED_BASELINE_SCHEMA_VERSION)
        self.assertEqual(report['run_mode'], 'supervised_action_frequency_baseline')
        self.assertEqual(report['objective'], 'supervised_action_prediction')
        self.assertEqual(report['split']['total_records'], 8)
        self.assertEqual(report['split']['train_records'], 6)
        self.assertEqual(report['split']['eval_records'], 2)
        self.assertEqual(report['split']['strategy'], 'hash')
        self.assertIn('runtime_mode_counts', report['split']['coverage']['train'])
        self.assertIn('runtime_mode_counts', report['split']['coverage']['eval'])
        self.assertGreaterEqual(len(report['split']['coverage']['eval']['runtime_mode_counts']), 1)
        self.assertEqual(report['metrics']['train']['record_count'], 6)
        self.assertEqual(report['metrics']['eval']['record_count'], 2)
        self.assertIsInstance(report['metrics']['eval']['accuracy'], float)
        self.assertIsInstance(report['metrics']['eval']['negative_log_likelihood'], float)
        breakdowns = report['metrics']['breakdowns']
        self.assertIn('scenario_id', breakdowns['eval'])
        seen_scenarios = set(breakdowns['train']['scenario_id']) | set(breakdowns['eval']['scenario_id'])
        self.assertEqual(seen_scenarios, {'lmop_first_combat', 'lmop_story_opening_choices'})
        self.assertTrue(Path(report['model_path']).exists())
        self.assertTrue(Path(report['report_path']).exists())
        self.assertTrue(Path(report['markdown_path']).exists())
        markdown = render_supervised_baseline_markdown(report)
        self.assertIn('Supervised Action Baseline', markdown)
        self.assertIn('Negative Log Loss', markdown)
        self.assertIn('Evaluation Breakdown', markdown)

    def test_supervised_baseline_supports_max_records(self) -> None:
        recipe_path = self._write_recipe()

        report = run_supervised_action_baseline(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            max_records=4,
            holdout_fraction=0.25,
        )

        self.assertEqual(report['split']['total_records'], 4)
        self.assertEqual(report['split']['train_records'], 3)
        self.assertEqual(report['split']['eval_records'], 1)

    def test_supervised_baseline_supports_tail_split_for_comparison(self) -> None:
        recipe_path = self._write_recipe()

        report = run_supervised_action_baseline(
            recipe_path,
            output_dir=self._tempdir / 'runs',
            holdout_fraction=0.25,
            split_strategy='tail',
        )

        self.assertEqual(report['split']['strategy'], 'tail')
        self.assertEqual(report['split']['train_records'], 6)
        self.assertEqual(report['split']['eval_records'], 2)

    def test_supervised_baseline_rejects_recipe_without_supervised_objective(self) -> None:
        recipe_path = self._write_recipe(include_supervised=False)

        with self.assertRaises(SupervisedBaselineError):
            run_supervised_action_baseline(recipe_path, output_dir=self._tempdir / 'runs')

    def test_supervised_baseline_rejects_invalid_holdout(self) -> None:
        recipe_path = self._write_recipe()

        with self.assertRaises(SupervisedBaselineError):
            run_supervised_action_baseline(
                recipe_path,
                output_dir=self._tempdir / 'runs',
                holdout_fraction=1.0,
            )

    def test_supervised_baseline_rejects_invalid_split_strategy(self) -> None:
        recipe_path = self._write_recipe()

        with self.assertRaises(SupervisedBaselineError):
            run_supervised_action_baseline(
                recipe_path,
                output_dir=self._tempdir / 'runs',
                split_strategy='middle',
            )

    def _write_recipe(self, *, include_supervised: bool = True) -> Path:
        transition_path = self._tempdir / 'combined_training_transitions.jsonl'
        rows = [
            self._transition_row('001', runtime_mode='combat', agent_id='player-1-controller', action='/attack goblin'),
            self._transition_row('002', runtime_mode='combat', agent_id='player-1-controller', action='/attack goblin'),
            self._transition_row('003', runtime_mode='combat', agent_id='player-1-controller', action='/attack goblin'),
            self._transition_row('004', runtime_mode='combat', agent_id='player-1-controller', action='/dodge'),
            self._transition_row('005', runtime_mode='storytelling', agent_id='player-2-controller', action='Ask Sildar about danger.'),
            self._transition_row('006', runtime_mode='storytelling', agent_id='player-2-controller', action='Ask Sildar about danger.'),
            self._transition_row('007', runtime_mode='storytelling', agent_id='player-2-controller', action='Inspect the wagon.'),
            self._transition_row('008', runtime_mode='storytelling', agent_id='player-2-controller', action='Ask Sildar about danger.'),
            self._transition_row('009', runtime_mode='combat', agent_id='player-1-controller', action='/attack missing-weapon', error='The required weapon is not currently equipped or held.'),
        ]
        self._write_jsonl(transition_path, rows)
        objectives = []
        if include_supervised:
            objectives.append({
                'objective': 'supervised_action_prediction',
                'weight': 0.6,
                'dataset_path': str(transition_path),
                'dataset_type': 'combined_training_transitions',
                'record_count': len(rows),
                'quality_status': 'pass',
                'target': 'action',
                'input_fields': ['observation', 'available_actions'],
            })
        else:
            objectives.append({
                'objective': 'preference_ranking',
                'weight': 1.0,
                'dataset_path': str(self._tempdir / 'preferences.jsonl'),
                'dataset_type': 'combined_preference_pairs',
                'record_count': 0,
                'quality_status': 'pass',
                'target': 'chosen_over_rejected',
                'input_fields': ['prompt', 'chosen', 'rejected'],
            })
        recipe_path = self._tempdir / 'training_recipe.json'
        recipe_path.write_text(
            json.dumps({
                'schema_version': TRAINING_RECIPE_SCHEMA_VERSION,
                'recipe_id': 'recipe-one',
                'objectives': objectives,
            }),
            encoding='utf-8',
        )
        return recipe_path

    def _transition_row(self, sample_id: str, *, runtime_mode: str, agent_id: str, action: str, error: str | None = None) -> dict:
        row = {
            'sample_id': sample_id,
            'agent_id': agent_id,
            'scenario_id': 'lmop_first_combat' if runtime_mode == 'combat' else 'lmop_story_opening_choices',
            'source': 'baseline',
            'runtime_mode': runtime_mode,
            'action': action,
            'reward': 0.1,
            'action_reward': 0.1,
            'terminal_reward': 0.0,
            'observation': {'summary_lines': ['test']},
            'available_actions': [],
            'reward_channels': {'validity': 0.1},
        }
        if error is not None:
            row['error'] = error
        return row

    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )


if __name__ == '__main__':
    unittest.main()
