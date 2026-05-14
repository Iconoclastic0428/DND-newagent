from __future__ import annotations

from pathlib import Path
import shutil
import unittest

from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.models import Ability
from shared_types.storytelling import StoryCheckRequestState

from dm_agent import (
    CampaignDocument,
    CombatTransitionContext,
    DMStorytellingRuntime,
    LLMClient,
    LLMConfig,
    LLMResponse,
    LLMConfigError,
    ModeSwitchDecisionType,
    RuntimeMode,
    StorytellingTurnContext,
    load_llm_config,
    validate_llm_example,
)
from dm_agent.adjudication import DMAdjudicationPlanner
from shared_types.adjudication import AdjudicationContext


class FakeTransport:
    def __init__(self, payload: dict | list[dict], *, stream_events: list[dict] | None = None) -> None:
        self.payload = payload
        self.stream_events = list(stream_events or [])
        self.requests: list[dict] = []

    def _next_payload(self) -> dict:
        if isinstance(self.payload, list):
            if not self.payload:
                raise AssertionError('No queued payloads remain for this test.')
            return self.payload.pop(0)
        return self.payload

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        if self.stream_events:
            return list(self.stream_events)
        return [{'type': 'response.completed', 'response': self._next_payload()}]


class DMRuntimeTests(unittest.TestCase):
    def test_config_loads_from_env_file(self) -> None:
        root = Path.cwd() / '_dm_runtime_test_artifacts'
        root.mkdir(exist_ok=True)
        env_path = root / '.env'
        try:
            env_path.write_text(
                '\n'.join(
                    [
                        'OPENAI_API_KEY=test-key',
                        'OPENAI_BASE_URL=https://example.invalid/v1',
                        'OPENAI_RESPONSES_MODEL=test-model',
                    ]
                ),
                encoding='utf-8',
            )
            config = load_llm_config(env_path=env_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(config.api_key, 'test-key')
        self.assertEqual(config.base_url, 'https://example.invalid/v1')
        self.assertEqual(config.responses_model, 'test-model')
        self.assertEqual(config.api_format, 'responses')
        self.assertNotIn('test-key', repr(config))

    def test_config_loads_explicit_chat_completions_format(self) -> None:
        root = Path.cwd() / '_dm_runtime_test_artifacts'
        root.mkdir(exist_ok=True)
        env_path = root / '.env'
        try:
            env_path.write_text(
                '\n'.join(
                    [
                        'OPENAI_API_KEY=test-key',
                        'OPENAI_BASE_URL=https://api.deepseek.com',
                        'OPENAI_RESPONSES_MODEL=deepseek-v4-pro',
                        'OPENAI_API_FORMAT=chat_completions',
                    ]
                ),
                encoding='utf-8',
            )
            config = load_llm_config(env_path=env_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(config.base_url, 'https://api.deepseek.com')
        self.assertEqual(config.responses_model, 'deepseek-v4-pro')
        self.assertEqual(config.api_format, 'chat_completions')

    def test_config_validation_rejects_missing_values(self) -> None:
        with self.assertRaises(LLMConfigError):
            LLMConfig(api_key='', base_url='https://example.invalid/v1', responses_model='model')
        with self.assertRaises(LLMConfigError):
            LLMConfig(api_key='x', base_url='not-a-url', responses_model='model')
        with self.assertRaises(LLMConfigError):
            LLMConfig(api_key='x', base_url='https://example.invalid/v1', responses_model='')
        with self.assertRaises(LLMConfigError):
            LLMConfig(api_key='x', base_url='https://example.invalid/v1', responses_model='model', api_format='bad-format')

    def test_env_example_placeholder_validation(self) -> None:
        root = Path.cwd() / '_dm_runtime_test_artifacts'
        root.mkdir(exist_ok=True)
        example_path = root / '.env.example'
        try:
            example_path.write_text(
                '\n'.join(
                    [
                        'OPENAI_API_KEY=replace-with-openai-api-key',
                        'OPENAI_BASE_URL=https://example.invalid/v1',
                        'OPENAI_RESPONSES_MODEL=replace-with-openai-responses-model',
                    ]
                ),
                encoding='utf-8',
            )
            values = validate_llm_example(env_example_path=example_path)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        self.assertEqual(values['OPENAI_API_KEY'], 'replace-with-openai-api-key')

    def test_responses_request_uses_responses_style_payload(self) -> None:
        config = LLMConfig(api_key='test-key', base_url='https://example.invalid/v1', responses_model='test-model')
        client = LLMClient(config, transport=FakeTransport({'output_text': '{"decision_type":"stay_in_storytelling","reason":"keep talking"}'}))
        request = client.build_request(
            instructions='return json',
            input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},),
            metadata={'request_type': 'mode_switch'},
            response_format={'type': 'json_object'},
        )
        payload = request.to_payload()
        self.assertEqual(payload['model'], 'test-model')
        self.assertEqual(payload['input'][0]['role'], 'user')
        self.assertEqual(payload['response_format'], {'type': 'json_object'})

    def test_output_text_prefers_final_assistant_message_over_reasoning(self) -> None:
        response = LLMResponse(
            request=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model')).build_request(
                instructions='json',
                input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},),
            ),
            payload={
                'output': [
                    {'type': 'reasoning', 'content': [{'type': 'reasoning_text', 'text': 'Thinking...'}]},
                    {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': '{"ok": true}'}]},
                ]
            },
        )
        self.assertEqual(response.output_text, '{"ok": true}')

    def test_chat_completions_mode_uses_chat_endpoint_and_payload(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'role': 'assistant', 'content': '{"ok": true}'}}]})
        client = LLMClient(
            LLMConfig(
                api_key='k',
                base_url='https://api.deepseek.com',
                responses_model='deepseek-v4-pro',
                api_format='chat_completions',
            ),
            transport=transport,
        )
        request = client.build_request(
            instructions='Return JSON.',
            input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'ping'}]},),
            metadata={'request_type': 'live_check'},
            response_format={'type': 'json_object'},
            max_output_tokens=64,
        )
        response = client.create_response(request)
        recorded = transport.requests[0]
        self.assertEqual(recorded['url'], 'https://api.deepseek.com/chat/completions')
        self.assertEqual(recorded['payload']['model'], 'deepseek-v4-pro')
        self.assertEqual(recorded['payload']['messages'][0]['role'], 'system')
        self.assertTrue(recorded['payload']['messages'][0]['content'].startswith('Return JSON.'))
        self.assertIn('DeepSeek JSON final-output contract', recorded['payload']['messages'][0]['content'])
        self.assertIn('reviewed by a separate GPT verifier', recorded['payload']['messages'][0]['content'])
        self.assertIn('Do not emit markdown fences, backticks, prose', recorded['payload']['messages'][0]['content'])
        self.assertEqual(recorded['payload']['messages'][1], {'role': 'user', 'content': 'ping'})
        self.assertEqual(recorded['payload']['max_tokens'], 64)
        self.assertEqual(recorded['payload']['thinking'], {'type': 'enabled'})
        self.assertEqual(recorded['payload']['reasoning_effort'], 'high')
        self.assertEqual(recorded['payload']['response_format'], {'type': 'json_object'})
        self.assertNotIn('metadata', recorded['payload'])
        self.assertEqual(response.output_text, '{"ok": true}')

    def test_chat_completions_non_json_request_does_not_add_json_hardening(self) -> None:
        transport = FakeTransport({'choices': [{'message': {'role': 'assistant', 'content': 'ok'}}]})
        client = LLMClient(
            LLMConfig(
                api_key='k',
                base_url='https://api.deepseek.com',
                responses_model='deepseek-v4-pro',
                api_format='chat_completions',
            ),
            transport=transport,
        )
        request = client.build_request(
            instructions='Answer plainly.',
            input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'ping'}]},),
            max_output_tokens=64,
        )
        client.create_response(request)
        recorded = transport.requests[0]
        self.assertEqual(recorded['payload']['messages'][0], {'role': 'system', 'content': 'Answer plainly.'})
        self.assertNotIn('thinking', recorded['payload'])
        self.assertNotIn('reasoning_effort', recorded['payload'])

    def test_chat_completions_stream_accumulates_output_and_reasoning(self) -> None:
        transport = FakeTransport(
            {'unused': True},
            stream_events=[
                {'choices': [{'delta': {'reasoning_content': 'Thinking.'}}]},
                {'choices': [{'delta': {'content': '{"ok"'}}]},
                {'choices': [{'delta': {'content': ': true}'}}]},
            ],
        )
        client = LLMClient(
            LLMConfig(
                api_key='k',
                base_url='https://api.deepseek.com',
                responses_model='deepseek-v4-pro',
                api_format='chat_completions',
            ),
            transport=transport,
        )
        request = client.build_request(
            instructions='json',
            input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},),
            response_format={'type': 'json_object'},
        )
        events = []
        response = client.create_response(request, stream_handler=events.append)
        self.assertEqual([event.kind for event in events], ['reasoning', 'output', 'output'])
        self.assertEqual(response.output_text, '{"ok": true}')

    def test_streamed_response_emits_reasoning_and_returns_final_payload(self) -> None:
        transport = FakeTransport(
            {'unused': True},
            stream_events=[
                {'type': 'response.reasoning_text.delta', 'delta': 'Thinking...'},
                {'type': 'response.completed', 'response': {'output': [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': '{"ok": true}'}]}]}},
            ],
        )
        client = LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport)
        request = client.build_request(
            instructions='json',
            input_messages=({'role': 'user', 'content': [{'type': 'input_text', 'text': 'hi'}]},),
            response_format={'type': 'json_object'},
        )
        events = []
        response = client.create_response(request, stream_handler=events.append)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, 'reasoning')
        self.assertEqual(events[0].text, 'Thinking...')
        self.assertEqual(response.output_text, '{"ok": true}')

    def test_story_turn_parser_accepts_visibility_alias_and_speaker_id(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"The tavern stays loud around the table.",'
                                    '"transcript_entries":[{"speaker_id":"player-3","text":"I try to lift Gundren\'s purse.","visibility":"private"}],'
                                    '"check_request":null,'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"test"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-3-controller',
            actor_id='player-3',
            declaration='pickpocket',
            available_actor_ids=('player-3',),
            available_combatant_actor_ids=('player-3', 'monster-goblin-1'),
        )
        self.assertEqual(decision.transcript_entries[1].speaker, 'player-3')
        self.assertEqual(decision.transcript_entries[1].visibility.value, 'dm-only')

    def test_story_turn_parser_drops_redundant_public_narration(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"Gundren Rockseeker crosses his arms and waits for your decision.",'
                                    '"transcript_entries":[{"speaker":"DM","text":"Gundren Rockseeker crosses his arms and waits for your decision.","visibility":"public"}],'
                                    '"check_request":null,'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"test"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='What now?',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )

        self.assertEqual(len(decision.transcript_entries), 1)
        self.assertEqual(decision.transcript_entries[0].speaker, 'DM')

    def test_story_turn_parser_drops_paraphrased_public_narration(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"Gundren grins broadly and claps you on the shoulder. '
                                    "Excellent! The wagon's loaded and waiting at the stable yard. "
                                    'We will ride ahead tonight. You will catch up to us on the road.",'
                                    '"transcript_entries":[{"speaker":"Gundren Rockseeker","text":"Excellent! '
                                    "The wagon's ready at the stable yard. We'll ride ahead--catch you in Phandalin!"
                                    '","visibility":"public"}],'
                                    '"check_request":null,'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"test"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='What now?',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )

        self.assertEqual(len(decision.transcript_entries), 1)
        self.assertEqual(decision.transcript_entries[0].speaker, 'Gundren Rockseeker')

    def test_story_turn_parser_keeps_distinct_public_narration_and_dialogue(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"The tavern quiets as Sildar studies the map.",'
                                    '"transcript_entries":[{"speaker":"Gundren Rockseeker","text":"Well? What is your call?","visibility":"public"}],'
                                    '"check_request":null,'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"test"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='What now?',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )

        self.assertEqual(len(decision.transcript_entries), 2)
        self.assertEqual(decision.transcript_entries[0].speaker, 'DM')
        self.assertEqual(decision.transcript_entries[1].speaker, 'Gundren Rockseeker')

    def test_story_turn_retries_with_exact_error_and_template(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': '{"public_narration": "broken"'}],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"Gundren answers cautiously.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":null,'
                                        '"memory_note":"retry ok"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(
            campaign_id='lmop',
            mode=RuntimeMode.STORYTELLING,
            current_scene_id='scene-1',
            current_location_id='waterdeep',
            party_goal_summary='take the job',
        )
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='hello',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )
        self.assertEqual(decision.public_narration, 'Gundren answers cautiously.')
        self.assertEqual(len(transport.requests), 2)
        retry_payload = transport.requests[1]['payload']
        self.assertIn('Expecting', retry_payload['input'][-1]['content'][0]['text'])
        self.assertIn('required_json_template', retry_payload['input'][-1]['content'][0]['text'])
        self.assertIn('public_narration', retry_payload['instructions'])
        self.assertIn('The first non-whitespace character of your reply must be `{`', retry_payload['instructions'])
        self.assertIn('Do not emit ```json, ```JSON, or ``` anywhere in the reply.', retry_payload['instructions'])
        self.assertIn('reviewed by a separate GPT verifier', retry_payload['instructions'])
        self.assertIn('Do not emit wrapper keys such as json, response, data, result, or output', retry_payload['instructions'])


    def test_story_turn_prompt_explicitly_requires_bare_json_object(self) -> None:
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=FakeTransport({'output_text': '{}'})),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(
            campaign_id='lmop',
            mode=RuntimeMode.STORYTELLING,
            current_scene_id='scene-1',
            current_location_id='waterdeep',
            party_goal_summary='take the job',
        )
        payload = runtime._build_story_turn_prompt(
            context,
            type('Selection', (), {'documents': ()})(),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='hello',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
            actors_with_resolved_scene_checks=(),
        )
        self.assertIn('The first non-whitespace character of your reply must be `{`', payload['instructions'])
        self.assertIn('do not emit ```json, ```json, or ``` anywhere in the reply.', payload['instructions'].lower())
        self.assertIn('Return exactly one JSON object and nothing else.', payload['instructions'])
        self.assertIn('reviewed by a separate GPT verifier', payload['instructions'])
        self.assertIn('Do not emit wrapper keys such as json, response, data, result, or output', payload['instructions'])

    def test_adjudication_prompt_explicitly_requires_bare_json_object(self) -> None:
        planner = DMAdjudicationPlanner(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=FakeTransport({'output_text': '{}'})),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = AdjudicationContext(
            campaign_id='lmop',
            runtime_mode='storytelling',
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='I try something unusual.',
            current_scene_id='scene-1',
            current_location_id='waterdeep',
            active_actor_id=None,
            party_goal_summary='take the job',
            recent_summary='The tavern is noisy.',
            unresolved_hooks=(),
            visible_actor_summaries=(),
            nearby_feature_summaries=(),
            actor_status_summary='',
            action_economy_summary='',
            allowed_template_ids=(),
            allowed_illusion_template_ids=(),
            allowed_operation_types=('update_scene_state_note',),
        )
        payload = planner._build_prompt(context, ())
        self.assertIn('The first non-whitespace character of your reply must be `{`', payload['instructions'])
        self.assertIn('do not emit ```json, ```json, or ``` anywhere in the reply.', payload['instructions'].lower())
        self.assertIn('Return exactly one JSON object and nothing else.', payload['instructions'])
        self.assertIn('reviewed by a separate GPT verifier', payload['instructions'])
        self.assertIn('Do not emit wrapper keys such as json, response, data, result, or output', payload['instructions'])
        self.assertIn('never leave operation_type blank', payload['instructions'])

    def test_adjudication_parser_ignores_blank_operation_placeholders(self) -> None:
        planner = DMAdjudicationPlanner(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=FakeTransport({'output_text': '{}'})),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        plan = planner._parse_plan_payload(
            {
                'action_summary': 'Player 1 checks the wagon straps.',
                'doable': True,
                'adjudication_type': 'automatic_success',
                'reasoning_summary_for_dm': 'The action is simple and needs no state mutation.',
                'clarification_request': None,
                'check_request': None,
                'save_request': None,
                'contest_request': None,
                'attack_request': None,
                'action_cost_recommendation': None,
                'improvised_objects_to_create': [],
                'terrain_changes_to_create': [],
                'operation_plan': [{'operation_type': '', 'note': ''}],
                'on_success': {'public_text': 'The wagon straps look secure.', 'dm_note': '', 'operations': [{'operation_type': ''}]},
                'on_failure': None,
                'on_partial': None,
                'mode_switch_recommendation': None,
            },
            raw_response_text='{}',
        )
        self.assertEqual(plan.operation_plan, ())
        self.assertIsNotNone(plan.on_success)
        self.assertEqual(plan.on_success.operations, ())

    def test_story_turn_retries_after_schema_validation_error(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The wagon jolts.",'
                                        '"transcript_entries":[{"speaker":"DM","text":"Hold it steady.","visibility":"private-ish"}],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":null,'
                                        '"memory_note":"bad visibility"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The wagon jolts.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":null,'
                                        '"memory_note":"fixed"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='steady the wagon',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )
        self.assertEqual(decision.public_narration, 'The wagon jolts.')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('Each transcript entry requires speaker, text, and a valid visibility.', transport.requests[1]['payload']['input'][-1]['content'][0]['text'])



    def test_story_turn_retries_when_same_actor_already_checked_this_scene(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"You steady yourself and look for signs in the brush.",'
                                        '"transcript_entries":[], '
                                        '"check_request":{'
                                        '"actor_id":"player-1","ability":"WIS","skill_name":"Perception","dc":12,'
                                        '"prompt":"Roll Wisdom (Perception).",'
                                        '"reason":"Look for danger.",'
                                        '"requires_sight":true,"requires_hearing":false,"interacting_with_actor_id":null},'
                                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"bad repeat"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"You already judged the brush once; now the tension sharpens as the wagon rolls on.",'
                                        '"transcript_entries":[], '
                                        '"check_request":null,'
                                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"no second check"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-00-high-road-journey', current_location_id='high-road', party_goal_summary='reach town')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='I keep driving and scan the road again.',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
            actors_with_resolved_scene_checks=('player-1',),
        )
        self.assertIsNone(decision.check_request)
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('A player can receive at most one story check per scene.', transport.requests[1]['payload']['input'][-1]['content'][0]['text'])

    def test_story_turn_retries_when_check_targets_a_different_actor(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The brush goes still around the wagon.",'
                                        '"transcript_entries":[], '
                                        '"check_request":{'
                                        '"actor_id":"player-2","ability":"WIS","skill_name":"Perception","dc":12,'
                                        '"prompt":"Roll Wisdom (Perception).",'
                                        '"reason":"Look for danger in the brush.",'
                                        '"requires_sight":true,"requires_hearing":false,"interacting_with_actor_id":null},'
                                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"bad actor"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The wagon keeps rolling as you tighten your grip on the reins.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,"mode_switch_decision":null,"memory_note":"no handoff"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-00-high-road-journey', current_location_id='high-road', party_goal_summary='reach town')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='I keep driving but watch the tree line.',
            available_actor_ids=('player-1', 'player-2'),
            available_combatant_actor_ids=('player-1', 'player-2', 'monster-goblin-1'),
        )
        self.assertIsNone(decision.check_request)
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('Story check requests must target the acting actor for this turn.', transport.requests[1]['payload']['input'][-1]['content'][0]['text'])

    def test_story_turn_retry_handler_receives_each_retry(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': '{not json'}],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The road stretches on.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":null,'
                                        '"memory_note":"retry ok"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        seen = []
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='keep driving',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
            retry_handler=lambda attempt, max_attempts, error: seen.append((attempt, max_attempts, error)),
        )
        self.assertEqual(decision.public_narration, 'The road stretches on.')
        self.assertEqual(seen[0][0:2], (2, 3))
        self.assertIn('LLM response did not contain valid JSON', seen[0][2])

    def test_story_turn_allows_third_attempt_before_failing(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': '{not json'}],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': '{still not json'}],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"The road stretches on.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":null,'
                                        '"memory_note":"third try"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-1-controller',
            actor_id='player-1',
            declaration='keep driving',
            available_actor_ids=('player-1',),
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )
        self.assertEqual(decision.public_narration, 'The road stretches on.')
        self.assertEqual(len(transport.requests), 3)

    def test_story_turn_parser_accepts_full_ability_name_alias(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"Gundren is distracted by the conversation.",'
                                    '"transcript_entries":[],'
                                    '"check_request":{'
                                    '"actor_id":"player-3",'
                                    '"ability":"DEXTERITY",'
                                    '"skill_name":"Sleight of Hand",'
                                    '"dc":15,'
                                    '"prompt":"Roll Dexterity (Sleight of Hand).",'
                                    '"reason":"Pickpocket attempt.",'
                                    '"requires_sight":true,'
                                    '"requires_hearing":false,'
                                    '"interacting_with_actor_id":"gundren-rockseeker"'
                                    '},'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"test"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        decision, _ = runtime.plan_story_turn(
            context,
            (),
            controller_id='player-3-controller',
            actor_id='player-3',
            declaration='pickpocket',
            available_actor_ids=('player-3',),
            available_combatant_actor_ids=('player-3', 'monster-goblin-1'),
        )
        self.assertEqual(decision.check_request.check_request.ability.value, 'DEX')



    def test_check_outcome_retries_when_enter_combat_plan_is_missing(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"Goblin arrows suddenly fly from the brush.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":{'
                                        '"decision_type":"enter_combat",'
                                        '"reason":"Ambush triggered.",'
                                        '"confidence":0.9'
                                        '},'
                                        '"memory_note":"bad plan"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{'
                                        '"public_narration":"Goblin arrows suddenly fly from the brush.",'
                                        '"transcript_entries":[],'
                                        '"check_request":null,'
                                        '"scene_update":null,'
                                        '"mode_switch_decision":{'
                                        '"decision_type":"enter_combat",'
                                        '"reason":"Ambush triggered.",'
                                        '"enter_combat_plan":{'
                                        '"reason":"Ambush triggered.",'
                                        '"participant_ids":["player-1","monster-goblin-1"],'
                                        '"scene_id":"scene-triboar-goblin-ambush",'
                                        '"location_id":"triboar-trail",'
                                        '"battlefield_map_id":"goblin-ambush-triboar-trail"'
                                        '},'
                                        '"confidence":0.95'
                                        '},'
                                        '"memory_note":"good plan"'
                                        '}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        pending_check = StoryCheckRequestState(
            request_id='story-check-player-1',
            actor_id='player-1',
            prompt='Keep watch on the trail.',
            reason='Scan for danger.',
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id='story-check-player-1',
                    source_actor_id=None,
                    target_actor_id='player-1',
                    reason='Scan for danger.',
                ),
                ability=Ability.WIS,
                dc=13,
                skill_name='Perception',
            ),
        )
        decision, _ = runtime.plan_check_outcome(
            context,
            (
                CampaignDocument(
                    doc_id='scene-triboar-goblin-ambush',
                    path='campaigns/lmop/chapters/chapter-01/scene-01-goblin-ambush.md',
                    title='Goblin Ambush',
                    type='scene',
                    campaign='lmop',
                    content='goblin ambush',
                    canonical_location='triboar-trail',
                ),
            ),
            pending_check=pending_check,
            result_total=14,
            success=True,
            selected_roll=12,
            declaration='I keep watch on the trail.',
            available_combatant_actor_ids=('player-1', 'monster-goblin-1'),
        )
        self.assertIsNotNone(decision.mode_switch_decision)
        self.assertEqual(decision.mode_switch_decision.enter_combat_plan.participant_ids, ('player-1', 'monster-goblin-1'))
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('Enter-combat decisions require an enter_combat_plan object.', transport.requests[1]['payload']['input'][-1]['content'][0]['text'])

    def test_check_outcome_prompt_marks_rules_engine_result_as_final(self) -> None:
        transport = FakeTransport(
            {
                'output': [
                    {
                        'type': 'message',
                        'role': 'assistant',
                        'content': [
                            {
                                'type': 'output_text',
                                'text': (
                                    '{'
                                    '"public_narration":"Gundren narrows his eyes.",'
                                    '"transcript_entries":[],'
                                    '"check_request":null,'
                                    '"scene_update":null,'
                                    '"mode_switch_decision":null,'
                                    '"memory_note":"resolved"'
                                    '}'
                                ),
                            }
                        ],
                    }
                ]
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(campaign_id='lmop', mode=RuntimeMode.STORYTELLING, current_scene_id='scene-1', current_location_id='waterdeep', party_goal_summary='take the job')
        pending_check = StoryCheckRequestState(
            request_id='story-check-player-3',
            actor_id='player-3',
            prompt="Pick Gundren's pocket.",
            reason='Steal from Gundren without notice.',
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id='story-check-player-3',
                    source_actor_id=None,
                    target_actor_id='player-3',
                    reason='Steal from Gundren without notice.',
                ),
                ability=Ability.DEX,
                dc=15,
                skill_name='Sleight of Hand',
                interacting_with_actor_id='gundren-rockseeker',
            ),
        )
        decision, _ = runtime.plan_check_outcome(
            context,
            (),
            pending_check=pending_check,
            result_total=17,
            success=True,
            selected_roll=14,
            declaration="I try to pick Gundren's pocket.",
            available_combatant_actor_ids=('player-3', 'monster-goblin-1', 'monster-goblin-2'),
        )
        self.assertEqual(decision.public_narration, 'Gundren narrows his eyes.')
        payload = transport.requests[0]['payload']
        self.assertIn('already rolled and finalized by the deterministic rules engine', payload['instructions'])
        self.assertIn('must interpret that result and describe consequences', payload['instructions'])
        self.assertIn('"rolled_by": "rules_engine"', payload['input'][0]['content'][0]['text'])
        self.assertIn('"selected_roll": 14', payload['input'][0]['content'][0]['text'])
        self.assertIn('"dc": 15', payload['input'][0]['content'][0]['text'])
        self.assertIn('"available_combatant_actor_ids": ["player-3", "monster-goblin-1", "monster-goblin-2"]', payload['input'][0]['content'][0]['text'])

    def test_mode_switch_decision_parses_enter_combat_and_exit_combat(self) -> None:
        transport = FakeTransport(
            {
                'output_text': (
                    '{"decision_type":"enter_combat","reason":"hostiles attack","confidence":0.9,'
                    '"enter_combat_plan":{"reason":"hostiles attack","participant_ids":["pc-1","goblin-1"],"scene_id":"scene-1","location_id":"triboar-trail","ambush":true,"battlefield_map_id":"goblin-ambush-triboar-trail"}}'
                )
            }
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(
            campaign_id='lmop',
            mode=RuntimeMode.STORYTELLING,
            current_scene_id='scene-1',
            current_location_id='triboar-trail',
            party_goal_summary='reach town',
            unresolved_hooks=('goblins nearby',),
            current_scene_summary='The trail is quiet.',
        )
        docs = (
            CampaignDocument(
                doc_id='scene-1',
                path='campaigns/lmop/chapters/chapter-01/scene-01.md',
                title='Scene 1',
                type='scene',
                campaign='lmop',
                content='goblin ambush',
                tags=('goblin', 'ambush'),
                canonical_location='triboar-trail',
            ),
        )
        decision, events = runtime.decide_mode_switch(context, docs, current_mode=RuntimeMode.STORYTELLING)
        self.assertEqual(decision.decision_type, ModeSwitchDecisionType.ENTER_COMBAT)
        self.assertEqual(decision.enter_combat_plan.participant_ids, ('pc-1', 'goblin-1'))
        self.assertEqual(decision.enter_combat_plan.location_id, 'triboar-trail')
        self.assertEqual(decision.enter_combat_plan.battlefield_map_id, 'goblin-ambush-triboar-trail')
        self.assertTrue(any(event.__class__.__name__ == 'LLMRequestIssuedEvent' for event in events))
        self.assertTrue(any(event.__class__.__name__ == 'LLMResponseAcceptedEvent' for event in events))
        self.assertEqual(len(transport.requests), 1)


    def test_mode_switch_decision_retries_when_enter_combat_scene_metadata_is_invalid(self) -> None:
        transport = FakeTransport(
            [
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{"decision_type":"enter_combat","reason":"hostiles attack","confidence":0.9,'
                                        '"enter_combat_plan":{"reason":"hostiles attack","participant_ids":["pc-1","goblin-1"],"scene_id":"scene-unknown","location_id":"triboar-trail","ambush":true,"battlefield_map_id":"goblin-ambush-triboar-trail"}}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
                {
                    'output': [
                        {
                            'type': 'message',
                            'role': 'assistant',
                            'content': [
                                {
                                    'type': 'output_text',
                                    'text': (
                                        '{"decision_type":"enter_combat","reason":"hostiles attack","confidence":0.9,'
                                        '"enter_combat_plan":{"reason":"hostiles attack","participant_ids":["pc-1","goblin-1"],"scene_id":"scene-1","location_id":"triboar-trail","ambush":true,"battlefield_map_id":"goblin-ambush-triboar-trail"}}'
                                    ),
                                }
                            ],
                        }
                    ]
                },
            ]
        )
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(
            campaign_id='lmop',
            mode=RuntimeMode.STORYTELLING,
            current_scene_id='scene-00-high-road-journey',
            current_location_id='high-road',
            party_goal_summary='reach town',
            unresolved_hooks=('goblins nearby',),
            current_scene_summary='The road is tense.',
        )
        docs = (
            CampaignDocument(
                doc_id='scene-00-high-road-journey',
                path='campaigns/lmop/chapters/chapter-01/scene-00-high-road-journey.md',
                title='High Road Journey',
                type='scene',
                campaign='lmop',
                content='Travel scene that links to the ambush.',
                tags=('travel', 'road'),
                canonical_location='high-road',
            ),
            CampaignDocument(
                doc_id='scene-1',
                path='campaigns/lmop/chapters/chapter-01/scene-01.md',
                title='Scene 1',
                type='scene',
                campaign='lmop',
                content='goblin ambush',
                tags=('goblin', 'ambush'),
                canonical_location='triboar-trail',
            ),
        )
        decision, _ = runtime.decide_mode_switch(context, docs, current_mode=RuntimeMode.STORYTELLING)
        self.assertEqual(decision.enter_combat_plan.scene_id, 'scene-1')
        self.assertEqual(len(transport.requests), 2)
        self.assertIn('Enter-combat decisions must transition to a retrieved scene id.', transport.requests[1]['payload']['input'][-1]['content'][0]['text'])

    def test_document_selection_is_selective(self) -> None:
        transport = FakeTransport({'output_text': '{"decision_type":"stay_in_storytelling","reason":"hold"}'})
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = StorytellingTurnContext(
            campaign_id='lmop',
            mode=RuntimeMode.STORYTELLING,
            current_scene_id='scene-triboar-goblin-ambush',
            current_location_id='triboar-trail',
            party_goal_summary='investigate ambush',
            unresolved_hooks=('goblin ambush',),
            current_scene_summary='A trail ambush occurred.',
        )
        docs = (
            CampaignDocument(
                doc_id='scene-triboar-goblin-ambush',
                path='campaigns/lmop/chapters/chapter-01/scene-01-goblin-ambush.md',
                title='Goblin Ambush',
                type='scene',
                campaign='lmop',
                content='goblins',
                tags=('ambush', 'trail'),
                canonical_location='triboar-trail',
                retrieval_keywords=('ambush', 'goblins'),
            ),
            CampaignDocument(
                doc_id='npc-sildar-hallwinter',
                path='campaigns/lmop/npcs/sildar-hallwinter.md',
                title='Sildar',
                type='npc',
                campaign='lmop',
                content='advisor',
                tags=('ally',),
                canonical_location='phandalin',
            ),
        )
        selection = runtime.select_relevant_documents(context, docs)
        self.assertEqual(selection.documents[0].doc_id, 'scene-triboar-goblin-ambush')
        self.assertEqual(selection.selection_reason, 'selected by scene/location/tag relevance')

    def test_mode_decision_is_typed_and_does_not_mutate_state(self) -> None:
        transport = FakeTransport({'output_text': '{"decision_type":"exit_combat","reason":"combat resolved","exit_combat_plan":{"reason":"combat resolved","preserve_scene_state":true}}'})
        runtime = DMStorytellingRuntime(
            client=LLMClient(LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'), transport=transport),
            config=LLMConfig(api_key='k', base_url='https://example.invalid/v1', responses_model='model'),
        )
        context = CombatTransitionContext(
            campaign_id='lmop',
            mode=RuntimeMode.COMBAT,
            reason='combat resolved',
            suggested_participants=('pc-1', 'goblin-1'),
            current_scene_id='scene-1',
            current_location_id='triboar-trail',
        )
        decision, _ = runtime.decide_mode_switch(context, (), current_mode=RuntimeMode.COMBAT)
        self.assertEqual(decision.decision_type, ModeSwitchDecisionType.EXIT_COMBAT)
        self.assertEqual(decision.exit_combat_plan.reason, 'combat resolved')
        self.assertEqual(context.mode, RuntimeMode.COMBAT)


if __name__ == '__main__':
    unittest.main()
