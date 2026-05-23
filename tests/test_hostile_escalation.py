from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from rules_engine.hostile_escalation import HostileEscalationEngine
from session_server import build_lmop_story_demo_session
from session_server.web_projection import project_story_session_view
from shared_types.hostile_escalation import (
    AdHocEncounterSceneKind,
    CombatParticipantGoal,
    FallbackNpcCombatArchetype,
    HostileEscalationOutcome,
    SynthesizedCombatantSourceKind,
    SynthesizedCombatantSpec,
)
from shared_types.spellcasting import SpellPerceptibilityProfile
from shared_types.storytelling import RuntimeMode

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


class HostileEscalationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.hostile-escalation-tests' / uuid4().hex
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
            self.fail(f'Hostile escalation tests wrote shared campaign DM memory: {", ".join(changed_paths)}')

    def _repo_dm_fingerprints(self) -> dict[Path, bytes]:
        dm_root = REPO_ROOT / 'campaigns' / 'lmop' / 'dm'
        return {
            path.relative_to(REPO_ROOT): path.read_bytes()
            for path in sorted(dm_root.rglob('*.md'))
        }

    def _build_session(self, payloads: list[dict]):
        return build_lmop_story_demo_session(
            base_url=Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/',
            env_path=self.env_path,
            client_transport=QueueTransport(payloads),
            campaign_root=self.campaign_root,
        )

    def test_test_fixture_uses_isolated_campaign_root(self) -> None:
        session = self._build_session([])
        repo_campaign_root = Path(__file__).resolve().parents[1] / 'campaigns' / 'lmop'
        self.assertNotEqual(session.campaign_root, repo_campaign_root.resolve())
        self.assertTrue(str(session.campaign_root).startswith(str(self._tempdir.resolve())))

    def test_verbal_threat_alone_can_remain_in_story_mode(self) -> None:
        session = self._build_session([
            {
                'output_text': (
                    '{'
                    '"public_narration":"Gundren meets the threat with a flat stare, but nobody has moved yet.",'
                    '"transcript_entries":[],"check_request":null,"scene_update":null,"mode_switch_decision":null,"memory_note":"Tension rises, but steel stays sheathed."'
                    '}'
                )
            }
        ])
        session.submit_story_action('player-1-controller', 'I warn Gundren that if he cheats us, I will make him regret it.')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertEqual(len(session.dm_runtime.client.transport.requests), 1)

    def test_information_request_about_attack_patterns_remains_story_mode(self) -> None:
        session = self._build_session([])
        decision = session.hostile_escalation_engine.evaluate_declaration(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            actor_id='player-1',
            declaration=(
                'Gundren, I keep hearing tales of goblin ambushes on the Triboar Trail. '
                "What can you tell us about their numbers or attack patterns? I'd rather not be caught off guard."
            ),
            visible_npc_ids=('gundren-rockseeker', 'sildar-hallwinter'),
        )
        self.assertEqual(decision.outcome, HostileEscalationOutcome.REMAIN_IN_STORY_MODE)
        self.assertFalse(decision.clarification_prompt)
        self.assertFalse(decision.order_now_matters)

    def test_question_about_goblins_attacking_remains_story_mode(self) -> None:
        session = self._build_session([])
        decision = session.hostile_escalation_engine.evaluate_declaration(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            actor_id='player-4',
            declaration="And what about the night? If we're camping, do goblins attack in the dark? Should we set watches?",
            visible_npc_ids=('gundren-rockseeker', 'sildar-hallwinter'),
        )
        self.assertEqual(decision.outcome, HostileEscalationOutcome.REMAIN_IN_STORY_MODE)
        self.assertFalse(decision.clarification_prompt)
        self.assertFalse(decision.order_now_matters)

    def test_contextual_attack_aftermath_reference_remains_story_mode(self) -> None:
        session = self._build_session([])
        decision = session.hostile_escalation_engine.evaluate_declaration(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            actor_id='player-2',
            declaration=(
                'I move carefully toward the riderless horses, eyes scanning the ground for tracks or blood. '
                'Then I cast Detect Magic, focusing on the area around the torn packs to see if any magical residue lingers from the attack.'
            ),
            visible_npc_ids=(),
        )
        self.assertEqual(decision.outcome, HostileEscalationOutcome.REMAIN_IN_STORY_MODE)
        self.assertFalse(decision.clarification_prompt)
        self.assertFalse(decision.order_now_matters)

    def test_direct_attack_declaration_still_escalates(self) -> None:
        session = self._build_session([])
        decision = session.hostile_escalation_engine.evaluate_declaration(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            actor_id='player-1',
            declaration='I attack Gundren Rockseeker.',
            visible_npc_ids=('gundren-rockseeker', 'sildar-hallwinter'),
        )
        self.assertEqual(decision.outcome, HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_REINFORCEMENT_TIMER)
        self.assertEqual(decision.target_npc_id, 'gundren-rockseeker')
        self.assertTrue(decision.order_now_matters)

    def test_hostile_declaration_synthesizes_tavern_combat_and_bypasses_llm(self) -> None:
        session = self._build_session([])
        session.submit_story_action('player-1-controller', 'I lunge across the table and stab Gundren Rockseeker.')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertEqual(session.state.battlefield.map_id, 'fallback-tavern-common-room-v1')
        self.assertIn('story-gundren-rockseeker', session.state.actors)
        self.assertIn('story-sildar-hallwinter', session.state.actors)
        self.assertEqual(session.state.actors['story-gundren-rockseeker'].story_context.current_goal, CombatParticipantGoal.FLEE)
        self.assertEqual(session.state.actors['story-sildar-hallwinter'].story_context.current_goal, CombatParticipantGoal.PROTECT)
        self.assertEqual(session.state.actors['story-gundren-rockseeker'].position.x, 10)
        self.assertTrue(any(event.__class__.__name__ == 'ReinforcementScheduledEvent' for event in session.state.event_log))
        self.assertEqual(len(session.dm_runtime.client.transport.requests), 0)

    def test_harmful_story_spell_escalates_before_spell_resolution(self) -> None:
        session = self._build_session([])
        slots_before = session.state.actors['player-1'].resource_pools['spell-slot-1'].current
        session.execute_for_controller('player-1-controller', '/cast player-1 magic-missile gundren-rockseeker')
        self.assertEqual(session.story_state.runtime_mode, RuntimeMode.COMBAT)
        self.assertEqual(session.state.actors['player-1'].resource_pools['spell-slot-1'].current, slots_before)
        self.assertFalse(any(event.__class__.__name__ == 'StoryModeSpellcastValidatedEvent' for event in session.state.event_log))
        self.assertFalse(any(event.__class__.__name__ == 'SpellCastEvent' for event in session.state.event_log))
        self.assertTrue(any(event.__class__.__name__ == 'HostileEscalationTriggeredEvent' for event in session.state.event_log))

    def test_componentless_hostile_spell_marks_unaware_targets_as_surprised(self) -> None:
        session = self._build_session([])
        actor = session.state.actors['player-1']
        actor.spells['fire-bolt'] = replace(
            actor.spells['fire-bolt'],
            perceptibility=SpellPerceptibilityProfile(componentless_casting=True, effect_visible=False, effect_audible=False),
        )
        session.execute_for_controller('player-1-controller', '/cast player-1 fire-bolt gundren-rockseeker')
        self.assertTrue(any(event.__class__.__name__ == 'SurpriseStateComputedEvent' for event in session.state.event_log))
        self.assertTrue(session.state.actors['story-gundren-rockseeker'].surprised)
        self.assertTrue(session.state.actors['story-sildar-hallwinter'].surprised)

    def test_tavern_scene_synthesizer_creates_cover_exits_and_watch_entry(self) -> None:
        engine = HostileEscalationEngine()
        plan = engine.build_scene_plan(scene_id='scene-waterdeep-gundren-briefing', location_id='waterdeep')
        self.assertEqual(plan.scene_kind, AdHocEncounterSceneKind.FALLBACK_TAVERN_COMMON_ROOM)
        self.assertIn('watch-entry', plan.battlefield.spawn_zones)
        self.assertIn('bystanders', plan.battlefield.spawn_zones)
        self.assertIn('bar-counter', plan.battlefield.features)
        self.assertIn('main-door', plan.battlefield.features)
        self.assertFalse(plan.battlefield.tiles[next(iter(plan.battlefield.features['bar-counter'].cells))].traversable)

    def test_synthesis_supports_full_statblock_and_fallback_archetype_paths(self) -> None:
        session = self._build_session([])
        engine = session.hostile_escalation_engine
        runtime_services = session.encounter_session.runtime_services
        assert runtime_services is not None
        mage_id = next(record_id for record_id, record in runtime_services.encounter_catalog.monsters.items() if record.name == 'Mage' and record.source == 'XMM')
        full_spec = SynthesizedCombatantSpec(
            actor_id='story-mage',
            display_name='Room Mage',
            source_npc_id='room-mage',
            monster_id=mage_id,
            source_kind=SynthesizedCombatantSourceKind.FULL_STATBLOCK,
            current_goal=CombatParticipantGoal.ATTACK,
            source_label='Room Mage',
        )
        full_actor = engine.synthesize_actor(runtime_services, full_spec, position=session.state.actors['player-1'].position)
        self.assertEqual(full_actor.name, 'Room Mage')
        self.assertEqual(full_actor.story_context.source_kind, SynthesizedCombatantSourceKind.FULL_STATBLOCK)
        fallback_spec = SynthesizedCombatantSpec(
            actor_id='watch-guard',
            display_name='Watch Guard',
            source_npc_id='watch-guard',
            monster_id=None,
            source_kind=SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK,
            current_goal=CombatParticipantGoal.ARREST,
            fallback_archetype=FallbackNpcCombatArchetype.GUARD_WATCHMAN,
            source_label='Watch Guard',
        )
        fallback_actor = engine.synthesize_actor(runtime_services, fallback_spec, position=session.state.actors['player-1'].position)
        self.assertEqual(fallback_actor.story_context.fallback_archetype, FallbackNpcCombatArchetype.GUARD_WATCHMAN)
        self.assertEqual(fallback_actor.story_context.source_kind, SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK)
        self.assertTrue(fallback_actor.fallback_synthesized)

    def test_local_combat_profile_is_used_for_gundren(self) -> None:
        session = self._build_session([])
        engine = session.hostile_escalation_engine
        decision = engine.evaluate_declaration(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            actor_id='player-1',
            declaration='I stab Gundren Rockseeker.',
            visible_npc_ids=('gundren-rockseeker', 'sildar-hallwinter'),
        )
        hydrated = engine.hydrate_decision(
            encounter_state=session.state,
            story_state=session.story_state,
            exploration_state=session.story_state.exploration_state,
            decision=decision,
            visible_npc_ids=('gundren-rockseeker', 'sildar-hallwinter'),
        )
        gundren = next(spec for spec in hydrated.synthesized_combatants if spec.source_npc_id == 'gundren-rockseeker')
        self.assertEqual(gundren.source_kind, SynthesizedCombatantSourceKind.LOCAL_NPC_DATA)
        self.assertEqual(gundren.monster_id, 'noble-xmm')

    def test_reinforcements_enter_after_timer(self) -> None:
        session = self._build_session([])
        session.submit_story_action('player-1-controller', 'I lunge across the table and stab Gundren Rockseeker.')
        self.assertFalse(any(event.__class__.__name__ == 'ReinforcementEnteredEvent' for event in session.state.event_log))
        for _ in range(12):
            active_actor_id = session.state.active_actor_id
            controller_id = session.encounter_session.control_runtime.controller_for_actor(active_actor_id) or 'dm'
            session.execute_for_controller(controller_id, f'/endturn {active_actor_id}')
            if any(event.__class__.__name__ == 'ReinforcementEnteredEvent' for event in session.state.event_log):
                break
        self.assertTrue(any(event.__class__.__name__ == 'ReinforcementEnteredEvent' for event in session.state.event_log))
        self.assertIn('watch-guard-1', session.state.actors)
        self.assertIn('watch-guard-2', session.state.actors)
        self.assertTrue(any(actor_id.startswith('watch-guard-') for actor_id in session.state.initiative_order))

    def test_story_web_projection_shows_synthesized_combat_transition(self) -> None:
        session = self._build_session([])
        session.submit_story_action('player-1-controller', 'I lunge across the table and stab Gundren Rockseeker.')
        player_view = project_story_session_view(session, 'player-1-controller', session_id='hostile-escalation-test')
        self.assertEqual(player_view.runtime_mode, 'combat')
        self.assertIsNotNone(player_view.map)
        assert player_view.map is not None
        self.assertEqual(player_view.map.map_id, 'fallback-tavern-common-room-v1')
        self.assertTrue(any('Reinforcement timer:' in line for line in player_view.summary_lines))
        self.assertTrue(any(entry.category == 'system' and 'order of actions matter' in entry.text.lower() for entry in player_view.chat_entries))


if __name__ == '__main__':
    unittest.main()
