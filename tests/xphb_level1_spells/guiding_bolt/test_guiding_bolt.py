from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectEndedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class GuidingBoltSpellTests(EncounterLevel1SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Guiding Bolt')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-mage-1']
        player.position = GridPosition(0, 0, 0)
        target.position = GridPosition(1, 0, 0)
        self.advance_to_actor(session, 'player-1')
        return session

    def test_hit_deals_damage_and_applies_next_attack_advantage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-mage-1'].armor_class = 0
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 guiding-bolt monster-mage-1')
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, start_hp)
        self.assertTrue(any(effect.name == 'Guiding Bolt' and 'monster-mage-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_miss_does_not_apply_the_rider(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -50
        session.state.actors['monster-mage-1'].armor_class = 99
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 guiding-bolt monster-mage-1')
        self.assertEqual(session.state.actors['monster-mage-1'].current_hit_points, start_hp)
        self.assertFalse(any(effect.name == 'Guiding Bolt' and 'monster-mage-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_next_attack_consumes_the_advantage_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-mage-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 guiding-bolt monster-mage-1')
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        player = session.state.actors['player-1']
        target = session.state.actors['monster-mage-1']
        modifiers = session.command_interface.kernel._attack_modifier_state(session.state, player, target, distance_ft=5, long_range_disadvantage=False)
        self.assertTrue(modifiers['advantage'])
        session.state, _ = session.command_interface.execute(session.state, '/attack player-1 unarmed-strike monster-mage-1')
        self.assertFalse(any(effect.name == 'Guiding Bolt' and 'monster-mage-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'incoming-attack-roll-consumed' for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
