from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from session_server import build_lmop_story_demo_session
from session_server.web_projection import project_story_session_view
from shared_types.storytelling import RuntimeMode, EnterCombatPlan
from shared_types.exploration import DowntimeProjectStatus, PuzzleStatus, TrapStatus
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class QueueTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict] = []

    def _next_payload(self) -> dict:
        if not self.payloads:
            raise AssertionError('No queued LLM payloads remain for this test.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return [{'type': 'response.completed', 'response': self._next_payload()}]


class ExplorationProcedureTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.exploration-procedure-tests' / uuid4().hex
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

    def _build_session(self):
        return build_lmop_story_demo_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}]),
        )

    def _set_scene(self, session, *, scene_id: str, location_id: str) -> None:
        session.story_state.current_scene_id = scene_id
        session.story_state.canonical_location_id = location_id
        session._refresh_exploration_context(sync_memory=False)

    def test_exploration_state_bootstraps_from_lmop_story_session(self) -> None:
        session = self._build_session()
        exploration = session.story_state.exploration_state
        self.assertIsNotNone(exploration)
        assert exploration is not None
        self.assertEqual(exploration.current_scene_id, 'scene-waterdeep-gundren-briefing')
        self.assertEqual(exploration.current_location_id, 'waterdeep')
        self.assertEqual(len(exploration.marching_order), 4)
        self.assertEqual(exploration.marching_order[0].position.value, 'scout')
        visible_npcs = session.exploration_engine.visible_npc_states(exploration)
        self.assertEqual([npc.npc_id for npc in visible_npcs], ['gundren-rockseeker', 'sildar-hallwinter'])

    def test_marching_watch_and_role_state_persist_into_combat(self) -> None:
        session = self._build_session()
        session.execute_for_controller('player-1-controller', '/march set player-2 player-1 player-3 player-4')
        session.execute_for_controller('player-1-controller', '/watch set player-4 player-3 player-2 player-1')
        session.execute_for_controller('player-1-controller', '/role set scout player-2')
        session.execute_for_controller('player-1-controller', '/role set search player-1 player-3')
        session.execute_for_controller('player-1-controller', '/camp start')
        session.execute_for_controller('dm', '/time light-activity 120')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        self.assertEqual(exploration.marching_order[0].actor_id, 'player-2')
        self.assertEqual(exploration.role_assignments.scout_actor_id, 'player-2')
        self.assertEqual(exploration.role_assignments.searching_actor_ids, ('player-1', 'player-3'))
        self.assertEqual(session.exploration_engine.active_watchers(exploration, encounter_state=session.state), ('player-3',))

        participant_ids = tuple(session.state.actors.keys())
        session.enter_combat(
            EnterCombatPlan(
                reason='Ambush check',
                participant_ids=participant_ids,
                scene_id='scene-triboar-goblin-ambush',
                location_id='triboar-trail',
                battlefield_map_id='goblin-ambush-triboar-trail',
            )
        )
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        exploration_after = session.story_state.exploration_state
        assert exploration_after is not None
        self.assertEqual(exploration_after.marching_order[0].actor_id, 'player-2')
        self.assertEqual(exploration_after.role_assignments.scout_actor_id, 'player-2')

    def test_social_influence_updates_npc_state_and_discoveries(self) -> None:
        session = self._build_session()
        actor = session.state.actors['player-1']
        actor.skill_bonuses['Persuasion'] = 20
        session.handle_input('player-1-controller', 'Gundren, can we bargain for a little prepay for supplies? We can keep the wagon safe in return.')
        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertIn('Persuasion', prompt.prompt)
        session.execute_for_controller('player-1-controller', '/check')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        npc_state = exploration.npc_states['gundren-rockseeker']
        self.assertIn(npc_state.attitude.value, {'cooperative', 'friendly', 'reserved'})
        self.assertGreaterEqual(npc_state.trust + npc_state.leverage + npc_state.obligation, 1)
        self.assertTrue(any('Gundren' in clue or 'Phandalin' in clue or 'terms' in clue for clue in exploration.known_discoveries))
        view = session.view_for_controller('player-1-controller')
        rendered = '\n'.join(view.summary_lines)
        self.assertIn('NPC stances:', rendered)
        self.assertIn('Gundren Rockseeker', rendered)

    def test_hidden_trap_is_dm_visible_only_until_revealed(self) -> None:
        session = self._build_session()
        self._set_scene(session, scene_id='scene-00-high-road-journey', location_id='high-road')
        player_view = project_story_session_view(session, 'player-1-controller', session_id='test-session')
        dm_view = project_story_session_view(session, 'dm', session_id='test-session')
        player_text = '\n'.join(player_view.summary_lines)
        dm_text = '\n'.join(dm_view.summary_lines)
        self.assertNotIn('Goblin Snare Line', player_text)
        self.assertIn('Goblin Snare Line', dm_text)

    def test_passive_detection_and_tool_disarm_flow(self) -> None:
        session = self._build_session()
        self._set_scene(session, scene_id='scene-00-high-road-journey', location_id='high-road')
        actor = session.state.actors['player-1']
        actor.passive_perception = 20
        actor.skill_bonuses['Sleight of Hand'] = 20
        actor.character_record.tool_proficiencies = actor.character_record.tool_proficiencies + ("Thieves' Tools",)
        session._refresh_exploration_context(sync_memory=False)
        exploration = session.story_state.exploration_state
        assert exploration is not None
        self.assertEqual(exploration.traps['triboar-snare-line'].status, TrapStatus.DETECTED)
        session.handle_input('player-1-controller', "I use my thieves' tools to disarm the snare line.")
        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        session.execute_for_controller('player-1-controller', '/check')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        self.assertEqual(exploration.traps['triboar-snare-line'].status, TrapStatus.DISARMED)
        self.assertTrue(any(event.__class__.__name__ == 'TrapDisarmedEvent' for event in session.state.event_log))

    def test_internal_trap_trigger_uses_exposed_marcher(self) -> None:
        session = self._build_session()
        self._set_scene(session, scene_id='scene-00-high-road-journey', location_id='high-road')
        session.execute_for_controller('player-1-controller', '/march set player-3 player-1 player-2 player-4')
        session.trigger_trap('dm', trap_id='triboar-snare-line')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        runtime = exploration.traps['triboar-snare-line']
        self.assertEqual(runtime.status, TrapStatus.TRIGGERED)
        self.assertEqual(runtime.triggered_by_actor_id, 'player-3')

    def test_puzzle_progress_and_solve_flow_reveal_cragmaw_trail(self) -> None:
        session = self._build_session()
        self._set_scene(session, scene_id='scene-02-trail-aftermath', location_id='triboar-trail')
        actor = session.state.actors['player-1']
        actor.skill_bonuses['Perception'] = 20
        actor.skill_bonuses['Survival'] = 20
        session.handle_input('player-1-controller', 'I search the ambush site for clues and tracks.')
        session.execute_for_controller('player-1-controller', '/check')
        session.handle_input('player-1-controller', 'I search the trail again for more signs of where they went.')
        session.execute_for_controller('player-1-controller', '/check')
        session.handle_input('player-1-controller', 'I follow the hidden trail and figure out where it leads.')
        session.execute_for_controller('player-1-controller', '/check')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        puzzle = exploration.puzzles['trail-aftermath-clues']
        self.assertEqual(puzzle.status, PuzzleStatus.SOLVED)
        self.assertTrue(any('Cragmaw trail' in clue for clue in exploration.known_discoveries))

    def test_downtime_project_progresses_and_advances_time(self) -> None:
        session = self._build_session()
        actor = session.state.actors['player-1']
        actor.skill_bonuses['Investigation'] = 20
        start_clock = session.state.clock_seconds
        session.execute_for_controller('player-1-controller', '/downtime start copy-wagon-ledger')
        session.execute_for_controller('player-1-controller', '/downtime work copy-wagon-ledger:player-1 2')
        exploration = session.story_state.exploration_state
        assert exploration is not None
        project = exploration.downtime_projects['copy-wagon-ledger:player-1']
        self.assertEqual(project.status, DowntimeProjectStatus.COMPLETED)
        self.assertEqual(session.state.clock_seconds - start_clock, 2 * 60 * 60)
        self.assertTrue(any('Barthen' in clue for clue in exploration.known_discoveries))


    def test_player_facing_social_trap_and_puzzle_slash_commands_are_rejected(self) -> None:
        session = self._build_session()
        with self.assertRaisesRegex(Exception, 'Use normal storytelling declarations'):
            session.execute_for_controller('player-1-controller', '/social gundren-rockseeker persuade')
        with self.assertRaisesRegex(Exception, 'Use normal storytelling declarations'):
            session.execute_for_controller('player-1-controller', '/trap status')
        with self.assertRaisesRegex(Exception, 'Use normal storytelling declarations'):
            session.execute_for_controller('player-1-controller', '/puzzle status')

    def test_downtime_help_lists_available_activities(self) -> None:
        session = self._build_session()
        view = session.execute_for_controller('player-1-controller', '/downtime help')
        rendered = '\n'.join(view.summary_lines)
        self.assertIn('Downtime help:', rendered)
        self.assertIn('copy-wagon-ledger', rendered)
        self.assertIn('/downtime start <activity-id> [actor-id]', rendered)


if __name__ == '__main__':
    unittest.main()
