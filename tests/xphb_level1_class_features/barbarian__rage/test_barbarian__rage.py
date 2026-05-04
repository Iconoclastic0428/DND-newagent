from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectStartedEvent
from shared_types.models import Ability
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class BarbarianRageFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        session = self.build_session(self.complete_record('barbarian'))
        self.advance_to_actor(session, 'player-1')
        return session

    def test_feature_name_and_capability_compile(self) -> None:
        record = self.complete_record('barbarian')
        actor = self.compile_actor(record)
        self.assertIn('Rage', record.class_feature_names)
        self.assertIn('rage', actor.capabilities)

    def test_rage_starts_an_active_effect_and_spends_a_use(self) -> None:
        session = self._session()
        uses_before = session.state.actors['player-1'].capabilities['rage'].remaining_uses
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 rage')
        self.assertEqual(session.state.actors['player-1'].capabilities['rage'].remaining_uses, uses_before - 1)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(self.events_since(session, start_index, ActiveEffectStartedEvent))

    def test_rage_applies_strength_advantage_resistances_and_spellcasting_lock(self) -> None:
        session = self._session()
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 rage')
        actor = session.state.actors['player-1']
        self.assertIn(Ability.STR, actor.ability_check_advantage_abilities)
        self.assertIn(Ability.STR, actor.saving_throw_advantage_abilities)
        self.assertIn('bludgeoning', actor.damage_resistances)
        self.assertTrue(actor.cannot_cast_spells)


if __name__ == '__main__':
    unittest.main()
