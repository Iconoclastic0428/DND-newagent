from __future__ import annotations

import copy
import json
from dataclasses import replace
from pathlib import Path
import unittest

from encounter_runtime.conditions import get_targeting_visibility_legality
from encounter_runtime.visibility import assess_visibility
from shared_types.battlefield import BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, LightingLevel, ObscurementLevel, TraversalMode
from shared_types.encounter_models import GridPosition
from shared_types.visibility import ObserverVisibilityState
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'darkvision'


class DarkvisionTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Darkvision'
    SPELL_SLUG = 'darkvision'

    def _build_linear_battlefield(self, width: int = 40) -> BattlefieldState:
        tiles = {}
        for x in range(width):
            tile = BattlefieldTile(
                position=GridPosition(x, 0, 0),
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
            tiles[tile.position.horizontal()] = tile
        return BattlefieldState(
            map_id='darkvision-linear-test',
            name='Darkvision Linear Test',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=width,
                height=1,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=width - 1,
                max_y=0,
            ),
            tiles=dict(tiles),
            base_tiles=dict(tiles),
            features={},
            object_ids=(),
            blocker_ids=(),
        )

    def _set_tile(self, session, position: GridPosition, *, lighting=None, obscurement=None):
        key = position.horizontal()
        tile = session.state.battlefield.tiles[key]
        session.state.battlefield.tiles[key] = replace(
            tile,
            lighting=tile.lighting if lighting is None else lighting,
            obscurement=tile.obscurement if obscurement is None else obscurement,
        )

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.battlefield = self._build_linear_battlefield()
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(10, 0, 0)
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_is_a_touch_buff_for_a_willing_creature(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'action')
        self.assertEqual(capability.targeting.range_ft, 5)
        self.assertEqual(capability.targeting.affinity.value, 'ally')
        self.assertEqual(capability.effect.active_effect.darkvision_radius_ft, 150)
        self.assertFalse(capability.effect.active_effect.concentration)

    def test_cast_grants_150_foot_darkvision(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-1')
        actor = session.state.actors['player-1']
        self.assertEqual(actor.darkvision_radius_ft, 150)
        self.assertTrue(any(effect.name == 'Darkvision' and actor.actor_id in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_darkvision_allows_visibility_and_targeting_in_darkness_within_range(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        monster = session.state.actors['monster-skeleton-1']
        self._set_tile(session, monster.position, lighting=LightingLevel.DARKNESS)
        before = assess_visibility(session.state, player, monster)
        self.assertEqual(before.visibility_state, ObserverVisibilityState.UNSEEN)

        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-1')
        after = assess_visibility(session.state, player, monster)
        legality = get_targeting_visibility_legality(player, monster, requires_target_to_be_seen=True, encounter_state=session.state)
        self.assertEqual(after.visibility_state, ObserverVisibilityState.VISIBLE)
        self.assertTrue(legality.legal)

    def test_darkvision_does_not_bypass_heavy_obscurement(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-1')
        player = session.state.actors['player-1']
        monster = session.state.actors['monster-skeleton-1']
        self._set_tile(session, monster.position, lighting=LightingLevel.DARKNESS, obscurement=ObscurementLevel.HEAVY)
        assessment = assess_visibility(session.state, player, monster)
        self.assertEqual(assessment.visibility_state, ObserverVisibilityState.UNSEEN)
        self.assertFalse(assessment.can_see_target)

    def test_darkness_beyond_the_150_foot_radius_remains_unseen(self) -> None:
        session = self._setup_session()
        session.state.actors['monster-skeleton-1'].position = GridPosition(31, 0, 0)
        self._set_tile(session, session.state.actors['monster-skeleton-1'].position, lighting=LightingLevel.DARKNESS)
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-1')
        assessment = assess_visibility(session.state, session.state.actors['player-1'], session.state.actors['monster-skeleton-1'])
        self.assertEqual(assessment.visibility_state, ObserverVisibilityState.UNSEEN)

    def test_same_caster_can_maintain_separate_darkvision_effects_on_multiple_allies(self) -> None:
        session = self._setup_session()
        ally = copy.deepcopy(session.state.actors['player-1'])
        ally.actor_id = 'player-2'
        ally.name = 'Player 2'
        ally.position = GridPosition(1, 0, 0)
        session.state.actors['player-2'] = ally

        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-1')
        session.state.actors['player-1'].action_available = True
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 darkvision player-2')

        self.assertEqual(session.state.actors['player-1'].darkvision_radius_ft, 150)
        self.assertEqual(session.state.actors['player-2'].darkvision_radius_ft, 150)
        effect_targets = [tuple(sorted(effect.target_actor_ids)) for effect in session.state.active_effects.values() if effect.name == 'Darkvision']
        self.assertIn(('player-1',), effect_targets)
        self.assertIn(('player-2',), effect_targets)

    def test_enemy_target_is_rejected_by_the_willing_target_model(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 darkvision monster-skeleton-1')


if __name__ == '__main__':
    unittest.main()
