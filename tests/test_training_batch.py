from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

from training.trajectory_summary import summarize_batch, summarize_trajectory

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_training_batch import run_batch
from session_server.llm_player import LLMPlayerDecision
from shared_types.encounter_models import ActorSide
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class FakeCombatLLMPlayerAgent:
    def __init__(self, controller_id: str) -> None:
        self.controller_id = controller_id
        self.label = f'fake-{controller_id}'

    def decide(self, story_session) -> LLMPlayerDecision | None:
        state = story_session.state
        active_actor_id = state.active_actor_id
        if active_actor_id is None:
            return None
        owner = story_session.encounter_session.control_runtime.controller_for_actor(active_actor_id)
        if owner != self.controller_id:
            return None
        actor = state.actors[active_actor_id]
        if actor.action_available:
            target = next(
                (
                    candidate
                    for candidate in state.actors.values()
                    if candidate.side == ActorSide.MONSTER and candidate.current_hit_points > 0
                ),
                None,
            )
            if target is not None and 'magic-missile' in actor.spells:
                return LLMPlayerDecision(
                    self.controller_id,
                    f'/cast {active_actor_id} magic-missile {target.actor_id}',
                    'Use guaranteed damage against the nearest living enemy.',
                )
            if target is not None and 'fire-bolt' in actor.spells:
                return LLMPlayerDecision(
                    self.controller_id,
                    f'/cast {active_actor_id} fire-bolt {target.actor_id}',
                    'Use a basic ranged attack against the nearest living enemy.',
                )
        return LLMPlayerDecision(
            self.controller_id,
            f'/endturn {active_actor_id}',
            'End the turn after available combat actions are spent.',
        )


class TrainingBatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.training-batch-tests' / uuid4().hex
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

    def test_summarize_trajectory_counts_rewards_errors_and_terminal_state(self) -> None:
        records = [
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'episode_started',
                'source': 'system',
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'turn',
                'agent_id': 'player-1-controller',
                'source': 'human',
                'reward_components': {'valid_action': 0.01},
                'metadata': {'reward_total': 0.01},
                'state_after': {'runtime_mode': 'combat', 'scene_id': 'scene-1', 'party_hp_current': 10, 'party_hp_max': 20},
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'turn',
                'agent_id': 'player-2-controller',
                'source': 'llm_player',
                'reward_components': {'invalid_action': -1.0},
                'metadata': {'reward_total': -1.0},
                'error': 'bad command',
                'state_after': {'runtime_mode': 'combat', 'scene_id': 'scene-1', 'party_hp_current': 10, 'party_hp_max': 20},
            },
            {
                'episode_id': 'episode-1',
                'scenario_id': 'scenario',
                'record_type': 'episode_completed',
                'runtime_mode': 'demo-complete',
                'source': 'system',
                'reward_components': {'episode_success': 1.0, 'party_survival': 0.5},
                'metadata': {
                    'reward_total': 1.5,
                    'success': True,
                    'winning_side': 'player',
                    'round_number': 2,
                    'party_hp_current': 10,
                    'party_hp_max': 20,
                    'living_party_count': 4,
                    'living_monster_count': 0,
                },
            },
        ]

        summary = summarize_trajectory(records)

        self.assertEqual(summary['episode_id'], 'episode-1')
        self.assertEqual(summary['turn_count'], 2)
        self.assertEqual(summary['invalid_action_count'], 1)
        self.assertEqual(summary['total_reward'], 0.51)
        self.assertTrue(summary['success'])
        self.assertEqual(summary['terminal']['party_hp_ratio'], 0.5)
        self.assertEqual(summary['action_count_by_agent']['player-1-controller'], 1)
        self.assertEqual(summary['action_count_by_source']['llm_player'], 1)
        self.assertEqual(summary['error_messages'], ['bad command'])

    def test_summarize_batch_aggregates_episode_summaries(self) -> None:
        report = summarize_batch([
            {'success': True, 'total_reward': 2.0, 'invalid_action_count': 0, 'turn_count': 10, 'final_party_hp_ratio': 1.0},
            {'success': False, 'total_reward': -1.0, 'invalid_action_count': 2, 'turn_count': 6, 'final_party_hp_ratio': 0.25, 'error_messages': ['timeout']},
        ])

        self.assertEqual(report['episodes'], 2)
        self.assertEqual(report['successes'], 1)
        self.assertEqual(report['success_rate'], 0.5)
        self.assertEqual(report['avg_reward'], 0.5)
        self.assertEqual(report['avg_invalid_actions'], 1.0)
        self.assertEqual(report['avg_turns'], 8.0)
        self.assertEqual(report['avg_party_hp_remaining'], 0.625)
        self.assertEqual(report['common_failure_modes'], [{'message': 'timeout', 'count': 1}])

    def test_single_episode_first_combat_batch_writes_report(self) -> None:
        report = run_batch(
            episodes=1,
            output_dir=self._tempdir / 'batches',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
        )

        report_path = Path(report['report_path'])
        self.assertTrue(report_path.exists())
        saved = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['policy'], 'scripted')
        self.assertEqual(saved['episodes'], 1)
        self.assertEqual(saved['successes'], 1)
        self.assertEqual(saved['success_rate'], 1.0)
        self.assertGreater(saved['avg_reward'], 1.0)
        self.assertEqual(saved['avg_invalid_actions'], 0.0)
        self.assertEqual(saved['episode_summaries'][0]['final_runtime_mode'], 'demo-complete')
        self.assertGreater(saved['transition_count'], 0)
        self.assertTrue(Path(saved['transition_path']).exists())
        self.assertTrue(Path(saved['transition_manifest_path']).exists())
        self.assertTrue(Path(saved['preference_path']).exists())
        self.assertTrue(Path(saved['preference_manifest_path']).exists())
        self.assertGreaterEqual(saved['preference_pair_count'], 0)
        self.assertTrue(Path(saved['evaluation_path']).exists())
        self.assertEqual(saved['policy_evaluation']['transition_count'], saved['transition_count'])
        self.assertGreater(saved['policy_evaluation']['reward_by_channel']['offense'], 0.0)
        transition_manifest = json.loads(Path(saved['transition_manifest_path']).read_text(encoding='utf-8'))
        self.assertEqual(transition_manifest['dataset_type'], 'training_transitions')
        self.assertEqual(transition_manifest['record_count'], saved['transition_count'])
        self.assertEqual(transition_manifest['context']['policy'], 'scripted')
        self.assertEqual(transition_manifest['filters']['include_roles'], ['player'])
        self.assertIn('enemy_damage', transition_manifest['reward_schema']['component_to_channel'])
        preference_manifest = json.loads(Path(saved['preference_manifest_path']).read_text(encoding='utf-8'))
        self.assertEqual(preference_manifest['dataset_type'], 'preference_pairs')
        self.assertEqual(preference_manifest['record_count'], saved['preference_pair_count'])
        self.assertEqual(preference_manifest['source_paths'], [saved['transition_path']])

    def test_llm_party_first_combat_batch_uses_llm_player_actions(self) -> None:
        def build_fake_agents():
            return tuple(FakeCombatLLMPlayerAgent(f'player-{index}-controller') for index in range(1, 5))

        report = run_batch(
            episodes=1,
            output_dir=self._tempdir / 'llm-batches',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
            policy='llm-party',
            llm_player_agent_factory=build_fake_agents,
            llm_player_max_actions_per_pump=1,
        )

        report_path = Path(report['report_path'])
        self.assertTrue(report_path.exists())
        saved = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['policy'], 'llm-party')
        self.assertEqual(saved['llm_player_controllers'], [f'player-{index}-controller' for index in range(1, 5)])
        self.assertEqual(saved['episodes'], 1)
        self.assertEqual(saved['successes'], 1)
        self.assertEqual(saved['success_rate'], 1.0)
        self.assertEqual(saved['avg_invalid_actions'], 0.0)
        self.assertGreater(saved['transition_count'], 0)
        self.assertTrue(Path(saved['transition_path']).exists())
        self.assertTrue(Path(saved['transition_manifest_path']).exists())
        self.assertTrue(Path(saved['preference_path']).exists())
        self.assertTrue(Path(saved['preference_manifest_path']).exists())
        self.assertGreaterEqual(saved['preference_pair_count'], 0)
        self.assertTrue(Path(saved['evaluation_path']).exists())
        summary = saved['episode_summaries'][0]
        self.assertEqual(saved['policy_evaluation']['action_count_by_source']['llm_player'], summary['action_count_by_source']['llm_player'])
        self.assertEqual(summary['final_runtime_mode'], 'demo-complete')
        self.assertGreater(summary['action_count_by_source']['llm_player'], 0)
        self.assertGreater(summary['total_reward'], 1.0)

    def test_random_legal_first_combat_batch_uses_baseline_actions(self) -> None:
        report = run_batch(
            episodes=1,
            output_dir=self._tempdir / 'random-legal-batches',
            env_path=self.env_path,
            base_url=LOCAL_MIRROR_BASE_URL,
            policy='random-legal',
            baseline_seed=123,
            max_combat_turns=120,
        )

        report_path = Path(report['report_path'])
        self.assertTrue(report_path.exists())
        saved = json.loads(report_path.read_text(encoding='utf-8'))
        self.assertEqual(saved['policy'], 'random-legal')
        self.assertEqual(saved['baseline_seed'], 123)
        self.assertEqual(saved['episodes'], 1)
        self.assertEqual(saved['successes'], 1)
        self.assertEqual(saved['success_rate'], 1.0)
        self.assertGreater(saved['transition_count'], 0)
        self.assertTrue(Path(saved['transition_path']).exists())
        self.assertTrue(Path(saved['evaluation_path']).exists())
        summary = saved['episode_summaries'][0]
        self.assertEqual(summary['final_runtime_mode'], 'demo-complete')
        self.assertGreater(summary['action_count_by_source']['baseline'], 0)
        self.assertEqual(saved['policy_evaluation']['action_count_by_source']['baseline'], summary['action_count_by_source']['baseline'])


if __name__ == '__main__':
    unittest.main()
