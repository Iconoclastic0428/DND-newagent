from __future__ import annotations

import unittest

from shared_types.models import SpellSelectionKind
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class RangerFavoredEnemyFeatureTests(Level1ClassFeatureTestCase):
    def test_feature_name_is_recorded(self) -> None:
        record = self.complete_record('ranger')
        self.assertIn('Favored Enemy', record.class_feature_names)

    def test_hunters_mark_is_added_as_an_always_prepared_class_spell(self) -> None:
        record = self.complete_record('ranger')
        hunter_mark = [selection for selection in record.spell_selections if selection.spell_name == "Hunter's Mark" and selection.source.source_kind.value == 'class']
        self.assertTrue(hunter_mark)
        self.assertTrue(any(selection.selection_kind == SpellSelectionKind.ALWAYS_PREPARED for selection in hunter_mark))

    def test_compiled_actor_has_the_free_hunters_mark_pool(self) -> None:
        actor = self.compile_actor(self.complete_record('ranger'))
        self.assertIn('favored-enemy-hunters-mark', actor.resource_pools)
        self.assertEqual(actor.resource_pools['favored-enemy-hunters-mark'].current, 2)


if __name__ == '__main__':
    unittest.main()
