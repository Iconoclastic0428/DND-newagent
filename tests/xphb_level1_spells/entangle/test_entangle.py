from __future__ import annotations

import unittest

from shared_types.battlefield import BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, LightingLevel, ObscurementLevel, TraversalMode
from shared_types.conditions import ConditionType
from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, PersistentAreaCreatedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class EntangleLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Entangle'
    SPELL_SLUG = 'entangle'
    COMMAND = '/cast player-1 entangle 2 0'

    def _open_battlefield(self) -> BattlefieldState:
        tiles = {}
        for x in range(0, 9):
            for y in range(0, 5):
                position = GridPosition(x, y, 0)
                tiles[position] = BattlefieldTile(
                    position=position,
                    terrain_id='grass',
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
            map_id='entangle-test-map',
            name='Entangle Test Map',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=9,
                height=5,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=8,
                max_y=4,
            ),
            tiles=dict(tiles),
            base_tiles=dict(tiles),
        )

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.battlefield = self._open_battlefield()
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.STR] = -20
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.STR] = 99
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def _effect_names(self, session):
        return {effect.name for effect in session.state.active_effects.values()}

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self.COMMAND)
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 0))

    def test_cast_creates_the_area_effect_and_persistent_area(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertIn('Entangle Area', self._effect_names(session))
        self.assertTrue(any(isinstance(event, ActiveEffectStartedEvent) and event.effect.name == 'Entangle Area' for event in session.state.event_log))
        self.assertTrue(any(isinstance(event, PersistentAreaCreatedEvent) and event.area.definition.name == 'Entangle' for event in session.state.event_log))

    def test_failed_strength_save_applies_restrained(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        restrained = [instance for instance in session.state.actors['monster-skeleton-1'].condition_instances if instance.condition_type == ConditionType.RESTRAINED]
        self.assertTrue(restrained)
        self.assertIn('Entangle Restrained', self._effect_names(session))

    def test_successful_strength_save_avoids_restrained(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        restrained = [instance for instance in session.state.actors['monster-mage-1'].condition_instances if instance.condition_type == ConditionType.RESTRAINED]
        self.assertFalse(restrained)

    def test_area_marks_battlefield_tiles_as_difficult_terrain(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        self.assertIn(GridPosition(2, 0, 0), session.state.battlefield.difficult_terrain_positions)
        self.assertIn(GridPosition(4, 0, 0), session.state.battlefield.difficult_terrain_positions)

    def test_effect_persists_across_the_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertIn('Entangle Area', self._effect_names(session))

    def test_ending_the_area_effect_clears_the_linked_restrained_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self.COMMAND)
        area_effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Entangle Area')
        for event in session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=area_effect.effect_instance_id, reason='test-end'):
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertNotIn('Entangle Area', self._effect_names(session))
        self.assertNotIn('Entangle Restrained', self._effect_names(session))
        self.assertFalse(any(instance.condition_type == ConditionType.RESTRAINED for instance in session.state.actors['monster-skeleton-1'].condition_instances))
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.reason in {'test-end', 'source-effect-ended'} for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
