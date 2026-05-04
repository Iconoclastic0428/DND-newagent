from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.encounter_models import ActorSide, GridPosition
from shared_types.models import Ability
from tests.xphb_level2_spells.support import EncounterLevel2SpellTestCase, inject_local_spell


ITEM_ROOT = Path(__file__).resolve().parents[1]


class EnhanceAbilityTests(EncounterLevel2SpellTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        inject_local_spell(session, actor_id='player-1', slug='enhance-ability', name='Enhance Ability')
        self.advance_to_actor(session, 'player-1')
        session.state.actors['player-1'].position = GridPosition(1, 1, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 1, 0)
        session.state.actors['monster-mage-1'].side = ActorSide.PLAYER
        return session

    def test_definition_metadata_documents_multi_target_cast_shape(self) -> None:
        definition = json.loads((ITEM_ROOT / 'definition.json').read_text(encoding='utf-8'))
        self.assertEqual(definition['display_name'], 'Enhance Ability')
        self.assertEqual(definition['runtime_status'], 'deterministic-capability')
        self.assertIn('--target-abilities', definition['cast_syntax'])

    def test_single_target_cast_requires_ability_choice(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 enhance-ability player-1')

    def test_single_target_cast_applies_chosen_ability_advantage(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 enhance-ability player-1 --ability STR')
        self.assertIn(Ability.STR, session.state.actors['player-1'].ability_check_advantage_abilities)
        self.assertNotIn(Ability.DEX, session.state.actors['player-1'].ability_check_advantage_abilities)

    def test_single_target_cast_accepts_case_insensitive_ability_names(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 enhance-ability player-1 --ability wisdom')
        self.assertIn(Ability.WIS, session.state.actors['player-1'].ability_check_advantage_abilities)

    def test_low_slot_rejects_multiple_targets(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 enhance-ability --targets player-1,monster-mage-1 --target-abilities player-1:STR,monster-mage-1:DEX --slot-level 2')

    def test_multi_target_cast_requires_target_ability_mappings(self) -> None:
        session = self._setup_session()
        with self.assertRaises(Exception):
            session.command_interface.execute(session.state, '/cast player-1 enhance-ability --targets player-1,monster-mage-1 --slot-level 3')

    def test_multi_target_cast_applies_distinct_abilities_per_target(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 enhance-ability --targets player-1,monster-mage-1 --target-abilities player-1:STR,monster-mage-1:DEX --slot-level 3')
        self.assertIn(Ability.STR, session.state.actors['player-1'].ability_check_advantage_abilities)
        self.assertNotIn(Ability.DEX, session.state.actors['player-1'].ability_check_advantage_abilities)
        self.assertIn(Ability.DEX, session.state.actors['monster-mage-1'].ability_check_advantage_abilities)
        self.assertNotIn(Ability.STR, session.state.actors['monster-mage-1'].ability_check_advantage_abilities)
        self.assertEqual(len(session.state.active_effects), 1)
        self.assertIsNotNone(session.state.actors['player-1'].concentrating_effect_id)


if __name__ == '__main__':
    unittest.main()
