from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase, adjudication_success_payload, spell_reaction_ignore_payload


class PrestidigitationCantripTests(StoryCantripTestCase):
    def test_story_mode_requires_a_listed_effect(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Prestidigitation')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 prestidigitation --description Clean the map case')

    def test_declaration_includes_exact_local_constraints(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Prestidigitation')
        intent = session._story_mode_cast_intent("/cast player-1 prestidigitation --effect clean-or-soil --description Clean the mud from Gundren's map case")
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells['prestidigitation'], intent)
        self.assertIn('Requested spell option: clean-or-soil', declaration)
        self.assertIn('You can sustain at most three non-instantaneous Prestidigitation effects', declaration)
        self.assertIn('Minor Creation must fit in your hand', declaration)

    def test_story_resolution_runs_through_adjudication(self) -> None:
        session, transport = self.build_story_session([
            adjudication_success_payload(action_summary='Use Prestidigitation to clean the map case.', public_text='The mud lifts away from the case in a quick magical flourish.'),
            spell_reaction_ignore_payload(public_narration='The harmless trick earns only a grunt from Gundren.'),
        ])
        self.grant_spell(session, 'Prestidigitation')
        session.execute_for_controller('player-1-controller', "/cast player-1 prestidigitation --effect clean-or-soil --description Clean the mud from Gundren's map case")
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('mud lifts away', '\n'.join(entry.text for entry in session.story_state.transcript_entries))


if __name__ == '__main__':
    unittest.main()
