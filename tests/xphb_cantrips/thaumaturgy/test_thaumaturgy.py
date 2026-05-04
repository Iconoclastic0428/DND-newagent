from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase, adjudication_success_payload, spell_reaction_ignore_payload


class ThaumaturgyCantripTests(StoryCantripTestCase):
    def test_story_mode_requires_a_listed_effect(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Thaumaturgy')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 thaumaturgy --description Boom my voice through the tavern')

    def test_declaration_includes_exact_local_constraints(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Thaumaturgy')
        intent = session._story_mode_cast_intent('/cast player-1 thaumaturgy --effect booming-voice --description Boom my voice through the tavern')
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells['thaumaturgy'], intent)
        self.assertIn('Requested spell option: booming-voice', declaration)
        self.assertIn('You can sustain at most three different 1-minute Thaumaturgy effects', declaration)
        self.assertIn('Booming Voice affects Intimidation checks only', declaration)

    def test_story_resolution_runs_through_adjudication(self) -> None:
        session, transport = self.build_story_session([
            adjudication_success_payload(action_summary='Use Thaumaturgy to boom a warning.', public_text='Your voice rolls through the room like a temple bell.'),
            spell_reaction_ignore_payload(public_narration='The room startles, then settles when no harm follows.'),
        ])
        self.grant_spell(session, 'Thaumaturgy')
        session.execute_for_controller('player-1-controller', '/cast player-1 thaumaturgy --effect booming-voice --description Boom my voice through the tavern')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('temple bell', '\n'.join(entry.text for entry in session.story_state.transcript_entries))


if __name__ == '__main__':
    unittest.main()
