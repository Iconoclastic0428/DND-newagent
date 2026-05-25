from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import threading
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

_ACTION_DECISION_TEMPLATE_TEXT = '<write one unique in-character action or slash command here>'
_OBSERVED_COPIED_ACTION_EXAMPLE_TEXT = 'Gundren, what signs of danger should we watch for on the road?'
_COPIED_ACTION_TEMPLATE_TEXTS = {
    _ACTION_DECISION_TEMPLATE_TEXT.casefold(),
    _OBSERVED_COPIED_ACTION_EXAMPLE_TEXT.casefold(),
}

_ACTION_DECISION_TEMPLATE = json.dumps(
    {
        'decision_type': 'command',
        'text': _ACTION_DECISION_TEMPLATE_TEXT,
        'option_id': None,
        'option_ids': [],
        'topic_focus': 'unique action focus',
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

_DM_COMBAT_DECISION_TEMPLATE = json.dumps(
    {
        'decision_type': 'command',
        'text': '/attack monster-goblin-1 shortbow player-1',
        'option_id': None,
        'option_ids': [],
        'topic_focus': 'monster tactical action',
        'reason': 'The active monster uses a legal visible combat option.',
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
_EMBEDDED_SLASH_COMMAND_RE = re.compile(r'(?<!\S)/(?:check|move|attack|cast|dodge|help|dash|disengage|hide|ready|search|use|do|improvise|travel|march|watch|role|camp|social|trap|puzzle|downtime|progression|levelup)\b', re.IGNORECASE)
_TRAVEL_COMMAND_USAGE = 'Unknown travel command. Use /travel status|pace|route|advance|resume|engage.'
_TRAVEL_SUBCOMMANDS = {'status', 'pace', 'route', 'advance', 'resume', 'engage'}
_TRAVEL_PACES = {'cautious', 'normal', 'fast'}
_COMBAT_SPELL_TARGET_RANGES_FEET = {
    'charm-person': 30,
    'fire-bolt': 120,
    'magic-missile': 120,
}
_COMBAT_TARGETED_SPELL_IDS = frozenset(_COMBAT_SPELL_TARGET_RANGES_FEET)
_COMBAT_POINT_TARGET_SPELL_IDS = {
    'light',
    'mage-hand',
}
_STALE_BRIEFING_FORBIDDEN_RE = re.compile(
    r'\?|'
    r'\blet\s+us\b|'
    r'\b(?:deal|ledger|bargain|terms|pay|gold|potion|secret|found|magic|spell|inspect|copy|what|why|before)\b',
    re.IGNORECASE,
)
_SAFE_BRIEFING_ACCEPTANCE_TEXT = 'Gundren, we accept the job. We will take the wagon to Phandalin.'
_PLAYER_ACTION_MAX_OUTPUT_TOKENS = 1200
_PLAYER_RETRY_MAX_OUTPUT_TOKENS = 800
_SPEAKER_VOTE_MAX_OUTPUT_TOKENS = 700
_DM_COMBAT_MAX_OUTPUT_TOKENS = 900
_DM_COMBAT_RETRY_MAX_OUTPUT_TOKENS = 700
_RECENT_CHAT_TEXT_LIMIT = 420
_SPEAKER_RECENT_CHAT_TEXT_LIMIT = 260
_RETRY_OUTPUT_PREVIEW_LIMIT = 1200

_DIRECT_ADDRESS_RE = re.compile(r'^[A-Z][A-Za-z\' -]{2,},\s+\S+')
_KNOWN_SCENE_NPC_NAMES = {
    'gundren-rockseeker': ('Gundren', 'Gundren Rockseeker', 'Master Rockseeker'),
    'sildar-hallwinter': ('Sildar', 'Sildar Hallwinter'),
}
_SELF_NARRATION_VERBS_RE = (
    r'asks?|begins?|casts?|checks?|draws?|flicks?|fix(?:es)?|gestures?|grins?|heads?|holds?|inspects?|kneels?|leans?|'
    r'keeps?|lifts?|looks?|moves?|murmurs?|narrows?|nods?|points?|presses?|produces?|pulls?|raises?|rolls?|says?|sets?|'
    r'shifts?|slides?|smiles?|speaks?|steps?|studies?|tells?|tilts?|traces?|turns?|warns?|waves?|whispers?'
)
_SELF_NARRATION_GENDERED_PRONOUNS_RE = r'(?:she|he)'
_SELF_NARRATION_PRONOUNS_RE = r'(?:she|he|they)'


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


class DMCombatPlanningError(PartyConnectorError):
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
    _seen_chat_entry_fingerprints: set[str] = field(default_factory=set, init=False, repr=False)
    _recent_combat_event_sequence: list[str] = field(default_factory=list, init=False, repr=False)
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
            combat_event_texts: list[str] = []
            for entry in view.get('chat_entries', []):
                if not isinstance(entry, dict):
                    continue
                entry_id = entry.get('entry_id')
                if not isinstance(entry_id, str) or not entry_id:
                    continue
                visibility = entry.get('visibility')
                if visibility not in {'public', 'dm_only'}:
                    continue
                speaker = entry.get('speaker') or 'Unknown'
                category = entry.get('category') or 'story'
                text = entry.get('text') or ''
                if visibility == 'public' and category == 'combat' and speaker == 'System':
                    if entry_id in self._seen_chat_entry_ids:
                        continue
                    self._seen_chat_entry_ids.add(entry_id)
                    combat_event_texts.append(str(text))
                    continue
                fingerprint = f'{visibility}\0{category}\0{speaker}\0{text}'
                if fingerprint in self._seen_chat_entry_fingerprints:
                    continue
                self._seen_chat_entry_ids.add(entry_id)
                self._seen_chat_entry_fingerprints.add(fingerprint)
                self._append(f'[chat:{visibility}:{category}] {speaker}: {text}')
            self._record_combat_event_texts(combat_event_texts)
            self._record_recent_event_summary_lines(view)
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

    def _record_recent_event_summary_lines(self, view: dict[str, Any]) -> None:
        if not self._is_demo_complete_view(view):
            return
        in_recent_events = False
        combat_event_texts: list[str] = []
        for line in view.get('summary_lines', ()):
            if not isinstance(line, str):
                continue
            if line == 'Recent events:':
                in_recent_events = True
                continue
            if not in_recent_events:
                continue
            if not line.startswith('  - '):
                break
            combat_event_texts.append(line[4:])
        self._record_combat_event_texts(combat_event_texts)

    def _is_demo_complete_view(self, view: dict[str, Any]) -> bool:
        for line in view.get('summary_lines', ()):
            if line == 'Runtime mode: demo-complete':
                return True
        return False

    def _record_combat_event_texts(self, event_texts: list[str]) -> None:
        if not event_texts:
            return
        if self._contains_recent_combat_subsequence(event_texts):
            return
        overlap = self._recent_combat_event_overlap(event_texts)
        for text in event_texts[overlap:]:
            self._recent_combat_event_sequence.append(text)
            self._append(f'[chat:public:combat] System: {text}')

    def _contains_recent_combat_subsequence(self, event_texts: list[str]) -> bool:
        if not event_texts:
            return True
        if len(event_texts) > len(self._recent_combat_event_sequence):
            return False
        last_start = len(self._recent_combat_event_sequence) - len(event_texts)
        for start in range(last_start + 1):
            if self._recent_combat_event_sequence[start : start + len(event_texts)] == event_texts:
                return True
        return False

    def _recent_combat_event_overlap(self, event_texts: list[str]) -> int:
        max_overlap = min(len(self._recent_combat_event_sequence), len(event_texts))
        for overlap in range(max_overlap, 0, -1):
            if self._recent_combat_event_sequence[-overlap:] == event_texts[:overlap]:
                return overlap
        return 0

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
        current_scene_story_turn_count: int = 0,
        previous_output: str | None = None,
        error_message: str | None = None,
        attempt_number: int = 1,
    ) -> tuple[PartyActionDecision, str]:
        request = self._build_request(
            snapshot,
            public_party_memory=public_party_memory,
            current_scene_story_turn_count=current_scene_story_turn_count,
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
        current_scene_story_turn_count: int,
        previous_output: str | None,
        error_message: str | None,
        attempt_number: int,
    ):
        view = _view_from_snapshot(snapshot)
        prompt = snapshot.get('prompt')
        scene_id = _string_or_none(view.get('current_scene_id'))
        scene_progress_pressure = _scene_progress_pressure(scene_id, current_scene_story_turn_count)
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
            'current_scene_id': scene_id,
            'current_scene_story_turn_count': current_scene_story_turn_count,
            'scene_progress_pressure': scene_progress_pressure,
            'round_number': view.get('round_number'),
            'active_actor_id': view.get('active_actor_id'),
            'owned_actor_ids': list(view.get('owned_actor_ids', [])),
            'summary_lines': _compact_summary_lines(view, limit=16),
            'recent_chat_entries': _recent_chat_entries(view, limit=10, text_limit=_RECENT_CHAT_TEXT_LIMIT),
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
                + 'The JSON template is shape-only; never copy its placeholder text or any example sentence verbatim. '
                + 'decision_type must be one of command, prompt_response, wait. '
                + 'Stay strictly in persona. Use only information visible in the provided controller-local context. '
                + 'Respect public/private boundaries; never invent hidden knowledge. '
                + 'If a prompt is present and its prompt_kind is story-check, you should usually answer with decision_type=command and text=/check. '
                + 'Never use /check unless a visible story-check prompt is present; without that prompt, describe the examination or attempted action directly. '
                + 'If a prompt is present and its prompt_kind is reaction or timing-order, answer with decision_type=prompt_response and choose only from the visible prompt option ids. '
                + 'In combat, use slash commands only. Prefer legal commands grounded in the visible actor ids, action hints, spells, items, and current battlefield. '
                + 'For weapon attacks, always use the full syntax /attack <active_actor_id> <attack option_id> <target_actor_id>. '
                + 'The active_actor_id, legal attack option ids, and visible enemy target actor ids are listed in the combat context. '
                + 'Do not choose /endturn while attacks, spells, or normal actions are still available. If enemies are out of melee range, prefer a thrown/ranged attack, a targeted spell, or /dodge <active_actor_id>. '
                + 'In story mode, prefer natural declarations unless a visible slash command is clearly the better move. '
                + 'If you speak to an NPC in story mode, write the character\'s actual words as direct dialogue or quoted direct speech. '
                + 'Do not write narrated speech such as "I ask Gundren..." or "I tell Sildar...". '
                + 'Only address NPCs who are visibly present in the current scene; if Gundren or Sildar are rescue targets or absent clues, refer to them in third person instead of speaking to them. '
                + 'Do not append third-person self narration such as "Iri produces..." or "She turns..." after quoted dialogue. '
                + 'Good style, not content to copy: "Gundren, do you think that is too little gold up front? We need equipment before the road." '
                + 'If you are doing a nonverbal action, describe the action directly and only include spoken words as dialogue. '
                + 'Be creative with spell and item usage, but keep it legal and grounded in the current character card and visible scene. '
                + 'Do not repeat the previous player\'s point. Either build on it from your own angle or introduce a different unresolved thread. '
                + 'topic_focus must be a short phrase describing the unique angle of your action. '
                + self._behavior_profile_instruction(scene_progress_pressure=scene_progress_pressure)
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
                                    'previous_invalid_output': _truncate_text(previous_output or '', _RETRY_OUTPUT_PREVIEW_LIMIT),
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
            metadata={
                'request_type': 'party_player_retry' if error_message is not None else 'party_player_turn',
                'controller_id': self.persona.controller_id,
            },
            temperature=0.7,
            max_output_tokens=_PLAYER_RETRY_MAX_OUTPUT_TOKENS if error_message is not None else _PLAYER_ACTION_MAX_OUTPUT_TOKENS,
            response_format={'type': 'json_object'},
            thinking_enabled=error_message is None,
            reasoning_effort='medium' if error_message is None else None,
        )

    def _behavior_profile_instruction(self, *, scene_progress_pressure: str = 'normal') -> str:
        if self.behavior_profile == 'negative':
            return (
                'This episode is collecting negative RL training examples. '
                f'Negative intensity is {self.negative_intensity:.2f}. '
                'Keep the action legal and parseable so the conversation can continue, but deliberately include some lower-quality player behavior: '
                'stalling, redundant concerns, repeated wording, over-cautious delay, or actions that fail to finish visible scene goals or hidden subgoals. '
                'Do not make every turn bad; mix in enough useful actions that the run can still progress and produce both positive and negative reward signs.'
                + (
                    ' This is a stale scene; keep the lower-quality flavor brief, then move the scene forward with a concrete imperfect action instead of asking another preparatory question.'
                    if scene_progress_pressure == 'close_scene_now'
                    else ''
                )
            )
        if self.behavior_profile != 'positive':
            raise PartyConnectorError(f'Unknown behavior profile: {self.behavior_profile!r}.')
        return (
            'This episode is collecting positive RL training examples. '
            'Act to finish visible scene goals and uncover or complete hidden subgoals. '
            'Prefer concrete progress: resolve open loops, reveal useful discoveries, answer pending checks, improve social leverage, and move the scene forward. '
            'You should avoid repeated wording, repeated questions, and stalling. '
            + (
                'The current scene has become stale; close the scene now; stop asking preparatory questions. '
                'Choose a concrete closure action: accept or lock terms, finish the current party goal, start travel, or otherwise move the party to the next scene. '
                'If the scene is the Gundren wagon briefing, use plain acceptance and departure; do not add new demands, ledger requests, bargaining terms, or fresh checks. '
                f'Good stale-briefing closure: "{_SAFE_BRIEFING_ACCEPTANCE_TEXT}" '
                'If the scene is the High Road journey, use the authoritative travel commands: /travel route phandalin when travel is idle, then /travel advance 5 when a route is planned.'
                if scene_progress_pressure == 'close_scene_now'
                else ''
            )
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
            'summary_lines': _compact_summary_lines(view, limit=10),
            'recent_chat_entries': _recent_chat_entries(view, limit=6, text_limit=_SPEAKER_RECENT_CHAT_TEXT_LIMIT),
            'recent_visible_check_entries': _recent_check_entries(view),
            'recent_party_actions': [
                {
                    'controller_id': record.controller_id,
                    'scene_id': record.scene_id,
                    'runtime_mode': record.runtime_mode,
                    'text': _truncate_text(record.text, _SPEAKER_RECENT_CHAT_TEXT_LIMIT),
                    'topic_focus': record.topic_focus,
                }
                for record in public_party_memory[-4:]
            ],
            'speaker_candidates': [_compact_speaker_candidate(candidate) for candidate in speaker_candidates],
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
                + 'Use the compact candidate summaries; do not ask for more context. '
                + 'reason must briefly explain the concrete advantage. '
                + 'advantage_factors must list one to three short evidence strings. confidence must be a number from 0 to 1.'
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
                                    'previous_invalid_output': _truncate_text(previous_output or '', _RETRY_OUTPUT_PREVIEW_LIMIT),
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
            max_output_tokens=_SPEAKER_VOTE_MAX_OUTPUT_TOKENS,
            response_format={'type': 'json_object'},
            thinking_enabled=False,
        )


class DMCombatAgent:
    def __init__(self, *, client: LLMClient, label: str | None = None) -> None:
        self.client = client
        self.label = label or client.config.responses_model

    def plan_monster_action(
        self,
        snapshot: dict[str, Any],
        *,
        previous_output: str | None = None,
        error_message: str | None = None,
        attempt_number: int = 1,
    ) -> tuple[PartyActionDecision, str]:
        request = self._build_request(
            snapshot,
            previous_output=previous_output,
            error_message=error_message,
            attempt_number=attempt_number,
        )
        response = self.client.create_response(request)
        output_text = response.output_text
        try:
            return _parse_action_decision(output_text), output_text
        except PartyConnectorError as exc:
            raise DMCombatPlanningError(str(exc), raw_output=output_text) from exc

    def _build_request(
        self,
        snapshot: dict[str, Any],
        *,
        previous_output: str | None,
        error_message: str | None,
        attempt_number: int,
    ):
        view = _view_from_snapshot(snapshot)
        context_payload = {
            'controller_id': 'dm',
            'runtime_mode': view.get('runtime_mode'),
            'current_scene_id': view.get('current_scene_id'),
            'round_number': view.get('round_number'),
            'active_actor_id': view.get('active_actor_id'),
            'owned_actor_ids': list(view.get('owned_actor_ids', [])),
            'summary_lines': _compact_summary_lines(view, limit=18),
            'recent_chat_entries': _recent_chat_entries(view, limit=8, text_limit=_RECENT_CHAT_TEXT_LIMIT),
            'action_groups': _summarize_action_groups(view),
            'combat': _summarize_combat_view(view),
        }
        if error_message is None:
            instructions = (
                'You are the Dungeon Master controlling the active monster in D&D combat. '
                + build_json_object_contract(template=_DM_COMBAT_DECISION_TEMPLATE)
                + ' The root object must contain exactly these keys: decision_type, text, option_id, option_ids, topic_focus, reason. '
                + 'decision_type must be command. '
                + 'Use only the active_actor_id and legal visible slash-command options in the provided combat context. '
                + 'Do not narrate outcomes, roll dice, change HP, invent hidden state, or decide whether an attack hits; the rules engine resolves mechanics. '
                + 'Prefer a legal attack, targeted spell, or tactical action over ending the turn while the monster still has an action. '
                + 'For attacks, always use /attack <active_actor_id> <attack option_id> <target actor id>. '
                + 'Visible enemy target actor ids are listed in combat.visible_enemy_target_ids. '
                + 'Use /endturn <active_actor_id> only when no useful legal action remains or the monster has already spent its action.'
            )
            input_messages = (
                {
                    'role': 'user',
                    'content': [{'type': 'input_text', 'text': json.dumps(context_payload, sort_keys=True)}],
                },
            )
        else:
            instructions = (
                'You are retrying a DM monster combat command after deterministic validation failed. '
                + build_json_retry_contract(template=_DM_COMBAT_DECISION_TEMPLATE, attempt_number=attempt_number)
                + ' Fix the exact error and return one corrected legal slash command only.'
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
                                    'required_json_template': _DM_COMBAT_DECISION_TEMPLATE,
                                    'previous_invalid_output': _truncate_text(previous_output or '', _RETRY_OUTPUT_PREVIEW_LIMIT),
                                    'task': 'Re-emit one corrected JSON DM monster combat action.',
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
            metadata={
                'request_type': 'dm_monster_retry' if error_message is not None else 'dm_monster_turn',
                'controller_id': 'dm',
            },
            temperature=0.35,
            max_output_tokens=_DM_COMBAT_RETRY_MAX_OUTPUT_TOKENS if error_message is not None else _DM_COMBAT_MAX_OUTPUT_TOKENS,
            response_format={'type': 'json_object'},
            thinking_enabled=error_message is None,
            reasoning_effort='medium' if error_message is None else None,
        )


class PartyConnector:
    def __init__(
        self,
        *,
        automation_client: AutomationHttpClient,
        player_agents: dict[str, PlayerAgent],
        dm_combat_agent: DMCombatAgent | None = None,
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
        self.dm_combat_agent = dm_combat_agent
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
        self._invalid_action_retries_lock = threading.Lock()

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
            player_view = _view_from_snapshot(snapshots[controller_id])
            if not _active_actor_action_available(player_view):
                command = f'/endturn {active_actor_id}'
                self._log(f'[combat] player action spent; auto-passes {active_actor_id}')
                self._validate_combat_command(player_view, command)
                self.automation_client.submit(controller_id, command)
                if self.transcript_logger is not None:
                    self.transcript_logger.record_system_action(controller_id, command)
                    self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
                self.commands_sent += 1
                self.turns_taken += 1
                return True
            self._execute_player_action(controller_id, snapshots[controller_id], count_for_story_rotation=False)
            return True
        if not self.auto_end_monster_turns:
            return False
        if dm_snapshot.get('prompt') is not None:
            raise PartyConnectorError('Combat is waiting on a DM-owned prompt that the player connector cannot answer.')
        if active_actor_id in tuple(dm_view.get('owned_actor_ids', ())) and self.dm_combat_agent is not None:
            if not _active_actor_action_available(dm_view):
                return self._execute_dm_end_turn(dm_view, active_actor_id)
            self._execute_dm_monster_action(dm_snapshot)
            return True
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

    def _execute_dm_end_turn(self, dm_view: dict[str, Any], active_actor_id: str) -> bool:
        command = f'/endturn {active_actor_id}'
        self._validate_combat_command(dm_view, command)
        self._log(f'[dm] {command}')
        self.automation_client.submit('dm', command)
        if self.transcript_logger is not None:
            self.transcript_logger.record_player_action(
                'dm',
                PartyActionDecision(
                    decision_type='command',
                    text=command,
                    option_id=None,
                    option_ids=(),
                    topic_focus='dm monster end turn',
                    reason='The active monster has already spent its action.',
                ),
            )
            self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
        self.commands_sent += 1
        self.turns_taken += 1
        if self.monster_turn_delay_seconds > 0:
            time.sleep(self.monster_turn_delay_seconds)
        return True

    def _execute_dm_monster_action(self, dm_snapshot: dict[str, Any]) -> None:
        if self.dm_combat_agent is None:
            raise PartyConnectorError('DM combat agent is not configured.')
        previous_output: str | None = None
        error_message: str | None = None
        current_snapshot = dm_snapshot
        for attempt in range(1, 4):
            raw_output = ''
            try:
                decision, raw_output = self.dm_combat_agent.plan_monster_action(
                    current_snapshot,
                    previous_output=previous_output,
                    error_message=error_message,
                    attempt_number=attempt,
                )
                self._validate_dm_combat_decision(current_snapshot, decision)
                self._apply_decision('dm', current_snapshot, decision)
                if self.transcript_logger is not None:
                    self.transcript_logger.record_player_action('dm', decision)
                    self.transcript_logger.record_snapshots(self._fetch_all_snapshots())
                self.turns_taken += 1
                if self.monster_turn_delay_seconds > 0:
                    time.sleep(self.monster_turn_delay_seconds)
                return
            except (PartyConnectorError, LiveWebStoryDemoError) as exc:
                if isinstance(exc, DMCombatPlanningError):
                    raw_output = exc.raw_output
                previous_output = raw_output
                error_message = str(exc)
                self._increment_invalid_action_retries()
                if attempt >= 3:
                    raise PartyConnectorError(f'DM monster combat action failed validation after 3 attempts: {error_message}') from exc
                current_snapshot = self.automation_client.state('dm')
        raise PartyConnectorError('Unable to obtain a valid DM monster combat action.')

    def _validate_dm_combat_decision(self, snapshot: dict[str, Any], decision: PartyActionDecision) -> None:
        view = _view_from_snapshot(snapshot)
        if _string_or_none(view.get('runtime_mode')) != 'combat':
            raise PartyConnectorError('DM monster combat agent may only act in combat mode.')
        if snapshot.get('prompt') is not None:
            raise PartyConnectorError('DM monster combat agent cannot answer DM prompts.')
        active_actor_id = _string_or_none(view.get('active_actor_id'))
        owned_actor_ids = tuple(view.get('owned_actor_ids', ()))
        if active_actor_id is None or active_actor_id not in owned_actor_ids:
            raise PartyConnectorError('DM monster combat agent can only act for a DM-owned active actor.')
        if decision.decision_type != 'command':
            raise PartyConnectorError('DM monster combat decisions must use decision_type=command.')
        if not decision.text.strip().startswith('/'):
            raise PartyConnectorError('DM monster combat decisions must use slash commands only.')
        self._validate_combat_command(view, decision.text)

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
        votes_by_voter: dict[str, PartySpeakerVote] = {}
        with ThreadPoolExecutor(max_workers=len(candidate_ids)) as executor:
            future_by_voter = {
                executor.submit(
                    self._collect_speaker_vote,
                    voter_controller_id,
                    snapshots[voter_controller_id],
                    candidates=candidates,
                    candidate_ids=candidate_ids,
                ): voter_controller_id
                for voter_controller_id in candidate_ids
            }
            for future in as_completed(future_by_voter):
                voter_controller_id = future_by_voter[future]
                votes_by_voter[voter_controller_id] = future.result()
        votes = [votes_by_voter[voter_controller_id] for voter_controller_id in candidate_ids]
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
                self._increment_invalid_action_retries()
                if attempt >= 3:
                    raise
        raise PartyConnectorError(f'Unable to obtain a valid speaker vote from {voter_controller_id}.')

    def _increment_invalid_action_retries(self) -> None:
        with self._invalid_action_retries_lock:
            self.invalid_action_retries += 1

    def _turns_since_story_action(self, controller_id: str) -> int:
        for distance, record in enumerate(reversed(self._public_history), start=1):
            if record.controller_id == controller_id:
                return distance
        return 999

    def _current_scene_story_turn_count(self, snapshot: dict[str, Any]) -> int:
        view = _view_from_snapshot(snapshot)
        scene_id = _string_or_none(view.get('current_scene_id'))
        if scene_id is None:
            return 0
        return sum(
            1
            for record in self._public_history
            if record.runtime_mode == 'storytelling' and record.scene_id == scene_id
        )

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
                    current_scene_story_turn_count=self._current_scene_story_turn_count(current_snapshot),
                    previous_output=previous_output,
                    error_message=error_message,
                    attempt_number=attempt,
                )
                decision = self._normalize_decision(controller_id, current_snapshot, decision)
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
                self._increment_invalid_action_retries()
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

    def _normalize_decision(
        self,
        controller_id: str,
        snapshot: dict[str, Any],
        decision: PartyActionDecision,
    ) -> PartyActionDecision:
        view = _view_from_snapshot(snapshot)
        prompt = snapshot.get('prompt')
        if isinstance(prompt, dict):
            prompt_kind = _string_or_none(prompt.get('prompt_kind'))
            if prompt_kind in {'reaction', 'timing-order'} and decision.decision_type == 'command':
                option_id = _prompt_option_id_matching_text(prompt, decision.text)
                if option_id is not None:
                    return PartyActionDecision(
                        decision_type='prompt_response',
                        text='',
                        option_id=option_id,
                        option_ids=(),
                        topic_focus=decision.topic_focus or f'{prompt_kind} prompt response',
                        reason=f'{decision.reason} Normalized clear {prompt_kind} intent to a prompt option.',
                    )
            if prompt_kind == 'story-check' and decision.decision_type == 'command' and _looks_like_check_response(decision.text):
                return PartyActionDecision(
                    decision_type='command',
                    text='/check',
                    option_id=None,
                    option_ids=(),
                    topic_focus=decision.topic_focus or 'resolve requested check',
                    reason=f'{decision.reason} Normalized clear check intent to /check.',
                )
            return decision
        if _string_or_none(view.get('runtime_mode')) != 'storytelling':
            return decision
        scene_id = _string_or_none(view.get('current_scene_id'))
        if _scene_progress_pressure(scene_id, self._current_scene_story_turn_count(snapshot)) != 'close_scene_now':
            return decision
        if scene_id == 'scene-waterdeep-gundren-briefing':
            return _normalize_stale_briefing_decision(view, decision)
        if scene_id == 'scene-00-high-road-journey':
            return _normalize_stale_high_road_decision(view, decision)
        return decision

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
        if scene_id == 'scene-waterdeep-gundren-briefing':
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
        elif scene_id == 'scene-00-high-road-journey':
            travel_status = _travel_status(view)
            if travel_status == 'route_planned':
                fallback_options = (('advance planned travel', '/travel advance 5'),)
            elif travel_status == 'idle':
                fallback_options = (('route to phandalin', '/travel route phandalin'),)
            else:
                fallback_options = (
                    (
                        'road watch',
                        'I keep watch along the road and check the wagon, team, and surrounding terrain for immediate trouble.',
                    ),
                    (
                        'wagon control',
                        'I keep the wagon moving steadily while watching the brush and road ahead for signs of danger.',
                    ),
                )
        else:
            fallback_options = (
                (
                    'ambush investigation',
                    'I inspect the road, brush, riderless horses, and torn packs for tracks or signs of where the attackers went.',
                ),
                (
                    'secure wagon',
                    'I keep the wagon guarded while the party checks the brush, horses, and scattered gear for danger.',
                ),
                (
                    'watch treeline',
                    'I watch the treeline and listen for movement before anyone moves deeper into the ambush site.',
                ),
                (
                    'compare clues',
                    'I compare the tracks, torn packs, and horse tack to work out who attacked and where they went.',
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
        if scene_id == 'scene-waterdeep-gundren-briefing':
            travel_status = _travel_status(view)
            if travel_status in {'route_planned', 'traveling'} and not _briefing_acceptance_pending(view):
                return PartyActionDecision(
                    decision_type='command',
                    text='/travel advance 5',
                    option_id=None,
                    option_ids=(),
                    topic_focus='advance planned travel',
                    reason=f'Last-resort fallback after invalid LLM output: {reason}',
                )
            if _briefing_ready_for_travel(view):
                return PartyActionDecision(
                    decision_type='command',
                    text='/travel route phandalin',
                    option_id=None,
                    option_ids=(),
                    topic_focus='route travel to phandalin',
                    reason=f'Last-resort fallback after invalid LLM output: {reason}',
                )
            return PartyActionDecision(
                decision_type='command',
                text=_SAFE_BRIEFING_ACCEPTANCE_TEXT,
                option_id=None,
                option_ids=(),
                topic_focus='accept job and depart',
                reason=f'Last-resort fallback after invalid LLM output: {reason}',
            )
        if scene_id == 'scene-00-high-road-journey':
            travel_status = _travel_status(view)
            if travel_status in {None, 'idle'}:
                text = '/travel route phandalin'
                topic_focus = 'route travel to phandalin'
            elif travel_status in {'route_planned', 'traveling'}:
                text = '/travel advance 5'
                topic_focus = 'advance planned travel'
            else:
                text = '/travel resume'
                topic_focus = 'resume travel'
            return PartyActionDecision(
                decision_type='command',
                text=text,
                option_id=None,
                option_ids=(),
                topic_focus=topic_focus,
                reason=f'Last-resort fallback after invalid LLM output: {reason}',
            )
        return PartyActionDecision(
            decision_type='command',
            text='I check the wagon harness, cargo tie-downs, and road supplies one last time so we can leave.',
            option_id=None,
            option_ids=(),
            topic_focus=f'last resort practical progress {scene_id}',
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
        if runtime_mode == 'storytelling':
            self._validate_story_slash_command(view, decision.text)
            scene_id = _string_or_none(view.get('current_scene_id'))
            if _scene_progress_pressure(scene_id, self._current_scene_story_turn_count(snapshot)) == 'close_scene_now':
                self._validate_stale_scene_closure(view, decision)
            if count_for_story_rotation:
                self._validate_direct_story_speech(controller_id, view, decision)
                self._validate_distinct_story_turn(controller_id, view, decision)

    def _validate_stale_scene_closure(self, view: dict[str, Any], decision: PartyActionDecision) -> None:
        scene_id = _string_or_none(view.get('current_scene_id'))
        if scene_id == 'scene-00-high-road-journey':
            self._validate_stale_high_road_travel_closure(view, decision)
            return
        if scene_id != 'scene-waterdeep-gundren-briefing':
            return
        text = decision.text.strip()
        if _briefing_ready_for_travel(view):
            if _is_travel_route_phandalin(text):
                return
            raise PartyConnectorError(
                'Stale Gundren briefing has already accepted the job and is ready for travel. '
                'Use /travel route phandalin to move to the High Road before any more acceptance, preparation, or conversation.'
            )
        if text.startswith('/'):
            return
        normalized = _normalize_text(text)
        if normalized != _normalize_text(_SAFE_BRIEFING_ACCEPTANCE_TEXT) or _STALE_BRIEFING_FORBIDDEN_RE.search(text) is not None:
            raise PartyConnectorError(
                'Stale Gundren briefing closure must use plain accept-and-depart wording only. '
                f'Use exactly "{_SAFE_BRIEFING_ACCEPTANCE_TEXT}" '
                'Do not add deals, ledgers, bargaining, spells, secrets, inspections, or new questions.'
            )

    def _validate_stale_high_road_travel_closure(self, view: dict[str, Any], decision: PartyActionDecision) -> None:
        text = decision.text.strip()
        tokens = text.split()
        travel_status = _travel_status(view)
        if not tokens or tokens[0].lower() != '/travel':
            raise PartyConnectorError(
                'Stale High Road travel closure must use the authoritative travel command path. '
                'Use /travel route phandalin when Travel status is idle, then /travel advance 5 after a route is planned.'
            )
        subcommand = 'status' if len(tokens) == 1 else tokens[1].lower()
        if travel_status in {None, 'idle'}:
            if subcommand == 'route' and any(token.lower() == 'phandalin' for token in tokens[2:]):
                return
            raise PartyConnectorError(
                'Stale High Road travel closure must start travel routing. '
                'Use /travel route phandalin before any more preparation, inspection, or conversation.'
            )
        if travel_status in {'route_planned', 'traveling'}:
            if subcommand == 'advance':
                return
            raise PartyConnectorError(
                'Stale High Road travel closure must advance the planned route. '
                'Use /travel advance 5 before any more preparation, inspection, or conversation.'
            )
        if subcommand not in {'route', 'advance', 'resume'}:
            raise PartyConnectorError(
                'Stale High Road travel closure must keep travel moving with /travel route, /travel advance, or /travel resume.'
            )

    def _validate_story_slash_command(self, view: dict[str, Any], text: str) -> None:
        stripped = text.strip()
        if not stripped.startswith('/'):
            return
        tokens = stripped.split()
        if not tokens:
            return
        verb = tokens[0].lower()
        if verb == '/travel':
            if (
                _string_or_none(view.get('current_scene_id')) == 'scene-waterdeep-gundren-briefing'
                and _briefing_acceptance_pending(view)
            ):
                raise PartyConnectorError(
                    'Accept the Phandalin job before using /travel from the Waterdeep briefing. '
                    f'Use exactly "{_SAFE_BRIEFING_ACCEPTANCE_TEXT}" before routing or advancing travel.'
                )
            subcommand = 'status' if len(tokens) == 1 else tokens[1].lower()
            if _travel_status(view) == 'interrupted' and subcommand in {'route', 'advance'}:
                raise PartyConnectorError(
                    'Travel is interrupted by a pending hook. Resolve the current scene hook in plain text or use /travel resume; '
                    'do not use /travel route or /travel advance while interrupted.'
                )
            self._validate_story_travel_command(tokens)
            return
        if verb == '/cast':
            self._validate_story_cast_command(view, tokens)
            return
        if verb in {'/do', '/improvise', '/say', '/story'}:
            if len(tokens) < 2:
                raise PartyConnectorError(f'{verb} requires text after the command.')
            return
        if verb == '/check':
            raise PartyConnectorError(
                'Story-mode /check may only answer a pending story-check prompt. '
                'Without a prompt, describe the attempted examination in plain text or with /do.'
            )
        if verb in {'/status', '/view'}:
            return
        raise PartyConnectorError(
            f'Unsupported story-mode slash command `{verb}`. '
            'Use plain text, /say, /story, /do, /improvise, /check, /travel, '
            'or /cast <owned_actor_id> <spell option id> ... in storytelling mode.'
        )

    def _validate_story_travel_command(self, tokens: list[str]) -> None:
        if len(tokens) == 1 or tokens[1].lower() == 'status':
            return
        subcommand = tokens[1].lower()
        if subcommand not in _TRAVEL_SUBCOMMANDS:
            raise PartyConnectorError(_TRAVEL_COMMAND_USAGE)
        if subcommand == 'pace':
            if len(tokens) != 3 or tokens[2].lower() not in _TRAVEL_PACES:
                raise PartyConnectorError('Usage: /travel pace <cautious|normal|fast>.')
            return
        if subcommand == 'route':
            if len(tokens) < 3:
                raise PartyConnectorError('Usage: /travel route <location-id|q r>.')
            return
        if subcommand == 'advance' and len(tokens) > 2:
            try:
                int(tokens[2])
            except ValueError as exc:
                raise PartyConnectorError('Travel advance steps must be an integer: /travel advance [steps].') from exc

    def _validate_story_cast_command(self, view: dict[str, Any], tokens: list[str]) -> None:
        owned_actor_ids = tuple(actor_id for actor_id in view.get('owned_actor_ids', ()) if isinstance(actor_id, str))
        expected_actor = owned_actor_ids[0] if owned_actor_ids else '<owned_actor_id>'
        if len(tokens) < 3:
            raise PartyConnectorError(
                f'Story-mode /cast must use `/cast {expected_actor} <spell option id> [target actor id|x y [z]] [--ritual] [--key value ...]`.'
            )
        if tokens[1] not in owned_actor_ids:
            raise PartyConnectorError(
                'Story-mode /cast must use the owned actor id before the spell id. '
                f'Use `/cast <owned_actor_id> <spell option id> ...`; owned actor ids: {", ".join(owned_actor_ids) or "none"}.'
            )
        spell_ids = _story_spell_option_ids(view)
        if spell_ids and tokens[2] not in spell_ids:
            raise PartyConnectorError(
                f'Unknown story-mode spell option id `{tokens[2]}`. '
                f'Legal visible spell option ids: {", ".join(spell_ids)}.'
            )
        positional: list[str] = []
        index = 3
        while index < len(tokens):
            token = tokens[index]
            if token == '--ritual':
                index += 1
                continue
            if token.startswith('--'):
                key = token[2:]
                if not key:
                    raise PartyConnectorError('Story-mode /cast parameter keys cannot be empty.')
                index += 1
                if index >= len(tokens) or tokens[index].startswith('--'):
                    raise PartyConnectorError(f'Story-mode /cast parameter --{key} requires a value.')
                while index < len(tokens) and not tokens[index].startswith('--'):
                    index += 1
                continue
            positional.append(token)
            index += 1
        if len(positional) > 3:
            raise PartyConnectorError(
                'Story-mode /cast supports at most one target actor id or point coordinates x y [z]. '
                'Use --ritual for ritual casting, not free text such as "as ritual".'
            )
        if len(positional) in {2, 3} and not all(_is_int_token(token) for token in positional):
            raise PartyConnectorError(
                'Story-mode /cast point targets must use integer coordinates x y [z]. '
                'Use --ritual for ritual casting, not free text such as "as ritual".'
            )

    def _validate_direct_story_speech(self, controller_id: str, view: dict[str, Any], decision: PartyActionDecision) -> None:
        text = decision.text.strip()
        if not text or text.startswith('/'):
            return
        if text.casefold() in _COPIED_ACTION_TEMPLATE_TEXTS or _ACTION_DECISION_TEMPLATE_TEXT.casefold() in text.casefold():
            raise PartyConnectorError(
                'Story speech must not copy the JSON template example text. '
                'Write one unique in-character action or slash command that fits the current scene.'
            )
        embedded_command = _EMBEDDED_SLASH_COMMAND_RE.search(text)
        if embedded_command is not None:
            raise PartyConnectorError(
                'Story speech must not embed slash commands inside natural-language declarations. '
                f'Rewrite the action without "{embedded_command.group(0)}"; use a standalone slash command only when required.'
            )
        self_narration = _third_person_self_narration_match(text, DEFAULT_PERSONAS.get(controller_id))
        if self_narration is not None:
            raise PartyConnectorError(
                'Story speech must not use third-person self narration. '
                f'Rewrite the action without "{self_narration}" and keep the action in the character\'s own words.'
            )
        offstage_address = _offstage_npc_direct_address_match(view, text)
        if offstage_address is not None:
            raise PartyConnectorError(
                'Story speech must not directly address an offstage NPC. '
                f'Rewrite the action without speaking to "{offstage_address}" unless that NPC is visibly present.'
            )
        if _NARRATED_SPEECH_RE.search(_unquoted_story_text(text)) is None:
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
        action_command_verbs = {
            '/attack',
            '/cast',
            '/dash',
            '/disengage',
            '/dodge',
            '/grapple',
            '/help',
            '/hide',
            '/ready',
            '/search',
            '/shove',
            '/study',
            '/use',
            '/utilize',
        }
        if parts[0] in action_command_verbs and not _active_actor_action_available(view):
            raise PartyConnectorError(f'The active actor has already used its action; use `/endturn {active_actor_id}`.')
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
            if _is_melee_attack_id(parts[2]):
                distance = _combat_distance_feet(view, active_actor_id, parts[3])
                if distance is not None and distance > 5:
                    raise PartyConnectorError(
                        f'Melee attack target is out of range at {distance:g} feet. '
                        f'Use a ranged/thrown attack, targeted spell, or /dodge {active_actor_id}.'
                    )
        elif parts[0] == '/cast':
            spell_ids = _available_choice_ids(view, 'magic')
            if len(parts) < 3:
                raise PartyConnectorError(f'Cast command must use `/cast {active_actor_id} <spell option_id> [target actor id]`.')
            if parts[1] != active_actor_id:
                raise PartyConnectorError(f'Cast command actor must be the active actor `{active_actor_id}`.')
            spell_id = parts[2]
            if spell_id not in spell_ids:
                raise PartyConnectorError(f'Unknown spell option id `{spell_id}`. Legal spell option ids: {", ".join(spell_ids) or "none"}.')
            if spell_id in _COMBAT_POINT_TARGET_SPELL_IDS:
                if len(parts) < 5 or not _is_int_token(parts[3]) or not _is_int_token(parts[4]):
                    raise PartyConnectorError(
                        f'Spell `{spell_id}` requires point target coordinates. '
                        f'Use `/cast {active_actor_id} {spell_id} <x> <y>` or choose a targeted combat spell/attack.'
                    )
                if len(parts) >= 6 and not parts[5].startswith('--') and not _is_int_token(parts[5]):
                    raise PartyConnectorError(
                        f'Spell `{spell_id}` point target z coordinate must be an integer when provided. '
                        f'Use `/cast {active_actor_id} {spell_id} <x> <y> [z]`.'
                    )
                return
            if spell_id not in _COMBAT_TARGETED_SPELL_IDS:
                safe_spell_ids = _combat_prompt_spell_ids(view)
                fallback = _combat_fallback_command(view)
                raise PartyConnectorError(
                    f'Unsupported combat spell `{spell_id}` for the autonomous connector. '
                    'Use a targeted enemy spell, legal ranged attack, dodge, or endturn instead. '
                    f'Connector-supported spell option ids: {", ".join(safe_spell_ids) or "none"}. '
                    f'Safe fallback command: {fallback or "none"}.'
                )
            if len(parts) > 4:
                target_ids = _visible_enemy_target_ids(view)
                raise PartyConnectorError(
                    f'Cast command supports at most one target actor id here. '
                    f'Use `/cast {active_actor_id} <spell option id> <target actor id>`. '
                    f'Visible enemy target actor ids: {", ".join(target_ids) or "none"}.'
                )
            if len(parts) != 4:
                target_ids = _visible_enemy_target_ids(view)
                raise PartyConnectorError(
                    f'Combat spell `{spell_id}` must use one visible enemy target. '
                    f'Use `/cast {active_actor_id} {spell_id} <target actor id>`. '
                    f'Visible enemy target actor ids: {", ".join(target_ids) or "none"}.'
                )
            if parts[3] not in _visible_enemy_target_ids(view):
                target_ids = _visible_enemy_target_ids(view)
                raise PartyConnectorError(f'Unknown spell target `{parts[3]}`. Visible enemy target actor ids: {", ".join(target_ids) or "none"}.')
            range_feet = _COMBAT_SPELL_TARGET_RANGES_FEET.get(spell_id)
            distance = _combat_distance_feet(view, active_actor_id, parts[3])
            if range_feet is not None and distance is not None and distance > range_feet:
                raise PartyConnectorError(
                    f'Spell target is out of range at {distance:g} feet for `{spell_id}` range {range_feet:g} feet. '
                    f'Use a longer-range spell, ranged/thrown attack, or /dodge {active_actor_id}.'
                )
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


def build_default_dm_combat_agent(
    *,
    config: LLMConfig,
    llm_transport=None,
) -> DMCombatAgent:
    return DMCombatAgent(
        client=LLMClient(config, transport=llm_transport),
        label=f'dm:{config.responses_model}',
    )


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
        dm_combat_agent=build_default_dm_combat_agent(config=config, llm_transport=llm_transport),
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


def _recent_chat_entries(view: dict[str, Any], *, limit: int = 18, text_limit: int = 600) -> list[dict[str, Any]]:
    entries = []
    for entry in list(view.get('chat_entries', []))[-limit:]:
        if not isinstance(entry, dict):
            continue
        text = entry.get('text')
        entries.append(
            {
                'speaker': entry.get('speaker'),
                'text': _truncate_text(text, text_limit) if isinstance(text, str) else text,
                'category': entry.get('category'),
                'visibility': entry.get('visibility'),
            }
        )
    return entries


def _compact_summary_lines(view: dict[str, Any], *, limit: int) -> list[str]:
    lines = [line for line in view.get('summary_lines', []) if isinstance(line, str)]
    important_prefixes = (
        'Runtime mode:',
        'Campaign:',
        'Current scene:',
        'Location:',
        'Party goals:',
        'Open loops:',
        'Travel status:',
        'Travel route:',
        'Travel interruption:',
        'Exploration mode:',
        'Story check pending:',
        'Active combatant:',
        'Round ',
        'Recent events:',
    )
    compact: list[str] = []
    for line in lines:
        if line.startswith(important_prefixes) and line not in compact:
            compact.append(_truncate_text(line, 320))
    for line in lines[-limit:]:
        truncated = _truncate_text(line, 320)
        if truncated not in compact:
            compact.append(truncated)
    return compact[-limit:]


def _compact_speaker_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    advantage_factors = candidate.get('advantage_factors')
    if isinstance(advantage_factors, (list, tuple)):
        compact_factors = list(advantage_factors)[:4]
    else:
        compact_factors = []
    return {
        'controller_id': candidate.get('controller_id'),
        'persona_codename': candidate.get('persona_codename'),
        'persona_story_focus': candidate.get('persona_story_focus'),
        'advantage_score': candidate.get('advantage_score'),
        'advantage_factors': compact_factors,
        'recently_spoke_distance': candidate.get('recently_spoke_distance'),
        'status': _compact_candidate_status(candidate.get('status')),
        'skill_bonuses': _top_numeric_items(candidate.get('skill_bonuses'), limit=5),
        'ability_modifiers': _top_numeric_items(candidate.get('ability_modifiers'), limit=6),
    }


def _compact_candidate_status(status: Any) -> dict[str, Any]:
    if not isinstance(status, dict):
        return {}
    resources = status.get('resources')
    compact_resources = []
    if isinstance(resources, list):
        for resource in resources[:4]:
            if not isinstance(resource, dict):
                continue
            compact_resources.append(
                {
                    'label': resource.get('label'),
                    'remaining_uses': resource.get('remaining_uses'),
                }
            )
    return {
        'hit_point_ratio': status.get('hit_point_ratio'),
        'conditions': list(status.get('conditions', []))[:3] if isinstance(status.get('conditions'), list) else [],
        'resources': compact_resources,
        'cantrips': list(status.get('cantrips', []))[:5] if isinstance(status.get('cantrips'), list) else [],
        'spells': list(status.get('spells', []))[:6] if isinstance(status.get('spells'), list) else [],
    }


def _top_numeric_items(value: Any, *, limit: int) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    items = [(str(key), item) for key, item in value.items() if isinstance(item, int)]
    items.sort(key=lambda item: (-abs(item[1]), item[0]))
    return dict(items[:limit])


def _truncate_text(value: Any, limit: int) -> str:
    text = '' if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + '...'


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
        'active_actor_action_available': _active_actor_action_available(view),
        'round_number': view.get('round_number'),
        'initiative_order': list(view.get('initiative_order', [])),
        'visible_tokens': tokens,
        'visible_enemy_target_ids': _visible_enemy_target_ids(view),
        'legal_attack_option_ids': _available_choice_ids(view, 'attacks'),
        'legal_spell_option_ids': _combat_prompt_spell_ids(view),
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


def _prompt_option_id_matching_text(prompt: dict[str, Any], text: str) -> str | None:
    options = [option for option in prompt.get('options', []) if isinstance(option, dict)]
    if len(options) == 1:
        option_id = options[0].get('option_id')
        return option_id if isinstance(option_id, str) else None
    normalized_text = _normalize_text(text)
    for option in options:
        option_id = option.get('option_id')
        if not isinstance(option_id, str):
            continue
        candidates = [
            option_id,
            str(option.get('label') or ''),
            str(option.get('detail') or ''),
        ]
        if any(candidate and _normalize_text(candidate) in normalized_text for candidate in candidates):
            return option_id
        option_tail = option_id.split(':')[-1]
        if option_tail and _normalize_text(option_tail) in normalized_text:
            return option_id
    return None


def _looks_like_check_response(text: str) -> bool:
    normalized = _normalize_text(text)
    return normalized in {'check', 'roll check', 'make check'} or normalized.startswith('i roll')


def _normalize_stale_briefing_decision(view: dict[str, Any], decision: PartyActionDecision) -> PartyActionDecision:
    text = decision.text.strip()
    if _briefing_ready_for_travel(view):
        if text.startswith('/') and _is_travel_route_phandalin(text):
            return decision
        if not text.startswith('/'):
            return PartyActionDecision(
                decision_type='command',
                text='/travel route phandalin',
                option_id=None,
                option_ids=(),
                topic_focus=decision.topic_focus or 'route travel to phandalin',
                reason=f'{decision.reason} Normalized stale accepted briefing to route travel.',
            )
        return decision
    if text.startswith('/'):
        return decision
    normalized = _normalize_text(text)
    if 'accept' in normalized or 'accepted' in normalized or 'guard' in normalized and 'wagon' in normalized:
        return PartyActionDecision(
            decision_type='command',
            text=_SAFE_BRIEFING_ACCEPTANCE_TEXT,
            option_id=None,
            option_ids=(),
            topic_focus=decision.topic_focus or 'accept job and depart',
            reason=f'{decision.reason} Normalized stale briefing closure to the safe acceptance wording.',
        )
    return decision


def _normalize_stale_high_road_decision(view: dict[str, Any], decision: PartyActionDecision) -> PartyActionDecision:
    travel_status = _travel_status(view)
    if travel_status in {None, 'idle'}:
        return PartyActionDecision(
            decision_type='command',
            text='/travel route phandalin',
            option_id=None,
            option_ids=(),
            topic_focus=decision.topic_focus or 'route travel to phandalin',
            reason=f'{decision.reason} Normalized stale High Road turn to route travel.',
        )
    if travel_status in {'route_planned', 'traveling'}:
        return PartyActionDecision(
            decision_type='command',
            text='/travel advance 5',
            option_id=None,
            option_ids=(),
            topic_focus=decision.topic_focus or 'advance planned travel',
            reason=f'{decision.reason} Normalized stale High Road turn to advance travel.',
        )
    return decision


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


def _story_spell_option_ids(view: dict[str, Any]) -> tuple[str, ...]:
    ids: list[str] = []
    for card in view.get('character_cards', []):
        if not isinstance(card, dict):
            continue
        for spell_list_key in ('cantrips', 'spells'):
            for spell in card.get(spell_list_key, []) or []:
                if not isinstance(spell, dict):
                    continue
                spell_id = (
                    spell.get('option_id')
                    or spell.get('spell_id')
                    or spell.get('id')
                    or _slugify_option_id(_string_or_none(spell.get('name')) or _string_or_none(spell.get('label')) or '')
                )
                if isinstance(spell_id, str) and spell_id and spell_id not in ids:
                    ids.append(spell_id)
    return tuple(ids)


def _combat_prompt_spell_ids(view: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        spell_id
        for spell_id in _available_choice_ids(view, 'magic')
        if spell_id in _COMBAT_TARGETED_SPELL_IDS
    )


def _visible_enemy_target_ids(view: dict[str, Any]) -> tuple[str, ...]:
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return ()
    active_side = _active_actor_side(view)
    target_side = 'player' if active_side == 'monster' else 'monster'
    targets: list[str] = []
    for token in map_view.get('tokens', []):
        if not isinstance(token, dict):
            continue
        actor_id = token.get('actor_id')
        if not isinstance(actor_id, str) or not actor_id:
            continue
        if token.get('side') != target_side:
            continue
        if token.get('status') not in {None, 'active'}:
            continue
        targets.append(actor_id)
    return tuple(targets)


def _active_actor_side(view: dict[str, Any]) -> str | None:
    active_actor_id = _string_or_none(view.get('active_actor_id'))
    if active_actor_id is None:
        return None
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return None
    for token in map_view.get('tokens', []):
        if not isinstance(token, dict) or token.get('actor_id') != active_actor_id:
            continue
        side = token.get('side')
        return side if isinstance(side, str) else None
    return None


def _is_melee_attack_id(attack_id: str) -> bool:
    return attack_id == 'unarmed-strike' or '-melee-' in attack_id or attack_id.endswith('-melee')


def _combat_distance_feet(view: dict[str, Any], actor_id: str, target_id: str) -> float | None:
    actor_position = _combat_token_position(view, actor_id)
    target_position = _combat_token_position(view, target_id)
    if actor_position is None or target_position is None:
        return None
    dx = abs(actor_position[0] - target_position[0])
    dy = abs(actor_position[1] - target_position[1])
    dz = abs(actor_position[2] - target_position[2])
    horizontal_feet = max(dx, dy) * 5
    return max(horizontal_feet, dz)


def _combat_token_position(view: dict[str, Any], actor_id: str) -> tuple[float, float, float] | None:
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return None
    for token in map_view.get('tokens', []):
        if not isinstance(token, dict) or token.get('actor_id') != actor_id:
            continue
        position = token.get('position')
        if not isinstance(position, dict):
            return None
        try:
            return (float(position.get('x')), float(position.get('y')), float(position.get('z', 0)))
        except (TypeError, ValueError):
            return None
    return None


def _active_actor_action_available(view: dict[str, Any]) -> bool:
    active_actor_id = _string_or_none(view.get('active_actor_id'))
    if active_actor_id is None:
        return False
    actor_prefix = f'{active_actor_id}:'
    for line in view.get('summary_lines', ()):
        if not isinstance(line, str):
            continue
        if not line.startswith(actor_prefix):
            continue
        match = re.search(r'\bAction (yes|no)\b', line)
        if match is not None:
            return match.group(1) == 'yes'
    return True


def _travel_status(view: dict[str, Any]) -> str | None:
    for line in view.get('summary_lines', ()):
        if not isinstance(line, str):
            continue
        if not line.startswith('Travel status:'):
            continue
        status = line.partition(':')[2].strip().lower()
        status = status.replace('-', '_')
        return status or None
    return None


def _briefing_ready_for_travel(view: dict[str, Any]) -> bool:
    if _travel_status(view) != 'idle':
        return False
    if _briefing_acceptance_pending(view):
        return False
    normalized_summary = _normalize_text(
        ' '.join(line for line in view.get('summary_lines', ()) if isinstance(line, str))
    )
    return 'get the wagon safely onto the high road' in normalized_summary


def _briefing_acceptance_pending(view: dict[str, Any]) -> bool:
    normalized_summary = _normalize_text(
        ' '.join(line for line in view.get('summary_lines', ()) if isinstance(line, str))
    )
    return 'decide whether to take the phandalin job' in normalized_summary


def _is_travel_route_phandalin(text: str) -> bool:
    tokens = text.strip().split()
    return (
        len(tokens) >= 3
        and tokens[0].lower() == '/travel'
        and tokens[1].lower() == 'route'
        and any(token.lower() == 'phandalin' for token in tokens[2:])
    )


def _has_available_combat_action(view: dict[str, Any]) -> bool:
    if not _active_actor_action_available(view):
        return False
    for group_id in ('attacks', 'magic', 'actions'):
        if _available_choice_ids(view, group_id):
            return True
    return False


def _combat_fallback_command(view: dict[str, Any]) -> str | None:
    active_actor_id = _string_or_none(view.get('active_actor_id'))
    if not active_actor_id:
        return None
    if not _active_actor_action_available(view):
        return f'/endturn {active_actor_id}'
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


def _slugify_option_id(text: str) -> str:
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')


def _normalize_topic(text: str) -> str:
    tokens = [token for token in re.sub(r'[^a-z0-9]+', ' ', text.lower()).split() if token and token not in _STOPWORDS]
    return ' '.join(tokens[:6])


def _is_int_token(value: str) -> bool:
    return re.fullmatch(r'-?\d+', value) is not None


def _scene_progress_pressure(scene_id: str | None, current_scene_story_turn_count: int) -> str:
    if scene_id == 'scene-waterdeep-gundren-briefing':
        return 'close_scene_now' if current_scene_story_turn_count >= 1 else 'normal'
    if scene_id == 'scene-00-high-road-journey':
        return 'close_scene_now'
    return 'close_scene_now' if current_scene_story_turn_count >= 2 else 'normal'


def _has_direct_dialogue(text: str) -> bool:
    stripped = text.strip()
    if _DIRECT_ADDRESS_RE.search(stripped):
        return True
    if re.search(r'"[^"]{3,}"', stripped):
        return True
    return re.search(r"(?<!\w)'[^']{3,}'(?!\w)", stripped) is not None


def _unquoted_story_text(text: str) -> str:
    unquoted = re.sub(r'"[^"]*"', ' ', text)
    return re.sub(r"(?<!\w)'[^']*'(?!\w)", ' ', unquoted)


def _offstage_npc_direct_address_match(view: dict[str, Any], text: str) -> str | None:
    scene_id = (_string_or_none(view.get('current_scene_id')) or '').casefold()
    visible_npc_ids = set(_visible_npc_ids_from_view(view))
    normalized_text = text.replace(chr(0x2014), '-').replace(chr(0x2013), '-')
    for npc_id, names in _KNOWN_SCENE_NPC_NAMES.items():
        if npc_id in visible_npc_ids or _scene_mentions_npc(scene_id, npc_id):
            continue
        for name in names:
            name_pattern = _word_sequence_pattern(name)
            if re.search(rf'(?:^|[.!?]\s+|["\']\s*){name_pattern}\s*[,;:!?-]', normalized_text, re.IGNORECASE):
                return name
    return None


def _visible_npc_ids_from_view(view: dict[str, Any]) -> tuple[str, ...]:
    raw = view.get('visible_npc_ids')
    if raw is None:
        raw = view.get('visibleNPCIds')
    if isinstance(raw, str):
        return tuple(item.strip() for item in raw.split(',') if item.strip())
    if isinstance(raw, (list, tuple)):
        return tuple(item for item in raw if isinstance(item, str) and item)
    return ()


def _scene_mentions_npc(scene_id: str, npc_id: str) -> bool:
    tokens = tuple(token for token in npc_id.split('-') if token)
    return any(token in scene_id for token in tokens)


def _third_person_self_narration_match(text: str, persona: PlayerPersona | None) -> str | None:
    if persona is None:
        return None
    unquoted = _unquoted_story_text(text)
    name_parts = [part for part in persona.codename.split() if part]
    subjects = [persona.codename, *name_parts]
    subject_pattern = '|'.join(_word_sequence_pattern(subject) for subject in subjects)
    if not subject_pattern:
        return None
    subject_match = re.search(rf'\b(?:{subject_pattern})\b', unquoted, re.IGNORECASE)
    if subject_match is not None:
        sentence_end = re.search(r'[.!?]', unquoted[subject_match.end() :])
        end = subject_match.end() + sentence_end.start() if sentence_end is not None else min(len(unquoted), subject_match.end() + 80)
        return unquoted[subject_match.start() : end].strip()
    gendered_pronoun_match = re.search(
        rf'(?:^|[.!?]\s+)\s*({_SELF_NARRATION_GENDERED_PRONOUNS_RE}\b\s+[a-z][a-z\'-]*(?:\s+[a-z][a-z\'-]*){{0,12}})',
        unquoted,
        re.IGNORECASE,
    )
    if gendered_pronoun_match is not None:
        return gendered_pronoun_match.group(1).strip()
    pronoun_match = re.search(
        rf'(?:^|[.!?]\s+)\s*({_SELF_NARRATION_PRONOUNS_RE}\s+(?:[a-z]+\s+){{0,2}}(?:{_SELF_NARRATION_VERBS_RE})\b)',
        unquoted,
        re.IGNORECASE,
    )
    return pronoun_match.group(1) if pronoun_match else None


def _word_sequence_pattern(value: str) -> str:
    return r'\s+'.join(re.escape(part) for part in value.split())


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
