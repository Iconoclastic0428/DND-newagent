from __future__ import annotations

import unittest

from shared_types.encounter_events import DetectionPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class DetectEvilAndGoodLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Detect Evil and Good'
    SPELL_SLUG = 'detect-evil-and-good'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        return session

    def _payload(self, session):
        return [event for event in session.state.event_log if isinstance(event, DetectionPayloadProducedEvent)][-1].payload

    def test_cast_reports_nothing_when_no_supported_creature_types_are_present(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        session.state.actors['monster-mage-1'].creature_type = 'beast'
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('Nothing relevant is detected in range.', self._payload(session).definition.detail)

    def test_undead_creatures_are_detected(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'undead'
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('Skeleton', self._payload(session).definition.detail)
        self.assertIn('undead', self._payload(session).definition.detail.casefold())

    def test_multiple_supported_creature_types_are_reported(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'undead'
        session.state.actors['monster-mage-1'].creature_type = 'fiend'
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        detail = self._payload(session).definition.detail.casefold()
        self.assertIn('undead', detail)
        self.assertIn('fiend', detail)

    def test_humanoids_are_ignored(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertNotIn('humanoid', self._payload(session).definition.detail.casefold())

    def test_inspect_mode_requires_the_spell_to_be_active_first(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(Exception, 'must already be active'):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, parameters={'mode': 'inspect'})

    def test_detection_payload_is_private_to_the_caster(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].creature_type = 'undead'
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertEqual(self._payload(session).persistent.observer_actor_ids, ('player-1',))


if __name__ == '__main__':
    unittest.main()
