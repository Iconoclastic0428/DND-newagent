from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class TrueStrikeCantripTests(EncounterCantripTestCase):
    def _non_one_counter(self, session) -> int:
        from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
        for counter in range(50):
            result = session.command_interface.kernel.d20_engine.resolve(
                D20TestRequest(request_id=f'probe:{counter}', test_type=D20TestType.ATTACK, actor_id='player-1', flat_modifier=0, roll_mode=D20RollMode.NORMAL, dc=10),
                random_counter=counter,
            )
            if result.result.selected_roll != 1:
                return counter
        raise AssertionError('Could not find a non-natural-1 counter in the search window.')

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'True Strike')
        session.state.actors['player-1'].character_record.weapon_proficiencies = ('simple weapons',)
        session.state.actors['monster-skeleton-1'].armor_class = 0
        return session

    def test_cast_can_strike_with_a_proficient_weapon_as_radiant(self) -> None:
        session = self._setup_session()
        session.state.random_counter = self._non_one_counter(session)
        self.advance_to_actor(session, 'player-1')
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant')
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        damage_events = [event for event in session.state.event_log if event.__class__.__name__ == 'DamageAppliedEvent']
        self.assertEqual(damage_events[-1].damage_type, 'radiant')

    def test_level_five_true_strike_adds_bonus_radiant_damage(self) -> None:
        session = self._setup_session()
        actor = session.state.actors['player-1']
        actor.level = 5
        session.state.random_counter = self._non_one_counter(session)
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 true-strike monster-skeleton-1 --item dagger --damage-type radiant')
        damage_events = [event for event in session.state.event_log if event.__class__.__name__ == 'DamageAppliedEvent']
        self.assertGreaterEqual(len(damage_events), 2)
        self.assertEqual(damage_events[-1].damage_type, 'radiant')

    def test_non_proficient_weapon_is_rejected(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'True Strike')
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/equip player-1 quarterstaff main-hand')
        with self.assertRaisesRegex(EncounterValidationError, 'not proficient'):
            session.command_interface.execute(session.state, '/cast player-1 true-strike monster-skeleton-1 --item quarterstaff --damage-type radiant')


if __name__ == '__main__':
    unittest.main()
