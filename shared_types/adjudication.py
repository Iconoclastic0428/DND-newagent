from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .battlefield import CoverLevel
from .capabilities import IllusionTemplateId
from .conditions import ConditionType
from .d20 import D20RollMode
from .effects import DisplacementVector
from .models import Ability


class AdjudicationType(str, Enum):
    AUTOMATIC_SUCCESS = 'automatic_success'
    ABILITY_CHECK = 'ability_check'
    SAVING_THROW = 'saving_throw'
    CONTEST = 'contest'
    ATTACK_ROLL = 'attack_roll'
    IMPOSSIBLE = 'impossible'
    PARTIAL_ONLY = 'partial_only'
    CLARIFICATION_REQUIRED = 'clarification_required'
    MODE_SWITCH_RECOMMENDED = 'mode_switch_recommended'


class ActionCostType(str, Enum):
    NONE = 'none'
    ACTION = 'action'
    BONUS_ACTION = 'bonus_action'
    REACTION = 'reaction'
    MOVEMENT = 'movement'
    OBJECT_INTERACTION = 'object_interaction'


class AdjudicationAttackMode(str, Enum):
    MELEE = 'melee'
    RANGED = 'ranged'
    IMPROVISED = 'improvised'


class ModeSwitchRecommendationAction(str, Enum):
    ENTER_COMBAT = 'enter_combat'
    EXIT_COMBAT = 'exit_combat'


class AdjudicationOperationType(str, Enum):
    MOVE_ACTOR = 'move_actor'
    APPLY_CONDITION = 'apply_condition'
    REMOVE_CONDITION = 'remove_condition'
    APPLY_DAMAGE = 'apply_damage'
    APPLY_HEALING = 'apply_healing'
    CREATE_IMPROVISED_OBJECT = 'create_improvised_object'
    DESTROY_OBJECT = 'destroy_object'
    CREATE_TEMPORARY_TERRAIN_EFFECT = 'create_temporary_terrain_effect'
    CREATE_ILLUSION = 'create_illusion'
    MODIFY_COVER_STATE = 'modify_cover_state'
    OPEN_CHECK_REQUEST = 'open_check_request'
    OPEN_SAVE_REQUEST = 'open_save_request'
    OPEN_CONTEST_REQUEST = 'open_contest_request'
    OPEN_ATTACK_REQUEST = 'open_attack_request'
    START_ACTIVE_EFFECT = 'start_active_effect'
    END_ACTIVE_EFFECT = 'end_active_effect'
    TRIGGER_FORCED_MOVEMENT = 'trigger_forced_movement'
    TRIGGER_HAZARD = 'trigger_hazard'
    RECOMMEND_ENTER_COMBAT = 'recommend_enter_combat'
    RECOMMEND_EXIT_COMBAT = 'recommend_exit_combat'
    UPDATE_SCENE_STATE_NOTE = 'update_scene_state_note'


class ImprovisedTemplateId(str, Enum):
    OVERTURNED_TABLE_COVER = 'overturned_table_cover'
    FRAGILE_OBSTACLE_SMALL = 'fragile_obstacle_small'
    FLAMMABLE_OIL_SPILL_SMALL = 'flammable_oil_spill_small'
    UNSTABLE_RUBBLE_PATCH = 'unstable_rubble_patch'
    IMPROVISED_BRIDGE_OR_PLANK = 'improvised_bridge_or_plank'
    LOOSE_DEBRIS_DIFFICULT_TERRAIN = 'loose_debris_difficult_terrain'
    BALL_BEARINGS_PATCH = 'ball_bearings_patch'
    HANGING_OBJECT_DROP_HAZARD = 'hanging_object_drop_hazard'


class ContestTieRule(str, Enum):
    DEFENDER_WINS = 'defender_wins'
    INITIATOR_WINS = 'initiator_wins'
    NO_CHANGE = 'no_change'


@dataclass(frozen=True)
class ActionCostRecommendation:
    cost_type: ActionCostType
    movement_cost_ft: int = 0
    reason: str = ''


@dataclass(frozen=True)
class ClarificationRequest:
    question_to_player: str
    missing_parameters: tuple[str, ...]
    why_clarification_is_needed: str


@dataclass(frozen=True)
class AdjudicationCheckRequest:
    actor_id: str
    ability: Ability
    skill_name: str | None
    dc: int
    advantage_state: D20RollMode
    reason: str
    requires_sight: bool = False
    requires_hearing: bool = False
    interacting_with_actor_id: str | None = None


@dataclass(frozen=True)
class AdjudicationSaveRequest:
    target_actor_ids: tuple[str, ...]
    save_ability: Ability
    dc: int
    advantage_state: D20RollMode
    reason: str


@dataclass(frozen=True)
class ContestParticipantRequest:
    actor_id: str
    ability: Ability
    skill_name: str | None
    advantage_state: D20RollMode


@dataclass(frozen=True)
class AdjudicationContestRequest:
    actor_a: ContestParticipantRequest
    actor_b: ContestParticipantRequest
    tie_rule: ContestTieRule
    reason: str


@dataclass(frozen=True)
class AdjudicationAttackRequest:
    attacker_id: str
    target_id: str
    attack_mode: AdjudicationAttackMode
    attack_id: str | None
    supporting_reason: str


@dataclass(frozen=True)
class AdjudicationModeSwitchRecommendation:
    action: ModeSwitchRecommendationAction
    reason: str
    participant_ids: tuple[str, ...] = ()
    scene_id: str | None = None
    location_id: str | None = None
    battlefield_map_id: str | None = None
    ambush: bool = False


@dataclass(frozen=True)
class AdjudicationIllusionSpec:
    template_id: IllusionTemplateId
    display_name: str
    display_description: str
    semantic_tags: tuple[str, ...] = ()
    target_observer_ids: tuple[str, ...] = ()
    apparent_blocker: bool = False
    apparent_cover: CoverLevel = CoverLevel.NONE
    reveal_policy: str | None = None

@dataclass(frozen=True)
class AdjudicationOperation:
    operation_type: AdjudicationOperationType
    actor_id: str | None = None
    target_actor_id: str | None = None
    note: str = ''
    condition_type: ConditionType | None = None
    source_label: str | None = None
    damage_dice_count: int | None = None
    damage_die_faces: int | None = None
    damage_bonus: int = 0
    damage_type: str | None = None
    damage_divisor: int = 1
    healing_dice_count: int | None = None
    healing_die_faces: int | None = None
    healing_bonus: int = 0
    template_id: ImprovisedTemplateId | None = None
    object_id: str | None = None
    terrain_effect_id: str | None = None
    x: int | None = None
    y: int | None = None
    z: int | None = None
    cover_level: CoverLevel | None = None
    forced_movement_distance_ft: int | None = None
    forced_movement_mode: str | None = None
    displacement: DisplacementVector | None = None
    duration_rounds: int | None = None
    illusion_spec: AdjudicationIllusionSpec | None = None
    extra_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdjudicationBranch:
    public_text: str = ''
    dm_note: str = ''
    operations: tuple[AdjudicationOperation, ...] = ()


@dataclass(frozen=True)
class AdjudicationPlan:
    action_summary: str
    doable: bool
    adjudication_type: AdjudicationType
    reasoning_summary_for_dm: str
    clarification_request: ClarificationRequest | None = None
    check_request: AdjudicationCheckRequest | None = None
    save_request: AdjudicationSaveRequest | None = None
    contest_request: AdjudicationContestRequest | None = None
    attack_request: AdjudicationAttackRequest | None = None
    action_cost_recommendation: ActionCostRecommendation | None = None
    improvised_objects_to_create: tuple[ImprovisedTemplateId, ...] = ()
    terrain_changes_to_create: tuple[ImprovisedTemplateId, ...] = ()
    operation_plan: tuple[AdjudicationOperation, ...] = ()
    on_success: AdjudicationBranch | None = None
    on_failure: AdjudicationBranch | None = None
    on_partial: AdjudicationBranch | None = None
    mode_switch_recommendation: AdjudicationModeSwitchRecommendation | None = None
    raw_response_text: str = ''


@dataclass(frozen=True)
class PendingAdjudicationResolutionState:
    plan_id: str
    actor_id: str
    action_summary: str
    reasoning_summary_for_dm: str
    check_request: AdjudicationCheckRequest | None = None
    on_success: AdjudicationBranch | None = None
    on_failure: AdjudicationBranch | None = None
    on_partial: AdjudicationBranch | None = None
    mode_switch_recommendation: AdjudicationModeSwitchRecommendation | None = None


@dataclass(frozen=True)
class ImprovisedTemplateDefinition:
    template_id: ImprovisedTemplateId
    feature_type: str
    cover_provided: CoverLevel
    traversable: bool
    occupiable: bool
    blocks_los: bool
    blocks_loe: bool
    bottom_offset_ft: int
    top_offset_ft: int
    movement_cost_override_feet_per_5ft: int | None = None
    tags: tuple[str, ...] = ()
    is_blocker: bool = False
    footprint: tuple[tuple[int, int], ...] = ((0, 0),)


@dataclass(frozen=True)
class AdjudicationContext:
    campaign_id: str
    runtime_mode: str
    controller_id: str
    actor_id: str
    declaration: str
    current_scene_id: str | None
    current_location_id: str | None
    active_actor_id: str | None
    party_goal_summary: str
    recent_summary: str
    unresolved_hooks: tuple[str, ...] = ()
    visible_actor_summaries: tuple[str, ...] = ()
    nearby_feature_summaries: tuple[str, ...] = ()
    actor_status_summary: str = ''
    action_economy_summary: str = ''
    allowed_template_ids: tuple[str, ...] = ()
    allowed_illusion_template_ids: tuple[str, ...] = ()
    allowed_operation_types: tuple[str, ...] = ()


AdjudicatedCheckRequest = AdjudicationCheckRequest
AdjudicatedSaveRequest = AdjudicationSaveRequest
AdjudicatedContestRequest = AdjudicationContestRequest
AdjudicatedAttackRequest = AdjudicationAttackRequest


