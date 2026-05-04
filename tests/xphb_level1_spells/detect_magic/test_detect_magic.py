from __future__ import annotations

from dataclasses import replace
import unittest

from shared_types.encounter_events import DetectionPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class DetectMagicLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Detect Magic'
    SPELL_SLUG = 'detect-magic'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].side = session.state.actors['player-1'].side
        session.state.actors['monster-skeleton-1'].position = GridPosition(4, 0, 0)
        return session

    def _payload(self, session):
        return [event for event in session.state.event_log if isinstance(event, DetectionPayloadProducedEvent)][-1].payload

    def test_cast_creates_the_active_detect_magic_effect(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertTrue(any(effect.name == 'Detect Magic' for effect in session.state.active_effects.values()))

    def test_cast_reports_nothing_when_no_magic_is_nearby(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('Nothing relevant is detected in range.', self._payload(session).definition.detail)

    def test_cast_reports_magical_presence_from_nearby_spell_effects(self) -> None:
        session = self._setup_session()
        self.grant_spell(session, 'Mage Armor')
        self.apply_spell_events(session, spell_id='mage-armor', target_id='monster-mage-1')
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('Magical presence detected near Mage.', self._payload(session).definition.detail)

    def test_inspect_mode_requires_the_detection_spell_to_be_active(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(Exception, 'must already be active'):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, parameters={'mode': 'inspect'})

    def test_inspect_mode_reveals_effect_names_on_visible_targets(self) -> None:
        session = self._setup_session()
        self.grant_spell(session, 'Mage Armor')
        self.apply_spell_events(session, spell_id='mage-armor', target_id='monster-mage-1')
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, parameters={'mode': 'inspect'})
        self.assertIn('effects: Mage Armor', self._payload(session).definition.detail)

    def test_inspect_mode_reveals_magical_items(self) -> None:
        session = self._setup_session()
        granted_item_id = next(iter(session.command_interface.kernel.item_catalog))
        item = session.command_interface.kernel.item_catalog[granted_item_id]
        session.command_interface.kernel.item_catalog[granted_item_id] = replace(item, is_magical=True)
        session.state.actors['monster-mage-1'].carried_item_counts[granted_item_id] = 1
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, parameters={'mode': 'inspect'})
        self.assertIn('items:', self._payload(session).definition.detail)

    def test_detection_payload_is_private_to_the_caster(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertEqual(self._payload(session).persistent.observer_actor_ids, ('player-1',))


if __name__ == '__main__':
    unittest.main()


