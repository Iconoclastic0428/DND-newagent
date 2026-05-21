from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import time
from typing import Any

from dm_agent.client import LLMClient, LLMHttpTransport
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
        'text': 'Gundren, what signs of danger should we watch for on the road?',
        'option_id': None,
        'option_ids': [],
        'topic_focus': 'road danger signs',
        'reason': 'Short explanation of why this fits the persona and current state.',
    },
    separators=(',', ':'),
)

_SPEAKER_VOTE_TEMPLATE = json.dumps(
    {
        'selected_controller_id': 'player-3-controller',
        'reason': 'They have the strongest current fit for wagon logistics and supplies.',
        'advantage_factors': ['relevant skills/status/resources from the candidate profile'],
        'confidence': 0.8,
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

_NARRATED_SPEECH_RE = re.compile(
    r'\b(?:i|we)\s+(?:[^.!?]{0,50}\s+)?(?:ask|asks|tell|tells|say|says|reassure|reassures|'
    r'explain|explains|warn|warns|press|presses|question|questions|request|requests|inquire|inquires)\b',
    re.IGNORECASE,
)

_DIRECT_ADDRESS_RE = re.compile(r'^[A-Z][A-Za-z\' -]{2,},\s+\S+')


class PartyConnectorError(RuntimeError):
    pass


class PartyActionPlanningError(PartyConnectorError):
    def __init__(self, message: str, *, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output


class PartySpeakerVotePlanningError(PartyConnectorError):
    def __init__(self, message: str, *, raw_output: str) -> None:
        super().__init__(message)
        self.raw_output = raw_output


@dataclass(frozen=True)
class RawInteractionLogger:
    path: Path

    def record(
        self,
        *,
        transport_method: str,
        url: str,
        request_payload: dict[str, Any],
        response_payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'transport_method': transport_method,
            'url': url,
            'request_metadata': request_payload.get('metadata') if isinstance(request_payload.get('metadata'), dict) else None,
            'request_payload': request_payload,
            'response_payload': response_payload,
            'error': error,
        }
        with self.path.open('a', encoding='utf-8') as handle:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + '\n')


class RawInteractionLoggingTransport:
    def __init__(self, inner_transport, logger: RawInteractionLogger) -> None:
        self.inner_transport = inner_transport
        self.logger = logger

    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.inner_transport.post(url=url, headers=headers, payload=payload)
        except Exception as exc:
            self.logger.record(transport_method='post', url=url, request_payload=payload, error=str(exc))
            raise
        self.logger.record(transport_method='post', url=url, request_payload=payload, response_payload=response)
        return response

    def stream(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = self.inner_transport.stream(url=url, headers=headers, payload=payload)
        except Exception as exc:
            self.logger.record(transport_method='stream', url=url, request_payload=payload, error=str(exc))
            raise
        self.logger.record(
            transport_method='stream',
            url=url,
            request_payload=payload,
            response_payload={'events': response},
        )
        return response


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
class PartySpeakerVote:
    selected_controller_id: str
    reason: str
    advantage_factors: tuple[str, ...]
    confidence: float


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
    def __init__(
        self,
        *,
        persona: PlayerPersona,
        client: LLMClient,
        behavior_profile: str = 'positive',
        negative_intensity: float = 0.5,
    ) -> None:
        self.persona = persona
        self.client = client
        self.behavior_profile = behavior_profile
        self.negative_intensity = max(0.0, min(1.0, float(negative_intensity)))

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

    def vote_speaker(
        self,
        snapshot: dict[str, Any],
        *,
        speaker_candidates: tuple[dict[str, Any], ...],
        public_party_memory: list[PartyActionRecord],
        previous_output: str | None = None,
        error_message: str | None = None,
        attempt_number: int = 1,
    ) -> tuple[PartySpeakerVote, str]:
        request = self._build_speaker_vote_request(
            snapshot,
            speaker_candidates=speaker_candidates,
            public_party_memory=public_party_memory,
            previous_output=previous_output,
            error_message=error_message,
            attempt_number=attempt_number,
        )
        response = self.client.create_response(request)
        output_text = response.output_text
        try:
            return _parse_speaker_vote(output_text), output_text
        except PartyConnectorError as exc:
            raise PartySpeakerVotePlanningError(str(exc), raw_output=output_text) from exc

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
                + 'For weapon attacks, always use the full syntax /attack <active_actor_id> <attack option_id> <target_actor_id>. '
                + 'The active_actor_id, legal attack option ids, and visible enemy target actor ids are listed in the combat context. '
                + 'Do not choose /endturn while attacks, spells, or normal actions are still available. If enemies are out of melee range, prefer a thrown/ranged attack, a targeted spell, or /dodge <active_actor_id>. '
                + 'In story mode, prefer natural declarations unless a visible slash command is clearly the better move. '
                + 'If you speak to an NPC in story mode, write the character\'s actual words as direct dialogue or quoted direct speech. '
                + 'Do not write narrated speech such as "I ask Gundren..." or "I tell Sildar...". '
                + 'Good style: "Gundren, do you think that is too little gold up front? We need equipment before the road." '
                + 'If you are doing a nonverbal action, describe the action directly and only include spoken words as dialogue. '
                + 'Be creative with spell and item usage, but keep it legal and grounded in the current character card and visible scene. '
                + 'Do not repeat the previous player\'s point. Either build on it from your own angle or introduce a different unresolved thread. '
                + 'topic_focus must be a short phrase describing the unique angle of your action. '
                + self._behavior_profile_instruction()
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
            max_output_tokens=3000,
            response_format={'type': 'json_object'},
        )

    def _behavior_profile_instruction(self) -> str:
        if self.behavior_profile == 'negative':
            return (
                'This episode is collecting negative RL training examples. '
                f'Negative intensity is {self.negative_intensity:.2f}. '
                'Keep the action legal and parseable so the conversation can continue, but deliberately include some lower-quality player behavior: '
                'stalling, redundant concerns, repeated wording, over-cautious delay, or actions that fail to finish visible scene goals or hidden subgoals. '
                'Do not make every turn bad; mix in enough useful actions that the run can still progress and produce both positive and negative reward signs.'
            )
        if self.behavior_profile != 'positive':
            raise PartyConnectorError(f'Unknown behavior profile: {self.behavior_profile!r}.')
        return (
            'This episode is collecting positive RL training examples. '
            'Act to finish visible scene goals and uncover or complete hidden subgoals. '
            'Prefer concrete progress: resolve open loops, reveal useful discoveries, answer pending checks, improve social leverage, and move the scene forward. '
            'You should avoid repeated wording, repeated questions, and stalling.'
        )

    def _build_speaker_vote_request(
        self,
        snapshot: dict[str, Any],
        *,
        speaker_candidates: tuple[dict[str, Any], ...],
        public_party_memory: list[PartyActionRecord],
        previous_output: str | None,
        error_message: str | None,
        attempt_number: int,
    ):
        view = _view_from_snapshot(snapshot)
        candidate_ids = [candidate['controller_id'] for candidate in speaker_candidates]
        context_payload = {
            'voter_persona': {
                'controller_id': self.persona.controller_id,
                'codename': self.persona.codename,
                'personality': self.persona.personality,
                'story_focus': self.persona.story_focus,
                'coordination_rule': self.persona.coordination_rule,
            },
            'runtime_mode': view.get('runtime_mode'),
            'current_scene_id': view.get('current_scene_id'),
            'summary_lines': list(view.get('summary_lines', [])[-24:]),
            'recent_chat_entries': _recent_chat_entries(view),
            'recent_visible_check_entries': _recent_check_entries(view),
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
            'speaker_candidates': list(speaker_candidates),
            'allowed_controller_ids': candidate_ids,
        }
        if error_message is None:
            instructions = (
                'You are voting for which one party member should speak next in the current D&D scene. '
                + build_json_object_contract(template=_SPEAKER_VOTE_TEMPLATE)
                + ' The root object must contain exactly these keys: selected_controller_id, reason, advantage_factors, confidence. '
                + 'selected_controller_id must be one of the allowed_controller_ids from the input. '
                + 'Choose the candidate with the best current advantage for this exact moment, using visible player data only: '
                + 'current HP/status/conditions, relevant skill and ability bonuses, remaining resources, spell/item fit, persona focus, recent checks, and unresolved scene goals. '
                + 'Do not vote merely by round-robin order. Do not vote for yourself unless your candidate profile is actually the best fit. '
                + 'reason must briefly explain the concrete advantage, not generic preference. '
                + 'advantage_factors must list one to four short evidence strings from the candidate profiles or visible scene. '
                + 'confidence must be a number from 0 to 1.'
            )
            input_messages = (
                {
                    'role': 'user',
                    'content': [{'type': 'input_text', 'text': json.dumps(context_payload, sort_keys=True)}],
                },
            )
        else:
            instructions = (
                'You are retrying a speaker vote after deterministic validation failed. '
                + build_json_retry_contract(template=_SPEAKER_VOTE_TEMPLATE, attempt_number=attempt_number)
                + ' Fix the exact error and return one corrected speaker vote only.'
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
                                    'allowed_controller_ids': candidate_ids,
                                    'required_json_template': _SPEAKER_VOTE_TEMPLATE,
                                    'previous_invalid_output': (previous_output or '')[:4000],
                                    'task': 'Re-emit one corrected JSON speaker vote.',
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
            metadata={'request_type': 'party_speaker_vote', 'controller_id': self.persona.controller_id},
            temperature=0.2,
            max_output_tokens=2200,
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
        enable_speaker_voting: bool = True,
        transcript_logger: PartyTranscriptLogger | None = None,
        verbose: bool = False,
    ) -> None:
        self.automation_client = automation_client
        self.player_agents = dict(player_agents)
        self.poll_interval_seconds = poll_interval_seconds
        self.max_actions = max_actions
        self.auto_end_monster_turns = auto_end_monster_turns
        self.monster_turn_delay_seconds = monster_turn_delay_seconds
        self.enable_speaker_voting = enable_speaker_voting
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
                controller_id = self._select_story_controller(snapshots)
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

    def _select_story_controller(self, snapshots: dict[str, dict[str, Any]]) -> str:
        if not self.enable_speaker_voting:
            return self._next_story_controller(snapshots)
        return self._vote_for_story_controller(snapshots)

    def _vote_for_story_controller(self, snapshots: dict[str, dict[str, Any]]) -> str:
        candidates = _speaker_candidates_from_snapshots(snapshots, public_party_memory=tuple(self._public_history))
        if not candidates:
            raise PartyConnectorError('No player controller is currently available for a speaker vote.')
        candidate_ids = tuple(candidate['controller_id'] for candidate in candidates)
        votes: list[PartySpeakerVote] = []
        for voter_controller_id in candidate_ids:
            votes.append(
                self._collect_speaker_vote(
                    voter_controller_id,
                    snapshots[voter_controller_id],
                    candidates=candidates,
                    candidate_ids=candidate_ids,
                )
            )
        vote_counts = Counter(vote.selected_controller_id for vote in votes)
        candidate_by_id = {candidate['controller_id']: candidate for candidate in candidates}
        selected_controller_id = max(
            candidate_ids,
            key=lambda controller_id: (
                vote_counts.get(controller_id, 0),
                float(candidate_by_id[controller_id].get('advantage_score', 0.0)),
                self._turns_since_story_action(controller_id),
                -PLAYER_CONTROLLER_IDS.index(controller_id),
            ),
        )
        self._log(f'[speaker-vote] {selected_controller_id} <- {dict(vote_counts)}')
        return selected_controller_id

    def _collect_speaker_vote(
        self,
        voter_controller_id: str,
        snapshot: dict[str, Any],
        *,
        candidates: tuple[dict[str, Any], ...],
        candidate_ids: tuple[str, ...],
    ) -> PartySpeakerVote:
        agent = self.player_agents[voter_controller_id]
        previous_output: str | None = None
        error_message: str | None = None
        for attempt in range(1, 4):
            raw_output = ''
            try:
                vote, raw_output = agent.vote_speaker(
                    snapshot,
                    speaker_candidates=candidates,
                    public_party_memory=list(self._public_history),
                    previous_output=previous_output,
                    error_message=error_message,
                    attempt_number=attempt,
                )
                if vote.selected_controller_id not in candidate_ids:
                    raise PartyConnectorError(
                        f'Speaker vote selected {vote.selected_controller_id!r}, expected one of {", ".join(candidate_ids)}.'
                    )
                return vote
            except (PartyConnectorError, PartySpeakerVotePlanningError) as exc:
                if isinstance(exc, PartySpeakerVotePlanningError):
                    raw_output = exc.raw_output
                previous_output = raw_output
                error_message = str(exc)
                self.invalid_action_retries += 1
                if attempt >= 3:
                    raise
        raise PartyConnectorError(f'Unable to obtain a valid speaker vote from {voter_controller_id}.')

    def _turns_since_story_action(self, controller_id: str) -> int:
        for distance, record in enumerate(reversed(self._public_history), start=1):
            if record.controller_id == controller_id:
                return distance
        return 999

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
        decision = self._fallback_decision(controller_id, snapshot, reason=reason)
        try:
            self._validate_decision(controller_id, snapshot, decision, count_for_story_rotation=count_for_story_rotation)
        except PartyConnectorError:
            decision = self._last_resort_fallback_decision(controller_id, snapshot, reason=reason)
        self._apply_decision(controller_id, snapshot, decision)
        if self.transcript_logger is not None:
            self.transcript_logger.record_system_action(controller_id, f'fallback after invalid LLM output: {decision.text}')
            self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
        if count_for_story_rotation:
            self._record_story_action(controller_id, snapshot, decision)
            self._story_turn_index = (PLAYER_CONTROLLER_IDS.index(controller_id) + 1) % len(PLAYER_CONTROLLER_IDS)
        self.turns_taken += 1

    def _fallback_decision(self, controller_id: str, snapshot: dict[str, Any], *, reason: str) -> PartyActionDecision:
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
            fallback_text = _combat_fallback_command(view)
            return PartyActionDecision(
                decision_type='command',
                text=fallback_text or f'/endturn {active_actor_id}'.strip(),
                option_id=None,
                option_ids=(),
                topic_focus='safe combat fallback',
                reason=f'Fallback after invalid LLM output: {reason}',
            )
        return self._story_fallback_decision(controller_id, view, reason=reason)

    def _story_fallback_decision(self, controller_id: str, view: dict[str, Any], *, reason: str) -> PartyActionDecision:
        index = PLAYER_CONTROLLER_IDS.index(controller_id) if controller_id in PLAYER_CONTROLLER_IDS else 0
        scene_id = _string_or_none(view.get('current_scene_id')) or 'current scene'
        fallback_options = (
            (
                'trust terms',
                'Gundren, what promise would make you feel safer trusting us with the road ahead?',
            ),
            (
                'organized threat pattern',
                'Gundren, what sign would prove this road danger is organized rather than random?',
            ),
            (
                'wagon readiness',
                'I check the wagon harness, cargo tie-downs, and road supplies so we are ready to leave without delay.',
            ),
            (
                'phandalin reaction watch',
                'I watch nearby faces for any reaction when Phandalin, Gundren, or the wagon cargo are mentioned.',
            ),
        )
        topic, text = fallback_options[index % len(fallback_options)]
        return PartyActionDecision(
            decision_type='command',
            text=text,
            option_id=None,
            option_ids=(),
            topic_focus=f'{topic} {scene_id}',
            reason=f'Fallback after invalid LLM output: {reason}',
        )

    def _last_resort_fallback_decision(self, controller_id: str, snapshot: dict[str, Any], *, reason: str) -> PartyActionDecision:
        view = _view_from_snapshot(snapshot)
        if _string_or_none(view.get('runtime_mode')) == 'combat':
            active_actor_id = _string_or_none(view.get('active_actor_id')) or ''
            return PartyActionDecision(
                decision_type='command',
                text=_combat_fallback_command(view) or f'/endturn {active_actor_id}'.strip(),
                option_id=None,
                option_ids=(),
                topic_focus='last resort combat fallback',
                reason=f'Last-resort fallback after invalid LLM output: {reason}',
            )
        scene_id = _string_or_none(view.get('current_scene_id')) or 'current-scene'
        safe_controller = controller_id.replace('-', ' ')
        return PartyActionDecision(
            decision_type='command',
            text=f'I take a fresh angle in {scene_id}: {safe_controller} focuses on one practical detail the party has not acted on yet.',
            option_id=None,
            option_ids=(),
            topic_focus=f'last resort {controller_id} {scene_id}',
            reason=f'Last-resort fallback after invalid LLM output: {reason}',
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
            self._validate_combat_command(view, decision.text)
            return
        if runtime_mode == 'storytelling' and count_for_story_rotation:
            self._validate_direct_story_speech(decision)
            self._validate_distinct_story_turn(controller_id, view, decision)

    def _validate_direct_story_speech(self, decision: PartyActionDecision) -> None:
        text = decision.text.strip()
        if not text or text.startswith('/'):
            return
        if _NARRATED_SPEECH_RE.search(text) is None:
            return
        if _has_direct_dialogue(text):
            return
        raise PartyConnectorError(
            'Story speech must use direct in-character words instead of narrated speech. '
            'Write text like "Gundren, do you think that is too little gold up front?" instead of "I ask Gundren...".'
        )

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

    def _validate_combat_command(self, view: dict[str, Any], text: str) -> None:
        parts = text.strip().split()
        if not parts:
            raise PartyConnectorError('Combat command must not be empty.')
        active_actor_id = _string_or_none(view.get('active_actor_id')) or ''
        if parts[0] == '/attack':
            attack_ids = _available_choice_ids(view, 'attacks')
            target_ids = _visible_enemy_target_ids(view)
            expected = f'/attack {active_actor_id} <attack option_id> <target actor id>'
            if len(parts) != 4:
                raise PartyConnectorError(
                    f'Attack command must use `{expected}`. '
                    f'Legal attack option ids: {", ".join(attack_ids) or "none"}. '
                    f'Visible enemy target actor ids: {", ".join(target_ids) or "none"}.'
                )
            if parts[1] != active_actor_id:
                raise PartyConnectorError(f'Attack command actor must be the active actor `{active_actor_id}`.')
            if parts[2] not in attack_ids:
                raise PartyConnectorError(f'Unknown attack option id `{parts[2]}`. Legal attack option ids: {", ".join(attack_ids) or "none"}.')
            if parts[3] not in target_ids:
                raise PartyConnectorError(f'Unknown attack target `{parts[3]}`. Visible enemy target actor ids: {", ".join(target_ids) or "none"}.')
        elif parts[0] == '/endturn':
            if len(parts) != 2 or parts[1] != active_actor_id:
                raise PartyConnectorError(f'End-turn command must use `/endturn {active_actor_id}`.')
            if _has_available_combat_action(view):
                fallback = _combat_fallback_command(view)
                raise PartyConnectorError(
                    f'Do not end the turn while actions, attacks, or spells are still available. '
                    f'Use an available option first; safe fallback: {fallback or f"/dodge {active_actor_id}"}.'
                )

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
    behavior_profile: str = 'positive',
    negative_intensity: float = 0.5,
) -> dict[str, PlayerAgent]:
    if behavior_profile not in {'positive', 'negative'}:
        raise PartyConnectorError(f'Unknown behavior profile: {behavior_profile!r}.')
    return {
        controller_id: PlayerAgent(
            persona=persona,
            client=LLMClient(config, transport=llm_transport),
            behavior_profile=behavior_profile,
            negative_intensity=negative_intensity,
        )
        for controller_id, persona in DEFAULT_PERSONAS.items()
    }


def run_party_connector(
    *,
    base_url: str,
    env_path: str | Path = '.env',
    request_timeout_seconds: float | None = 300.0,
    llm_timeout_seconds: float = 300.0,
    poll_interval_seconds: float = 0.5,
    max_actions: int = 60,
    auto_end_monster_turns: bool = True,
    monster_turn_delay_seconds: float = 0.2,
    transcript_path: str | Path | None = None,
    interaction_log_path: str | Path | None = None,
    behavior_profile: str = 'positive',
    negative_intensity: float = 0.5,
    enable_speaker_voting: bool = True,
    llm_transport=None,
    verbose: bool = False,
) -> PartyConnectorResult:
    config = load_llm_config(env_path=env_path)
    automation_client = AutomationHttpClient(base_url, request_timeout_seconds=request_timeout_seconds)
    llm_transport = _build_llm_transport(
        llm_transport=llm_transport,
        interaction_log_path=(Path(interaction_log_path) if interaction_log_path is not None else None),
        llm_timeout_seconds=llm_timeout_seconds,
    )
    connector = PartyConnector(
        automation_client=automation_client,
        player_agents=build_default_player_agents(
            config=config,
            llm_transport=llm_transport,
            behavior_profile=behavior_profile,
            negative_intensity=negative_intensity,
        ),
        poll_interval_seconds=poll_interval_seconds,
        max_actions=max_actions,
        auto_end_monster_turns=auto_end_monster_turns,
        monster_turn_delay_seconds=monster_turn_delay_seconds,
        enable_speaker_voting=enable_speaker_voting,
        transcript_logger=(PartyTranscriptLogger(Path(transcript_path)) if transcript_path is not None else None),
        verbose=verbose,
    )
    return connector.run()


def _build_llm_transport(
    *,
    llm_transport=None,
    interaction_log_path: Path | None = None,
    llm_timeout_seconds: float = 300.0,
):
    transport = llm_transport or LLMHttpTransport(
        timeout_seconds=llm_timeout_seconds,
        stream_timeout_seconds=llm_timeout_seconds,
    )
    if interaction_log_path is None:
        return transport
    return RawInteractionLoggingTransport(
        transport,
        RawInteractionLogger(interaction_log_path),
    )


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


def _parse_speaker_vote(raw_text: str) -> PartySpeakerVote:
    try:
        decoded = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise PartyConnectorError(f'Player agent returned invalid speaker-vote JSON: {exc}') from exc
    if not isinstance(decoded, dict):
        raise PartyConnectorError('Speaker vote reply must be a JSON object.')
    allowed_keys = {'selected_controller_id', 'reason', 'advantage_factors', 'confidence'}
    unexpected_keys = sorted(set(decoded) - allowed_keys)
    if unexpected_keys:
        raise PartyConnectorError(f'Speaker vote reply used unexpected keys: {", ".join(unexpected_keys)}.')
    selected_controller_id = decoded.get('selected_controller_id')
    reason = decoded.get('reason')
    advantage_factors = decoded.get('advantage_factors')
    confidence = decoded.get('confidence')
    if not isinstance(selected_controller_id, str) or not selected_controller_id:
        raise PartyConnectorError('selected_controller_id must be a non-empty string.')
    if not isinstance(reason, str) or not reason.strip():
        raise PartyConnectorError('reason must be a non-empty string.')
    if (
        not isinstance(advantage_factors, list)
        or not advantage_factors
        or not all(isinstance(item, str) and item.strip() for item in advantage_factors)
    ):
        raise PartyConnectorError('advantage_factors must be a non-empty array of strings.')
    if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
        raise PartyConnectorError('confidence must be a number from 0 to 1.')
    return PartySpeakerVote(
        selected_controller_id=selected_controller_id,
        reason=reason.strip(),
        advantage_factors=tuple(item.strip() for item in advantage_factors),
        confidence=float(confidence),
    )


def _speaker_candidates_from_snapshots(
    snapshots: dict[str, dict[str, Any]],
    *,
    public_party_memory: tuple[PartyActionRecord, ...],
) -> tuple[dict[str, Any], ...]:
    candidates: list[dict[str, Any]] = []
    for controller_id in PLAYER_CONTROLLER_IDS:
        snapshot = snapshots.get(controller_id)
        if not isinstance(snapshot, dict):
            continue
        view = _view_from_snapshot(snapshot)
        if view.get('runtime_mode') != 'storytelling':
            continue
        candidates.append(
            _speaker_candidate_from_view(
                controller_id=controller_id,
                view=view,
                public_party_memory=public_party_memory,
            )
        )
    return tuple(candidates)


def _speaker_candidate_from_view(
    *,
    controller_id: str,
    view: dict[str, Any],
    public_party_memory: tuple[PartyActionRecord, ...],
) -> dict[str, Any]:
    card = _first_character_card(view)
    persona = DEFAULT_PERSONAS[controller_id]
    skill_bonuses = _skill_bonus_summary(card)
    ability_modifiers = _ability_modifier_summary(card)
    status = _candidate_status_summary(card)
    advantage = _speaker_advantage(
        controller_id=controller_id,
        scene_text=_speaker_scene_text(view),
        skill_bonuses=skill_bonuses,
        ability_modifiers=ability_modifiers,
        status=status,
        public_party_memory=public_party_memory,
    )
    return {
        'controller_id': controller_id,
        'persona_codename': persona.codename,
        'persona_story_focus': persona.story_focus,
        'persona_coordination_rule': persona.coordination_rule,
        'character': _summarize_character_card(view),
        'skill_bonuses': skill_bonuses,
        'ability_modifiers': ability_modifiers,
        'status': status,
        'advantage_score': advantage['score'],
        'advantage_factors': advantage['factors'],
        'recently_spoke_distance': _recent_speaker_distance(controller_id, public_party_memory),
    }


def _first_character_card(view: dict[str, Any]) -> dict[str, Any] | None:
    cards = view.get('character_cards', [])
    if not isinstance(cards, list) or not cards:
        return None
    card = cards[0]
    return card if isinstance(card, dict) else None


def _skill_bonus_summary(card: dict[str, Any] | None) -> dict[str, int]:
    if card is None:
        return {}
    summary: dict[str, int] = {}
    for skill in card.get('skills', []) or []:
        if not isinstance(skill, dict):
            continue
        label = skill.get('label')
        bonus = skill.get('bonus')
        if isinstance(label, str) and isinstance(bonus, int):
            summary[label.lower()] = bonus
    return summary


def _ability_modifier_summary(card: dict[str, Any] | None) -> dict[str, int]:
    if card is None:
        return {}
    summary: dict[str, int] = {}
    for ability in card.get('abilities', []) or []:
        if not isinstance(ability, dict):
            continue
        ability_id = ability.get('ability_id')
        modifier = ability.get('modifier')
        if isinstance(ability_id, str) and isinstance(modifier, int):
            summary[ability_id.upper()] = modifier
    return summary


def _candidate_status_summary(card: dict[str, Any] | None) -> dict[str, Any]:
    if card is None:
        return {}
    current_hp = card.get('current_hit_points')
    max_hp = card.get('max_hit_points')
    resources = []
    for resource in card.get('resources', []) or []:
        if not isinstance(resource, dict):
            continue
        resources.append(
            {
                'label': resource.get('label'),
                'remaining_uses': resource.get('remaining_uses'),
                'detail': resource.get('detail'),
            }
        )
    return {
        'current_hit_points': current_hp,
        'max_hit_points': max_hp,
        'hit_point_ratio': (round(float(current_hp) / float(max_hp), 3) if isinstance(current_hp, int) and isinstance(max_hp, int) and max_hp > 0 else None),
        'conditions': list(card.get('conditions', []) or []),
        'resources': resources[:8],
        'cantrips': [spell.get('name') for spell in list(card.get('cantrips', []))[:8] if isinstance(spell, dict)],
        'spells': [spell.get('name') for spell in list(card.get('spells', []))[:10] if isinstance(spell, dict)],
        'items': [item.get('label') or item.get('name') for item in list(card.get('items', []))[:12] if isinstance(item, dict)],
    }


def _speaker_scene_text(view: dict[str, Any]) -> str:
    parts = []
    parts.extend(line for line in view.get('summary_lines', []) if isinstance(line, str))
    for entry in list(view.get('chat_entries', []))[-10:]:
        if not isinstance(entry, dict):
            continue
        text = entry.get('text')
        if isinstance(text, str):
            parts.append(text)
    return ' '.join(parts).lower()


def _speaker_advantage(
    *,
    controller_id: str,
    scene_text: str,
    skill_bonuses: dict[str, int],
    ability_modifiers: dict[str, int],
    status: dict[str, Any],
    public_party_memory: tuple[PartyActionRecord, ...],
) -> dict[str, Any]:
    score = 0.0
    factors: list[str] = []
    if any(term in scene_text for term in ('gundren', 'sildar', 'bargain', 'pay', 'gold', 'terms', 'persuasion')):
        charisma = ability_modifiers.get('CHA', 0)
        persuasion = skill_bonuses.get('persuasion', charisma)
        social_score = max(charisma, persuasion)
        score += social_score
        factors.append(f'social check fit {social_score:+d}')
    if any(term in scene_text for term in ('secret', 'holding back', 'hiding', 'truth', 'worry', 'afraid', 'insight')):
        insight = skill_bonuses.get('insight', ability_modifiers.get('WIS', 0))
        score += insight
        factors.append(f'insight fit {insight:+d}')
    if any(term in scene_text for term in ('magic', 'magical', 'arcana', 'undead', 'aberration', 'sigil')):
        arcana = skill_bonuses.get('arcana', ability_modifiers.get('INT', 0))
        score += arcana
        factors.append(f'arcana fit {arcana:+d}')
    if any(term in scene_text for term in ('wagon', 'supplies', 'ledger', 'route', 'road', 'trail', 'equipment')):
        logistics = max(
            skill_bonuses.get('investigation', ability_modifiers.get('INT', 0)),
            skill_bonuses.get('survival', ability_modifiers.get('WIS', 0)),
        )
        score += logistics
        factors.append(f'logistics fit {logistics:+d}')
    hp_ratio = status.get('hit_point_ratio')
    if isinstance(hp_ratio, float):
        if hp_ratio >= 0.5:
            score += 1.0
            factors.append('healthy enough to lead')
        else:
            score -= 2.0
            factors.append('low hit points')
    conditions = status.get('conditions')
    if isinstance(conditions, list) and conditions:
        score -= 2.0
        factors.append(f'conditions: {", ".join(str(item) for item in conditions[:3])}')
    recent_distance = _recent_speaker_distance(controller_id, public_party_memory)
    if recent_distance <= 2:
        score -= 1.5
        factors.append('spoke recently')
    elif recent_distance >= 6:
        score += 0.5
        factors.append('has not spoken recently')
    return {'score': round(score, 3), 'factors': factors[:6]}


def _recent_speaker_distance(controller_id: str, public_party_memory: tuple[PartyActionRecord, ...]) -> int:
    for distance, record in enumerate(reversed(public_party_memory), start=1):
        if record.controller_id == controller_id:
            return distance
    return 999


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
        'visible_enemy_target_ids': _visible_enemy_target_ids(view),
        'legal_attack_option_ids': _available_choice_ids(view, 'attacks'),
        'legal_spell_option_ids': _available_choice_ids(view, 'magic'),
        'safe_fallback_command': _combat_fallback_command(view),
        'command_templates': {
            'attack': f'/attack {view.get("active_actor_id") or "<active_actor_id>"} <attack option_id> <target actor id>',
            'cast_targeted_spell': f'/cast {view.get("active_actor_id") or "<active_actor_id>"} <spell option_id> <target actor id>',
            'dodge': f'/dodge {view.get("active_actor_id") or "<active_actor_id>"}',
            'end_turn': f'/endturn {view.get("active_actor_id") or "<active_actor_id>"}',
        },
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


def _available_choice_ids(view: dict[str, Any], group_id: str) -> tuple[str, ...]:
    ids: list[str] = []
    for group in view.get('action_groups', []):
        if not isinstance(group, dict) or group.get('group_id') != group_id:
            continue
        for choice in group.get('choices', []):
            if not isinstance(choice, dict):
                continue
            option_id = choice.get('option_id')
            if isinstance(option_id, str) and option_id:
                ids.append(option_id)
    return tuple(ids)


def _visible_enemy_target_ids(view: dict[str, Any]) -> tuple[str, ...]:
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return ()
    targets: list[str] = []
    for token in map_view.get('tokens', []):
        if not isinstance(token, dict):
            continue
        actor_id = token.get('actor_id')
        if not isinstance(actor_id, str) or not actor_id:
            continue
        if token.get('side') != 'monster':
            continue
        if token.get('status') not in {None, 'active'}:
            continue
        targets.append(actor_id)
    return tuple(targets)


def _has_available_combat_action(view: dict[str, Any]) -> bool:
    for group_id in ('attacks', 'magic', 'actions'):
        if _available_choice_ids(view, group_id):
            return True
    return False


def _combat_fallback_command(view: dict[str, Any]) -> str | None:
    active_actor_id = _string_or_none(view.get('active_actor_id'))
    if not active_actor_id:
        return None
    target_ids = _visible_enemy_target_ids(view)
    if target_ids:
        attack_ids = _available_choice_ids(view, 'attacks')
        preferred_attack = _preferred_ranged_attack_id(attack_ids)
        if preferred_attack is not None:
            return f'/attack {active_actor_id} {preferred_attack} {target_ids[0]}'
        spell_ids = _available_choice_ids(view, 'magic')
        preferred_spell = _preferred_targeted_spell_id(spell_ids)
        if preferred_spell is not None:
            return f'/cast {active_actor_id} {preferred_spell} {target_ids[0]}'
    if 'dodge' in _available_choice_ids(view, 'actions'):
        return f'/dodge {active_actor_id}'
    if 'dash' in _available_choice_ids(view, 'actions'):
        return f'/dash {active_actor_id}'
    return f'/endturn {active_actor_id}'


def _preferred_ranged_attack_id(attack_ids: tuple[str, ...]) -> str | None:
    for marker in ('ranged', 'thrown'):
        for attack_id in attack_ids:
            if marker in attack_id:
                return attack_id
    return None


def _preferred_targeted_spell_id(spell_ids: tuple[str, ...]) -> str | None:
    priority = (
        'magic-missile',
        'fire-bolt',
        'sacred-flame',
        'guiding-bolt',
        'ray-of-frost',
        'vicious-mockery',
        'witch-bolt',
        'toll-the-dead',
        'chill-touch',
        'acid-splash',
    )
    for spell_id in priority:
        if spell_id in spell_ids:
            return spell_id
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


def _has_direct_dialogue(text: str) -> bool:
    stripped = text.strip()
    if _DIRECT_ADDRESS_RE.search(stripped):
        return True
    if re.search(r'"[^"]{3,}"', stripped):
        return True
    return re.search(r"(?<!\w)'[^']{3,}'(?!\w)", stripped) is not None


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
    parser.add_argument(
        '--llm-timeout-seconds',
        type=float,
        default=300.0,
        help='HTTP request timeout for player-agent LLM calls.',
    )
    parser.add_argument('--poll-interval-seconds', type=float, default=0.5, help='Polling interval while waiting for the next actionable player turn.')
    parser.add_argument('--max-actions', type=int, default=60, help='Maximum number of connector-driven actions before exiting.')
    parser.add_argument('--disable-auto-end-monster-turns', action='store_true', help='Do not auto-pass DM-owned monster turns during combat.')
    parser.add_argument('--disable-speaker-voting', action='store_true', help='Use legacy round-robin story speakers instead of party speaker votes.')
    parser.add_argument('--monster-turn-delay-seconds', type=float, default=0.2, help='Delay after auto-ending a monster turn.')
    parser.add_argument('--transcript-path', help='Optional path to a local transcript log file for player actions and visible DM/public outputs.')
    parser.add_argument('--interaction-log-path', help='Optional JSONL path for raw player-agent LLM request/response records.')
    parser.add_argument('--behavior-profile', choices=('positive', 'negative'), default='positive', help='Prompt profile for positive or negative RL data collection.')
    parser.add_argument('--negative-intensity', type=float, default=0.5, help='Negative-profile intensity from 0.0 to 1.0.')
    parser.add_argument('--verbose', action='store_true', help='Print each accepted connector action.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.request_timeout_seconds < 0:
        raise SystemExit('ERROR: --request-timeout-seconds must be >= 0.')
    if args.llm_timeout_seconds <= 0:
        raise SystemExit('ERROR: --llm-timeout-seconds must be > 0.')
    if args.poll_interval_seconds <= 0:
        raise SystemExit('ERROR: --poll-interval-seconds must be > 0.')
    if args.max_actions <= 0:
        raise SystemExit('ERROR: --max-actions must be > 0.')
    if args.monster_turn_delay_seconds < 0:
        raise SystemExit('ERROR: --monster-turn-delay-seconds must be >= 0.')
    if args.negative_intensity < 0 or args.negative_intensity > 1:
        raise SystemExit('ERROR: --negative-intensity must be between 0 and 1.')
    result = run_party_connector(
        base_url=args.base_url,
        env_path=Path(args.env_path),
        request_timeout_seconds=(None if args.request_timeout_seconds == 0 else args.request_timeout_seconds),
        llm_timeout_seconds=args.llm_timeout_seconds,
        poll_interval_seconds=args.poll_interval_seconds,
        max_actions=args.max_actions,
        auto_end_monster_turns=not args.disable_auto_end_monster_turns,
        monster_turn_delay_seconds=args.monster_turn_delay_seconds,
        transcript_path=(Path(args.transcript_path) if args.transcript_path else None),
        interaction_log_path=(Path(args.interaction_log_path) if args.interaction_log_path else None),
        behavior_profile=args.behavior_profile,
        negative_intensity=args.negative_intensity,
        enable_speaker_voting=not args.disable_speaker_voting,
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
