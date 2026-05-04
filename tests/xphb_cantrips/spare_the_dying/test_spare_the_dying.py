from __future__ import annotations

from dataclasses import replace
import unittest

from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import DyingStateStatus
from tests.xphb_cantrips.support import EncounterCantripTestCase


class SpareTheDyingCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Spare the Dying')
        self.advance_to_actor(session, 'player-1')
        return session

    def test_stabilizes_a_dying_creature(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-mage-1']
        target.current_hit_points = 0
        target.dying_state = replace(target.dying_state, status=DyingStateStatus.AT_0_HP_UNCONSCIOUS)
        target.position = session.state.actors['player-1'].position
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 spare-the-dying monster-mage-1')
        self.assertEqual(session.state.actors['monster-mage-1'].dying_state.status, DyingStateStatus.STABLE_AT_0_HP)

    def test_healthy_target_is_rejected(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].position = session.state.actors['player-1'].position
        with self.assertRaisesRegex(EncounterValidationError, 'cannot be stabilized'):
            session.command_interface.execute(session.state, '/cast player-1 spare-the-dying monster-mage-1')

    def test_dead_target_is_rejected(self) -> None:
        session = self._setup_session()
        target = session.state.actors['monster-mage-1']
        target.current_hit_points = 0
        target.dying_state = replace(target.dying_state, status=DyingStateStatus.DEAD)
        target.position = session.state.actors['player-1'].position
        with self.assertRaisesRegex(EncounterValidationError, 'already dead'):
            session.command_interface.execute(session.state, '/cast player-1 spare-the-dying monster-mage-1')


if __name__ == '__main__':
    unittest.main()
