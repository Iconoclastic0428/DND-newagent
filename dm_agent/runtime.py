from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.models import Ability
from shared_types.storytelling import (
    CombatTransitionContext,
    EnterCombatPlan,
    ExitCombatPlan,
    ModeSwitchAction,
    ModeSwitchDecision,
    ModeSwitchDecisionType,
    RuntimeMode,
    SpellcastingReactionCategory,
    SpellcastingSocialReactionPlan,
    SpellcastingWitnessReaction,
    StoryCheckRequestState,
    StoryModeCastContext,
    StoryModeCastEscalationDecision,
    StorySceneUpdate,
    StorytellingTurnContext,
    StoryTranscriptEntry,
    StoryTranscriptVisibility,
    StoryTurnDecision,
    WitnessObservationPacket,
)

from .client import LLMClient, LLMResponse
from .config import LLMConfig
from .json_contract import build_json_object_contract, build_json_retry_contract


@dataclass(frozen=True)
class CampaignDocument:
    doc_id: str
    path: str
    title: str
    type: str
    campaign: str
    content: str
    tags: tuple[str, ...] = ()
    visibility: str = 'public'
    canonical_location: str | None = None
    involved_npcs: tuple[str, ...] = ()
    related_files: tuple[str, ...] = ()
    retrieval_keywords: tuple[str, ...] = ()
    token_budget_hint: str = 'small'


@dataclass(frozen=True)
class RetrievalSelection:
    documents: tuple[CampaignDocument, ...]
    selection_reason: str


@dataclass(frozen=True)
class LLMConfigLoadedEvent:
    base_url: str
    responses_model: str


@dataclass(frozen=True)
class LLMRequestIssuedEvent:
    request_type: str
    model: str
    selection_count: int


@dataclass(frozen=True)
class LLMResponseAcceptedEvent:
    request_type: str
    decision_type: str


class DMRuntimeError(RuntimeError):
    pass


_ALLOWED_TRANSCRIPT_VISIBILITY = {
    StoryTranscriptVisibility.PUBLIC.value: StoryTranscriptVisibility.PUBLIC,
    StoryTranscriptVisibility.DM_ONLY.value: StoryTranscriptVisibility.DM_ONLY,
}

_ABILITY_ALIASES = {
    'STRENGTH': Ability.STR,
    'DEXTERITY': Ability.DEX,
    'CONSTITUTION': Ability.CON,
    'INTELLIGENCE': Ability.INT,
    'WISDOM': Ability.WIS,
    'CHARISMA': Ability.CHA,
}

_VISIBILITY_ALIASES = {
    'public': StoryTranscriptVisibility.PUBLIC,
    'dm_only': StoryTranscriptVisibility.DM_ONLY,
    'dm-only': StoryTranscriptVisibility.DM_ONLY,
    'dmonly': StoryTranscriptVisibility.DM_ONLY,
    'private': StoryTranscriptVisibility.DM_ONLY,
    'hidden': StoryTranscriptVisibility.DM_ONLY,
    'secret': StoryTranscriptVisibility.DM_ONLY,
    'gm_only': StoryTranscriptVisibility.DM_ONLY,
    'gm-only': StoryTranscriptVisibility.DM_ONLY,
    'gmonly': StoryTranscriptVisibility.DM_ONLY,
}

_STORY_TURN_JSON_TEMPLATE = json.dumps(
    {
        'public_narration': 'string',
        'transcript_entries': [
            {
                'speaker': 'string',
                'text': 'string',
                'visibility': 'public',
            }
        ],
        'check_request': {
            'actor_id': 'player-1',
            'ability': 'DEX',
            'skill_name': 'Stealth',
            'dc': 12,
            'prompt': 'Roll Dexterity (Stealth).',
            'reason': 'Example reason.',
            'requires_sight': False,
            'requires_hearing': False,
            'interacting_with_actor_id': None,
        },
        'scene_update': {
            'scene_id': 'scene-id',
            'location_id': 'location-id',
            'summary': 'string',
            'open_loops': ['loop'],
            'party_goals': ['goal'],
            'party_beliefs': ['belief'],
        },
        'mode_switch_decision': None,
        'memory_note': 'string',
    },
    separators=(',', ':'),
)

_MODE_SWITCH_JSON_TEMPLATE = json.dumps(
    {
        'decision_type': 'stay_in_storytelling',
        'reason': 'string',
        'enter_combat_plan': None,
        'exit_combat_plan': None,
        'confidence': 0.8,
    },
    separators=(',', ':'),
)

_ENTER_COMBAT_MODE_SWITCH_TEMPLATE = json.dumps(
    {
        'decision_type': 'enter_combat',
        'reason': 'Immediate initiative-sensitive danger has begun.',
        'enter_combat_plan': {
            'reason': 'Immediate initiative-sensitive danger has begun.',
            'participant_ids': ['player-1', 'monster-goblin-1'],
            'scene_id': 'scene-id',
            'location_id': 'location-id',
            'ambush': False,
            'battlefield_map_id': 'battlefield-id',
        },
        'exit_combat_plan': None,
        'confidence': 0.9,
    },
    separators=(',', ':'),
)


_SPELLCAST_REACTION_JSON_TEMPLATE = json.dumps(
    {
        'public_narration': 'string',
        'witness_reactions': [
            {
                'witness_id': 'npc-id',
                'reaction_category': 'curious',
                'summary': 'string',
                'public_text': 'string',
                'private_note': 'string',
            }
        ],
        'scene_note': 'string',
        'dm_note': 'string',
        'escalation': {
            'recommended': False,
            'reason': 'string',
            'mode_switch_decision': None,
        },
    },
    separators=(',', ':'),
)


def _canonical_visibility(raw: str) -> StoryTranscriptVisibility | None:
    return _VISIBILITY_ALIASES.get(raw.strip().lower())


def _canonical_ability(raw: str) -> Ability:
    normalized = raw.strip().upper()
    if normalized in Ability.__members__:
        return Ability[normalized]
    alias = _ABILITY_ALIASES.get(normalized)
    if alias is not None:
        return alias
    raise DMRuntimeError(f'Invalid check_request ability {normalized!r}.')


def _serialize_document(document: CampaignDocument) -> dict[str, Any]:
    return {
        'id': document.doc_id,
        'path': document.path,
        'title': document.title,
        'type': document.type,
        'campaign': document.campaign,
        'tags': list(document.tags),
        'visibility': document.visibility,
        'canonical_location': document.canonical_location,
        'involved_npcs': list(document.involved_npcs),
        'related_files': list(document.related_files),
        'retrieval_keywords': list(document.retrieval_keywords),
        'token_budget_hint': document.token_budget_hint,
        'content': document.content,
    }


def _serialize_spell_perceptibility(profile) -> dict[str, Any]:
    return {
        'has_verbal_component': profile.has_verbal_component,
        'has_somatic_component': profile.has_somatic_component,
        'has_material_component': profile.has_material_component,
        'material_is_costly_or_consumed': profile.material_is_costly_or_consumed,
        'material_description': profile.material_description,
        'casting_visual_manifestation': profile.casting_visual_manifestation,
        'casting_auditory_manifestation': profile.casting_auditory_manifestation,
        'effect_visible': profile.effect_visible,
        'effect_audible': profile.effect_audible,
        'componentless_casting': profile.componentless_casting,
    }


def _serialize_story_cast_context(context: StoryModeCastContext) -> dict[str, Any]:
    return {
        'attempt': {
            'actor_id': context.attempt.actor_id,
            'spell_id': context.attempt.spell_id,
            'controller_id': context.attempt.controller_id,
            'scene_id': context.attempt.scene_id,
            'location_id': context.attempt.location_id,
            'target_id': context.attempt.target_id,
            'point': context.attempt.point,
            'casting_time_seconds': context.attempt.casting_time_seconds,
            'ritual_cast': context.attempt.ritual_cast,
        },
        'spell_name': context.spell_name,
        'spell_level': context.spell_level,
        'action_cost': context.action_cost,
        'perceptibility': _serialize_spell_perceptibility(context.perceptibility),
        'current_scene_summary': context.current_scene_summary,
        'recent_session_summary': context.recent_session_summary,
        'party_goal_summary': context.party_goal_summary,
        'unresolved_hooks': list(context.unresolved_hooks),
        'visible_npc_ids': list(context.visible_npc_ids),
        'nearby_tags': list(context.nearby_tags),
    }


def _serialize_witness_packet(packet: WitnessObservationPacket) -> dict[str, Any]:
    return {
        'caster_actor_id': packet.caster_actor_id,
        'spell_id': packet.spell_id,
        'spell_name': packet.spell_name,
        'spell_level': packet.spell_level,
        'action_cost': packet.action_cost,
        'target_actor_id': packet.target_actor_id,
        'point': packet.point,
        'witnesses': [
            {
                'observer_id': witness.observer_id,
                'observer_kind': witness.observer_kind.value,
                'display_name': witness.display_name,
                'paying_attention': witness.paying_attention,
                'perceived_casting_act': witness.perceived_casting_act,
                'perceived_spell_effect': witness.perceived_spell_effect,
                'confidence': witness.confidence.value,
                'concern_level': witness.concern_level.value,
                'attitude': (witness.attitude.value if witness.attitude is not None else None),
                'current_stance': witness.current_stance,
                'applicable_norm_ids': list(witness.applicable_norm_ids),
                'norm_tags': list(witness.norm_tags),
                'relationship_trust': witness.relationship_trust,
                'relationship_suspicion': witness.relationship_suspicion,
                'relationship_fear': witness.relationship_fear,
                'relationship_respect': witness.relationship_respect,
            }
            for witness in packet.witnesses
        ],
    }


def _clean_tokens(*values: str) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        for chunk in value.replace('_', '-').replace('/', ' ').split():
            token = chunk.strip().lower()
            if token:
                tokens.add(token)
    return tokens


class DMStorytellingRuntime:
    def __init__(self, *, client: LLMClient, config: LLMConfig) -> None:
        self.client = client
        self.config = config

    @classmethod
    def from_env(
        cls,
        *,
        env_path: str | Path = '.env',
        environ: Mapping[str, str] | None = None,
        client_transport: Any | None = None,
    ) -> 'DMStorytellingRuntime':
        from .config import load_llm_config

        config = load_llm_config(env_path=env_path, environ=environ)
        client = LLMClient(config, transport=client_transport)
        return cls(client=client, config=config)

    def config_loaded_event(self) -> LLMConfigLoadedEvent:
        return LLMConfigLoadedEvent(base_url=self.config.base_url, responses_model=self.config.responses_model)

    def select_relevant_documents(self, context: StorytellingTurnContext, documents: Iterable[CampaignDocument], *, limit: int = 8) -> RetrievalSelection:
        scored: list[tuple[int, int, CampaignDocument]] = []
        scene_tokens = _clean_tokens(context.current_scene_id or '', context.current_location_id or '', *context.nearby_tags)
        hook_tokens = _clean_tokens(*context.unresolved_hooks, context.party_goal_summary, context.current_scene_summary, context.recent_session_summary)
        for index, document in enumerate(documents):
            doc_tokens = _clean_tokens(
                document.doc_id,
                document.path,
                document.title,
                document.type,
                document.canonical_location or '',
                *document.tags,
                *document.involved_npcs,
                *document.retrieval_keywords,
            )
            score = 0
            score += 5 if document.type in {'chapter_index', 'scene', 'location', 'npc', 'npc_playbook', 'scene_state', 'dm_summary'} else 0
            score += 6 if context.current_scene_id and context.current_scene_id in document.doc_id else 0
            score += 4 if context.current_location_id and context.current_location_id in (document.canonical_location or '') else 0
            score += 3 if scene_tokens.intersection(doc_tokens) else 0
            score += 2 if hook_tokens.intersection(doc_tokens) else 0
            score += 1 if context.campaign_id in document.campaign else 0
            scored.append((score, index, document))
        scored.sort(key=lambda item: (-item[0], item[1], item[2].path))
        selected = tuple(document for score, _, document in scored[:limit] if score > 0)
        reason = 'selected by scene/location/tag relevance'
        return RetrievalSelection(documents=selected, selection_reason=reason)

    def decide_mode_switch(
        self,
        context: StorytellingTurnContext | CombatTransitionContext,
        documents: Iterable[CampaignDocument],
        *,
        current_mode: RuntimeMode,
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ) -> tuple[ModeSwitchDecision, tuple[object, ...]]:
        story_context = StorytellingTurnContext(
            campaign_id=context.campaign_id,
            mode=current_mode,
            current_scene_id=getattr(context, 'current_scene_id', None),
            current_location_id=getattr(context, 'current_location_id', None),
            party_goal_summary=getattr(context, 'party_goal_summary', '') if hasattr(context, 'party_goal_summary') else '',
            unresolved_hooks=getattr(context, 'unresolved_hooks', ()) if hasattr(context, 'unresolved_hooks') else (),
            current_scene_summary=getattr(context, 'current_scene_summary', '') if hasattr(context, 'current_scene_summary') else '',
            recent_session_summary=getattr(context, 'recent_session_summary', '') if hasattr(context, 'recent_session_summary') else '',
            party_beliefs=getattr(context, 'party_beliefs', ()) if hasattr(context, 'party_beliefs') else (),
            visible_npc_ids=getattr(context, 'visible_npc_ids', ()) if hasattr(context, 'visible_npc_ids') else (),
            mode_hint=getattr(context, 'mode_hint', 'storytelling') if hasattr(context, 'mode_hint') else 'combat',
            nearby_tags=getattr(context, 'nearby_tags', ()) if hasattr(context, 'nearby_tags') else (),
        )
        selection = self.select_relevant_documents(story_context, documents)
        payload = self._build_mode_switch_prompt(context, selection, current_mode=current_mode)
        request = self.client.build_request(
            instructions=payload['instructions'],
            input_messages=payload['input'],
            metadata={'request_type': 'mode_switch', 'campaign_id': context.campaign_id},
            response_format={'type': 'json_object'},
        )
        events: list[object] = [LLMRequestIssuedEvent(request_type='mode_switch', model=self.config.responses_model, selection_count=len(selection.documents))]
        decision = self._request_with_json_retry(
            request,
            lambda response: self._parse_mode_switch_response(response, selection=selection),
            stream_handler=stream_handler,
            retry_handler=retry_handler,
        )
        events.append(LLMResponseAcceptedEvent(request_type='mode_switch', decision_type=decision.decision_type.value))
        return decision, tuple(events)

    def plan_story_turn(
        self,
        context: StorytellingTurnContext,
        documents: Iterable[CampaignDocument],
        *,
        controller_id: str,
        actor_id: str,
        declaration: str,
        available_actor_ids: tuple[str, ...],
        available_combatant_actor_ids: tuple[str, ...],
        actors_with_resolved_scene_checks: tuple[str, ...] = (),
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ) -> tuple[StoryTurnDecision, tuple[object, ...]]:
        selection = self.select_relevant_documents(context, documents)
        payload = self._build_story_turn_prompt(
            context,
            selection,
            controller_id=controller_id,
            actor_id=actor_id,
            declaration=declaration,
            available_actor_ids=available_actor_ids,
            available_combatant_actor_ids=available_combatant_actor_ids,
            actors_with_resolved_scene_checks=actors_with_resolved_scene_checks,
        )
        request = self.client.build_request(
            instructions=payload['instructions'],
            input_messages=payload['input'],
            metadata={'request_type': 'story_turn', 'campaign_id': context.campaign_id, 'actor_id': actor_id},
            response_format={'type': 'json_object'},
            max_output_tokens=6000,
        )
        events: list[object] = [LLMRequestIssuedEvent(request_type='story_turn', model=self.config.responses_model, selection_count=len(selection.documents))]
        decision = self._request_with_json_retry(
            request,
            lambda response: self._parse_story_turn_response(response, selection=selection, fallback_actor_id=actor_id, blocked_check_actor_ids=actors_with_resolved_scene_checks),
            stream_handler=stream_handler,
            retry_handler=retry_handler,
        )
        events.append(LLMResponseAcceptedEvent(request_type='story_turn', decision_type=(decision.mode_switch_decision.decision_type.value if decision.mode_switch_decision is not None else 'story_turn')))
        return decision, tuple(events)

    def plan_check_outcome(
        self,
        context: StorytellingTurnContext,
        documents: Iterable[CampaignDocument],
        *,
        pending_check: StoryCheckRequestState,
        result_total: int,
        success: bool,
        selected_roll: int,
        declaration: str,
        available_combatant_actor_ids: tuple[str, ...],
        actors_with_resolved_scene_checks: tuple[str, ...] = (),
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ) -> tuple[StoryTurnDecision, tuple[object, ...]]:
        selection = self.select_relevant_documents(context, documents)
        payload = self._build_check_outcome_prompt(
            context,
            selection,
            pending_check=pending_check,
            result_total=result_total,
            success=success,
            selected_roll=selected_roll,
            declaration=declaration,
            available_combatant_actor_ids=available_combatant_actor_ids,
            actors_with_resolved_scene_checks=actors_with_resolved_scene_checks,
        )
        request = self.client.build_request(
            instructions=payload['instructions'],
            input_messages=payload['input'],
            metadata={'request_type': 'story_check_outcome', 'campaign_id': context.campaign_id, 'actor_id': pending_check.actor_id},
            response_format={'type': 'json_object'},
            max_output_tokens=6000,
        )
        events: list[object] = [LLMRequestIssuedEvent(request_type='story_check_outcome', model=self.config.responses_model, selection_count=len(selection.documents))]
        decision = self._request_with_json_retry(
            request,
            lambda response: self._parse_story_turn_response(response, selection=selection, fallback_actor_id=pending_check.actor_id, blocked_check_actor_ids=actors_with_resolved_scene_checks),
            stream_handler=stream_handler,
            retry_handler=retry_handler,
        )
        events.append(LLMResponseAcceptedEvent(request_type='story_check_outcome', decision_type=(decision.mode_switch_decision.decision_type.value if decision.mode_switch_decision is not None else 'story_turn')))
        return decision, tuple(events)

    def plan_spellcasting_reaction(
        self,
        context: StoryModeCastContext,
        documents: Iterable[CampaignDocument],
        *,
        witness_packet: WitnessObservationPacket,
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ) -> tuple[SpellcastingSocialReactionPlan, tuple[object, ...]]:
        selection = RetrievalSelection(documents=tuple(documents), selection_reason='story spellcasting reaction context')
        payload = self._build_spellcasting_reaction_prompt(context, selection, witness_packet=witness_packet)
        request = self.client.build_request(
            instructions=payload['instructions'],
            input_messages=payload['input'],
            metadata={
                'request_type': 'story_spellcasting_reaction',
                'actor_id': context.attempt.actor_id,
                'scene_id': context.attempt.scene_id or '',
            },
            response_format={'type': 'json_object'},
            max_output_tokens=5000,
        )
        events: list[object] = [
            LLMRequestIssuedEvent(
                request_type='story_spellcasting_reaction',
                model=self.config.responses_model,
                selection_count=len(selection.documents),
            )
        ]
        plan = self._request_with_json_retry(
            request,
            lambda response: self._parse_spellcasting_reaction_response(
                response,
                selection=selection,
                witness_packet=witness_packet,
            ),
            stream_handler=stream_handler,
            retry_handler=retry_handler,
        )
        events.append(
            LLMResponseAcceptedEvent(
                request_type='story_spellcasting_reaction',
                decision_type='spellcasting-social-reaction',
            )
        )
        return plan, tuple(events)

    def _request_with_json_retry(
        self,
        request: object,
        parser: Any,
        *,
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ):
        current_request = request
        last_error: DMRuntimeError | None = None
        for attempt in range(3):
            response = self.client.create_response(current_request, stream_handler=stream_handler)
            try:
                return parser(response)
            except DMRuntimeError as exc:
                last_error = exc
                if attempt >= 2:
                    raise
                next_attempt = attempt + 2
                if retry_handler is not None:
                    retry_handler(next_attempt, 3, str(exc))
                current_request = self._build_retry_request(current_request, response.output_text, str(exc), attempt_number=next_attempt)
        if last_error is not None:
            raise last_error
        raise DMRuntimeError('LLM response did not contain valid JSON.')

    def _build_retry_request(self, request, previous_output: str, error_message: str, *, attempt_number: int):
        template = self._response_template_for_request(request)
        retry_instruction = build_json_retry_contract(template=template, attempt_number=attempt_number)
        retry_message = {
            'role': 'user',
            'content': [
                {
                    'type': 'input_text',
                    'text': json.dumps(
                        {
                            'retry_reason': error_message,
                            'required_json_template': template,
                            'previous_invalid_output': previous_output[:4000],
                            'task': 'Re-emit the answer as one valid JSON object matching the schema exactly.',
                        },
                        sort_keys=True,
                    ),
                }
            ],
        }
        return self.client.build_request(
            instructions=f'{request.instructions} {retry_instruction}',
            input_messages=tuple(request.input) + (retry_message,),
            metadata=(dict(request.metadata) if request.metadata is not None else None),
            temperature=request.temperature,
            max_output_tokens=request.max_output_tokens,
            response_format=(dict(request.response_format) if request.response_format is not None else None),
        )

    def _response_template_for_request(self, request) -> str:
        request_type = ''
        if request.metadata is not None:
            request_type = str(request.metadata.get('request_type', ''))
        if request_type == 'mode_switch':
            return _MODE_SWITCH_JSON_TEMPLATE
        if request_type == 'story_spellcasting_reaction':
            return _SPELLCAST_REACTION_JSON_TEMPLATE
        return _STORY_TURN_JSON_TEMPLATE

    def _build_mode_switch_prompt(
        self,
        context: StorytellingTurnContext | CombatTransitionContext,
        selection: RetrievalSelection,
        *,
        current_mode: RuntimeMode,
    ) -> dict[str, Any]:
        context_payload = {
            'campaign_id': context.campaign_id,
            'current_mode': current_mode.value,
            'current_scene_id': getattr(context, 'current_scene_id', None),
            'current_location_id': getattr(context, 'current_location_id', None),
            'reason': getattr(context, 'reason', getattr(context, 'mode_hint', '')),
            'party_goal_summary': getattr(context, 'party_goal_summary', ''),
            'unresolved_hooks': list(getattr(context, 'unresolved_hooks', ()) if hasattr(context, 'unresolved_hooks') else ()),
            'current_scene_summary': getattr(context, 'current_scene_summary', '') if hasattr(context, 'current_scene_summary') else '',
            'recent_session_summary': getattr(context, 'recent_session_summary', '') if hasattr(context, 'recent_session_summary') else '',
            'visible_npc_ids': list(getattr(context, 'visible_npc_ids', ()) if hasattr(context, 'visible_npc_ids') else ()),
            'suggested_participants': list(getattr(context, 'suggested_participants', ()) if hasattr(context, 'suggested_participants') else ()),
            'ambush': getattr(context, 'ambush', False) if hasattr(context, 'ambush') else False,
        }
        selected_docs = [_serialize_document(document) for document in selection.documents]
        instructions = (
            'You are a D&D DM mode-switch planner. '
            + build_json_object_contract(template=_MODE_SWITCH_JSON_TEMPLATE)
            + ' The root object must contain exactly these keys: decision_type, reason, enter_combat_plan, exit_combat_plan, confidence. '
            + 'decision_type must be one of stay_in_storytelling, enter_combat, remain_in_combat, exit_combat.'
        )
        input_messages = (
            {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps({'context': context_payload, 'documents': selected_docs}, sort_keys=True)}]},
        )
        return {'instructions': instructions, 'input': input_messages}

    def _build_story_turn_prompt(
        self,
        context: StorytellingTurnContext,
        selection: RetrievalSelection,
        *,
        controller_id: str,
        actor_id: str,
        declaration: str,
        available_actor_ids: tuple[str, ...],
        available_combatant_actor_ids: tuple[str, ...],
        actors_with_resolved_scene_checks: tuple[str, ...],
    ) -> dict[str, Any]:
        context_payload = {
            'campaign_id': context.campaign_id,
            'current_mode': context.mode.value,
            'current_scene_id': context.current_scene_id,
            'current_location_id': context.current_location_id,
            'party_goal_summary': context.party_goal_summary,
            'unresolved_hooks': list(context.unresolved_hooks),
            'current_scene_summary': context.current_scene_summary,
            'recent_session_summary': context.recent_session_summary,
            'party_beliefs': list(context.party_beliefs),
            'visible_npc_ids': list(context.visible_npc_ids),
            'nearby_tags': list(context.nearby_tags),
            'acting_controller_id': controller_id,
            'acting_actor_id': actor_id,
            'available_actor_ids': list(available_actor_ids),
            'available_combatant_actor_ids': list(available_combatant_actor_ids),
            'actors_with_resolved_scene_checks': list(actors_with_resolved_scene_checks),
            'declaration': declaration,
        }
        selected_docs = [_serialize_document(document) for document in selection.documents]
        instructions = (
            'You are a D&D DM storytelling runtime. '
            + build_json_object_contract(template=_STORY_TURN_JSON_TEMPLATE)
            + ' The root object must contain exactly these keys: public_narration, transcript_entries, check_request, scene_update, mode_switch_decision, memory_note. '
            + 'transcript_entries must be an array of objects with exactly speaker, text, visibility. visibility must be public or dm_only. Never use speaker_id. '
            + 'check_request must be null or an object with exactly actor_id, ability, skill_name, dc, prompt, reason, requires_sight, requires_hearing, interacting_with_actor_id. ability must be one of STR, DEX, CON, INT, WIS, CHA. '
            + 'If you issue a check_request during a story turn, actor_id must exactly equal acting_actor_id from the context payload. Do not hand this turn off to another player by assigning a pending check to a different actor. '
            + 'scene_update must be null or an object using only these keys: scene_id, location_id, summary, open_loops, party_goals, party_beliefs. Do not emit status, focus, npc_states, or any other keys. '
            + 'mode_switch_decision must be null unless combat is actually beginning right now. Never emit a partial mode_switch_decision object. '
            + 'If combat begins, mode_switch_decision must use exactly decision_type, reason, enter_combat_plan, exit_combat_plan, confidence. '
            + 'For enter_combat, enter_combat_plan is required and must use exactly reason, participant_ids, scene_id, location_id, ambush, battlefield_map_id. '
            + 'participant_ids must be selected from available_combatant_actor_ids in the context payload. '
            + 'Combat must not begin from a bridge or travel beat unless the response explicitly transitions into the linked combat scene. If the current scene is a travel/setup scene and danger becomes immediate later on the route, set both scene_update.scene_id and enter_combat_plan.scene_id to the combat scene instead of keeping the current travel scene id. '
            + 'For enter_combat, scene_id, location_id, and battlefield_map_id must all be non-empty and scene_id must match a retrieved scene document. '
            + 'If actors_with_resolved_scene_checks is non-empty, do not issue another check_request for any of those actor ids in this same scene; narrate consequences and move the scene forward instead. '
            + f'Use this combat-entry template when switching to combat: {_ENTER_COMBAT_MODE_SWITCH_TEMPLATE}. '
            + 'If a field is unused, set it to null, [] , or an empty string as appropriate instead of inventing extra keys. '
            + 'Use simple strings and arrays.'
        )
        input_messages = (
            {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps({'context': context_payload, 'documents': selected_docs}, sort_keys=True)}]},
        )
        return {'instructions': instructions, 'input': input_messages}

    def _build_check_outcome_prompt(
        self,
        context: StorytellingTurnContext,
        selection: RetrievalSelection,
        *,
        pending_check: StoryCheckRequestState,
        result_total: int,
        success: bool,
        selected_roll: int,
        declaration: str,
        available_combatant_actor_ids: tuple[str, ...],
        actors_with_resolved_scene_checks: tuple[str, ...],
    ) -> dict[str, Any]:
        context_payload = {
            'campaign_id': context.campaign_id,
            'current_mode': context.mode.value,
            'current_scene_id': context.current_scene_id,
            'current_location_id': context.current_location_id,
            'party_goal_summary': context.party_goal_summary,
            'unresolved_hooks': list(context.unresolved_hooks),
            'current_scene_summary': context.current_scene_summary,
            'recent_session_summary': context.recent_session_summary,
            'pending_check': {
                'request_id': pending_check.request_id,
                'actor_id': pending_check.actor_id,
                'prompt': pending_check.prompt,
                'reason': pending_check.reason,
                'ability': pending_check.check_request.ability.value,
                'skill_name': pending_check.check_request.skill_name,
                'dc': pending_check.check_request.dc,
            },
            'available_combatant_actor_ids': list(available_combatant_actor_ids),
            'actors_with_resolved_scene_checks': list(actors_with_resolved_scene_checks),
            'check_result': {
                'total': result_total,
                'success': success,
                'selected_roll': selected_roll,
                'dc': pending_check.check_request.dc,
                'modifier': result_total - selected_roll,
                'ability': pending_check.check_request.ability.value,
                'skill_name': pending_check.check_request.skill_name,
                'interacting_with_actor_id': pending_check.check_request.interacting_with_actor_id,
                'rolled_by': 'rules_engine',
            },
            'original_declaration': declaration,
        }
        selected_docs = [_serialize_document(document) for document in selection.documents]
        instructions = (
            'You are a D&D DM storytelling runtime resolving the outcome of a just-rolled skill or ability check. '
            + build_json_object_contract(template=_STORY_TURN_JSON_TEMPLATE)
            + ' The check result in the context payload was already rolled and finalized by the deterministic rules engine. '
            + 'You must interpret that result and describe consequences. Do not reroll, alter, or override the roll, DC, modifier, or success state. '
            + 'The root object must contain exactly these keys: public_narration, transcript_entries, check_request, scene_update, mode_switch_decision, memory_note. '
            + 'transcript_entries must be an array of objects with exactly speaker, text, visibility. visibility must be public or dm_only. Never use speaker_id. '
            + 'check_request should usually be null here unless an immediate follow-up check is explicitly required; if present it must use exactly actor_id, ability, skill_name, dc, prompt, reason, requires_sight, requires_hearing, interacting_with_actor_id. ability must be one of STR, DEX, CON, INT, WIS, CHA. '
            + 'Do not redirect check resolution to a different player. If a follow-up check is absolutely required here, actor_id must stay equal to pending_check.actor_id from the context payload. '
            + 'scene_update must be null or an object using only scene_id, location_id, summary, open_loops, party_goals, party_beliefs. '
            + 'mode_switch_decision must be null unless this check result immediately starts combat. Never emit a partial mode_switch_decision object. '
            + 'If combat begins, mode_switch_decision must use exactly decision_type, reason, enter_combat_plan, exit_combat_plan, confidence. '
            + 'For enter_combat, enter_combat_plan is required and must use exactly reason, participant_ids, scene_id, location_id, ambush, battlefield_map_id. '
            + 'participant_ids must be selected from available_combatant_actor_ids in the context payload. '
            + 'Combat must not begin from a bridge or travel beat unless the response explicitly transitions into the linked combat scene. If the current scene is a travel/setup scene and danger becomes immediate later on the route, set both scene_update.scene_id and enter_combat_plan.scene_id to the combat scene instead of keeping the current travel scene id. '
            + 'For enter_combat, scene_id, location_id, and battlefield_map_id must all be non-empty and scene_id must match a retrieved scene document. '
            + 'If actors_with_resolved_scene_checks is non-empty, do not issue another check_request for any of those actor ids in this same scene; narrate consequences and move the scene forward instead. '
            + f'Use this combat-entry template when switching to combat: {_ENTER_COMBAT_MODE_SWITCH_TEMPLATE}. '
            + 'If a field is unused, set it to null, [] , or an empty string as appropriate instead of inventing extra keys.'
        )
        input_messages = (
            {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps({'context': context_payload, 'documents': selected_docs}, sort_keys=True)}]},
        )
        return {'instructions': instructions, 'input': input_messages}

    def _build_spellcasting_reaction_prompt(
        self,
        context: StoryModeCastContext,
        selection: RetrievalSelection,
        *,
        witness_packet: WitnessObservationPacket,
    ) -> dict[str, Any]:
        context_payload = _serialize_story_cast_context(context)
        selected_docs = [_serialize_document(document) for document in selection.documents]
        instructions = (
            'You are a D&D DM spellcasting witness-reaction planner. '
            + build_json_object_contract(template=_SPELLCAST_REACTION_JSON_TEMPLATE)
            + ' The root object must contain exactly these keys: public_narration, witness_reactions, scene_note, dm_note, escalation. '
            + 'witness_reactions must be an array of objects with exactly witness_id, reaction_category, summary, public_text, private_note. '
            + 'reaction_category must be one of no_reaction, notices_but_ignores, curious, mildly_wary, socially_disapproving, suspicious, alarmed, confrontational, report_to_authority, hostile, escalates_to_mode_switch_candidate. '
            + 'Only use witness_id values that already appear in witness_packet.witnesses. '
            + 'You may interpret social meaning, tension, and whether observers care, but you may not directly mutate combat state, HP, spell slots, conditions, or actor positions. '
            + 'If escalation matters, escalation must be an object with exactly recommended, reason, mode_switch_decision. '
            + 'mode_switch_decision must be null unless you are recommending an existing typed mode switch. '
            + 'If you recommend entering combat, mode_switch_decision must use exactly decision_type, reason, enter_combat_plan, exit_combat_plan, confidence. '
            + f'Use this combat-entry template when escalation truly starts combat: {_ENTER_COMBAT_MODE_SWITCH_TEMPLATE}.'
        )
        input_messages = (
            {
                'role': 'user',
                'content': [
                    {
                        'type': 'input_text',
                        'text': json.dumps(
                            {
                                'context': context_payload,
                                'witness_packet': _serialize_witness_packet(witness_packet),
                                'documents': selected_docs,
                            },
                            sort_keys=True,
                        ),
                    }
                ],
            },
        )
        return {'instructions': instructions, 'input': input_messages}


    def _parse_mode_switch_response(self, response: LLMResponse, *, selection: RetrievalSelection) -> ModeSwitchDecision:
        raw = response.output_text.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DMRuntimeError(self._format_json_error(exc)) from exc
        if not isinstance(payload, dict):
            raise DMRuntimeError('LLM response JSON must be an object.')
        return self._parse_mode_switch_payload(payload, selection=selection, raw_response_text=raw)

    def _format_json_error(self, exc: json.JSONDecodeError) -> str:
        return (
            'LLM response did not contain valid JSON: '
            f'{exc.msg} at line {exc.lineno} column {exc.colno} (char {exc.pos}).'
        )

    def _parse_mode_switch_payload(self, payload: Mapping[str, Any], *, selection: RetrievalSelection | None, raw_response_text: str) -> ModeSwitchDecision:
        decision_type_raw = str(payload.get('decision_type', '')).strip()
        try:
            decision_type = ModeSwitchDecisionType(decision_type_raw)
        except ValueError as exc:
            raise DMRuntimeError(f'Invalid decision_type {decision_type_raw!r}.') from exc
        reason = str(payload.get('reason', '')).strip()
        if not reason:
            raise DMRuntimeError('LLM response missing a decision reason.')
        enter_plan = None
        enter_payload = payload.get('enter_combat_plan')
        if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and not isinstance(enter_payload, dict):
            raise DMRuntimeError('Enter-combat decisions require an enter_combat_plan object.')
        if isinstance(enter_payload, dict):
            enter = enter_payload
            participants = tuple(str(item).strip() for item in enter.get('participant_ids', []) if str(item).strip())
            scene_id = (str(enter.get('scene_id')).strip() if enter.get('scene_id') is not None else None)
            location_id = (str(enter.get('location_id')).strip() if enter.get('location_id') is not None else None)
            battlefield_map_id = (str(enter.get('battlefield_map_id')).strip() if enter.get('battlefield_map_id') is not None else None)
            if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and not participants:
                raise DMRuntimeError('Enter-combat decisions require non-empty participant_ids.')
            if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and not scene_id:
                raise DMRuntimeError('Enter-combat decisions require a non-empty scene_id.')
            if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and not location_id:
                raise DMRuntimeError('Enter-combat decisions require a non-empty location_id.')
            if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and not battlefield_map_id:
                raise DMRuntimeError('Enter-combat decisions require a non-empty battlefield_map_id.')
            if decision_type == ModeSwitchDecisionType.ENTER_COMBAT and selection is not None:
                retrieved_scene_docs = {doc.doc_id: doc for doc in selection.documents if doc.type == 'scene'}
                if scene_id not in retrieved_scene_docs:
                    raise DMRuntimeError('Enter-combat decisions must transition to a retrieved scene id.')
                scene_doc = retrieved_scene_docs[scene_id]
                if scene_doc.canonical_location is not None and location_id != scene_doc.canonical_location:
                    raise DMRuntimeError('Enter-combat decisions require location_id to match the selected combat scene.')
            enter_plan = EnterCombatPlan(
                reason=str(enter.get('reason', reason)).strip(),
                participant_ids=participants,
                scene_id=scene_id,
                location_id=location_id,
                ambush=bool(enter.get('ambush', False)),
                battlefield_map_id=battlefield_map_id,
            )
        exit_plan = None
        exit_payload = payload.get('exit_combat_plan')
        if decision_type == ModeSwitchDecisionType.EXIT_COMBAT and not isinstance(exit_payload, dict):
            raise DMRuntimeError('Exit-combat decisions require an exit_combat_plan object.')
        if isinstance(exit_payload, dict):
            exit_obj = exit_payload
            exit_plan = ExitCombatPlan(
                reason=str(exit_obj.get('reason', reason)).strip(),
                preserve_scene_state=bool(exit_obj.get('preserve_scene_state', True)),
                resulting_scene_id=(str(exit_obj.get('resulting_scene_id')).strip() if exit_obj.get('resulting_scene_id') is not None else None),
                follow_up_summary=str(exit_obj.get('follow_up_summary', '')).strip(),
            )
        confidence = float(payload.get('confidence', 1.0))
        return ModeSwitchDecision(
            decision_type=decision_type,
            reason=reason,
            enter_combat_plan=enter_plan,
            exit_combat_plan=exit_plan,
            selection=selection,
            confidence=confidence,
            raw_response_text=raw_response_text,
        )

    def _parse_story_turn_response(
        self,
        response: LLMResponse,
        *,
        selection: RetrievalSelection,
        fallback_actor_id: str,
        blocked_check_actor_ids: tuple[str, ...] = (),
    ) -> StoryTurnDecision:
        raw = response.output_text.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DMRuntimeError(self._format_json_error(exc)) from exc
        if not isinstance(payload, dict):
            raise DMRuntimeError('LLM response JSON must be an object.')
        public_narration = str(payload.get('public_narration', '')).strip()
        transcript_entries = self._parse_transcript_entries(payload.get('transcript_entries'), public_narration)
        check_request = self._parse_story_check_request(payload.get('check_request'), fallback_actor_id=fallback_actor_id)
        if check_request is not None and check_request.actor_id != fallback_actor_id:
            raise DMRuntimeError('Story check requests must target the acting actor for this turn.')
        if check_request is not None and check_request.actor_id in set(blocked_check_actor_ids):
            raise DMRuntimeError('A player can receive at most one story check per scene.')
        scene_update = self._parse_scene_update(payload.get('scene_update'))
        mode_switch_decision = None
        if isinstance(payload.get('mode_switch_decision'), dict):
            mode_switch_decision = self._parse_mode_switch_payload(payload['mode_switch_decision'], selection=selection, raw_response_text=raw)
        memory_note = str(payload.get('memory_note', '')).strip()
        return StoryTurnDecision(
            public_narration=public_narration,
            transcript_entries=transcript_entries,
            check_request=check_request,
            scene_update=scene_update,
            mode_switch_decision=mode_switch_decision,
            memory_note=memory_note,
            raw_response_text=raw,
        )

    def _parse_transcript_entries(self, raw_entries: Any, public_narration: str) -> tuple[StoryTranscriptEntry, ...]:
        entries: list[StoryTranscriptEntry] = []
        if isinstance(raw_entries, list):
            for raw_entry in raw_entries:
                if not isinstance(raw_entry, dict):
                    raise DMRuntimeError('transcript_entries must contain only objects.')
                speaker = str(raw_entry.get('speaker', '') or raw_entry.get('speaker_id', '')).strip()
                text = str(raw_entry.get('text', '')).strip()
                visibility_raw = str(raw_entry.get('visibility', 'public')).strip().lower()
                visibility = _canonical_visibility(visibility_raw)
                if not speaker or not text or visibility is None:
                    raise DMRuntimeError('Each transcript entry requires speaker, text, and a valid visibility.')
                entries.append(StoryTranscriptEntry(speaker=speaker, text=text, visibility=visibility))
        if public_narration:
            entries.insert(0, StoryTranscriptEntry(speaker='DM', text=public_narration, visibility=StoryTranscriptVisibility.PUBLIC))
        if not entries:
            raise DMRuntimeError('Story turn response must include public_narration or transcript_entries.')
        return tuple(entries)

    def _parse_story_check_request(self, raw_request: Any, *, fallback_actor_id: str) -> StoryCheckRequestState | None:
        if raw_request is None:
            return None
        if not isinstance(raw_request, dict):
            raise DMRuntimeError('check_request must be an object when present.')
        actor_id = str(raw_request.get('actor_id', '')).strip()
        if not actor_id:
            raise DMRuntimeError('check_request.actor_id is required.')
        request_id = str(raw_request.get('request_id', '')).strip() or f'story-check-{actor_id}'
        prompt = str(raw_request.get('prompt', '')).strip()
        reason = str(raw_request.get('reason', '')).strip()
        ability_raw = str(raw_request.get('ability', '')).strip()
        if not prompt or not reason or not ability_raw:
            raise DMRuntimeError('check_request requires prompt, reason, and ability.')
        try:
            ability = _canonical_ability(ability_raw)
        except DMRuntimeError as exc:
            raise exc
        dc = raw_request.get('dc')
        if not isinstance(dc, int):
            raise DMRuntimeError('check_request.dc must be an integer.')
        skill_name = raw_request.get('skill_name')
        if skill_name is not None:
            skill_name = str(skill_name).strip() or None
        interacting_with_actor_id = raw_request.get('interacting_with_actor_id')
        if interacting_with_actor_id is not None:
            interacting_with_actor_id = str(interacting_with_actor_id).strip() or None
        request = CheckRequest(
            context=ResolutionContext(
                effect_id=request_id,
                source_actor_id=None,
                target_actor_id=actor_id or fallback_actor_id,
                reason=reason,
            ),
            ability=ability,
            dc=dc,
            skill_name=skill_name,
            requires_sight=bool(raw_request.get('requires_sight', False)),
            requires_hearing=bool(raw_request.get('requires_hearing', False)),
            interacting_with_actor_id=interacting_with_actor_id,
        )
        return StoryCheckRequestState(
            request_id=request_id,
            controller_id=None,
            actor_id=actor_id or fallback_actor_id,
            prompt=prompt,
            reason=reason,
            check_request=request,
        )

    def _parse_scene_update(self, raw_update: Any) -> StorySceneUpdate | None:
        if raw_update is None:
            return None
        if not isinstance(raw_update, dict):
            raise DMRuntimeError('scene_update must be an object when present.')
        def _tuple_field(key: str) -> tuple[str, ...] | None:
            value = raw_update.get(key)
            if value is None:
                return None
            if not isinstance(value, list):
                raise DMRuntimeError(f'scene_update.{key} must be a list of strings when present.')
            return tuple(str(item).strip() for item in value if str(item).strip())
        return StorySceneUpdate(
            scene_id=(str(raw_update.get('scene_id')).strip() if raw_update.get('scene_id') is not None else None),
            location_id=(str(raw_update.get('location_id')).strip() if raw_update.get('location_id') is not None else None),
            summary=(str(raw_update.get('summary')).strip() if raw_update.get('summary') is not None else None),
            open_loops=_tuple_field('open_loops'),
            party_goals=_tuple_field('party_goals'),
            party_beliefs=_tuple_field('party_beliefs'),
        )


    def _parse_spellcasting_reaction_response(
        self,
        response: LLMResponse,
        *,
        selection: RetrievalSelection,
        witness_packet: WitnessObservationPacket,
    ) -> SpellcastingSocialReactionPlan:
        raw = response.output_text.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DMRuntimeError(self._format_json_error(exc)) from exc
        if not isinstance(payload, dict):
            raise DMRuntimeError('LLM response JSON must be an object.')
        return self._parse_spellcasting_reaction_payload(
            payload,
            selection=selection,
            witness_packet=witness_packet,
            raw_response_text=raw,
        )

    def _parse_spellcasting_reaction_payload(
        self,
        payload: Mapping[str, Any],
        *,
        selection: RetrievalSelection,
        witness_packet: WitnessObservationPacket,
        raw_response_text: str,
    ) -> SpellcastingSocialReactionPlan:
        public_narration = str(payload.get('public_narration', '')).strip()
        witness_ids = {witness.observer_id for witness in witness_packet.witnesses}
        raw_reactions = payload.get('witness_reactions', [])
        if not isinstance(raw_reactions, list):
            raise DMRuntimeError('witness_reactions must be a list.')
        reactions: list[SpellcastingWitnessReaction] = []
        for item in raw_reactions:
            if not isinstance(item, dict):
                raise DMRuntimeError('witness_reactions must contain only objects.')
            witness_id = str(item.get('witness_id', '')).strip()
            if not witness_id:
                raise DMRuntimeError('Each witness reaction requires a witness_id.')
            if witness_id not in witness_ids:
                raise DMRuntimeError(f'Unsupported witness_id {witness_id!r} in spellcasting reaction response.')
            reaction_raw = str(item.get('reaction_category', '')).strip().lower()
            try:
                reaction_category = SpellcastingReactionCategory(reaction_raw)
            except ValueError as exc:
                raise DMRuntimeError(f'Invalid reaction_category {reaction_raw!r}.') from exc
            summary = str(item.get('summary', '')).strip()
            if not summary:
                raise DMRuntimeError('Each witness reaction requires a non-empty summary.')
            reactions.append(
                SpellcastingWitnessReaction(
                    witness_id=witness_id,
                    reaction_category=reaction_category,
                    summary=summary,
                    public_text=str(item.get('public_text', '')).strip(),
                    private_note=str(item.get('private_note', '')).strip(),
                )
            )
        scene_note = str(payload.get('scene_note', '')).strip()
        dm_note = str(payload.get('dm_note', '')).strip()
        escalation = None
        raw_escalation = payload.get('escalation')
        if raw_escalation is not None:
            if not isinstance(raw_escalation, dict):
                raise DMRuntimeError('escalation must be an object when present.')
            mode_switch_decision = None
            raw_mode_switch = raw_escalation.get('mode_switch_decision')
            if raw_mode_switch is not None:
                if not isinstance(raw_mode_switch, dict):
                    raise DMRuntimeError('escalation.mode_switch_decision must be an object when present.')
                mode_switch_decision = self._parse_mode_switch_payload(
                    raw_mode_switch,
                    selection=selection,
                    raw_response_text=raw_response_text,
                )
            escalation = StoryModeCastEscalationDecision(
                recommended=bool(raw_escalation.get('recommended', False)),
                reason=str(raw_escalation.get('reason', '')).strip(),
                mode_switch_decision=mode_switch_decision,
            )
        return SpellcastingSocialReactionPlan(
            public_narration=public_narration,
            witness_reactions=tuple(reactions),
            scene_note=scene_note,
            dm_note=dm_note,
            escalation=escalation,
            raw_response_text=raw_response_text,
        )


