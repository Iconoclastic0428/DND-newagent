from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class CompelledDuelLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Compelled Duel'
    SPELL_SLUG = 'compelled-duel'
    COMMAND = '/cast player-1 compelled-duel monster-skeleton-1'

    def _setup_session(self, *, caster_dc: int = 99, target_save_bonus: int = -50, target_position: GridPosition = GridPosition(5, 0, 0)):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = target_position
        session.state.actors['monster-mage-1'].position = GridPosition(12, 0, 0)
        session.state.actors['player-1'].spell_save_dc = caster_dc
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = target_save_bonus
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_the_single_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual(tuple(intent.parameters), ())

    def test_failed_save_applies_the_duel_penalty_against_other_targets_but_not_the_source(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        target = session.state.actors['monster-skeleton-1']
        source = session.state.actors['player-1']
        other = session.state.actors['monster-mage-1']
        modifiers_vs_other = session.command_interface.kernel._attack_modifier_state(session.state, target, other, distance_ft=5, long_range_disadvantage=False)
        modifiers_vs_source = session.command_interface.kernel._attack_modifier_state(session.state, target, source, distance_ft=5, long_range_disadvantage=False)
        self.assertTrue(modifiers_vs_other['disadvantage'])
        self.assertFalse(modifiers_vs_source['disadvantage'])
        self.assertTrue(any(effect.name == 'Compelled Duel' and 'monster-skeleton-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_successful_save_creates_no_active_effect(self) -> None:
        session = self._setup_session(caster_dc=1, target_save_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertFalse(any(effect.name == 'Compelled Duel' for effect in session.state.active_effects.values()))

    def test_the_target_cannot_willingly_move_more_than_thirty_feet_from_the_caster(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, '/move monster-skeleton-1 40 0')

    def test_the_effect_persists_through_the_targets_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        self.assertTrue(any(effect.name == 'Compelled Duel' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()

