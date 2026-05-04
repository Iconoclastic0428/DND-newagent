from __future__ import annotations

import unittest
from dataclasses import replace

from shared_types.encounter_events import ActiveEffectStartedEvent, DamageAppliedEvent, SpellCastEvent
from shared_types.encounter_models import AttackKind, GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


class MagicWeaponLevel2SpellTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Magic Weapon'
    SPELL_SLUG = 'magic-weapon'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_to_actor(session, 'player-1')
        player = session.state.actors['player-1']
        player.position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(8, 8, 0)
        return session

    def _main_hand_item_id(self, session) -> str:
        item_id = session.state.actors['player-1'].main_hand_item_id
        self.assertIsNotNone(item_id)
        assert item_id is not None
        return item_id

    def _weapon_attack_id(self, session, item_id: str) -> str:
        player = session.state.actors['player-1']
        for attack_id, attack in player.attacks.items():
            if attack.source_item_id == item_id and attack.attack_kind == AttackKind.MELEE:
                return attack_id
        return next(iter(player.attacks))

    def _weapon_damage_total(self, session, item_id: str) -> int:
        attack_id = self._weapon_attack_id(session, item_id)
        player = session.state.actors['player-1']
        player.attacks[attack_id] = replace(player.attacks[attack_id], to_hit_bonus=99)
        monster = session.state.actors['monster-skeleton-1']
        monster.armor_class = 0
        start_index = len([event for event in session.state.event_log if isinstance(event, DamageAppliedEvent)])
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        damage_events = [event for event in session.state.event_log[start_index:] if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1']
        self.assertTrue(damage_events)
        return damage_events[-1].applied_damage_total

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 magic-weapon --item quarterstaff')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.parameters.get('item'), 'quarterstaff')

    def test_capability_definition_uses_flat_enchantment_bonuses(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertIsNotNone(capability)
        assert capability is not None
        self.assertEqual(capability.action_cost, 'bonus-action')
        self.assertEqual(capability.effect.enchanted_attack_bonus, 1)
        self.assertEqual(capability.effect.enchanted_damage_bonus, 1)
        self.assertFalse(capability.effect.concentration)

    def test_cast_creates_the_active_effect_on_the_selected_weapon(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon --item {item_id}')
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Magic Weapon' for event in session.state.event_log))
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Magic Weapon')
        self.assertEqual(effect.definition.enchanted_item_id, item_id)
        self.assertEqual(effect.definition.enchanted_attack_bonus, 1)
        self.assertEqual(effect.definition.enchanted_damage_bonus, 1)

    def test_weapon_damage_increases_while_the_spell_is_active(self) -> None:
        baseline = self._setup_session()
        item_id = self._main_hand_item_id(baseline)
        baseline_damage = self._weapon_damage_total(baseline, item_id)

        buffed = self._setup_session()
        item_id = self._main_hand_item_id(buffed)
        buffed.state, _ = buffed.command_interface.execute(buffed.state, f'/cast player-1 magic-weapon --item {item_id}')
        buffed_damage = self._weapon_damage_total(buffed, item_id)

        self.assertGreater(buffed_damage, baseline_damage)

    def test_cast_does_not_require_a_spellcasting_ability_when_only_flat_bonuses_apply(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        player = session.state.actors['player-1']
        player.spellcasting_ability = None
        player.spell_attack_bonus = None
        session.state, _ = session.command_interface.execute(session.state, f'/cast player-1 magic-weapon --item {item_id}')
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))

    def test_magical_weapons_are_rejected(self) -> None:
        session = self._setup_session()
        item_id = self._main_hand_item_id(session)
        session.command_interface.kernel.item_catalog[item_id] = replace(session.command_interface.kernel.item_catalog[item_id], is_magical=True)
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, f'/cast player-1 magic-weapon --item {item_id}')

if __name__ == '__main__':
    unittest.main()
