from __future__ import annotations

import unittest

from shared_types.encounter_events import ConsumablesPurifiedEvent, DivinationPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import ItemRecord
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class PurifyFoodAndDrinkLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Purify Food and Drink'
    SPELL_SLUG = 'purify-food-and-drink'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(8, 0, 0)
        return session

    def _add_item(self, session, *, item_id: str, name: str, tags: tuple[str, ...], is_magical: bool = False, actor_id: str = 'player-1', quantity: int = 1):
        session.command_interface.kernel.item_catalog[item_id] = ItemRecord(
            record_id=item_id,
            name=name,
            source='TEST',
            edition='2024',
            official=False,
            homebrew=True,
            cost_cp=0,
            is_magical=is_magical,
            tags=tags,
        )
        session.state.actors[actor_id].carried_item_counts[item_id] = quantity

    def _detail(self, session) -> str:
        event = next(event for event in session.state.event_log if isinstance(event, DivinationPayloadProducedEvent))
        return event.payload.definition.detail

    def test_command_shape_targets_a_point(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 purify-food-and-drink 2 0')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 0))

    def test_poisoned_food_is_replaced_with_a_purified_copy(self) -> None:
        session = self._setup_session()
        self._add_item(session, item_id='spoiled-rations', name='Spoiled Rations', tags=('food', 'poison'))
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(0, 0, 0))
        actor = session.state.actors['player-1']
        self.assertNotIn('spoiled-rations', actor.carried_item_counts)
        self.assertIn('purified-spoiled-rations', actor.carried_item_counts)
        self.assertNotIn('poison', {tag.casefold() for tag in session.command_interface.kernel.item_catalog['purified-spoiled-rations'].tags})

    def test_poisoned_drink_on_a_nearby_creature_is_purified(self) -> None:
        session = self._setup_session()
        self._add_item(session, item_id='tainted-wine', name='Tainted Wine', tags=('drink', 'poisoned'), actor_id='monster-mage-1')
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(0, 0, 0))
        actor = session.state.actors['monster-mage-1']
        self.assertIn('purified-tainted-wine', actor.carried_item_counts)
        self.assertTrue(any(isinstance(event, ConsumablesPurifiedEvent) and event.actor_id == 'monster-mage-1' for event in session.state.event_log))

    def test_magical_food_is_not_purified(self) -> None:
        session = self._setup_session()
        self._add_item(session, item_id='enchanted-feast', name='Enchanted Feast', tags=('food', 'poison'), is_magical=True)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(0, 0, 0))
        actor = session.state.actors['player-1']
        self.assertIn('enchanted-feast', actor.carried_item_counts)
        self.assertNotIn('purified-enchanted-feast', actor.carried_item_counts)

    def test_clean_food_reports_that_nothing_needed_purification(self) -> None:
        session = self._setup_session()
        self._add_item(session, item_id='fresh-bread', name='Fresh Bread', tags=('food',))
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(0, 0, 0))
        self.assertIn('No nonmagical poisoned or rotten food or drink was found', self._detail(session))

    def test_out_of_range_items_are_left_untouched(self) -> None:
        session = self._setup_session()
        self._add_item(session, item_id='far-stew', name='Far Stew', tags=('food', 'poisoned'), actor_id='monster-skeleton-1')
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(0, 0, 0))
        actor = session.state.actors['monster-skeleton-1']
        self.assertIn('far-stew', actor.carried_item_counts)
        self.assertNotIn('purified-far-stew', actor.carried_item_counts)


if __name__ == '__main__':
    unittest.main()
