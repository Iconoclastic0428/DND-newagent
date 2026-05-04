from __future__ import annotations

import json
from typing import Any, Callable, Iterable, Mapping

from shared_types.adjudication import (
    ActionCostRecommendation,
    ActionCostType,
    AdjudicationAttackMode,
    AdjudicationAttackRequest,
    AdjudicationBranch,
    AdjudicationCheckRequest,
    AdjudicationContext,
    AdjudicationContestRequest,
    AdjudicationIllusionSpec,
    AdjudicationModeSwitchRecommendation,
    AdjudicationOperation,
    AdjudicationOperationType,
    AdjudicationPlan,
    AdjudicationSaveRequest,
    AdjudicationType,
    ClarificationRequest,
    ContestParticipantRequest,
    ContestTieRule,
    ImprovisedTemplateId,
    ModeSwitchRecommendationAction,
)
from shared_types.battlefield import CoverLevel
from shared_types.capabilities import IllusionTemplateId
from shared_types.conditions import parse_condition_type
from shared_types.d20 import D20RollMode
from shared_types.effects import DisplacementVector
from shared_types.models import Ability

from .client import LLMClient, LLMResponse
from .runtime import CampaignDocument, DMRuntimeError, LLMConfig, LLMRequestIssuedEvent, LLMResponseAcceptedEvent
from .json_contract import build_json_object_contract, build_json_retry_contract


_ADJUDICATION_JSON_TEMPLATE = json.dumps(
    {
        'action_summary': 'Attempt to tip the table over for cover.',
        'doable': True,
        'adjudication_type': 'ability_check',
        'reasoning_summary_for_dm': 'The action is possible but uncertain under pressure.',
        'clarification_request': None,
        'check_request': {
            'actor_id': 'player-1',
            'ability': 'STR',
            'skill_name': 'Athletics',
            'dc': 12,
            'advantage_state': 'normal',
            'reason': 'Shove the table into cover quickly.',
            'requires_sight': False,
            'requires_hearing': False,
            'interacting_with_actor_id': None,
        },
        'save_request': None,
        'contest_request': None,
        'attack_request': None,
        'action_cost_recommendation': {'cost_type': 'action', 'movement_cost_ft': 0, 'reason': 'Uses the main action in combat.'},
        'improvised_objects_to_create': ['overturned_table_cover'],
        'terrain_changes_to_create': [],
        'operation_plan': [],
        'on_success': {'public_text': 'The table crashes over and gives you cover.', 'dm_note': '', 'operations': []},
        'on_failure': {'public_text': 'The table catches, buying no protection.', 'dm_note': '', 'operations': []},
        'on_partial': None,
        'mode_switch_recommendation': None,
    },
    separators=(',', ':'),
)


_ABILITY_ALIASES = {
    'STRENGTH': Ability.STR,
    'DEXTERITY': Ability.DEX,
    'CONSTITUTION': Ability.CON,
    'INTELLIGENCE': Ability.INT,
    'WISDOM': Ability.WIS,
    'CHARISMA': Ability.CHA,
}


def _canonical_ability(raw: str) -> Ability:
    normalized = raw.strip().upper()
    if normalized in Ability.__members__:
        return Ability[normalized]
    alias = _ABILITY_ALIASES.get(normalized)
    if alias is not None:
        return alias
    raise DMRuntimeError(f'Invalid ability {normalized!r}.')


def _canonical_roll_mode(raw: str | None) -> D20RollMode:
    if raw is None:
        return D20RollMode.NORMAL
    normalized = raw.strip().lower().replace('_', '-').replace(' ', '-')
    if normalized in {'normal', ''}:
        return D20RollMode.NORMAL
    if normalized in {'advantage', 'adv'}:
        return D20RollMode.ADVANTAGE
    if normalized in {'disadvantage', 'disadv'}:
        return D20RollMode.DISADVANTAGE
    raise DMRuntimeError(f'Invalid roll mode {raw!r}.')


def _canonical_cover(raw: str | None) -> CoverLevel | None:
    if raw is None:
        return None
    normalized = raw.strip().lower().replace('_', '-').replace(' ', '-')
    for cover in CoverLevel:
        if cover.value == normalized:
            return cover
    raise DMRuntimeError(f'Invalid cover level {raw!r}.')


def _serialize_document(document: CampaignDocument) -> dict[str, Any]:
    return {
        'id': document.doc_id,
        'path': document.path,
        'title': document.title,
        'type': document.type,
        'visibility': document.visibility,
        'canonical_location': document.canonical_location,
        'tags': list(document.tags),
        'involved_npcs': list(document.involved_npcs),
        'content': document.content,
    }


class DMAdjudicationPlanner:
    def __init__(self, *, client: LLMClient, config: LLMConfig) -> None:
        self.client = client
        self.config = config

    def plan_action(
        self,
        context: AdjudicationContext,
        documents: Iterable[CampaignDocument],
        *,
        validation_callback: Callable[[AdjudicationPlan], AdjudicationPlan] | None = None,
        stream_handler: Any | None = None,
        retry_handler: Any | None = None,
    ) -> tuple[AdjudicationPlan, tuple[object, ...]]:
        payload = self._build_prompt(context, tuple(documents))
        request = self.client.build_request(
            instructions=payload['instructions'],
            input_messages=payload['input'],
            metadata={'request_type': 'adjudication', 'campaign_id': context.campaign_id, 'actor_id': context.actor_id},
            response_format={'type': 'json_object'},
            max_output_tokens=6000,
        )
        events: list[object] = [
            LLMRequestIssuedEvent(request_type='adjudication', model=self.config.responses_model, selection_count=len(payload['documents'])),
        ]
        plan = self._request_with_retry(
            request,
            lambda response: self._parse_response(response, validation_callback=validation_callback),
            stream_handler=stream_handler,
            retry_handler=retry_handler,
        )
        events.append(LLMResponseAcceptedEvent(request_type='adjudication', decision_type=plan.adjudication_type.value))
        return plan, tuple(events)

    def _request_with_retry(self, request, parser, *, stream_handler: Any | None, retry_handler: Any | None):
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
        retry_instruction = build_json_retry_contract(template=_ADJUDICATION_JSON_TEMPLATE, attempt_number=attempt_number)
        retry_message = {
            'role': 'user',
            'content': [
                {
                    'type': 'input_text',
                    'text': json.dumps(
                        {
                            'retry_reason': error_message,
                            'required_json_template': _ADJUDICATION_JSON_TEMPLATE,
                            'previous_invalid_output': previous_output[:4000],
                            'task': 'Re-emit the adjudication plan as one valid JSON object matching the schema exactly.',
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

    def _build_prompt(self, context: AdjudicationContext, documents: tuple[CampaignDocument, ...]) -> dict[str, Any]:
        instructions = (
            'You are a D&D 2024 DM adjudication planner for improvised or nonstandard actions. '
            + build_json_object_contract(template=_ADJUDICATION_JSON_TEMPLATE)
            + ' You are not allowed to mutate state directly. You must return a typed adjudication plan using only the supported vocabulary. '
            + 'Prefer automatic success or automatic failure when the outcome is certain. Use a roll only when uncertainty is meaningful. '
            + 'Use contests when two creatures directly oppose each other. Use saving throws when an effect is imposed on another creature. '
            + 'Use attack_roll only when the fiction is best represented as an actual attack. '
            + 'If the declaration is underspecified, use clarification_required instead of guessing. '
            + 'In storytelling mode, keep mode_switch_recommendation null unless initiative-sensitive danger truly begins now. '
            + 'In combat mode, respect action economy. Recommend only one of action, bonus_action, reaction, movement, object_interaction, or none. '
            + 'The root object must contain exactly these keys: '
            + 'action_summary, doable, adjudication_type, reasoning_summary_for_dm, clarification_request, check_request, save_request, contest_request, attack_request, action_cost_recommendation, improvised_objects_to_create, terrain_changes_to_create, operation_plan, on_success, on_failure, on_partial, mode_switch_recommendation. '
            + 'adjudication_type must be one of automatic_success, ability_check, saving_throw, contest, attack_roll, impossible, partial_only, clarification_required, mode_switch_recommended. '
            + 'Use only these operation types: ' + ', '.join(context.allowed_operation_types) + '. '
            + 'Use only these improvised templates: ' + ', '.join(context.allowed_template_ids) + '. '
            + 'Use only these illusion templates: ' + ', '.join(context.allowed_illusion_template_ids) + '. '
            + 'All ability fields must use STR, DEX, CON, INT, WIS, CHA. '
            + 'All roll states must use normal, advantage, or disadvantage.'
        )
        context_payload = {
            'campaign_id': context.campaign_id,
            'runtime_mode': context.runtime_mode,
            'controller_id': context.controller_id,
            'actor_id': context.actor_id,
            'declaration': context.declaration,
            'current_scene_id': context.current_scene_id,
            'current_location_id': context.current_location_id,
            'active_actor_id': context.active_actor_id,
            'party_goal_summary': context.party_goal_summary,
            'recent_summary': context.recent_summary,
            'unresolved_hooks': list(context.unresolved_hooks),
            'visible_actor_summaries': list(context.visible_actor_summaries),
            'nearby_feature_summaries': list(context.nearby_feature_summaries),
            'actor_status_summary': context.actor_status_summary,
            'action_economy_summary': context.action_economy_summary,
            'allowed_template_ids': list(context.allowed_template_ids),
            'allowed_operation_types': list(context.allowed_operation_types),
        }
        selected_docs = [_serialize_document(document) for document in documents]
        input_messages = (
            {'role': 'user', 'content': [{'type': 'input_text', 'text': json.dumps({'context': context_payload, 'documents': selected_docs}, sort_keys=True)}]},
        )
        return {'instructions': instructions, 'input': input_messages, 'documents': selected_docs}

    def _parse_response(
        self,
        response: LLMResponse,
        *,
        validation_callback: Callable[[AdjudicationPlan], AdjudicationPlan] | None,
    ) -> AdjudicationPlan:
        raw = response.output_text.strip()
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise DMRuntimeError(
                f'LLM response did not contain valid JSON: {exc.msg} at line {exc.lineno} column {exc.colno} (char {exc.pos}).'
            ) from exc
        if not isinstance(payload, dict):
            raise DMRuntimeError('LLM adjudication response JSON must be an object.')
        plan = self._parse_plan_payload(payload, raw_response_text=raw)
        if validation_callback is not None:
            plan = validation_callback(plan)
        return plan

    def _parse_plan_payload(self, payload: Mapping[str, Any], *, raw_response_text: str) -> AdjudicationPlan:
        action_summary = str(payload.get('action_summary', '')).strip()
        if not action_summary:
            raise DMRuntimeError('Adjudication response missing action_summary.')
        reasoning = str(payload.get('reasoning_summary_for_dm', '')).strip()
        if not reasoning:
            raise DMRuntimeError('Adjudication response missing reasoning_summary_for_dm.')
        adjudication_type = self._parse_adjudication_type(payload.get('adjudication_type'))
        doable = bool(payload.get('doable', adjudication_type not in {AdjudicationType.IMPOSSIBLE, AdjudicationType.CLARIFICATION_REQUIRED}))
        plan = AdjudicationPlan(
            action_summary=action_summary,
            doable=doable,
            adjudication_type=adjudication_type,
            reasoning_summary_for_dm=reasoning,
            clarification_request=self._parse_clarification(payload.get('clarification_request')),
            check_request=self._parse_check_request(payload.get('check_request')),
            save_request=self._parse_save_request(payload.get('save_request')),
            contest_request=self._parse_contest_request(payload.get('contest_request')),
            attack_request=self._parse_attack_request(payload.get('attack_request')),
            action_cost_recommendation=self._parse_action_cost(payload.get('action_cost_recommendation')),
            improvised_objects_to_create=self._parse_template_list(payload.get('improvised_objects_to_create')),
            terrain_changes_to_create=self._parse_template_list(payload.get('terrain_changes_to_create')),
            operation_plan=self._parse_operations(payload.get('operation_plan')),
            on_success=self._parse_branch(payload.get('on_success')),
            on_failure=self._parse_branch(payload.get('on_failure')),
            on_partial=self._parse_branch(payload.get('on_partial')),
            mode_switch_recommendation=self._parse_mode_switch_recommendation(payload.get('mode_switch_recommendation')),
            raw_response_text=raw_response_text,
        )
        self._validate_plan_shape(plan)
        return plan

    def _validate_plan_shape(self, plan: AdjudicationPlan) -> None:
        if plan.adjudication_type == AdjudicationType.CLARIFICATION_REQUIRED and plan.clarification_request is None:
            raise DMRuntimeError('clarification_required adjudication requires clarification_request.')
        if plan.adjudication_type == AdjudicationType.ABILITY_CHECK and plan.check_request is None:
            raise DMRuntimeError('ability_check adjudication requires check_request.')
        if plan.adjudication_type == AdjudicationType.SAVING_THROW and plan.save_request is None:
            raise DMRuntimeError('saving_throw adjudication requires save_request.')
        if plan.adjudication_type == AdjudicationType.CONTEST and plan.contest_request is None:
            raise DMRuntimeError('contest adjudication requires contest_request.')
        if plan.adjudication_type == AdjudicationType.ATTACK_ROLL and plan.attack_request is None:
            raise DMRuntimeError('attack_roll adjudication requires attack_request.')
        if plan.adjudication_type == AdjudicationType.MODE_SWITCH_RECOMMENDED and plan.mode_switch_recommendation is None:
            raise DMRuntimeError('mode_switch_recommended adjudication requires mode_switch_recommendation.')

    def _parse_adjudication_type(self, raw: Any) -> AdjudicationType:
        if raw is None:
            raise DMRuntimeError('Adjudication response missing adjudication_type.')
        normalized = str(raw).strip().lower().replace(' ', '_')
        aliases = {
            'automatic': AdjudicationType.AUTOMATIC_SUCCESS,
            'save': AdjudicationType.SAVING_THROW,
            'clarification': AdjudicationType.CLARIFICATION_REQUIRED,
            'mode_switch': AdjudicationType.MODE_SWITCH_RECOMMENDED,
        }
        if normalized in aliases:
            return aliases[normalized]
        try:
            return AdjudicationType(normalized)
        except ValueError as exc:
            raise DMRuntimeError(f'Invalid adjudication_type {raw!r}.') from exc

    def _parse_clarification(self, raw: Any) -> ClarificationRequest | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('clarification_request must be an object when present.')
        question = str(raw.get('question_to_player', '')).strip()
        why = str(raw.get('why_clarification_is_needed', '')).strip()
        missing = tuple(str(item).strip() for item in raw.get('missing_parameters', []) if str(item).strip())
        if not question or not why or not missing:
            raise DMRuntimeError('clarification_request requires question_to_player, why_clarification_is_needed, and missing_parameters.')
        return ClarificationRequest(question_to_player=question, missing_parameters=missing, why_clarification_is_needed=why)

    def _parse_check_request(self, raw: Any) -> AdjudicationCheckRequest | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('check_request must be an object when present.')
        actor_id = str(raw.get('actor_id', '')).strip()
        if not actor_id:
            raise DMRuntimeError('check_request.actor_id is required.')
        dc = raw.get('dc')
        if not isinstance(dc, int):
            raise DMRuntimeError('check_request.dc must be an integer.')
        return AdjudicationCheckRequest(
            actor_id=actor_id,
            ability=_canonical_ability(str(raw.get('ability', ''))),
            skill_name=(str(raw.get('skill_name')).strip() if raw.get('skill_name') is not None and str(raw.get('skill_name')).strip() else None),
            dc=dc,
            advantage_state=_canonical_roll_mode(raw.get('advantage_state')),
            reason=str(raw.get('reason', '')).strip(),
            requires_sight=bool(raw.get('requires_sight', False)),
            requires_hearing=bool(raw.get('requires_hearing', False)),
            interacting_with_actor_id=(str(raw.get('interacting_with_actor_id')).strip() if raw.get('interacting_with_actor_id') is not None and str(raw.get('interacting_with_actor_id')).strip() else None),
        )

    def _parse_save_request(self, raw: Any) -> AdjudicationSaveRequest | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('save_request must be an object when present.')
        targets = tuple(str(item).strip() for item in raw.get('target_actor_ids', []) if str(item).strip())
        if not targets:
            raise DMRuntimeError('save_request.target_actor_ids must be non-empty.')
        dc = raw.get('dc')
        if not isinstance(dc, int):
            raise DMRuntimeError('save_request.dc must be an integer.')
        return AdjudicationSaveRequest(
            target_actor_ids=targets,
            save_ability=_canonical_ability(str(raw.get('save_ability', ''))),
            dc=dc,
            advantage_state=_canonical_roll_mode(raw.get('advantage_state')),
            reason=str(raw.get('reason', '')).strip(),
        )

    def _parse_contest_request(self, raw: Any) -> AdjudicationContestRequest | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('contest_request must be an object when present.')
        participant_a = self._parse_contest_participant(raw.get('actor_a'), label='actor_a')
        participant_b = self._parse_contest_participant(raw.get('actor_b'), label='actor_b')
        tie_raw = str(raw.get('tie_rule', ContestTieRule.DEFENDER_WINS.value)).strip().lower()
        try:
            tie_rule = ContestTieRule(tie_raw)
        except ValueError as exc:
            raise DMRuntimeError(f'Invalid contest tie_rule {tie_raw!r}.') from exc
        reason = str(raw.get('reason', '')).strip()
        if not reason:
            raise DMRuntimeError('contest_request.reason is required.')
        return AdjudicationContestRequest(actor_a=participant_a, actor_b=participant_b, tie_rule=tie_rule, reason=reason)

    def _parse_contest_participant(self, raw: Any, *, label: str) -> ContestParticipantRequest:
        if not isinstance(raw, dict):
            raise DMRuntimeError(f'contest_request.{label} must be an object.')
        actor_id = str(raw.get('actor_id', '')).strip()
        if not actor_id:
            raise DMRuntimeError(f'contest_request.{label}.actor_id is required.')
        return ContestParticipantRequest(
            actor_id=actor_id,
            ability=_canonical_ability(str(raw.get('ability', ''))),
            skill_name=(str(raw.get('skill_name')).strip() if raw.get('skill_name') is not None and str(raw.get('skill_name')).strip() else None),
            advantage_state=_canonical_roll_mode(raw.get('advantage_state')),
        )

    def _parse_attack_request(self, raw: Any) -> AdjudicationAttackRequest | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('attack_request must be an object when present.')
        attacker_id = str(raw.get('attacker_id', '')).strip()
        target_id = str(raw.get('target_id', '')).strip()
        if not attacker_id or not target_id:
            raise DMRuntimeError('attack_request requires attacker_id and target_id.')
        mode_raw = str(raw.get('attack_mode', '')).strip().lower()
        try:
            attack_mode = AdjudicationAttackMode(mode_raw)
        except ValueError as exc:
            raise DMRuntimeError(f'Invalid attack_request.attack_mode {mode_raw!r}.') from exc
        supporting_reason = str(raw.get('supporting_reason', '')).strip()
        if not supporting_reason:
            raise DMRuntimeError('attack_request.supporting_reason is required.')
        attack_id = raw.get('attack_id')
        if attack_id is not None:
            attack_id = str(attack_id).strip() or None
        return AdjudicationAttackRequest(
            attacker_id=attacker_id,
            target_id=target_id,
            attack_mode=attack_mode,
            attack_id=attack_id,
            supporting_reason=supporting_reason,
        )

    def _parse_action_cost(self, raw: Any) -> ActionCostRecommendation | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('action_cost_recommendation must be an object when present.')
        cost_raw = str(raw.get('cost_type', '')).strip().lower()
        try:
            cost_type = ActionCostType(cost_raw)
        except ValueError as exc:
            raise DMRuntimeError(f'Invalid action_cost_recommendation.cost_type {cost_raw!r}.') from exc
        movement_cost_ft = raw.get('movement_cost_ft', 0)
        if not isinstance(movement_cost_ft, int):
            raise DMRuntimeError('action_cost_recommendation.movement_cost_ft must be an integer.')
        return ActionCostRecommendation(cost_type=cost_type, movement_cost_ft=movement_cost_ft, reason=str(raw.get('reason', '')).strip())

    def _parse_template_list(self, raw: Any) -> tuple[ImprovisedTemplateId, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise DMRuntimeError('Template id collections must be arrays.')
        values: list[ImprovisedTemplateId] = []
        for item in raw:
            token = str(item).strip()
            try:
                values.append(ImprovisedTemplateId(token))
            except ValueError as exc:
                raise DMRuntimeError(f'Unsupported improvised template id {token!r}.') from exc
        return tuple(values)

    def _parse_operations(self, raw: Any) -> tuple[AdjudicationOperation, ...]:
        if raw is None:
            return ()
        if not isinstance(raw, list):
            raise DMRuntimeError('operation_plan and branch operations must be arrays.')
        operations: list[AdjudicationOperation] = []
        for item in raw:
            if not isinstance(item, dict):
                raise DMRuntimeError('Each adjudication operation must be an object.')
            op_type_raw = str(item.get('operation_type', '')).strip().lower()
            try:
                op_type = AdjudicationOperationType(op_type_raw)
            except ValueError as exc:
                raise DMRuntimeError(f'Unsupported operation_type {op_type_raw!r}.') from exc
            condition_raw = item.get('condition_type')
            condition_type = None
            if condition_raw is not None:
                condition_type = parse_condition_type(str(condition_raw))
                if condition_type is None:
                    raise DMRuntimeError(f'Unsupported condition_type {condition_raw!r}.')
            template_raw = item.get('template_id')
            template_id = None
            if template_raw is not None:
                try:
                    template_id = ImprovisedTemplateId(str(template_raw).strip())
                except ValueError as exc:
                    raise DMRuntimeError(f'Unsupported improvised template id {template_raw!r}.') from exc
            illusion_spec = None
            illusion_raw = item.get('illusion_spec')
            if illusion_raw is not None:
                if not isinstance(illusion_raw, dict):
                    raise DMRuntimeError('illusion_spec must be an object when present.')
                template_value = illusion_raw.get('template_id')
                if template_value is None:
                    raise DMRuntimeError('illusion_spec.template_id is required.')
                try:
                    illusion_template_id = IllusionTemplateId(str(template_value).strip())
                except ValueError as exc:
                    raise DMRuntimeError(f'Unsupported illusion template id {template_value!r}.') from exc
                illusion_spec = AdjudicationIllusionSpec(
                    template_id=illusion_template_id,
                    display_name=str(illusion_raw.get('display_name', '')).strip(),
                    display_description=str(illusion_raw.get('display_description', '')).strip(),
                    semantic_tags=tuple(str(tag).strip() for tag in illusion_raw.get('semantic_tags', []) if str(tag).strip()) if isinstance(illusion_raw.get('semantic_tags'), list) else (),
                    target_observer_ids=tuple(str(actor_id).strip() for actor_id in illusion_raw.get('target_observer_ids', []) if str(actor_id).strip()) if isinstance(illusion_raw.get('target_observer_ids'), list) else (),
                    apparent_blocker=bool(illusion_raw.get('apparent_blocker', False)),
                    apparent_cover=(_canonical_cover(illusion_raw.get('apparent_cover')) or CoverLevel.NONE),
                    reveal_policy=(str(illusion_raw.get('reveal_policy')).strip() if illusion_raw.get('reveal_policy') is not None and str(illusion_raw.get('reveal_policy')).strip() else None),
                )
            operations.append(
                AdjudicationOperation(
                    operation_type=op_type,
                    actor_id=(str(item.get('actor_id')).strip() if item.get('actor_id') is not None and str(item.get('actor_id')).strip() else None),
                    target_actor_id=(str(item.get('target_actor_id')).strip() if item.get('target_actor_id') is not None and str(item.get('target_actor_id')).strip() else None),
                    note=str(item.get('note', '')).strip(),
                    condition_type=condition_type,
                    source_label=(str(item.get('source_label')).strip() if item.get('source_label') is not None and str(item.get('source_label')).strip() else None),
                    damage_dice_count=(item.get('damage_dice_count') if isinstance(item.get('damage_dice_count'), int) else None),
                    damage_die_faces=(item.get('damage_die_faces') if isinstance(item.get('damage_die_faces'), int) else None),
                    damage_bonus=(item.get('damage_bonus', 0) if isinstance(item.get('damage_bonus', 0), int) else 0),
                    damage_type=(str(item.get('damage_type')).strip() if item.get('damage_type') is not None and str(item.get('damage_type')).strip() else None),
                    damage_divisor=(item.get('damage_divisor', 1) if isinstance(item.get('damage_divisor', 1), int) else 1),
                    healing_dice_count=(item.get('healing_dice_count') if isinstance(item.get('healing_dice_count'), int) else None),
                    healing_die_faces=(item.get('healing_die_faces') if isinstance(item.get('healing_die_faces'), int) else None),
                    healing_bonus=(item.get('healing_bonus', 0) if isinstance(item.get('healing_bonus', 0), int) else 0),
                    template_id=template_id,
                    object_id=(str(item.get('object_id')).strip() if item.get('object_id') is not None and str(item.get('object_id')).strip() else None),
                    terrain_effect_id=(str(item.get('terrain_effect_id')).strip() if item.get('terrain_effect_id') is not None and str(item.get('terrain_effect_id')).strip() else None),
                    x=(item.get('x') if isinstance(item.get('x'), int) else None),
                    y=(item.get('y') if isinstance(item.get('y'), int) else None),
                    z=(item.get('z') if isinstance(item.get('z'), int) else None),
                    cover_level=_canonical_cover(item.get('cover_level')),
                    forced_movement_distance_ft=(item.get('forced_movement_distance_ft') if isinstance(item.get('forced_movement_distance_ft'), int) else None),
                    forced_movement_mode=(str(item.get('forced_movement_mode')).strip().lower() if item.get('forced_movement_mode') is not None and str(item.get('forced_movement_mode')).strip() else None),
                    displacement=(
                        DisplacementVector(
                            dx=int(item.get('displacement', {}).get('dx', 0)),
                            dy=int(item.get('displacement', {}).get('dy', 0)),
                            dz=int(item.get('displacement', {}).get('dz', 0)),
                        )
                        if isinstance(item.get('displacement'), dict)
                        else None
                    ),
                    duration_rounds=(item.get('duration_rounds') if isinstance(item.get('duration_rounds'), int) else None),
                    extra_tags=tuple(str(tag).strip() for tag in item.get('extra_tags', []) if str(tag).strip()) if isinstance(item.get('extra_tags'), list) else (),
                )
            )
        return tuple(operations)

    def _parse_branch(self, raw: Any) -> AdjudicationBranch | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('Branch payloads must be objects when present.')
        return AdjudicationBranch(
            public_text=str(raw.get('public_text', '')).strip(),
            dm_note=str(raw.get('dm_note', '')).strip(),
            operations=self._parse_operations(raw.get('operations')),
        )

    def _parse_mode_switch_recommendation(self, raw: Any) -> AdjudicationModeSwitchRecommendation | None:
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise DMRuntimeError('mode_switch_recommendation must be an object when present.')
        action_raw = str(raw.get('action', '')).strip().lower()
        try:
            action = ModeSwitchRecommendationAction(action_raw)
        except ValueError as exc:
            raise DMRuntimeError(f'Unsupported mode_switch_recommendation.action {action_raw!r}.') from exc
        reason = str(raw.get('reason', '')).strip()
        if not reason:
            raise DMRuntimeError('mode_switch_recommendation.reason is required.')
        participants = tuple(str(item).strip() for item in raw.get('participant_ids', []) if str(item).strip())
        return AdjudicationModeSwitchRecommendation(
            action=action,
            reason=reason,
            participant_ids=participants,
            scene_id=(str(raw.get('scene_id')).strip() if raw.get('scene_id') is not None and str(raw.get('scene_id')).strip() else None),
            location_id=(str(raw.get('location_id')).strip() if raw.get('location_id') is not None and str(raw.get('location_id')).strip() else None),
            battlefield_map_id=(str(raw.get('battlefield_map_id')).strip() if raw.get('battlefield_map_id') is not None and str(raw.get('battlefield_map_id')).strip() else None),
            ambush=bool(raw.get('ambush', False)),
        )




