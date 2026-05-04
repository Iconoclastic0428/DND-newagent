from __future__ import annotations

import unittest

from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class WarlockEldritchInvocationOptionsFeatureTests(Level1ClassFeatureTestCase):
    CHOICE_ID = 'class:warlock:feature:eldritch-invocation-options'

    def test_armor_of_shadows_grants_mage_armor_to_the_compiled_actor(self) -> None:
        record = self.complete_record('warlock', assign_command='/create ability assign 10 14 13 12 8 15', overrides={self.CHOICE_ID: ('armor-of-shadows',)})
        actor = self.compile_actor(record)
        self.assertIn('mage-armor', actor.spells)

    def test_pact_of_the_tome_grants_bonus_cantrips_and_ritual_spells(self) -> None:
        record = self.complete_record(
            'warlock',
            assign_command='/create ability assign 10 14 13 12 8 15',
            overrides={
                self.CHOICE_ID: ('pact-of-the-tome',),
                'class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-cantrips': ('guidance', 'light', 'mending'),
                'class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-rituals': ('detect-magic', 'unseen-servant'),
            },
        )
        spell_names = {selection.spell_name for selection in record.spell_selections}
        self.assertIn('Guidance', spell_names)
        self.assertIn('Light', spell_names)
        self.assertIn('Mending', spell_names)
        self.assertIn('Detect Magic', spell_names)
        self.assertIn('Unseen Servant', spell_names)

    def test_choice_label_is_recorded(self) -> None:
        record = self.complete_record('warlock', assign_command='/create ability assign 10 14 13 12 8 15', overrides={self.CHOICE_ID: ('pact-of-the-tome',), 'class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-cantrips': ('guidance', 'light', 'mending'), 'class:warlock:feature:eldritch-invocation-options:pact-of-the-tome-rituals': ('detect-magic', 'unseen-servant')})
        self.assertEqual(self.choice_labels(record, self.CHOICE_ID), ('Pact of the Tome',))


if __name__ == '__main__':
    unittest.main()
