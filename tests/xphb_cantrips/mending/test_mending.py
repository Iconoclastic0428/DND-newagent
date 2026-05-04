from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase, adjudication_success_payload, spell_reaction_ignore_payload


class MendingCantripTests(StoryCantripTestCase):
    def test_story_mode_requires_a_description(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Mending')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 mending')

    def test_declaration_includes_exact_local_constraints(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Mending')
        intent = session._story_mode_cast_intent('/cast player-1 mending --description Repair the torn wagon harness')
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells['mending'], intent)
        self.assertIn('Casting time 1 minute and range Touch.', declaration)
        self.assertIn('damaged area is no larger than 1 foot', declaration)
        self.assertIn('does not restore lost magic', declaration)

    def test_story_resolution_runs_through_adjudication(self) -> None:
        session, transport = self.build_story_session([
            adjudication_success_payload(action_summary='Use Mending to repair the harness.', public_text='The torn harness fibers knit back together under the cantrip.'),
            spell_reaction_ignore_payload(public_narration='The simple repair draws no objection.'),
        ])
        self.grant_spell(session, 'Mending')
        session.execute_for_controller('player-1-controller', '/cast player-1 mending --description Repair the torn wagon harness')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('harness fibers knit back together', '\n'.join(entry.text for entry in session.story_state.transcript_entries))


if __name__ == '__main__':
    unittest.main()
