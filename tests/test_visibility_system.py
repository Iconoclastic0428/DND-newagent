from __future__ import annotations

from dataclasses import replace
import unittest

from encounter_runtime.conditions import get_targeting_visibility_legality
from encounter_runtime.visibility import assess_visibility
from session_server.bootstrap import build_goblin_ambush_encounter_session
from session_server.web_projection import inspect_cell, project_encounter_session_view
from shared_types.encounter_events import ActorRevealedEvent, HideAttemptedEvent, PassiveNoticeTriggeredEvent, SearchAttemptedEvent, StudyAttemptedEvent
from shared_types.errors import EncounterPermissionError
from shared_types.visibility import LightingLevel, ObscurementLevel, ObserverVisibilityState
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class VisibilitySystemTests(unittest.TestCase):
    def _build_session(self):
        return build_goblin_ambush_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def _set_tile(self, session, actor_id: str, *, lighting=None, obscurement=None, blocks_los=None):
        actor = session.state.actors[actor_id]
        key = actor.position.horizontal()
        tile = session.state.battlefield.tiles[key]
        session.state.battlefield.tiles[key] = replace(
            tile,
            lighting=(tile.lighting if lighting is None else lighting),
            obscurement=(tile.obscurement if obscurement is None else obscurement),
            blocks_los=(tile.blocks_los if blocks_los is None else blocks_los),
        )

    def _advance_to_actor(self, session, actor_id: str):
        guard = 0
        while session.state.active_actor_id != actor_id:
            guard += 1
            if guard > 12:
                raise AssertionError(f'Could not advance to {actor_id}.')
            active_actor_id = session.state.active_actor_id
            owner = session.control_runtime.controller_for_actor(active_actor_id)
            session.execute_for_controller(owner, f'/endturn {active_actor_id}')

    def test_darkness_and_heavy_obscurement_affect_visibility_and_targeting(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        monster = session.state.actors['monster-skeleton-1']

        self._set_tile(session, 'monster-skeleton-1', lighting=LightingLevel.DARKNESS)
        darkness_assessment = assess_visibility(session.state, player, monster)
        self.assertEqual(darkness_assessment.visibility_state, ObserverVisibilityState.UNSEEN)
        self.assertFalse(darkness_assessment.can_see_target)
        darkness_legality = get_targeting_visibility_legality(player, monster, requires_target_to_be_seen=True, encounter_state=session.state)
        self.assertFalse(darkness_legality.legal)

        self._set_tile(session, 'monster-skeleton-1', lighting=LightingLevel.BRIGHT, obscurement=ObscurementLevel.HEAVY)
        obscurement_assessment = assess_visibility(session.state, player, monster)
        self.assertEqual(obscurement_assessment.visibility_state, ObserverVisibilityState.UNSEEN)
        self.assertFalse(obscurement_assessment.can_see_target)

    def test_hide_action_and_passive_reveal_flow(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        self._advance_to_actor(session, 'player-1')
        player = session.state.actors['player-1']
        monster = session.state.actors['monster-skeleton-1']
        self._set_tile(session, 'player-1', lighting=LightingLevel.DIM)
        player.skill_bonuses['Stealth'] = 30
        monster.passive_perception = 5

        session.execute_for_controller('player-1-controller', '/hide player-1')

        self.assertTrue(player.hidden)
        self.assertIn('monster-skeleton-1', player.hidden_from_actor_ids)
        self.assertTrue(any(isinstance(event, HideAttemptedEvent) and event.success for event in session.state.event_log))

        monster.passive_perception = 40
        self._advance_to_actor(session, 'monster-skeleton-1')
        destination_x = session.state.actors['monster-skeleton-1'].position.x + 1
        destination_y = session.state.actors['monster-skeleton-1'].position.y
        session.execute_for_controller('dm', f'/move monster-skeleton-1 {destination_x} {destination_y}')

        self.assertNotIn('monster-skeleton-1', session.state.actors['player-1'].hidden_from_actor_ids)
        self.assertTrue(any(isinstance(event, PassiveNoticeTriggeredEvent) and event.observer_id == 'monster-skeleton-1' and event.noticed for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, ActorRevealedEvent) and event.observer_id == 'monster-skeleton-1' for event in session.state.event_log))

    def test_search_and_study_reveal_hidden_targets(self) -> None:
        session = self._build_session()
        session.system_execute('/encounter start')
        self._advance_to_actor(session, 'player-1')
        player = session.state.actors['player-1']
        monster = session.state.actors['monster-skeleton-1']
        self._set_tile(session, 'player-1', lighting=LightingLevel.DIM)
        player.skill_bonuses['Stealth'] = 30
        monster.passive_perception = 5
        session.execute_for_controller('player-1-controller', '/hide player-1')

        self._advance_to_actor(session, 'monster-skeleton-1')
        monster.skill_bonuses['Perception'] = 30
        session.execute_for_controller('dm', '/search monster-skeleton-1')
        self.assertNotIn('monster-skeleton-1', session.state.actors['player-1'].hidden_from_actor_ids)
        self.assertTrue(any(isinstance(event, SearchAttemptedEvent) and 'player-1' in event.discovered_actor_ids for event in session.state.event_log))

        player.hidden = True
        player.stealth_check_total = 18
        player.hidden_from_actor_ids = frozenset({'monster-skeleton-1'})
        monster.action_available = True
        monster.skill_bonuses['Investigation'] = 30
        session.execute_for_controller('dm', '/study monster-skeleton-1')
        self.assertNotIn('monster-skeleton-1', session.state.actors['player-1'].hidden_from_actor_ids)
        self.assertTrue(any(isinstance(event, StudyAttemptedEvent) and 'player-1' in event.discovered_actor_ids for event in session.state.event_log))

    def test_player_projection_hides_hidden_tokens_and_redacts_unseen_contacts(self) -> None:
        session = self._build_session()
        monster = session.state.actors['monster-skeleton-1']
        monster.hidden = True
        monster.stealth_check_total = 18
        monster.hidden_from_actor_ids = frozenset({'player-1'})

        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='visibility-test')
        dm_view = project_encounter_session_view(session, 'dm', session_id='visibility-test')
        player_token_ids = {token.actor_id for token in player_view.map.tokens}
        dm_token_ids = {token.actor_id for token in dm_view.map.tokens}
        self.assertNotIn('monster-skeleton-1', player_token_ids)
        self.assertIn('monster-skeleton-1', dm_token_ids)
        self.assertNotIn('Skeleton', '\n'.join(player_view.summary_lines))

        monster.hidden = False
        monster.stealth_check_total = None
        monster.hidden_from_actor_ids = frozenset()
        self._set_tile(session, 'monster-skeleton-1', lighting=LightingLevel.DARKNESS)
        player_view = project_encounter_session_view(session, 'player-1-controller', session_id='visibility-test')
        unseen_token = next(token for token in player_view.map.tokens if token.actor_id == 'monster-skeleton-1')
        self.assertEqual(unseen_token.visibility_state, 'unseen')
        self.assertEqual(unseen_token.name, 'Unseen contact')
        self.assertEqual(unseen_token.side, 'unknown')

    def test_inspect_cell_requires_current_visibility(self) -> None:
        session = self._build_session()
        self._set_tile(session, 'monster-skeleton-1', lighting=LightingLevel.DARKNESS)
        monster = session.state.actors['monster-skeleton-1']
        with self.assertRaises(EncounterPermissionError):
            inspect_cell(session, 'player-1-controller', x=monster.position.x, y=monster.position.y, z=monster.position.z)
        dm_inspection = inspect_cell(session, 'dm', x=monster.position.x, y=monster.position.y, z=monster.position.z)
        self.assertEqual(dm_inspection.lighting, 'darkness')


if __name__ == '__main__':
    unittest.main()
