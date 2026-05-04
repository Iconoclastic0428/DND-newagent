from __future__ import annotations

from dataclasses import replace
import unittest

import encounter_runtime.conditions as runtime_conditions
from shared_types.battlefield import BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, LightingLevel, ObscurementLevel, TraversalMode
from shared_types.conditions import ConditionType
from shared_types.encounter_events import DamageAppliedEvent, ReactionWindowOpenedEvent, SpellCastEvent
from shared_types.encounter_models import AttackKind, GridPosition
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


def _patched_state_from_instances(actor, instances):
    clone = replace(actor, condition_instances=tuple(instances))
    return runtime_conditions.get_condition_state(clone)


runtime_conditions._state_from_instances = _patched_state_from_instances


class ThunderousSmiteLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Thunderous Smite'
    SPELL_SLUG = 'thunderous-smite'
    COMMAND = '/cast player-1 thunderous-smite monster-skeleton-1'

    def _battlefield(self) -> BattlefieldState:
        tiles = {}
        for x in range(0, 20):
            for y in range(0, 20):
                position = GridPosition(x, y, 0)
                tiles[position] = BattlefieldTile(
                    position=position,
                    terrain_id='stone-floor',
                    elevation_ft=0,
                    ceiling_ft=20,
                    traversable=True,
                    occupiable=True,
                    movement_cost_feet_per_5ft=5,
                    difficult_terrain=False,
                    lightly_obscured=False,
                    lighting=LightingLevel.BRIGHT,
                    obscurement=ObscurementLevel.NONE,
                    blocks_los=False,
                    blocks_loe=False,
                    base_cover=CoverLevel.NONE,
                    supported_modes=(TraversalMode.WALK, TraversalMode.CLIMB, TraversalMode.FLY),
                )
        return BattlefieldState(
            map_id='thunderous-smite-test-map',
            name='Thunderous Smite Test Map',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=20,
                height=20,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=19,
                max_y=19,
            ),
            tiles=dict(tiles),
            base_tiles=dict(tiles),
        )

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].spells[self.SPELL_SLUG] = replace(session.state.actors['player-1'].spells[self.SPELL_SLUG], action_cost='reaction')
        session.state.battlefield = self._battlefield()
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-skeleton-1'].armor_class = 0
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _melee_attack_id(self, session) -> str:
        actor = session.state.actors['player-1']
        for attack_id, attack in actor.attacks.items():
            if attack.attack_kind != AttackKind.RANGED and attack_id != 'unarmed-strike':
                return attack_id
        return 'unarmed-strike'

    def _trigger_after_melee_hit(self, session):
        attack_id = self._melee_attack_id(session)
        session.state.actors['player-1'].attacks[attack_id] = replace(session.state.actors['player-1'].attacks[attack_id], to_hit_bonus=99)
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, f'/attack player-1 {attack_id} monster-skeleton-1')
        self.assertIsNotNone(session.state.pending_reaction_window)
        assert session.state.pending_reaction_window is not None
        option_id = next(option.option_id for option in session.state.pending_reaction_window.options if option.actor_id == 'player-1')
        session.state, _ = session.command_interface.execute(session.state, f'/react player-1 {option_id}')
        return start_index

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')

    def test_direct_cast_rejects_outside_a_reaction_window(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(EncounterValidationError, 'legal reaction window'):
            session.command_interface.execute(session.state, self.COMMAND)

    def test_melee_hit_opens_the_reaction_window_and_deals_thunder_damage(self) -> None:
        session = self._setup_session()
        start_index = self._trigger_after_melee_hit(session)
        self.assertTrue(any(isinstance(event, ReactionWindowOpenedEvent) for event in session.state.event_log[start_index:]))
        self.assertTrue(any(isinstance(event, SpellCastEvent) and event.spell_id == self.SPELL_SLUG for event in session.state.event_log[start_index:]))
        thunder_events = [event for event in session.state.event_log[start_index:] if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-skeleton-1' and event.damage_type == 'thunder']
        self.assertTrue(thunder_events)

    def test_failed_save_pushes_the_target_and_knocks_it_prone(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = -20
        self._trigger_after_melee_hit(session)
        target = session.state.actors['monster-skeleton-1']
        self.assertEqual(target.position.x, 3)
        self.assertTrue(any(instance.condition_type == ConditionType.PRONE for instance in target.condition_instances))

    def test_successful_save_avoids_the_push_and_prone_effects(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = 99
        self._trigger_after_melee_hit(session)
        target = session.state.actors['monster-skeleton-1']
        self.assertEqual(target.position.x, 1)
        self.assertFalse(any(instance.condition_type == ConditionType.PRONE for instance in target.condition_instances))

    def test_ranged_attacks_do_not_open_the_post_hit_window(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        player.attacks['test-longbow'] = replace(
            next(attack for attack in player.attacks.values() if attack.attack_kind == AttackKind.RANGED),
            attack_id='test-longbow',
            name='Test Longbow',
            to_hit_bonus=99,
        )
        session.state.actors['monster-skeleton-1'].position = GridPosition(4, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, '/attack player-1 test-longbow monster-skeleton-1')
        self.assertIsNone(session.state.pending_reaction_window)


if __name__ == '__main__':
    unittest.main()
