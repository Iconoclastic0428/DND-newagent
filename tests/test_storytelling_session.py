from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.encounter_events import StoryActionDeclaredEvent
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from shared_types.spellcasting import SpellPerceptibilityProfile
from shared_types.storytelling import StoryCheckRequestState
from session_server import build_lmop_story_demo_session
from session_server.story_orchestrator import present_story_snapshot
from shared_types.storytelling import RuntimeMode, StoryTranscriptEntry, StoryTranscriptVisibility
from shared_types.travel import TravelStatus
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL

REPO_ROOT = Path(__file__).resolve().parents[1]


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


class StorytellingSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.story-session-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self._repo_dm_fingerprints_before = self._repo_dm_fingerprints()
        self.campaign_root = self._tempdir / 'campaign-root'
        shutil.copytree(REPO_ROOT / 'campaigns' / 'lmop', self.campaign_root)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        changed_paths = [
            str(path)
            for path, before in self._repo_dm_fingerprints_before.items()
            if (REPO_ROOT / path).read_bytes() != before
        ]
        shutil.rmtree(self._tempdir, ignore_errors=True)
        if changed_paths:
            self.fail(f'Storytelling session tests wrote shared campaign DM memory: {", ".join(changed_paths)}')

    def _repo_dm_fingerprints(self) -> dict[Path, bytes]:
        dm_root = REPO_ROOT / 'campaigns' / 'lmop' / 'dm'
        return {
            path.relative_to(REPO_ROOT): path.read_bytes()
            for path in sorted(dm_root.rglob('*.md'))
        }

    def _build_session(self, payloads: list[dict]):
        return build_lmop_story_demo_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport(payloads),
            campaign_root=self.campaign_root,
        )

    def test_demo_bootstrap_starts_in_waterdeep_with_four_players(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        self.assertEqual(session.story_state.current_scene_id, 'scene-waterdeep-gundren-briefing')
        self.assertEqual(session.story_state.canonical_location_id, 'waterdeep')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertEqual(sorted(actor_id for actor_id, actor in session.state.actors.items() if actor.side.value == 'player'), ['player-1', 'player-2', 'player-3', 'player-4'])
        self.assertEqual(sorted(actor_id for actor_id, actor in session.state.actors.items() if actor.side.value == 'monster'), ['monster-goblin-1', 'monster-goblin-2', 'monster-goblin-3', 'monster-goblin-4'])

    def test_system_open_scene_adds_waterdeep_intro(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.system_open_scene()
        view = session.view_for_controller('player-1-controller')
        text = '\n'.join(view.summary_lines)
        self.assertIn('Current scene: scene-waterdeep-gundren-briefing', text)
        self.assertIn('A stout dwarf with dust still caught in his beard', text)

    def test_story_turn_can_request_check_for_acting_player(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren leans in and studies your reaction before answering.",'
                        '"transcript_entries":[{"speaker":"Gundren","text":"You have the look of someone who wants the fuller truth.","visibility":"public"}],'
                        '"check_request":{'
                        '"actor_id":"player-1","ability":"WIS","skill_name":"Insight","dc":12,'
                        '"prompt":"Make a Wisdom (Insight) check to read what Gundren is holding back.",'
                        '"reason":"Read Gundren\'s nerves and omissions.",'
                        '"requires_sight":false,"requires_hearing":true,"interacting_with_actor_id":null},'
                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"Gundren is being careful."'
                        '}'
                    )
                }
            ]
        )
        session.system_open_scene()
        session.submit_story_action('player-1-controller', 'I watch Gundren closely and ask what he is not saying.')
        self.assertIsNotNone(session.story_state.pending_check)
        self.assertEqual(session.story_state.pending_check.actor_id, 'player-1')
        self.assertEqual(session.story_state.pending_check.controller_id, 'player-1-controller')
        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.prompt_kind, 'story-check')
        self.assertIn('Wisdom (Insight)', prompt.prompt)

    def test_invalid_story_declaration_does_not_append_public_action_event(self) -> None:
        session = self._build_session([])
        session.system_open_scene()
        declaration = (
            'Gundren, I appreciate the warnings about goblins and rock slides, but what about simpler threats? '
            'A broken wheel or a sudden storm could be just as dangerous. Do we have spare parts beyond what Sildar mentioned?'
        )
        event_count_before = len(session.state.event_log)

        with self.assertRaisesRegex(EncounterValidationError, 'Clarify which NPC'):
            session.submit_story_action('player-3-controller', declaration)

        self.assertEqual(len(session.state.event_log), event_count_before)
        self.assertFalse(
            any(isinstance(event, StoryActionDeclaredEvent) and event.declaration == declaration for event in session.state.event_log)
        )

    def test_story_turn_drops_npc_echo_of_player_declaration(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren Rockseeker leans forward, waiting for the group to answer.",'
                        '"transcript_entries":[{"speaker":"Gundren Rockseeker","text":"What does everyone think?","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        '"memory_note":"Gundren waits for the party decision."'
                        '}'
                    )
                }
            ]
        )
        session.system_open_scene()
        session.submit_story_action('player-2-controller', 'What does everyone think?')

        echoed_entries = [
            entry for entry in session.story_state.transcript_entries
            if entry.speaker == 'Gundren Rockseeker' and entry.text == 'What does everyone think?'
        ]
        self.assertEqual(echoed_entries, [])
        self.assertTrue(any(entry.speaker == 'DM' and 'waiting for the group' in entry.text for entry in session.story_state.transcript_entries))

    def test_story_turn_drops_quoted_player_speech_subset_echo(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"A translucent hand yanks the snare line, springing the trap safely ahead of the wagon.",'
                        '"transcript_entries":[{"speaker":"Player 4","text":"Stand back. I\'ll trip it with Mage Hand no sense giving a goblin a free swing.","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        '"memory_note":"The snare was triggered safely with Mage Hand."'
                        '}'
                    )
                }
            ]
        )
        session.system_open_scene()
        declaration = (
            '"Stand back. I\'ll trip it with Mage Hand no sense giving a goblin a free swing." '
            'I cast the cantrip, sending a spectral hand forward to yank the snare line.'
        )
        session.submit_story_action('player-4-controller', declaration)

        echoed_entries = [
            entry for entry in session.story_state.transcript_entries
            if entry.speaker == 'Player 4' and 'Stand back' in entry.text
        ]
        self.assertEqual(echoed_entries, [])
        self.assertTrue(any(entry.speaker == 'DM' and 'springing the trap safely' in entry.text for entry in session.story_state.transcript_entries))

    def test_story_turn_drops_dm_authored_player_speaker_paraphrase(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"The snare snaps harmlessly as the magic pulls the line from a distance.",'
                        '"transcript_entries":[{"speaker":"Player 4","text":"Stay back. I can trip that from here. Mage Hand should do the trick.","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":null,'
                        '"mode_switch_decision":null,'
                        '"memory_note":"Mage Hand triggered the snare from a safe distance."'
                        '}'
                    )
                }
            ]
        )
        session.system_open_scene()
        declaration = 'I could use a touch of magic to trip that snare from here. No need for anyone to get close. Mage Hand should do it.'
        session.submit_story_action('player-4-controller', declaration)

        player_speaker_entries = [
            entry for entry in session.story_state.transcript_entries
            if entry.speaker == 'Player 4'
        ]
        self.assertEqual(player_speaker_entries, [])
        self.assertTrue(any(entry.speaker == 'DM' and 'snare snaps harmlessly' in entry.text for entry in session.story_state.transcript_entries))

    def test_story_check_prompt_always_names_the_required_check_and_dc(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.story_state.pending_check = StoryCheckRequestState(
            request_id='story-check-player-1',
            actor_id='player-1',
            controller_id='player-1-controller',
            prompt='Secure the wagon wheel and verify the load stability after the jolt.',
            reason='Stabilize the wagon after the road jolt.',
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id='story-check-player-1',
                    source_actor_id=None,
                    target_actor_id='player-1',
                    reason='Stabilize the wagon after the road jolt.',
                ),
                ability=Ability.STR,
                dc=10,
                skill_name='Athletics',
            ),
        )
        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        self.assertIn('Required check: Strength (Athletics).', prompt.prompt)
        self.assertIn('DC: 10.', prompt.prompt)

    def test_foreign_pending_check_is_visible_before_the_story_log(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.story_state.transcript_entries = (
            StoryTranscriptEntry(speaker='DM', text='The wagon creaks along the road.', visibility=StoryTranscriptVisibility.PUBLIC),
        )
        session.story_state.pending_check = StoryCheckRequestState(
            request_id='story-check-player-2',
            actor_id='player-2',
            controller_id='player-2-controller',
            prompt='Roll Wisdom (Perception).',
            reason='Watch the brush for hidden movement.',
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id='story-check-player-2',
                    source_actor_id=None,
                    target_actor_id='player-2',
                    reason='Watch the brush for hidden movement.',
                ),
                ability=Ability.WIS,
                dc=13,
                skill_name='Perception',
            ),
        )
        view = session.view_for_controller('player-1-controller')
        lines = list(view.summary_lines)
        waiting_index = lines.index('Story check pending: waiting on Player 2.')
        story_log_index = lines.index('Story log:')
        self.assertLess(waiting_index, story_log_index)

    def test_story_check_prompt_shows_competition_target_when_present(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.story_state.pending_check = StoryCheckRequestState(
            request_id='story-check-player-3',
            actor_id='player-3',
            controller_id='player-3-controller',
            prompt="Slip a hand toward Gundren's pocket while the others distract him.",
            reason="Attempt to pick Gundren's pocket without being noticed.",
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id='story-check-player-3',
                    source_actor_id=None,
                    target_actor_id='player-3',
                    reason="Attempt to pick Gundren's pocket without being noticed.",
                ),
                ability=Ability.DEX,
                dc=15,
                skill_name='Sleight of Hand',
                interacting_with_actor_id='gundren-rockseeker',
            ),
        )
        prompt = session.prompt_for_controller('player-3-controller')
        self.assertIsNotNone(prompt)
        self.assertIn('Required check: Dexterity (Sleight of Hand).', prompt.prompt)
        self.assertIn('DC: 15.', prompt.prompt)
        self.assertIn('Competition / opposed interaction: Gundren Rockseeker.', prompt.prompt)

    def test_story_check_resolution_uses_rules_engine_and_updates_story(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren gives you a thin smile instead of a straight answer.",'
                        '"transcript_entries":[], '
                        '"check_request":{'
                        '"actor_id":"player-1","ability":"WIS","skill_name":"Insight","dc":10,'
                        '"prompt":"Make a Wisdom (Insight) check to read Gundren.",'
                        '"reason":"Read Gundren.",'
                        '"requires_sight":false,"requires_hearing":true,"interacting_with_actor_id":null},'
                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"The party is probing Gundren."'
                        '}'
                    )
                },
                {
                    'output_text': (
                        '{'
                        '"public_narration":"You catch the flicker of real excitement beneath Gundren\'s caution: Phandalin matters more than a routine cargo drop.",'
                        '"transcript_entries":[{"speaker":"DM","text":"Gundren keeps the map itself off the table, but you know this is bigger than freight.","visibility":"public"}],'
                        '"check_request":null,'
                        '"scene_update":{"summary":"The party now knows Gundren is hiding the scale of the discovery.","party_beliefs":["Gundren is hiding something larger than a wagon contract."],"open_loops":["What exactly did Gundren find near Phandalin?","Why must Gundren reach town ahead of the wagon?"],"party_goals":["Take the job and keep Gundren\'s route intact.","Learn more on the road without forcing his hand too early."]},'
                        '"mode_switch_decision":null,'
                        '"memory_note":"Successful read on Gundren\'s excitement."'
                        '}'
                    )
                },
            ]
        )
        session.system_open_scene()
        session.submit_story_action('player-1-controller', 'I study Gundren for a weakness in his story.')
        session.resolve_pending_check('player-1-controller')
        self.assertIsNone(session.story_state.pending_check)
        self.assertIn('Gundren is hiding something larger than a wagon contract.', session.story_state.metadata.get('party_beliefs', ''))
        self.assertIn('The party now knows Gundren is hiding the scale of the discovery.', session.story_state.recent_summary)
        resolved_events = [event for event in session.state.event_log if event.__class__.__name__ == 'StoryCheckResolvedEvent']
        self.assertTrue(resolved_events)
        self.assertEqual(resolved_events[-1].ability.value, 'WIS')
        self.assertEqual(resolved_events[-1].skill_name, 'Insight')
        self.assertEqual(resolved_events[-1].dc, 10)
        view = session.view_for_controller('player-1-controller')
        text = '\n'.join(view.summary_lines)

        self.assertIn('Recent check results:', text)
        self.assertIn('Wisdom (Insight)', text)
        self.assertIn('vs DC 10', text)
        self.assertIn('Phandalin matters more than a routine cargo drop', text)

    def test_story_turn_can_enter_combat_and_rules_engine_rolls_initiative(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"The road goes deathly quiet for one heartbeat, then goblin arrows cut down from both banks.",'
                        '"transcript_entries":[], '
                        '"check_request":null, '
                        '"scene_update":{"scene_id":"scene-waterdeep-gundren-briefing","location_id":"waterdeep","summary":"The ambush is sprung on the Triboar Trail.","open_loops":["Where were Gundren and Sildar taken?","Can the party survive the ambush and hold the road?"],"party_goals":["Survive the ambush.","Recover clues from the attack site."]},'
                        '"mode_switch_decision":{'
                        '"decision_type":"enter_combat",'
                        '"reason":"The goblin ambush has begun and turn order now matters.",'
                        '"enter_combat_plan":{'
                        '"reason":"The goblin ambush has begun and turn order now matters.",'
                        '"participant_ids":["player-1","player-2","player-3","player-4","monster-goblin-1","monster-goblin-2","monster-goblin-3","monster-goblin-4"],'
                        '"scene_id":"scene-triboar-goblin-ambush",'
                        '"location_id":"triboar-trail",'
                        '"battlefield_map_id":"goblin-ambush-triboar-trail"'
                        '},'
                        '"exit_combat_plan":null,'
                        '"confidence":0.95'
                        '},'
                        '"memory_note":"Combat began at the ambush site."'
                        '}'
                    )
                }
            ]
        )
        session.story_state.current_scene_id = 'scene-00-high-road-journey'
        session.story_state.canonical_location_id = 'high-road'
        session.story_state.current_party_goals = ('Reach Phandalin with the wagon.',)
        session.story_state.open_loops = ('Stay alert on the eastbound trail.',)
        session.submit_story_action('player-2-controller', 'I move up the wagon bench and scan the brush as we round the bend.')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertEqual(session.state.phase.value, 'in-progress')
        self.assertEqual(set(session.state.initiative_order), {'player-1', 'player-2', 'player-3', 'player-4', 'monster-goblin-1', 'monster-goblin-2', 'monster-goblin-3', 'monster-goblin-4'})
        self.assertEqual(session.story_state.current_scene_id, 'scene-triboar-goblin-ambush')
        dm_view = session.view_for_controller('dm')
        rendered = present_story_snapshot(dm_view)
        self.assertIn('actions:', rendered)
        self.assertIn('attacks:', rendered)



    def test_story_mode_witnessed_benign_spell_can_resolve_without_hostility(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren clocks the healing prayer but lets it pass without a hostile move.",'
                        '"witness_reactions":['
                        '{"witness_id":"gundren-rockseeker","reaction_category":"notices_but_ignores","summary":"Gundren reads the spell as practical healing magic.","public_text":"Keep the magic practical and we will have no quarrel.","private_note":"He stays alert, but not alarmed."}'
                        '],'
                        '"scene_note":"Gundren tolerates obvious healing magic during the briefing.",'
                        '"dm_note":"No escalation from the witnessed healing spell.",'
                        '"escalation":{"recommended":false,"reason":"","mode_switch_decision":null}'
                        '}'
                    )
                }
            ]
        )
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertEqual(session.state.actors['player-1'].spells['cure-wounds'].remaining_uses, 0)
        resolved = [event for event in session.state.event_log if event.__class__.__name__ == 'StoryModeSpellcastResolvedEvent']
        self.assertTrue(resolved)
        self.assertTrue(resolved[-1].resolution.witness_packet.witnesses)
        self.assertIsNotNone(resolved[-1].resolution.social_reaction_plan)
        self.assertIn('Gundren clocks the healing prayer', '\n'.join(entry.text for entry in session.story_state.transcript_entries))
        self.assertTrue(any(event.__class__.__name__ == 'SpellcastingSocialReactionResolvedEvent' for event in session.state.event_log))
        self.assertTrue(any(event.__class__.__name__ == 'StoryModeSpellcastIgnoredEvent' for event in session.state.event_log))

    def test_story_mode_componentless_unwitnessed_spell_skips_social_reaction(self) -> None:
        session = self._build_session([])
        actor = session.state.actors['player-1']
        actor.spells['cure-wounds'] = replace(
            actor.spells['cure-wounds'],
            perceptibility=SpellPerceptibilityProfile(componentless_casting=True, effect_visible=False, effect_audible=False),
        )
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        resolved = [event for event in session.state.event_log if event.__class__.__name__ == 'StoryModeSpellcastResolvedEvent']
        self.assertTrue(resolved)
        self.assertEqual(resolved[-1].resolution.witness_packet.witnesses, ())
        self.assertIsNone(resolved[-1].resolution.social_reaction_plan)
        self.assertEqual(len(session.dm_runtime.client.transport.requests), 0)
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertTrue(any(event.__class__.__name__ == 'StoryModeSpellcastIgnoredEvent' for event in session.state.event_log))

    def test_story_mode_spellcasting_reaction_can_escalate_into_combat(self) -> None:
        session = self._build_session(
            [
                {
                    'output_text': (
                        '{'
                        '"public_narration":"Gundren jerks back as the sudden magic changes the room from negotiation to threat.",'
                        '"witness_reactions":['
                        '{"witness_id":"gundren-rockseeker","reaction_category":"escalates_to_mode_switch_candidate","summary":"Gundren mistakes the spellcasting for the start of a fight.","public_text":"No more surprises. Hands where I can see them.","private_note":"He is ready to call for steel."}'
                        '],'
                        '"scene_note":"The briefing collapses into armed tension.",'
                        '"dm_note":"Immediate escalation into combat.",'
                        '"escalation":{'
                        '"recommended":true,'
                        '"reason":"The witnessed spellcasting creates immediate initiative-sensitive conflict.",'
                        '"mode_switch_decision":{'
                        '"decision_type":"enter_combat",'
                        '"reason":"The witnessed spellcasting turns the scene into an armed standoff.",'
                        '"enter_combat_plan":{'
                        '"reason":"The witnessed spellcasting turns the scene into an armed standoff.",'
                        '"participant_ids":["player-1","player-2","player-3","player-4","monster-goblin-1","monster-goblin-2","monster-goblin-3","monster-goblin-4"],'
                        '"scene_id":"scene-waterdeep-gundren-briefing",'
                        '"location_id":"waterdeep",'
                        '"ambush":false,'
                        '"battlefield_map_id":"goblin-ambush-triboar-trail"'
                        '},'
                        '"exit_combat_plan":null,'
                        '"confidence":0.92'
                        '}'
                        '}'
                        '}'
                    )
                }
            ]
        )
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertEqual(session.state.phase.value, 'in-progress')
        self.assertTrue(any(event.__class__.__name__ == 'StoryModeSpellcastEscalationRecommendedEvent' for event in session.state.event_log))
        self.assertTrue(any(event.__class__.__name__ == 'CombatStartedEvent' for event in session.state.event_log))

    def test_demo_bootstrap_initializes_travel_state(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        self.assertIsNotNone(session.story_state.travel_state)
        travel_state = session.story_state.travel_state
        assert travel_state is not None
        self.assertEqual(travel_state.map_id, 'lmop_high_road_region_v1')
        self.assertEqual((travel_state.party_coord.q, travel_state.party_coord.r), (0, 0))
        self.assertEqual(travel_state.status, TravelStatus.IDLE)
        view = session.view_for_controller('player-1-controller')
        rendered = '\n'.join(view.summary_lines)
        self.assertIn('Travel map: lmop_high_road_region_v1', rendered)
        self.assertIn('Travel hex: (0,0)', rendered)

    def test_travel_route_and_advance_interrupt_at_lmop_ambush_hook(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.travel_plan_route('player-1-controller', destination_location_id='phandalin')
        self.assertEqual(session.story_state.travel_state.status, TravelStatus.ROUTE_PLANNED)
        session.travel_advance('player-1-controller', steps=5)
        travel_state = session.story_state.travel_state
        assert travel_state is not None
        self.assertEqual((travel_state.party_coord.q, travel_state.party_coord.r), (5, 0))
        self.assertEqual(travel_state.status, TravelStatus.INTERRUPTED)
        self.assertIsNotNone(travel_state.pending_hook)
        self.assertEqual(travel_state.pending_hook.hook_id, 'hook-ambush-candidate')
        self.assertIn('ambush-horses', travel_state.discovered_landmark_ids)
        self.assertEqual(session.story_state.current_scene_id, 'scene-triboar-goblin-ambush')
        self.assertEqual(session.story_state.canonical_location_id, 'triboar-trail')

    def test_dm_can_engage_pending_travel_hook_into_combat(self) -> None:
        session = self._build_session([{'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'}])
        session.travel_plan_route('player-1-controller', destination_location_id='phandalin')
        session.travel_advance('player-1-controller', steps=5)
        session.travel_engage_pending_hook('dm')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertEqual(session.story_state.current_scene_id, 'scene-triboar-goblin-ambush')
        self.assertEqual(session.story_state.canonical_location_id, 'triboar-trail')
        self.assertEqual(session.state.phase.value, 'in-progress')


if __name__ == '__main__':
    unittest.main()


