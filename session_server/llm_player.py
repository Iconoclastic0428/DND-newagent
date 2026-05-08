from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from dm_agent.client import LLMClient, LLMResponseError
from shared_types.errors import EncounterPermissionError
from shared_types.storytelling import RuntimeMode, StoryTranscriptVisibility


@dataclass(frozen=True)
class LLMPlayerDecision:
    controller_id: str
    command: str
    reason: str


class LLMPlayerAgent:
    def __init__(
        self,
        *,
        controller_id: str,
        client: LLMClient,
        label: str | None = None,
    ) -> None:
        self.controller_id = controller_id
        self.client = client
        self.label = label or client.config.responses_model
        self._last_signature: tuple[object, ...] | None = None

    def should_act(self, session) -> bool:
        return self._eligibility_signature(session) is not None

    def decide(self, session) -> LLMPlayerDecision | None:
        signature = self._eligibility_signature(session)
        if signature is None or signature == self._last_signature:
            return None
        self._last_signature = signature
        prompt = self._controller_prompt(session)
        if prompt is not None and getattr(prompt, 'prompt_kind', None) == 'story-check':
            return LLMPlayerDecision(self.controller_id, '/check', 'Responding to the active story check prompt.')
        fallback = self._fallback_command(session)
        try:
            response = self.client.create_response(
                self.client.build_request(
                    instructions=_PLAYER_INSTRUCTIONS,
                    input_messages=(
                        {
                            'role': 'user',
                            'content': self._build_context(session, fallback=fallback),
                        },
                    ),
                    metadata={'request_type': 'llm_player_action', 'controller_id': self.controller_id},
                    temperature=0.4,
                    max_output_tokens=320,
                    response_format={'type': 'json_object'},
                )
            )
            payload = _parse_json_object(response.output_text)
            command = self._sanitize_command(str(payload.get('command', '')).strip(), fallback=fallback)
            reason = str(payload.get('reason', '')).strip() or 'LLM player selected an action.'
            return LLMPlayerDecision(self.controller_id, command, reason)
        except (LLMResponseError, ValueError, TypeError, KeyError):
            return LLMPlayerDecision(self.controller_id, fallback, 'Fell back after an invalid LLM player response.')

    def _eligibility_signature(self, session) -> tuple[object, ...] | None:
        prompt = self._controller_prompt(session)
        if prompt is not None:
            return ('prompt', getattr(prompt, 'prompt_id', None), getattr(prompt, 'prompt_kind', None))
        story_state = getattr(session, 'story_state', None)
        if story_state is None:
            return None
        pending_check = getattr(story_state, 'pending_check', None)
        if pending_check is not None:
            return None
        if story_state.runtime_mode == RuntimeMode.COMBAT:
            active_actor_id = getattr(session.state, 'active_actor_id', None)
            if active_actor_id is None or active_actor_id not in self._owned_actor_ids(session):
                return None
            return (
                'combat',
                active_actor_id,
                getattr(session.state, 'round_number', None),
                len(getattr(session.state, 'event_log', ())),
            )
        if story_state.runtime_mode != RuntimeMode.STORYTELLING:
            return None
        return (
            'story',
            getattr(story_state, 'current_scene_id', None),
            getattr(story_state, 'canonical_location_id', None),
            len(getattr(story_state, 'transcript_entries', ())),
        )

    def _controller_prompt(self, session):
        try:
            return session.prompt_for_controller(self.controller_id)
        except EncounterPermissionError:
            return None

    def _fallback_command(self, session) -> str:
        prompt = self._controller_prompt(session)
        if prompt is not None:
            return '/check'
        story_state = getattr(session, 'story_state', None)
        if story_state is not None and story_state.runtime_mode == RuntimeMode.COMBAT:
            active_actor_id = getattr(session.state, 'active_actor_id', None)
            if active_actor_id in self._owned_actor_ids(session):
                return f'/endturn {active_actor_id}'
        return '/do I stay alert and support the party plan.'

    def _build_context(self, session, *, fallback: str) -> str:
        story_state = session.story_state
        view = session.view_for_controller(self.controller_id)
        prompt = self._controller_prompt(session)
        lines: list[str] = [
            f'Controller: {self.controller_id}',
            f'Model label: {self.label}',
            f'Runtime mode: {story_state.runtime_mode.value}',
            f'Current scene: {getattr(story_state, "current_scene_id", "")}',
            f'Current location: {getattr(story_state, "canonical_location_id", "")}',
            f'Fallback command if uncertain: {fallback}',
            '',
            'Your character(s):',
        ]
        owned_ids = self._owned_actor_ids(session)
        for actor_id in owned_ids:
            actor = session.state.actors.get(actor_id)
            if actor is None:
                continue
            hp = getattr(actor, 'hp', None)
            max_hp = getattr(actor, 'max_hp', None)
            hp_text = f'{hp}/{max_hp} hp' if hp is not None and max_hp is not None else 'hp unknown'
            lines.append(f'- {actor_id}: {getattr(actor, "name", actor_id)} ({hp_text})')
        if not owned_ids:
            lines.append('- No owned actor is visible in the current state.')
        if prompt is not None:
            lines.extend(('', 'Active prompt:', getattr(prompt, 'prompt', str(prompt))))
        lines.extend(('', 'Controller summary:'))
        lines.extend(str(line) for line in getattr(view, 'summary_lines', ())[-40:])
        action_lines = self._action_choice_lines(getattr(view, 'available_choices', {}))
        if action_lines:
            lines.extend(('', 'Available action choices:', *action_lines))
        transcript_lines = self._transcript_lines(story_state)
        if transcript_lines:
            lines.extend(('', 'Recent transcript:', *transcript_lines))
        lines.extend(
            (
                '',
                'Return JSON with this exact shape:',
                '{"command": "/do ...", "reason": "brief tactical or roleplay reason"}',
            )
        )
        return '\n'.join(lines)

    def _owned_actor_ids(self, session) -> tuple[str, ...]:
        runtime = session.encounter_session.control_runtime
        actor_ids: list[str] = []
        for actor_id in session.state.actors:
            try:
                owner = runtime.controller_for_actor(actor_id)
            except EncounterPermissionError:
                continue
            if owner == self.controller_id:
                actor_ids.append(actor_id)
        return tuple(actor_ids)

    def _action_choice_lines(self, choices_by_group: dict[str, tuple]) -> list[str]:
        lines: list[str] = []
        for group_id, choices in choices_by_group.items():
            option_ids = []
            for choice in choices[:12]:
                option_id = getattr(choice, 'option_id', None)
                label = getattr(choice, 'label', None)
                if option_id is None:
                    continue
                option_ids.append(f'{option_id} ({label})' if label else str(option_id))
            if option_ids:
                lines.append(f'- {group_id}: {", ".join(option_ids)}')
        return lines[:12]

    def _transcript_lines(self, story_state) -> list[str]:
        lines: list[str] = []
        for entry in getattr(story_state, 'transcript_entries', ())[-10:]:
            visibility = getattr(entry, 'visibility', StoryTranscriptVisibility.PUBLIC)
            if visibility == StoryTranscriptVisibility.DM_ONLY:
                continue
            speaker = getattr(entry, 'speaker', 'Unknown')
            text = getattr(entry, 'text', '')
            if text:
                lines.append(f'- {speaker}: {text}')
        return lines

    def _sanitize_command(self, command: str, *, fallback: str) -> str:
        command = command.splitlines()[0].strip() if command.strip() else ''
        if not command:
            return fallback
        if not command.startswith('/'):
            return f'/do {command}'
        verb = command.split(maxsplit=1)[0].lower()
        if verb in {'/create', '/levelup', '/progression'}:
            return fallback
        return command


def _parse_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if not stripped:
        raise ValueError('Empty LLM player response.')
    start = stripped.find('{')
    end = stripped.rfind('}')
    if start == -1 or end == -1 or end < start:
        raise ValueError('LLM player response did not contain a JSON object.')
    parsed = json.loads(stripped[start:end + 1])
    if not isinstance(parsed, dict):
        raise ValueError('LLM player response JSON must be an object.')
    return parsed


_PLAYER_INSTRUCTIONS = """You control one Dungeons & Dragons player character.
You are a player, not the DM: never narrate outcomes, invent hidden facts, decide monster behavior, or rewrite rules.
Choose one concise command for this controller only.
In storytelling mode, prefer /say, /do, or /story.
If there is an active check prompt, use /check.
In combat mode, use a legal slash command from the visible options when obvious; if uncertain, use the provided fallback.
Return one bare JSON object only with keys command and reason."""
