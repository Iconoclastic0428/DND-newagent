
from __future__ import annotations

import unittest

from shared_types.encounter_events import ActiveEffectEndedEvent, TemporaryHitPointsAppliedEvent
from shared_types.encounter_models import AttackKind, GridPosition
from tests.xphb_cantrips.support import find_non_one_counter
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class ArmorOfAgathysLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Armor of Agathys'
    SPELL_SLUG = 'armor-of-agathys'
    COMMAND = '/cast player-1 armor-of-agathys'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(1, 1, 0)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _melee_attack_id(self, session, actor_id: str) -> str:
        actor = session.state.actors[actor_id]
        for attack_id, attack in actor.attacks.items():
            if attack.attack_kind == AttackKind.MELEE and attack_id != 'unarmed-strike':
                return attack_id
        return 'shortsword' if 'shortsword' in actor.attacks else next(iter(actor.attacks))

    def test_command_shape_requires_no_target(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertIsNone(intent.target_id)

    def test_cast_grants_five_temporary_hit_points(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertTrue(any(isinstance(event, TemporaryHitPointsAppliedEvent) for event in session.state.event_log))
        self.assertEqual(session.state.actors['player-1'].temp_hit_points, 5)

    def test_melee_hit_retaliates_with_cold_damage_while_temp_hp_remain(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        attacker = session.state.actors['monster-skeleton-1']
        attacker_start_hp = attacker.current_hit_points
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['player-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'monster-skeleton-1')
        session.state.random_counter = find_non_one_counter(session, actor_id='monster-skeleton-1')
        attack_id = self._melee_attack_id(session, 'monster-skeleton-1')
        session.state, _ = session.command_interface.execute(session.state, f'/attack monster-skeleton-1 {attack_id} player-1')
        if session.state.pending_reaction_window is not None:
            session.state, _ = session.command_interface.execute(session.state, '/react player-1 decline')
        self.assertLess(attacker.current_hit_points, attacker_start_hp)

    def test_effect_ends_once_temporary_hit_points_are_gone(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state.actors['player-1'].temp_hit_points = 0
        events = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id='player-1')
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'temp-hit-points-gone' for event in session.state.event_log))
        self.assertFalse(any(effect.name == 'Armor of Agathys' for effect in session.state.active_effects.values()))

    def test_retaliation_does_not_fire_once_the_temp_hp_buffer_is_gone(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state.actors['player-1'].temp_hit_points = 0
        events = session.command_interface.kernel._effect_reconciliation_events(session.state, actor_id='player-1')
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        attacker = session.state.actors['monster-mage-1']
        attacker_start_hp = attacker.current_hit_points
        session.state.actors['monster-mage-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'monster-mage-1')
        attack_id = self._melee_attack_id(session, 'monster-mage-1')
        session.state, _ = session.command_interface.execute(session.state, f'/attack monster-mage-1 {attack_id} player-1')
        if session.state.pending_reaction_window is not None:
            session.state, _ = session.command_interface.execute(session.state, '/react player-1 decline')
        self.assertEqual(attacker.current_hit_points, attacker_start_hp)


if __name__ == '__main__':
    unittest.main()
