from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectStartedEvent
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class SorcererInnateSorceryFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        session = self.build_session(self.complete_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15'))
        self.advance_to_actor(session, 'player-1')
        return session

    def test_feature_name_and_capability_compile(self) -> None:
        record = self.complete_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        actor = self.compile_actor(record)
        self.assertIn('Innate Sorcery', record.class_feature_names)
        self.assertIn('innate-sorcery', actor.capabilities)

    def test_innate_sorcery_starts_an_active_effect_and_spends_a_use(self) -> None:
        session = self._session()
        uses_before = session.state.actors['player-1'].capabilities['innate-sorcery'].remaining_uses
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 innate-sorcery')
        self.assertEqual(session.state.actors['player-1'].capabilities['innate-sorcery'].remaining_uses, uses_before - 1)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(self.events_since(session, start_index, ActiveEffectStartedEvent))

    def test_innate_sorcery_effect_grants_spell_attack_advantage_and_dc_bonus(self) -> None:
        session = self._session()
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 innate-sorcery')
        effect = next(iter(session.state.active_effects.values()))
        self.assertTrue(effect.definition.spell_attack_roll_advantage)
        self.assertEqual(effect.definition.spell_save_dc_bonus, 1)


if __name__ == '__main__':
    unittest.main()
