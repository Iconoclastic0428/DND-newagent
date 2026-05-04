from __future__ import annotations

import unittest

from shared_types.encounter_events import AttackMissedEvent, DamageAppliedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class SanctuaryLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Sanctuary'
    SPELL_SLUG = 'sanctuary'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        self.grant_spell(session, 'Magic Missile')
        session.state.actors['player-1'].spells.pop('shield', None)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(1, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(3, 0, 0)
        return session

    def _monster_attack(self, session):
        self.advance_to_actor(session, 'monster-skeleton-1')
        attack_id = next(attack_id for attack_id in session.state.actors['monster-skeleton-1'].attacks if attack_id != 'unarmed-strike')
        session.state, _ = session.command_interface.execute(session.state, f'/attack monster-skeleton-1 {attack_id} player-1')
        if session.state.pending_timing_queue is not None:
            self.resolve_pending_timing(session, actor_id='player-1')

    def _monster_spell(self, session):
        self.advance_to_actor(session, 'monster-mage-1')
        spell_id = 'magic-missile' if 'magic-missile' in session.state.actors['monster-mage-1'].spells else next(iter(session.state.actors['monster-mage-1'].spells))
        session.state, _ = session.command_interface.execute(session.state, f'/cast monster-mage-1 {spell_id} player-1')

    def test_command_shape_supports_creature_target(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command('/cast player-1 sanctuary player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'player-1')

    def test_cast_creates_ward_on_target(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='player-1')
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Sanctuary')
        self.assertEqual(effect.target_actor_ids, ('player-1',))
        self.assertEqual(effect.definition.incoming_hostile_targeting_save_ability.value, 'WIS')

    def test_failed_hostile_save_causes_attack_to_fail_before_damage(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='player-1')
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = -20
        self._monster_attack(session)
        self.assertTrue(any(isinstance(event, AttackMissedEvent) for event in session.state.event_log))
        self.assertFalse(any(isinstance(event, DamageAppliedEvent) and event.target_id == 'player-1' for event in session.state.event_log))

    def test_successful_hostile_save_allows_attack_to_continue(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='player-1')
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = 99
        session.state.actors['player-1'].armor_class = -100
        self._monster_attack(session)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) and event.target_id == 'player-1' for event in session.state.event_log))

    def test_failed_hostile_save_can_stop_targeted_spell(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='player-1')
        session.state.actors['monster-mage-1'].saving_throw_bonuses[Ability.WIS] = -20
        self._monster_spell(session)
        self.assertFalse(any(isinstance(event, DamageAppliedEvent) and event.target_id == 'player-1' for event in session.state.event_log))

    def test_harmful_spell_from_protected_target_ends_ward(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, target_id='player-1')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 magic-missile monster-skeleton-1')
        self.assertFalse(any(effect.name == 'Sanctuary' for effect in session.state.active_effects.values()))


if __name__ == '__main__':
    unittest.main()
