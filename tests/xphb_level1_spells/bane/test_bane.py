from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class BaneLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Bane'
    SPELL_SLUG = 'bane'
    COMMAND = '/cast player-1 bane monster-skeleton-1 --target monster-mage-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.CHA] = -50
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.CHA] = 99
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_supported_multiple_targets(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual(tuple((param.key, param.value) for param in intent.parameters), (('target', 'monster-mage-1'),))

    def test_cast_applies_the_active_effect_only_to_failed_targets(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(effect.name == 'Bane' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))
        self.assertFalse(any(effect.name == 'Bane' and 'monster-mage-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_failed_target_gets_a_negative_attack_roll_modifier(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        modifier, events = session.command_interface.kernel._attack_roll_effect_modifier(session.state, actor_id='monster-skeleton-1')
        self.assertLess(modifier, 0)
        self.assertTrue(events)

    def test_failed_target_gets_a_negative_saving_throw_modifier(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        modifier, events = session.command_interface.kernel._saving_throw_effect_modifier(session.state, actor_id='monster-skeleton-1')
        self.assertLess(modifier, 0)
        self.assertTrue(events)

    def test_effect_persists_through_a_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Bane' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
