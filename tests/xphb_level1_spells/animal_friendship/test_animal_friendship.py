from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class AnimalFriendshipLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Animal Friendship'
    SPELL_SLUG = 'animal-friendship'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-skeleton-1'].creature_type = 'beast'
        return session

    def test_command_shape_targets_a_visible_beast(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 animal-friendship monster-skeleton-1')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_failed_save_applies_charmed_effect_for_24_hours(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = -20
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Animal Friendship')
        self.assertEqual(effect.remaining_rounds, 14400)
        conditions = {instance.condition_type for instance in session.state.actors['monster-skeleton-1'].condition_instances}
        self.assertIn(ConditionType.CHARMED, conditions)

    def test_successful_save_avoids_the_effect(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = 99
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        self.assertFalse(any(effect.name == 'Animal Friendship' for effect in session.state.active_effects.values()))
        self.assertFalse(any(instance.condition_type == ConditionType.CHARMED for instance in session.state.actors['monster-skeleton-1'].condition_instances))

    def test_non_beast_target_is_rejected(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        with self.assertRaises(EncounterValidationError):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-mage-1')

    def test_damage_from_caster_side_ends_the_effect(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Animal Friendship')
        events = session.command_interface.kernel._end_effects_on_source_side_damage(
            session.state,
            source_actor_id='player-1',
            target_id='monster-skeleton-1',
        )
        for event in events:
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertFalse(any(active.effect_instance_id == effect.effect_instance_id for active in session.state.active_effects.values()))

    def test_effect_payload_describes_the_charmed_beast_state(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='monster-skeleton-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Animal Friendship')
        payload = effect.definition.information_payloads[0]
        self.assertIn('animal-friendship', payload.tags)
        self.assertIn('beast', payload.tags)
        self.assertIn('charmed', payload.tags)


if __name__ == '__main__':
    unittest.main()
