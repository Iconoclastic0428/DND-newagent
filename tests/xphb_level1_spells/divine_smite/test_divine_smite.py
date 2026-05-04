from __future__ import annotations

from dataclasses import replace
import unittest

from shared_types.encounter_events import DamageAppliedEvent, ReactionWindowOpenedEvent, SpellCastEvent
from shared_types.encounter_models import AttackKind, AttackProfile, AttackUsageKind, GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class DivineSmiteLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Divine Smite'
    SPELL_SLUG = 'divine-smite'
    COMMAND = '/cast player-1 divine-smite monster-skeleton-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['player-1'].armor_class = 12
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _melee_attack_id(self, session) -> str:
        actor = session.state.actors['player-1']
        for attack_id, attack in actor.attacks.items():
            if attack.attack_kind != AttackKind.RANGED and attack_id != 'unarmed-strike':
                return attack_id
        return 'unarmed-strike'

    def _grant_test_ranged_attack(self, session) -> str:
        player = session.state.actors['player-1']
        player.attacks['test-longbow'] = AttackProfile(
            attack_id='test-longbow',
            name='Test Longbow',
            attack_kind=AttackKind.RANGED,
            to_hit_bonus=99,
            reach_ft=None,
            range_ft=60,
            long_range_ft=120,
            damage_dice_count=1,
            damage_die_faces=8,
            damage_bonus=3,
            damage_type='piercing',
            attack_usage_kind=AttackUsageKind.WEAPON_RANGED,
        )
        return 'test-longbow'

    def _cast_after_hit(self, session, *, target_id: str = 'monster-skeleton-1') -> list[DamageAppliedEvent]:
        attack_id = self._melee_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} {target_id}')
        self.assertIsNotNone(session.state.pending_reaction_window)
        assert session.state.pending_reaction_window is not None
        self.assertEqual(session.state.pending_reaction_window.trigger_type.value, 'post-hit-trigger')
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        return [
            event for event in session.state.event_log[start_index:]
            if isinstance(event, DamageAppliedEvent) and event.target_id == target_id
        ]

    def _spell_damage_total(self, events: list[DamageAppliedEvent]) -> int:
        radiant = [event for event in events if event.damage_type == 'radiant']
        self.assertTrue(radiant)
        return sum(event.applied_damage_total for event in radiant)

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_direct_cast_rejects_outside_a_post_hit_window(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(EncounterValidationError, 'legal post-hit trigger window'):
            session.command_interface.execute(session.state, self.COMMAND)

    def test_melee_hit_opens_post_hit_window_and_reaction_adds_radiant_damage(self) -> None:
        session = self._setup_session()
        damage_events = self._cast_after_hit(session)
        self.assertGreaterEqual(len(damage_events), 2)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(session.state.actors['player-1'].reaction_available)
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))
        self.assertGreater(self._spell_damage_total(damage_events), 0)

    def test_ranged_weapon_hit_does_not_open_divine_smite_trigger(self) -> None:
        session = self._setup_session()
        attack_id = self._grant_test_ranged_attack(session)
        session.state.actors['monster-skeleton-1'].position = GridPosition(6, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertIsNone(session.state.pending_reaction_window)
        self.assertFalse(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))

    def test_undead_target_takes_extra_radiant_damage(self) -> None:
        humanoid_session = self._setup_session()
        humanoid_session.state.actors['monster-skeleton-1'].creature_type = 'humanoid'
        humanoid_damage = self._spell_damage_total(self._cast_after_hit(humanoid_session))

        undead_session = self._setup_session()
        undead_session.state.actors['monster-skeleton-1'].creature_type = 'undead'
        undead_damage = self._spell_damage_total(self._cast_after_hit(undead_session))

        self.assertGreater(undead_damage, humanoid_damage)

    def test_no_trigger_opens_when_bonus_action_is_unavailable(self) -> None:
        session = self._setup_session()
        attack_id = self._melee_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        session.state.actors['player-1'].bonus_action_available = False
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertIsNone(session.state.pending_reaction_window)


if __name__ == '__main__':
    unittest.main()
