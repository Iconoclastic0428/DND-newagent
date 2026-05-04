from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class BlessLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Bless'
    SPELL_SLUG = 'bless'

    def _command(self, *, material: str) -> str:
        return f'/cast player-1 bless player-1 --target monster-skeleton-1 --target monster-mage-1 --material {material}'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        material_id = self.grant_material_item(session, required_tags=('focus-holy',), min_cost_cp=500)
        session._bless_material_id = material_id
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(2, 0, 0)
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_three_supported_targets(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        material_id = self.grant_material_item(session, required_tags=('focus-holy',), min_cost_cp=500)
        session._bless_material_id = material_id
        intent = session.command_interface.parse_command('/cast player-1 bless player-1 --target monster-skeleton-1 --target monster-mage-1 --material holy-symbol')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')
        self.assertEqual(tuple((param.key, param.value) for param in intent.parameters), (('target', 'monster-skeleton-1'), ('target', 'monster-mage-1'), ('material', 'holy-symbol')))

    def test_cast_applies_the_active_effect_to_all_targets(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._bless_material_id))
        self.assertTrue(any(effect.name == 'Bless' for effect in session.state.active_effects.values()))
        for target_id in ('player-1', 'monster-skeleton-1', 'monster-mage-1'):
            self.assertTrue(any(effect.name == 'Bless' and target_id in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_bless_grants_a_positive_attack_roll_bonus_on_the_target(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._bless_material_id))
        target = session.state.actors['monster-skeleton-1']
        modifier, events = session.command_interface.kernel._attack_roll_effect_modifier(session.state, actor_id=target.actor_id)
        self.assertGreater(modifier, 0)
        self.assertTrue(events)

    def test_bless_grants_a_positive_saving_throw_bonus_on_the_target(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._bless_material_id))
        target = session.state.actors['monster-mage-1']
        modifier, events = session.command_interface.kernel._saving_throw_effect_modifier(session.state, actor_id=target.actor_id)
        self.assertGreater(modifier, 0)
        self.assertTrue(events)

    def test_effect_persists_through_a_turn_cycle(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._bless_material_id))
        session.state, _ = session.command_interface.execute(session.state, '/endturn player-1')
        self.advance_existing_turn(session, 'player-1')
        self.assertTrue(any(effect.name == 'Bless' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
