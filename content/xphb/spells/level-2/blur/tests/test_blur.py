from __future__ import annotations

import json
from pathlib import Path
import unittest

from encounter_runtime.conditions import get_attack_roll_modifiers
from encounter_runtime.visibility import assess_visibility
from shared_types.encounter_models import GridPosition
from shared_types.visibility import ObserverVisibilityState
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'blur'


class BlurTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Blur'
    SPELL_SLUG = 'blur'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_is_a_self_only_concentration_defense_buff(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'action')
        self.assertEqual(capability.targeting.selection_kind.value, 'self')
        self.assertTrue(capability.effect.active_effect.concentration)
        self.assertTrue(capability.effect.active_effect.attackers_rely_on_sight_have_disadvantage)

    def test_cast_starts_concentration_on_the_caster(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        actor = session.state.actors['player-1']
        self.assertIsNotNone(actor.concentrating_effect_id)
        self.assertTrue(any(effect.name == 'Blur' and actor.actor_id in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_incoming_attacks_have_disadvantage_while_blur_is_active(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        mods = get_attack_roll_modifiers(session.state.actors['monster-skeleton-1'], session.state.actors['player-1'], distance_ft=5, encounter_state=session.state)
        self.assertTrue(mods.disadvantage)
        self.assertIn('blurred-target', mods.reasons)

    def test_blindsight_bypasses_the_blur_disadvantage(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        attacker = session.state.actors['monster-skeleton-1']
        attacker.blindsight_radius_ft = 10
        mods = get_attack_roll_modifiers(attacker, session.state.actors['player-1'], distance_ft=5, encounter_state=session.state)
        self.assertNotIn('blurred-target', mods.reasons)

    def test_truesight_bypasses_the_blur_disadvantage(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        attacker = session.state.actors['monster-skeleton-1']
        attacker.truesight_radius_ft = 10
        mods = get_attack_roll_modifiers(attacker, session.state.actors['player-1'], distance_ft=5, encounter_state=session.state)
        self.assertNotIn('blurred-target', mods.reasons)

    def test_blur_does_not_hide_the_caster(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        assessment = assess_visibility(session.state, session.state.actors['monster-skeleton-1'], session.state.actors['player-1'])
        self.assertEqual(assessment.visibility_state, ObserverVisibilityState.VISIBLE)

    def test_recasting_blur_does_not_stack_multiple_blur_effects(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        session.state.actors['player-1'].action_available = True
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 blur')
        blur_effects = [effect for effect in session.state.active_effects.values() if effect.name == 'Blur']
        self.assertEqual(len(blur_effects), 1)


if __name__ == '__main__':
    unittest.main()
