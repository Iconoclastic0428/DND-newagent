from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .adjudication import PendingAdjudicationResolutionState
from .effects import CheckRequest
from .exploration import ExplorationState, NpcAttitude, PendingExplorationCheckState
from .hostile_escalation import AdHocEncounterScenePlan, CombatTransitionState, ReinforcementPlan, SynthesizedCombatantSpec
from .spellcasting import SpellPerceptibilityProfile
from .travel import TravelState
from .social import SocialRuntimeState
from .progression import CampaignProgressionState
from .advancement import AdvancementRuntimeState


class RuntimeMode(str, Enum):
    STORYTELLING = 'storytelling'
    COMBAT = 'combat'


class ModeSwitchAction(str, Enum):
    STAY_IN_STORYTELLING = 'stay_in_storytelling'
    ENTER_COMBAT = 'enter_combat'
    REMAIN_IN_COMBAT = 'remain_in_combat'
    EXIT_COMBAT = 'exit_combat'


ModeSwitchDecisionType = ModeSwitchAction


class StoryTranscriptVisibility(str, Enum):
    PUBLIC = 'public'
    DM_ONLY = 'dm-only'
    PRIVATE_CONTROLLERS = 'private-controllers'


@dataclass(frozen=True)
class StorytellingTurnContext:
    campaign_id: str
    mode: RuntimeMode
    current_scene_id: str | None
    current_location_id: str | None
    party_goal_summary: str
    unresolved_hooks: tuple[str, ...] = ()
    current_scene_summary: str = ''
    recent_session_summary: str = ''
    party_beliefs: tuple[str, ...] = ()
    visible_npc_ids: tuple[str, ...] = ()
    mode_hint: str = 'storytelling'
    nearby_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CombatTransitionContext:
    campaign_id: str
    mode: RuntimeMode
    reason: str
    suggested_participants: tuple[str, ...] = ()
    current_scene_id: str | None = None
    current_location_id: str | None = None
    ambush: bool = False


@dataclass(frozen=True)
class EnterCombatPlan:
    reason: str
    participant_ids: tuple[str, ...]
    scene_id: str | None = None
    location_id: str | None = None
    ambush: bool = False
    battlefield_map_id: str | None = None
    surprised_actor_ids: tuple[str, ...] = ()
    synthesized_combatants: tuple[SynthesizedCombatantSpec, ...] = ()
    reinforcement_plans: tuple[ReinforcementPlan, ...] = ()
    scene_plan: AdHocEncounterScenePlan | None = None
    transition_state: CombatTransitionState | None = None


@dataclass(frozen=True)
class ExitCombatPlan:
    reason: str
    preserve_scene_state: bool = True
    resulting_scene_id: str | None = None
    follow_up_summary: str = ''


@dataclass(frozen=True)
class ModeSwitchDecision:
    decision_type: ModeSwitchDecisionType
    reason: str
    enter_combat_plan: EnterCombatPlan | None = None
    exit_combat_plan: ExitCombatPlan | None = None
    selection: Any | None = None
    confidence: float = 1.0
    raw_response_text: str = ''


@dataclass(frozen=True)
class StoryTranscriptEntry:
    speaker: str
    text: str
    visibility: StoryTranscriptVisibility = StoryTranscriptVisibility.PUBLIC
    controller_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class StorySceneUpdate:
    scene_id: str | None = None
    location_id: str | None = None
    summary: str | None = None
    open_loops: tuple[str, ...] | None = None
    party_goals: tuple[str, ...] | None = None
    party_beliefs: tuple[str, ...] | None = None


@dataclass(frozen=True)
class StoryCheckRequestState:
    request_id: str
    actor_id: str
    prompt: str
    reason: str
    check_request: CheckRequest
    controller_id: str | None = None


@dataclass(frozen=True)
class StoryTurnDecision:
    public_narration: str
    transcript_entries: tuple[StoryTranscriptEntry, ...] = ()
    check_request: StoryCheckRequestState | None = None
    scene_update: StorySceneUpdate | None = None
    mode_switch_decision: ModeSwitchDecision | None = None
    memory_note: str = ''
    raw_response_text: str = ''


class SpellcastingObservationConfidence(str, Enum):
    UNAWARE = 'unaware'
    EFFECT_ONLY = 'effect-only'
    SUSPECTED = 'suspected'
    CLEAR = 'clear'


class SpellcastingConcernLevel(str, Enum):
    NONE = 'none'
    LOW = 'low'
    MODERATE = 'moderate'
    HIGH = 'high'
    EXTREME = 'extreme'


class SpellcastingReactionCategory(str, Enum):
    NO_REACTION = 'no_reaction'
    NOTICES_BUT_IGNORES = 'notices_but_ignores'
    CURIOUS = 'curious'
    MILDLY_WARY = 'mildly_wary'
    SOCIALLY_DISAPPROVING = 'socially_disapproving'
    SUSPICIOUS = 'suspicious'
    ALARMED = 'alarmed'
    CONFRONTATIONAL = 'confrontational'
    REPORT_TO_AUTHORITY = 'report_to_authority'
    HOSTILE = 'hostile'
    ESCALATES_TO_MODE_SWITCH_CANDIDATE = 'escalates_to_mode_switch_candidate'


class StoryWitnessKind(str, Enum):
    RUNTIME_ACTOR = 'runtime-actor'
    SCENE_NPC = 'scene-npc'


class StorySpellObserverAwareness(str, Enum):
    CASTER_CONFIRMED = 'caster-confirmed'
    TARGET_AFFECTED = 'target-affected'
    SAW_CASTING = 'saw-casting'
    SAW_EFFECT_ONLY = 'saw-effect-only'
    NOTICED_UNUSUAL = 'noticed-unusual'
    UNAWARE = 'unaware'


@dataclass(frozen=True)
class StoryModeCastAttempt:
    actor_id: str
    spell_id: str
    controller_id: str
    scene_id: str | None
    location_id: str | None
    target_id: str | None = None
    point: tuple[int, int, int] | None = None
    casting_time_seconds: int = 6
    ritual_cast: bool = False


@dataclass(frozen=True)
class StoryModeCastContext:
    attempt: StoryModeCastAttempt
    spell_name: str
    spell_level: int
    action_cost: str
    perceptibility: SpellPerceptibilityProfile
    current_scene_summary: str = ''
    recent_session_summary: str = ''
    party_goal_summary: str = ''
    unresolved_hooks: tuple[str, ...] = ()
    visible_npc_ids: tuple[str, ...] = ()
    nearby_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WitnessObservation:
    observer_id: str
    observer_kind: StoryWitnessKind
    display_name: str
    paying_attention: bool
    perceived_casting_act: bool
    perceived_spell_effect: bool
    confidence: SpellcastingObservationConfidence
    concern_level: SpellcastingConcernLevel
    attitude: NpcAttitude | None = None
    current_stance: str | None = None
    applicable_norm_ids: tuple[str, ...] = ()
    norm_tags: tuple[str, ...] = ()
    relationship_trust: int = 0
    relationship_suspicion: int = 0
    relationship_fear: int = 0
    relationship_respect: int = 0


@dataclass(frozen=True)
class WitnessObservationPacket:
    caster_actor_id: str
    spell_id: str
    spell_name: str
    spell_level: int
    action_cost: str
    target_actor_id: str | None
    point: tuple[int, int, int] | None = None
    witnesses: tuple[WitnessObservation, ...] = ()


@dataclass(frozen=True)
class ObserverFacingSpellcastResult:
    observer_id: str
    observer_kind: StoryWitnessKind
    awareness: StorySpellObserverAwareness


@dataclass(frozen=True)
class SpellcastingWitnessReaction:
    witness_id: str
    reaction_category: SpellcastingReactionCategory
    summary: str
    public_text: str = ''
    private_note: str = ''


@dataclass(frozen=True)
class StoryModeCastEscalationDecision:
    recommended: bool = False
    reason: str = ''
    mode_switch_decision: ModeSwitchDecision | None = None


@dataclass(frozen=True)
class SpellcastingSocialReactionPlan:
    public_narration: str = ''
    witness_reactions: tuple[SpellcastingWitnessReaction, ...] = ()
    scene_note: str = ''
    dm_note: str = ''
    escalation: StoryModeCastEscalationDecision | None = None
    raw_response_text: str = ''


@dataclass(frozen=True)
class StoryModeCastResolution:
    attempt: StoryModeCastAttempt
    context: StoryModeCastContext
    witness_packet: WitnessObservationPacket
    observer_results: tuple[ObserverFacingSpellcastResult, ...] = ()
    social_reaction_plan: SpellcastingSocialReactionPlan | None = None
    remained_in_storytelling: bool = True
    time_advanced_seconds: int = 0


@dataclass
class StoryRuntimeState:
    campaign_id: str
    current_scene_id: str
    runtime_mode: RuntimeMode = RuntimeMode.STORYTELLING
    current_chapter_id: str | None = None
    canonical_location_id: str | None = None
    active_battlefield_map_id: str | None = None
    open_loops: tuple[str, ...] = ()
    current_party_goals: tuple[str, ...] = ()
    recent_summary: str = ''
    metadata: dict[str, str] = field(default_factory=dict)
    pending_check: StoryCheckRequestState | None = None
    pending_exploration_check: PendingExplorationCheckState | None = None
    pending_adjudication: PendingAdjudicationResolutionState | None = None
    transcript_entries: tuple[StoryTranscriptEntry, ...] = ()
    travel_state: TravelState | None = None
    exploration_state: ExplorationState | None = None
    social_state: SocialRuntimeState = field(default_factory=SocialRuntimeState)
    progression_state: CampaignProgressionState = field(default_factory=CampaignProgressionState)
    advancement_state: AdvancementRuntimeState = field(default_factory=AdvancementRuntimeState)
    combat_transition: CombatTransitionState | None = None
    session_log_id: str = 'session-demo-0001'



