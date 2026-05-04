from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase, adjudication_success_payload, spell_reaction_ignore_payload


class DruidcraftCantripTests(StoryCantripTestCase):
    def test_story_mode_requires_a_listed_effect(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Druidcraft')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 druidcraft --description Predict tomorrow rain')

    def test_declaration_includes_exact_local_constraints(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Druidcraft')
        intent = session._story_mode_cast_intent('/cast player-1 druidcraft --effect weather-sensor --description Predict tomorrow rain over the road')
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells['druidcraft'], intent)
        self.assertIn('Requested spell option: weather-sensor', declaration)
        self.assertIn('Choose exactly one listed Druidcraft option each casting.', declaration)
        self.assertIn('The weather-sensor token lasts 1 round', declaration)

    def test_story_resolution_runs_through_adjudication(self) -> None:
        session, transport = self.build_story_session([
            adjudication_success_payload(action_summary='Use Druidcraft to predict the road weather.', public_text='A tiny natural omen sketches the coming rain in the air.'),
            spell_reaction_ignore_payload(public_narration='Gundren notices the omen and keeps talking.'),
        ])
        self.grant_spell(session, 'Druidcraft')
        session.execute_for_controller('player-1-controller', '/cast player-1 druidcraft --effect weather-sensor --description Predict tomorrow rain over the road')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('tiny natural omen', '\n'.join(entry.text for entry in session.story_state.transcript_entries))


if __name__ == '__main__':
    unittest.main()
