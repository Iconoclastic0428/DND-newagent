from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from tests.xphb_cantrips.support import EncounterCantripTestCase


class MageHandCantripTests(EncounterCantripTestCase):
    def _build_door_session(self):
        session = self.build_default_session()
        session.state.battlefield = self.build_door_battlefield()
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 0, 0)
        self.attach_door_object(session)
        self.grant_spell(session, 'Mage Hand')
        return session

    def test_cast_creates_a_mage_hand_at_the_target_point(self) -> None:
        session = self._build_door_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mage-hand 1 0')
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Mage Hand'), 1)
        created = next(iter(session.state.created_objects.values()))
        self.assertEqual(created.cells[0], GridPosition(1, 0, 0))

    def test_move_repositions_the_existing_hand(self) -> None:
        session = self._build_door_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mage-hand 1 0')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mage-hand 2 0 --mode move')
        created = next(iter(session.state.created_objects.values()))
        self.assertEqual(created.cells[0], GridPosition(2, 0, 0))
        effect = next(iter(session.state.active_effects.values()))
        self.assertEqual(effect.origin_point, GridPosition(2, 0, 0))

    def test_command_mode_can_open_a_nearby_door_from_the_hand_position(self) -> None:
        session = self._build_door_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mage-hand 1 0')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 mage-hand --mode command --object door-1 --action open')
        self.assertTrue(session.state.environment_objects['door-1'].open_state)


if __name__ == '__main__':
    unittest.main()
