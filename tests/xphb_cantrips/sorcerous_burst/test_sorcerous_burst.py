from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class SorcerousBurstCantripTests(EncounterCantripTestCase):
    def _non_one_counter(self, session) -> int:
        request = session.command_interface.kernel.d20_engine.resolve
        from shared_types.d20 import D20RollMode, D20TestRequest, D20TestType
        for counter in range(50):
            result = request(D20TestRequest(request_id=f'probe:{counter}', test_type=D20TestType.ATTACK, actor_id='player-1', flat_modifier=0, roll_mode=D20RollMode.NORMAL, dc=10), random_counter=counter)
            if result.result.selected_roll != 1:
                return counter
        raise AssertionError('Could not find a non-natural-1 counter in the search window.')

    def test_invalid_damage_type_is_rejected(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Sorcerous Burst')
        self.advance_to_actor(session, 'player-1')
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, '/cast player-1 sorcerous-burst monster-skeleton-1 --damage-type wood')

    def test_recursive_damage_roll_can_explode_on_max_result(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Sorcerous Burst')
        actor = session.state.actors['player-1']
        extra_limit = max(0, actor.ability_modifiers[actor.spellcasting_ability])
        found = None
        for counter in range(250):
            session.state.random_counter = counter
            rolls, total = session.command_interface.kernel.effect_executor._recursive_damage_roll(session.state, die_faces=8, base_dice_count=1, extra_limit=extra_limit)
            if len(rolls) > 1:
                found = (rolls, total)
                break
        self.assertIsNotNone(found)
        rolls, total = found
        self.assertGreater(len(rolls), 1)
        self.assertEqual(total, sum(rolls))
        self.assertLessEqual(len(rolls), 1 + extra_limit)

    def test_cast_uses_the_chosen_damage_type(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Sorcerous Burst')
        session.state.actors['player-1'].spell_attack_bonus = 99
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.random_counter = self._non_one_counter(session)
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 sorcerous-burst monster-skeleton-1 --damage-type acid')
        damage_events = [event for event in session.state.event_log if event.__class__.__name__ == 'DamageAppliedEvent']
        self.assertTrue(damage_events)
        self.assertEqual(damage_events[-1].damage_type, 'acid')


if __name__ == '__main__':
    unittest.main()
