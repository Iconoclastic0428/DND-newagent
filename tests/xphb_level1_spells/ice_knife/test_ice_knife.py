from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class IceKnifeLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Ice Knife'
    SPELL_SLUG = 'ice-knife'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(3, 0, 0)
        return session

    def _damage_types(self, session, *, target_id: str):
        return [event.damage_type for event in session.state.event_log if isinstance(event, DamageAppliedEvent) and event.target_id == target_id]

    def test_command_shape_targets_a_creature(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 ice-knife monster-skeleton-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_hit_target_takes_piercing_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        session.state.random_counter = self.find_attack_counter(session)
        session.state.actors['monster-skeleton-1'].armor_class = 1
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertIn('piercing', self._damage_types(session, target_id='monster-skeleton-1'))
        self.assertNotIn('cold', self._damage_types(session, target_id='monster-skeleton-1'))

    def test_primary_target_can_take_cold_damage_from_burst(self) -> None:
        session = self._setup_session()
        session.state.random_counter = self.find_attack_counter(session)
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertIn('piercing', self._damage_types(session, target_id='monster-skeleton-1'))
        self.assertIn('cold', self._damage_types(session, target_id='monster-skeleton-1'))

    def test_nearby_creature_in_radius_makes_save_against_cold_burst(self) -> None:
        session = self._setup_session()
        session.state.random_counter = self.find_attack_counter(session)
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertIn('cold', self._damage_types(session, target_id='monster-mage-1'))

    def test_successful_save_avoids_cold_damage(self) -> None:
        session = self._setup_session()
        session.state.random_counter = self.find_attack_counter(session)
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = 99
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertNotIn('cold', self._damage_types(session, target_id='monster-mage-1'))

    def test_miss_still_triggers_burst(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = 99
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = -20
        session.state.random_counter = self.find_attack_counter(session, want_natural_one=True)
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertNotIn('piercing', self._damage_types(session, target_id='monster-skeleton-1'))
        self.assertIn('cold', self._damage_types(session, target_id='monster-mage-1'))


if __name__ == '__main__':
    unittest.main()
