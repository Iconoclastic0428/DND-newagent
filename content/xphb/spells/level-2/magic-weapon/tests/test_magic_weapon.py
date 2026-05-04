from __future__ import annotations

import copy
from dataclasses import replace
import json
from pathlib import Path
import unittest

from shared_types.errors import EncounterValidationError
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'magic-weapon'


class MagicWeaponTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Magic Weapon'
    SPELL_SLUG = 'magic-weapon'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        return session

    def _main_hand_item_id(self, session, actor_id: str = 'player-1') -> str:
        item_id = session.state.actors[actor_id].main_hand_item_id
        self.assertIsNotNone(item_id)
        return item_id

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_targets_a_touched_weapon_and_scales_bonus_by_slot(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'bonus-action')
        self.assertEqual(capability.targeting.range_ft, 5)
        self.assertTrue(capability.effect.select_item_from_target_actor)
        self.assertEqual(capability.effect.scaled_enchanted_bonus_tiers, ((3, 2), (6, 3)))

    def test_cast_applies_to_the_casters_weapon(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-1 --item {item_id}')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Magic Weapon')
        self.assertEqual(effect.definition.enchanted_item_id, item_id)
        self.assertEqual(effect.definition.enchanted_attack_bonus, 1)

    def test_cast_can_target_an_ally_weapon(self) -> None:
        session = self._setup_session()
        ally = copy.deepcopy(session.state.actors['player-1'])
        ally.actor_id = 'player-2'
        ally.name = 'Player 2'
        ally.position = GridPosition(1, 2, 0)
        session.state.actors['player-2'] = ally
        item_id = self._main_hand_item_id(session, 'player-2')
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-2 --item {item_id}')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Magic Weapon')
        self.assertEqual(effect.target_actor_ids, ('player-2',))
        self.assertEqual(effect.definition.enchanted_item_id, item_id)

    def test_higher_slot_increases_the_enchantment_bonus(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-1 --item {item_id} --slot-level 3')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Magic Weapon')
        self.assertEqual(effect.definition.enchanted_attack_bonus, 2)
        self.assertEqual(effect.definition.enchanted_damage_bonus, 2)

    def test_magical_weapons_are_rejected(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.command_interface.kernel.item_catalog[item_id] = replace(session.command_interface.kernel.item_catalog[item_id], is_magical=True)
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-1 --item {item_id}')

    def test_recast_replaces_the_previous_effect_from_the_same_source(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-1 --item {item_id}')
        session.state.actors['player-1'].bonus_action_available = True
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon player-1 --item {item_id} --slot-level 3')
        active = [effect for effect in session.state.active_effects.values() if effect.name == 'Magic Weapon']
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].definition.enchanted_attack_bonus, 2)


if __name__ == '__main__':
    unittest.main()