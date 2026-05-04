from __future__ import annotations

import unittest

from shared_types.conditions import ConditionType
from shared_types.encounter_events import GroundItemCreatedEvent
from shared_types.encounter_models import GridPosition
from shared_types.models import Ability, slugify
from tests.xphb_cantrips.support import EncounterCantripTestCase, grant_item_by_catalog_match



class CommandLevel1SpellTests(EncounterCantripTestCase):
    SPELL_NAME = 'Command'
    SPELL_SLUG = 'command'

    def _advance_existing_turn(self, session, actor_id: str) -> None:
        guard = 0
        while session.state.active_actor_id != actor_id:
            guard += 1
            if guard > 30:
                raise AssertionError(f'Could not advance to actor {actor_id}.')
            session.state, _ = session.command_interface.execute(session.state, f'/endturn {session.state.active_actor_id}')

    def _command(self, word: str, target_id: str = 'monster-skeleton-1') -> str:
        return f'/cast player-1 command {target_id} --word {word}'

    def _resolve_command_word(self, session, word: str, *, target_id: str = 'monster-skeleton-1') -> None:
        actor = session.state.actors['player-1']
        spell = actor.spells[slugify(self.SPELL_NAME)]
        command_effect = spell.capability.effect.on_failure[0]
        events: list[object] = []
        session.command_interface.kernel.effect_executor._apply_command_word(
            session.state,
            events,
            source_actor_id=actor.actor_id,
            capability=spell.capability,
            target_ids=(target_id,),
            point=None,
            effect=command_effect,
            parameters={'word': word},
        )

    def _setup_session(self, *, target_position: GridPosition = GridPosition(10, 0, 0), caster_dc: int = 99, target_save_bonus: int = -50):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = target_position
        session.state.actors['monster-mage-1'].position = GridPosition(12, 0, 0)
        session.state.actors['player-1'].spell_save_dc = caster_dc
        session.state.actors['monster-skeleton-1'].saving_throw_bonuses[Ability.WIS] = target_save_bonus
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self._advance_existing_turn(session, 'player-1')
        return session

    def test_command_shape_uses_the_word_parameter(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        intent = session.command_interface.parse_command(self._command('halt'))
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual(intent.target_id, 'monster-skeleton-1')
        self.assertEqual(tuple((param.key, param.value) for param in intent.parameters), (('word', 'halt'),))

    def test_command_capability_exposes_all_legal_words(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        spell = session.state.actors['player-1'].spells[slugify(self.SPELL_NAME)]
        command_effect = spell.capability.effect.on_failure[0]
        self.assertEqual(command_effect.allowed_commands, ('approach', 'drop', 'flee', 'grovel', 'halt'))

    def test_failed_save_halt_consumes_the_targets_action_bonus_action_and_movement(self) -> None:
        session = self._setup_session()
        self._resolve_command_word(session, 'halt')
        self._advance_existing_turn(session, 'monster-skeleton-1')
        target = session.state.actors['monster-skeleton-1']
        self.assertFalse(target.action_available)
        self.assertFalse(target.bonus_action_available)
        self.assertEqual(target.remaining_movement_ft, 0)

    def test_failed_save_grovel_applies_prone_before_the_targets_turn_actions(self) -> None:
        session = self._setup_session()
        self._resolve_command_word(session, 'grovel')
        self._advance_existing_turn(session, 'monster-skeleton-1')
        self.assertTrue(any(instance.condition_type == ConditionType.PRONE for instance in session.state.actors['monster-skeleton-1'].condition_instances))

    def test_failed_save_drop_releases_held_items_and_creates_a_ground_item(self) -> None:
        session = self._setup_session()
        item_id = grant_item_by_catalog_match(session, 'monster-skeleton-1', name_substrings=('shortsword',))
        target = session.state.actors['monster-skeleton-1']
        target.held_item_ids = (item_id,)
        target.main_hand_item_id = item_id
        self._resolve_command_word(session, 'drop')
        self._advance_existing_turn(session, 'monster-skeleton-1')
        self.assertNotIn(item_id, session.state.actors['monster-skeleton-1'].held_item_ids)
        self.assertEqual(session.state.actors['monster-skeleton-1'].carried_item_counts.get(item_id, 0), 0)
        self.assertTrue(any(isinstance(event, GroundItemCreatedEvent) and event.item_id == item_id for event in session.state.event_log))

    def test_failed_save_approach_moves_the_target_closer_to_the_caster(self) -> None:
        session = self._setup_session(target_position=GridPosition(12, 0, 0))
        start_position = session.state.actors['monster-skeleton-1'].position
        self._resolve_command_word(session, 'approach')
        self._advance_existing_turn(session, 'monster-skeleton-1')
        self.assertLess(session.state.actors['monster-skeleton-1'].position.x, start_position.x)

    def test_failed_save_flee_moves_the_target_farther_from_the_caster(self) -> None:
        session = self._setup_session(target_position=GridPosition(5, 0, 0))
        start_position = session.state.actors['monster-skeleton-1'].position
        self._resolve_command_word(session, 'flee')
        self._advance_existing_turn(session, 'monster-skeleton-1')
        self.assertGreater(session.state.actors['monster-skeleton-1'].position.x, start_position.x)


if __name__ == '__main__':
    unittest.main()

