from __future__ import annotations

import unittest

from shared_types.encounter_events import RitualCastCompletedEvent, RitualCastStartedEvent, TimeAdvancedEvent
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class WizardRitualAdeptFeatureTests(Level1ClassFeatureTestCase):
    def _record(self):
        return self.complete_record('wizard', assign_command='/create ability assign 8 14 13 15 12 10', overrides={'class:wizard:spells': ('alarm', 'burning-hands', 'charm-person', 'detect-magic')})

    def test_feature_name_is_recorded(self) -> None:
        record = self._record()
        self.assertIn('Ritual Adept', record.class_feature_names)

    def test_detect_magic_compiles_as_a_ritual_capable_spell(self) -> None:
        actor = self.compile_actor(self._record())
        self.assertTrue(actor.spells['detect-magic'].can_cast_as_ritual)

    def test_ritual_casting_detect_magic_does_not_spend_a_spell_slot(self) -> None:
        session = self.build_session(self._record())
        slots_before = session.state.actors['player-1'].resource_pools['spell-slot-1'].current
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 detect-magic --ritual')
        self.assertEqual(session.state.actors['player-1'].resource_pools['spell-slot-1'].current, slots_before)
        self.assertTrue(any(isinstance(event, RitualCastStartedEvent) for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, RitualCastCompletedEvent) for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, TimeAdvancedEvent) for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
