
from __future__ import annotations

import unittest

from shared_types.encounter_models import AttackKind, GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class LongstriderLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Longstrider'
    SPELL_SLUG = 'longstrider'
    COMMAND = '/cast player-1 longstrider player-1'

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
        self.assertTrue(any(effect.name == 'Longstrider' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_effect_increases_the_targets_speed_bonus_by_ten(self) -> None:
        session = self._setup_session()
        actor = session.state.actors['player-1']
        base_speed = actor.max_path_speed_ft
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['player-1'].speed_bonus_ft, 10)
        self.assertEqual(session.state.actors['player-1'].max_path_speed_ft, base_speed + 10)

    def test_the_spell_can_target_another_creature(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-mage-1']
        target.position = GridPosition(1, 0, 0)
        base_speed = target.max_path_speed_ft
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 longstrider monster-mage-1')
        self.assertEqual(target.speed_bonus_ft, 10)
        self.assertEqual(target.max_path_speed_ft, base_speed + 10)

    def test_effect_persists_through_a_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Longstrider' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
