from __future__ import annotations

from pathlib import Path
import shutil
import sys
import unittest
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from story_demo_system_server import build_full_story_demo_manual_session
from shared_types.encounter_models import ActorSide, EncounterPhase
from shared_types.errors import EncounterPermissionError
from shared_types.storytelling import RuntimeMode


class QueueTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict] = []

    def _next_payload(self) -> dict:
        if not self.payloads:
            raise AssertionError('No queued LLM payloads remain for this test.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return [{'type': 'response.completed', 'response': self._next_payload()}]


class FullStoryDemoSessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.full-story-demo-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )
        self.base_url = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _build_session(self):
        return build_full_story_demo_manual_session(
            base_url=self.base_url,
            env_path=self.env_path,
            client_transport=QueueTransport([]),
        )

    def _confirm_default_character(self, session, controller_id: str) -> None:
        commands = (
            '/create begin',
            '/create choose species aasimar',
            '/create choose class wizard',
            '/create choose class-skills Arcana History',
            '/create choose background acolyte',
            '/create choose choice class:wizard:cantrips fire-bolt mage-hand light',
            '/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance',
            '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds',
            '/create ability generate point-buy 15 14 13 12 10 8',
            '/create ability assign 8 14 13 15 12 10',
            '/create background-asi choose acolyte-int2-wis1',
            '/create equipment background gold',
            '/create equipment class package wizard-package-1',
            '/create confirm',
        )
        for command in commands:
            session.handle_input(controller_id, command)

    def test_demo_starts_in_character_creation(self) -> None:
        session = self._build_session()
        player_view = session.view_for_controller('player-1-controller')
        dm_view = session.view_for_controller('dm')
        self.assertIn('Runtime mode: character-creation', player_view.summary_lines)
        self.assertIn('Demo phase: create your character', player_view.summary_lines)
        self.assertIn('Phase: not-started', player_view.summary_lines)
        self.assertIn('Demo phase: waiting for four player characters', dm_view.summary_lines)
        self.assertIsNone(session.story_session)

    def test_demo_hands_off_to_story_after_all_four_players_confirm(self) -> None:
        session = self._build_session()
        for controller_id in ('player-1-controller', 'player-2-controller', 'player-3-controller', 'player-4-controller'):
            self._confirm_default_character(session, controller_id)
        self.assertIsNotNone(session.story_session)
        self.assertEqual(session.story_session.story_state.runtime_mode, RuntimeMode.STORYTELLING)
        self.assertEqual(session.story_session.story_state.current_scene_id, 'scene-waterdeep-gundren-briefing')
        player_view = session.view_for_controller('player-1-controller')
        text = '\n'.join(player_view.summary_lines)
        self.assertIn('Runtime mode: storytelling', text)
        self.assertIn('Current scene: scene-waterdeep-gundren-briefing', text)
        self.assertIn('A stout dwarf with dust still caught in his beard', text)

    def test_demo_ends_when_ambush_combat_resolves(self) -> None:
        session = self._build_session()
        for controller_id in ('player-1-controller', 'player-2-controller', 'player-3-controller', 'player-4-controller'):
            self._confirm_default_character(session, controller_id)
        assert session.story_session is not None
        session.story_session.story_state.runtime_mode = RuntimeMode.COMBAT
        session.story_session.state.phase = EncounterPhase.COMPLETE
        session.story_session.state.winning_side = ActorSide.PLAYER
        view = session.view_for_controller('player-2-controller')
        text = '\n'.join(view.summary_lines)
        self.assertIn('Runtime mode: demo-complete', text)
        self.assertIn('The party survived the goblin ambush.', text)
        self.assertEqual(view.available_choices, {})
        status_view = session.handle_input('player-2-controller', '/view')
        self.assertIn('Runtime mode: demo-complete', '\n'.join(status_view.summary_lines))
        with self.assertRaises(EncounterPermissionError):
            session.handle_input('player-2-controller', 'We head into the woods.')


if __name__ == '__main__':
    unittest.main()
