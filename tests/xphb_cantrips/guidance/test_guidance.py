from __future__ import annotations

import unittest

from session_server.bootstrap import build_default_encounter_session
from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.encounter_events import EffectRollAppliedEvent
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class GuidanceCantripTests(unittest.TestCase):
    def _build_session(self):
        return build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def test_guidance_applies_chosen_skill_bonus_to_matching_check(self) -> None:
        session = self._build_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 guidance player-1 --skill Arcana')
        request = CheckRequest(
            context=ResolutionContext(effect_id='test-guidance', source_actor_id='player-1', target_actor_id='player-1', reason='Arcana check'),
            ability=Ability.INT,
            dc=10,
            skill_name='Arcana',
        )
        _, events = session.command_interface.kernel.resolve_check_consumer(session.state, request, apply=True)
        self.assertTrue(any(isinstance(event, EffectRollAppliedEvent) and event.reason == 'ability-check-bonus:Arcana' for event in events))

    def test_guidance_does_not_apply_to_a_different_skill(self) -> None:
        session = self._build_session()
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 guidance player-1 --skill Arcana')
        request = CheckRequest(
            context=ResolutionContext(effect_id='test-guidance', source_actor_id='player-1', target_actor_id='player-1', reason='History check'),
            ability=Ability.INT,
            dc=10,
            skill_name='History',
        )
        _, events = session.command_interface.kernel.resolve_check_consumer(session.state, request, apply=True)
        self.assertFalse(any(isinstance(event, EffectRollAppliedEvent) and event.reason == 'ability-check-bonus:History' for event in events))

    def test_guidance_rejects_invalid_skill_parameter(self) -> None:
        session = self._build_session()
        with self.assertRaises(EncounterValidationError):
            session.command_interface.execute(session.state, '/cast player-1 guidance player-1 --skill Flying')


if __name__ == '__main__':
    unittest.main()
