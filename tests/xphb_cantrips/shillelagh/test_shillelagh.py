from __future__ import annotations

import unittest

from tests.xphb_cantrips.support import EncounterCantripTestCase


class ShillelaghCantripTests(EncounterCantripTestCase):
    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, 'Shillelagh')
        session.state.actors['player-1'].character_record.weapon_proficiencies = ('simple weapons',)
        session.state, _ = session.command_interface.execute(session.state, '/equip player-1 quarterstaff main-hand')
        return session

    def test_cast_enchants_a_held_quarterstaff_with_force_damage(self) -> None:
        session = self._setup_session()
        actor = session.state.actors['player-1']
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 shillelagh --item quarterstaff --damage-type force')
        attack = actor.attacks['quarterstaff-melee-str']
        self.assertEqual(attack.damage_die_faces, 8)
        self.assertEqual(attack.damage_type, 'force')
        self.assertEqual(attack.to_hit_bonus, actor.proficiency_bonus + actor.ability_modifiers[actor.spellcasting_ability])
        self.assertEqual(attack.damage_bonus, actor.ability_modifiers[actor.spellcasting_ability])

    def test_default_damage_type_stays_bludgeoning_without_override(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 shillelagh --item quarterstaff')
        attack = session.state.actors['player-1'].attacks['quarterstaff-melee-str']
        self.assertEqual(attack.damage_type, 'bludgeoning')
        self.assertEqual(attack.damage_die_faces, 8)

    def test_dropping_the_enchanted_weapon_ends_the_effect(self) -> None:
        session = self._setup_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 shillelagh --item quarterstaff --damage-type force')
        self.assertTrue(any(effect.name == 'Shillelagh' for effect in session.state.active_effects.values()))
        session.state, _ = session.command_interface.execute(session.state, '/interact player-1 drop quarterstaff')
        self.assertFalse(any(effect.name == 'Shillelagh' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
