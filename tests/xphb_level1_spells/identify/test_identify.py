from __future__ import annotations

import unittest
from dataclasses import replace

from session_server.web_projection import project_encounter_session_view
from shared_types.encounter_events import DivinationPayloadProducedEvent, ItemIdentifiedEvent
from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import grant_item_by_catalog_match
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class IdentifyLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Identify'
    SPELL_SLUG = 'identify'

    def _grant_pearl(self, session) -> str:
        return grant_item_by_catalog_match(session, actor_id='player-1', name_substrings=('pearl',), min_cost_cp=10000)

    def _grant_magic_item(self, session) -> str:
        return grant_item_by_catalog_match(session, actor_id='player-1', name_substrings=('potion of healing',), min_cost_cp=0)

    def _grant_magic_weapon(self, session) -> str:
        dagger = session.command_interface.kernel.item_catalog['dagger']
        record = replace(dagger, record_id='mystic-dagger', name='Mystic Dagger', source='TEST', official=False, is_magical=True)
        session.command_interface.kernel.item_catalog[record.record_id] = record
        session.state.actors['player-1'].carried_item_counts[record.record_id] = 1
        return record.record_id

    def _project_card(self, session, *, controller_id: str = 'player-1-controller', actor_id: str = 'player-1'):
        view = project_encounter_session_view(session, controller_id, session_id='identify-test')
        return next(card for card in view.character_cards if card.actor_id == actor_id)

    def _cast(self, session, *, item_name: str) -> None:
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 identify --item {item_name}')

    def _project_item(self, session, *, controller_id: str = 'player-1-controller', actor_id: str = 'player-1', item_id: str):
        view = project_encounter_session_view(session, controller_id, session_id='identify-test')
        card = next(card for card in view.character_cards if card.actor_id == actor_id)
        return next(item for item in card.items if item.item_id == item_id)

    def test_command_shape_uses_item_parameter(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 identify --item potion-of-healing')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual({param.key: param.value for param in intent.parameters}, {'item': 'potion-of-healing'})

    def test_cast_requires_the_pearl_material_component(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_magic_item(session)
        with self.assertRaises(EncounterValidationError):
            self._cast(session, item_name='potion-of-healing')

    def test_cast_requires_the_target_item_to_be_carried(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        with self.assertRaises(EncounterValidationError):
            self._cast(session, item_name='potion-of-healing')

    def test_successful_cast_marks_a_magical_item_as_identified(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        item_id = self._grant_magic_item(session)
        self._cast(session, item_name='potion-of-healing')
        self.assertIn(item_id, session.state.actors['player-1'].identified_item_ids)
        self.assertTrue(any(isinstance(event, ItemIdentifiedEvent) and event.item_id == item_id for event in session.state.event_log))

    def test_successful_cast_emits_divination_details_for_the_item(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        self._grant_magic_item(session)
        self._cast(session, item_name='potion-of-healing')
        payload_event = next(event for event in session.state.event_log if isinstance(event, DivinationPayloadProducedEvent))
        detail = payload_event.payload.definition.detail
        self.assertIn('Name: Potion of Healing', detail)
        self.assertIn('Magical: yes', detail)

    def test_nonmagical_item_can_be_inspected_without_identification_mark(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        item_id = grant_item_by_catalog_match(session, actor_id='player-1', name_substrings=('dagger',), min_cost_cp=0)
        self._cast(session, item_name='dagger')
        self.assertNotIn(item_id, session.state.actors['player-1'].identified_item_ids)
        payload_event = next(event for event in session.state.event_log if isinstance(event, DivinationPayloadProducedEvent))
        self.assertIn('Magical: no', payload_event.payload.definition.detail)

    def test_player_projection_masks_unidentified_magical_item_name_and_shows_passive_summary(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        item_id = self._grant_magic_weapon(session)
        session.state, _ = session.command_interface.execute(session.state, f'/equip player-1 {item_id} main-hand')
        item_view = self._project_item(session, item_id=item_id)
        self.assertNotEqual(item_view.label, 'Mystic Dagger')
        self.assertTrue(item_view.label.casefold().startswith('unidentified magical'))
        self.assertIsNotNone(item_view.state_label)
        self.assertIn('weapon', item_view.state_label.casefold())
        card = self._project_card(session)
        self.assertEqual(card.main_hand_label, 'Unidentified magical weapon')
        self.assertIn('Unidentified magical weapon', {attack.name for attack in card.attacks})

    def test_player_projection_reveals_the_item_name_after_identify(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self._grant_pearl(session)
        item_id = self._grant_magic_weapon(session)
        session.state, _ = session.command_interface.execute(session.state, f'/equip player-1 {item_id} main-hand')
        self._cast(session, item_name='mystic-dagger')
        item_view = self._project_item(session, item_id=item_id)
        self.assertEqual(item_view.label, 'Mystic Dagger')
        if item_view.state_label is not None:
            self.assertNotIn('unidentified magical', item_view.state_label.casefold())
        card = self._project_card(session)
        self.assertEqual(card.main_hand_label, 'Mystic Dagger')
        self.assertTrue(any(attack.name.startswith('Mystic Dagger') for attack in card.attacks))


if __name__ == '__main__':
    unittest.main()
