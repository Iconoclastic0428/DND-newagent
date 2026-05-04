from __future__ import annotations

import unittest
from dataclasses import replace

from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, SpellCastEvent
from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.conditions import ConditionType
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


class InvisibilityLevel2SpellTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Invisibility'
    SPELL_SLUG = 'invisibility'
    COMMAND = '/cast player-1 invisibility player-1'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(8, 8, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(9, 9, 0)
        return session

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_capability_definition_requires_touch_and_concentration(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(capability.action_cost, 'action')
        self.assertEqual(capability.targeting.range_ft, 5)
        self.assertTrue(capability.effect.active_effect.concentration)
        self.assertTrue(capability.effect.active_effect.end_when_target_attacks_or_harmful_casts)

    def test_cast_applies_the_invisible_condition_to_the_target(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        actor = session.state.actors['player-1']
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Invisibility' for event in session.state.event_log))
        self.assertTrue(any(instance.condition_type == ConditionType.INVISIBLE for instance in actor.condition_instances))

    def test_cast_on_another_creature_is_supported(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 invisibility monster-skeleton-1')
        self.assertTrue(any('monster-skeleton-1' in effect.target_actor_ids and effect.name == 'Invisibility' for effect in session.state.active_effects.values()))

    def test_effect_persists_across_the_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.assertTrue(any(effect.name == 'Invisibility' for effect in session.state.active_effects.values()))

    def test_attacking_ends_invisibility(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        player = session.state.actors['player-1']
        attack_id = next(iter(player.attacks))
        player.attacks[attack_id] = replace(player.attacks[attack_id], to_hit_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.effect.name == 'Invisibility' for event in session.state.event_log))
        self.assertFalse(any(effect.name == 'Invisibility' for effect in session.state.active_effects.values()))

if __name__ == '__main__':
    unittest.main()
