from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest

from player_interface import EncounterSlashCommandInterface
from shared_types.encounter_events import SneakAttackAppliedEvent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class RogueSneakAttackFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        runtime = self.build_runtime()
        rogue_record = self.complete_record('rogue', overrides={'class:rogue:expertise': ('acrobatics', 'thieves-tools'), 'class:rogue:weapon-mastery': ('dagger', 'shortbow')})
        ally_record = self.complete_record('fighter')
        monster_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(
                CharacterPlacement(actor_id='player-1', record=rogue_record, position=GridPosition(0, 0, 0)),
                CharacterPlacement(actor_id='ally-1', record=ally_record, position=GridPosition(1, 1, 0)),
            ),
            monsters=(MonsterPlacement(actor_id='monster-1', monster_id=monster_id, position=GridPosition(1, 0, 0)),),
        )
        return SimpleNamespace(runtime_services=runtime, command_interface=EncounterSlashCommandInterface(runtime.kernel), state=state)

    def _finesse_attack_id(self, session) -> str:
        actor = session.state.actors['player-1']
        for attack_id, attack in actor.attacks.items():
            if attack.is_finesse and attack.attack_kind.value == 'melee':
                return attack_id
        raise AssertionError('No finesse melee attack was found for the rogue.')

    def test_feature_name_is_recorded(self) -> None:
        record = self.complete_record('rogue', overrides={'class:rogue:expertise': ('acrobatics', 'thieves-tools'), 'class:rogue:weapon-mastery': ('dagger', 'shortbow')})
        self.assertIn('Sneak Attack', record.class_feature_names)

    def test_qualifying_hit_opens_a_sneak_attack_prompt_without_spending_reaction(self) -> None:
        session = self._session()
        self.advance_to_actor(session, 'player-1')
        attack_id = self._finesse_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-1')
        self.assertIsNotNone(session.state.pending_reaction_window)
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.capability_id == 'sneak-attack')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        self.assertTrue(session.state.actors['player-1'].reaction_available)
        self.assertTrue(self.events_since(session, start_index, SneakAttackAppliedEvent))

    def test_sneak_attack_can_only_apply_once_per_turn(self) -> None:
        session = self._session()
        self.advance_to_actor(session, 'player-1')
        attack_id = self._finesse_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-1')
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.capability_id == 'sneak-attack')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        session.state.actors['player-1'].action_available = True
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-1')
        if session.state.pending_reaction_window is not None:
            self.assertFalse(any(option.capability_id == 'sneak-attack' for option in session.state.pending_reaction_window.options))

    def test_sneak_attack_can_apply_on_a_different_turn_via_a_readied_attack(self) -> None:
        session = self._session()
        session.state.actors['monster-1'].position = GridPosition(3, 0, 0)
        self.advance_to_actor(session, 'player-1')
        attack_id = self._finesse_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        session.state, _ = session.command_interface.execute(session.state, f'/ready attack player-1 monster-1 {attack_id}')
        self.end_turn_and_resolve(session, 'player-1')
        self.advance_existing_turn(session, 'monster-1')
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/move monster-1 1 0')
        ready_option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {ready_option_id}')
        self.assertFalse(session.state.actors['player-1'].reaction_available)
        self.assertIsNotNone(session.state.pending_reaction_window)
        sneak_option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.capability_id == 'sneak-attack')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {sneak_option_id}')
        events = self.events_since(session, start_index, SneakAttackAppliedEvent)
        self.assertTrue(events)
        self.assertEqual(events[-1].current_turn_actor_id, 'monster-1')


if __name__ == '__main__':
    unittest.main()

