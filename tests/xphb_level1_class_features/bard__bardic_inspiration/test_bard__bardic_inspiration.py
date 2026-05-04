from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
import unittest

from player_interface import EncounterSlashCommandInterface
from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from tests.xphb_level1_class_features.support import Level1ClassFeatureTestCase


class BardBardicInspirationFeatureTests(Level1ClassFeatureTestCase):
    def _session(self):
        runtime = self.build_runtime()
        bard_record = self.complete_record('bard', assign_command='/create ability assign 10 14 13 12 8 15')
        ally_record = self.complete_record('fighter')
        monster_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(
                CharacterPlacement(actor_id='player-1', record=bard_record, position=GridPosition(0, 0, 0)),
                CharacterPlacement(actor_id='ally-1', record=ally_record, position=GridPosition(1, 0, 0)),
            ),
            monsters=(MonsterPlacement(actor_id='monster-1', monster_id=monster_id, position=GridPosition(2, 0, 0)),),
        )
        return SimpleNamespace(runtime_services=runtime, command_interface=EncounterSlashCommandInterface(runtime.kernel), state=state)

    def test_feature_name_and_capability_compile(self) -> None:
        record = self.complete_record('bard', assign_command='/create ability assign 10 14 13 12 8 15')
        actor = self.compile_actor(record)
        self.assertIn('Bardic Inspiration', record.class_feature_names)
        self.assertIn('bardic-inspiration', actor.capabilities)

    def test_bardic_inspiration_targets_an_ally_and_starts_an_effect(self) -> None:
        session = self._session()
        self.advance_to_actor(session, 'player-1')
        uses_before = session.state.actors['player-1'].capabilities['bardic-inspiration'].remaining_uses
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 bardic-inspiration ally-1')
        self.assertEqual(session.state.actors['player-1'].capabilities['bardic-inspiration'].remaining_uses, uses_before - 1)
        self.assertFalse(session.state.actors['player-1'].bonus_action_available)
        started = self.events_since(session, start_index, ActiveEffectStartedEvent)
        self.assertTrue(started)
        self.assertEqual(started[-1].effect.target_actor_ids, ('ally-1',))

    def test_the_next_d20_test_consumes_the_bardic_inspiration_effect(self) -> None:
        session = self._session()
        self.advance_to_actor(session, 'player-1')
        session.state, _ = session.command_interface.execute(session.state, '/feature player-1 bardic-inspiration ally-1')
        self.end_turn_and_resolve(session, 'player-1')
        self.advance_existing_turn(session, 'ally-1')
        session.state.actors['ally-1'].attacks['unarmed-strike'] = replace(session.state.actors['ally-1'].attacks['unarmed-strike'], to_hit_bonus=99)
        start_index = len(session.state.event_log)
        session.state, _ = session.command_interface.execute(session.state, '/attack ally-1 unarmed-strike monster-1')
        ended = self.events_since(session, start_index, ActiveEffectEndedEvent)
        self.assertTrue(any(event.reason == 'd20-test-consumed' for event in ended))


if __name__ == '__main__':
    unittest.main()
