from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.encounter_events import ActiveEffectEndedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'aid'


class AidTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Aid'
    SPELL_SLUG = 'aid'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(3, 1, 0)
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_targets_up_to_three_creatures_and_scales_bonus_per_slot(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'action')
        self.assertEqual(capability.targeting.range_ft, 30)
        self.assertEqual(capability.targeting.max_targets, 3)
        self.assertEqual(capability.effect.active_effect.max_hit_points_bonus, 5)
        self.assertEqual(capability.effect.bonus_max_hit_points_per_slot_level, 5)

    def test_cast_increases_current_and_max_hit_points(self) -> None:
        session = self._setup_session()
        target = session.state.actors['player-1']
        starting_hp = target.current_hit_points
        starting_max = target.max_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 aid player-1')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, starting_hp + 5)
        self.assertEqual(session.state.actors['player-1'].max_hit_points, starting_max + 5)

    def test_cast_supports_three_targets(self) -> None:
        session = self._setup_session()
        starting_max = {actor_id: session.state.actors[actor_id].max_hit_points for actor_id in ('player-1', 'monster-skeleton-1', 'monster-mage-1')}
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 aid --targets player-1,monster-skeleton-1,monster-mage-1')
        for actor_id in ('player-1', 'monster-skeleton-1', 'monster-mage-1'):
            self.assertTrue(any(effect.name == 'Aid' and actor_id in effect.target_actor_ids for effect in session.state.active_effects.values()))
            self.assertEqual(session.state.actors[actor_id].max_hit_points, starting_max[actor_id] + 5)

    def test_higher_slot_increases_the_bonus(self) -> None:
        session = self._setup_session()
        target = session.state.actors['player-1']
        starting_hp = target.current_hit_points
        starting_max = target.max_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 aid player-1 --slot-level 3')
        self.assertEqual(session.state.actors['player-1'].current_hit_points, starting_hp + 10)
        self.assertEqual(session.state.actors['player-1'].max_hit_points, starting_max + 10)

    def test_effect_end_rolls_the_bonus_back_off(self) -> None:
        session = self._setup_session()
        starting_max = session.state.actors['player-1'].max_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 aid player-1')
        effect_id = next(effect_id for effect_id, effect in session.state.active_effects.items() if effect.name == 'Aid')
        for event in session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect_id, reason='test-expire'):
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)
        self.assertEqual(session.state.actors['player-1'].max_hit_points, starting_max)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) and event.effect_instance_id == effect_id for event in session.state.event_log))

    def test_more_than_three_targets_are_rejected(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 aid --targets player-1,monster-skeleton-1,monster-mage-1,player-2')


if __name__ == '__main__':
    unittest.main()
