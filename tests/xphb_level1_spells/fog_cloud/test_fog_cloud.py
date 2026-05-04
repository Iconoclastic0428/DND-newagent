from __future__ import annotations

import unittest

from encounter_runtime.visibility import assess_visibility
from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, PersistentAreaCreatedEvent, PersistentAreaEndedEvent
from shared_types.encounter_models import GridPosition
from shared_types.visibility import ObserverVisibilityState
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class FogCloudLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Fog Cloud'
    SPELL_SLUG = 'fog-cloud'
    COMMAND = '/cast player-1 fog-cloud 2 0'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(10, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _active_effect(self, session):
        return next((effect for effect in session.state.active_effects.values() if effect.name == 'Fog Cloud'), None)

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 0))

    def test_cast_creates_the_active_effect_and_persistent_area(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertIsNotNone(self._active_effect(session))
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Fog Cloud' for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, PersistentAreaCreatedEvent) and event.area.definition.name == 'Fog Cloud' for event in session.state.event_log))

    def test_creatures_inside_the_cloud_are_unseen(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        observer = session.state.actors['player-1']
        target = session.state.actors['monster-skeleton-1']
        assessment = assess_visibility(session.state, observer, target)
        self.assertEqual(assessment.visibility_state, ObserverVisibilityState.UNSEEN)

    def test_creatures_outside_the_cloud_remain_visible(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        observer = session.state.actors['player-1']
        target = session.state.actors['monster-mage-1']
        assessment = assess_visibility(session.state, observer, target)
        self.assertEqual(assessment.visibility_state, ObserverVisibilityState.VISIBLE)

    def test_effect_persists_across_the_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertIsNotNone(self._active_effect(session))
        self.assertTrue(session.state.actors['player-1'].bonus_action_available)

    def test_ending_the_active_effect_removes_the_persistent_area(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        effect = self._active_effect(session)
        assert effect is not None
        for event in session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end'):
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertIsNone(self._active_effect(session))
        self.assertFalse(session.state.persistent_areas)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'test-end' for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, PersistentAreaEndedEvent) for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
