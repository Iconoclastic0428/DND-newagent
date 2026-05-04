from __future__ import annotations

import unittest

from shared_types.encounter_events import DetectionPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class AlarmLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Alarm'
    SPELL_SLUG = 'alarm'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(10, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(12, 0, 0)
        return session

    def _payloads(self, session):
        return [event for event in session.state.event_log if isinstance(event, DetectionPayloadProducedEvent)]

    def _transition(self, session, *, actor_id: str, from_position: GridPosition, to_position: GridPosition):
        events = session.command_interface.kernel._persistent_area_transition_events(
            session.state,
            actor_id=actor_id,
            from_position=from_position,
            to_position=to_position,
        )
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)
        return events

    def test_command_shape_supports_point_mode_form_and_exclude_parameters(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 alarm 2 3 --mode mental --form cube --exclude monster-mage-1')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 3))
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {'mode': 'mental', 'form': 'cube', 'exclude': 'monster-mage-1'})

    def test_cast_creates_alarm_effect_and_persistent_area(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'mental', 'form': 'cube'})
        self.assertTrue(any(effect.name == 'Alarm' for effect in session.state.active_effects.values()))
        self.assertTrue(any(area.definition.name == 'Alarm' for area in session.state.persistent_areas.values()))
        payload = self._payloads(session)[-1]
        self.assertIn('mental alerting', payload.payload.definition.detail)

    def test_door_form_uses_single_cell_coverage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'audible', 'form': 'door'})
        area = next(iter(session.state.persistent_areas.values()))
        self.assertEqual(area.definition.area_size_ft, 5)
        self.assertIn('alarm-form:door', area.definition.semantic_tags)

    def test_excluded_actor_does_not_trigger_the_alarm(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'mental', 'form': 'cube', 'exclude': 'monster-mage-1'})
        start_count = len(self._payloads(session))
        self._transition(session, actor_id='monster-mage-1', from_position=GridPosition(12, 0, 0), to_position=GridPosition(2, 0, 0))
        self.assertEqual(len(self._payloads(session)), start_count)

    def test_non_excluded_intruder_triggers_a_mental_alarm_for_the_caster(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'mental', 'form': 'cube'})
        self._transition(session, actor_id='monster-skeleton-1', from_position=GridPosition(10, 0, 0), to_position=GridPosition(2, 0, 0))
        payload = self._payloads(session)[-1].payload
        self.assertEqual(payload.persistent.observer_actor_ids, ('player-1',))
        self.assertIn('Skeleton', payload.definition.detail)
        self.assertIn('mental', payload.definition.tags)

    def test_audible_alarm_notifies_all_observers_within_sixty_feet(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'audible', 'form': 'cube'})
        self._transition(session, actor_id='monster-skeleton-1', from_position=GridPosition(10, 0, 0), to_position=GridPosition(2, 0, 0))
        payload = self._payloads(session)[-1].payload
        self.assertIn('player-1', payload.persistent.observer_actor_ids)
        self.assertIn('monster-mage-1', payload.persistent.observer_actor_ids)
        self.assertIn('monster-skeleton-1', payload.persistent.observer_actor_ids)
        self.assertIn('audible', payload.definition.tags)


if __name__ == '__main__':
    unittest.main()

