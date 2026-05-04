from __future__ import annotations

import unittest

from shared_types.encounter_events import DamageAppliedEvent
from tests.xphb_cantrips.support import EncounterCantripTestCase


class ResistanceCantripTests(EncounterCantripTestCase):
    def _apply_damage(self, session, *, target_id: str, damage_total: int, damage_type: str, source_actor_id: str = 'monster-mage-1') -> int:
        target = session.state.actors[target_id]
        hp_after, temp_after, applied, effect_events = session.command_interface.kernel._damage_preview(session.state, target, damage_total, damage_type=damage_type)
        for event in effect_events:
            session.command_interface.kernel._apply_event(session.state, event)
        session.command_interface.kernel._apply_event(
            session.state,
            DamageAppliedEvent(
                source_actor_id=source_actor_id,
                target_id=target_id,
                damage_total=damage_total,
                applied_damage_total=applied,
                target_hit_points_after=hp_after,
                target_temp_hit_points_after=temp_after,
                damage_type=damage_type,
            ),
        )
        return applied

    def test_cast_records_the_chosen_damage_type(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Resistance')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 resistance player-1 --damage-type fire')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Resistance')
        self.assertEqual(tuple(effect.definition.damage_reduction_damage_types), ('fire',))

    def test_matching_damage_is_reduced_only_once_per_turn(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Resistance')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 resistance player-1 --damage-type fire')
        first_applied = self._apply_damage(session, target_id='player-1', damage_total=10, damage_type='fire')
        second_applied = self._apply_damage(session, target_id='player-1', damage_total=10, damage_type='fire')
        self.assertLess(first_applied, 10)
        self.assertEqual(second_applied, 10)

    def test_other_damage_types_are_not_reduced(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Resistance')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 resistance player-1 --damage-type fire')
        applied = self._apply_damage(session, target_id='player-1', damage_total=10, damage_type='cold')
        self.assertEqual(applied, 10)


if __name__ == '__main__':
    unittest.main()
