from __future__ import annotations

import unittest

from shared_types.battlefield import FallReason
from shared_types.encounter_events import FallDamageRolledEvent, ReactionWindowOpenedEvent, SpellCastEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class FeatherFallLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Feather Fall'
    SPELL_SLUG = 'feather-fall'

    def _setup_session(self, *, caster_position: GridPosition = GridPosition(0, 0, 0), falling_position: GridPosition = GridPosition(6, 0, 20)):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = caster_position
        session.state.actors['monster-skeleton-1'].position = falling_position
        session.state.actors['monster-skeleton-1'].fly_speed_ft = 30
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        session.command_interface.kernel.reconcile_support_state(
            session.state,
            actor_id='monster-skeleton-1',
            reason=FallReason.STATE_CHANGE,
        )
        return session

    def _trigger_fall(self, session) -> None:
        session.state.actors['monster-skeleton-1'].fly_speed_ft = 0
        session.command_interface.kernel.reconcile_support_state(
            session.state,
            actor_id='monster-skeleton-1',
            reason=FallReason.FLY_SPEED_ZERO,
        )

    def test_command_shape_uses_single_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 feather-fall monster-skeleton-1')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_effect_definition_prevents_falling_damage_and_slows_the_fall(self) -> None:
        session = self._setup_session()
        spell = session.state.actors['player-1'].spells[self.SPELL_SLUG]
        active_effect = spell.capability.effect.active_effect
        self.assertEqual(active_effect.fall_speed_override_ft, 60)
        self.assertTrue(active_effect.prevent_falling_damage)

    def test_fall_opens_a_feather_fall_reaction_window_for_nearby_casters(self) -> None:
        session = self._setup_session()
        self._trigger_fall(session)
        self.assertIsNotNone(session.state.pending_reaction_window)
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in session.state.event_log))
        assert session.state.pending_reaction_window is not None
        self.assertTrue(any(option.spell_id == self.SPELL_SLUG for option in session.state.pending_reaction_window.options))

    def test_choosing_the_reaction_prevents_fall_damage(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-skeleton-1'].current_hit_points
        self._trigger_fall(session)
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.spell_id == self.SPELL_SLUG)
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        self.assertEqual(session.state.actors['monster-skeleton-1'].current_hit_points, start_hp)
        self.assertFalse(any(isinstance(event, FallDamageRolledEvent) for event in session.state.event_log))
        self.assertFalse(session.state.actors['player-1'].reaction_available)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))

    def test_caster_out_of_range_gets_no_reaction_option(self) -> None:
        session = self._setup_session(caster_position=GridPosition(20, 20, 0), falling_position=GridPosition(6, 0, 20))
        self._trigger_fall(session)
        window = session.state.pending_reaction_window
        if window is None:
            self.assertIsNone(window)
            return
        self.assertFalse(any(option.spell_id == self.SPELL_SLUG for option in window.options))

    def test_landing_ends_the_feather_fall_effect(self) -> None:
        session = self._setup_session()
        self._trigger_fall(session)
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.spell_id == self.SPELL_SLUG)
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        self.assertFalse(any(effect.name == 'Feather Fall' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
