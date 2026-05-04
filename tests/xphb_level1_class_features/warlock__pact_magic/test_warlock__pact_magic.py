from __future__ import annotations

import unittest

from shared_types.models import Ability
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class WarlockPactMagicFeatureTests(Level1ClassFeatureTestCase):
    def _record(self):
        return self.complete_record('warlock', assign_command='/create ability assign 10 14 13 12 8 15', overrides={'class:warlock:feature:eldritch-invocation-options': ('armor-of-shadows',)})

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Pact Magic', record.class_feature_names)

    def test_compiled_actor_has_level_one_pact_slots(self) -> None:
        actor = self.compile_actor(self._record())
        self.assertIn('spell-slot-1', actor.resource_pools)
        self.assertEqual(actor.resource_pools['spell-slot-1'].current, 1)
        self.assertEqual(actor.resource_pools['spell-slot-1'].maximum, 1)

    def test_compiled_actor_has_charisma_spellcasting_and_spells(self) -> None:
        actor = self.compile_actor(self._record())
        self.assertEqual(actor.spellcasting_ability, Ability.CHA)
        self.assertTrue(actor.spells)


if __name__ == '__main__':
    unittest.main()
