from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.encounter_events import HitPointDieSpentEvent
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, build_local_spell_capability, inject_local_spell


ROOT = Path(__file__).resolve().parents[6]
ITEM_ROOT = ROOT / 'content' / 'xphb' / 'spells' / 'level-2' / 'arcane-vigor'


class ArcaneVigorTests(EncounterLevel2SpellTestCase):
    SPELL_NAME = 'Arcane Vigor'
    SPELL_SLUG = 'arcane-vigor'

    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        player = session.state.actors['player-1']
        player.current_hit_points = max(1, player.current_hit_points - 8)
        player.remaining_hit_dice = 3
        player.total_hit_dice = max(player.total_hit_dice, 3)
        player.spellcasting_ability = player.spellcasting_ability or next(iter(player.ability_modifiers))
        return session

    def test_definition_and_registry_mark_the_spell_deterministic(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        registry = json.loads((ITEM_ROOT / 'registry.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], self.SPELL_NAME)
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertEqual(registry['runtime_support_mode'], 'deterministic-capability')

    def test_capability_uses_bonus_action_and_hit_dice_scaling(self) -> None:
        capability = build_local_spell_capability(self.SPELL_SLUG, name=self.SPELL_NAME)
        self.assertEqual(capability.action_cost, 'bonus')
        self.assertEqual(capability.effect.minimum_count, 1)
        self.assertEqual(capability.effect.maximum_count, 2)
        self.assertEqual(capability.effect.bonus_maximum_count_per_slot_level, 1)

    def test_cast_requires_count_parameter(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 arcane-vigor')

    def test_cast_spends_requested_hit_dice_and_heals(self) -> None:
        session = self._setup_session()
        player = session.state.actors['player-1']
        starting_hp = player.current_hit_points
        starting_dice = player.remaining_hit_dice
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 arcane-vigor --count 2')
        self.assertEqual(session.state.actors['player-1'].remaining_hit_dice, starting_dice - 2)
        self.assertGreater(session.state.actors['player-1'].current_hit_points, starting_hp)
        self.assertEqual(len([event for event in session.state.event_log if isinstance(event, HitPointDieSpentEvent)]), 2)

    def test_higher_slot_allows_more_hit_dice(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 arcane-vigor --count 3 --slot-level 3')
        self.assertEqual(len([event for event in session.state.event_log if isinstance(event, HitPointDieSpentEvent)]), 3)

    def test_base_slot_rejects_more_than_two_hit_dice(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 arcane-vigor --count 3')

    def test_cast_is_rejected_at_maximum_hit_points(self) -> None:
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug=self.SPELL_SLUG, name=self.SPELL_NAME)
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].remaining_hit_dice = 3
        session.state.actors['player-1'].total_hit_dice = max(session.state.actors['player-1'].total_hit_dice, 3)
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 arcane-vigor --count 1')


if __name__ == '__main__':
    unittest.main()