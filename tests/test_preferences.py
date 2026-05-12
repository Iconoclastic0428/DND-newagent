from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.preferences import build_preference_pairs, context_signature, load_preference_pairs, write_preference_pairs_jsonl


REPO_ROOT = Path(__file__).resolve().parents[1]


def _transition(*, sample_id: str, action: str, reward: float, error: str | None = None) -> dict:
    observation = {
        'summary_lines': ['Runtime mode: combat', 'Player 1 is up.', 'A goblin is wounded.'],
        'prompt': None,
    }
    available_actions = [
        {'group_id': 'spells', 'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'guaranteed force damage'},
        {'group_id': 'turn', 'option_id': 'endturn', 'label': 'End Turn', 'detail': ''},
    ]
    return {
        'sample_id': sample_id,
        'episode_id': sample_id.split(':', 1)[0],
        'scenario_id': 'lmop_first_combat',
        'agent_id': 'player-1-controller',
        'source': 'llm_player',
        'runtime_mode': 'combat',
        'acting_actor_id': 'player-1',
        'observation': observation,
        'available_actions': available_actions,
        'state_before': {
            'runtime_mode': 'combat',
            'scene_id': 'scene-triboar-goblin-ambush',
            'location_id': 'triboar-trail',
            'round_number': 1,
            'encounter_phase': 'in-progress',
            'active_actor_id': 'player-1',
        },
        'action': action,
        'reward': reward,
        'action_reward': reward,
        'terminal_reward': 0.0,
        'reward_channels': {'offense': reward} if reward > 0 else {'validity': reward},
        'error': error,
    }


class PreferencePairTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.preference-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_build_preference_pairs_uses_matching_context_and_reward_gap(self) -> None:
        chosen = _transition(sample_id='episode-1:5', action='/cast player-1 magic-missile monster-goblin-1', reward=0.31)
        rejected = _transition(sample_id='episode-2:5', action='/endturn player-1', reward=0.01)
        unrelated = _transition(sample_id='episode-3:5', action='/cast player-1 fire-bolt monster-goblin-1', reward=0.4)
        unrelated['state_before']['round_number'] = 2

        pairs = build_preference_pairs([chosen, rejected, unrelated], min_reward_gap=0.05)

        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair['context_signature'], context_signature(chosen))
        self.assertEqual(pair['chosen'], '/cast player-1 magic-missile monster-goblin-1')
        self.assertEqual(pair['rejected'], '/endturn player-1')
        self.assertAlmostEqual(pair['reward_gap'], 0.3)
        self.assertEqual(pair['chosen_sample_id'], 'episode-1:5')
        self.assertEqual(pair['rejected_sample_id'], 'episode-2:5')
        self.assertIn('Available actions:', pair['prompt'])
        self.assertEqual(pair['chosen_metadata']['reward_channels'], {'offense': 0.31})

    def test_preference_pairs_can_include_or_exclude_errors(self) -> None:
        chosen = _transition(sample_id='episode-1:5', action='/cast player-1 magic-missile monster-goblin-1', reward=0.31)
        rejected = _transition(sample_id='episode-2:5', action='/dance player-1', reward=-1.0, error='Unknown command')

        included = build_preference_pairs([chosen, rejected], min_reward_gap=0.05, include_errors=True)
        excluded = build_preference_pairs([chosen, rejected], min_reward_gap=0.05, include_errors=False)

        self.assertEqual(len(included), 1)
        self.assertEqual(included[0]['rejected'], '/dance player-1')
        self.assertEqual(excluded, [])

    def test_write_and_load_preference_pairs_jsonl(self) -> None:
        output_path = self._tempdir / 'preference_pairs.jsonl'
        pairs = [{'pair_id': 'pair-1', 'chosen': '/say yes', 'rejected': '/say no'}]

        write_preference_pairs_jsonl(pairs, output_path)

        self.assertEqual(load_preference_pairs(output_path), pairs)
        rows = [json.loads(line) for line in output_path.read_text(encoding='utf-8').splitlines()]
        self.assertEqual(rows, pairs)


if __name__ == '__main__':
    unittest.main()
