
from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_models import AttackKind
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class ProtectionFromEvilAndGoodLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Protection from Evil and Good'
    SPELL_SLUG = 'protection-from-evil-and-good'

    def _command(self, *, material: str) -> str:
        return f'/cast player-1 protection-from-evil-and-good player-1 --material {material}'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        material_id = self.grant_material_item(session, name_substrings=('holy water',), min_cost_cp=2500)
        session._protection_material_id = material_id
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_the_supported_self_target_syntax(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 protection-from-evil-and-good player-1 --material holy-water')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')
        self.assertEqual(tuple((param.key, param.value) for param in intent.parameters), (('material', 'holy-water'),))

    def test_cast_creates_the_active_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._protection_material_id))
        self.assertTrue(any(effect.name == 'Protection from Evil and Good' and 'player-1' in effect.target_actor_ids for effect in session.state.active_effects.values()))

    def test_effect_definition_tracks_the_expected_condition_protections(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._protection_material_id))
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Protection from Evil and Good')
        self.assertIn(ConditionType.CHARMED, effect.definition.protected_condition_types)
        self.assertIn(ConditionType.FRIGHTENED, effect.definition.protected_condition_types)

    def test_undead_attackers_disadvantage_against_the_protected_target(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._protection_material_id))
        modifiers = session.command_interface.kernel._attack_modifier_state(
            session.state,
            session.state.actors['monster-skeleton-1'],
            session.state.actors['player-1'],
            distance_ft=5,
            long_range_disadvantage=False,
        )
        self.assertTrue(modifiers['disadvantage'])

    def test_humanoid_attackers_do_not_gain_the_protection_penalty(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, self._command(material=session._protection_material_id))
        modifiers = session.command_interface.kernel._attack_modifier_state(
            session.state,
            session.state.actors['monster-mage-1'],
            session.state.actors['player-1'],
            distance_ft=5,
            long_range_disadvantage=False,
        )
        self.assertFalse(modifiers['disadvantage'])


if __name__ == '__main__':
    unittest.main()
