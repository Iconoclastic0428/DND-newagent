from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectEndedEvent, DivinationPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class CreateOrDestroyWaterLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Create or Destroy Water'
    SPELL_SLUG = 'create-or-destroy-water'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self.grant_spell(session, 'Fog Cloud')
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        return session

    def _details(self, session) -> str:
        payload = next(event for event in session.state.event_log if isinstance(event, DivinationPayloadProducedEvent))
        return payload.payload.definition.detail

    def test_command_shape_supports_mode_and_container_parameters(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 create-or-destroy-water 2 0 --mode create --container bucket')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 0))
        self.assertEqual({param.key: param.value for param in intent.parameters}, {'mode': 'create', 'container': 'bucket'})

    def test_create_mode_with_container_reports_ten_gallons_in_the_container(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'create', 'container': 'bucket'})
        detail = self._details(session)
        self.assertIn('create up to 10 gallons of clean water', detail)
        self.assertIn('bucket', detail)
        self.assertFalse(session.state.active_effects)

    def test_destroy_mode_with_container_reports_water_removed(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'destroy', 'container': 'barrel'})
        detail = self._details(session)
        self.assertIn('destroy up to 10 gallons of water', detail)
        self.assertIn('barrel', detail)

    def test_create_mode_at_a_point_reports_rain_in_a_thirty_foot_cube(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'create'})
        detail = self._details(session)
        self.assertIn('30-foot cube', detail)
        self.assertIn('Exposed flames', detail)
        self.assertFalse(session.state.active_effects)

    def test_destroy_mode_clears_overlapping_fog_cloud(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id='fog-cloud', point=GridPosition(2, 0, 0))
        self.assertTrue(any(effect.name == 'Fog Cloud' for effect in session.state.active_effects.values()))
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'destroy'})
        self.assertFalse(any(effect.name == 'Fog Cloud' for effect in session.state.active_effects.values()))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'create-or-destroy-water-destroy' for event in session.state.event_log))

    def test_invalid_mode_is_rejected(self) -> None:
        session = self._setup_session()
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 0, 0), parameters={'mode': 'flood'})


if __name__ == '__main__':
    unittest.main()
