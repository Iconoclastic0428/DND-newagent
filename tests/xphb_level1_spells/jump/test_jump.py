
from __future__ import annotations

import unittest

from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class JumpLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Jump'
    SPELL_SLUG = 'jump'
    COMMAND = '/cast player-1 jump player-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_the_supported_self_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_the_active_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(effect.name == 'Jump' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_effect_sets_the_jump_replacement_distance_and_cost(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        actor = session.state.actors['player-1']
        self.assertEqual(actor.jump_replacement_distance_ft, 30)
        self.assertEqual(actor.jump_replacement_movement_cost_ft, 10)

    def test_effect_duration_is_one_minute_in_combat_rounds(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Jump')
        self.assertEqual(effect.definition.duration.rounds, 10)
        self.assertEqual(effect.definition.duration.duration_type.value, 'rounds')

    def test_effect_persists_through_a_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Jump' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
