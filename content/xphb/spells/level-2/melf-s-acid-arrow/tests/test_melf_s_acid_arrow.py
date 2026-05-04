from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.encounter_events import DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'melf-s-acid-arrow'


class MelfsAcidArrowTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = "Melf's Acid Arrow"
    SPELL_SLUG = 'melf-s-acid-arrow'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 1, 0)
        session.state.actors['player-1'].spell_attack_bonus = 20
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_is_a_ranged_spell_attack_with_scaled_damage(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'action')
        self.assertEqual(capability.targeting.range_ft, 90)
        self.assertEqual(capability.effect.on_hit[0].base_dice_count, 4)

    def test_hit_deals_initial_damage(self) -> None:
        session = self._setup_session()
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 melf-s-acid-arrow monster-mage-1')
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, start_hp)

    def test_delayed_damage_resolves_at_the_end_of_the_targets_next_turn(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 melf-s-acid-arrow monster-mage-1')
        after_hit_hp = session.state.actors['monster-mage-1'].current_hit_points
        self.advance_existing_turn(session, 'monster-mage-1')
        self.end_turn_and_resolve(session, 'monster-mage-1')
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, after_hit_hp)

    def test_miss_only_deals_the_halved_initial_damage(self) -> None:
        session = self._setup_session()
        session.state.actors['player-1'].spell_attack_bonus = -20
        start_hp = session.state.actors['monster-mage-1'].current_hit_points
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 melf-s-acid-arrow monster-mage-1')
        damage_events = [event for event in session.state.event_log if isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-mage-1']
        self.assertEqual(len(damage_events), 1)
        self.assertLess(session.state.actors['monster-mage-1'].current_hit_points, start_hp)

    def test_higher_slot_scales_the_initial_damage(self) -> None:
        base = self._setup_session()
        start_base = base.state.actors['monster-mage-1'].current_hit_points
        base.state, _ = base.command_interface.execute(base.state, '/cast player-1 melf-s-acid-arrow monster-mage-1 --slot-level 2')
        base_damage = start_base - base.state.actors['monster-mage-1'].current_hit_points

        scaled = self._setup_session()
        start_scaled = scaled.state.actors['monster-mage-1'].current_hit_points
        scaled.state, _ = scaled.command_interface.execute(scaled.state, '/cast player-1 melf-s-acid-arrow monster-mage-1 --slot-level 4')
        scaled_damage = start_scaled - scaled.state.actors['monster-mage-1'].current_hit_points
        self.assertGreaterEqual(scaled_damage, base_damage)


if __name__ == '__main__':
    unittest.main()
