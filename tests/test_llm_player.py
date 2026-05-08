from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
import unittest

from dm_agent.client import LLMClient
from dm_agent.config import LLMConfig
from session_server.llm_player import LLMPlayerAgent
from shared_types.storytelling import RuntimeMode, StoryRuntimeState, StoryTranscriptEntry, StoryTranscriptVisibility


class QueueTransport:
    def __init__(self, *texts: str) -> None:
        self.texts = list(texts)
        self.payloads = []

    def post(self, *, url, headers, payload):
        del url, headers
        self.payloads.append(payload)
        text = self.texts.pop(0)
        return {'output_text': text}

    def stream(self, *, url, headers, payload):
        del url, headers
        self.payloads.append(payload)
        text = self.texts.pop(0)
        return [{'type': 'response.completed', 'response': {'output_text': text}}]


@dataclass
class FakeRuntime:
    owners: dict[str, str]

    def controller_for_actor(self, actor_id: str) -> str:
        return self.owners[actor_id]


@dataclass
class FakeSession:
    story_state: StoryRuntimeState = field(
        default_factory=lambda: StoryRuntimeState(
            campaign_id='lmop',
            current_chapter_id='chapter-1',
            current_scene_id='scene-1',
            canonical_location_id='waterdeep',
            runtime_mode=RuntimeMode.STORYTELLING,
            transcript_entries=(
                StoryTranscriptEntry(
                    speaker='DM',
                    text='Gundren explains the wagon job.',
                    visibility=StoryTranscriptVisibility.PUBLIC,
                ),
            ),
        )
    )

    def __post_init__(self) -> None:
        self.state = SimpleNamespace(
            actors={'player-1': SimpleNamespace(actor_id='player-1', name='Ari', hp=10, max_hp=10)},
            active_actor_id=None,
            round_number=0,
            event_log=[],
        )
        self.encounter_session = SimpleNamespace(
            control_runtime=FakeRuntime({'player-1': 'player-1-controller'})
        )

    def prompt_for_controller(self, controller_id: str):
        del controller_id
        return None

    def view_for_controller(self, controller_id: str):
        del controller_id
        return SimpleNamespace(
            summary_lines=('Runtime mode: storytelling', 'Gundren is waiting for an answer.'),
            available_choices={},
        )


class LLMPlayerAgentTests(unittest.TestCase):
    def _agent(self, transport: QueueTransport) -> LLMPlayerAgent:
        client = LLMClient(
            LLMConfig(
                api_key='test-key',
                base_url='https://example.test',
                responses_model='test-model',
            ),
            transport=transport,
        )
        return LLMPlayerAgent(controller_id='player-1-controller', client=client, label='test-player')

    def test_agent_builds_player_command_from_json_response(self) -> None:
        transport = QueueTransport('{"command": "/say We accept the job.", "reason": "Move the scene forward."}')
        decision = self._agent(transport).decide(FakeSession())

        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertEqual(decision.controller_id, 'player-1-controller')
        self.assertEqual(decision.command, '/say We accept the job.')
        self.assertEqual(transport.payloads[0]['metadata']['request_type'], 'llm_player_action')
        prompt_text = transport.payloads[0]['input'][0]['content']
        self.assertIn('Do not ask for information that was already answered', prompt_text)

    def test_agent_wraps_plain_text_as_story_action(self) -> None:
        transport = QueueTransport('{"command": "I inspect the wagon.", "reason": "Check for problems."}')
        decision = self._agent(transport).decide(FakeSession())

        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertEqual(decision.command, '/do I inspect the wagon.')

    def test_agent_falls_back_on_malformed_response(self) -> None:
        transport = QueueTransport('not json')
        decision = self._agent(transport).decide(FakeSession())

        self.assertIsNotNone(decision)
        assert decision is not None
        self.assertEqual(decision.command, '/do I stay alert and support the party plan.')

    def test_agent_does_not_repeat_same_observation(self) -> None:
        transport = QueueTransport('{"command": "/say Ready.", "reason": "Once."}')
        agent = self._agent(transport)
        session = FakeSession()

        self.assertIsNotNone(agent.decide(session))
        self.assertIsNone(agent.decide(session))

    def test_agent_context_humanizes_raw_speaker_ids(self) -> None:
        transport = QueueTransport('{"command": "/do I check the harness.", "reason": "Act on the answer."}')
        session = FakeSession()
        session.story_state.transcript_entries = session.story_state.transcript_entries + (
            StoryTranscriptEntry(
                speaker='gundren-rockseeker',
                text='Supplies, mostly.',
                visibility=StoryTranscriptVisibility.PUBLIC,
            ),
        )

        self._agent(transport).decide(session)

        prompt_text = transport.payloads[0]['input'][0]['content']
        self.assertIn('Gundren Rockseeker: Supplies, mostly.', prompt_text)


if __name__ == '__main__':
    unittest.main()
