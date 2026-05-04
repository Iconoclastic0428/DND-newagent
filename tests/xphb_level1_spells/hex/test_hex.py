from __future__ import annotations

import unittest

from encounter_runtime.conditions import get_ability_check_modifiers_or_auto_fail
from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class HexLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Hex'
    SPELL_SLUG = 'hex'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        return session

    def _attack(self, session, *, target_id: str):
        self.advance_to_actor(session, 'player-1')
        attack_id = 'dagger-thrown-dex' if 'dagger-thrown-dex' in session.state.actors['player-1'].attacks else next(attack_id for attack_id in session.state.actors['player-1'].attacks if attack_id != 'unarmed-strike')
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} {target_id}')
        return list(session.state.event_log)

    def _damage_types(self, events):
        return [event.damage_type for event in events if isinstance(event, DamageAppliedEvent)]

    def test_command_shape_supports_ability_parameter(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 hex monster-skeleton-1 --ability strength')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual({param.key: param.value for param in intent.parameters}, {'ability': 'strength'})

    def test_cast_creates_concentration_mark_on_source_with_metadata(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Hex')
        self.assertEqual(effect.target_actor_ids, ('player-1',))
        self.assertTrue(effect.definition.concentration)
        self.assertEqual(dict(effect.metadata)['marked-target-id'], 'monster-skeleton-1')
        self.assertEqual(dict(effect.metadata)['marked-ability'], 'STR')

    def test_cast_applies_disadvantage_on_chosen_ability_checks(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        target = session.state.actors['monster-skeleton-1']
        self.assertIn(Ability.STR, target.ability_check_disadvantage_abilities)

    def test_weapon_attack_against_marked_target_adds_necrotic_damage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.random_counter = self.find_attack_counter(session, actor_id='player-1')
        events = self._attack(session, target_id='monster-skeleton-1')
        self.assertIn('necrotic', self._damage_types(events))

    def test_weapon_attack_against_other_target_does_not_add_necrotic_damage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        session.state.actors['monster-mage-1'].armor_class = 1
        session.state.random_counter = self.find_attack_counter(session, actor_id='player-1')
        events = self._attack(session, target_id='monster-mage-1')
        self.assertNotIn('necrotic', self._damage_types(events))

    def test_transfer_requires_current_target_to_be_at_zero_hp(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1', parameters={'mode': 'transfer'})

    def test_transfer_after_zero_hp_keeps_original_ability_choice(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1', parameters={'ability': 'strength'})
        session.state.actors['monster-skeleton-1'].current_hit_points = 0
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1', parameters={'mode': 'transfer'})
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Hex')
        self.assertEqual(dict(effect.metadata)['marked-target-id'], 'monster-mage-1')
        self.assertEqual(dict(effect.metadata)['marked-ability'], 'STR')


if __name__ == '__main__':
    unittest.main()
