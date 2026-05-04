from __future__ import annotations

import unittest
from dataclasses import replace

from shared_types.encounter_events import ActiveEffectStartedEvent, DamageAppliedEvent
from shared_types.encounter_models import AttackKind
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class DivineFavorLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Divine Favor'
    SPELL_SLUG = 'divine-favor'
    COMMAND = '/cast player-1 divine-favor player-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _weapon_attack_id(self, session) -> str:
        actor = session.state.actors['player-1']
        for attack_id, attack in actor.attacks.items():
            if attack.attack_kind != AttackKind.RANGED and attack_id != 'unarmed-strike':
                return attack_id
        return next(iter(actor.attacks))

    def _weapon_damage_total(self, session) -> int:
        attack_id = self._weapon_attack_id(session)
        session.state.actors['monster-mage-1'].armor_class = 0
        player = session.state.actors['player-1']
        session.state.actors['monster-mage-1'].position = type(player.position)(player.position.x + 1, player.position.y, player.position.z)
        player.attacks[attack_id] = replace(player.attacks[attack_id], to_hit_bonus=99)
        start_count = len([event for event in session.state.event_log if isinstance(event, DamageAppliedEvent)])
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-mage-1')
        if session.state.pending_reaction_window is not None:
            session.state, _ = session.command_interface.execute(session.state, '/react monster-mage-1 decline')
        damage_events = [event for event in session.state.event_log[start_count:] if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-mage-1']
        self.assertTrue(damage_events)
        return damage_events[-1].applied_damage_total

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_the_active_effect_and_spends_the_bonus_action(self) -> None:
        session = self._setup_session()
        self.assertTrue(session.state.actors['player-1'].bonus_action_available)
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Divine Favor' for event in session.state.event_log))
        self.assertTrue(any(effect.name == 'Divine Favor' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_active_effect_exposes_the_expected_weapon_bonus_damage(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Divine Favor')
        self.assertIsNotNone(effect.definition.weapon_attack_bonus_damage)
        self.assertEqual(effect.definition.weapon_attack_bonus_damage.dice_count, 1)
        self.assertEqual(effect.definition.weapon_attack_bonus_damage.die_faces, 4)
        self.assertEqual(effect.definition.weapon_attack_bonus_damage.damage_type, 'radiant')

    def test_weapon_hit_damage_increases_while_the_spell_is_active(self) -> None:
        baseline = self._setup_session()
        baseline_damage = self._weapon_damage_total(baseline)

        buffed = self._setup_session()
        buffed.state, _ = buffed.command_interface.execute(buffed.state, self.COMMAND)
        buffed_damage = self._weapon_damage_total(buffed)

        self.assertGreater(buffed_damage, baseline_damage)

    def test_effect_persists_across_the_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Divine Favor' for effect in session.state.active_effects.values()))
        self.assertTrue(session.state.actors['player-1'].bonus_action_available)


if __name__ == '__main__':
    unittest.main()
