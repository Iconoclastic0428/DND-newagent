from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from session_server import build_lmop_story_demo_session
from shared_types.adjudication import (
    AdjudicationAttackMode,
    AdjudicationAttackRequest,
    AdjudicationBranch,
    AdjudicationCheckRequest,
    AdjudicationContestRequest,
    AdjudicationOperation,
    AdjudicationOperationType,
    AdjudicationPlan,
    AdjudicationSaveRequest,
    AdjudicationType,
    ActionCostRecommendation,
    ActionCostType,
    ContestParticipantRequest,
    ContestTieRule,
    ImprovisedTemplateId,
)
from shared_types.d20 import D20RollMode
from shared_types.encounter_models import EncounterPhase
from shared_types.models import Ability
from shared_types.storytelling import RuntimeMode
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


class AdjudicationRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        self._tempdir = repo_root / '.adjudication-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        self.campaign_root = self._tempdir / 'campaigns' / 'lmop'
        shutil.copytree(repo_root / 'campaigns' / 'lmop', self.campaign_root)
        self.base_url = LOCAL_MIRROR_BASE_URL

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _build_session(self, payloads: list[dict]):
        transport = QueueTransport(payloads)
        session = build_lmop_story_demo_session(
            base_url=self.base_url,
            campaign_root=self.campaign_root,
            env_path=self.env_path,
            client_transport=transport,
        )
        return session, transport

    def _put_player_one_in_combat(self, session, *, action_available: bool = True) -> None:
        session.story_state.runtime_mode = RuntimeMode.COMBAT
        session.state.phase = EncounterPhase.IN_PROGRESS
        session.state.round_number = 1
        session.state.turn_index = 0
        session.state.initiative_order = ('player-1', 'monster-goblin-1')
        session.state.active_actor_id = 'player-1'
        player = session.state.actors['player-1']
        player.action_available = action_available
        player.bonus_action_available = True
        player.reaction_available = True
        player.remaining_movement_ft = max(player.remaining_movement_ft, 30)
        player.remaining_free_object_interaction = True

    def _shift_to_high_road(self, session) -> None:
        session.story_state.current_scene_id = 'scene-00-high-road-journey'
        session.story_state.canonical_location_id = 'high-road'
        session.story_state.open_loops = ('Watch the brush for the first sign of danger.',)
        session.story_state.current_party_goals = ('Escort the wagon safely east.',)
        session.story_state.recent_summary = 'The wagon has just entered the rougher High Road stretch.'
        session.story_state.metadata['retrieval_tags'] = 'high-road,wagon,brush'
        session.story_state.metadata['nearby_tags'] = 'trail,brush,wagon'
        session._sync_memory_files()

    def test_standard_combat_slash_command_bypasses_adjudication_llm(self) -> None:
        session, transport = self._build_session([])
        self._put_player_one_in_combat(session)
        session.execute_for_controller('player-1-controller', '/dodge player-1')
        self.assertEqual(len(transport.requests), 0)
        self.assertFalse(session.state.actors['player-1'].action_available)

    def test_storytelling_do_routes_to_adjudication_and_creates_improvised_object(self) -> None:
        session, transport = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 yanks a wagon board into cover.",'
                        '"doable":true,'
                        '"adjudication_type":"automatic_success",'
                        '"reasoning_summary_for_dm":"The wagon provides immediate improvised cover without a roll.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":["overturned_table_cover"],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[{"operation_type":"create_improvised_object","template_id":"overturned_table_cover","x":15,"y":17,"note":"A loose board is dragged into a low wall of cover."}],'
                        '"on_success":{"public_text":"You wrench a loose board into place and make a scrap of cover beside the wagon.","dm_note":"","operations":[{"operation_type":"update_scene_state_note","note":"Player 1 created improvised wagon-board cover beside the wagon."}]},'
                        '"on_failure":null,'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                }
            ]
        )
        self._shift_to_high_road(session)
        session.execute_for_controller('player-1-controller', '/do I yank a loose board off the wagon and set it up as cover.')
        self.assertEqual(len(transport.requests), 1)
        self.assertTrue(session.state.battlefield.dynamic_feature_ids)
        self.assertIn('A loose board is dragged into a low wall of cover.', session.story_state.metadata.get('terrain_change_lines', ''))
        scene_state_path = self.campaign_root / 'dm' / 'scene-state' / f'{session.story_state.current_scene_id}.md'
        self.assertIn('A loose board is dragged into a low wall of cover.', scene_state_path.read_text(encoding='utf-8'))

    def test_adjudication_retries_when_template_is_unsupported(self) -> None:
        session, transport = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 invents a stone barricade.",'
                        '"doable":true,'
                        '"adjudication_type":"automatic_success",'
                        '"reasoning_summary_for_dm":"Bad template.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":["stone_barricade_large"],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[],'
                        '"on_success":null,'
                        '"on_failure":null,'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                },
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 braces the wagon.",'
                        '"doable":true,'
                        '"adjudication_type":"automatic_success",'
                        '"reasoning_summary_for_dm":"Valid fallback.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":[],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[],'
                        '"on_success":{"public_text":"You brace the wagon and keep it steady.","dm_note":"","operations":[]},'
                        '"on_failure":null,'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                },
            ]
        )
        self._shift_to_high_road(session)
        session.execute_for_controller('player-1-controller', '/do I try to build a barricade out of whatever is nearby.')
        self.assertEqual(len(transport.requests), 2)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Unsupported improvised template id', retry_text)

    def test_blank_operation_placeholders_are_treated_as_no_operation(self) -> None:
        session, transport = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 checks the wagon straps.",'
                        '"doable":true,'
                        '"adjudication_type":"automatic_success",'
                        '"reasoning_summary_for_dm":"The action is simple and does not need state mutation.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":[],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[{"operation_type":"","note":""}],'
                        '"on_success":{"public_text":"The wagon straps look secure.","dm_note":"","operations":[{"operation_type":""}]},'
                        '"on_failure":null,'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                }
            ]
        )
        self._shift_to_high_road(session)
        session.execute_for_controller('player-1-controller', '/do I check the wagon straps before we move.')
        self.assertEqual(len(transport.requests), 1)

    def test_adjudicated_ability_check_resolves_through_rules_engine_without_second_llm_call(self) -> None:
        session, transport = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 scrambles onto the wagon roof.",'
                        '"doable":true,'
                        '"adjudication_type":"ability_check",'
                        '"reasoning_summary_for_dm":"Quick scrambling is uncertain but straightforward.",'
                        '"clarification_request":null,'
                        '"check_request":{"actor_id":"player-1","ability":"STR","skill_name":"Athletics","dc":1,"advantage_state":"normal","reason":"Climb quickly onto the wagon roof.","requires_sight":false,"requires_hearing":false,"interacting_with_actor_id":null},'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":[],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[],'
                        '"on_success":{"public_text":"You haul yourself up onto the wagon roof and get a better view down the trail.","dm_note":"","operations":[{"operation_type":"update_scene_state_note","note":"Player 1 reached the wagon roof for a higher vantage."}]},'
                        '"on_failure":{"public_text":"You slip on the side rail and stay on the ground.","dm_note":"","operations":[]},'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                }
            ]
        )
        self._shift_to_high_road(session)
        player = session.state.actors['player-1']
        player.ability_modifiers[Ability.STR] = max(player.ability_modifiers.get(Ability.STR, 0), 10)
        session.execute_for_controller('player-1-controller', '/do I climb up onto the wagon roof for a better view.')
        self.assertIsNotNone(session.story_state.pending_check)
        self.assertIsNotNone(session.story_state.pending_adjudication)
        self.assertEqual(len(transport.requests), 1)
        session.execute_for_controller('player-1-controller', '/check')
        self.assertEqual(len(transport.requests), 1)
        self.assertIsNone(session.story_state.pending_check)
        self.assertIsNone(session.story_state.pending_adjudication)
        self.assertIn('Player 1 reached the wagon roof for a higher vantage.', session.story_state.metadata.get('scene_state_notes', ''))

    def test_combat_improvised_action_cannot_bypass_action_economy(self) -> None:
        session, transport = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 tries to kick a crate into the goblin.",'
                        '"doable":true,'
                        '"adjudication_type":"automatic_success",'
                        '"reasoning_summary_for_dm":"Treat it as a combat action.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":{"cost_type":"action","movement_cost_ft":0,"reason":"This takes the actor\'s main effort in combat."},'
                        '"improvised_objects_to_create":[],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[],'
                        '"on_success":{"public_text":"The crate slams toward the goblin.","dm_note":"","operations":[]},'
                        '"on_failure":null,'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                },
                {
                    'output_text': (
                        '{'
                        '"action_summary":"Player 1 cannot spare another combat action.",'
                        '"doable":false,'
                        '"adjudication_type":"impossible",'
                        '"reasoning_summary_for_dm":"The actor already spent its action this turn.",'
                        '"clarification_request":null,'
                        '"check_request":null,'
                        '"save_request":null,'
                        '"contest_request":null,'
                        '"attack_request":null,'
                        '"action_cost_recommendation":null,'
                        '"improvised_objects_to_create":[],'
                        '"terrain_changes_to_create":[],'
                        '"operation_plan":[],'
                        '"on_success":null,'
                        '"on_failure":{"public_text":"You are out of time to improvise anything elaborate before the goblin reacts.","dm_note":"","operations":[]},'
                        '"on_partial":null,'
                        '"mode_switch_recommendation":null'
                        '}'
                    )
                },
            ]
        )
        self._put_player_one_in_combat(session, action_available=False)
        session.execute_for_controller('player-1-controller', '/do I kick a crate into the goblin.')
        self.assertEqual(len(transport.requests), 2)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('has no action available', retry_text)

    def test_direct_save_contest_and_attack_bridges_use_existing_engine(self) -> None:
        session, _transport = self._build_session([])
        runtime = session.adjudication_runtime

        save_plan = AdjudicationPlan(
            action_summary='Force the goblin to duck from a sudden burst of sparks.',
            doable=True,
            adjudication_type=AdjudicationType.SAVING_THROW,
            reasoning_summary_for_dm='A save cleanly models the imposed effect.',
            save_request=AdjudicationSaveRequest(
                target_actor_ids=('monster-goblin-1',),
                save_ability=Ability.DEX,
                dc=1,
                advantage_state=D20RollMode.NORMAL,
                reason='Avoid the shower of sparks.',
            ),
            on_success=AdjudicationBranch(public_text='The goblin ducks the sparks.'),
            on_failure=AdjudicationBranch(public_text='The goblin takes the sparks head-on.'),
        )
        save_result = runtime.execute_plan(session.state, runtime_mode=RuntimeMode.STORYTELLING, controller_id='player-1-controller', actor_id='player-1', plan=save_plan)
        self.assertEqual(save_result.outcome, 'resolved')
        self.assertTrue(any(event.__class__.__name__ == 'DMSaveIssuedEvent' for event in session.state.event_log))
        self.assertTrue(any(event.__class__.__name__ == 'SaveRequestedEvent' for event in session.state.event_log))

        contest_plan = AdjudicationPlan(
            action_summary='Wrest the map case away from the goblin scout.',
            doable=True,
            adjudication_type=AdjudicationType.CONTEST,
            reasoning_summary_for_dm='This is directly opposed effort.',
            contest_request=AdjudicationContestRequest(
                actor_a=ContestParticipantRequest(actor_id='player-1', ability=Ability.STR, skill_name='Athletics', advantage_state=D20RollMode.NORMAL),
                actor_b=ContestParticipantRequest(actor_id='monster-goblin-1', ability=Ability.DEX, skill_name='Acrobatics', advantage_state=D20RollMode.NORMAL),
                tie_rule=ContestTieRule.DEFENDER_WINS,
                reason='Pull the case free before the goblin slips away.',
            ),
            on_success=AdjudicationBranch(public_text='You wrench the case free.'),
            on_failure=AdjudicationBranch(public_text='The goblin twists away with the case.'),
            on_partial=AdjudicationBranch(public_text='Neither of you gets clear control.'),
        )
        contest_result = runtime.execute_plan(session.state, runtime_mode=RuntimeMode.STORYTELLING, controller_id='player-1-controller', actor_id='player-1', plan=contest_plan)
        self.assertEqual(contest_result.outcome, 'resolved')
        self.assertTrue(any(event.__class__.__name__ == 'DMContestIssuedEvent' for event in session.state.event_log))
        self.assertGreaterEqual(sum(1 for event in session.state.event_log if event.__class__.__name__ == 'CheckRequestedEvent'), 2)

        self._put_player_one_in_combat(session)
        attack_actor_id = 'monster-goblin-1'
        attack_actor = session.state.actors[attack_actor_id]
        attack_id = next((attack_key for attack_key in attack_actor.attacks if 'bow' in attack_key.lower()), next(iter(attack_actor.attacks)))
        session.state.active_actor_id = attack_actor_id
        session.state.initiative_order = (attack_actor_id, 'player-1')
        attack_plan = AdjudicationPlan(
            action_summary='Loose a quick shot with the goblin shortbow.',
            doable=True,
            adjudication_type=AdjudicationType.ATTACK_ROLL,
            reasoning_summary_for_dm='Use the existing attack flow.',
            attack_request=AdjudicationAttackRequest(
                attacker_id=attack_actor_id,
                target_id='player-1',
                attack_mode=AdjudicationAttackMode.RANGED,
                attack_id=attack_id,
                supporting_reason='A fast improvised ranged attack still resolves as an attack roll.',
            ),
            on_success=AdjudicationBranch(public_text='The shot lands cleanly.'),
            on_failure=AdjudicationBranch(public_text='The shot goes wide.'),
        )
        attack_result = runtime.execute_plan(session.state, runtime_mode=RuntimeMode.COMBAT, controller_id='dm', actor_id=attack_actor_id, plan=attack_plan)
        self.assertIn(attack_result.outcome, {'hit', 'miss'})
        self.assertTrue(any(event.__class__.__name__ == 'AttackDeclaredEvent' for event in session.state.event_log))
        self.assertTrue(any(event.__class__.__name__ == 'AdjudicatedActionResolvedEvent' for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
