from __future__ import annotations

from dataclasses import replace
import unittest

import encounter_runtime.conditions as runtime_conditions
from shared_types.conditions import ConditionType
from shared_types.encounter_events import ActiveEffectEndedEvent, DamageAppliedEvent, ReactionWindowOpenedEvent, SpellCastEvent
from shared_types.encounter_models import AttackKind, GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


def _patched_state_from_instances(actor, instances):
    clone = replace(actor, condition_instances=tuple(instances))
    return runtime_conditions.get_condition_state(clone)


runtime_conditions._state_from_instances = _patched_state_from_instances


class EnsnaringStrikeLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Ensnaring Strike'
    SPELL_SLUG = 'ensnaring-strike'
    COMMAND = '/cast player-1 ensnaring-strike monster-skeleton-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].spells[self.SPELL_SLUG] = replace(session.state.actors['player-1'].spells[self.SPELL_SLUG], action_cost='reaction')
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _melee_attack_id(self, session) -> str:
        actor = session.state.actors['player-1']
        for attack_id, attack in actor.attacks.items():
            if attack.attack_kind != AttackKind.RANGED and attack_id != 'unarmed-strike':
                return attack_id
        return 'unarmed-strike'

    def _trigger_after_melee_hit(self, session):
        attack_id = self._melee_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertIsNotNone(session.state.pending_reaction_window)
        assert session.state.pending_reaction_window is not None
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        return start_index

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_direct_cast_rejects_outside_a_reaction_window(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(EncounterValidationError, 'legal reaction window'):
            session.command_interface.execute(session.state, self.COMMAND)

    def test_melee_hit_opens_the_reaction_window_and_applies_the_restrained_condition(self) -> None:
        session = self._setup_session()
        start_index = self._trigger_after_melee_hit(session)
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in session.state.event_log[start_index:]))
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log[start_index:]))
        restrained = [instance for instance in session.state.actors['monster-skeleton-1'].condition_instances if instance.condition_type == ConditionType.RESTRAINED]
        self.assertTrue(restrained)
        self.assertTrue(any(effect.name == 'Ensnaring Strike' for effect in session.state.active_effects.values()))

    def test_failed_initial_strength_save_creates_lingering_damage_on_the_targets_turn(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = -20
        start_index = self._trigger_after_melee_hit(session)
        self.advance_existing_turn(session, 'monster-skeleton-1')
        new_damage_events = [
            event for event in session.state.event_log[start_index:]
            if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1' and event.damage_type == 'piercing'
        ]
        self.assertTrue(new_damage_events)
        self.assertLess(session.state.actors['monster-skeleton-1'].current_hit_points, session.state.actors['monster-skeleton-1'].max_hit_points)

    def test_successful_save_avoids_the_lingering_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = 99
        self._trigger_after_melee_hit(session)
        self.assertFalse(any(effect.name == 'Ensnaring Strike' for effect in session.state.active_effects.values()))
        self.assertFalse(any(instance.condition_type == ConditionType.RESTRAINED for instance in session.state.actors['monster-skeleton-1'].condition_instances))

    def test_concentration_break_ends_the_restrained_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = -20
        self._trigger_after_melee_hit(session)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Ensnaring Strike')
        for event in session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end'):
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertFalse(any(effect.name == 'Ensnaring Strike' for effect in session.state.active_effects.values()))
        self.assertFalse(any(instance.condition_type == ConditionType.RESTRAINED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason == 'test-end' for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
