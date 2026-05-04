from __future__ import annotations

from dataclasses import replace
import unittest

from encounter_runtime.visibility import target_light_level
from shared_types.errors import EncounterValidationError
from shared_types.visibility import LightLevel, LightingLevel
from tests.xphb_cantrips.support import EncounterCantripTestCase


class ProduceFlameCantripTests(EncounterCantripTestCase):
    def test_cast_creates_a_light_source_on_the_caster(self) -> None:
        session = self.build_goblin_session()
        self.grant_spell(session, 'Produce Flame')
        player = session.state.actors['player-1']
        tile = session.state.battlefield.tiles[player.position.horizontal()]
        session.state.battlefield.tiles[player.position.horizontal()] = replace(tile, lighting=LightingLevel.DARKNESS)
        self.assertEqual(target_light_level(session.state, player), LightLevel.DARKNESS)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 produce-flame')
        self.assertEqual(target_light_level(session.state, player), LightLevel.BRIGHT)
        self.assertTrue(any(effect.name == 'Produce Flame' for effect in session.state.active_effects.values()))

    def test_throw_requires_an_existing_flame(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Produce Flame')
        self.advance_to_actor(session, 'player-1')
        with self.assertRaisesRegex(EncounterValidationError, 'already be active'):
            session.command_interface.execute(session.state, '/cast player-1 produce-flame monster-skeleton-1 --mode throw')

    def test_throw_damages_the_target_and_consumes_the_effect(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Produce Flame')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 produce-flame')
        session.state.actors['player-1'].spell_attack_bonus = 99
        self.advance_to_actor(session, 'player-1')
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 produce-flame monster-skeleton-1 --mode throw')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertFalse(any(effect.name == 'Produce Flame' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
