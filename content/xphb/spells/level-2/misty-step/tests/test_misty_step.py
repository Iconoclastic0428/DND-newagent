from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.encounter_events import SpellCastEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'misty-step'


class MistyStepTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Misty Step'
    SPELL_SLUG = 'misty-step'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(8, 8, 0)
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_definition_matches_the_local_text(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'bonus-action')
        self.assertEqual(capability.targeting.range_ft, 30)
        self.assertTrue(capability.targeting.requires_unoccupied_point)
        self.assertTrue(capability.targeting.point_must_be_visible)

    def test_cast_teleports_to_the_requested_point(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 misty-step 2 2')
        self.assertEqual(session.state.actors['player-1'].position, GridPosition(2, 2, 0))

    def test_cast_spends_the_bonus_action(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 misty-step 2 2')
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(session.state.actors['player-1'].action_available)

    def test_cast_records_a_spell_cast_event(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 misty-step 2 2')
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))

    def test_occupied_or_out_of_range_destinations_are_rejected(self) -> None:
        blocked = self._setup_session()
        blocked.state.actors['monster-mage-1'].position = GridPosition(2, 2, 0)
        with self.assertRaises(EncounterValidationError):
            blocked.command_interface.execute(blocked.state, '/cast player-1 misty-step 2 2')
        far = self._setup_session()
        with self.assertRaises(EncounterValidationError):
            far.command_interface.execute(far.state, '/cast player-1 misty-step 12 12')


if __name__ == '__main__':
    unittest.main()
