from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.trainable_policy import (
    TRAINABLE_POLICY_SCHEMA_VERSION,
    TrainablePolicyError,
    render_trainable_policy_markdown,
    run_trainable_policy_preflight,
)
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainablePolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.trainable-policy-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_trainable_policy_preflight_writes_model_and_report(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report()

        report = run_trainable_policy_preflight(
            recipe_path,
            baseline_report_path=baseline_path,
            output_dir=self._tempdir / 'runs',
            run_name='unit-policy',
            epochs=3,
            learning_rate=0.5,
            holdout_fraction=0.25,
        )

        self.assertEqual(report['schema_version'], TRAINABLE_POLICY_SCHEMA_VERSION)
        self.assertEqual(report['run_mode'], 'local_trainable_policy_preflight')
        self.assertTrue(report['trainer_backend']['updates_model_weights'])
        self.assertEqual(report['model']['kind'], 'sparse_linear_action_policy')
        self.assertEqual(report['split']['train_records'], 6)
        self.assertEqual(report['split']['eval_records'], 2)
        self.assertIn('baseline_comparison', report)
        self.assertIn('overall', report['baseline_comparison'])
        self.assertIn('scenario_id', report['metrics']['breakdowns']['eval'])
        self.assertIn('action_family_accuracy', report['metrics']['eval'])
        self.assertIn('action_component_accuracy', report['metrics']['eval'])
        self.assertIn('arg_1', report['metrics']['train']['action_component_accuracy'])
        self.assertIn('command_head_recommendation', report)
        self.assertIn(report['command_head_recommendation']['architecture'], {'single_full_command_head_acceptable', 'multi_head_command_policy'})
        self.assertEqual(report['command_head_recommendation']['heads'][0]['head'], 'command_family')
        self.assertGreater(report['model']['feature_count'], 12)
        self.assertTrue(Path(report['model_path']).exists())
        self.assertTrue(Path(report['report_path']).exists())
        self.assertTrue(Path(report['markdown_path']).exists())
        markdown = render_trainable_policy_markdown(report)
        self.assertIn('Trainable Policy Preflight', markdown)
        self.assertIn('Baseline Comparison', markdown)
        self.assertIn('Family Accuracy', markdown)
        self.assertIn('Component Accuracy', markdown)
        self.assertIn('Command Head Recommendation', markdown)

    def test_trainable_policy_rejects_invalid_baseline_schema(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report(schema_version='wrong')

        with self.assertRaises(TrainablePolicyError):
            run_trainable_policy_preflight(
                recipe_path,
                baseline_report_path=baseline_path,
                output_dir=self._tempdir / 'runs',
            )

    def _write_recipe(self) -> Path:
        transition_path = self._tempdir / 'combined_training_transitions.jsonl'
        rows = [
            self._transition_row('001', runtime_mode='combat', agent_id='player-1-controller', action='/attack goblin', scene='ambush'),
            self._transition_row('002', runtime_mode='combat', agent_id='player-1-controller', action='/attack goblin', scene='ambush'),
            self._transition_row('003', runtime_mode='combat', agent_id='player-2-controller', action='/dodge', scene='ambush'),
            self._transition_row('004', runtime_mode='combat', agent_id='player-2-controller', action='/dodge', scene='ambush'),
            self._transition_row('005', runtime_mode='storytelling', agent_id='player-3-controller', action='Ask Gundren about the road.', scene='briefing'),
            self._transition_row('006', runtime_mode='storytelling', agent_id='player-3-controller', action='Ask Gundren about the road.', scene='briefing'),
            self._transition_row('007', runtime_mode='storytelling', agent_id='player-4-controller', action='Inspect the wagon.', scene='briefing'),
            self._transition_row('008', runtime_mode='storytelling', agent_id='player-4-controller', action='Inspect the wagon.', scene='briefing'),
            self._transition_row('009', runtime_mode='combat', agent_id='player-1-controller', action='/attack missing-weapon', scene='ambush', error='The required weapon is not currently equipped or held.'),
        ]
        transition_path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows),
            encoding='utf-8',
        )
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
                        'record_count': len(rows),
                        'quality_status': 'pass',
                        'target': 'action',
                        'input_fields': ['observation', 'available_actions', 'runtime_mode', 'agent_id'],
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
                'metrics': {
                    'eval': {
                        'record_count': 2,
                        'correct_count': 1,
                        'accuracy': 0.5,
                        'negative_log_likelihood': 1.4,
                    },
                    'breakdowns': {
                        'eval': {
                            'scenario_id': {
                                'unit_combat': {
                                    'record_count': 1,
                                    'correct_count': 0,
                                    'accuracy': 0.0,
                                    'negative_log_likelihood': 2.0,
                                },
                            },
                            'runtime_mode': {
                                'combat': {
                                    'record_count': 1,
                                    'correct_count': 0,
                                    'accuracy': 0.0,
                                    'negative_log_likelihood': 2.0,
                                },
                            },
                        },
                    },
                },
            }),
            encoding='utf-8',
        )
        return baseline_path

    def _transition_row(self, sample_id: str, *, runtime_mode: str, agent_id: str, action: str, scene: str, error: str | None = None) -> dict:
        row = {
            'sample_id': sample_id,
            'agent_id': agent_id,
            'scenario_id': 'unit_combat' if runtime_mode == 'combat' else 'unit_story',
            'source': 'baseline',
            'role': 'player',
            'runtime_mode': runtime_mode,
            'action': action,
            'observation': {
                'summary_lines': [
                    f'Runtime mode: {runtime_mode}',
                    f'Current scene: {scene}',
                    f'Controller: {agent_id}',
                ],
            },
            'available_actions': [
                {'command': '/attack goblin', 'label': 'Attack Goblin'},
                {'command': '/dodge', 'label': 'Dodge'},
            ] if runtime_mode == 'combat' else [],
            'state_before': {
                'scene_id': scene,
                'location_id': 'road' if runtime_mode == 'combat' else 'waterdeep',
                'round_number': 1 if runtime_mode == 'combat' else 0,
                'party_hp_current': 30,
                'party_hp_max': 40,
                'monster_hp_current': 20,
                'monster_hp_max': 30,
                'living_monster_count': 2,
                'living_party_count': 4,
                'active_actor_id': agent_id.replace('-controller', ''),
                'event_count': 5,
            },
        }
        if error is not None:
            row['error'] = error
        return row


if __name__ == '__main__':
    unittest.main()
