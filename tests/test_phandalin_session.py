from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import json
import shutil
import tempfile
import unittest

from session_server import build_lmop_story_demo_session
from session_server.web_projection import project_story_session_view, to_jsonable
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterPermissionError, EncounterValidationError
from shared_types.storytelling import RuntimeMode
from shared_types.travel import HexCoord
from tests.test_storytelling_session import QueueTransport
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL

ROOT = Path(__file__).resolve().parents[1]


class PhandalinSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='phandalin-tests-')
        self.root = Path(self.temp.name)
        self.campaign = self.root / 'campaign'
        shutil.copytree(ROOT / 'campaigns/lmop', self.campaign)
        self.env = self.root / '.env'
        self.env.write_text(
            'OPENAI_API_KEY=test-key\nOPENAI_BASE_URL=https://example.invalid/v1\nOPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        self.transport = QueueTransport([])

    def tearDown(self):
        self.temp.cleanup()

    def build(self, start='phandalin'):
        return build_lmop_story_demo_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            campaign_root=self.campaign,
            env_path=self.env,
            client_transport=self.transport,
            story_start=start,
        )

    def view(self, session, controller='player-1-controller'):
        return to_jsonable(project_story_session_view(session, controller, session_id='site-test'))

    def enter(self, session, entrance='manor'):
        if entrance == 'tunnel':
            session.handle_input('player-1-controller', '/visit alderleaf-farm')
            session.handle_input('player-1-controller', '/talk carp-alderleaf')
        session.handle_input('player-1-controller', '/visit tresendar-manor')
        session.handle_input('player-1-controller', '/talk manor-tracks')
        session.handle_input('player-1-controller', f'/site enter {entrance}')

    def test_direct_start_town_map_and_choices_require_no_model_call(self):
        session = self.build()
        self.assertEqual(session.story_state.canonical_location_id, 'phandalin')
        self.assertEqual(session.story_state.current_scene_id, 'scene-phandalin-arrival')
        view = self.view(session)
        self.assertEqual(view['site']['town_image'], 'assets/maps/phandalin-player.webp')
        self.assertEqual(len(view['site']['places']), 6)
        self.assertIsNone(view['map'])
        self.assertNotIn('secret-tunnel-known', json.dumps(view))
        session.handle_input('player-1-controller', '/visit stonehill-inn')
        session.handle_input('player-1-controller', '/talk toblen-stonehill')
        self.assertIn('missing-family-known', session.campaign_site.state.progress.flags)
        self.assertEqual(self.transport.requests, [])

    def test_real_regional_arrival_connects_without_resetting_hp_or_sildar(self):
        session = self.build('waterdeep')
        session.state.actors['player-1'].current_hit_points = 3
        session.story_state.metadata['sildar_rescued'] = 'true'
        session.story_state.metadata['story_slice'] = 'post-ambush-cragmaw'
        travel = session.story_state.travel_state
        session.story_state.travel_state = replace(
            travel,
            party_coord=HexCoord(5, 0),
            discovered_hexes=tuple(set(travel.discovered_hexes) | {HexCoord(5, 0)}),
        )
        session.travel_plan_route('player-1-controller', destination_location_id='phandalin')
        session.travel_advance('player-1-controller', steps=1)
        self.assertTrue(session.campaign_site.state.progress.arrived)
        self.assertEqual(session.story_state.canonical_location_id, 'phandalin')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, 3)
        self.assertEqual(session.story_state.metadata['sildar_rescued'], 'true')
        self.assertIsNotNone(self.view(session)['site'])

    def test_hidden_route_and_player_dm_hideout_projection(self):
        session = self.build()
        session.handle_input('player-1-controller', '/visit tresendar-manor')
        with self.assertRaises(EncounterValidationError):
            session.handle_input('player-1-controller', '/site enter tunnel')
        self.enter(session)
        player = self.view(session)
        dm = self.view(session, 'dm')
        self.assertEqual(player['runtime_mode'], 'storytelling')
        self.assertEqual(player['map']['map_id'], 'redbrand_hideout_player_v1')
        self.assertNotIn('glasstaff-1', [token['actor_id'] for token in player['map']['tokens']])
        self.assertIn('glasstaff-1', [token['actor_id'] for token in dm['map']['tokens']])
        self.assertNotIn('quarters-secret', json.dumps(player['map']))
        self.assertNotIn('cellar-secret', json.dumps(player['map']))
        hidden = next(
            cell
            for cell in player['map']['cells']
            if cell['position']['x'] == 8 and cell['position']['y'] == 3
        )
        self.assertFalse(hidden['visible'])
        self.assertEqual(hidden['terrain_id'], 'unknown')
        self.assertEqual(hidden['object_ids'], [])

    def test_ownership_and_explicit_targets(self):
        session = self.build()
        self.enter(session, 'tunnel')
        before = deepcopy(session.state)
        with self.assertRaises(EncounterPermissionError):
            session.handle_input('player-1-controller', '/move player-2 10 17')
        self.assertEqual(session.state, before)
        with self.assertRaises(EncounterValidationError):
            session.handle_input('player-1-controller', '/visit')
        with self.assertRaises(EncounterValidationError):
            session.handle_input('player-1-controller', '/site enter')

    def test_hideout_exploration_moves_and_scoped_combat_return(self):
        session = self.build()
        self.enter(session)
        session.state.actors['player-1'].position = GridPosition(20, 14)
        session.handle_input('player-1-controller', '/site open cellar-barracks')
        session.handle_input('player-1-controller', '/move player-1 19 14')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertNotIn('glasstaff-1', session.state.initiative_order)
        for mid in ('redbrand-barracks-1', 'redbrand-barracks-2', 'redbrand-barracks-3'):
            session.state.actors[mid].current_hit_points = 0
        session.campaign_site.after_combat_action()
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertIn('redbrand-barracks', session.campaign_site.state.progress.resolved_encounters)
        self.assertIsNotNone(self.view(session)['map'])

    def test_exploration_preview_and_secret_inspection_use_redacted_state(self):
        from session_server.web_projection import preview_path, inspect_cell

        session = self.build()
        self.enter(session, 'tunnel')
        preview = preview_path(session, 'player-1-controller', x=9, y=16, mode='walk')
        self.assertEqual(preview.actor_id, 'player-1')
        with self.assertRaises(EncounterPermissionError):
            inspect_cell(session, 'player-1-controller', x=8, y=3)
        session.state.actors['player-1'].position = GridPosition(20, 18)
        inspection = inspect_cell(session, 'player-1-controller', x=20, y=18)
        self.assertNotIn('cellar-secret', inspection.feature_ids)
        self.assertNotIn('cellar-secret', inspection.object_ids)

    def test_frontend_has_town_choices_and_opaque_dungeon_fog(self):
        script = (ROOT / 'web_frontend/app.js').read_text(encoding='utf-8')
        css = (ROOT / 'web_frontend/styles.css').read_text(encoding='utf-8')
        self.assertIn('function renderTownMap(', script)
        self.assertIn('function renderSiteActions(', script)
        self.assertIn('site?.in_dungeon', script)
        self.assertIn('background: #080c12;', css)
        self.assertIn('Choose a town location, then select a conversation or entrance.', script)
        self.assertIn('function focusBattlefieldToken(', script)
        self.assertIn('token.is_owner', script)
        self.assertIn('.town-place[data-place-id="stonehill-inn"]', css)
        self.assertIn('color: #513817;', css.split('.site-discoveries {')[1].split('}')[0])

    def test_arrival_goals_replace_obsolete_waterdeep_briefing(self):
        session = self.build()
        self.assertIn('Redbrands', ' '.join(session.story_state.current_party_goals))
        self.assertNotIn('Hear Gundren', ' '.join(session.story_state.current_party_goals))

    def test_body_weight_is_explicit_controller_owned_data(self):
        session = self.build()
        self.assertEqual(self.view(session)['site']['actor_body_weight_lb'], 0)
        before = deepcopy(session.state)
        with self.assertRaises(EncounterValidationError):
            session.handle_input('player-1-controller', '/site weight nan')
        self.assertEqual(session.state, before)
        session.handle_input('player-1-controller', '/site weight 150')
        self.assertEqual(session.state.actors['player-1'].body_weight_lb, 150)
        self.assertEqual(session.state.actors['player-2'].body_weight_lb, 0)

    def test_exact_natural_choices_are_typed_and_ambiguity_does_not_call_model(self):
        from shared_types.errors import EncounterClarificationRequiredError

        session = self.build()
        session.handle_input('player-1-controller', 'Visit Stonehill Inn')
        self.assertEqual(session.campaign_site.state.progress.place_id, 'stonehill-inn')
        session.handle_input('player-1-controller', 'Speak with Toblen')
        self.assertIn('missing-family-known', session.campaign_site.state.progress.flags)
        before = deepcopy(session.state)
        with self.assertRaises(EncounterClarificationRequiredError):
            session.handle_input('player-1-controller', 'Go to the inn or the farm')
        self.assertEqual(session.state, before)
        self.assertEqual(self.transport.requests, [])

    def test_model_scene_transition_is_rejected_before_transcript_mutation(self):
        from shared_types.storytelling import StoryTurnDecision, StorySceneUpdate, StoryTranscriptEntry

        session = self.build()
        before = deepcopy((session.state, session.story_state))
        with self.assertRaises(EncounterValidationError):
            session._apply_story_turn_decision(
                StoryTurnDecision(
                    public_narration='You teleport into the lair.',
                    transcript_entries=(
                        StoryTranscriptEntry(speaker='DM', text='You teleport into the lair.'),
                    ),
                    scene_update=StorySceneUpdate(scene_id='invented', location_id='redbrand-hideout'),
                )
            )
        self.assertEqual((session.state, session.story_state), before)

    def test_dungeon_regional_travel_rejects_teleport(self):
        session = self.build()
        self.enter(session)
        before = deepcopy((session.state, session.story_state))
        with self.assertRaisesRegex(EncounterValidationError, 'Leave the dungeon'):
            session.travel_plan_route('player-1-controller', destination_location_id='cragmaw-hideout')
        self.assertEqual((session.state, session.story_state), before)

    def test_direct_model_transition_entrypoints_preserve_site_authority(self):
        from shared_types.storytelling import StorySceneUpdate, ModeSwitchDecision, ModeSwitchAction

        session = self.build()
        before = deepcopy((session.state, session.story_state))
        with self.assertRaises(EncounterValidationError):
            session._apply_scene_update(StorySceneUpdate(location_id='redbrand-hideout'))
        self.assertEqual((session.state, session.story_state), before)
        with self.assertRaises(EncounterValidationError):
            session.apply_mode_switch_decision(
                ModeSwitchDecision(decision_type=ModeSwitchAction.REMAIN_IN_COMBAT, reason='fixture')
            )
        self.assertEqual((session.state, session.story_state), before)

    def test_real_demo_wrapper_supports_map_preview_and_move(self):
        from tests.test_web_server import SessionWebServerTests, build_full_story_demo_manual_session

        helper = SessionWebServerTests()
        helper.setUp()
        wrapper = build_full_story_demo_manual_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            campaign_root=self.campaign,
            env_path=self.env,
            client_transport=self.transport,
            precreate_characters=True,
            story_start='phandalin',
        )
        self.enter(wrapper)
        try:
            server = helper._start_server(wrapper)
            with helper._connect_and_join(server, 'player-1-controller')[0] as ws:
                ws.send(json.dumps({'type': 'preview_move', 'x': 26, 'y': 13, 'mode': 'walk'}))
                message = json.loads(ws.recv(timeout=10))
                self.assertEqual(message['type'], 'path_preview', message)
                ws.send(json.dumps({'type': 'move_proposal', 'x': 26, 'y': 13, 'mode': 'walk'}))
                message = json.loads(ws.recv(timeout=10))
                self.assertEqual(message['type'], 'view', message)
                self.assertEqual(
                    wrapper.story_session.state.actors['player-1'].position.horizontal(), GridPosition(26, 13)
                )
        finally:
            helper.tearDown()

    def test_second_door_action_projects_explicit_utilize_command(self):
        session = self.build()
        self.enter(session)
        session.state.actors['player-1'].position = GridPosition(6, 4)
        session.handle_input('player-1-controller', '/site engage glasstaff')
        session.state.active_actor_id = 'player-1'
        session.handle_input('player-1-controller', '/site open quarters-door')
        choices = self.view(session)['site']['actions']
        close = next(a for a in choices if a['action_id'] == 'quarters-door')
        self.assertEqual(close['command'], '/site close quarters-door utilize')
        self.assertIn('Utilize', close['label'])
        session.handle_input('player-1-controller', close['command'])
        self.assertFalse(session.state.actors['player-1'].action_available)
