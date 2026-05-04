from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from tests.xphb_cantrips.support import EncounterCantripTestCase


class FriendsCantripTests(EncounterCantripTestCase):
    def test_failed_save_charms_a_humanoid_and_creates_dm_note(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Friends')
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-mage-1'].position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 friends monster-mage-1')
        target = session.state.actors['monster-mage-1']
        self.assertIn(ConditionType.CHARMED, {instance.condition_type for instance in target.condition_instances})
        self.assertTrue(any(payload.definition.title == 'Friends' for payload in session.state.informational_payloads.values()))

    def test_non_humanoid_target_auto_succeeds_and_is_not_charmed(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Friends')
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-skeleton-1'].position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 friends monster-skeleton-1')
        target = session.state.actors['monster-skeleton-1']
        self.assertNotIn(ConditionType.CHARMED, {instance.condition_type for instance in target.condition_instances})
        self.assertFalse(any(effect.name == 'Friends' for effect in session.state.active_effects.values()))

    def test_recently_targeted_creature_auto_succeeds(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Friends')
        session.state.actors['player-1'].spell_save_dc = 99
        session.state.actors['monster-mage-1'].position = GridPosition(session.state.actors['player-1'].position.x + 1, session.state.actors['player-1'].position.y, session.state.actors['player-1'].position.z)
        session.state.actors['player-1'].friends_targeted_at_seconds['monster-mage-1'] = 0
        session.state.clock_seconds = 60
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 friends monster-mage-1')
        target = session.state.actors['monster-mage-1']
        self.assertNotIn(ConditionType.CHARMED, {instance.condition_type for instance in target.condition_instances})
        self.assertFalse(any(effect.name == 'Friends' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
