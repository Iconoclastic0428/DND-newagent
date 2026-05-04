from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class MonkMartialArtsFeatureTests(Level1ClassFeatureTestCase):
    def _record(self):
        return self.complete_record('monk', assign_command='/create ability assign 8 15 13 10 14 12')

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Martial Arts', record.class_feature_names)

    def test_unarmed_strike_uses_a_d6_damage_die(self) -> None:
        actor = self.compile_actor(self._record())
        self.assertEqual(actor.attacks['unarmed-strike'].damage_die_faces, 6)

    def test_unarmed_strike_uses_dexterity_for_attack_and_damage(self) -> None:
        record = self._record()
        actor = self.compile_actor(record)
        self.assertEqual(actor.attacks['unarmed-strike'].to_hit_bonus, record.proficiency_bonus + record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'DEX')])
        self.assertEqual(actor.attacks['unarmed-strike'].damage_bonus, record.ability_modifiers[next(ability for ability in record.ability_modifiers if ability.value == 'DEX')])


if __name__ == '__main__':
    unittest.main()
