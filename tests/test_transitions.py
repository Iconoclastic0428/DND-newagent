from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.transitions import build_training_transitions, write_training_transitions_jsonl


REPO_ROOT = Path(__file__).resolve().parents[1]


class TrainingTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.transition-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_build_training_transitions_exports_player_decisions_with_terminal_reward(self) -> None:
        records = [
            {
                'record_type': 'episode_started',
                'episode_id': 'episode-1',
                'scenario_id': 'scenario-1',
                'turn_index': 0,
                'source': 'system',
            },
            {
                'record_type': 'turn',
                'episode_id': 'episode-1',
                'scenario_id': 'scenario-1',
                'turn_index': 1,
                'agent_id': 'player-1-controller',
                'role': 'player',
                'source': 'llm_player',
                'runtime_mode': 'combat',
                'raw_text': '/cast player-1 magic-missile monster-goblin-1',
                'parsed_action': {'kind': 'command', 'command': '/cast'},
                'observation': {
                    'summary_lines': ['Player 1 turn.'],
                    'available_choices': {
                        'spells': [
                            {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': '1st-level spell'}
                        ]
                    },
                },
                'post_observation': {'summary_lines': ['Goblin is hurt.']},
                'state_before': {'runtime_mode': 'combat', 'party_hp_current': 20, 'party_hp_max': 20},
                'state_after': {'runtime_mode': 'combat', 'party_hp_current': 20, 'party_hp_max': 20},
                'reward_components': {'valid_action': 0.01, 'enemy_damage': 0.2},
                'metadata': {'reward_total': 0.21},
            },
            {
                'record_type': 'turn',
                'episode_id': 'episode-1',
                'scenario_id': 'scenario-1',
                'turn_index': 2,
                'agent_id': 'dm',
                'role': 'dm',
                'source': 'human',
                'runtime_mode': 'combat',
                'raw_text': '/endturn monster-goblin-1',
                'reward_components': {'valid_action': 0.01},
                'metadata': {'reward_total': 0.01},
            },
            {
                'record_type': 'turn',
                'episode_id': 'episode-1',
                'scenario_id': 'scenario-1',
                'turn_index': 3,
                'agent_id': 'player-2-controller',
                'role': 'player',
                'source': 'human',
                'runtime_mode': 'combat',
                'raw_text': '/cast player-2 fire-bolt monster-goblin-1',
                'parsed_action': {'kind': 'command', 'command': '/cast'},
                'observation': {'summary_lines': ['Player 2 turn.'], 'available_action_groups': ['attacks']},
                'post_observation': {'summary_lines': ['Combat complete.']},
                'reward_components': {'valid_action': 0.01, 'enemy_defeated': 0.5},
                'metadata': {'reward_total': 0.51},
            },
            {
                'record_type': 'episode_completed',
                'episode_id': 'episode-1',
                'scenario_id': 'scenario-1',
                'turn_index': 4,
                'runtime_mode': 'demo-complete',
                'source': 'system',
                'reward_components': {'episode_success': 1.0, 'party_survival': 0.5},
                'metadata': {'reward_total': 1.5, 'success': True},
            },
        ]

        transitions = build_training_transitions(records)

        self.assertEqual(len(transitions), 2)
        first, second = transitions
        self.assertEqual(first['sample_id'], 'episode-1:1')
        self.assertEqual(first['agent_id'], 'player-1-controller')
        self.assertEqual(first['action_reward'], 0.21)
        self.assertEqual(first['terminal_reward'], 0.0)
        self.assertEqual(first['reward'], 0.21)
        self.assertFalse(first['done'])
        self.assertEqual(
            first['available_actions'],
            [{'group_id': 'spells', 'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': '1st-level spell'}],
        )
        self.assertEqual(second['agent_id'], 'player-2-controller')
        self.assertEqual(second['action_reward'], 0.51)
        self.assertEqual(second['terminal_reward'], 1.5)
        self.assertEqual(second['reward'], 2.01)
        self.assertTrue(second['done'])
        self.assertTrue(second['success'])
        self.assertEqual(second['available_actions'], [{'group_id': 'attacks', 'option_id': '', 'label': '', 'detail': ''}])

    def test_write_training_transitions_jsonl_round_trips(self) -> None:
        output_path = self._tempdir / 'transitions.jsonl'
        transitions = [{'sample_id': 'episode-1:1', 'reward': 1.0}]

        write_training_transitions_jsonl(transitions, output_path)

        rows = [json.loads(line) for line in output_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows, transitions)


if __name__ == '__main__':
    unittest.main()
