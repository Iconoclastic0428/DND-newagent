from __future__ import annotations

import unittest

from shared_types.encounter_events import SpellCastEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


class MistyStepLevel2SpellTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Misty Step'
    SPELL_SLUG = 'misty-step'
    COMMAND = '/cast player-1 misty-step 2 2'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(8, 8, 0)
        return session

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_point, GridPosition(2, 2, 0))

    def test_capability_definition_is_exact(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(capability.action_cost, 'bonus-action')
        self.assertEqual(capability.targeting.range_ft, 30)
        self.assertTrue(capability.targeting.requires_unoccupied_point)
        self.assertTrue(capability.targeting.point_must_be_visible)
        self.assertIsNotNone(capability.effect)

    def test_cast_teleports_to_requested_point(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(2, 2, 0))
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))

    def test_cast_uses_the_bonus_action_and_leaves_action_available(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(session.state.actors['player-1'].action_available)

    def test_cast_rejects_a_blocked_destination(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-mage-1'].position = GridPosition(2, 2, 0)
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, self.COMMAND)

if __name__ == '__main__':
    unittest.main()
