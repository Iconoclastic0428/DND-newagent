from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from dm_agent.memory import DmMemoryWriter
from rules_engine.progression import CampaignProgressionEngine
from session_server import build_default_encounter_session
from session_server.storytelling_session import StorytellingSession
from shared_types.encounter_events import (
    LevelUpQueuedEvent,
    MilestoneCompletedEvent,
    ProgressionEligibilityUpdatedEvent,
    XPRewardAppliedEvent,
    XPRewardLoggedEvent,
)
from shared_types.errors import EncounterPermissionError
from shared_types.progression import (
    MilestoneDistributionPolicy,
    MilestoneSourceType,
    ProgressionMode,
    ProgressionPolicy,
    ProgressionRecipientScope,
    XPDistributionPolicy,
    XPRewardSourceType,
)
from shared_types.storytelling import RuntimeMode, StoryRuntimeState
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


_ONE_ACTOR = (('player-1', 'Player 1', 1),)
_FOUR_ACTORS = (
    ('player-1', 'Player 1', 1),
    ('player-2', 'Player 2', 1),
    ('player-3', 'Player 3', 1),
    ('player-4', 'Player 4', 1),
)


class CampaignProgressionEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = CampaignProgressionEngine()

    def test_xp_logging_and_threshold_queue(self) -> None:
        state = self.engine.initial_state(actor_snapshots=_ONE_ACTOR)
        state, first_events = self.engine.log_xp_reward(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='bonus-299',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=299,
            reason='Almost level two',
            timestamp_seconds=1,
        )
        self.assertEqual(state.actor_progress['player-1'].xp_total, 299)
        self.assertEqual(state.actor_progress['player-1'].eligible_level, 1)
        self.assertFalse(state.pending_level_ups)
        self.assertTrue(any(isinstance(event, XPRewardLoggedEvent) for event in first_events))

        state, second_events = self.engine.log_xp_reward(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='bonus-1',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=1,
            reason='Threshold reached',
            timestamp_seconds=2,
        )
        self.assertEqual(state.actor_progress['player-1'].xp_total, 300)
        self.assertEqual(state.actor_progress['player-1'].current_level, 1)
        self.assertEqual(state.actor_progress['player-1'].eligible_level, 2)
        self.assertIn('level-up:xp:player-1:2', state.pending_level_ups)
        self.assertTrue(any(isinstance(event, LevelUpQueuedEvent) for event in second_events))
        self.assertTrue(any(isinstance(event, ProgressionEligibilityUpdatedEvent) for event in second_events))

    def test_xp_dedupe_prevents_double_award(self) -> None:
        state = self.engine.initial_state(actor_snapshots=_ONE_ACTOR)
        state, first_events = self.engine.log_xp_reward(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.QUEST_OBJECTIVE,
            source_id='deliver-wagon',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=150,
            reason='Escort complete',
            timestamp_seconds=1,
        )
        state, second_events = self.engine.log_xp_reward(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.QUEST_OBJECTIVE,
            source_id='deliver-wagon',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=150,
            reason='Escort complete',
            timestamp_seconds=2,
        )
        self.assertEqual(len(state.xp_rewards), 1)
        self.assertEqual(state.actor_progress['player-1'].xp_total, 150)
        self.assertTrue(first_events)
        self.assertEqual(second_events, ())

    def test_progression_policies_apply_expected_recipient_amounts(self) -> None:
        state = self.engine.initial_state(
            actor_snapshots=_FOUR_ACTORS,
            policy=ProgressionPolicy(xp_distribution=XPDistributionPolicy.PARTY_WIDE),
        )
        state, _ = self.engine.log_xp_reward(
            state,
            actor_snapshots=_FOUR_ACTORS,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='party-wide',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=tuple(actor_id for actor_id, _label, _level in _FOUR_ACTORS),
            amount=100,
            reason='Party-wide award',
            timestamp_seconds=1,
        )
        self.assertEqual({actor_id: state.actor_progress[actor_id].xp_total for actor_id, _label, _level in _FOUR_ACTORS}, {
            'player-1': 100,
            'player-2': 100,
            'player-3': 100,
            'player-4': 100,
        })

        state, _ = self.engine.set_policy(
            state,
            policy=replace(state.policy, xp_distribution=XPDistributionPolicy.EQUAL_SHARE),
            actor_snapshots=_FOUR_ACTORS,
        )
        state, _ = self.engine.log_xp_reward(
            state,
            actor_snapshots=_FOUR_ACTORS,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='equal-share',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=tuple(actor_id for actor_id, _label, _level in _FOUR_ACTORS),
            amount=101,
            reason='Equal-share award',
            timestamp_seconds=2,
        )
        self.assertEqual(state.actor_progress['player-1'].xp_total, 126)
        self.assertEqual(state.actor_progress['player-2'].xp_total, 125)
        self.assertEqual(state.actor_progress['player-3'].xp_total, 125)
        self.assertEqual(state.actor_progress['player-4'].xp_total, 125)

        state, _ = self.engine.set_policy(
            state,
            policy=replace(state.policy, xp_distribution=XPDistributionPolicy.INDIVIDUAL),
            actor_snapshots=_FOUR_ACTORS,
        )
        state, _ = self.engine.log_xp_reward(
            state,
            actor_snapshots=_FOUR_ACTORS,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='individual',
            recipient_scope=ProgressionRecipientScope.SUBSET,
            recipient_actor_ids=('player-1', 'player-3'),
            amount=50,
            reason='Individual award',
            timestamp_seconds=3,
        )
        self.assertEqual(state.actor_progress['player-1'].xp_total, 176)
        self.assertEqual(state.actor_progress['player-2'].xp_total, 125)
        self.assertEqual(state.actor_progress['player-3'].xp_total, 175)
        self.assertEqual(state.actor_progress['player-4'].xp_total, 125)

    def test_milestone_logging_dedupe_and_pending_queue(self) -> None:
        state = self.engine.initial_state(actor_snapshots=_ONE_ACTOR, mode=ProgressionMode.MILESTONE)
        state, first_events = self.engine.complete_milestone(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='phandalin',
            source_type=MilestoneSourceType.CHAPTER_BEAT_REACHED,
            source_id='chapter-01-finish',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            reason='Chapter complete',
            timestamp_seconds=10,
        )
        self.assertEqual(state.actor_progress['player-1'].granted_milestone_advancements, 1)
        self.assertEqual(state.actor_progress['player-1'].eligible_level, 2)
        self.assertIn('level-up:milestone:player-1:2', state.pending_level_ups)
        self.assertTrue(any(isinstance(event, MilestoneCompletedEvent) for event in first_events))

        state, second_events = self.engine.complete_milestone(
            state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='phandalin',
            source_type=MilestoneSourceType.CHAPTER_BEAT_REACHED,
            source_id='chapter-01-finish',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            reason='Chapter complete',
            timestamp_seconds=11,
        )
        self.assertEqual(len(state.milestone_records), 1)
        self.assertEqual(second_events, ())

    def test_pending_queue_respects_multiple_pending_policy(self) -> None:
        multi_state = self.engine.initial_state(
            actor_snapshots=_ONE_ACTOR,
            policy=ProgressionPolicy(allow_multiple_pending_level_ups=True),
        )
        multi_state, _ = self.engine.log_xp_reward(
            multi_state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='big-award',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=2700,
            reason='Catch-up award',
            timestamp_seconds=1,
        )
        self.assertEqual(sorted(record.target_new_total_level for record in multi_state.pending_level_ups.values()), [2, 3, 4])

        single_state = self.engine.initial_state(
            actor_snapshots=_ONE_ACTOR,
            policy=ProgressionPolicy(allow_multiple_pending_level_ups=False),
        )
        single_state, _ = self.engine.log_xp_reward(
            single_state,
            actor_snapshots=_ONE_ACTOR,
            campaign_id='lmop',
            session_id='session-1',
            scene_id='scene-1',
            location_id='waterdeep',
            source_type=XPRewardSourceType.DM_MANUAL,
            source_id='big-award',
            recipient_scope=ProgressionRecipientScope.PARTY,
            recipient_actor_ids=('player-1',),
            amount=2700,
            reason='Catch-up award',
            timestamp_seconds=1,
        )
        self.assertEqual(sorted(record.target_new_total_level for record in single_state.pending_level_ups.values()), [2])

    def test_replay_sequence_is_deterministic(self) -> None:
        def run_sequence():
            state = self.engine.initial_state(actor_snapshots=_ONE_ACTOR)
            state, _ = self.engine.log_xp_reward(
                state,
                actor_snapshots=_ONE_ACTOR,
                campaign_id='lmop',
                session_id='session-1',
                scene_id='scene-1',
                location_id='waterdeep',
                source_type=XPRewardSourceType.DM_MANUAL,
                source_id='award-1',
                recipient_scope=ProgressionRecipientScope.PARTY,
                recipient_actor_ids=('player-1',),
                amount=300,
                reason='Threshold',
                timestamp_seconds=1,
            )
            state, _ = self.engine.complete_milestone(
                state,
                actor_snapshots=_ONE_ACTOR,
                campaign_id='lmop',
                session_id='session-1',
                scene_id='scene-1',
                location_id='phandalin',
                source_type=MilestoneSourceType.DM_MANUAL_MILESTONE,
                source_id='dm-beat-1',
                recipient_scope=ProgressionRecipientScope.PARTY,
                recipient_actor_ids=('player-1',),
                reason='DM beat',
                timestamp_seconds=2,
            )
            return state

        first = run_sequence()
        second = run_sequence()
        self.assertEqual(first.actor_progress, second.actor_progress)
        self.assertEqual(first.xp_rewards, second.xp_rewards)
        self.assertEqual(first.milestone_records, second.milestone_records)
        self.assertEqual(first.pending_level_ups, second.pending_level_ups)


class StoryProgressionSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.progression-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _build_session(self) -> StorytellingSession:
        encounter_session = build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)
        story_state = StoryRuntimeState(
            campaign_id='lmop',
            current_scene_id='scene-progression-test',
            runtime_mode=RuntimeMode.STORYTELLING,
            current_chapter_id='chapter-01',
            canonical_location_id='waterdeep',
            current_party_goals=('Track rewards cleanly.',),
            open_loops=('Verify advancement later.',),
            session_log_id='session-progression-test',
        )
        return StorytellingSession(
            encounter_session=encounter_session,
            story_state=story_state,
            campaign_root=Path('campaigns/lmop'),
            memory_writer=DmMemoryWriter(self._tempdir, campaign_id='lmop'),
            dm_runtime=None,
        )

    def test_progression_commands_update_view_and_memory(self) -> None:
        session = self._build_session()
        view = session.execute_for_controller('dm', '/progression xp award party 300 dm_manual tavern-bonus Escort bonus')
        text = '\n'.join(view.summary_lines)
        self.assertIn('Progression:', text)
        self.assertIn('XP 300', text)
        self.assertIn('pending 2', text)

        player_text = '\n'.join(session.view_for_controller('player-1-controller').summary_lines)
        self.assertIn('XP 300', player_text)
        self.assertIn('pending 2', player_text)
        self.assertEqual(session.state.actors['player-1'].level, 1)
        self.assertIn('level-up:xp:player-1:2', session.story_state.progression_state.pending_level_ups)
        self.assertTrue(any(isinstance(event, XPRewardAppliedEvent) for event in session.state.event_log))

        campaign_state = (self._tempdir / 'lmop' / 'dm' / 'summaries' / 'campaign-state.md').read_text(encoding='utf-8')
        session_log = (self._tempdir / 'lmop' / 'dm' / 'sessions' / 'session-progression-test.md').read_text(encoding='utf-8')
        self.assertIn('# Progression', campaign_state)
        self.assertIn('XP reward dm_manual:tavern-bonus', campaign_state)
        self.assertIn('# Progression', session_log)
        self.assertIn('pending 2', session_log)

    def test_player_cannot_award_progression_and_level_does_not_mutate(self) -> None:
        session = self._build_session()
        with self.assertRaises(EncounterPermissionError):
            session.execute_for_controller('player-1-controller', '/progression xp award party 300 dm_manual bad-attempt')
        session.execute_for_controller('dm', '/progression xp award party 300 dm_manual threshold-award')
        self.assertEqual(session.state.actors['player-1'].level, 1)
        self.assertEqual(session.story_state.progression_state.actor_progress['player-1'].eligible_level, 2)

    def test_milestone_projection_is_hidden_from_players_until_revealed(self) -> None:
        session = self._build_session()
        session.execute_for_controller('dm', '/progression mode milestone')
        session.execute_for_controller('dm', '/progression milestone complete party dm_manual_milestone beat-1 Cleared the first beat')

        dm_text = '\n'.join(session.view_for_controller('dm').summary_lines)
        player_text = '\n'.join(session.view_for_controller('player-1-controller').summary_lines)
        self.assertIn('milestones granted 1', dm_text)
        self.assertIn('pending level-up to 2', player_text)
        self.assertNotIn('milestones granted 1', player_text)


if __name__ == '__main__':
    unittest.main()
