from __future__ import annotations

from dataclasses import replace
import unittest

from shared_types.encounter_events import DamageAppliedEvent, SpellCastEvent
from shared_types.encounter_models import AttackKind, AttackProfile, AttackUsageKind, GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class HailOfThornsLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Hail of Thorns'
    SPELL_SLUG = 'hail-of-thorns'
    COMMAND = '/cast player-1 hail-of-thorns monster-skeleton-1'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(3, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state.actors['monster-mage-1'].armor_class = 10
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
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
        return session

    def _trigger_spell(self, session):
        session.state, _ = session.command_interface.execute(session.state, '/attack player-1 test-longbow monster-skeleton-1')
        self.assertIsNotNone(session.state.pending_reaction_window)
        assert session.state.pending_reaction_window is not None
        self.assertEqual(session.state.pending_reaction_window.trigger_type.value, 'post-hit-trigger')
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        return [event for event in session.state.event_log[start_index:] if isinstance(event, DamageAppliedEvent)]

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

    def test_ranged_hit_opens_trigger_and_damages_primary_and_nearby_creatures(self) -> None:
        session = self._setup_session()
        damage_events = self._trigger_spell(session)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        self.assertTrue(session.state.actors['player-1'].reaction_available)
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log))
        target_ids = {event.target_id for event in damage_events if event.damage_type == 'piercing'}
        self.assertIn('monster-skeleton-1', target_ids)
        self.assertIn('monster-mage-1', target_ids)

    def test_successful_save_takes_less_damage_than_failed_save(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.DEX] = -20
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.DEX] = 99
        damage_events = self._trigger_spell(session)
        damage_by_target = {}
        for event in damage_events:
            if event.damage_type == 'piercing' and event.target_id in {'monster-skeleton-1', 'monster-mage-1'} and event.target_id not in damage_by_target:
                damage_by_target[event.target_id] = event.applied_damage_total
        self.assertGreater(damage_by_target['monster-skeleton-1'], damage_by_target['monster-mage-1'])

    def test_melee_attack_does_not_open_hail_of_thorns_trigger(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        player = session.state.actors['player-1']
        attack_id = next(attack_id for attack_id, attack in player.attacks.items() if attack.attack_kind != AttackKind.RANGED)
        player.attacks[attack_id] = replace(player.attacks[attack_id], to_hit_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertIsNone(session.state.pending_reaction_window)

    def test_no_trigger_opens_when_bonus_action_is_unavailable(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].bonus_action_available = False
        session.state, _ = session.command_interface.execute(session.state, '/attack player-1 test-longbow monster-skeleton-1')
        self.assertIsNone(session.state.pending_reaction_window)


if __name__ == '__main__':
    unittest.main()
