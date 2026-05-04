from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class BladeWardCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Blade Ward')
        self.advance_to_actor(session, 'player-1')
        return session

    def test_cast_creates_the_self_protection_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blade-ward')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Blade Ward')
        self.assertIn('player-1', effect.target_actor_ids)
        self.assertTrue(effect.definition.concentration)

    def test_incoming_attack_rolls_against_the_caster_are_penalized(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blade-ward')
        modifier, events = session.command_interface.kernel._incoming_attack_roll_penalty(session.state, target_actor_id='player-1')
        self.assertLess(modifier, 0)
        self.assertTrue(events)

    def test_other_creatures_do_not_receive_the_penalty(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blade-ward')
        modifier, events = session.command_interface.kernel._incoming_attack_roll_penalty(session.state, target_actor_id='monster-skeleton-1')
        self.assertEqual(modifier, 0)
        self.assertFalse(events)


if __name__ == '__main__':
    unittest.main()
