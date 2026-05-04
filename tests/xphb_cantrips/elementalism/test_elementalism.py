from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase, adjudication_success_payload, spell_reaction_ignore_payload


class ElementalismCantripTests(StoryCantripTestCase):
    def test_story_mode_rejects_invalid_effect_choice(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Elementalism')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 elementalism --effect wrong --description Light the lantern')

    def test_declaration_includes_exact_local_constraints(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Elementalism')
        intent = session._story_mode_cast_intent('/cast player-1 elementalism --effect beckon-fire --description Light the lantern with harmless embers')
        declaration = session._story_spell_adjudication_declaration(session.state.actors['player-1'].spells['elementalism'], intent)
        self.assertIn('Requested spell option: beckon-fire', declaration)
        self.assertIn('Choose exactly one listed Elementalism option each casting.', declaration)
        self.assertIn('Beckon Water creates only one cup of clean water', declaration)

    def test_story_resolution_runs_through_adjudication(self) -> None:
        session, transport = self.build_story_session([
            adjudication_success_payload(action_summary='Use Elementalism to light the lantern.', public_text='Harmless embers flare and catch in the lantern wick.'),
            spell_reaction_ignore_payload(public_narration='The brief elemental display earns only a passing glance.'),
        ])
        self.grant_spell(session, 'Elementalism')
        session.execute_for_controller('player-1-controller', '/cast player-1 elementalism --effect beckon-fire --description Light the lantern with harmless embers')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('lantern wick', '\n'.join(entry.text for entry in session.story_state.transcript_entries))


if __name__ == '__main__':
    unittest.main()
