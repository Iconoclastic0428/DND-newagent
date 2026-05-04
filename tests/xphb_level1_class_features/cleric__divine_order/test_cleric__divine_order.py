from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class ClericDivineOrderFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:cleric:feature:divine-order'

    def test_protector_choice_is_recorded_in_traits_and_choices(self) -> None:
        record = self.complete_record('cleric', overrides={self.CHOICE_ID: ('protector',)})
        self.assertEqual(self.choice_ids(record, self.CHOICE_ID), ('protector',))
        self.assertIn('Divine Order: Protector', record.traits)

    def test_protector_grants_heavy_armor_and_martial_weapon_training(self) -> None:
        record = self.complete_record('cleric', overrides={self.CHOICE_ID: ('protector',)})
        self.assertIn('heavy', record.armor_training)
        self.assertIn('martial', record.weapon_proficiencies)

    def test_thaumaturge_adds_wisdom_modifier_to_arcana_and_religion(self) -> None:
        record = self.complete_record('cleric', assign_command='/create ability assign 10 12 13 8 15 14', overrides={self.CHOICE_ID: ('thaumaturge',)})
        actor = self.compile_actor(record)
        self.assertGreaterEqual(actor.skill_bonuses['Arcana'], record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'WIS')])
        self.assertGreaterEqual(actor.skill_bonuses['Religion'], record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'WIS')])


if __name__ == '__main__':
    unittest.main()
