from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class GoodberryLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Goodberry'
    SPELL_SLUG = 'goodberry'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(1, 0, 0)
        return session

    def _cast(self, session) -> None:
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)

    def test_command_shape_casts_on_self(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 goodberry')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertIsNone(intent.target_id)

    def test_cast_grants_ten_goodberries_to_inventory(self) -> None:
        session = self._setup_session()
        self._cast(session)
        self.assertEqual(session.state.actors['player-1'].carried_item_counts.get('goodberry'), 10)

    def test_cast_refreshes_the_goodberry_item_capability(self) -> None:
        session = self._setup_session()
        self._cast(session)
        capability = session.state.actors['player-1'].capabilities['goodberry']
        self.assertEqual(capability.remaining_uses, 10)
        self.assertEqual(capability.capability.action_cost, 'bonus')

    def test_using_a_goodberry_on_self_heals_one_hit_point_and_consumes_one(self) -> None:
        session = self._setup_session()
        self._cast(session)
        actor = session.state.actors['player-1']
        actor.current_hit_points = actor.max_hit_points - 3
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/use player-1 goodberry player-1')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, actor.max_hit_points - 2)
        self.assertEqual(session.state.actors['player-1'].carried_item_counts.get('goodberry'), 9)

    def test_using_a_goodberry_on_another_creature_heals_that_target(self) -> None:
        session = self._setup_session()
        self._cast(session)
        target = session.state.actors['monster-mage-1']
        target.current_hit_points = target.max_hit_points - 4
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/use player-1 goodberry monster-mage-1')
        self.assertEqual(session.state.actors['monster-mage-1'].current_hit_points, target.max_hit_points - 3)
        self.assertEqual(session.state.actors['player-1'].carried_item_counts.get('goodberry'), 9)

    def test_goodberry_capability_disappears_after_the_last_berry_is_used(self) -> None:
        session = self._setup_session()
        self._cast(session)
        self.advance_to_actor(session, 'player-1')
        for _ in range(10):
            session.state, _ = session.command_interface.execute(session.state, '/use player-1 goodberry player-1')
            session.state.actors['player-1'].bonus_action_available = True
        self.assertNotIn('goodberry', session.state.actors['player-1'].carried_item_counts)
        self.assertNotIn('goodberry', session.state.actors['player-1'].capabilities)


if __name__ == '__main__':
    unittest.main()
