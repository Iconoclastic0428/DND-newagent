from __future__ import annotations

import copy
import json
from pathlib import Path
import sys
import unittest

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from dm_agent.config import LLMConfig
from web_story_demo_party_connector import (
    PartyActionRecord,
    PartyConnector,
    PartyTranscriptLogger,
    build_default_player_agents,
)


class QueueTransport:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict] = []

    def _next_payload(self) -> dict:
        if not self.payloads:
            raise AssertionError('No queued player-agent payloads remain for this test.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return [{'type': 'response.completed', 'response': self._next_payload()}]


def _base_story_view(*, controller_id: str, actor_id: str, prompt: dict | None = None) -> dict[str, object]:
    return {
        'ok': True,
        'controllerId': controller_id,
        'view': {
            'runtime_mode': 'storytelling',
            'current_scene_id': 'scene-waterdeep-gundren-briefing',
            'round_number': None,
            'active_actor_id': None,
            'owned_actor_ids': [actor_id],
            'summary_lines': [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Open loops: What is Gundren hiding?',
                'Recent check results:',
                '  - Wisdom (Insight): die 14, total 17 vs DC 12 (success).',
            ],
            'action_groups': [
                {
                    'group_id': 'story',
                    'label': 'Story',
                    'choices': [
                        {
                            'option_id': 'declare',
                            'label': 'Describe what you do',
                            'detail': 'story declaration',
                            'command_insert_text': None,
                            'command_prefix': None,
                            'command_hint': 'Use natural language for improvised story actions.',
                        }
                    ],
                }
            ],
            'chat_entries': [
                {
                    'entry_id': 'story-1',
                    'speaker': 'Gundren',
                    'text': 'Phandalin will pay off for all of us if we arrive intact.',
                    'category': 'story',
                    'visibility': 'public',
                },
                {
                    'entry_id': 'check-1',
                    'speaker': 'Player 1',
                    'text': 'Wisdom (Insight): die 14, total 17 vs DC 12 (success).',
                    'category': 'check',
                    'visibility': 'public',
                },
            ],
            'character_cards': [
                {
                    'actor_id': actor_id,
                    'name': actor_id.title(),
                    'class_name': 'Wizard',
                    'level': 1,
                    'species_name': 'Aasimar',
                    'background_name': 'Acolyte',
                    'current_hit_points': 8,
                    'max_hit_points': 8,
                    'temp_hit_points': 0,
                    'armor_class': 12,
                    'conditions': [],
                    'resources': [{'label': 'Level 1 Spell Slots', 'remaining_uses': 2, 'max_uses': 2}],
                    'cantrips': [{'name': 'Fire Bolt'}],
                    'spells': [{'name': 'Magic Missile', 'remaining_uses': 2}],
                    'items': [{'name': 'Explorer Pack'}],
                }
            ],
            'map': None,
        },
        'prompt': prompt,
    }


def _base_combat_view(*, controller_id: str, actor_id: str) -> dict[str, object]:
    snapshot = _base_story_view(controller_id=controller_id, actor_id=actor_id)
    snapshot['view'].update(
        {
            'runtime_mode': 'combat',
            'current_scene_id': 'scene-triboar-goblin-ambush',
            'round_number': 1,
            'active_actor_id': 'player-1',
            'owned_actor_ids': [actor_id],
            'summary_lines': [
                'Runtime mode: combat',
                'Active actor: player-1',
                'monster-goblin-1: Goblin Ambusher 1 [monster] Pos (4,10,10); Status active',
                'monster-goblin-2: Goblin Ambusher 2 [monster] Pos (5,10,10); Status active',
            ],
            'action_groups': [
                {
                    'group_id': 'actions',
                    'label': 'Actions',
                    'choices': [
                        {'option_id': 'attack', 'label': 'Attack', 'detail': 'action'},
                        {'option_id': 'dodge', 'label': 'Dodge', 'detail': 'action'},
                    ],
                },
                {
                    'group_id': 'attacks',
                    'label': 'Attacks',
                    'choices': [{'option_id': 'flail-melee-str', 'label': 'Flail (Melee STR)', 'detail': '+3 to hit'}],
                },
            ],
            'map': {
                'tokens': [
                    {
                        'actor_id': 'player-1',
                        'side': 'player',
                        'status': 'active',
                        'is_owner': controller_id == 'player-1-controller',
                        'position': {'x': 15, 'y': 17, 'z': 0},
                        'hit_points': {'current': 12, 'max': 12, 'temp': 0},
                    },
                    {
                        'actor_id': 'monster-goblin-1',
                        'side': 'monster',
                        'status': 'active',
                        'is_owner': False,
                        'position': {'x': 4, 'y': 10, 'z': 10},
                        'hit_points': {'current': 10, 'max': 10, 'temp': 0},
                    },
                    {
                        'actor_id': 'monster-goblin-2',
                        'side': 'monster',
                        'status': 'active',
                        'is_owner': False,
                        'position': {'x': 5, 'y': 10, 'z': 10},
                        'hit_points': {'current': 10, 'max': 10, 'temp': 0},
                    },
                ]
            },
        }
    )
    return snapshot


class FakeAutomationClient:
    def __init__(self, snapshots: dict[str, dict[str, object]]) -> None:
        self.snapshots = snapshots
        self.submissions: list[tuple[str, str]] = []
        self.prompt_responses: list[tuple[str, object]] = []

    def state(self, controller_id: str) -> dict[str, object]:
        return copy.deepcopy(self.snapshots[controller_id])

    def submit(self, controller_id: str, text: str) -> dict[str, object]:
        self.submissions.append((controller_id, text))
        self._after_action()
        return self.state(controller_id)

    def respond_to_prompt(self, controller_id: str, *, option_id=None, option_ids=None) -> dict[str, object]:
        choice = option_id if option_id is not None else option_ids
        self.prompt_responses.append((controller_id, choice))
        snapshot = self.snapshots[controller_id]
        snapshot['prompt'] = None
        self._after_action()
        return self.state(controller_id)

    def _after_action(self) -> None:
        entry_id = f'dm-{len(self.submissions) + len(self.prompt_responses)}'
        for snapshot in self.snapshots.values():
            view = snapshot['view']
            view['chat_entries'].append(
                {
                    'entry_id': entry_id,
                    'speaker': 'Gundren',
                    'text': 'Phandalin still has dangers worth naming carefully.',
                    'category': 'story',
                    'visibility': 'public',
                }
            )
        if len(self.submissions) + len(self.prompt_responses) >= 2:
            for snapshot in self.snapshots.values():
                snapshot['view']['runtime_mode'] = 'demo-complete'


class PartyConnectorTests(unittest.TestCase):
    def _config(self) -> LLMConfig:
        return LLMConfig(api_key='test-key', base_url='https://example.invalid/v1', responses_model='test-model')

    def _story_snapshots(self) -> dict[str, dict[str, object]]:
        snapshots = {
            controller_id: _base_story_view(controller_id=controller_id, actor_id=f'player-{index}')
            for index, controller_id in enumerate(
                (
                    'player-1-controller',
                    'player-2-controller',
                    'player-3-controller',
                    'player-4-controller',
                ),
                start=1,
            )
        }
        dm_snapshot = _base_story_view(controller_id='dm', actor_id='dm-actor')
        dm_snapshot['view']['owned_actor_ids'] = []
        dm_snapshot['view']['character_cards'] = []
        snapshots['dm'] = dm_snapshot
        return snapshots

    def _combat_snapshots(self) -> dict[str, dict[str, object]]:
        snapshots = {
            controller_id: _base_combat_view(controller_id=controller_id, actor_id=f'player-{index}')
            for index, controller_id in enumerate(
                (
                    'player-1-controller',
                    'player-2-controller',
                    'player-3-controller',
                    'player-4-controller',
                ),
                start=1,
            )
        }
        dm_snapshot = _base_combat_view(controller_id='dm', actor_id='dm-actor')
        dm_snapshot['view']['owned_actor_ids'] = ['monster-goblin-1', 'monster-goblin-2']
        dm_snapshot['view']['character_cards'] = []
        snapshots['dm'] = dm_snapshot
        return snapshots

    def test_player_agent_context_includes_recent_history_and_checks(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I ask Gundren what danger on the road would force him to split from the wagon.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'road danger contingencies',
                            'reason': 'Seraphine pushes the conversation toward practical danger without repeating the insight check.',
                        }
                    )
                }
            ]
        )
        agents = build_default_player_agents(config=self._config(), llm_transport=transport)
        decision, _raw = agents['player-1-controller'].plan_action(
            _base_story_view(controller_id='player-1-controller', actor_id='player-1'),
            public_party_memory=[
                PartyActionRecord(
                    controller_id='player-4-controller',
                    runtime_mode='storytelling',
                    scene_id='scene-waterdeep-gundren-briefing',
                    text='I ask whether the wagon is bait for thieves.',
                    topic_focus='wagon as bait',
                )
            ],
        )
        self.assertEqual(decision.topic_focus, 'road danger contingencies')
        request_text = transport.requests[0]['payload']['input'][0]['content'][0]['text']
        context = json.loads(request_text)
        self.assertTrue(context['recent_visible_check_entries'])
        self.assertIn('Wisdom (Insight)', context['recent_visible_check_entries'][0])
        self.assertEqual(context['recent_party_actions'][0]['topic_focus'], 'wagon as bait')
        self.assertEqual(context['character']['spells'][0]['name'], 'Magic Missile')

    def test_party_connector_retries_duplicate_story_topic_and_accepts_revision(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I thank Gundren and ask what danger he expects on the road.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'road danger',
                            'reason': 'Seraphine opens with a warm question about risk.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I also ask what danger he expects on the road.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'road danger',
                            'reason': 'This intentionally duplicates the previous player topic.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I ask what clue, map detail, or magical anomaly makes Phandalin worth this secrecy.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'phandalin clue and anomaly',
                            'reason': 'Thalen shifts from generic danger to hidden evidence and motive.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=2,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [
                ('player-1-controller', 'I thank Gundren and ask what danger he expects on the road.'),
                ('player-2-controller', 'I ask what clue, map detail, or magical anomaly makes Phandalin worth this secrecy.'),
            ],
        )
        self.assertEqual(result.invalid_action_retries, 1)

    def test_party_connector_retries_invalid_json_and_accepts_revision(self) -> None:
        transport = QueueTransport(
            [
                {'output_text': 'I should ask Gundren about the road.'},
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I ask Gundren which road sign would make him turn the wagon around.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'wagon turnaround warning',
                            'reason': 'The retry returns strict JSON and chooses a distinct actionable question.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'I ask Gundren which road sign would make him turn the wagon around.')],
        )
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Player agent returned invalid JSON', retry_text)
        self.assertIn('I should ask Gundren about the road.', retry_text)

    def test_player_agent_combat_context_includes_attack_template_and_targets(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack player-1 flail-melee-str monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'strike visible goblin',
                            'reason': 'The combat context exposes active actor, attack id, and target ids.',
                        }
                    )
                }
            ]
        )
        agents = build_default_player_agents(config=self._config(), llm_transport=transport)
        agents['player-1-controller'].plan_action(
            _base_combat_view(controller_id='player-1-controller', actor_id='player-1'),
            public_party_memory=[],
        )
        request_text = transport.requests[0]['payload']['input'][0]['content'][0]['text']
        context = json.loads(request_text)
        self.assertEqual(context['combat']['command_templates']['attack'], '/attack player-1 <attack option_id> <target actor id>')
        self.assertEqual(context['combat']['command_templates']['dodge'], '/dodge player-1')
        self.assertEqual(context['combat']['legal_attack_option_ids'], ['flail-melee-str'])
        self.assertEqual(context['combat']['visible_enemy_target_ids'], ['monster-goblin-1', 'monster-goblin-2'])
        self.assertEqual(context['combat']['safe_fallback_command'], '/dodge player-1')

    def test_party_connector_retries_attack_without_target_and_accepts_full_command(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack flail-melee-str',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'strike visible goblin',
                            'reason': 'This intentionally omits actor and target ids.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack player-1 flail-melee-str monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'strike visible goblin',
                            'reason': 'The retry uses the full attack syntax with a visible target.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/attack player-1 flail-melee-str monster-goblin-1')],
        )
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('/attack player-1 <attack option_id> <target actor id>', retry_text)
        self.assertIn('monster-goblin-1', retry_text)

    def test_party_connector_retries_endturn_when_action_is_available(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/endturn player-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'pass turn',
                            'reason': 'This intentionally passes despite available actions.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/dodge player-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'defensive stance',
                            'reason': 'The retry uses a real action instead of ending the turn.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/dodge player-1')])
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Do not end the turn while actions, attacks, or spells are still available', retry_text)

    def test_party_connector_fallback_uses_dodge_instead_of_endturn_when_actions_remain(self) -> None:
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/dodge player-1')])
        self.assertEqual(result.invalid_action_retries, 3)

    def test_party_connector_falls_back_after_repeated_invalid_json(self) -> None:
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'I steady the conversation and ask what promise would make Gundren feel safer trusting us with the road ahead.',
                )
            ],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_story_fallback_uses_last_resort_when_default_fallback_repeats(self) -> None:
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-2-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='I steady the conversation and ask what promise would make Gundren feel safer trusting us with the road ahead.',
                topic_focus='trust terms scene-waterdeep-gundren-briefing',
            )
        )
        result = connector.run()
        self.assertEqual(len(connector.automation_client.submissions), 1)
        controller_id, text = connector.automation_client.submissions[0]
        self.assertEqual(controller_id, 'player-1-controller')
        self.assertIn('I take a fresh angle in scene-waterdeep-gundren-briefing', text)
        self.assertEqual(result.invalid_action_retries, 3)

    def test_party_connector_uses_prompt_response_path_for_player_prompt(self) -> None:
        prompt = {
            'prompt_id': 'timing:test',
            'prompt_kind': 'timing-order',
            'text': 'Choose the next start-of-turn effect to resolve.',
            'options': [
                {'option_id': 'effect-trigger', 'label': 'Resolve trigger', 'detail': 'trigger', 'actor_id': 'player-1'},
                {'option_id': 'effect-expire', 'label': 'Expire effect', 'detail': 'expire', 'actor_id': 'player-1'},
            ],
        }
        snapshots = self._story_snapshots()
        snapshots['player-1-controller']['prompt'] = prompt
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'prompt_response',
                            'text': '',
                            'option_id': 'effect-trigger',
                            'option_ids': [],
                            'topic_focus': 'resolve upkeep trigger',
                            'reason': 'The prompt requires a timing-order choice, so answer it directly.',
                        }
                    )
                }
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(connector.automation_client.prompt_responses, [('player-1-controller', 'effect-trigger')])
        self.assertEqual(result.prompt_responses_sent, 1)

    def test_party_connector_writes_transcript_file(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I ask Gundren what warning he keeps softening.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'softened warning',
                            'reason': 'Seraphine presses for the truth in a calm way.',
                        }
                    )
                }
            ]
        )
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript.log'
        if transcript_path.exists():
            transcript_path.unlink()
        try:
            connector = PartyConnector(
                automation_client=FakeAutomationClient(self._story_snapshots()),
                player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
                poll_interval_seconds=0.01,
                max_actions=1,
                transcript_logger=PartyTranscriptLogger(transcript_path),
            )
            connector.run()
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()
        self.assertIn('# Live Party Transcript', transcript)
        self.assertIn('[player-1-controller] I ask Gundren what warning he keeps softening.', transcript)
        self.assertIn('Gundren: Phandalin still has dangers worth naming carefully.', transcript)


if __name__ == '__main__':
    unittest.main()
