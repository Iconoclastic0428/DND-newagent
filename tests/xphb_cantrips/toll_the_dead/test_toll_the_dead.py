from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageRolledEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_cantrips.support import EncounterCantripTestCase


class TollTheDeadCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Toll the Dead')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 99
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.WIS] = -50
        return session

    def _last_damage_roll(self, session) -> DamageRolledEvent:
        damage_events = [event for event in session.state.event_log if isinstance(event, DamageRolledEvent)]
        self.assertTrue(damage_events)
        return damage_events[-1]

    def _find_counter_for_wounded_branch(self) -> int:
        for counter in range(120):
            healthy = self.build_default_session()
            self.grant_spell(healthy, 'Toll the Dead')
            self.advance_to_actor(healthy, 'player-1')
            healthy.state.random_counter = counter
            healthy.state.actors['player-1'].spell_save_dc = 99
            healthy_target = healthy.state.actors['monster-skeleton-1']
            healthy_target.position = healthy.state.actors['player-1'].position
            healthy_target.saving_throw_bonuses[Ability.WIS] = -50
            healthy.state, _ = healthy.command_interface.execute(healthy.state, '/cast player-1 toll-the-dead monster-skeleton-1')
            healthy_total = self._last_damage_roll(healthy).damage_total

            wounded = self.build_default_session()
            self.grant_spell(wounded, 'Toll the Dead')
            self.advance_to_actor(wounded, 'player-1')
            wounded.state.random_counter = counter
            wounded.state.actors['player-1'].spell_save_dc = 99
            wounded_target = wounded.state.actors['monster-skeleton-1']
            wounded_target.position = wounded.state.actors['player-1'].position
            wounded_target.current_hit_points = max(1, wounded_target.max_hit_points - 1)
            wounded_target.saving_throw_bonuses[Ability.WIS] = -50
            wounded.state, _ = wounded.command_interface.execute(wounded.state, '/cast player-1 toll-the-dead monster-skeleton-1')
            wounded_total = self._last_damage_roll(wounded).damage_total

            if wounded_total > healthy_total:
                return counter
        raise AssertionError('Could not find a counter showing the wounded branch dealing more damage.')

    def test_healthy_target_takes_necrotic_damage(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 toll-the-dead monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertEqual(self._last_damage_roll(session).damage_type, 'necrotic')

    def test_wounded_target_uses_the_larger_damage_branch(self) -> None:
        counter = self._find_counter_for_wounded_branch()

        healthy = self.build_default_session()
        self.grant_spell(healthy, 'Toll the Dead')
        self.advance_to_actor(healthy, 'player-1')
        healthy.state.random_counter = counter
        healthy.state.actors['player-1'].spell_save_dc = 99
        healthy_target = healthy.state.actors['monster-skeleton-1']
        healthy_target.position = healthy.state.actors['player-1'].position
        healthy_target.saving_throw_bonuses[Ability.WIS] = -50
        healthy.state, _ = healthy.command_interface.execute(healthy.state, '/cast player-1 toll-the-dead monster-skeleton-1')
        healthy_total = self._last_damage_roll(healthy).damage_total

        wounded = self.build_default_session()
        self.grant_spell(wounded, 'Toll the Dead')
        self.advance_to_actor(wounded, 'player-1')
        wounded.state.random_counter = counter
        wounded.state.actors['player-1'].spell_save_dc = 99
        wounded_target = wounded.state.actors['monster-skeleton-1']
        wounded_target.position = wounded.state.actors['player-1'].position
        wounded_target.current_hit_points = max(1, wounded_target.max_hit_points - 1)
        wounded_target.saving_throw_bonuses[Ability.WIS] = -50
        wounded.state, _ = wounded.command_interface.execute(wounded.state, '/cast player-1 toll-the-dead monster-skeleton-1')
        wounded_total = self._last_damage_roll(wounded).damage_total

        self.assertGreater(wounded_total, healthy_total)

    def test_successful_save_negates_damage(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Toll the Dead')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].spell_save_dc = 1
        target = session.state.actors['monster-skeleton-1']
        target.position = session.state.actors['player-1'].position
        target.saving_throw_bonuses[Ability.WIS] = 99
        start_hp = target.current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 toll-the-dead monster-skeleton-1')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)


if __name__ == '__main__':
    unittest.main()
