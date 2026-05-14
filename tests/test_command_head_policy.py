from __future__ import annotations

from collections import Counter
import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.command_head_policy import (
    COMMAND_HEAD_POLICY_SCHEMA_VERSION,
    CommandHeadPolicyError,
    _predict_command,
    _argument_candidates,
    _command_features,
    render_command_head_policy_markdown,
    run_command_head_policy_preflight,
)
from training.supervised_baseline import SUPERVISED_BASELINE_SCHEMA_VERSION
from training.training_recipe import TRAINING_RECIPE_SCHEMA_VERSION


REPO_ROOT = Path(__file__).resolve().parents[1]


class CommandHeadPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.command-head-policy-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_command_head_policy_writes_report_and_heads(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report()

        report = run_command_head_policy_preflight(
            recipe_path,
            baseline_report_path=baseline_path,
            output_dir=self._tempdir / 'runs',
            run_name='unit-command-head',
            epochs=3,
            learning_rate=0.5,
            holdout_fraction=0.25,
        )

        self.assertEqual(report['schema_version'], COMMAND_HEAD_POLICY_SCHEMA_VERSION)
        self.assertEqual(report['run_mode'], 'local_command_head_policy_preflight')
        self.assertTrue(report['trainer_backend']['updates_model_weights'])
        self.assertEqual(report['model']['kind'], 'multi_head_command_policy')
        self.assertIn('command_family', report['model']['heads'])
        self.assertIn('command_arg_1', report['model']['heads'])
        self.assertIn('natural_action', report['model']['heads'])
        self.assertEqual(report['split']['train_records'], 6)
        self.assertEqual(report['split']['eval_records'], 2)
        self.assertIn('action_component_accuracy', report['metrics']['eval'])
        self.assertIn('argument_candidate_coverage', report['metrics']['eval'])
        self.assertIn('baseline_comparison', report)
        self.assertTrue(Path(report['model_path']).exists())
        self.assertTrue(Path(report['report_path']).exists())
        self.assertTrue(Path(report['markdown_path']).exists())
        markdown = render_command_head_policy_markdown(report)
        self.assertIn('Command Head Policy Preflight', markdown)
        self.assertIn('Head Metrics', markdown)

    def test_command_head_policy_rejects_invalid_baseline_schema(self) -> None:
        recipe_path = self._write_recipe()
        baseline_path = self._write_baseline_report(schema_version='wrong')

        with self.assertRaises(CommandHeadPolicyError):
            run_command_head_policy_preflight(
                recipe_path,
                baseline_report_path=baseline_path,
                output_dir=self._tempdir / 'runs',
            )

    def test_combat_command_family_is_constrained_to_available_commands(self) -> None:
        model = {
            'heads': {
                'command_family': {
                    'labels': ['/attack', 'natural:ask'],
                    'weights': {
                        '/attack': Counter({'bias': 1.0}),
                        'natural:ask': Counter({'bias': 5.0}),
                    },
                },
                'command_arg_count': {
                    'labels': ['3'],
                    'weights': {'3': Counter({'bias': 1.0})},
                },
                'command_arg_1': {
                    'labels': ['player-1'],
                    'weights': {'player-1': Counter({'bias': 1.0})},
                },
                'command_arg_2': {
                    'labels': ['sword'],
                    'weights': {'sword': Counter({'bias': 1.0})},
                },
                'command_arg_3': {
                    'labels': ['goblin-2'],
                    'weights': {'goblin-2': Counter({'bias': 1.0})},
                },
                'natural_action': {
                    'labels': ['Ask about the road.'],
                    'weights': {'Ask about the road.': Counter({'bias': 1.0})},
                },
            },
        }
        row = self._transition_row('family-candidate', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-2', scene='ambush')
        row['available_actions'] = [
            {'command': '/attack player-1 sword goblin-2', 'label': 'Attack Goblin Two'},
            {'command': '/dodge player-1', 'label': 'Dodge'},
        ]

        self.assertEqual(_predict_command(row, model), '/attack player-1 sword goblin-2')

    def test_command_arguments_are_constrained_to_available_commands(self) -> None:
        model = {
            'heads': {
                'command_family': {
                    'labels': ['/attack'],
                    'weights': {'/attack': Counter({'bias': 1.0})},
                },
                'command_arg_count': {
                    'labels': ['3'],
                    'weights': {'3': Counter({'bias': 1.0})},
                },
                'command_arg_1': {
                    'labels': ['player-1'],
                    'weights': {'player-1': Counter({'bias': 1.0})},
                },
                'command_arg_2': {
                    'labels': ['sword'],
                    'weights': {'sword': Counter({'bias': 1.0})},
                },
                'command_arg_3': {
                    'labels': ['goblin-9'],
                    'weights': {'goblin-9': Counter({'bias': 5.0})},
                },
            },
        }
        row = self._transition_row('candidate', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-2', scene='ambush')
        row['available_actions'] = [
            {'command': '/attack player-1 sword goblin-2', 'label': 'Attack Goblin Two'},
            {'command': '/dodge player-1', 'label': 'Dodge'},
        ]

        self.assertEqual(_predict_command(row, model), '/attack player-1 sword goblin-2')

    def test_command_features_include_available_option_families(self) -> None:
        row = self._transition_row('features', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-2', scene='ambush')
        row['available_actions'] = [
            {'group_id': 'actions', 'option_id': 'attack', 'label': 'Attack'},
            {'group_id': 'actions', 'option_id': 'dodge', 'label': 'Dodge'},
            {'group_id': 'attacks', 'option_id': 'sword', 'label': 'Longsword'},
        ]

        features = _command_features(row)

        self.assertIn('command_available_family=/attack', features)
        self.assertIn('command_available_family=/dodge', features)
        self.assertIn('command_available_group=attacks', features)

    def test_command_features_include_argument_choice_signals(self) -> None:
        row = self._transition_row('arg-features', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-2', scene='ambush')
        row['available_actions'] = [
            {'group_id': 'attacks', 'option_id': 'dagger-melee-dex', 'label': 'Dagger Melee DEX'},
            {'command': '/attack player-1 dagger-melee-dex monster-goblin-1', 'label': 'Attack Goblin'},
        ]
        row['observation']['summary_lines'].extend([
            'monster-goblin-1: Goblin Ambusher 1 [monster] Pos (4,10,10); Status active',
            'player-1: Player 1 [player] HP 10/10; Status active',
        ])
        row['state_before']['active_actor_side'] = 'player'

        features = _command_features(row)

        self.assertIn('command_attack_option=dagger-melee-dex', features)
        self.assertIn('command_candidate_arg_2=dagger-melee-dex', features)
        self.assertIn('command_candidate_target=monster-goblin-1', features)

    def test_argument_candidates_include_visible_targets(self) -> None:
        row = self._transition_row('target-candidates', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword monster-goblin-1', scene='ambush')
        row['observation']['summary_lines'].extend([
            'monster-goblin-1: Goblin Ambusher 1 [monster] Pos (4,10,10); Status active',
            'monster-goblin-2: Goblin Ambusher 2 [monster] Pos (5,10,10); Status active',
            'player-1: Player 1 [player] HP 10/10; Status active',
        ])
        row['state_before']['active_actor_side'] = 'player'

        candidates = _argument_candidates(row, '/attack', 3, for_decoding=True)

        self.assertIn('monster-goblin-1', candidates)
        self.assertIn('monster-goblin-2', candidates)
        self.assertNotIn('player-1', candidates)

    def test_argument_candidates_report_attack_options(self) -> None:
        row = self._transition_row('weapon-candidates', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 dagger-melee-dex monster-goblin-1', scene='ambush')
        row['available_actions'] = [
            {'group_id': 'attacks', 'option_id': 'dagger-melee-dex', 'label': 'Dagger Melee DEX'},
        ]

        decode_candidates = _argument_candidates(row, '/attack', 2, for_decoding=True)
        report_candidates = _argument_candidates(row, '/attack', 2, for_decoding=False)

        self.assertNotIn('dagger-melee-dex', decode_candidates)
        self.assertIn('dagger-melee-dex', report_candidates)


    def _write_recipe(self) -> Path:
        transition_path = self._tempdir / 'combined_training_transitions.jsonl'
        rows = [
            self._transition_row('001', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-1', scene='ambush'),
            self._transition_row('002', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 sword goblin-1', scene='ambush'),
            self._transition_row('003', runtime_mode='combat', agent_id='player-2-controller', action='/dodge player-2', scene='ambush'),
            self._transition_row('004', runtime_mode='combat', agent_id='player-2-controller', action='/dodge player-2', scene='ambush'),
            self._transition_row('005', runtime_mode='storytelling', agent_id='player-3-controller', action='Ask Gundren about the road.', scene='briefing'),
            self._transition_row('006', runtime_mode='storytelling', agent_id='player-3-controller', action='Ask Gundren about the road.', scene='briefing'),
            self._transition_row('007', runtime_mode='storytelling', agent_id='player-4-controller', action='Inspect the wagon.', scene='briefing'),
            self._transition_row('008', runtime_mode='storytelling', agent_id='player-4-controller', action='Inspect the wagon.', scene='briefing'),
            self._transition_row('009', runtime_mode='combat', agent_id='player-1-controller', action='/attack player-1 missing-weapon goblin-1', scene='ambush', error='The required weapon is not currently equipped or held.'),
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
                'objectives': [{
                    'objective': 'supervised_action_prediction',
                    'weight': 0.6,
                    'dataset_path': str(transition_path),
                    'dataset_type': 'combined_training_transitions',
                    'record_count': len(rows),
                    'quality_status': 'pass',
                    'target': 'action',
                    'input_fields': ['observation', 'available_actions', 'runtime_mode', 'agent_id'],
                }],
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
                    'breakdowns': {'eval': {}},
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
                {'command': '/attack player-1 sword goblin-1', 'label': 'Attack Goblin'},
                {'command': '/dodge player-2', 'label': 'Dodge'},
            ] if runtime_mode == 'combat' else [],
            'state_before': {
                'scene_id': scene,
                'location_id': 'road' if runtime_mode == 'combat' else 'waterdeep',
                'round_number': 1 if runtime_mode == 'combat' else 0,
                'party_hp_current': 30,
                'party_hp_max': 40,
                'monster_hp_current': 20,
                'monster_hp_max': 30,
            },
        }
        if error is not None:
            row['error'] = error
        return row


if __name__ == '__main__':
    unittest.main()
