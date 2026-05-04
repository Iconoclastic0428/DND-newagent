from __future__ import annotations

import unittest

from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class MageArmorLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Mage Armor'
    SPELL_SLUG = 'mage-armor'
    COMMAND = '/cast player-1 mage-armor player-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _armor_item_id(self, session) -> str:
        for item in session.command_interface.kernel.item_catalog.values():
            if 'armor' in item.name.casefold() and item.record_id != self.SPELL_SLUG:
                return item.record_id
        raise AssertionError('Could not locate an armor item in the local catalog.')

    def test_command_shape_uses_the_supported_self_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_the_active_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(effect.name == 'Mage Armor' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_effect_sets_the_expected_armor_class_base(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        dex_bonus = player.ability_modifiers.get(Ability.DEX, 0)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertEqual(session.state.actors['player-1'].effective_armor_class, 13 + dex_bonus)

    def test_cast_can_resolve_once_the_target_is_without_worn_armor_and_material_is_not_required(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].equipped_armor_item_id = None
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(effect.name == 'Mage Armor' for effect in session.state.active_effects.values()))

    def test_effect_ends_when_armor_is_equipped_later(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        player = session.state.actors['player-1']
        player.equipped_armor_item_id = self._armor_item_id(session)
        events = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id='player-1')
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertFalse(any(effect.name == 'Mage Armor' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
