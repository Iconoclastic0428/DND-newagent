from __future__ import annotations

import unittest

from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import StoryCantripTestCase


class MessageCantripTests(StoryCantripTestCase):
    def test_story_mode_requires_message_text(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Message')
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/cast player-1 message player-2')

    def test_message_creates_private_whisper_and_reply_without_llm(self) -> None:
        session, transport = self.build_story_session([])
        self.grant_spell(session, 'Message')
        session.execute_for_controller('player-1-controller', '/cast player-1 message player-2 --message Keep Gundren talking --reply I can do that')
        entries = session.story_state.transcript_entries[-2:]
        self.assertEqual(entries[0].speaker, 'Player 1 (Message)')
        self.assertIn('Keep Gundren talking', entries[0].text)
        self.assertEqual(entries[1].speaker, 'Player 2 (Reply)')
        self.assertEqual(len(transport.requests), 0)

    def test_message_visibility_is_limited_to_caster_target_and_dm(self) -> None:
        session, _transport = self.build_story_session([])
        self.grant_spell(session, 'Message')
        session.execute_for_controller('player-1-controller', '/cast player-1 message player-2 --message Check the back door')
        player_two_view = '\n'.join(session.view_for_controller('player-2-controller').summary_lines)
        player_three_view = '\n'.join(session.view_for_controller('player-3-controller').summary_lines)
        self.assertIn('Check the back door', player_two_view)
        self.assertNotIn('Check the back door', player_three_view)


if __name__ == '__main__':
    unittest.main()
