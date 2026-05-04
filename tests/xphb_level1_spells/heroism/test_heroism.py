
from __future__ import annotations

import unittest
from pathlib import Path

from shared_types.conditions import ConditionType
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class HeroismLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Heroism'
    SPELL_SLUG = 'heroism'
    COMMAND = '/cast player-1 heroism player-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].temp_hit_points = 0
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_the_active_effect_and_spends_the_action(self) -> None:
        session = self._setup_session()
        self.assertTrue(session.state.actors['player-1'].action_available)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertFalse(session.state.actors['player-1'].action_available)
        self.assertTrue(any(effect.name == 'Heroism' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_effect_grants_frightened_immunity(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        actor = session.state.actors['player-1']
        self.assertIn(ConditionType.FRIGHTENED, actor.condition_immunities)
        self.assertIn(ConditionType.FRIGHTENED, actor.granted_condition_immunities)

    def test_start_of_turn_temp_hp_matches_the_spellcasting_modifier(self) -> None:
        session = self._setup_session()
        caster = session.state.actors['player-1']
        expected = caster.ability_modifiers[caster.spellcasting_ability] if caster.spellcasting_ability is not None else 0
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertEqual(session.state.actors['player-1'].temp_hit_points, expected)

    def test_effect_survives_one_full_round_and_remains_active(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Heroism' for effect in session.state.active_effects.values()))
        self.assertGreaterEqual(session.state.clock_seconds, 0)


if __name__ == '__main__':
    unittest.main()
