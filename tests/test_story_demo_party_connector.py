from __future__ import annotations

import copy
import json
import threading
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
    PartyConnectorError,
    RawInteractionLogger,
    RawInteractionLoggingTransport,
    PartyTranscriptLogger,
    build_default_dm_combat_agent,
    _build_llm_transport,
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


class BlockingVoteTransport:
    def __init__(self, *, vote_payload: dict, action_payload: dict, expected_votes: int = 4) -> None:
        self.vote_payload = dict(vote_payload)
        self.action_payload = dict(action_payload)
        self.expected_votes = expected_votes
        self.requests: list[dict] = []
        self.max_pending_vote_requests = 0
        self._vote_requests = 0
        self._condition = threading.Condition()

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        request_type = payload.get('metadata', {}).get('request_type')
        with self._condition:
            self.requests.append({'url': url, 'headers': headers, 'payload': payload})
            if request_type != 'party_speaker_vote':
                return {'output_text': json.dumps(self.action_payload)}

            self._vote_requests += 1
            self.max_pending_vote_requests = max(self.max_pending_vote_requests, self._vote_requests)
            if self._vote_requests >= self.expected_votes:
                self._condition.notify_all()
            elif not self._condition.wait_for(
                lambda: self._vote_requests >= self.expected_votes,
                timeout=0.5,
            ):
                raise AssertionError('speaker votes were collected sequentially instead of concurrently')
            return {'output_text': json.dumps(self.vote_payload)}

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        return [{'type': 'response.completed', 'response': self.post(url=url, headers=headers, payload=payload)}]


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

    def _combat_snapshots_with_spent_action(self) -> dict[str, dict[str, object]]:
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'].append(
                'player-1: Player 1 [player] HP 7/7; Temp 0; AC 12; Pos (15,17,0); Move 30; Action no; Bonus yes; Reaction yes'
            )
        return snapshots

    def _monster_active_combat_snapshots(self) -> dict[str, dict[str, object]]:
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['active_actor_id'] = 'monster-goblin-1'
            snapshot['view']['summary_lines'] = [
                'Runtime mode: combat',
                'Active actor: monster-goblin-1',
                'player-1: Player 1 [player] HP 7/7; Temp 0; AC 12; Pos (15,17,0); Move 30; Action yes; Bonus yes; Reaction yes',
                'monster-goblin-1: Goblin Ambusher 1 [monster] HP 10/10; Temp 0; AC 15; Pos (4,10,10); Move 30; Action yes; Bonus yes; Reaction yes',
            ]
            snapshot['view']['action_groups'] = [
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
                    'choices': [{'option_id': 'shortbow', 'label': 'Shortbow', 'detail': '+4 to hit; range 80/320'}],
                },
            ]
        return snapshots

    def test_player_agent_context_includes_recent_history_and_checks(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what danger on the road would force you to split from the wagon?',
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
                    text='Gundren, is the wagon bait for thieves?',
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
        self.assertEqual(transport.requests[0]['payload']['max_output_tokens'], 1200)
        self.assertEqual(transport.requests[0]['payload']['thinking'], {'type': 'enabled'})
        self.assertEqual(transport.requests[0]['payload']['reasoning_effort'], 'medium')

    def test_player_agent_positive_profile_prioritizes_scene_goal_completion(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what would settle the last concern before we take the wagon east?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'resolve final contract concern',
                            'reason': 'The positive profile pushes toward scene-goal completion.',
                        }
                    )
                }
            ]
        )
        agents = build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive')
        agents['player-1-controller'].plan_action(
            _base_story_view(controller_id='player-1-controller', actor_id='player-1'),
            public_party_memory=[],
        )

        instructions = transport.requests[0]['payload']['instructions']
        self.assertIn('finish visible scene goals', instructions)
        self.assertIn('avoid repeated wording', instructions)

    def test_party_connector_sends_scene_closure_pressure_to_positive_player(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job depart',
                            'reason': 'The scene has enough setup and should move to the road.',
                        }
                    )
                }
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index in range(2):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=f'player-{(index % 4) + 1}-controller',
                    runtime_mode='storytelling',
                    scene_id='scene-waterdeep-gundren-briefing',
                    text=f'Gundren, preparatory question {index}?',
                    topic_focus=f'preparatory topic {index}',
                )
            )

        connector.run()

        request = transport.requests[0]['payload']
        instructions = request['instructions']
        context = json.loads(request['input'][0]['content'][0]['text'])
        self.assertEqual(context['current_scene_story_turn_count'], 2)
        self.assertEqual(context['scene_progress_pressure'], 'close_scene_now')
        self.assertIn('close the scene now', instructions)
        self.assertIn('stop asking preparatory questions', instructions)
        self.assertIn('do not add new demands', instructions)
        self.assertIn('Gundren, we accept the job', instructions)

    def test_party_connector_retries_stale_briefing_closure_that_can_trigger_checks(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. Let us finish loading and get the wagon onto the High Road now.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job with request wording',
                            'reason': 'This sounds like closure but can still trigger a request/favor check.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job depart',
                            'reason': 'Plain acceptance matches the no-check interpreter path.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index in range(2):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=f'player-{(index % 4) + 1}-controller',
                    runtime_mode='storytelling',
                    scene_id='scene-waterdeep-gundren-briefing',
                    text=f'Gundren, preparatory question {index}?',
                    topic_focus=f'preparatory topic {index}',
                )
            )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, we accept the job. We will take the wagon to Phandalin.',
                )
            ],
        )
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_retries_second_briefing_ledger_detour(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '"Gundren, if you will not speak of your find, at least let me examine your wagon ledger. Knowing the cargo and roads may tell me what wards we need."',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'wagon ledger detour',
                            'reason': 'This repeats stale briefing demands instead of accepting and departing.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job depart',
                            'reason': 'The retry closes the briefing with the safe no-check acceptance wording.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-3-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text="Gundren, what is waiting for us on the road?",
                topic_focus='road danger',
            )
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, we accept the job. We will take the wagon to Phandalin.',
                )
            ],
        )
        first_context = json.loads(transport.requests[0]['payload']['input'][0]['content'][0]['text'])
        self.assertEqual(first_context['current_scene_story_turn_count'], 1)
        self.assertEqual(first_context['scene_progress_pressure'], 'close_scene_now')
        retry_payload = json.dumps(transport.requests[1]['payload'])
        self.assertIn('Stale Gundren briefing closure', retry_payload)

    def test_party_connector_retries_noncanonical_briefing_acceptance(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '"Gundren, the job is accepted. We will guard the wagon north to Phandalin. Point us to it and we will be off."',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'noncanonical accept job',
                            'reason': 'This sounds like acceptance but does not reliably trigger the runtime transition.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job depart',
                            'reason': 'The retry uses the transition-safe wording.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-3-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, what danger should we watch for?',
                topic_focus='road danger',
            )
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, we accept the job. We will take the wagon to Phandalin.',
                )
            ],
        )
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_routes_after_briefing_acceptance_still_in_scene(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Get some rest at the inn and depart at first light.; Get the wagon safely onto the High Road.',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'repeat accepted briefing',
                            'reason': 'This repeats natural acceptance after the accepted/rest goals are already present.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel route phandalin',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route to phandalin',
                            'reason': 'The accepted briefing now needs the authoritative travel command.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-3-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, what danger should we watch for?',
                topic_focus='road danger',
            )
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_retries_stale_high_road_idle_scene_to_travel_route(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-00-high-road-journey'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Before we head out, I check the wheels and count rations again.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'repeat wagon prep',
                            'reason': 'This is legal but stalls the stale High Road scene.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel route phandalin',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route to phandalin',
                            'reason': 'Route planning uses the authoritative travel system.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index in range(2):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=f'player-{(index % 4) + 1}-controller',
                    runtime_mode='storytelling',
                    scene_id='scene-00-high-road-journey',
                    text=f'High Road prep turn {index}',
                    topic_focus=f'high road prep {index}',
                )
            )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_routes_high_road_idle_scene_before_any_detour(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-00-high-road-journey'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Before we roll, I inspect the wagon again for hidden magic or loose wheels.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'repeat wagon inspection',
                            'reason': 'This is the observed first High Road detour after accepting the briefing.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel route phandalin',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route to phandalin',
                            'reason': 'The first High Road action must start authoritative travel.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        first_context = json.loads(transport.requests[0]['payload']['input'][0]['content'][0]['text'])
        self.assertEqual(first_context['scene_progress_pressure'], 'close_scene_now')
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_retries_stale_high_road_planned_route_to_travel_advance(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-00-high-road-journey'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (1,0)',
                'Travel status: route_planned',
                'Travel route: Phandalin; 240 minutes at current pace.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel route phandalin',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'repeat route plan',
                            'reason': 'This repeats planning instead of advancing the route.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel advance 5',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'advance toward ambush',
                            'reason': 'Advancing the planned route can reach the ambush hook.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index in range(2):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=f'player-{(index % 4) + 1}-controller',
                    runtime_mode='storytelling',
                    scene_id='scene-00-high-road-journey',
                    text=f'High Road route-planned prep turn {index}',
                    topic_focus=f'high road planned prep {index}',
                )
            )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel advance 5')])
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_retries_hyphenated_route_planned_status_to_travel_advance(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-00-high-road-journey'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (1,0)',
                'Travel status: route-planned',
                'Travel route: Phandalin; 240 minutes at current pace.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel resume',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'resume planned travel',
                            'reason': 'This should not be submitted while the live status is route-planned.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel advance 5',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'advance planned travel',
                            'reason': 'Advancing the planned route can reach the ambush hook.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel advance 5')])
        self.assertEqual(len(transport.requests), 1)

    def test_party_connector_retries_malformed_story_slash_commands_before_submit(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-triboar-goblin-ambush'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-triboar-goblin-ambush',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (5,0)',
                'Travel status: interrupted',
                'Travel interruption: The road ahead shows riderless horses, torn packs, and signs of an ambush on the Triboar Trail.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast Detect Magic as ritual',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'investigate ambush site for magic',
                            'reason': 'This omits the owned actor id and spell option id.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/ritual Detect Magic',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'investigate ambush site for magic',
                            'reason': 'This is not a supported story-mode slash command.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/do casts Detect Magic as a ritual, scanning the ambush site for lingering magical auras.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'investigate ambush site for magic',
                            'reason': 'The retry uses a supported story-mode improvised declaration.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 2)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/do casts Detect Magic as a ritual, scanning the ambush site for lingering magical auras.')],
        )
        retry_payloads = '\n'.join(json.dumps(request['payload']) for request in transport.requests[1:])
        self.assertIn('/cast <owned_actor_id> <spell option id>', retry_payloads)
        self.assertIn('Unsupported story-mode slash command `/ritual`', retry_payloads)

    def test_party_connector_retries_unprompted_story_check_before_submit(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['prompt'] = None
            view = snapshot['view']
            view['current_scene_id'] = 'scene-triboar-goblin-ambush'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-triboar-goblin-ambush',
                'Travel status: interrupted',
                'Travel interruption: The road ahead shows riderless horses, torn packs, and signs of an ambush on the Triboar Trail.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/check investigation',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'examining the ambush scene',
                            'reason': 'This tries to roll a check without a pending story-check prompt.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/do examine the riderless horses and scattered packs for ambush clues.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'examining ambush clues',
                            'reason': 'The retry uses a legal story declaration instead of an unprompted check roll.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='negative'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/do examine the riderless horses and scattered packs for ambush clues.')],
        )
        retry_payload = json.dumps(transport.requests[1]['payload'])
        self.assertIn('Story-mode /check may only answer a pending story-check prompt', retry_payload)

    def test_party_connector_retries_travel_advance_while_interrupted(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['prompt'] = None
            view = snapshot['view']
            view['current_scene_id'] = 'scene-triboar-goblin-ambush'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-triboar-goblin-ambush',
                'Location: triboar-trail',
                'Party goals: Survive the ambush.; Secure the wagon and investigate the trail.',
                'Travel status: interrupted',
                'Travel interruption: The road ahead shows riderless horses, torn packs, and signs of an ambush on the Triboar Trail.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel advance 5',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'advance travel past ambush',
                            'reason': 'This skips the interrupted scene hook.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/do examine the riderless horses, torn packs, and nearby brush for ambush clues.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'resolve ambush interruption',
                            'reason': 'The retry resolves the interrupted travel hook in story mode.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/do examine the riderless horses, torn packs, and nearby brush for ambush clues.')],
        )
        retry_payload = json.dumps(transport.requests[1]['payload'])
        self.assertIn('Travel is interrupted by a pending hook', retry_payload)

    def test_party_connector_retries_waterdeep_travel_before_job_acceptance(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-waterdeep-gundren-briefing'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Hear Gundren out and decide whether to take the Phandalin job.; Get the wagon safely onto the High Road.',
                'Travel status: idle',
                'Story log:',
                'Exploration: Gundren shuts down the bargaining attempt and keeps the purse strings tight.',
            ]
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel route phandalin',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job and plan travel route',
                            'reason': 'This tries to route travel before the party has accepted the job.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, we accept the job. We will take the wagon to Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'accept job and depart',
                            'reason': 'The retry accepts the job before any travel routing.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, we accept the job. We will take the wagon to Phandalin.')],
        )
        retry_payload = json.dumps(transport.requests[1]['payload'])
        self.assertIn('Accept the Phandalin job before using /travel', retry_payload)

    def test_player_agent_negative_profile_prompts_legal_stalling_examples(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, can you repeat the safest part again before we decide?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'repeat safety concern',
                            'reason': 'The negative profile creates a legal but lower-value stalled turn.',
                        }
                    )
                }
            ]
        )
        agents = build_default_player_agents(
            config=self._config(),
            llm_transport=transport,
            behavior_profile='negative',
            negative_intensity=0.75,
        )
        agents['player-1-controller'].plan_action(
            _base_story_view(controller_id='player-1-controller', actor_id='player-1'),
            public_party_memory=[],
            current_scene_story_turn_count=4,
        )

        instructions = transport.requests[0]['payload']['instructions']
        self.assertIn('negative RL training examples', instructions)
        self.assertIn('Keep the action legal and parseable', instructions)
        self.assertIn('Never use /check unless a visible story-check prompt is present', instructions)
        self.assertIn('stalling', instructions)
        self.assertIn('stale scene', instructions)
        self.assertIn('move the scene forward', instructions)

    def test_deepseek_json_requests_use_task_specific_completion_budgets(self) -> None:
        vote_payload = {
            'selected_controller_id': 'player-3-controller',
            'reason': 'Mira has the best logistics fit for the wagon job.',
            'advantage_factors': ['wagon logistics', 'travel supplies'],
            'confidence': 0.8,
        }
        transport = QueueTransport(
            [
                {'output_text': json.dumps(vote_payload)},
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what must be settled before the wagon leaves?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'departure blocker',
                            'reason': 'Ask a concrete scene-goal question.',
                        }
                    )
                },
            ]
        )
        agents = build_default_player_agents(
            config=LLMConfig(
                api_key='test-key',
                base_url='https://api.deepseek.com',
                responses_model='deepseek-v4-pro',
                api_format='chat_completions',
            ),
            llm_transport=transport,
        )
        snapshot = _base_story_view(controller_id='player-1-controller', actor_id='player-1')

        agents['player-1-controller'].vote_speaker(
            snapshot,
            speaker_candidates=({'controller_id': 'player-3-controller'},),
            public_party_memory=[],
        )
        agents['player-1-controller'].plan_action(snapshot, public_party_memory=[])

        self.assertEqual(transport.requests[0]['payload']['max_tokens'], 700)
        self.assertEqual(transport.requests[0]['payload']['thinking'], {'type': 'disabled'})
        self.assertNotIn('reasoning_effort', transport.requests[0]['payload'])
        self.assertEqual(transport.requests[1]['payload']['max_tokens'], 1200)
        self.assertEqual(transport.requests[1]['payload']['thinking'], {'type': 'enabled'})
        self.assertEqual(transport.requests[1]['payload']['reasoning_effort'], 'medium')

    def test_raw_interaction_logging_transport_writes_request_and_response_jsonl(self) -> None:
        log_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / 'raw-llm-io.jsonl'
        if log_path.exists():
            log_path.unlink()
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what matters most before we roll out?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'departure priority',
                            'reason': 'The logger should capture this raw model response.',
                        }
                    )
                }
            ]
        )
        try:
            logging_transport = RawInteractionLoggingTransport(transport, RawInteractionLogger(log_path))
            agents = build_default_player_agents(config=self._config(), llm_transport=logging_transport)
            agents['player-1-controller'].plan_action(
                _base_story_view(controller_id='player-1-controller', actor_id='player-1'),
                public_party_memory=[],
            )
            rows = [json.loads(line) for line in log_path.read_text(encoding='utf-8').splitlines()]
        finally:
            if log_path.exists():
                log_path.unlink()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['transport_method'], 'post')
        self.assertIn('request_payload', rows[0])
        self.assertIn('response_payload', rows[0])
        self.assertNotIn('Authorization', json.dumps(rows[0], sort_keys=True))

    def test_build_llm_transport_applies_timeout_before_raw_logging_wrapper(self) -> None:
        log_path = REPO_ROOT / 'tmp' / 'test_party_connector' / 'raw-timeout.jsonl'

        transport = _build_llm_transport(
            llm_transport=None,
            interaction_log_path=log_path,
            llm_timeout_seconds=42.0,
        )

        self.assertIsInstance(transport, RawInteractionLoggingTransport)
        self.assertEqual(transport.inner_transport.timeout_seconds, 42.0)
        self.assertEqual(transport.inner_transport.stream_timeout_seconds, 42.0)

    def test_party_connector_retries_duplicate_story_topic_and_accepts_revision(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, thank you. What danger do you expect on the road?',
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
                            'text': 'Gundren, what danger do you expect on the road?',
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
                            'text': 'Gundren, what clue, map detail, or magical anomaly makes Phandalin worth this secrecy?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'phandalin clue and anomaly',
                            'reason': 'Thalen shifts from generic danger to hidden evidence and motive.',
                        }
                    )
                },
            ]
        )
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['current_scene_id'] = 'scene-gundren-social-test'
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=2,
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [
                ('player-1-controller', 'Gundren, thank you. What danger do you expect on the road?'),
                ('player-2-controller', 'Gundren, what clue, map detail, or magical anomaly makes Phandalin worth this secrecy?'),
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
                            'text': 'Gundren, which road sign would make you turn the wagon around?',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, which road sign would make you turn the wagon around?')],
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

    def test_player_agent_combat_context_filters_unsupported_spell_options(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'safe targeted spell',
                            'reason': 'The context should only advertise connector-supported combat spells.',
                        }
                    )
                }
            ]
        )
        snapshot = _base_combat_view(controller_id='player-1-controller', actor_id='player-1')
        snapshot['view']['action_groups'].append(
            {
                'group_id': 'magic',
                'label': 'Magic',
                'choices': [
                    {'option_id': 'detect-magic', 'label': 'Detect Magic', 'detail': 'action; uses at-will'},
                    {'option_id': 'guidance', 'label': 'Guidance', 'detail': 'action; uses at-will'},
                    {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'action; range 120 feet'},
                    {'option_id': 'fire-bolt', 'label': 'Fire Bolt', 'detail': 'action; range 120 feet'},
                ],
            }
        )
        agents = build_default_player_agents(config=self._config(), llm_transport=transport)
        agents['player-1-controller'].plan_action(snapshot, public_party_memory=[])

        request_text = transport.requests[0]['payload']['input'][0]['content'][0]['text']
        context = json.loads(request_text)
        self.assertEqual(context['combat']['legal_spell_option_ids'], ['magic-missile', 'fire-bolt'])

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
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            tokens = snapshot['view']['map']['tokens']
            for token in tokens:
                if token['actor_id'] == 'monster-goblin-1':
                    token['position'] = {'x': 15, 'y': 18, 'z': 0}
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
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

    def test_party_connector_retries_cast_with_multiple_targets(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1 monster-goblin-2',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'split magic missile',
                            'reason': 'This intentionally adds a second target token.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'focus magic missile',
                            'reason': 'The retry uses one visible target.',
                        }
                    )
                },
            ]
        )
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['action_groups'].append(
                {
                    'group_id': 'magic',
                    'label': 'Magic',
                    'choices': [{'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': '1st-level spell'}],
                }
            )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/cast player-1 magic-missile monster-goblin-1')],
        )
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('/cast player-1 <spell option id> <target actor id>', retry_text)
        self.assertIn('monster-goblin-1', retry_text)

    def test_party_connector_retries_unsupported_combat_detect_magic_cast(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 detect-magic',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'scan for magic in combat',
                            'reason': 'This utility spell can fail later on resources and should not be submitted.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'damage visible goblin',
                            'reason': 'The retry uses a connector-supported targeted combat spell.',
                        }
                    )
                },
            ]
        )
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['action_groups'].append(
                {
                    'group_id': 'magic',
                    'label': 'Magic',
                    'choices': [
                        {'option_id': 'detect-magic', 'label': 'Detect Magic', 'detail': 'action; uses at-will'},
                        {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'action; range 120 feet'},
                    ],
                }
            )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/cast player-1 magic-missile monster-goblin-1')])
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Unsupported combat spell `detect-magic`', retry_text)

    def test_party_connector_retries_unsupported_combat_guidance_cast(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 guidance player-2',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'support ally with guidance',
                            'reason': 'Guidance needs extra skill arguments and should not be submitted by the combat connector.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'damage visible goblin',
                            'reason': 'The retry uses a connector-supported targeted combat spell.',
                        }
                    )
                },
            ]
        )
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['action_groups'].append(
                {
                    'group_id': 'magic',
                    'label': 'Magic',
                    'choices': [
                        {'option_id': 'guidance', 'label': 'Guidance', 'detail': 'action; uses at-will'},
                        {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'action; range 120 feet'},
                    ],
                }
            )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/cast player-1 magic-missile monster-goblin-1')])
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Unsupported combat spell `guidance`', retry_text)

    def test_party_connector_retries_point_target_spell_without_coordinates(self) -> None:
        for point_spell in ('mage-hand', 'light'):
            with self.subTest(point_spell=point_spell):
                transport = QueueTransport(
                    [
                        {
                            'output_text': json.dumps(
                                {
                                    'decision_type': 'command',
                                    'text': f'/cast player-1 {point_spell}',
                                    'option_id': None,
                                    'option_ids': [],
                                    'topic_focus': 'summon point spell',
                                    'reason': 'This omits the required point coordinates.',
                                }
                            )
                        },
                        {
                            'output_text': json.dumps(
                                {
                                    'decision_type': 'command',
                                    'text': '/cast player-1 magic-missile monster-goblin-1',
                                    'option_id': None,
                                    'option_ids': [],
                                    'topic_focus': 'damage visible goblin',
                                    'reason': 'The retry uses a combat spell with a visible enemy target.',
                                }
                            )
                        },
                    ]
                )
                snapshots = self._combat_snapshots()
                for snapshot in snapshots.values():
                    snapshot['view']['action_groups'].append(
                        {
                            'group_id': 'magic',
                            'label': 'Magic',
                            'choices': [
                                {'option_id': point_spell, 'label': point_spell, 'detail': 'action; point target'},
                                {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'action; range 120 feet'},
                            ],
                        }
                    )
                connector = PartyConnector(
                    automation_client=FakeAutomationClient(snapshots),
                    player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
                    poll_interval_seconds=0.01,
                    max_actions=1,
                )
                result = connector.run()
                self.assertEqual(
                    connector.automation_client.submissions,
                    [('player-1-controller', '/cast player-1 magic-missile monster-goblin-1')],
                )
                self.assertEqual(result.invalid_action_retries, 1)
                retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
                self.assertIn('requires point target coordinates', retry_text)
                self.assertIn(f'/cast player-1 {point_spell} <x> <y>', retry_text)

    def test_party_connector_retries_melee_attack_against_distant_target(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack player-1 unarmed-strike monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'distant unarmed strike',
                            'reason': 'This melee attack is out of range.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack player-1 dagger-thrown-str monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'thrown dagger fallback',
                            'reason': 'The thrown attack can target a distant visible enemy.',
                        }
                    )
                },
            ]
        )
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['action_groups'] = [
                group
                for group in snapshot['view']['action_groups']
                if group['group_id'] != 'attacks'
            ]
            snapshot['view']['action_groups'].append(
                {
                    'group_id': 'attacks',
                    'label': 'Attacks',
                    'choices': [
                        {'option_id': 'unarmed-strike', 'label': 'Unarmed Strike', 'detail': '+1 to hit'},
                        {'option_id': 'dagger-thrown-str', 'label': 'Dagger (Thrown STR)', 'detail': '+1 to hit'},
                    ],
                }
            )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/attack player-1 dagger-thrown-str monster-goblin-1')],
        )
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Melee attack target is out of range', retry_text)

    def test_party_connector_retries_range_limited_spell_against_distant_target(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 charm-person monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'distant charm person',
                            'reason': 'This spell is out of range for the target.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/cast player-1 magic-missile monster-goblin-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'ranged spell fallback',
                            'reason': 'Magic Missile can target the distant visible enemy.',
                        }
                    )
                },
            ]
        )
        snapshots = self._combat_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['action_groups'].append(
                {
                    'group_id': 'magic',
                    'label': 'Magic',
                    'choices': [
                        {'option_id': 'charm-person', 'label': 'Charm Person', 'detail': 'action; range 30 feet'},
                        {'option_id': 'magic-missile', 'label': 'Magic Missile', 'detail': 'action; range 120 feet'},
                    ],
                }
            )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', '/cast player-1 magic-missile monster-goblin-1')],
        )
        self.assertEqual(result.invalid_action_retries, 1)
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('Spell target is out of range', retry_text)

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

    def test_combat_validator_rejects_attack_when_active_actor_action_spent(self) -> None:
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots_with_spent_action()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=QueueTransport([])),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        view = connector.automation_client.state('player-1-controller')['view']

        with self.assertRaisesRegex(PartyConnectorError, 'already used its action'):
            connector._validate_combat_command(view, '/attack player-1 flail-melee-str monster-goblin-1')

    def test_party_connector_fast_paths_endturn_when_active_actor_action_spent(self) -> None:
        transport = QueueTransport([])
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots_with_spent_action()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/endturn player-1')])
        self.assertEqual(transport.requests, [])
        self.assertEqual(result.invalid_action_retries, 0)

    def test_party_connector_fast_path_skips_invalid_output_fallback_when_action_spent(self) -> None:
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._combat_snapshots_with_spent_action()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )
        result = connector.run()
        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/endturn player-1')])
        self.assertEqual(transport.requests, [])
        self.assertEqual(result.invalid_action_retries, 0)

    def test_party_connector_routes_active_monster_turn_through_dm_agent(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'dm-monster-action-transcript.log'
        if transcript_path.exists():
            transcript_path.unlink()
        dm_transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack monster-goblin-1 shortbow player-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'goblin shortbow attack',
                            'reason': 'The active goblin uses a legal ranged attack against a visible player.',
                        }
                    )
                }
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._monster_active_combat_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=QueueTransport([])),
            dm_combat_agent=build_default_dm_combat_agent(config=self._config(), llm_transport=dm_transport),
            poll_interval_seconds=0.01,
            max_actions=1,
            transcript_logger=PartyTranscriptLogger(transcript_path),
        )
        try:
            result = connector.run()
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertEqual(connector.automation_client.submissions, [('dm', '/attack monster-goblin-1 shortbow player-1')])
        self.assertEqual(result.invalid_action_retries, 0)
        self.assertEqual(dm_transport.requests[0]['payload']['metadata']['request_type'], 'dm_monster_turn')
        request_context = json.loads(dm_transport.requests[0]['payload']['input'][0]['content'][0]['text'])
        self.assertEqual(request_context['combat']['visible_enemy_target_ids'], ['player-1'])
        self.assertNotIn('[system:dm] /endturn monster-goblin-1', transcript)
        self.assertIn('[dm] /attack monster-goblin-1 shortbow player-1', transcript)

    def test_dm_combat_agent_retry_uses_compact_no_thinking_budget(self) -> None:
        dm_transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/attack monster-goblin-1 shortbow player-1',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'goblin retry attack',
                            'reason': 'The retry uses a legal ranged attack against a visible player.',
                        }
                    )
                }
            ]
        )
        agent = build_default_dm_combat_agent(config=self._config(), llm_transport=dm_transport)

        agent.plan_monster_action(
            self._monster_active_combat_snapshots()['dm'],
            previous_output='/endturn monster-goblin-1',
            error_message='Do not end the turn while an attack is available.',
            attempt_number=2,
        )

        request_payload = dm_transport.requests[0]['payload']
        self.assertEqual(request_payload['metadata']['request_type'], 'dm_monster_retry')
        self.assertEqual(request_payload['max_output_tokens'], 700)
        self.assertEqual(request_payload['thinking'], {'type': 'disabled'})
        self.assertNotIn('reasoning_effort', request_payload)

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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, what promise would make you feel safer trusting us with the road ahead?',
                )
            ],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_story_fallback_avoids_offstage_gundren_in_ambush_scene(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-triboar-goblin-ambush'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-triboar-goblin-ambush',
                'Party goals: Survive the ambush.; Secure the wagon and investigate the trail.',
                'Open loops: Who ambushed Gundren and Sildar?; Can the party survive the goblin ambush?',
                'Travel status: interrupted',
                'Travel interruption: The road ahead shows riderless horses, torn packs, and signs of an ambush on the Triboar Trail.',
            ]
            view['chat_entries'] = []
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'I inspect the road, brush, riderless horses, and torn packs for tracks or signs of where the attackers went.',
                )
            ],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_party_connector_retries_offstage_npc_direct_address_in_ambush_scene(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            view = snapshot['view']
            view['current_scene_id'] = 'scene-triboar-goblin-ambush'
            view['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-triboar-goblin-ambush',
                'Party goals: Follow the hidden trail north to the goblins\' hideout; Rescue Gundren Rockseeker and Sildar Hallwinter',
                'Open loops: Find the ambushers\' trail; Rescue Gundren and Sildar',
                'Travel status: interrupted',
            ]
            view['chat_entries'] = []
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I turn to the others. "Enough poking at tracks. Gundren, Sildar - we move north. I will take point."',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'follow ambushers trail',
                            'reason': 'This incorrectly addresses offstage rescue targets as if they were present.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I turn to the others. "Enough poking at tracks. We move north. I will take point."',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'follow ambushers trail',
                            'reason': 'The retry addresses only the present party.',
                        }
                    )
                },
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'I turn to the others. "Enough poking at tracks. We move north. I will take point."',
                )
            ],
        )

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
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-2-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, what promise would make you feel safer trusting us with the road ahead?',
                topic_focus='trust terms scene-waterdeep-gundren-briefing',
            )
        )
        result = connector.run()
        self.assertEqual(len(connector.automation_client.submissions), 1)
        controller_id, text = connector.automation_client.submissions[0]
        self.assertEqual(controller_id, 'player-1-controller')
        self.assertNotIn('fresh angle', text)
        self.assertNotIn('player 1 controller', text)
        self.assertEqual(text, 'Gundren, we accept the job. We will take the wagon to Phandalin.')
        self.assertEqual(result.invalid_action_retries, 3)

    def test_stale_briefing_last_resort_uses_direct_acceptance(self) -> None:
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
            enable_speaker_voting=False,
        )
        for index, controller_id in enumerate(
            ('player-2-controller', 'player-3-controller', 'player-4-controller'),
            start=1,
        ):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=controller_id,
                    runtime_mode='storytelling',
                    scene_id='scene-waterdeep-gundren-briefing',
                    text=f'Gundren, stale setup question {index}?',
                    topic_focus=f'stale setup question {index}',
                )
            )

        result = connector.run()

        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, we accept the job. We will take the wagon to Phandalin.')],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_accepted_briefing_last_resort_routes_idle_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Get some rest at the inn and depart at first light.; Get the wagon safely onto the High Road.',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-2-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, what promise would make you feel safer trusting us with the road ahead?',
                topic_focus='trust terms scene-waterdeep-gundren-briefing',
            )
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        self.assertEqual(result.invalid_action_retries, 3)

    def test_accepted_briefing_routes_idle_travel_without_rest_goal(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Get the wagon safely onto the High Road.',
                'Open loops: Why is Gundren so eager to reach Phandalin ahead of the wagon?',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
                'Story log:',
                "Gundren Rockseeker: Aye, that's what I wanted to hear! The wagon's in the stable yard, loaded and ready. You'll set out at dawn.",
                "Sildar Hallwinter: I'll make sure the waybill is clear. Ten gold each on delivery, no less, no more.",
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-4-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, we accept the job. We will take the wagon to Phandalin.',
                topic_focus='accept job and depart',
            )
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        self.assertEqual(result.invalid_action_retries, 3)

    def test_unaccepted_briefing_last_resort_accepts_before_routing_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Hear Gundren out and decide whether to take the Phandalin job.; Get the wagon safely onto the High Road.',
                'Open loops: Why is Gundren so eager to reach Phandalin ahead of the wagon?',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-3-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text="Gundren, what's the pay and what are we hauling?",
                topic_focus='payment cargo',
            )
        )

        result = connector.run()

        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, we accept the job. We will take the wagon to Phandalin.')],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_briefing_with_planned_route_last_resort_advances_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Get the wagon safely onto the High Road.',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: route-planned',
                'Travel route: Phandalin; 480 minutes at current pace.',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-4-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='Gundren, we accept the job. We will take the wagon to Phandalin.',
                topic_focus='accept job and depart',
            )
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-2-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='/travel route phandalin',
                topic_focus='route travel to phandalin',
            )
        )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel advance 5')])
        self.assertEqual(result.invalid_action_retries, 3)

    def test_route_planned_unaccepted_briefing_accepts_before_advancing_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-waterdeep-gundren-briefing',
                'Party goals: Hear Gundren out and decide whether to take the Phandalin job.; Get the wagon safely onto the High Road.',
                'Travel map: lmop_high_road_region_v1',
                'Travel hex: (0,0)',
                'Travel status: route-planned',
                'Travel route: Phandalin; 480 minutes at current pace.',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport, behavior_profile='positive'),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        connector._public_history.append(
            PartyActionRecord(
                controller_id='player-1-controller',
                runtime_mode='storytelling',
                scene_id='scene-waterdeep-gundren-briefing',
                text='/travel route phandalin',
                topic_focus='route travel to phandalin',
            )
        )

        result = connector.run()

        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, we accept the job. We will take the wagon to Phandalin.')],
        )
        self.assertEqual(result.invalid_action_retries, 3)

    def test_stale_high_road_last_resort_routes_idle_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['current_scene_id'] = 'scene-00-high-road-journey'
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel status: idle',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index, controller_id in enumerate(
            ('player-2-controller', 'player-3-controller', 'player-4-controller'),
            start=1,
        ):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=controller_id,
                    runtime_mode='storytelling',
                    scene_id='scene-00-high-road-journey',
                    text=f'I inspect another travel concern {index}.',
                    topic_focus=f'travel concern {index}',
                )
            )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel route phandalin')])
        self.assertEqual(result.invalid_action_retries, 3)

    def test_stale_high_road_last_resort_advances_planned_travel(self) -> None:
        snapshots = self._story_snapshots()
        for snapshot in snapshots.values():
            snapshot['view']['current_scene_id'] = 'scene-00-high-road-journey'
            snapshot['view']['summary_lines'] = [
                'Runtime mode: storytelling',
                'Current scene: scene-00-high-road-journey',
                'Travel status: route_planned',
            ]
        transport = QueueTransport(
            [
                {'output_text': ''},
                {'output_text': 'not json'},
                {'output_text': '```json\n{}\n```'},
            ]
        )
        connector = PartyConnector(
            automation_client=FakeAutomationClient(snapshots),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
            enable_speaker_voting=False,
        )
        for index, controller_id in enumerate(
            ('player-2-controller', 'player-3-controller', 'player-4-controller'),
            start=1,
        ):
            connector._public_history.append(
                PartyActionRecord(
                    controller_id=controller_id,
                    runtime_mode='storytelling',
                    scene_id='scene-00-high-road-journey',
                    text=f'I inspect another planned route concern {index}.',
                    topic_focus=f'planned route concern {index}',
                )
            )

        result = connector.run()

        self.assertEqual(connector.automation_client.submissions, [('player-1-controller', '/travel advance 5')])
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
                            'text': 'Gundren, what warning do you keep softening before we leave?',
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
                enable_speaker_voting=False,
                transcript_logger=PartyTranscriptLogger(transcript_path),
            )
            connector.run()
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()
        self.assertIn('# Live Party Transcript', transcript)
        self.assertIn('[player-1-controller] Gundren, what warning do you keep softening before we leave?', transcript)
        self.assertIn('Gundren: Phandalin still has dangers worth naming carefully.', transcript)

    def test_transcript_logger_dedupes_same_chat_text_when_entry_ids_change(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript-dedupe.log'
        if transcript_path.exists():
            transcript_path.unlink()
        snapshots = self._story_snapshots()
        duplicate_text = 'Gundren Rockseeker: Good! Then it is settled. The wagon is ready.'
        for snapshot in snapshots.values():
            snapshot['view']['chat_entries'] = [
                {
                    'entry_id': 'story-original',
                    'speaker': 'Gundren Rockseeker',
                    'text': duplicate_text,
                    'category': 'story',
                    'visibility': 'public',
                }
            ]
        try:
            logger = PartyTranscriptLogger(transcript_path)
            logger.start(snapshots)
            for snapshot in snapshots.values():
                snapshot['view']['chat_entries'] = [
                    {
                        'entry_id': 'story-replayed-with-new-id',
                        'speaker': 'Gundren Rockseeker',
                        'text': duplicate_text,
                        'category': 'story',
                        'visibility': 'public',
                    }
                ]
            logger.record_snapshots(snapshots)
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertEqual(transcript.count(duplicate_text), 1)

    def test_transcript_logger_ignores_mutated_combat_text_when_entry_id_replays(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript-mutated-combat-id.log'
        if transcript_path.exists():
            transcript_path.unlink()
        snapshots = self._story_snapshots()
        first_text = 'Goblin Ambusher 2 takes 9 force damage; HP 1/10, Temp 0.'
        mutated_replay_text = 'Goblin Ambusher 2 takes 9 force damage; HP 0/10, Temp 0.'
        for snapshot in snapshots.values():
            snapshot['view']['chat_entries'] = [
                {
                    'entry_id': 'encounter-event:211',
                    'speaker': 'System',
                    'text': first_text,
                    'category': 'combat',
                    'visibility': 'public',
                }
            ]
        try:
            logger = PartyTranscriptLogger(transcript_path)
            logger.start(snapshots)
            for snapshot in snapshots.values():
                snapshot['view']['chat_entries'] = [
                    {
                        'entry_id': 'encounter-event:211',
                        'speaker': 'System',
                        'text': mutated_replay_text,
                        'category': 'combat',
                        'visibility': 'public',
                    }
                ]
            logger.record_snapshots(snapshots)
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertIn(first_text, transcript)
        self.assertNotIn(mutated_replay_text, transcript)

    def test_transcript_logger_records_recent_event_summary_lines(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript-recent-events.log'
        if transcript_path.exists():
            transcript_path.unlink()
        snapshots = self._combat_snapshots()
        damage_text = 'Goblin Ambusher 4 takes 11 force damage; HP 0/10, Temp 0.'
        death_text = 'Goblin Ambusher 4 dies.'
        for snapshot in snapshots.values():
            snapshot['view']['chat_entries'] = []
            snapshot['view']['summary_lines'] = [
                'Runtime mode: demo-complete',
                'Recent events:',
                f'  - {damage_text}',
                f'  - {death_text}',
                'The demo is complete. Restart the full story demo to begin a new run.',
            ]
        try:
            logger = PartyTranscriptLogger(transcript_path)
            logger.start(snapshots)
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertIn(f'[chat:public:combat] System: {damage_text}', transcript)
        self.assertIn(f'[chat:public:combat] System: {death_text}', transcript)

    def test_transcript_logger_records_repeated_recent_event_text_after_distinct_rolls(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript-repeated-combat-text.log'
        if transcript_path.exists():
            transcript_path.unlink()
        snapshots = self._combat_snapshots()
        first_roll = 'Player 4 rolled 1 for fire-bolt: total 6.'
        second_roll = 'Player 1 rolled 4 for fire-bolt: total 9.'
        miss_text = 'fire-bolt misses Goblin Ambusher 3.'
        for snapshot in snapshots.values():
            snapshot['view']['chat_entries'] = [
                {
                    'entry_id': 'encounter:0',
                    'speaker': 'System',
                    'text': first_roll,
                    'category': 'combat',
                    'visibility': 'public',
                },
                {
                    'entry_id': 'encounter:1',
                    'speaker': 'System',
                    'text': miss_text,
                    'category': 'combat',
                    'visibility': 'public',
                },
            ]
        try:
            logger = PartyTranscriptLogger(transcript_path)
            logger.start(snapshots)
            for snapshot in snapshots.values():
                snapshot['view']['chat_entries'] = [
                    {
                        'entry_id': 'encounter:0',
                        'speaker': 'System',
                        'text': first_roll,
                        'category': 'combat',
                        'visibility': 'public',
                    },
                    {
                        'entry_id': 'encounter:1',
                        'speaker': 'System',
                        'text': miss_text,
                        'category': 'combat',
                        'visibility': 'public',
                    },
                    {
                        'entry_id': 'encounter:2',
                        'speaker': 'System',
                        'text': second_roll,
                        'category': 'combat',
                        'visibility': 'public',
                    },
                    {
                        'entry_id': 'encounter:3',
                        'speaker': 'System',
                        'text': miss_text,
                        'category': 'combat',
                        'visibility': 'public',
                    },
                ]
            logger.record_snapshots(snapshots)
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertIn(f'[chat:public:combat] System: {first_roll}', transcript)
        self.assertIn(f'[chat:public:combat] System: {second_roll}', transcript)
        self.assertEqual(transcript.count(f'[chat:public:combat] System: {miss_text}'), 2)

    def test_transcript_logger_ignores_nonterminal_recent_event_summary_replay(self) -> None:
        transcript_dir = REPO_ROOT / 'tmp' / 'test_party_connector'
        transcript_dir.mkdir(parents=True, exist_ok=True)
        transcript_path = transcript_dir / 'party-transcript-nonterminal-recent-replay.log'
        if transcript_path.exists():
            transcript_path.unlink()
        snapshots = self._combat_snapshots()
        immutable_damage = 'Goblin Ambusher 1 takes 2 fire damage; HP 8/10, Temp 0.'
        replayed_mutated_damage = 'Goblin Ambusher 1 takes 2 fire damage; HP 1/10, Temp 0.'
        force_damage = 'Goblin Ambusher 1 takes 7 force damage; HP 1/10, Temp 0.'
        for snapshot in snapshots.values():
            snapshot['view']['chat_entries'] = [
                {
                    'entry_id': 'encounter:0',
                    'speaker': 'System',
                    'text': immutable_damage,
                    'category': 'combat',
                    'visibility': 'public',
                }
            ]
            snapshot['view']['summary_lines'] = [
                'Runtime mode: combat',
                'Recent events:',
                f'  - {replayed_mutated_damage}',
                f'  - {force_damage}',
            ]
        try:
            logger = PartyTranscriptLogger(transcript_path)
            logger.start(snapshots)
            transcript = transcript_path.read_text(encoding='utf-8')
        finally:
            if transcript_path.exists():
                transcript_path.unlink()

        self.assertIn(f'[chat:public:combat] System: {immutable_damage}', transcript)
        self.assertNotIn(replayed_mutated_damage, transcript)
        self.assertNotIn(force_damage, transcript)

    def test_party_connector_votes_for_story_speaker_before_action(self) -> None:
        vote_payload = {
            'selected_controller_id': 'player-3-controller',
            'reason': 'Mira has the best logistics fit for wagon supplies and route risk.',
            'advantage_factors': ['logistics fit', 'healthy enough to lead'],
            'confidence': 0.82,
        }
        transport = QueueTransport(
            [
                {'output_text': json.dumps(vote_payload)},
                {'output_text': json.dumps(vote_payload)},
                {'output_text': json.dumps(vote_payload)},
                {'output_text': json.dumps(vote_payload)},
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, before we leave, I want to inspect the wagon supplies and mark what must be protected first.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'wagon supply inspection',
                            'reason': 'Mira was voted to lead the practical logistics beat.',
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
        connector.run()
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-3-controller',
                    'Gundren, before we leave, I want to inspect the wagon supplies and mark what must be protected first.',
                )
            ],
        )
        self.assertEqual([request['payload'].get('metadata', {}).get('request_type') for request in transport.requests[:4]], ['party_speaker_vote'] * 4)
        self.assertEqual(transport.requests[4]['payload'].get('metadata', {}).get('request_type'), 'party_player_turn')
        first_vote_payload = transport.requests[0]['payload']
        vote_context = json.loads(first_vote_payload['input'][0]['content'][0]['text'])
        self.assertEqual(first_vote_payload['max_output_tokens'], 700)
        self.assertEqual(first_vote_payload['thinking'], {'type': 'disabled'})
        self.assertNotIn('character', vote_context['speaker_candidates'][0])
        self.assertLessEqual(len(vote_context['recent_chat_entries']), 6)

    def test_party_connector_collects_speaker_votes_concurrently(self) -> None:
        vote_payload = {
            'selected_controller_id': 'player-3-controller',
            'reason': 'Mira has the best logistics fit for wagon supplies and route risk.',
            'advantage_factors': ['logistics fit', 'healthy enough to lead'],
            'confidence': 0.82,
        }
        action_payload = {
            'decision_type': 'command',
            'text': 'Gundren, before we leave, what supplies most need our eyes on the road?',
            'option_id': None,
            'option_ids': [],
            'topic_focus': 'wagon supply risk',
            'reason': 'Mira was voted to lead the practical logistics beat.',
        }
        transport = BlockingVoteTransport(vote_payload=vote_payload, action_payload=action_payload)
        connector = PartyConnector(
            automation_client=FakeAutomationClient(self._story_snapshots()),
            player_agents=build_default_player_agents(config=self._config(), llm_transport=transport),
            poll_interval_seconds=0.01,
            max_actions=1,
        )

        connector.run()

        self.assertEqual(
            connector.automation_client.submissions,
            [('player-3-controller', 'Gundren, before we leave, what supplies most need our eyes on the road?')],
        )
        self.assertGreaterEqual(transport.max_pending_vote_requests, 4)
        self.assertEqual(
            [request['payload'].get('metadata', {}).get('request_type') for request in transport.requests[:4]],
            ['party_speaker_vote'] * 4,
        )
        self.assertEqual(transport.requests[4]['payload'].get('metadata', {}).get('request_type'), 'party_player_turn')

    def test_party_connector_retries_narrated_speech_as_direct_dialogue(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': "I ask Gundren if it's too little gold up front for equipment.",
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'advance equipment pay',
                            'reason': 'This intentionally uses narrated speech and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, do you think that is too little gold up front? We need equipment before the road.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'advance equipment pay',
                            'reason': 'The retry states the request in the character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, do you think that is too little gold up front? We need equipment before the road.',
                )
            ],
        )

    def test_party_connector_retries_narrated_framing_around_quoted_dialogue(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Leaning forward, I ask, "Gundren, what exactly are we hauling, and who else knows about this shipment?"',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'cargo secrecy',
                            'reason': 'This wraps quoted dialogue in narrated speech and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what exactly are we hauling, and who else knows about this shipment?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'cargo secrecy',
                            'reason': 'The retry uses direct player speech only.',
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
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, what exactly are we hauling, and who else knows about this shipment?')],
        )
        retry_text = transport.requests[1]['payload']['input'][-1]['content'][0]['text']
        self.assertIn('instead of narrated speech', retry_text)

    def test_party_connector_retries_copied_action_template_text(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what signs of danger should we watch for on the road?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'road danger signs',
                            'reason': 'This copies the JSON schema example and should be retried for dataset diversity.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, which part of the route has actually cost you wagons before?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route-specific wagon risk',
                            'reason': 'The retry asks a distinct in-character question.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, which part of the route has actually cost you wagons before?',
                )
            ],
        )
        retry_text = json.dumps(transport.requests[1]['payload'])
        self.assertIn('template example', retry_text)

    def test_party_connector_retries_unknown_story_travel_command_before_submit(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '/travel start',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'start travel',
                            'reason': 'This intentionally chooses an unsupported travel subcommand.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, the road is clear enough now. Let us get the wagon moving toward Phandalin.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'start road travel',
                            'reason': 'The retry uses natural language to advance the scene without an unsupported slash command.',
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
            enable_speaker_voting=False,
        )

        result = connector.run()

        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, the road is clear enough now. Let us get the wagon moving toward Phandalin.',
                )
            ],
        )
        retry_payload = json.dumps(transport.requests[1]['payload'])
        self.assertIn('Unknown travel command. Use /travel status|pace|route|advance|resume|engage.', retry_payload)

    def test_party_connector_retries_quoted_dialogue_with_third_person_self_narration(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '"Gundren, hold still while I check for magic." Seraphine produces a copper wire and begins the ritual of Detect Magic.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic probe',
                            'reason': 'This mixes direct dialogue with third-person narration and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, hold still while I check for lingering magic around you.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic probe',
                            'reason': 'The retry keeps the speech in character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, hold still while I check for lingering magic around you.',
                )
            ],
        )

    def test_party_connector_retries_proper_name_fixes_narrated_dialogue(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': (
                                'Leaning forward, Seraphine fixes Gundren with a steady gaze. '
                                '"How many days to Phandalin, and what exactly is the route?"'
                            ),
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route risk',
                            'reason': 'This mirrors the live proper-name narration failure.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, how many days to Phandalin, and what exactly is the route?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'route risk',
                            'reason': 'The retry keeps the turn in direct character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, how many days to Phandalin, and what exactly is the route?',
                )
            ],
        )

    def test_party_connector_retries_proper_name_kneels_narrated_action(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': (
                                'Seraphine kneels near the torn packs, sorting through the debris for letters. '
                                'She then moves to the horses, checking their tack and saddlebags.'
                            ),
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'ambush evidence',
                            'reason': 'This mirrors the live proper-name action narration failure.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I kneel near the torn packs and sort through the debris for letters, then check the horses, tack, and saddlebags.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'ambush evidence',
                            'reason': 'The retry keeps the action in the character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'I kneel near the torn packs and sort through the debris for letters, then check the horses, tack, and saddlebags.',
                )
            ],
        )

    def test_party_connector_retries_pronoun_adverb_narrated_action(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': (
                                '"Gundren, wait here while I check the tack." '
                                'She then kneels by the horses and checks their saddlebags.'
                            ),
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'horse tack',
                            'reason': 'This uses third-person pronoun narration with an intervening adverb.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, wait here while I check the horses, tack, and saddlebags.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'horse tack',
                            'reason': 'The retry keeps the action in direct character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, wait here while I check the horses, tack, and saddlebags.',
                )
            ],
        )

    def test_party_connector_retries_quoted_dialogue_with_pronoun_self_narration(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': (
                                '"Before we depart, I could examine the wagon for lingering magic." '
                                'She turns to Gundren with a warm, steady gaze. '
                                '"Trust takes time. We will prove ours on the road."'
                            ),
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic trust pledge',
                            'reason': 'This mixes direct dialogue with third-person pronoun narration and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, before we depart, I can examine the wagon for lingering magic. Trust takes time, and we will prove ours on the road.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic trust pledge',
                            'reason': 'The retry keeps the turn in direct character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'Gundren, before we depart, I can examine the wagon for lingering magic. Trust takes time, and we will prove ours on the road.',
                )
            ],
        )

    def test_party_connector_retries_quoted_dialogue_with_broad_pronoun_self_narration(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '"Gundren, what is the pay exactly, and does the job cover provisions?" She eyes the dwarf, a ledger already open in her mind.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'contract provisions',
                            'reason': 'This appends third-person pronoun narration after direct dialogue and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, what is the pay exactly, and does the job cover provisions?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'contract provisions',
                            'reason': 'The retry keeps the turn in direct character voice.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [('player-1-controller', 'Gundren, what is the pay exactly, and does the job cover provisions?')],
        )

    def test_party_connector_retries_quoted_dialogue_with_short_name_action_verb(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': '"Trust? Let\'s make it a two-way street, Gundren." Iri flicks her fingers, and a spectral hand rises from the table. "If I wanted trouble, you\'d know it."',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'two-way trust bargain',
                            'reason': 'This uses a short persona name and an action verb after quoted dialogue.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, trust goes both ways. I want the coin and the road, not trouble, so are we doing this or not?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'two-way trust bargain',
                            'reason': 'The retry keeps the turn in direct character voice.',
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
            enable_speaker_voting=False,
        )
        connector._story_turn_index = 3
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-4-controller',
                    'Gundren, trust goes both ways. I want the coin and the road, not trouble, so are we doing this or not?',
                )
            ],
        )

    def test_party_connector_retries_leading_third_person_persona_action(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Iri rolls her eyes at the ledger copying. "Ledgers? For a dwarf who is burning daylight, you are fine with a scribe pace." She pulls out a copper piece and casts Detect Magic.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic cargo scan',
                            'reason': 'This begins with third-person self narration and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Gundren, if we are burning daylight, let me make this quick: I scan the cargo for magic before we roll out.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'detect magic cargo scan',
                            'reason': 'The retry keeps the action in the character voice.',
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
            enable_speaker_voting=False,
        )
        connector._story_turn_index = 3
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-4-controller',
                    'Gundren, if we are burning daylight, let me make this quick: I scan the cargo for magic before we roll out.',
                )
            ],
        )

    def test_party_connector_retries_leading_third_person_logistics_action(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Mira heads to the stable yard to inspect the wagon: checking the wheels, harness, and how the crates are tied down. "We will want those tarps tight on the Triboar Trail," she mutters, half to herself.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'wagon inspection',
                            'reason': 'This begins with third-person logistics narration and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I head to the stable yard and inspect the wagon: wheels, harness, crate ties, and tarps before we take the Triboar Trail.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'wagon inspection',
                            'reason': 'The retry keeps the action in the character voice.',
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
            enable_speaker_voting=False,
        )
        connector._story_turn_index = 2
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-3-controller',
                    'I head to the stable yard and inspect the wagon: wheels, harness, crate ties, and tarps before we take the Triboar Trail.',
                )
            ],
        )

    def test_party_connector_retries_leading_third_person_observation_action(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Thalen narrows his eyes, studying the dwarf\'s eagerness. "You seem in quite the hurry, Master Rockseeker. What exactly awaits you in Phandalin?"',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'phandalin urgency',
                            'reason': 'This starts with third-person observation narration and should be retried.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'Master Rockseeker, you seem in quite the hurry. What exactly awaits you in Phandalin?',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'phandalin urgency',
                            'reason': 'The retry asks directly in character voice.',
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
            enable_speaker_voting=False,
        )
        connector._story_turn_index = 1
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-2-controller',
                    'Master Rockseeker, you seem in quite the hurry. What exactly awaits you in Phandalin?',
                )
            ],
        )

    def test_party_connector_retries_third_person_scouting_with_embedded_check(self) -> None:
        transport = QueueTransport(
            [
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': "From her spot ahead of the wagon, Seraphine keeps her eyes moving across the landscape. 'Eyes sharp, heart steady,' she murmurs to herself, then whispers a prayer for guidance. /check Perception",
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'scouting for danger with guidance',
                            'reason': 'This uses third-person narration and embeds a slash command in a natural declaration.',
                        }
                    )
                },
                {
                    'output_text': json.dumps(
                        {
                            'decision_type': 'command',
                            'text': 'I move ahead of the wagon and keep my eyes on the brush for anything Sildar warned us about.',
                            'option_id': None,
                            'option_ids': [],
                            'topic_focus': 'scouting for danger',
                            'reason': 'The retry describes the scouting action directly without an embedded slash command.',
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
            enable_speaker_voting=False,
        )
        result = connector.run()
        self.assertEqual(result.invalid_action_retries, 1)
        self.assertEqual(
            connector.automation_client.submissions,
            [
                (
                    'player-1-controller',
                    'I move ahead of the wagon and keep my eyes on the brush for anything Sildar warned us about.',
                )
            ],
        )


if __name__ == '__main__':
    unittest.main()
