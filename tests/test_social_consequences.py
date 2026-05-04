from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import json
import shutil
import unittest
from uuid import uuid4

from session_server import build_lmop_story_demo_session
from session_server.web_projection import project_story_session_projection, project_story_session_view
from shared_types.encounter_events import SocialInfluenceResolvedEvent
from shared_types.exploration import SocialApproachType, SocialOutcome
from shared_types.social import MagicalNormTag, NormProfile, NormScope, SocialIncident, SocialIncidentCategory, SocialIncidentSeverity, WitnessReactionCategory
from shared_types.spellcasting import SpellPerceptibilityProfile
from shared_types.storytelling import StoryTranscriptEntry, StoryTranscriptVisibility
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


class SocialConsequencesTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.social-consequence-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        repo_campaign_root = Path(__file__).resolve().parents[1] / 'campaigns' / 'lmop'
        self.campaign_root = self._tempdir / 'campaigns' / 'lmop'
        shutil.copytree(repo_campaign_root, self.campaign_root)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _build_session(self, payloads: list[dict]):
        return build_lmop_story_demo_session(
            base_url=LOCAL_MIRROR_BASE_URL,
            campaign_root=self.campaign_root,
            env_path=self.env_path,
            client_transport=QueueTransport(payloads),
        )

    def _ignore_payload(self) -> dict:
        payload = {
            'public_narration': 'Gundren notices the spellcasting but does not treat it as a threat.',
            'witness_reactions': [
                {
                    'witness_id': 'gundren-rockseeker',
                    'reaction_category': 'notices_but_ignores',
                    'summary': 'Gundren reads the spell as practical magic and lets it pass.',
                    'public_text': 'Gundren eyes the magic, then waves the moment onward.',
                    'private_note': 'He is watching, but not alarmed.',
                }
            ],
            'scene_note': 'The room accepts the magic without escalation.',
            'dm_note': 'No immediate social penalty from the spell.',
            'escalation': {'recommended': False, 'reason': '', 'mode_switch_decision': None},
        }
        return {'output_text': json.dumps(payload, ensure_ascii=False)}

    def _report_payload(self) -> dict:
        payload = {
            'public_narration': 'The spell lands badly in the room, and Gundren starts thinking about the Watch.',
            'witness_reactions': [
                {
                    'witness_id': 'gundren-rockseeker',
                    'reaction_category': 'report_to_authority',
                    'summary': 'Gundren sees the spellcasting as improper and worth reporting to the authorities.',
                    'public_text': 'Easy there. Keep that sort of magic under control.',
                    'private_note': 'He is weighing whether to report the matter to the Watch.',
                }
            ],
            'scene_note': 'The spellcasting introduces legal and social risk.',
            'dm_note': 'Gundren may pass this along to the Watch later.',
            'escalation': {'recommended': False, 'reason': '', 'mode_switch_decision': None},
        }
        return {'output_text': json.dumps(payload, ensure_ascii=False)}

    def _last_spell_resolution(self, session):
        matches = [event for event in session.state.event_log if event.__class__.__name__ == 'StoryModeSpellcastResolvedEvent']
        self.assertTrue(matches)
        return matches[-1].resolution

    def test_social_state_bootstraps_relationships_and_norms(self) -> None:
        session = self._build_session([])
        social = session.story_state.social_state
        self.assertIn('relationship:gundren-rockseeker:party', social.relationships)
        self.assertIn('relationship:sildar-hallwinter:party', social.relationships)
        self.assertIn('norm:waterdeep-public-order', social.norm_profiles)
        self.assertIn('norm:waterdeep-anti-enchantment', social.norm_profiles)
        exploration = session.story_state.exploration_state
        assert exploration is not None
        self.assertEqual(
            social.relationships['relationship:gundren-rockseeker:party'].attitude,
            exploration.npc_states['gundren-rockseeker'].attitude,
        )

    def test_story_spell_witness_packet_includes_norms_and_relationship_context(self) -> None:
        session = self._build_session([self._ignore_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        resolution = self._last_spell_resolution(session)
        gundren = next(witness for witness in resolution.witness_packet.witnesses if witness.observer_id == 'gundren-rockseeker')
        self.assertIn('norm:waterdeep-public-order', gundren.applicable_norm_ids)
        self.assertIn('guarded_magic', gundren.norm_tags)
        self.assertIn('public_order_sensitive', gundren.norm_tags)
        self.assertEqual(gundren.relationship_trust, 0)
        self.assertEqual(gundren.relationship_suspicion, 0)
        self.assertEqual(gundren.relationship_fear, 0)
        self.assertEqual(gundren.relationship_respect, 0)

    def test_helpful_public_magic_updates_reputation_and_schedules_rumor(self) -> None:
        session = self._build_session([self._ignore_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        social = session.story_state.social_state
        self.assertGreaterEqual(social.location_reputations['waterdeep'].respect, 1)
        self.assertTrue(any(task.propagation_kind.value == 'local_rumor' for task in social.propagation_queue.values()))
        player_view = project_story_session_view(session, 'player-1-controller', session_id='social-test')
        rendered = '\n'.join(player_view.summary_lines)
        self.assertIn('Social consequences:', rendered)
        self.assertIn('Gundren notices the spellcasting', rendered)

    def test_unwitnessed_componentless_spell_stays_dm_only_with_no_propagation(self) -> None:
        session = self._build_session([])
        actor = session.state.actors['player-1']
        actor.spells['cure-wounds'] = replace(
            actor.spells['cure-wounds'],
            perceptibility=SpellPerceptibilityProfile(componentless_casting=True, effect_visible=False, effect_audible=False),
        )
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        social = session.story_state.social_state
        self.assertEqual(len(social.incidents), 1)
        self.assertFalse(social.propagation_queue)
        self.assertTrue(any(projection.summary == 'No one in the scene clearly witnessed the spellcasting.' and projection.audience.value == 'dm_only' for projection in social.known_projections.values()))
        dm_view = project_story_session_view(session, 'dm', session_id='social-test')
        player_view = project_story_session_view(session, 'player-1-controller', session_id='social-test')
        self.assertIn('No one in the scene clearly witnessed the spellcasting.', '\n'.join(dm_view.summary_lines))
        self.assertNotIn('No one in the scene clearly witnessed the spellcasting.', '\n'.join(player_view.summary_lines))

    def test_suspicious_spellcasting_schedules_authority_report_and_hides_dm_only_details(self) -> None:
        session = self._build_session([self._report_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 detect-magic')
        social = session.story_state.social_state
        self.assertTrue(any(task.target_id == 'waterdeep-watch' for task in social.propagation_queue.values()))
        self.assertGreaterEqual(social.relationships['relationship:gundren-rockseeker:party'].suspicion, 2)
        self.assertGreaterEqual(social.location_reputations['waterdeep'].suspicion, 1)
        dm_view = session.view_for_controller('dm')
        player_view = session.view_for_controller('player-1-controller')
        dm_text = '\n'.join(dm_view.summary_lines)
        player_text = '\n'.join(player_view.summary_lines)
        self.assertIn('Pending propagation:', dm_text)
        self.assertIn('Waterdeep Watch', dm_text)
        self.assertNotIn('Pending propagation:', player_text)
        self.assertNotIn('Waterdeep Watch', player_text)

    def test_failed_influence_sets_retry_cooldown_and_raises_next_social_dc(self) -> None:
        session = self._build_session([])
        actor = session.state.actors['player-1']
        actor.skill_bonuses['Persuasion'] = -20
        session.handle_input('player-1-controller', 'Gundren, bargain with us for a little more coin up front.')
        self.assertIsNotNone(session.story_state.pending_check)
        assert session.story_state.pending_check is not None
        first_dc = session.story_state.pending_check.check_request.dc
        session.execute_for_controller('player-1-controller', '/check')
        self.assertTrue(session.story_state.social_state.retry_cooldowns)
        session.handle_input('player-1-controller', 'Gundren, bargain with us for a little more coin up front.')
        self.assertIsNotNone(session.story_state.pending_check)
        assert session.story_state.pending_check is not None
        self.assertGreater(session.story_state.pending_check.check_request.dc, first_dc)
        prompt = session.prompt_for_controller('player-1-controller')
        self.assertIsNotNone(prompt)
        assert prompt is not None
        self.assertIn('tired of that line of pressure', prompt.prompt)

    def test_propagation_execution_updates_authority_memory_and_dm_writeback(self) -> None:
        session = self._build_session([self._report_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 detect-magic')
        task = next(task for task in session.story_state.social_state.propagation_queue.values() if task.target_id == 'waterdeep-watch')
        session.state.clock_seconds = task.due_at_seconds
        session._sync_memory_files()
        social = session.story_state.social_state
        self.assertFalse(any(queued.target_id == 'waterdeep-watch' for queued in social.propagation_queue.values()))
        self.assertGreaterEqual(social.authority_reputations['waterdeep-watch'].suspicion, 2)
        authority_state = social.location_authorities['authority-state:waterdeep:waterdeep-watch:party']
        self.assertGreaterEqual(authority_state.suspicion, 2)
        self.assertIn('Watch', authority_state.current_alert)
        campaign_state_path = self.campaign_root / 'dm' / 'summaries' / 'campaign-state.md'
        playbook_path = self.campaign_root / 'dm' / 'npc-playbooks' / 'gundren-rockseeker.md'
        self.assertTrue(campaign_state_path.exists())
        self.assertTrue(playbook_path.exists())
        campaign_state = campaign_state_path.read_text(encoding='utf-8')
        playbook = playbook_path.read_text(encoding='utf-8')
        self.assertIn('Waterdeep Watch', campaign_state)
        self.assertIn('Trust and Leverage', playbook)
        self.assertIn('Current willingness', playbook)
        self.assertIn('Detect Magic was cast in story mode at waterdeep.', playbook)

    def test_incident_dedupe_prevents_double_spell_penalty(self) -> None:
        session = self._build_session([self._ignore_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        resolution = self._last_spell_resolution(session)
        social_before = session.story_state.social_state
        incident_count = len(social_before.incidents)
        suspicion_before = social_before.relationships['relationship:gundren-rockseeker:party'].suspicion
        social_state, _, events, _, _, _ = session.social_engine.log_story_spellcast_incident(
            social_before,
            exploration_state=session.story_state.exploration_state,
            context=resolution.context,
            witness_packet=resolution.witness_packet,
            social_reaction_plan=resolution.social_reaction_plan,
            clock_seconds=session.state.clock_seconds,
            location_id=session.story_state.canonical_location_id,
            scene_id=session.story_state.current_scene_id,
        )
        self.assertEqual(len(social_state.incidents), incident_count)
        self.assertEqual(social_state.relationships['relationship:gundren-rockseeker:party'].suspicion, suspicion_before)
        self.assertEqual(events, ())

    def test_norm_precedence_orders_npc_before_location(self) -> None:
        session = self._build_session([])
        social = session.story_state.social_state
        social.norm_profiles['norm:test-location'] = NormProfile(
            norm_id='norm:test-location',
            applies_to_kind='location',
            applies_to_id='waterdeep',
            label='Test Location Norm',
            scope=NormScope.LOCATION,
            tags=(MagicalNormTag.OPEN_MAGIC,),
        )
        social.norm_profiles['norm:test-npc'] = NormProfile(
            norm_id='norm:test-npc',
            applies_to_kind='npc',
            applies_to_id='gundren-rockseeker',
            label='Test NPC Norm',
            scope=NormScope.NPC,
            tags=(MagicalNormTag.RESTRICTED_MAGIC,),
        )
        norms = session.social_engine.norms_for_observer(social, 'gundren-rockseeker', 'waterdeep')
        ids = [profile.norm_id for profile in norms]
        self.assertLess(ids.index('norm:test-npc'), ids.index('norm:test-location'))
        evaluation = session.social_engine.evaluate_norms(social, incident_id='incident:test', witness_id='gundren-rockseeker', location_id='waterdeep')
        self.assertIn('restricted_magic', evaluation.applied_tags)
        self.assertIn('open_magic', evaluation.applied_tags)

    def test_private_controller_transcript_stays_hidden_in_projection(self) -> None:
        session = self._build_session([])
        session.story_state.transcript_entries = session.story_state.transcript_entries + (
            StoryTranscriptEntry(
                speaker='DM',
                text='Private suspicion note.',
                visibility=StoryTranscriptVisibility.PRIVATE_CONTROLLERS,
                controller_ids=('player-2-controller', 'dm'),
            ),
        )
        player_one = project_story_session_projection(session, 'player-1-controller', session_id='social-test')
        player_two = project_story_session_projection(session, 'player-2-controller', session_id='social-test')
        self.assertNotIn('Private suspicion note.', '\n'.join(entry.text for entry in player_one.story.transcript_entries))
        self.assertIn('Private suspicion note.', '\n'.join(entry.text for entry in player_two.story.transcript_entries))

    def test_faction_propagation_executes_without_duplicate_loop(self) -> None:
        session = self._build_session([self._report_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 detect-magic')
        faction_task = next(task for task in session.story_state.social_state.propagation_queue.values() if task.propagation_kind.value == 'faction_propagation')
        session.state.clock_seconds = faction_task.due_at_seconds
        session._sync_memory_files()
        social = session.story_state.social_state
        self.assertFalse(any(task.propagation_kind.value == 'faction_propagation' for task in social.propagation_queue.values()))
        self.assertGreaterEqual(social.faction_relationships['rockseeker'].suspicion, 1)
        record = next(record for record in social.incident_propagations.values() if record.target_id == 'rockseeker')
        self.assertEqual(record.status.value, 'executed')

    def test_authored_witness_archetypes_resolve_for_gundren_and_sildar(self) -> None:
        session = self._build_session([])
        gundren = session.social_engine.witness_archetype_for('gundren-rockseeker', scene_id='scene-waterdeep-gundren-briefing', location_id='waterdeep')
        sildar = session.social_engine.witness_archetype_for('sildar-hallwinter', scene_id='scene-waterdeep-gundren-briefing', location_id='waterdeep')
        self.assertIsNotNone(gundren)
        self.assertIsNotNone(sildar)
        assert gundren is not None and sildar is not None
        self.assertEqual(gundren.archetype_id, 'merchant')
        self.assertEqual(sildar.archetype_id, 'watch_officer')

    def test_scene_binding_norms_apply_before_location_defaults(self) -> None:
        session = self._build_session([])
        social = session.story_state.social_state
        norms = session.social_engine.norms_for_observer(social, 'gundren-rockseeker', 'waterdeep', scene_id='scene-waterdeep-gundren-briefing')
        norm_ids = [profile.norm_id for profile in norms]
        self.assertIn('norm:scene:tavern-common-room', norm_ids)
        self.assertIn('norm:waterdeep-public-order', norm_ids)
        self.assertIn('norm:gundren-public-secrecy', norm_ids)
        self.assertLess(norm_ids.index('norm:scene:tavern-common-room'), norm_ids.index('norm:waterdeep-public-order'))

    def test_helpful_public_magic_selects_authored_template_and_chain(self) -> None:
        session = self._build_session([self._ignore_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        incident = next(reversed(tuple(session.story_state.social_state.incidents.values())))
        self.assertIn('consequence:helpful-public-magic', incident.consequence_template_ids)
        self.assertTrue(any(task.chain_id == 'chain:local-rumor' for task in session.story_state.social_state.propagation_queue.values()))

    def test_guarded_enchantment_template_is_selected_for_sildar_context(self) -> None:
        session = self._build_session([])
        social = session.story_state.social_state
        incident = SocialIncident(
            incident_id='incident:test-enchantment',
            category=SocialIncidentCategory.ENCHANTMENT_MAGIC_USED,
            scene_id='scene-waterdeep-gundren-briefing',
            location_id='waterdeep',
            timestamp_seconds=0,
            severity=SocialIncidentSeverity.MODERATE,
        )
        norm_eval = session.social_engine.evaluate_norms(social, incident_id=incident.incident_id, witness_id='sildar-hallwinter', location_id='waterdeep', scene_id='scene-waterdeep-gundren-briefing')
        templates = session.social_engine.applicable_consequence_templates(
            incident=incident,
            witness_id='sildar-hallwinter',
            scene_id='scene-waterdeep-gundren-briefing',
            location_id='waterdeep',
            reaction_category=WitnessReactionCategory.REPORT_TO_AUTHORITY,
            norm_evaluation=norm_eval,
        )
        self.assertIn('consequence:guarded-enchantment', {template.template_id for template in templates})

    def test_failed_intimidation_against_gundren_applies_contract_risk_and_blacklist_chain(self) -> None:
        session = self._build_session([])
        exploration = session.story_state.exploration_state
        self.assertIsNotNone(exploration)
        assert exploration is not None
        social_state, _, _, _, _, open_loops = session.social_engine.integrate_exploration_update(
            session.story_state.social_state,
            previous_state=exploration,
            new_state=exploration,
            events=(
                SocialInfluenceResolvedEvent(
                    actor_id='player-1',
                    npc_id='gundren-rockseeker',
                    approach=SocialApproachType.INTIMIDATE,
                    outcome=SocialOutcome.FAILURE,
                    summary='The threat lands badly at the table.',
                ),
            ),
            clock_seconds=session.state.clock_seconds,
            location_id='waterdeep',
            scene_id='scene-waterdeep-gundren-briefing',
        )
        relationship = social_state.relationships['relationship:gundren-rockseeker:party']
        self.assertIn('contract-risk', relationship.temporary_tags)
        self.assertTrue(any(task.chain_id == 'chain:employer-blacklist' for task in social_state.propagation_queue.values()))
        self.assertTrue(any('employer' in loop.lower() or 'warn others' in loop.lower() for loop in open_loops))

    def test_reapplying_same_authored_consequence_does_not_duplicate_chain(self) -> None:
        session = self._build_session([self._ignore_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 cure-wounds player-1')
        social = session.story_state.social_state
        incident = next(reversed(tuple(social.incidents.values())))
        before = len(social.propagation_queue)
        norm_eval = session.social_engine.evaluate_norms(social, incident_id=incident.incident_id, witness_id='gundren-rockseeker', location_id='waterdeep', scene_id='scene-waterdeep-gundren-briefing')
        session.social_engine._apply_consequence_templates(
            social,
            incident_id=incident.incident_id,
            witness_id='gundren-rockseeker',
            witness_label='Gundren Rockseeker',
            scene_id='scene-waterdeep-gundren-briefing',
            location_id='waterdeep',
            reaction_category=WitnessReactionCategory.IGNORE,
            norm_evaluation=norm_eval,
            clock_seconds=session.state.clock_seconds,
            emitted=[],
            notes=[],
            open_loops=[],
        )
        self.assertEqual(len(social.propagation_queue), before)

    def test_dm_only_authored_suspicion_projection_stays_hidden_from_players(self) -> None:
        session = self._build_session([self._report_payload()])
        session.execute_for_controller('player-1-controller', '/cast player-1 detect-magic')
        dm_view = project_story_session_view(session, 'dm', session_id='social-test')
        player_view = project_story_session_view(session, 'player-1-controller', session_id='social-test')
        self.assertIn('Suspicious public magic should raise scrutiny and often seeds later reports.', '\n'.join(dm_view.summary_lines))
        self.assertNotIn('Suspicious public magic should raise scrutiny and often seeds later reports.', '\n'.join(player_view.summary_lines))


if __name__ == '__main__':
    unittest.main()
