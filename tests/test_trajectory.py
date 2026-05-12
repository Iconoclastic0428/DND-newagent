from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

from dm_agent.client import LLMClient
from dm_agent.config import LLMConfig
from session_server.llm_player import LLMPlayerAgent
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.encounter_models import ActorSide, EncounterPhase
from shared_types.errors import EncounterPermissionError
from shared_types.storytelling import RuntimeMode
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL
from tests.test_storytelling_session import QueueTransport
from training.trajectory import TrajectoryRecorder

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from story_demo_system_server import build_full_story_demo_manual_session
from web_story_demo_server import LocalDemoLLMTransport


class TrajectoryRecorderTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.trajectory-tests' / uuid4().hex
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

    def test_full_story_demo_records_story_turn_jsonl(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_gundren_briefing',
            episode_id='episode-test',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren gives the party the practical terms.",'
                        '"transcript_entries":[{"speaker":"Gundren Rockseeker","text":"Ten gold each when the wagon reaches Phandalin.","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        '"memory_note":"The party asked about payment."'
                        '}'
                    )
                }
            ]),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )

        session.handle_input('player-1-controller', "What's the pay?")

        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        record_types = [record['record_type'] for record in records]
        self.assertIn('episode_started', record_types)
        self.assertIn('story_started', record_types)
        turn = next(record for record in records if record['record_type'] == 'turn')
        self.assertEqual(turn['scenario_id'], 'lmop_gundren_briefing')
        self.assertEqual(turn['agent_id'], 'player-1-controller')
        self.assertEqual(turn['role'], 'player')
        self.assertEqual(turn['source'], 'human')
        self.assertEqual(turn['raw_text'], "What's the pay?")
        self.assertEqual(turn['parsed_action']['kind'], 'natural_language')
        self.assertEqual(turn['runtime_mode'], 'storytelling')
        self.assertEqual(turn['state_before']['scene_id'], 'scene-waterdeep-gundren-briefing')
        self.assertGreater(turn['state_after']['transcript_count'], turn['state_before']['transcript_count'])
        self.assertTrue(turn['observation']['summary_lines'])
        self.assertIn('available_choices', turn['observation'])
        self.assertGreater(turn['reward_components']['valid_action'], 0.0)
        self.assertGreater(turn['reward_components']['story_progress'], 0.0)
        self.assertGreater(turn['metadata']['reward_total'], 0.0)

    def test_full_story_demo_records_invalid_action_reward(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_invalid_action',
            episode_id='episode-invalid-action',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([]),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )

        with self.assertRaises(EncounterPermissionError):
            session.handle_input('dm', 'I am a player now.')

        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        turn = records[-1]
        self.assertEqual(turn['record_type'], 'turn')
        self.assertEqual(turn['agent_id'], 'dm')
        self.assertIsNotNone(turn['error'])
        self.assertEqual(turn['reward_components'], {'invalid_action': -1.0})
        self.assertEqual(turn['metadata']['reward_total'], -1.0)

    def test_full_story_demo_records_terminal_episode_reward(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_terminal_reward',
            episode_id='episode-terminal-reward',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([]),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )
        assert session.story_session is not None
        session.story_session.story_state.runtime_mode = RuntimeMode.COMBAT
        session.story_session.state.phase = EncounterPhase.COMPLETE
        session.story_session.state.winning_side = ActorSide.PLAYER

        session.view_for_controller('player-1-controller')
        session.view_for_controller('player-2-controller')

        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        completion_records = [record for record in records if record['record_type'] == 'episode_completed']
        self.assertEqual(len(completion_records), 1)
        completion = completion_records[0]
        self.assertEqual(completion['runtime_mode'], 'demo-complete')
        self.assertEqual(completion['reward_components']['episode_success'], 1.0)
        self.assertGreaterEqual(completion['reward_components']['party_survival'], 0.0)
        self.assertGreater(completion['reward_components']['encounter_efficiency'], 0.0)
        self.assertGreater(completion['metadata']['reward_total'], 1.0)
        self.assertEqual(completion['metadata']['living_monster_count'], 4)
        self.assertTrue(completion['metadata']['success'])

    def test_trajectory_snapshot_exposes_support_and_debuff_metrics(self) -> None:
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([]),
            precreate_characters=True,
        )
        assert session.story_session is not None
        player = session.story_session.state.actors['player-1']
        player.temp_hit_points = 5
        goblin = session.story_session.state.actors['monster-goblin-1']
        goblin.condition_instances = (
            ConditionInstance(instance_id='test-prone', condition_type=ConditionType.PRONE),
            ConditionInstance(instance_id='test-poisoned', condition_type=ConditionType.POISONED),
            ConditionInstance(instance_id='test-stunned', condition_type=ConditionType.STUNNED),
        )

        snapshot = session._trajectory_state_snapshot()

        self.assertEqual(snapshot['party_temp_hp'], 5)
        self.assertEqual(snapshot['monster_control_debuff_count'], 1)
        self.assertEqual(snapshot['monster_accuracy_debuff_count'], 1)
        self.assertEqual(snapshot['monster_action_debuff_count'], 1)
        self.assertEqual(snapshot['party_control_debuff_count'], 0)

    def test_real_cure_wounds_action_records_ally_healing_reward(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_real_healing_reward',
            episode_id='episode-real-healing',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=LocalDemoLLMTransport(),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )
        assert session.story_session is not None
        actor = session.story_session.state.actors['player-1']
        actor.current_hit_points = max(1, actor.current_hit_points - 4)

        session.handle_input('player-1-controller', '/cast player-1 cure-wounds player-1')

        self.assertEqual(actor.current_hit_points, actor.max_hit_points)
        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        turn = records[-1]
        self.assertEqual(turn['raw_text'], '/cast player-1 cure-wounds player-1')
        self.assertIsNone(turn['error'])
        self.assertEqual(turn['state_before']['party_hp_current'], turn['state_after']['party_hp_current'] - 4)
        self.assertEqual(turn['reward_components']['ally_healing'], 0.12)

    def test_real_monster_hit_records_party_damage_and_down_penalties(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_real_monster_attack_reward',
            episode_id='episode-real-monster-attack',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=LocalDemoLLMTransport(),
            precreate_characters=True,
            trajectory_recorder=recorder,
        )
        assert session.story_session is not None
        session.story_session.story_state.runtime_mode = RuntimeMode.COMBAT
        state = session.story_session.state
        state.phase = EncounterPhase.IN_PROGRESS
        state.active_actor_id = 'monster-goblin-1'
        state.initiative_order = ('monster-goblin-1', 'player-1')
        player = state.actors['player-1']
        player.armor_class = 1
        player.base_armor_class = 1

        session.handle_input('dm', '/attack monster-goblin-1 shortbow player-1')
        self.assertIsNotNone(state.pending_reaction_window)
        session.handle_input('player-1-controller', '/react player-1 decline')

        self.assertEqual(player.current_hit_points, 0)
        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        turn = records[-1]
        self.assertEqual(turn['raw_text'], '/react player-1 decline')
        self.assertIsNone(turn['error'])
        self.assertLess(turn['state_after']['party_hp_current'], turn['state_before']['party_hp_current'])
        self.assertLess(turn['state_after']['living_party_count'], turn['state_before']['living_party_count'])
        self.assertLess(turn['reward_components']['party_damage_taken'], 0.0)
        self.assertEqual(turn['reward_components']['ally_defeated'], -0.5)
        self.assertEqual(turn['reward_components']['ally_action_debuffed'], -0.25)

    def test_full_llm_party_autopump_records_each_player_once(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_full_llm_party',
            episode_id='episode-full-llm-party',
        )
        agents = tuple(
            LLMPlayerAgent(
                controller_id=f'player-{index}-controller',
                client=LLMClient(
                    LLMConfig(api_key='test-key', base_url='https://example.invalid/v1', responses_model=f'player-{index}-model'),
                    transport=QueueTransport([
                        {
                            'output_text': json.dumps(
                                {
                                    'command': f'/say Player {index} is ready to continue.',
                                    'reason': 'Keep the party moving.',
                                }
                            )
                        }
                    ]),
                ),
                label=f'test-player-{index}',
            )
            for index in range(1, 5)
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([
                {
                    'output_text': (
                        '{'
                        f'"public_narration":"The DM acknowledges player {index}.",'
                        '"transcript_entries":[],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        f'"memory_note":"Player {index} acted."'
                        '}'
                    )
                }
                for index in range(1, 5)
            ]),
            precreate_characters=True,
            llm_player_agents=agents,
            llm_player_autopump=True,
            llm_player_max_actions_per_pump=4,
            trajectory_recorder=recorder,
        )

        actions = session.pump_llm_players(max_actions=4)

        self.assertEqual(
            actions,
            (
                ('player-1-controller', '/say Player 1 is ready to continue.'),
                ('player-2-controller', '/say Player 2 is ready to continue.'),
                ('player-3-controller', '/say Player 3 is ready to continue.'),
                ('player-4-controller', '/say Player 4 is ready to continue.'),
            ),
        )
        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        llm_turns = [record for record in records if record['record_type'] == 'turn' and record['source'] == 'llm_player']
        self.assertEqual([record['agent_id'] for record in llm_turns], [f'player-{index}-controller' for index in range(1, 5)])
        self.assertTrue(all(record['parsed_action']['kind'] == 'command' for record in llm_turns))

    def test_first_combat_smoke_records_clean_terminal_success(self) -> None:
        recorder = TrajectoryRecorder(
            output_dir=self._tempdir / 'episodes',
            scenario_id='lmop_first_combat_smoke',
            episode_id='episode-first-combat-smoke',
        )
        session = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=LocalDemoLLMTransport(),
            trajectory_recorder=recorder,
        )
        script = json.loads((REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts' / 'lmop-friendly-live-web-run.json').read_text(encoding='utf-8'))
        for step in script['steps']:
            if step.get('type') == 'repeat':
                break
            if step.get('type') not in {'command', 'command_if_prompt'}:
                continue
            controller_id = step['controller_id']
            if step['type'] == 'command_if_prompt':
                prompt = session.prompt_for_controller(controller_id)
                if prompt is None or prompt.prompt_kind != step.get('prompt_kind'):
                    continue
            session.handle_input(controller_id, step['input'])
            if step.get('input') == '/travel engage':
                break

        assert session.story_session is not None
        self.assertEqual(session.story_session.story_state.runtime_mode, RuntimeMode.COMBAT)
        for _turn in range(80):
            session._refresh_demo_completion()
            state = session.story_session.state
            if state.phase == EncounterPhase.COMPLETE:
                break
            active_actor_id = state.active_actor_id
            self.assertIsNotNone(active_actor_id)
            actor = state.actors[active_actor_id]
            if actor.side == ActorSide.MONSTER:
                session.handle_input('dm', f'/endturn {active_actor_id}')
                continue
            controller_id = f'{active_actor_id}-controller'
            target = next(
                candidate
                for candidate in state.actors.values()
                if candidate.side != actor.side and candidate.current_hit_points > 0
            )
            if 'magic-missile' in actor.spells:
                session.handle_input(controller_id, f'/cast {active_actor_id} magic-missile {target.actor_id}')
            elif 'fire-bolt' in actor.spells:
                session.handle_input(controller_id, f'/cast {active_actor_id} fire-bolt {target.actor_id}')
            session._refresh_demo_completion()
            if session.story_session.state.phase == EncounterPhase.COMPLETE:
                break
            session.handle_input(controller_id, f'/endturn {active_actor_id}')

        session._refresh_demo_completion()
        self.assertIsNotNone(session._completion_state)
        self.assertEqual(session.story_session.state.winning_side, ActorSide.PLAYER)
        records = [json.loads(line) for line in recorder.path.read_text(encoding='utf-8').splitlines()]
        self.assertFalse([record for record in records if record.get('error')])
        combat_turns = [record for record in records if record['record_type'] == 'turn' and record['state_after'].get('runtime_mode') == 'combat']
        self.assertTrue(any('enemy_damage' in record['reward_components'] for record in combat_turns))
        self.assertTrue(any('enemy_defeated' in record['reward_components'] for record in combat_turns))
        self.assertTrue(all('party_hp_current' in record['state_after'] for record in combat_turns))
        completion = next(record for record in records if record['record_type'] == 'episode_completed')
        self.assertEqual(completion['reward_components']['episode_success'], 1.0)
        self.assertEqual(completion['reward_components']['party_survival'], 1.0)
        self.assertGreater(completion['metadata']['reward_total'], 1.0)
        self.assertEqual(completion['metadata']['living_monster_count'], 0)
        self.assertEqual(completion['metadata']['party_hp_current'], completion['metadata']['party_hp_max'])


if __name__ == '__main__':
    unittest.main()
