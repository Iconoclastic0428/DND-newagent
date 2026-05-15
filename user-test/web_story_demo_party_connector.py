from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import time
from typing import Any

from dm_agent.client import LLMClient
from dm_agent.config import LLMConfig, load_llm_config
from dm_agent.json_contract import build_json_object_contract, build_json_retry_contract
from web_story_demo_live_runner import AutomationHttpClient, LiveWebStoryDemoError


PLAYER_CONTROLLER_IDS = (
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)

_ACTION_DECISION_TEMPLATE = json.dumps(
    {
        'decision_type': 'command',
        'text': 'I ask Gundren what signs of danger he expects on the road.',
        'option_id': None,
        'option_ids': [],
        'topic_focus': 'road danger signs',
        'reason': 'Short explanation of why this fits the persona and current state.',
    },
    separators=(',', ':'),
)

_STOPWORDS = {
    'a',
    'an',
    'and',
    'are',
    'as',
    'at',
    'be',
    'by',
    'for',
    'from',
    'i',
    'in',
    'into',
    'is',
    'it',
    'my',
    'of',
    'on',
    'or',
    'our',
    'that',
    'the',
    'their',
    'them',
    'they',
    'this',
    'to',
    'us',
    'we',
    'with',
    'you',
    'your',
}


class PartyConnectorError(RuntimeError):
    pass


class PartyActionPlanningError(PartyConnectorError):
    def __init__(self, message: str, *, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output


@dataclass(frozen=True)
class PlayerPersona:
    controller_id: str
    codename: str
    personality: str
    story_focus: str
    combat_style: str
    coordination_rule: str


@dataclass(frozen=True)
class PartyActionDecision:
    decision_type: str
    text: str
    option_id: str | None
    option_ids: tuple[str, ...]
    topic_focus: str
    reason: str


@dataclass(frozen=True)
class PartyActionRecord:
    controller_id: str
    runtime_mode: str
    scene_id: str | None
    text: str
    topic_focus: str


@dataclass(frozen=True)
class PartyConnectorResult:
    turns_taken: int
    commands_sent: int
    prompt_responses_sent: int
    invalid_action_retries: int
    final_runtime_mode: str | None
    final_scene_id: str | None


@dataclass
class PartyTranscriptLogger:
    path: Path
    _seen_chat_entry_ids: set[str] = field(default_factory=set, init=False, repr=False)
    _seen_prompt_keys: set[str] = field(default_factory=set, init=False, repr=False)
    _started: bool = field(default=False, init=False, repr=False)

    def start(self, snapshots: dict[str, dict[str, Any]]) -> None:
        if self._started:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text('# Live Party Transcript\n\n', encoding='utf-8')
        self._started = True
        self._append(f'[start] controllers: {", ".join(PLAYER_CONTROLLER_IDS)}')
        self.record_snapshots(snapshots)

    def record_player_action(self, controller_id: str, decision: PartyActionDecision) -> None:
        self._append(f'[{controller_id}] {decision.text}')

    def record_system_action(self, actor: str, text: str) -> None:
        self._append(f'[system:{actor}] {text}')

    def record_snapshots(self, snapshots: dict[str, dict[str, Any]]) -> None:
        for controller_id in ('dm',) + PLAYER_CONTROLLER_IDS:
            snapshot = snapshots.get(controller_id)
            if not isinstance(snapshot, dict):
                continue
            view = _view_from_snapshot(snapshot)
            for entry in view.get('chat_entries', []):
                if not isinstance(entry, dict):
                    continue
                entry_id = entry.get('entry_id')
                if not isinstance(entry_id, str) or not entry_id or entry_id in self._seen_chat_entry_ids:
                    continue
                visibility = entry.get('visibility')
                if visibility not in {'public', 'dm_only'}:
                    continue
                self._seen_chat_entry_ids.add(entry_id)
                speaker = entry.get('speaker') or 'Unknown'
                category = entry.get('category') or 'story'
                text = entry.get('text') or ''
                self._append(f'[chat:{visibility}:{category}] {speaker}: {text}')
            prompt = snapshot.get('prompt')
            if not isinstance(prompt, dict):
                continue
            prompt_kind = prompt.get('prompt_kind') or 'prompt'
            prompt_text = prompt.get('text') or ''
            prompt_id = prompt.get('prompt_id') or f'{controller_id}:{prompt_kind}:{prompt_text}'
            prompt_key = f'{controller_id}:{prompt_id}'
            if prompt_key in self._seen_prompt_keys:
                continue
            self._seen_prompt_keys.add(prompt_key)
            self._append(f'[prompt:{controller_id}:{prompt_kind}] {prompt_text}')

    def _append(self, line: str) -> None:
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(f'{line}\n')


DEFAULT_PERSONAS: dict[str, PlayerPersona] = {
    'player-1-controller': PlayerPersona(
        controller_id='player-1-controller',
        codename='Seraphine Vale',
        personality='Warm, sincere, and protective. You calm people down, build trust, and look for emotional truth before force.',
        story_focus='relationships, reassurance, and promises people are afraid to make aloud',
        combat_style='Protect allies, stabilize chaotic scenes, and use magic to create clean advantages instead of brute repetition.',
        coordination_rule='If another player opens a topic, either deepen it from an emotional angle or deliberately shift to a different unresolved thread.',
    ),
    'player-2-controller': PlayerPersona(
        controller_id='player-2-controller',
        codename='Thalen Marr',
        personality='Measured, skeptical, and scholarly. You care about patterns, contradictions, magical details, and hidden structure.',
        story_focus='clues, lore, magical anomalies, and inconsistencies in what NPCs say',
        combat_style='Use precise spells and information-rich actions; solve the tactical puzzle rather than showing off.',
        coordination_rule='Do not repeat social reassurance or logistics. Contribute new analysis, a pointed follow-up, or a technically useful spell/item idea.',
    ),
    'player-3-controller': PlayerPersona(
        controller_id='player-3-controller',
        codename='Mira Ashdown',
        personality='Practical, dry, and relentlessly prepared. You think about routes, supplies, leverage, and what will keep the party alive tomorrow.',
        story_focus='travel plans, equipment, terrain, fallback options, and getting value from items or downtime',
        combat_style='Exploit terrain, visibility, positioning, and practical item use. End turns cleanly once the plan is executed.',
        coordination_rule='If the last player handled talk or lore, move the scene forward with logistics, procedure, or a concrete resourceful action.',
    ),
    'player-4-controller': PlayerPersona(
        controller_id='player-4-controller',
        codename='Iri Sunfell',
        personality='Bold, curious, and slightly irreverent. You take risks, make scenes lively, and look for clever spell or item usage that changes the tempo.',
        story_focus='provocations, misdirection, tests of nerve, and surprising but useful magical or item play',
        combat_style='Be inventive without being reckless: create openings, force reactions, and use spells/items in interesting legal ways.',
        coordination_rule='Do not echo the previous player. Either cap their point with a daring next step or pivot hard to a fresh angle.',
    ),
}


class PlayerAgent:
    def __init__(self, *, persona: PlayerPersona, client: LLMClient) -> None:
        self.persona = persona
        self.client = client

    def plan_action(
        self,
        snapshot: dict[str, Any],
        *,
        public_party_memory: list[PartyActionRecord],
        previous_output: str | None = None,
        error_message: str | None = None,
        attempt_number: int = 1,
    ) -> tuple[PartyActionDecision, str]:
        request = self._build_request(
            snapshot,
            public_party_memory=public_party_memory,
            previous_output=previous_output,
            error_message=error_message,
            attempt_number=attempt_number,
        )
        response = self.client.create_response(request)
        output_text = response.output_text
        try:
            return _parse_action_decision(output_text), output_text
        except PartyConnectorError as exc:
            raise PartyActionPlanningError(str(exc), raw_output=output_text) from exc

    def _build_request(
        self,
        snapshot: dict[str, Any],
        *,
        public_party_memory: list[PartyActionRecord],
        previous_output: str | None,
        error_message: str | None,
        attempt_number: int,
    ):
        view = _view_from_snapshot(snapshot)
        prompt = snapshot.get('prompt')
        context_payload = {
            'persona': {
                'codename': self.persona.codename,
                'personality': self.persona.personality,
                'story_focus': self.persona.story_focus,
                'combat_style': self.persona.combat_style,
                'coordination_rule': self.persona.coordination_rule,
            },
            'controller_id': self.persona.controller_id,
            'runtime_mode': view.get('runtime_mode'),
            'current_scene_id': view.get('current_scene_id'),
            'round_number': view.get('round_number'),
            'active_actor_id': view.get('active_actor_id'),
            'owned_actor_ids': list(view.get('owned_actor_ids', [])),
            'summary_lines': list(view.get('summary_lines', [])[-24:]),
            'recent_chat_entries': _recent_chat_entries(view),
            'recent_visible_check_entries': _recent_check_entries(view),
            'action_groups': _summarize_action_groups(view),
            'character': _summarize_character_card(view),
            'combat': _summarize_combat_view(view),
            'prompt': _summarize_prompt(prompt),
            'recent_party_actions': [
                {
                    'controller_id': record.controller_id,
                    'scene_id': record.scene_id,
                    'runtime_mode': record.runtime_mode,
                    'text': record.text,
                    'topic_focus': record.topic_focus,
                }
                for record in public_party_memory[-8:]
            ],
            'reserved_recent_topics': [
                record.topic_focus
                for record in public_party_memory[-3:]
                if record.runtime_mode == 'storytelling' and record.scene_id == view.get('current_scene_id')
            ],
        }
        if error_message is None:
            instructions = (
                'You are one autonomous D&D player, not the DM and not another party member. '
                f'Your fixed persona is {self.persona.codename}. '
                + build_json_object_contract(template=_ACTION_DECISION_TEMPLATE)
                + ' The root object must contain exactly these keys: decision_type, text, option_id, option_ids, topic_focus, reason. '
                + 'decision_type must be one of command, prompt_response, wait. '
                + 'Stay strictly in persona. Use only information visible in the provided controller-local context. '
                + 'Respect public/private boundaries; never invent hidden knowledge. '
                + 'If a prompt is present and its prompt_kind is story-check, you should usually answer with decision_type=command and text=/check. '
                + 'If a prompt is present and its prompt_kind is reaction or timing-order, answer with decision_type=prompt_response and choose only from the visible prompt option ids. '
                + 'In combat, use slash commands only. Prefer legal commands grounded in the visible actor ids, action hints, spells, items, and current battlefield. '
                + 'In story mode, prefer natural declarations unless a visible slash command is clearly the better move. '
                + 'Be creative with spell and item usage, but keep it legal and grounded in the current character card and visible scene. '
                + 'Do not repeat the previous player\'s point. Either build on it from your own angle or introduce a different unresolved thread. '
                + 'topic_focus must be a short phrase describing the unique angle of your action.'
            )
            input_messages = (
                {
                    'role': 'user',
                    'content': [{'type': 'input_text', 'text': json.dumps(context_payload, sort_keys=True)}],
                },
            )
        else:
            instructions = (
                'You are retrying a D&D player action after deterministic validation failed. '
                + build_json_retry_contract(template=_ACTION_DECISION_TEMPLATE, attempt_number=attempt_number)
                + ' Keep the persona fixed, fix the exact error, and return one corrected action only.'
            )
            input_messages = (
                {
                    'role': 'user',
                    'content': [{'type': 'input_text', 'text': json.dumps(context_payload, sort_keys=True)}],
                },
                {
                    'role': 'user',
                    'content': [
                        {
                            'type': 'input_text',
                            'text': json.dumps(
                                {
                                    'retry_reason': error_message,
                                    'required_json_template': _ACTION_DECISION_TEMPLATE,
                                    'previous_invalid_output': (previous_output or '')[:4000],
                                    'task': 'Re-emit one corrected JSON action.',
                                },
                                sort_keys=True,
                            ),
                        }
                    ],
                },
            )
        return self.client.build_request(
            instructions=instructions,
            input_messages=input_messages,
            metadata={'request_type': 'party_player_turn', 'controller_id': self.persona.controller_id},
            temperature=0.7,
            max_output_tokens=900,
            response_format={'type': 'json_object'},
        )


class PartyConnector:
    def __init__(
        self,
        *,
        automation_client: AutomationHttpClient,
        player_agents: dict[str, PlayerAgent],
        poll_interval_seconds: float = 0.5,
        max_actions: int = 60,
        auto_end_monster_turns: bool = True,
        monster_turn_delay_seconds: float = 0.2,
        transcript_logger: PartyTranscriptLogger | None = None,
        verbose: bool = False,
    ) -> None:
        self.automation_client = automation_client
        self.player_agents = dict(player_agents)
        self.poll_interval_seconds = poll_interval_seconds
        self.max_actions = max_actions
        self.auto_end_monster_turns = auto_end_monster_turns
        self.monster_turn_delay_seconds = monster_turn_delay_seconds
        self.transcript_logger = transcript_logger
        self.verbose = verbose
        self._public_history: list[PartyActionRecord] = []
        self._story_turn_index = 0
        self.turns_taken = 0
        self.commands_sent = 0
        self.prompt_responses_sent = 0
        self.invalid_action_retries = 0

    def run(self) -> PartyConnectorResult:
        self._wait_for_post_creation()
        if self.transcript_logger is not None:
            self.transcript_logger.start(self._fetch_all_snapshots())
        actions_processed = 0
        while actions_processed < self.max_actions:
            snapshots = self._fetch_player_snapshots()
            primary_view = _view_from_snapshot(snapshots['player-1-controller'])
            runtime_mode = _string_or_none(primary_view.get('runtime_mode'))
            if runtime_mode == 'demo-complete':
                break
            prompt_owner = self._prompt_owner(snapshots)
            if prompt_owner is not None:
                self._execute_player_action(prompt_owner, snapshots[prompt_owner], count_for_story_rotation=False)
                actions_processed += 1
                continue
            if runtime_mode == 'combat':
                if self._execute_combat_cycle(snapshots):
                    actions_processed += 1
                    continue
                time.sleep(self.poll_interval_seconds)
                continue
            if runtime_mode == 'storytelling':
                controller_id = self._next_story_controller(snapshots)
                self._execute_player_action(controller_id, snapshots[controller_id], count_for_story_rotation=True)
                actions_processed += 1
                continue
            time.sleep(self.poll_interval_seconds)
        final_snapshot = self.automation_client.state('player-1-controller')
        final_view = _view_from_snapshot(final_snapshot)
        return PartyConnectorResult(
            turns_taken=self.turns_taken,
            commands_sent=self.commands_sent,
            prompt_responses_sent=self.prompt_responses_sent,
            invalid_action_retries=self.invalid_action_retries,
            final_runtime_mode=_string_or_none(final_view.get('runtime_mode')),
            final_scene_id=_string_or_none(final_view.get('current_scene_id')),
        )

    def _wait_for_post_creation(self) -> None:
        while True:
            snapshots = self._fetch_player_snapshots()
            runtime_modes = {_view_from_snapshot(snapshot).get('runtime_mode') for snapshot in snapshots.values()}
            if runtime_modes and runtime_modes != {'character-creation'}:
                return
            time.sleep(self.poll_interval_seconds)

    def _fetch_player_snapshots(self) -> dict[str, dict[str, Any]]:
        return {
            controller_id: self.automation_client.state(controller_id)
            for controller_id in PLAYER_CONTROLLER_IDS
        }

    def _fetch_all_snapshots(self) -> dict[str, dict[str, Any]]:
        snapshots = self._fetch_player_snapshots()
        snapshots['dm'] = self.automation_client.state('dm')
        return snapshots

    def _prompt_owner(self, snapshots: dict[str, dict[str, Any]]) -> str | None:
        for controller_id in PLAYER_CONTROLLER_IDS:
            if snapshots[controller_id].get('prompt') is not None:
                return controller_id
        return None

    def _execute_combat_cycle(self, snapshots: dict[str, dict[str, Any]]) -> bool:
        dm_snapshot = self.automation_client.state('dm')
        dm_view = _view_from_snapshot(dm_snapshot)
        active_actor_id = _string_or_none(dm_view.get('active_actor_id'))
        if active_actor_id is None:
            return False
        controller_id = self._controller_for_actor(active_actor_id, snapshots)
        if controller_id is not None:
            self._execute_player_action(controller_id, snapshots[controller_id], count_for_story_rotation=False)
            return True
        if not self.auto_end_monster_turns:
            return False
        if dm_snapshot.get('prompt') is not None:
            raise PartyConnectorError('Combat is waiting on a DM-owned prompt that the player connector cannot answer.')
        self._log(f'[combat] dm auto-passes {active_actor_id}')
        self.automation_client.submit('dm', f'/endturn {active_actor_id}')
        if self.transcript_logger is not None:
            self.transcript_logger.record_system_action('dm', f'/endturn {active_actor_id}')
            self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
        self.commands_sent += 1
        self.turns_taken += 1
        if self.monster_turn_delay_seconds > 0:
            time.sleep(self.monster_turn_delay_seconds)
        return True

    def _controller_for_actor(self, actor_id: str, snapshots: dict[str, dict[str, Any]]) -> str | None:
        for controller_id, snapshot in snapshots.items():
            view = _view_from_snapshot(snapshot)
            if actor_id in view.get('owned_actor_ids', ()):
                return controller_id
        return None

    def _next_story_controller(self, snapshots: dict[str, dict[str, Any]]) -> str:
        for offset in range(len(PLAYER_CONTROLLER_IDS)):
            index = (self._story_turn_index + offset) % len(PLAYER_CONTROLLER_IDS)
            controller_id = PLAYER_CONTROLLER_IDS[index]
            view = _view_from_snapshot(snapshots[controller_id])
            if view.get('runtime_mode') == 'storytelling':
                return controller_id
        raise PartyConnectorError('No player controller is currently available for a storytelling turn.')

    def _execute_player_action(
        self,
        controller_id: str,
        snapshot: dict[str, Any],
        *,
        count_for_story_rotation: bool,
    ) -> None:
        agent = self.player_agents[controller_id]
        previous_output: str | None = None
        error_message: str | None = None
        current_snapshot = snapshot
        for attempt in range(1, 4):
            raw_output = ''
            try:
                decision, raw_output = agent.plan_action(
                    current_snapshot,
                    public_party_memory=list(self._public_history),
                    previous_output=previous_output,
                    error_message=error_message,
                    attempt_number=attempt,
                )
                self._validate_decision(controller_id, current_snapshot, decision, count_for_story_rotation=count_for_story_rotation)
                self._apply_decision(controller_id, current_snapshot, decision)
                if self.transcript_logger is not None:
                    self.transcript_logger.record_player_action(controller_id, decision)
                    self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
                if count_for_story_rotation:
                    self._record_story_action(controller_id, current_snapshot, decision)
                    self._story_turn_index = (PLAYER_CONTROLLER_IDS.index(controller_id) + 1) % len(PLAYER_CONTROLLER_IDS)
                self.turns_taken += 1
                return
            except (PartyConnectorError, LiveWebStoryDemoError) as exc:
                if isinstance(exc, PartyActionPlanningError):
                    raw_output = exc.raw_output
                previous_output = raw_output
                error_message = str(exc)
                self.invalid_action_retries += 1
                if attempt >= 3:
                    self._execute_fallback_action(
                        controller_id,
                        current_snapshot,
                        count_for_story_rotation=count_for_story_rotation,
                        reason=error_message,
                    )
                    return
                current_snapshot = self.automation_client.state(controller_id)
        raise PartyConnectorError(f'Unable to obtain a valid action for {controller_id}.')

    def _execute_fallback_action(
        self,
        controller_id: str,
        snapshot: dict[str, Any],
        *,
        count_for_story_rotation: bool,
        reason: str,
    ) -> None:
        decision = self._fallback_decision(snapshot, reason=reason)
        self._validate_decision(controller_id, snapshot, decision, count_for_story_rotation=count_for_story_rotation)
        self._apply_decision(controller_id, snapshot, decision)
        if self.transcript_logger is not None:
            self.transcript_logger.record_system_action(controller_id, f'fallback after invalid LLM output: {decision.text}')
            self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
        if count_for_story_rotation:
            self._record_story_action(controller_id, snapshot, decision)
            self._story_turn_index = (PLAYER_CONTROLLER_IDS.index(controller_id) + 1) % len(PLAYER_CONTROLLER_IDS)
        self.turns_taken += 1

    def _fallback_decision(self, snapshot: dict[str, Any], *, reason: str) -> PartyActionDecision:
        view = _view_from_snapshot(snapshot)
        prompt = snapshot.get('prompt')
        if isinstance(prompt, dict):
            prompt_kind = _string_or_none(prompt.get('prompt_kind'))
            if prompt_kind == 'story-check':
                return PartyActionDecision(
                    decision_type='command',
                    text='/check',
                    option_id=None,
                    option_ids=(),
                    topic_focus='resolve requested check',
                    reason=f'Fallback after invalid LLM output: {reason}',
                )
            if prompt_kind in {'reaction', 'timing-order'}:
                option_id = _first_prompt_option_id(prompt)
                return PartyActionDecision(
                    decision_type='prompt_response',
                    text='',
                    option_id=option_id,
                    option_ids=(),
                    topic_focus='safe prompt response',
                    reason=f'Fallback after invalid LLM output: {reason}',
                )
        if _string_or_none(view.get('runtime_mode')) == 'combat':
            active_actor_id = _string_or_none(view.get('active_actor_id')) or ''
            return PartyActionDecision(
                decision_type='command',
                text=f'/endturn {active_actor_id}'.strip(),
                option_id=None,
                option_ids=(),
                topic_focus='safe combat pass',
                reason=f'Fallback after invalid LLM output: {reason}',
            )
        return PartyActionDecision(
            decision_type='command',
            text='I stay alert, keep pace with the group, and watch for any detail the others may have missed.',
            option_id=None,
            option_ids=(),
            topic_focus='stay alert and observe',
            reason=f'Fallback after invalid LLM output: {reason}',
        )

    def _validate_decision(
        self,
        controller_id: str,
        snapshot: dict[str, Any],
        decision: PartyActionDecision,
        *,
        count_for_story_rotation: bool,
    ) -> None:
        view = _view_from_snapshot(snapshot)
        prompt = snapshot.get('prompt')
        runtime_mode = _string_or_none(view.get('runtime_mode'))
        if prompt is not None:
            prompt_kind = _string_or_none(prompt.get('prompt_kind'))
            if prompt_kind == 'story-check':
                if decision.decision_type != 'command' or decision.text.strip() != '/check':
                    raise PartyConnectorError('A story-check prompt must be answered with decision_type=command and text=/check.')
                return
            if prompt_kind in {'reaction', 'timing-order'}:
                if decision.decision_type != 'prompt_response':
                    raise PartyConnectorError(f'A {prompt_kind} prompt must be answered with decision_type=prompt_response.')
                self._validate_prompt_option_selection(prompt, decision)
                return
            raise PartyConnectorError(f'Unsupported prompt kind for player connector: {prompt_kind!r}.')
        if decision.decision_type != 'command':
            raise PartyConnectorError('Non-prompt turns must produce decision_type=command.')
        if not decision.text.strip():
            raise PartyConnectorError('Command decisions require non-empty `text`.')
        if runtime_mode == 'combat':
            if not decision.text.startswith('/'):
                raise PartyConnectorError('Combat turns must use slash commands only.')
            active_actor_id = _string_or_none(view.get('active_actor_id'))
            owned_actor_ids = tuple(view.get('owned_actor_ids', ()))
            if active_actor_id is None or active_actor_id not in owned_actor_ids:
                raise PartyConnectorError('The connector asked a player to act outside that player\'s active combat turn.')
            return
        if runtime_mode == 'storytelling' and count_for_story_rotation:
            self._validate_distinct_story_turn(controller_id, view, decision)

    def _validate_prompt_option_selection(self, prompt: dict[str, Any], decision: PartyActionDecision) -> None:
        valid_option_ids = {option.get('option_id') for option in prompt.get('options', []) if isinstance(option.get('option_id'), str)}
        if decision.option_id is not None:
            if decision.option_id not in valid_option_ids:
                raise PartyConnectorError(f'Invalid prompt option id: {decision.option_id}')
            return
        if decision.option_ids:
            invalid = [option_id for option_id in decision.option_ids if option_id not in valid_option_ids]
            if invalid:
                raise PartyConnectorError(f'Invalid prompt option ids: {", ".join(invalid)}')
            return
        return

    def _validate_distinct_story_turn(self, controller_id: str, view: dict[str, Any], decision: PartyActionDecision) -> None:
        scene_id = _string_or_none(view.get('current_scene_id'))
        normalized_text = _normalize_text(decision.text)
        normalized_topic = _normalize_topic(decision.topic_focus)
        if not normalized_topic:
            raise PartyConnectorError('topic_focus must contain a distinct non-empty topic phrase.')
        recent_same_scene = [
            record
            for record in reversed(self._public_history)
            if record.runtime_mode == 'storytelling' and record.scene_id == scene_id and record.controller_id != controller_id
        ]
        for record in recent_same_scene[:4]:
            if _normalize_text(record.text) == normalized_text:
                raise PartyConnectorError('That storytelling action repeats a recent player action too closely. Pick a different angle.')
        for record in recent_same_scene[:2]:
            if _normalize_topic(record.topic_focus) == normalized_topic:
                raise PartyConnectorError('That storytelling turn duplicates the previous player topic. Choose a new focus.')

    def _apply_decision(self, controller_id: str, snapshot: dict[str, Any], decision: PartyActionDecision) -> None:
        prompt = snapshot.get('prompt')
        if prompt is not None and _string_or_none(prompt.get('prompt_kind')) in {'reaction', 'timing-order'}:
            if decision.option_id is not None:
                self.automation_client.respond_to_prompt(controller_id, option_id=decision.option_id)
            elif decision.option_ids:
                self.automation_client.respond_to_prompt(controller_id, option_ids=list(decision.option_ids))
            else:
                self.automation_client.respond_to_prompt(controller_id, option_id=None)
            self.prompt_responses_sent += 1
            self._log(f'[{controller_id}] prompt -> {decision.option_id or list(decision.option_ids)}')
            return
        self.automation_client.submit(controller_id, decision.text)
        self.commands_sent += 1
        self._log(f'[{controller_id}] {decision.text}')

    def _record_story_action(self, controller_id: str, snapshot: dict[str, Any], decision: PartyActionDecision) -> None:
        if decision.text.strip() == '/check':
            return
        view = _view_from_snapshot(snapshot)
        self._public_history.append(
            PartyActionRecord(
                controller_id=controller_id,
                runtime_mode='storytelling',
                scene_id=_string_or_none(view.get('current_scene_id')),
                text=decision.text,
                topic_focus=decision.topic_focus,
            )
        )
        self._public_history = self._public_history[-20:]

    def _log(self, message: str) -> None:
        if self.verbose:
            print(message, flush=True)


def build_default_player_agents(
    *,
    config: LLMConfig,
    llm_transport=None,
) -> dict[str, PlayerAgent]:
    return {
        controller_id: PlayerAgent(
            persona=persona,
            client=LLMClient(config, transport=llm_transport),
        )
        for controller_id, persona in DEFAULT_PERSONAS.items()
    }


def run_party_connector(
    *,
    base_url: str,
    env_path: str | Path = '.env',
    request_timeout_seconds: float | None = 300.0,
    poll_interval_seconds: float = 0.5,
    max_actions: int = 60,
    auto_end_monster_turns: bool = True,
    monster_turn_delay_seconds: float = 0.2,
    transcript_path: str | Path | None = None,
    llm_transport=None,
    verbose: bool = False,
) -> PartyConnectorResult:
    config = load_llm_config(env_path=env_path)
    automation_client = AutomationHttpClient(base_url, request_timeout_seconds=request_timeout_seconds)
    connector = PartyConnector(
        automation_client=automation_client,
        player_agents=build_default_player_agents(config=config, llm_transport=llm_transport),
        poll_interval_seconds=poll_interval_seconds,
        max_actions=max_actions,
        auto_end_monster_turns=auto_end_monster_turns,
        monster_turn_delay_seconds=monster_turn_delay_seconds,
        transcript_logger=(PartyTranscriptLogger(Path(transcript_path)) if transcript_path is not None else None),
        verbose=verbose,
    )
    return connector.run()


def _parse_action_decision(raw_text: str) -> PartyActionDecision:
    try:
        decoded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PartyConnectorError(f'Player agent returned invalid JSON: {exc}') from exc
    if not isinstance(decoded, dict):
        raise PartyConnectorError('Player agent reply must be a JSON object.')
    allowed_keys = {'decision_type', 'text', 'option_id', 'option_ids', 'topic_focus', 'reason'}
    unexpected_keys = sorted(set(decoded) - allowed_keys)
    if unexpected_keys:
        raise PartyConnectorError(f'Player agent reply used unexpected keys: {", ".join(unexpected_keys)}.')
    decision_type = decoded.get('decision_type')
    text = decoded.get('text')
    option_id = decoded.get('option_id')
    option_ids = decoded.get('option_ids')
    topic_focus = decoded.get('topic_focus')
    reason = decoded.get('reason')
    if decision_type not in {'command', 'prompt_response', 'wait'}:
        raise PartyConnectorError('decision_type must be one of command, prompt_response, wait.')
    if not isinstance(text, str):
        raise PartyConnectorError('text must be a string.')
    if option_id is not None and not isinstance(option_id, str):
        raise PartyConnectorError('option_id must be null or a string.')
    if not isinstance(option_ids, list) or not all(isinstance(item, str) for item in option_ids):
        raise PartyConnectorError('option_ids must be an array of strings.')
    if not isinstance(topic_focus, str) or not topic_focus.strip():
        raise PartyConnectorError('topic_focus must be a non-empty string.')
    if not isinstance(reason, str) or not reason.strip():
        raise PartyConnectorError('reason must be a non-empty string.')
    return PartyActionDecision(
        decision_type=decision_type,
        text=text.strip(),
        option_id=option_id,
        option_ids=tuple(option_ids),
        topic_focus=topic_focus.strip(),
        reason=reason.strip(),
    )


def _recent_chat_entries(view: dict[str, Any]) -> list[dict[str, Any]]:
    entries = []
    for entry in list(view.get('chat_entries', []))[-18:]:
        if not isinstance(entry, dict):
            continue
        entries.append(
            {
                'speaker': entry.get('speaker'),
                'text': entry.get('text'),
                'category': entry.get('category'),
                'visibility': entry.get('visibility'),
            }
        )
    return entries


def _recent_check_entries(view: dict[str, Any]) -> list[str]:
    checks = []
    for entry in list(view.get('chat_entries', []))[-18:]:
        if not isinstance(entry, dict):
            continue
        if entry.get('category') != 'check':
            continue
        text = entry.get('text')
        if isinstance(text, str) and text:
            checks.append(text)
    if checks:
        return checks[-6:]
    summary_lines = [line for line in view.get('summary_lines', []) if isinstance(line, str)]
    return [line for line in summary_lines if 'Recent check results:' in line or 'vs DC ' in line][-6:]


def _summarize_action_groups(view: dict[str, Any]) -> list[dict[str, Any]]:
    groups = []
    for group in view.get('action_groups', [])[:10]:
        if not isinstance(group, dict):
            continue
        summarized_choices = []
        for choice in group.get('choices', [])[:6]:
            if not isinstance(choice, dict):
                continue
            summarized_choices.append(
                {
                    'option_id': choice.get('option_id'),
                    'label': choice.get('label'),
                    'detail': choice.get('detail'),
                    'command_insert_text': choice.get('command_insert_text'),
                    'command_prefix': choice.get('command_prefix'),
                    'command_hint': choice.get('command_hint'),
                }
            )
        groups.append(
            {
                'group_id': group.get('group_id'),
                'label': group.get('label'),
                'choices': summarized_choices,
            }
        )
    return groups


def _summarize_character_card(view: dict[str, Any]) -> dict[str, Any] | None:
    cards = view.get('character_cards', [])
    if not isinstance(cards, list) or not cards:
        return None
    card = cards[0]
    if not isinstance(card, dict):
        return None
    return {
        'actor_id': card.get('actor_id'),
        'name': card.get('name'),
        'class_name': card.get('class_name'),
        'level': card.get('level'),
        'species_name': card.get('species_name'),
        'background_name': card.get('background_name'),
        'hit_points': {
            'current': card.get('current_hit_points'),
            'max': card.get('max_hit_points'),
            'temp': card.get('temp_hit_points'),
        },
        'armor_class': card.get('armor_class'),
        'conditions': list(card.get('conditions', [])),
        'resources': [
            {
                'label': resource.get('label'),
                'remaining_uses': resource.get('remaining_uses'),
                'max_uses': resource.get('max_uses'),
            }
            for resource in list(card.get('resources', []))[:8]
            if isinstance(resource, dict)
        ],
        'cantrips': [spell.get('name') for spell in list(card.get('cantrips', []))[:8] if isinstance(spell, dict)],
        'spells': [
            {
                'name': spell.get('name'),
                'remaining_uses': spell.get('remaining_uses'),
            }
            for spell in list(card.get('spells', []))[:10]
            if isinstance(spell, dict)
        ],
        'items': [item.get('name') for item in list(card.get('items', []))[:12] if isinstance(item, dict)],
    }


def _summarize_combat_view(view: dict[str, Any]) -> dict[str, Any] | None:
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return None
    tokens = []
    for token in list(map_view.get('tokens', []))[:16]:
        if not isinstance(token, dict):
            continue
        tokens.append(
            {
                'actor_id': token.get('actor_id'),
                'side': token.get('side'),
                'status': token.get('status'),
                'is_owner': token.get('is_owner'),
                'position': token.get('position'),
                'hit_points': token.get('hit_points'),
            }
        )
    return {
        'active_actor_id': view.get('active_actor_id'),
        'round_number': view.get('round_number'),
        'initiative_order': list(view.get('initiative_order', [])),
        'visible_tokens': tokens,
    }


def _summarize_prompt(prompt: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(prompt, dict):
        return None
    return {
        'prompt_kind': prompt.get('prompt_kind'),
        'text': prompt.get('text'),
        'options': [
            {
                'option_id': option.get('option_id'),
                'label': option.get('label'),
                'detail': option.get('detail'),
                'actor_id': option.get('actor_id'),
            }
            for option in prompt.get('options', [])
            if isinstance(option, dict)
        ],
    }


def _first_prompt_option_id(prompt: dict[str, Any]) -> str | None:
    for option in prompt.get('options', []):
        if not isinstance(option, dict):
            continue
        option_id = option.get('option_id')
        if isinstance(option_id, str):
            return option_id
    return None


def _view_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    view = snapshot.get('view')
    if not isinstance(view, dict):
        raise PartyConnectorError('Automation snapshot is missing object `view`.')
    return view


def _normalize_text(text: str) -> str:
    lowered = re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()
    return ' '.join(lowered.split())


def _normalize_topic(text: str) -> str:
    tokens = [token for token in re.sub(r'[^a-z0-9]+', ' ', text.lower()).split() if token and token not in _STOPWORDS]
    return ' '.join(tokens[:6])


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run four autonomous player agents against the live web story demo automation API.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='Base URL of the running web story demo server.')
    parser.add_argument('--env-path', default='.env', help='Path to the LLM .env file used for the player agents.')
    parser.add_argument(
        '--request-timeout-seconds',
        type=float,
        default=300.0,
        help='HTTP request timeout for automation API calls. Use 0 to disable the timeout.',
    )
    parser.add_argument('--poll-interval-seconds', type=float, default=0.5, help='Polling interval while waiting for the next actionable player turn.')
    parser.add_argument('--max-actions', type=int, default=60, help='Maximum number of connector-driven actions before exiting.')
    parser.add_argument('--disable-auto-end-monster-turns', action='store_true', help='Do not auto-pass DM-owned monster turns during combat.')
    parser.add_argument('--monster-turn-delay-seconds', type=float, default=0.2, help='Delay after auto-ending a monster turn.')
    parser.add_argument('--transcript-path', help='Optional path to a local transcript log file for player actions and visible DM/public outputs.')
    parser.add_argument('--verbose', action='store_true', help='Print each accepted connector action.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.request_timeout_seconds < 0:
        raise SystemExit('ERROR: --request-timeout-seconds must be >= 0.')
    if args.poll_interval_seconds <= 0:
        raise SystemExit('ERROR: --poll-interval-seconds must be > 0.')
    if args.max_actions <= 0:
        raise SystemExit('ERROR: --max-actions must be > 0.')
    if args.monster_turn_delay_seconds < 0:
        raise SystemExit('ERROR: --monster-turn-delay-seconds must be >= 0.')
    result = run_party_connector(
        base_url=args.base_url,
        env_path=Path(args.env_path),
        request_timeout_seconds=(None if args.request_timeout_seconds == 0 else args.request_timeout_seconds),
        poll_interval_seconds=args.poll_interval_seconds,
        max_actions=args.max_actions,
        auto_end_monster_turns=not args.disable_auto_end_monster_turns,
        monster_turn_delay_seconds=args.monster_turn_delay_seconds,
        transcript_path=(Path(args.transcript_path) if args.transcript_path else None),
        verbose=args.verbose,
    )
    print(
        f'Party connector stopped after {result.turns_taken} turns: '
        f'{result.commands_sent} commands, {result.prompt_responses_sent} prompt responses, '
        f'{result.invalid_action_retries} retries, final mode {result.final_runtime_mode}, '
        f'final scene {result.final_scene_id}.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
