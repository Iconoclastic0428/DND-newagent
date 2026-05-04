from __future__ import annotations

from dataclasses import replace
import unittest

from session_server.bootstrap import build_goblin_ambush_encounter_session
from encounter_runtime.visibility import target_light_level
from shared_types.visibility import LightLevel, LightingLevel
from shared_types.errors import EncounterValidationError
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class LightCantripTests(unittest.TestCase):
    def _build_session(self):
        return build_goblin_ambush_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def test_light_brightens_a_dark_space(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        tile = session.state.battlefield.tiles[player.position.horizontal()]
        session.state.battlefield.tiles[player.position.horizontal()] = replace(tile, lighting=LightingLevel.DARKNESS)
        self.assertEqual(target_light_level(session.state, player), LightLevel.DARKNESS)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 light {player.position.x} {player.position.y}')
        self.assertEqual(target_light_level(session.state, player), LightLevel.BRIGHT)

    def test_light_recast_replaces_the_previous_light_from_same_caster(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 light {player.position.x} {player.position.y}')
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Light'), 1)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 light {player.position.x + 1} {player.position.y}')
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Light'), 1)
        self.assertEqual(len(session.state.persistent_areas), 1)
        area = next(iter(session.state.persistent_areas.values()))
        self.assertEqual(area.origin.x, player.position.x + 1)

    def test_light_requires_a_point_target(self) -> None:
        session = self._build_session()
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, '/cast player-1 light')


if __name__ == '__main__':
    unittest.main()
