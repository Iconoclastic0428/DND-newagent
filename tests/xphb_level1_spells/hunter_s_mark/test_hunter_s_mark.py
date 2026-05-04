from __future__ import annotations

import unittest

from encounter_runtime.conditions import get_ability_check_modifiers_or_auto_fail
from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class HuntersMarkLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = "Hunter's Mark"
    SPELL_SLUG = 'hunter-s-mark'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        return session

    def _attack(self, session, *, target_id: str):
        self.advance_to_actor(session, 'player-1')
        attack_id = 'dagger-thrown-dex' if 'dagger-thrown-dex' in session.state.actors['player-1'].attacks else next(attack_id for attack_id in session.state.actors['player-1'].attacks if attack_id != 'unarmed-strike')
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} {target_id}')
        return list(session.state.event_log)

    def _damage_types(self, events):
        return [event.damage_type for event in events if isinstance(event, DamageAppliedEvent)]

    def test_command_shape_targets_a_creature(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 hunter-s-mark monster-skeleton-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_cast_creates_concentration_mark_with_tracking_metadata(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == "Hunter's Mark")
        self.assertTrue(effect.definition.concentration)
        self.assertEqual(dict(effect.metadata)['marked-target-id'], 'monster-skeleton-1')
        self.assertIn('Perception', effect.definition.marked_target_skill_advantage_names)
        self.assertIn('Survival', effect.definition.marked_target_skill_advantage_names)

    def test_attack_against_marked_target_adds_force_damage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        session.state.actors['monster-skeleton-1'].armor_class = 1
        session.state.random_counter = self.find_attack_counter(session, actor_id='player-1')
        events = self._attack(session, target_id='monster-skeleton-1')
        self.assertIn('force', self._damage_types(events))

    def test_attack_against_other_target_does_not_add_force_damage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        session.state.actors['monster-mage-1'].armor_class = 1
        session.state.random_counter = self.find_attack_counter(session, actor_id='player-1')
        events = self._attack(session, target_id='monster-mage-1')
        self.assertNotIn('force', self._damage_types(events))

    def test_mark_grants_advantage_on_perception_checks_to_track_target(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        actor = session.state.actors['player-1']
        modifiers = get_ability_check_modifiers_or_auto_fail(
            actor,
            Ability.WIS,
            encounter_state=session.state,
            interacting_with_actor_id='monster-skeleton-1',
            skill_name='Perception',
        )
        self.assertTrue(modifiers.advantage)
        self.assertIn('marked-target-skill', modifiers.reasons)

    def test_transfer_requires_current_target_to_be_at_zero_hp(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1', parameters={'mode': 'transfer'})

    def test_transfer_after_zero_hp_moves_mark(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        session.state.actors['monster-skeleton-1'].current_hit_points = 0
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1', parameters={'mode': 'transfer'})
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == "Hunter's Mark")
        self.assertEqual(dict(effect.metadata)['marked-target-id'], 'monster-mage-1')


if __name__ == '__main__':
    unittest.main()
