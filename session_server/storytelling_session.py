from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
import re

from campaign_ingestion import CampaignRetrievalIndex, CampaignRetrievalQuery
from dm_agent.memory import (
    CampaignStateSummary,
    DiscoveredSecretsSummary,
    DmMemoryWriter,
    NpcPlaybook,
    OpenLoopsSummary,
    SceneState,
    SessionLogEntry,
)
from dm_agent.adjudication import DMAdjudicationPlanner
from dm_agent.runtime import CampaignDocument, DMRuntimeError, DMStorytellingRuntime
from shared_types.adjudication import AdjudicationContext
from shared_types.capabilities import (
    AttackRollGateEffect,
    CompositeEffect,
    ConditionEffectDef,
    DamageEffectDef,
    HealingEffectDef,
    IllusionTemplateId,
    SaveGateEffect,
    StartActiveEffectDef,
)
from shared_types.encounter_events import (
    AdHocEncounterSceneSynthesizedEvent,
    AdjudicationContextBuiltEvent,
    AdjudicationPlanReceivedEvent,
    AdjudicationPlanRejectedEvent,
    AdjudicationPlanValidatedEvent,
    AdjudicationRequestedEvent,
    ClarificationRequestedEvent,
    CheckRolledEvent,
    CombatEndedEvent,
    CombatStartedEvent,
    StorySceneCommittedToCombatEvent,
    StoryNPCCombatantSynthesizedEvent,
    StoryNPCCombatantFallbackUsedEvent,
    ReinforcementScheduledEvent,
    ReinforcementEnteredEvent,
    HostileEscalationTriggeredEvent,
    HostileEscalationEvaluatedEvent,
    SurpriseEvaluationTriggeredEvent,
    SurpriseStateComputedEvent,
    CombatStartedFromStorySceneEvent,
    DiscoveryRevealedEvent,
    DowntimeProjectCompletedEvent,
    DowntimeProjectProgressedEvent,
    DowntimeProjectStartedEvent,
    EnterCombatPlannedEvent,
    HexDiscoveredEvent,
    HexMapLoadedEvent,
    LandmarkDiscoveredEvent,
    LocationReachedEvent,
    ModeSwitchRequestedEvent,
    ReturnedToStorytellingEvent,
    StoryActionDeclaredEvent,
    StoryCheckPromptedEvent,
    StoryCheckResolvedEvent,
    StorySceneUpdatedEvent,
    StoryModeSpellcastCausedSuspicionEvent,
    StoryModeSpellcastDeclaredEvent,
    StoryModeSpellcastEscalationRecommendedEvent,
    StoryModeSpellcastIgnoredEvent,
    StoryModeSpellcastRejectedEvent,
    StoryModeSpellcastResolvedEvent,
    StoryModeSpellcastValidatedEvent,
    StoryModeSpellEffectPerceivedEvent,
    StoryModeSpellcastingPerceivedEvent,
    StoryTranscriptAppendedEvent,
    SpellcastingSocialReactionResolvedEvent,
    SpellcastingWitnessPacketCreatedEvent,
    TravelEventHookTriggeredEvent,
    TravelInterruptedEvent,
    TravelModeProjectionUpdatedEvent,
    SocialInfluenceResolvedEvent,
    TrapDetectedEvent,
    FactionRelationshipChangedEvent,
    InfluenceRetryCooldownSetEvent,
    MagicalNormConsultedEvent,
    NPCAttitudeChangedEvent,
    ReputationChangedEvent,
    SocialConsequenceAppliedEvent,
    SocialIncidentLoggedEvent,
    SocialPropagationExecutedEvent,
    SocialPropagationScheduledEvent,
    SocialStateProjectionUpdatedEvent,
    TrapDisarmedEvent,
    TrapTriggeredEvent,
    PuzzleProgressedEvent,
    PuzzleSolvedEvent,
    TravelPaceChangedEvent,
    TravelResumedEvent,
    TravelRoutePlannedEvent,
    TravelStartedEvent,
    TravelStepAdvancedEvent,
    XPRewardAppliedEvent,
    XPRewardLoggedEvent,
    MilestoneAdvancementGrantedEvent,
    MilestoneCompletedEvent,
    ProgressionEligibilityUpdatedEvent,
    ProgressionProjectionUpdatedEvent,
    LevelUpQueuedEvent,
    AdvancementCommitFailedEvent,
    LevelUpAvailableEvent,
)
from shared_types.encounter_intents import CastSpellIntent, StartEncounterIntent
from shared_types.encounter_models import ActorSide, DyingState, DyingStateStatus, EncounterPhase, GridPosition, RuntimeSpellState
from shared_types.effects import CheckRequest, ResolutionContext
from shared_types.errors import EncounterClarificationRequiredError, EncounterOwnershipError, EncounterPermissionError, EncounterValidationError
from shared_types.models import CharacterRecord, ChoiceSource, ChoiceSourceKind, ChoiceView
from shared_types.conditions import ConditionType
from shared_types.advancement import AdvancementCommitStatus, AdvancementValidationStatus
from shared_types.exploration import (
    AbandonPuzzleIntent,
    AssignExplorationRoleIntent,
    AttemptPuzzleIntent,
    AttemptSocialInfluenceIntent,
    AttemptTrapIntent,
    BypassTrapIntent,
    CancelDowntimeProjectIntent,
    DowntimeProjectStatus,
    ExplorationMode,
    ExplorationRole,
    ExplorationState,
    ProcedureAttemptKind,
    SetCampStateIntent,
    SetMarchingOrderIntent,
    SetWatchOrderIntent,
    SocialApproachType,
    StartDowntimeProjectIntent,
    TriggerTrapIntent,
    WorkDowntimeProjectIntent,
)
from shared_types.hostile_escalation import (
    CombatTransitionState,
    HostileEscalationDecision,
    HostileEscalationOutcome,
)
from shared_types.spellcasting import SpellRuntimeSupportMode
from shared_types.storytelling import (
    EnterCombatPlan,
    ExitCombatPlan,
    ModeSwitchAction,
    ModeSwitchDecision,
    ObserverFacingSpellcastResult,
    RuntimeMode,
    SpellcastingConcernLevel,
    SpellcastingObservationConfidence,
    SpellcastingReactionCategory,
    SpellcastingSocialReactionPlan,
    StoryCheckRequestState,
    StoryModeCastAttempt,
    StoryModeCastContext,
    StoryModeCastResolution,
    StoryRuntimeState,
    StorySceneUpdate,
    StorySpellObserverAwareness,
    StorytellingTurnContext,
    StoryTranscriptEntry,
    StoryTranscriptVisibility,
    StoryTurnDecision,
    StoryWitnessKind,
    WitnessObservation,
    WitnessObservationPacket,
)
from shared_types.social import SocialRuntimeState, SocialKnowledgeAudience
from shared_types.progression import (
    MilestoneDistributionPolicy,
    MilestoneSourceType,
    ProgressionMode,
    ProgressionPolicy,
    ProgressionRecipientScope,
    XPDistributionPolicy,
    XPRewardSourceType,
)

from .encounter_session import EncounterSession
from encounter_runtime.adjudication import EncounterAdjudicationRuntime
from encounter_runtime.equipment import refresh_actor_equipment_state
from encounter_runtime.improvised_templates import list_template_ids
from rules_engine.exploration import ExplorationProcedureEngine
from rules_engine.hexmap_loader import HexMapLoader
from rules_engine.hostile_escalation import HostileEscalationEngine
from rules_engine.travel import HexTravelEngine
from rules_engine.social import SocialConsequenceEngine
from rules_engine.progression import CampaignProgressionEngine
from rules_engine.advancement import CharacterAdvancementEngine
from shared_types.travel import AdvanceTravelIntent, HexCoord, PlanTravelRouteIntent, ResumeTravelIntent, SetTravelPaceIntent, TravelHookDefinition, TravelPace, TravelState, TravelStatus, unique_strings


def _without_echoed_player_declaration(entries: tuple[StoryTranscriptEntry, ...], declaration: str | None) -> tuple[StoryTranscriptEntry, ...]:
    if not declaration:
        return entries
    declaration_tokens = _story_echo_tokens(declaration)
    if not declaration_tokens:
        return entries
    return tuple(entry for entry in entries if not _is_echoed_player_declaration(entry, declaration_tokens))


def _is_echoed_player_declaration(entry: StoryTranscriptEntry, declaration_tokens: tuple[str, ...]) -> bool:
    if entry.visibility != StoryTranscriptVisibility.PUBLIC:
        return False
    entry_tokens = _story_echo_tokens(entry.text)
    if not entry_tokens:
        return False
    if entry_tokens == declaration_tokens:
        return True
    if len(declaration_tokens) <= 12 and abs(len(entry_tokens) - len(declaration_tokens)) <= 2:
        shared = set(entry_tokens) & set(declaration_tokens)
        return len(shared) / max(1, min(len(set(entry_tokens)), len(set(declaration_tokens)))) >= 0.85
    return False


def _story_echo_tokens(text: str) -> tuple[str, ...]:
    return tuple(re.findall(r"[a-z0-9']+", text.lower()))


@dataclass(frozen=True)
class StoryControllerView:
    summary_lines: tuple[str, ...]
    available_choices: dict[str, tuple]


@dataclass(frozen=True)
class StoryPrompt:
    prompt_id: str
    prompt_kind: str
    controller_id: str
    prompt: str


_STORY_UTILITY_CANTRIP_SPECS = {
    'Druidcraft': {
        'effects': {
            'weather-sensor': 'Create a harmless sensory token that predicts the next 24 hours of local weather and lasts 1 round.',
            'bloom': 'Cause a flower to bloom, a seed pod to open, or a leaf bud to blossom at once.',
            'sensory-effect': 'Create a harmless sensory effect in a 5-foot cube, such as falling leaves, tiny fey, a breeze, animal sounds, or a faint skunk odor.',
            'fire-play': 'Light or snuff out a candle, torch, or small campfire.',
        },
        'rules': (
            'Range 30 feet.',
            'Choose exactly one listed Druidcraft option each casting.',
            'The weather-sensor token lasts 1 round and only forecasts local weather for the next 24 hours.',
            'The sensory effect must remain harmless and fit inside a 5-foot cube.',
            'Fire Play only affects a candle, torch, or small campfire.',
        ),
    },
    'Elementalism': {
        'effects': {
            'beckon-air': 'Create a breeze in a 5-foot cube strong enough to move cloth, stir dust, rustle leaves, or shut open doors and shutters that are not being held open.',
            'beckon-earth': 'Create a thin shroud of dust or sand over surfaces in a 5-foot cube, or write a word in earth or sand.',
            'beckon-fire': 'Create harmless embers and colorful scented smoke in a 5-foot cube; the embers can light candles, torches, or lamps, and the scent lasts 1 minute.',
            'beckon-water': 'Create cool mist in a 5-foot cube, or create one cup of clean water on a surface or in an open container; that water evaporates within 1 minute.',
            'sculpt-element': 'Shape a 1-foot cube of earth, sand, fire, smoke, mist, or water into a crude form for 1 hour.',
        },
        'rules': (
            'Range 30 feet.',
            'Choose exactly one listed Elementalism option each casting.',
            'Beckon Air cannot shut a door or shutter that something is holding open.',
            'Beckon Fire creates harmless embers and smoke only in a 5-foot cube.',
            'Beckon Water creates only one cup of clean water and it evaporates within 1 minute.',
            'Sculpt Element only shapes a 1-foot cube of the listed element types and lasts 1 hour.',
        ),
    },
    'Prestidigitation': {
        'effects': {
            'sensory-effect': 'Create an immediate harmless sensory effect such as sparks, a puff of wind, faint music, or an odd odor.',
            'fire-play': 'Instantly light or snuff a candle, torch, or small campfire.',
            'clean-or-soil': 'Instantly clean or soil one object no larger than 1 cubic foot.',
            'minor-sensation': 'Chill, warm, or flavor one nonliving material no larger than 1 cubic foot for 1 hour.',
            'magic-mark': 'Create a color, mark, or symbol on an object or surface for 1 hour.',
            'minor-creation': 'Create a nonmagical trinket or an illusory image that can fit in your hand until the end of your next turn; it cannot deal damage or be worth money.',
        },
        'rules': (
            'Range 10 feet.',
            'Choose exactly one listed Prestidigitation option each casting.',
            'You can sustain at most three non-instantaneous Prestidigitation effects at the same time.',
            'Clean or Soil and Minor Sensation are limited to objects or material no larger than 1 cubic foot.',
            'Minor Creation must fit in your hand, cannot deal damage, and has no monetary value.',
        ),
    },
    'Thaumaturgy': {
        'effects': {
            'altered-eyes': 'Change the appearance of your eyes for 1 minute.',
            'booming-voice': 'Triple the volume of your voice for 1 minute; during that time you have advantage on Charisma (Intimidation) checks.',
            'fire-play': 'Cause flames to flicker, brighten, dim, or change color for 1 minute.',
            'invisible-hand': 'Instantly open or close an unlocked door or window.',
            'phantom-sound': 'Create a brief sound at a point within range, such as thunder, a raven cry, or ominous whispers.',
            'tremors': 'Cause harmless tremors in the ground for 1 minute.',
        },
        'rules': (
            'Range 30 feet.',
            'Choose exactly one listed Thaumaturgy option each casting.',
            'You can sustain at most three different 1-minute Thaumaturgy effects at the same time.',
            'Invisible Hand only opens or closes an unlocked door or window.',
            'Booming Voice affects Intimidation checks only while that 1-minute effect lasts.',
        ),
    },
    'Mending': {
        'rules': (
            'Casting time 1 minute and range Touch.',
            'Repair one break or tear in an object when the damaged area is no larger than 1 foot in any dimension.',
            'Mending can physically repair a magic item but does not restore lost magic.',
        ),
        'requires_description': True,
    },
    'Message': {
        'rules': (
            'Range 120 feet.',
            'Point at one creature and whisper a message that only that creature hears.',
            'The target may reply in a whisper that only the caster hears.',
            'The spell can pass through solid barriers only if the caster knows the target is behind them and is familiar with the target.',
            'Magical silence, 1 foot of stone, metal, or wood, or a thin sheet of lead blocks the spell.',
        ),
        'requires_message': True,
    },
}


class StorytellingSession:
    def __init__(
        self,
        *,
        encounter_session: EncounterSession,
        story_state: StoryRuntimeState,
        campaign_root: Path,
        memory_writer: DmMemoryWriter,
        dm_runtime: DMStorytellingRuntime | None = None,
        llm_feedback_sink: object | None = None,
        travel_engine: HexTravelEngine | None = None,
        exploration_engine: ExplorationProcedureEngine | None = None,
        social_engine: SocialConsequenceEngine | None = None,
        progression_engine: CampaignProgressionEngine | None = None,
        advancement_engine: CharacterAdvancementEngine | None = None,
        hostile_escalation_engine: HostileEscalationEngine | None = None,
    ) -> None:
        self.encounter_session = encounter_session
        self.story_state = story_state
        self.campaign_root = campaign_root.resolve()
        self.memory_writer = memory_writer
        self.dm_runtime = dm_runtime
        self.llm_feedback_sink = llm_feedback_sink
        self.retrieval_index = CampaignRetrievalIndex.from_root(self.campaign_root)
        self.adjudication_planner = DMAdjudicationPlanner(client=dm_runtime.client, config=dm_runtime.config) if dm_runtime is not None else None
        self.adjudication_runtime = EncounterAdjudicationRuntime(kernel=self.encounter_session.control_runtime.kernel)
        self.travel_engine = travel_engine
        self.exploration_engine = exploration_engine
        self.social_engine = social_engine
        self.progression_engine = progression_engine or CampaignProgressionEngine()
        self.advancement_engine = advancement_engine or CharacterAdvancementEngine()
        if hostile_escalation_engine is None:
            self.hostile_escalation_engine = HostileEscalationEngine(
                runtime_services=self.encounter_session.runtime_services,
                campaign_id=self.story_state.campaign_id,
                campaign_root=self.campaign_root,
            )
        else:
            hostile_escalation_engine.configure(
                runtime_services=self.encounter_session.runtime_services,
                campaign_id=self.story_state.campaign_id,
                campaign_root=self.campaign_root,
            )
            self.hostile_escalation_engine = hostile_escalation_engine
        if self.social_engine is not None and (not self.story_state.social_state.relationships) and self.story_state.exploration_state is not None:
            self.story_state.social_state = self.social_engine.initial_state(exploration_state=self.story_state.exploration_state, current_location_id=self.story_state.canonical_location_id)
        if self.story_state.progression_state.actor_progress:
            self.story_state.progression_state = self.progression_engine.sync_actor_snapshots(self.story_state.progression_state, actor_snapshots=self._progression_actor_snapshots())
        else:
            self.story_state.progression_state = self.progression_engine.initial_state(actor_snapshots=self._progression_actor_snapshots(), mode=self.story_state.progression_state.mode, policy=self.story_state.progression_state.policy)
        self._refresh_exploration_context(auto_initialize=True)
        self._sync_memory_files()

    @property
    def state(self):
        return self.encounter_session.state

    def _require_travel_engine(self) -> HexTravelEngine:
        if self.travel_engine is None or self.story_state.travel_state is None:
            raise EncounterValidationError('No travel map is configured for this session.')
        return self.travel_engine

    def _require_exploration_engine(self) -> ExplorationProcedureEngine:
        if self.exploration_engine is None or self.story_state.exploration_state is None:
            raise EncounterValidationError('No exploration procedure engine is configured for this session.')
        return self.exploration_engine

    def _current_travel_map_id(self) -> str | None:
        travel_state = self.story_state.travel_state
        return None if travel_state is None else travel_state.map_id

    def _travel_active(self) -> bool:
        travel_state = self.story_state.travel_state
        return travel_state is not None and travel_state.status.value != 'idle'

    def _is_dm_controller(self, controller_id: str) -> bool:
        return self.encounter_session.control_runtime.validate_controller(controller_id).role.value == 'dm'

    def _resolve_exploration_actor_id(self, controller_id: str, explicit_actor_id: str | None) -> str:
        if explicit_actor_id is None:
            return self._owned_actor_for_controller(controller_id)
        if self._is_dm_controller(controller_id):
            return explicit_actor_id
        owned_actor_id = self._owned_actor_for_controller(controller_id)
        if explicit_actor_id != owned_actor_id:
            raise EncounterPermissionError('Controllers may only declare exploration procedures for their owned actor.')
        return explicit_actor_id

    def _refresh_exploration_context(self, *, auto_initialize: bool = False, sync_memory: bool = False) -> None:
        engine = self.exploration_engine
        if engine is None:
            return
        actor_ids = self._player_actor_ids()
        if not actor_ids:
            return
        current = self.story_state.exploration_state
        if current is None:
            if not auto_initialize:
                return
            new_state, events = engine.initial_state(
                encounter_state=self.state,
                actor_ids=actor_ids,
                current_scene_id=self.story_state.current_scene_id,
                current_location_id=self.story_state.canonical_location_id,
                current_travel_map_id=self._current_travel_map_id(),
                travel_active=self._travel_active(),
            )
        else:
            new_state, events = engine.sync_context(
                current,
                encounter_state=self.state,
                current_scene_id=self.story_state.current_scene_id,
                current_location_id=self.story_state.canonical_location_id,
                current_travel_map_id=self._current_travel_map_id(),
                travel_active=self._travel_active(),
            )
        if self.social_engine is not None:
            if not self.story_state.social_state.relationships and current is not None:
                self.story_state.social_state = self.social_engine.initial_state(exploration_state=current, current_location_id=self.story_state.canonical_location_id)
            new_state = self.social_engine.sync_exploration_projection(new_state, self.story_state.social_state)
        if current is new_state and not events:
            return
        self._commit_exploration_result(new_state, list(events), sync_memory=sync_memory)

    def _apply_runtime_event(self, event: object) -> None:
        self.encounter_session.control_runtime.kernel._apply_event(self.state, event)

    def _append_exploration_public_entry(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.story_state.transcript_entries = self.story_state.transcript_entries + (
            StoryTranscriptEntry(speaker='Exploration', text=text, visibility=StoryTranscriptVisibility.PUBLIC),
        )
        self.story_state.transcript_entries = self.story_state.transcript_entries[-40:]
        self.story_state.recent_summary = text

    def _commit_exploration_result(self, new_state: ExplorationState, events: list[object], *, sync_memory: bool = True) -> None:
        previous_state = self.story_state.exploration_state
        social_entries: tuple[StoryTranscriptEntry, ...] = ()
        social_notes: tuple[str, ...] = ()
        social_open_loops: tuple[str, ...] = ()
        if self.social_engine is not None:
            social_state, new_state, social_events, social_entries, social_notes, social_open_loops = self.social_engine.integrate_exploration_update(
                self.story_state.social_state,
                previous_state=previous_state,
                new_state=new_state,
                events=tuple(events),
                clock_seconds=self.state.clock_seconds,
                location_id=self.story_state.canonical_location_id,
                scene_id=self.story_state.current_scene_id,
            )
            self.story_state.social_state = social_state
            events = [*events, *social_events]
        self.story_state.exploration_state = new_state
        for event in events:
            self._apply_runtime_event(event)
            if isinstance(event, DiscoveryRevealedEvent) and event.public:
                self._merge_metadata_list('discovered_secrets', (event.text,))
            elif isinstance(event, SocialInfluenceResolvedEvent):
                self._append_exploration_public_entry(event.summary)
                self._merge_metadata_list('scene_state_notes', (event.summary,))
            elif isinstance(event, (TrapDetectedEvent, TrapTriggeredEvent, TrapDisarmedEvent, PuzzleProgressedEvent, PuzzleSolvedEvent)):
                self._append_exploration_public_entry(event.summary)
                self._merge_metadata_list('scene_state_notes', (event.summary,))
            elif isinstance(event, DowntimeProjectStartedEvent):
                text = f'Downtime project started: {event.title}.'
                self._append_exploration_public_entry(text)
                self._merge_metadata_list('scene_state_notes', (text,))
            elif isinstance(event, DowntimeProjectProgressedEvent):
                self._append_exploration_public_entry(event.summary)
                self._merge_metadata_list('scene_state_notes', (event.summary,))
            elif isinstance(event, DowntimeProjectCompletedEvent):
                self._append_exploration_public_entry(event.summary)
                self._merge_metadata_list('scene_state_notes', (event.summary,))
        if social_entries:
            self._append_transcript(social_entries)
        for note in social_notes:
            self._merge_metadata_list('scene_state_notes', (note,))
        if social_open_loops:
            self.story_state.open_loops = unique_strings(self.story_state.open_loops + social_open_loops)
        if sync_memory:
            self._sync_memory_files()

    def validate_controller(self, controller_id: str):
        return self.encounter_session.control_runtime.validate_controller(controller_id)

    def refresh_retrieval_index(self) -> None:
        self.retrieval_index = CampaignRetrievalIndex.from_root(self.campaign_root)

    def storytelling_context(self) -> StorytellingTurnContext:
        return StorytellingTurnContext(
            campaign_id=self.story_state.campaign_id,
            mode=self.story_state.runtime_mode,
            current_scene_id=self.story_state.current_scene_id,
            current_location_id=self.story_state.canonical_location_id,
            party_goal_summary='; '.join(self.story_state.current_party_goals),
            unresolved_hooks=self.story_state.open_loops,
            current_scene_summary=self.story_state.recent_summary,
            recent_session_summary=self.story_state.recent_summary,
            party_beliefs=tuple(item for item in self.story_state.metadata.get('party_beliefs', '').split('|') if item),
            visible_npc_ids=self._visible_npc_ids(),
            nearby_tags=tuple(tag for tag in self.story_state.metadata.get('nearby_tags', '').split(',') if tag),
        )

    def _visible_npc_ids(self) -> tuple[str, ...]:
        explicit = tuple(item for item in self.story_state.metadata.get('visible_npc_ids', '').split(',') if item)
        if explicit:
            return explicit
        return tuple(actor_id for actor_id, actor in self.state.actors.items() if actor.side == ActorSide.MONSTER)

    def _player_actor_ids(self) -> tuple[str, ...]:
        return tuple(actor_id for actor_id, actor in self.state.actors.items() if actor.side == ActorSide.PLAYER)


    def _progression_actor_snapshots(self) -> tuple[tuple[str, str, int], ...]:
        return tuple(
            (actor_id, self.state.actors[actor_id].name, self.state.actors[actor_id].level)
            for actor_id in self._player_actor_ids()
        )

    def _sync_progression_state(self) -> None:
        self.story_state.progression_state = self.progression_engine.sync_actor_snapshots(
            self.story_state.progression_state,
            actor_snapshots=self._progression_actor_snapshots(),
        )

    def _parse_progression_recipient_spec(self, spec: str) -> tuple[ProgressionRecipientScope, tuple[str, ...]]:
        if spec == 'party':
            return ProgressionRecipientScope.PARTY, self._player_actor_ids()
        if spec.startswith('actor:'):
            actor_id = spec.split(':', 1)[1].strip()
            if not actor_id:
                raise EncounterValidationError('Progression actor recipients require `actor:<actor-id>`.')
            return ProgressionRecipientScope.INDIVIDUAL, (actor_id,)
        if spec.startswith('actors:'):
            actor_ids = tuple(item.strip() for item in spec.split(':', 1)[1].split(',') if item.strip())
            if not actor_ids:
                raise EncounterValidationError('Progression subset recipients require `actors:<actor-id>,<actor-id>`.')
            scope = ProgressionRecipientScope.INDIVIDUAL if len(actor_ids) == 1 else ProgressionRecipientScope.SUBSET
            return scope, actor_ids
        raise EncounterValidationError('Progression recipients must be `party`, `actor:<actor-id>`, or `actors:<actor-id>,<actor-id>`.')

    def _progression_visible_lines(self, *, dm_view: bool) -> tuple[str, ...]:
        self._sync_progression_state()
        return self.progression_engine.visible_projection_lines(
            self.story_state.progression_state,
            actor_snapshots=self._progression_actor_snapshots(),
            dm_view=dm_view,
        )

    def _progression_dm_lines(self) -> tuple[str, ...]:
        self._sync_progression_state()
        return self.progression_engine.dm_status_lines(
            self.story_state.progression_state,
            actor_snapshots=self._progression_actor_snapshots(),
        )

    def _social_visible_lines(self, *, dm_view: bool) -> tuple[str, ...]:
        if self.social_engine is None:
            return ()
        social_state = self.story_state.social_state
        if not social_state.incidents and not social_state.propagation_queue and not social_state.retry_cooldowns:
            return ()
        projection_lines = self.social_engine.visible_projection_lines(social_state, dm_view=dm_view)
        dm_status_lines = self.social_engine.dm_status_lines(social_state) if dm_view else ()
        if not projection_lines and not dm_status_lines:
            return ()
        lines = ['Social consequences:']
        lines.extend(f'  - {line}' for line in projection_lines)
        if dm_status_lines:
            lines.extend(dm_status_lines)
        return tuple(lines)

    def _resolve_levelup_actor_id(self, controller_id: str, explicit_actor_id: str | None) -> str:
        if explicit_actor_id is None:
            actor_id = self._owned_actor_for_controller(controller_id)
        else:
            if not self._is_dm_controller(controller_id):
                owned_actor_id = self._owned_actor_for_controller(controller_id)
                if explicit_actor_id != owned_actor_id:
                    raise EncounterPermissionError('Controllers may only advance their owned actor.')
            actor_id = explicit_actor_id
        actor = self.state.actors.get(actor_id)
        if actor is None or actor.side != ActorSide.PLAYER or actor.character_record is None:
            raise EncounterValidationError('Level-up commands require a player actor with a CharacterRecord.')
        return actor_id

    def _parse_levelup_actor(self, controller_id: str, tokens: list[str], *, index: int) -> tuple[str, int]:
        if len(tokens) > index and tokens[index] in self.state.actors:
            return self._resolve_levelup_actor_id(controller_id, tokens[index]), index + 1
        if self._is_dm_controller(controller_id):
            raise EncounterValidationError('DM level-up commands require an explicit <actor-id>.')
        return self._resolve_levelup_actor_id(controller_id, None), index

    def _pending_level_up_for_actor(self, actor_id: str):
        self._sync_progression_state()
        pending_records = [
            record
            for record in self.story_state.progression_state.pending_level_ups.values()
            if record.actor_id == actor_id and not record.applied and record.source_mode == self.story_state.progression_state.mode
        ]
        pending_records.sort(key=lambda item: (item.target_new_total_level, item.pending_id))
        return pending_records[0] if pending_records else None

    def _live_character_record(self, actor_id: str) -> CharacterRecord:
        actor = self.state.actors.get(actor_id)
        if actor is None or actor.character_record is None:
            raise EncounterValidationError('Level-up requires a player actor with a committed character record.')
        return replace(actor.character_record, inventory={item_id: quantity for item_id, quantity in actor.carried_item_counts.items() if quantity > 0})

    def _species_hit_point_bonus_for_actor(self, actor_id: str) -> int:
        record = self._live_character_record(actor_id)
        species = self.encounter_session.runtime_services.character_catalog.species.get(record.species_id)
        if species is None:
            raise EncounterValidationError(f'Species {record.species_id!r} is missing from the active character catalog.')
        return species.hit_point_bonus_per_level

    def _advancement_choice_group_id(self, actor_id: str, choice_id: str) -> str:
        return f'levelup:{actor_id}:{choice_id}'

    def _advancement_visible_lines(self, controller_id: str, *, dm_view: bool) -> tuple[str, ...]:
        actor_ids: list[str]
        if dm_view:
            actor_ids = list(self._player_actor_ids())
        else:
            try:
                actor_ids = [self._owned_actor_for_controller(controller_id)]
            except EncounterPermissionError:
                actor_ids = []
        lines: list[str] = []
        for actor_id in actor_ids:
            actor = self.state.actors.get(actor_id)
            if actor is None or actor.character_record is None:
                continue
            pending = self._pending_level_up_for_actor(actor_id)
            transaction_id = self.story_state.advancement_state.actor_transaction_ids.get(actor_id)
            if pending is None and transaction_id is None:
                continue
            label = actor.name
            if pending is not None and transaction_id is None:
                lines.append(f'{label}: level-up available to {pending.target_new_total_level} from {pending.source_mode.value}; start with /levelup start {actor_id}.')
                continue
            transaction_lines = self.advancement_engine.actor_summary_lines(self.story_state.advancement_state, actor_id=actor_id)
            if transaction_lines:
                lines.append(f'{label}: {transaction_lines[0]}')
                lines.extend(f'  {line}' for line in transaction_lines[1:])
        return tuple(lines)

    def _advancement_available_choices(self, controller_id: str, *, dm_view: bool) -> dict[str, tuple[ChoiceView, ...]]:
        if dm_view:
            actor_ids = self._player_actor_ids()
        else:
            try:
                actor_ids = (self._owned_actor_for_controller(controller_id),)
            except EncounterPermissionError:
                actor_ids = ()
        projected: dict[str, tuple[ChoiceView, ...]] = {}
        for actor_id in actor_ids:
            transaction_id = self.story_state.advancement_state.actor_transaction_ids.get(actor_id)
            if transaction_id is None:
                continue
            transaction = self.story_state.advancement_state.transactions.get(transaction_id)
            if transaction is None:
                continue
            if transaction.chosen_class_id is None:
                record = self._live_character_record(actor_id)
                allocations = self.advancement_engine._legal_class_allocations(
                    record=record,
                    catalog=self.encounter_session.runtime_services.character_catalog,
                    state=self.story_state.advancement_state,
                )
                if len(allocations) > 1:
                    projected[self._advancement_choice_group_id(actor_id, 'class-selection')] = tuple(
                        ChoiceView(
                            option_id=allocation.class_id,
                            label=allocation.class_name,
                            detail=f'Advance to class level {allocation.new_class_level}',
                        )
                        for allocation in allocations
                    )
            for choice_id, options in self.advancement_engine.available_choice_views(self.story_state.advancement_state, actor_id=actor_id).items():
                projected[self._advancement_choice_group_id(actor_id, choice_id)] = tuple(
                    ChoiceView(option_id=option.option_id, label=option.label, detail=option.detail)
                    for option in options
                )
        return projected

    def _advancement_writeback_lines(self) -> tuple[str, ...]:
        lines = list(self._advancement_visible_lines('dm', dm_view=True))
        return tuple(lines[-6:])

    def _refresh_pending_level_up_block_state(self, actor_id: str) -> None:
        transaction_id = self.story_state.advancement_state.actor_transaction_ids.get(actor_id)
        pending = self._pending_level_up_for_actor(actor_id)
        if pending is None:
            return
        blocked = True
        if transaction_id is not None:
            transaction = self.story_state.advancement_state.transactions.get(transaction_id)
            blocked = transaction is None or transaction.validation_status != AdvancementValidationStatus.READY_TO_COMMIT
        new_state, events = self.progression_engine.set_pending_level_up_blocked_state(
            self.story_state.progression_state,
            pending_id=pending.pending_id,
            blocked=blocked,
            actor_snapshots=self._progression_actor_snapshots(),
        )
        self.story_state.progression_state = new_state
        for event in events:
            self._apply_runtime_event(event)

    def _apply_committed_character_record(self, actor_id: str, committed_record: CharacterRecord, *, gained_hit_points: int) -> None:
        actor = self.state.actors.get(actor_id)
        if actor is None or actor.character_record is None:
            raise EncounterValidationError('Advancement can only be applied to a compiled player actor.')
        runtime_services = self.encounter_session.runtime_services
        if runtime_services is None:
            raise EncounterValidationError('The session runtime services are not configured for player recompilation.')
        old_actor = actor
        new_actor = runtime_services.monster_runtime.compile_player(record=committed_record, actor_id=actor_id, position=old_actor.position)
        dynamic_fields = (
            'name',
            'summon_owner_actor_id',
            'mounted_on_actor_id',
            'initiative_roll',
            'initiative_total',
            'damage_immunities',
            'damage_resistances',
            'condition_immunities',
            'ability_check_advantage_abilities',
            'ability_check_disadvantage_abilities',
            'saving_throw_advantage_abilities',
            'melee_attack_damage_bonus',
            'cannot_cast_spells',
            'cannot_take_reactions',
            'can_dash_as_bonus_action',
            'understand_all_languages',
            'can_communicate_with_beasts',
            'identified_item_ids',
            'purified_item_ids',
            'fall_speed_override_ft',
            'prevent_falling_damage',
            'speed_override_ft',
            'speed_bonus_ft',
            'jump_replacement_distance_ft',
            'jump_replacement_movement_cost_ft',
            'action_available',
            'bonus_action_available',
            'reaction_available',
            'remaining_free_object_interaction',
            'dodge_active',
            'disengage_active',
            'hidden',
            'surprised',
            'stealth_check_total',
            'hidden_from_actor_ids',
            'help_target_id',
            'readied_action',
            'temp_hit_points',
            'armor_class_modifier',
            'spell_casts_this_turn',
            'concentrating_effect_id',
            'body_weight_lb',
            'main_hand_item_id',
            'off_hand_item_id',
            'equipped_armor_item_id',
            'held_item_ids',
            'worn_armor_item_id',
            'worn_shield_item_id',
            'loading_spent_resources',
            'can_see_invisible',
            'support_state',
            'condition_instances',
            'story_npc_id',
            'story_combat_goal',
            'story_attitude',
            'story_stance',
            'story_faction_tags',
            'story_authority_tags',
            'story_synthesized_source',
            'story_fallback_archetype',
            'story_context',
            'shared_sense_owner_actor_id',
            'shared_senses_actor_id',
            'story_goal',
            'story_context_tags',
            'fallback_synthesized',
            'zero_hit_points_behavior',
            'dying_state',
            'rest_state',
            'last_long_rest_completed_at_seconds',
            'friends_targeted_at_seconds',
            'last_sneak_attack_round_number',
            'last_sneak_attack_turn_actor_id',
        )
        for field_name in dynamic_fields:
            setattr(new_actor, field_name, getattr(old_actor, field_name))
        new_actor.carried_item_counts = dict(old_actor.carried_item_counts)
        old_max_speed = old_actor.max_path_speed_ft
        refresh_actor_equipment_state(
            new_actor,
            runtime_services.character_catalog.items,
            unarmed_attack=new_actor.attacks.get('unarmed-strike'),
            active_effects=self.state.active_effects,
        )
        new_actor.current_hit_points = min(new_actor.max_hit_points, old_actor.current_hit_points + gained_hit_points)
        if old_actor.current_hit_points == 0 and new_actor.current_hit_points > 0 and old_actor.dying_state.status != DyingStateStatus.DEAD:
            new_actor.dying_state = DyingState()
        speed_delta = max(0, new_actor.max_path_speed_ft - old_max_speed)
        new_actor.movement_spent_ft = old_actor.movement_spent_ft
        new_actor.remaining_movement_ft = min(new_actor.max_path_speed_ft, old_actor.remaining_movement_ft + speed_delta)
        spent_hit_dice = max(0, old_actor.total_hit_dice - old_actor.remaining_hit_dice)
        new_actor.remaining_hit_dice = max(0, min(new_actor.total_hit_dice, new_actor.total_hit_dice - spent_hit_dice))
        for resource_id, pool in new_actor.resource_pools.items():
            old_pool = old_actor.resource_pools.get(resource_id)
            if old_pool is None:
                continue
            spent_amount = max(0, old_pool.maximum - old_pool.current)
            pool.current = max(0, min(pool.maximum, pool.maximum - spent_amount))
        updated_spells: dict[str, RuntimeSpellState] = {}
        for spell_id, spell in new_actor.spells.items():
            old_spell = old_actor.spells.get(spell_id)
            if old_spell is None or old_spell.max_uses is None or spell.max_uses is None:
                updated_spells[spell_id] = spell
                continue
            old_remaining = old_spell.remaining_uses if old_spell.remaining_uses is not None else old_spell.max_uses
            spent_uses = max(0, old_spell.max_uses - old_remaining)
            updated_spells[spell_id] = replace(
                spell,
                remaining_uses=max(0, min(spell.max_uses, spell.max_uses - spent_uses)),
            )
        new_actor.spells = updated_spells
        new_actor.base_armor_class = new_actor.armor_class
        new_actor.base_initiative_bonus = new_actor.initiative_bonus
        new_actor.base_passive_perception = new_actor.passive_perception
        new_actor.base_ability_scores = dict(new_actor.ability_scores)
        new_actor.base_ability_modifiers = dict(new_actor.ability_modifiers)
        new_actor.base_saving_throw_bonuses = dict(new_actor.saving_throw_bonuses)
        new_actor.base_skill_bonuses = dict(new_actor.skill_bonuses)
        self.state.actors[actor_id] = new_actor

    def _execute_levelup_command(self, controller_id: str, command: str):
        self.encounter_session.control_runtime.validate_controller(controller_id)
        tokens = command.strip().split()
        self._sync_progression_state()
        if len(tokens) == 1 or tokens[1].lower() == 'status':
            return self.view_for_controller(controller_id)
        subcommand = tokens[1].lower()
        if subcommand == 'start':
            actor_id, next_index = self._parse_levelup_actor(controller_id, tokens, index=2)
            if next_index != len(tokens):
                raise EncounterValidationError('Usage: /levelup start [actor-id]')
            pending = self._pending_level_up_for_actor(actor_id)
            if pending is None:
                raise EncounterValidationError('That actor does not have a pending level-up to start.')
            record = self._live_character_record(actor_id)
            updated_state, transaction, events = self.advancement_engine.start_transaction(
                self.story_state.advancement_state,
                actor_id=actor_id,
                actor_label=self.state.actors[actor_id].name,
                record=record,
                pending_record=pending,
                timestamp_seconds=self.state.clock_seconds,
                catalog=self.encounter_session.runtime_services.character_catalog,
            )
            self.story_state.advancement_state = updated_state
            self._apply_runtime_event(LevelUpAvailableEvent(pending_id=pending.pending_id, actor_id=actor_id, target_total_level=pending.target_new_total_level))
            for event in events:
                self._apply_runtime_event(event)
            self._refresh_pending_level_up_block_state(actor_id)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if subcommand == 'class':
            actor_id, next_index = self._parse_levelup_actor(controller_id, tokens, index=2)
            if len(tokens) != next_index + 1:
                raise EncounterValidationError('Usage: /levelup class [actor-id] <class-id>')
            class_id = tokens[next_index]
            if actor_id not in self.story_state.advancement_state.actor_transaction_ids:
                pending = self._pending_level_up_for_actor(actor_id)
                if pending is None:
                    raise EncounterValidationError('That actor does not have a pending level-up to start.')
                record = self._live_character_record(actor_id)
                updated_state, _transaction, events = self.advancement_engine.start_transaction(
                    self.story_state.advancement_state,
                    actor_id=actor_id,
                    actor_label=self.state.actors[actor_id].name,
                    record=record,
                    pending_record=pending,
                    timestamp_seconds=self.state.clock_seconds,
                    catalog=self.encounter_session.runtime_services.character_catalog,
                )
                self.story_state.advancement_state = updated_state
                self._apply_runtime_event(LevelUpAvailableEvent(pending_id=pending.pending_id, actor_id=actor_id, target_total_level=pending.target_new_total_level))
                for event in events:
                    self._apply_runtime_event(event)
            updated_state, _transaction, events = self.advancement_engine.choose_class(
                self.story_state.advancement_state,
                transaction_id=self.story_state.advancement_state.actor_transaction_ids[actor_id],
                chosen_class_id=class_id,
                record=self._live_character_record(actor_id),
                catalog=self.encounter_session.runtime_services.character_catalog,
            )
            self.story_state.advancement_state = updated_state
            for event in events:
                self._apply_runtime_event(event)
            self._refresh_pending_level_up_block_state(actor_id)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if subcommand == 'choose':
            actor_id, next_index = self._parse_levelup_actor(controller_id, tokens, index=2)
            if len(tokens) <= next_index + 1:
                raise EncounterValidationError('Usage: /levelup choose [actor-id] <choice-id> <option-id> [option-id ...]')
            choice_id = tokens[next_index]
            option_ids = tuple(tokens[next_index + 1:])
            updated_state, _transaction, events = self.advancement_engine.resolve_choice(
                self.story_state.advancement_state,
                actor_id=actor_id,
                choice_id=choice_id,
                option_ids=option_ids,
            )
            self.story_state.advancement_state = updated_state
            for event in events:
                self._apply_runtime_event(event)
            self._refresh_pending_level_up_block_state(actor_id)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if subcommand == 'apply':
            actor_id, next_index = self._parse_levelup_actor(controller_id, tokens, index=2)
            if next_index != len(tokens):
                raise EncounterValidationError('Usage: /levelup apply [actor-id]')
            if self.story_state.runtime_mode == RuntimeMode.COMBAT and not self.story_state.advancement_state.policy.allow_apply_in_combat:
                raise EncounterValidationError('The active advancement policy blocks applying level-ups during combat.')
            record = self._live_character_record(actor_id)
            try:
                updated_state, committed_record, transaction, events, next_random_counter = self.advancement_engine.commit_transaction(
                    self.story_state.advancement_state,
                    actor_id=actor_id,
                    record=record,
                    species_hit_point_bonus_per_level=self._species_hit_point_bonus_for_actor(actor_id),
                    catalog=self.encounter_session.runtime_services.character_catalog,
                    random_counter=self.state.random_counter,
                    seed=self.encounter_session.control_runtime.kernel.seed,
                )
                self._apply_committed_character_record(actor_id, committed_record, gained_hit_points=(transaction.hp_gain.total_gained if transaction.hp_gain is not None else 0))
            except Exception as exc:
                open_transaction_id = self.story_state.advancement_state.actor_transaction_ids.get(actor_id)
                if open_transaction_id is not None:
                    self._apply_runtime_event(AdvancementCommitFailedEvent(transaction_id=open_transaction_id, actor_id=actor_id, status=AdvancementCommitStatus.FAILED, reason=str(exc)))
                raise
            self.story_state.advancement_state = updated_state
            self.state.random_counter = next_random_counter
            for event in events:
                self._apply_runtime_event(event)
            progression_state, progression_events = self.progression_engine.mark_pending_level_up_applied(
                self.story_state.progression_state,
                pending_id=transaction.source_pending_level_up_id,
                actor_snapshots=self._progression_actor_snapshots(),
            )
            self.story_state.progression_state = progression_state
            for event in progression_events:
                self._apply_runtime_event(event)
            self._append_transcript((
                StoryTranscriptEntry(
                    speaker='System',
                    text=f'{self.state.actors[actor_id].name} advances to level {committed_record.level} as {transaction.chosen_class_id}.',
                    visibility=StoryTranscriptVisibility.PUBLIC,
                ),
            ))
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if subcommand == 'cancel':
            actor_id, next_index = self._parse_levelup_actor(controller_id, tokens, index=2)
            if next_index != len(tokens):
                raise EncounterValidationError('Usage: /levelup cancel [actor-id]')
            if actor_id not in self.story_state.advancement_state.actor_transaction_ids:
                raise EncounterValidationError('That actor does not have an open advancement transaction.')
            self.story_state.advancement_state = self.advancement_engine.cancel_transaction(self.story_state.advancement_state, actor_id=actor_id)
            self._refresh_pending_level_up_block_state(actor_id)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        raise EncounterValidationError('Usage: /levelup <status|start|class|choose|apply|cancel> ...')

    def _available_story_combatant_actor_ids(self) -> tuple[str, ...]:
        return tuple(self.state.actors.keys())

    def _visible_actor_summaries(self) -> tuple[str, ...]:
        summaries: list[str] = []
        for actor in self.state.actors.values():
            parts = [f'{actor.actor_id}: {actor.name} [{actor.side.value}]']
            if actor.current_hit_points > 0:
                parts.append(f'HP {actor.current_hit_points}/{actor.max_hit_points}')
            parts.append(f'Pos ({actor.position.x},{actor.position.y},{actor.position.z})')
            if self.story_state.runtime_mode == RuntimeMode.COMBAT:
                parts.append(f'Action {"yes" if actor.action_available else "no"}')
                parts.append(f'Bonus {"yes" if actor.bonus_action_available else "no"}')
                parts.append(f'Reaction {"yes" if actor.reaction_available else "no"}')
            summaries.append('; '.join(parts))
        return tuple(summaries)

    def _nearby_feature_summaries(self, actor_id: str) -> tuple[str, ...]:
        actor = self.state.actors.get(actor_id)
        battlefield = self.state.battlefield
        if actor is None or not battlefield.has_authored_map:
            return ()
        summaries: list[str] = []
        for feature in battlefield.features.values():
            if not feature.cells:
                continue
            distance = min(max(abs(cell.x - actor.position.x), abs(cell.y - actor.position.y)) for cell in feature.cells)
            if distance > 2:
                continue
            tags = ', '.join(feature.tags[:3]) if feature.tags else 'no-tags'
            anchor = feature.cells[0]
            summaries.append(f'{feature.feature_id}: {feature.feature_type} at ({anchor.x},{anchor.y},{anchor.z}); tags {tags}')
        return tuple(summaries[:8])

    def _action_economy_summary(self, actor_id: str) -> str:
        actor = self.state.actors.get(actor_id)
        if actor is None:
            return ''
        if self.story_state.runtime_mode != RuntimeMode.COMBAT:
            return 'No initiative or combat action economy is active.'
        return (
            f'Remaining movement {actor.remaining_movement_ft} ft; '
            f'action {"available" if actor.action_available else "spent"}; '
            f'bonus action {"available" if actor.bonus_action_available else "spent"}; '
            f'reaction {"available" if actor.reaction_available else "spent"}; '
            f'free object interaction {"available" if actor.remaining_free_object_interaction else "spent"}.'
        )

    def _build_adjudication_context(self, *, controller_id: str, actor_id: str, declaration: str) -> AdjudicationContext:
        actor = self.state.actors[actor_id]
        battlefield = self.state.battlefield
        tile_summary = ''
        if battlefield.has_authored_map:
            tile = battlefield.tiles.get(GridPosition(actor.position.x, actor.position.y))
            if tile is not None:
                tile_summary = f'Current tile {tile.terrain_id} at {tile.elevation_ft} ft.'
        language_tags: list[str] = []
        if actor.understand_all_languages:
            language_tags.append('understands all languages')
        if actor.can_communicate_with_beasts:
            language_tags.append('can communicate with beasts')
        tag_summary = ('; ' + ', '.join(language_tags)) if language_tags else ''
        actor_status_summary = (
            f'{actor.actor_id}: {actor.name} [{actor.side.value}] HP {actor.current_hit_points}/{actor.max_hit_points}; '
            f'AC {actor.effective_armor_class}; Pos ({actor.position.x},{actor.position.y},{actor.position.z}){tag_summary}; {tile_summary}'.strip()
        )
        return AdjudicationContext(
            campaign_id=self.story_state.campaign_id,
            runtime_mode=self.story_state.runtime_mode.value,
            controller_id=controller_id,
            actor_id=actor_id,
            declaration=declaration,
            current_scene_id=self.story_state.current_scene_id,
            current_location_id=self.story_state.canonical_location_id,
            active_actor_id=self.state.active_actor_id,
            party_goal_summary='; '.join(self.story_state.current_party_goals),
            recent_summary=self.story_state.recent_summary,
            unresolved_hooks=self.story_state.open_loops,
            visible_actor_summaries=self._visible_actor_summaries(),
            nearby_feature_summaries=self._nearby_feature_summaries(actor_id),
            actor_status_summary=actor_status_summary,
            action_economy_summary=self._action_economy_summary(actor_id),
            allowed_template_ids=list_template_ids(),
            allowed_illusion_template_ids=tuple(template.value for template in IllusionTemplateId),
            allowed_operation_types=self.adjudication_runtime.allowed_operation_types(),
        )

    def _emit_llm_feedback(self, controller_id: str, kind: str, text: str) -> None:
        sink = self.llm_feedback_sink
        if sink is None or not text.strip():
            return
        sink(controller_id, kind, text)

    def _story_llm_stream_handler(self, acting_controller_id: str):
        buffer: list[str] = []

        def flush() -> None:
            if not buffer:
                return
            self._emit_llm_feedback('dm', 'thinking', ''.join(buffer))
            buffer.clear()

        def _handle(event) -> None:
            if getattr(event, 'kind', None) != 'reasoning':
                return
            text = getattr(event, 'text', '')
            if not text:
                return
            buffer.append(text)
            current = ''.join(buffer)
            if '\n' in text or len(current) >= 160:


                flush()

        _handle.flush = flush
        return _handle

    def _story_llm_retry_handler(self, acting_controller_id: str, *, request_label: str):
        def _handle(attempt_number: int, max_attempts: int, error_message: str) -> None:
            message = (
                f'{request_label} returned invalid structured output; retrying '
                f'{attempt_number}/{max_attempts}. Error: {error_message}'
            )
            self._emit_llm_feedback('dm', 'info', message)
            if acting_controller_id != 'dm':
                self._emit_llm_feedback(acting_controller_id, 'info', message)

        return _handle

    def _owned_actor_for_controller(self, controller_id: str) -> str:
        actor_ids = [actor_id for actor_id in self.state.actors if self.encounter_session.control_runtime.actor_controllers.get(actor_id) == controller_id]
        if not actor_ids:
            raise EncounterPermissionError(f'Controller {controller_id!r} does not own an actor in this session.')
        if len(actor_ids) > 1:
            actor_ids.sort()
            return actor_ids[0]
        return actor_ids[0]

    def _normalized_pending_check(self) -> StoryCheckRequestState | None:
        pending = self.story_state.pending_check
        if pending is None:
            return None
        try:
            controller_id = self.encounter_session.control_runtime.controller_for_actor(pending.actor_id)
        except EncounterOwnershipError:
            return pending
        if pending.controller_id != controller_id:
            pending = replace(pending, controller_id=controller_id)
            self.story_state.pending_check = pending
        return pending

    def _pending_check_owner_label(self, pending: StoryCheckRequestState) -> str:
        controller_id = pending.controller_id
        if controller_id is not None:
            binding = self.encounter_session.control_runtime.controllers.get(controller_id)
            if binding is not None:
                return binding.label
        return self._format_actor_reference(pending.actor_id)

    def _pending_check_waiting_message(self, pending: StoryCheckRequestState) -> str:
        return f'Storytelling is waiting on {self._pending_check_owner_label(pending)} to resolve a pending story check.'

    def _exploration_summary_lines(self, controller_id: str, *, dm_view: bool) -> list[str]:
        state = self.story_state.exploration_state
        engine = self.exploration_engine
        if state is None or engine is None:
            return []
        lines = [f'Exploration mode: {state.mode.value}']
        if state.marching_order:
            ordered = ' -> '.join(
                f"{self._format_actor_reference(entry.actor_id)} ({entry.position.value})"
                for entry in sorted(state.marching_order, key=lambda item: item.ordinal)
            )
            lines.append(f'Marching order: {ordered}')
        roles = []
        if state.role_assignments.navigator_actor_id:
            roles.append(f'Navigator {self._format_actor_reference(state.role_assignments.navigator_actor_id)}')
        if state.role_assignments.scout_actor_id:
            roles.append(f'Scout {self._format_actor_reference(state.role_assignments.scout_actor_id)}')
        if state.role_assignments.lookout_actor_ids:
            roles.append('Lookout ' + ', '.join(self._format_actor_reference(actor_id) for actor_id in state.role_assignments.lookout_actor_ids))
        if state.role_assignments.searching_actor_ids:
            roles.append('Searching ' + ', '.join(self._format_actor_reference(actor_id) for actor_id in state.role_assignments.searching_actor_ids))
        if state.role_assignments.studying_actor_ids:
            roles.append('Studying ' + ', '.join(self._format_actor_reference(actor_id) for actor_id in state.role_assignments.studying_actor_ids))
        if state.role_assignments.sneaking_actor_ids:
            roles.append('Sneaking ' + ', '.join(self._format_actor_reference(actor_id) for actor_id in state.role_assignments.sneaking_actor_ids))
        if roles:
            lines.append('Roles: ' + '; '.join(roles))
        if state.watch_order:
            watch_text = '; '.join(
                f"shift {assignment.shift_index}: {self._format_actor_reference(assignment.actor_id)}"
                for assignment in state.watch_order
            )
            lines.append(f'Watch order: {watch_text}')
        active_shift = engine.active_watch_shift_index(state, encounter_state=self.state)
        active_watchers = engine.active_watchers(state, encounter_state=self.state)
        if active_shift is not None:
            watcher_text = ', '.join(self._format_actor_reference(actor_id) for actor_id in active_watchers) or 'none'
            lines.append(f'Active watch: shift {active_shift}; awake {watcher_text}')
        if state.known_discoveries:
            lines.append('Known discoveries: ' + '; '.join(state.known_discoveries[-4:]))
        visible_npcs = engine.visible_npc_states(state)
        if visible_npcs:
            lines.append('NPC stances:')
            for npc_state in visible_npcs[:4]:
                lines.append(f'  - {npc_state.display_name}: {npc_state.attitude.value}; {npc_state.current_stance}')
        visible_traps = engine.visible_trap_states(state, dm_view=dm_view)
        if visible_traps:
            lines.append('Traps:')
            for definition, runtime in visible_traps[:4]:
                summary = runtime.last_summary or (definition.revealed_summary if runtime.visible_to_party or dm_view else definition.hidden_summary)
                lines.append(f'  - {definition.title}: {runtime.status.value}; {summary}')
        visible_puzzles = engine.visible_puzzle_states(state, dm_view=dm_view)
        if visible_puzzles:
            lines.append('Puzzles:')
            for definition, runtime in visible_puzzles[:4]:
                summary = runtime.last_summary or definition.summary
                lines.append(f'  - {definition.title}: {runtime.status.value}; {summary}')
        owned_actor_ids: tuple[str, ...]
        if dm_view:
            owned_actor_ids = self._player_actor_ids()
        else:
            try:
                owned_actor_ids = (self._owned_actor_for_controller(controller_id),)
            except EncounterPermissionError:
                owned_actor_ids = ()
        projects = engine.visible_downtime_projects(state, actor_ids=owned_actor_ids, dm_view=dm_view)
        if projects:
            lines.append('Downtime projects:')
            for project in projects[:4]:
                status_text = project.status.value
                summary = project.last_summary or project.title
                lines.append(f'  - {project.title}: {status_text}; {summary}')
        activities = engine.available_downtime_activities(state)
        if activities:
            lines.append('Available downtime: ' + '; '.join(activity.title for activity in activities[:4]))
        return lines

    def _downtime_help_view(self, controller_id: str) -> StoryControllerView:
        view = self.view_for_controller(controller_id)
        state = self.story_state.exploration_state
        if state is None or self.exploration_engine is None:
            return view
        lines = list(view.summary_lines)
        lines.append('Downtime help:')
        lines.append('  - /downtime start <activity-id> [actor-id]')
        lines.append('  - /downtime work <project-id> <hours> [actor-id] [tool=<tool-name>]')
        lines.append('  - /downtime cancel <project-id>')
        activities = self.exploration_engine.available_downtime_activities(state)
        if activities:
            lines.append('Available activities:')
            for activity in activities[:6]:
                lines.append(f'  - {activity.activity_id}: {activity.title} - {activity.summary}')
        return StoryControllerView(summary_lines=tuple(lines), available_choices=view.available_choices)

    def _open_exploration_pending_check(self, controller_id: str, prompt) -> None:
        request_id = f'exploration-check:{prompt.pending_state.kind.value}:{prompt.pending_state.actor_id}:{len(self.state.event_log)}'
        pending = StoryCheckRequestState(
            request_id=request_id,
            actor_id=prompt.pending_state.actor_id,
            prompt=prompt.prompt,
            reason=prompt.reason,
            controller_id=controller_id,
            check_request=CheckRequest(
                context=ResolutionContext(
                    effect_id=request_id,
                    source_actor_id=prompt.pending_state.actor_id,
                    target_actor_id=prompt.pending_state.actor_id,
                    reason=prompt.reason,
                ),
                ability=prompt.ability,
                dc=prompt.dc,
                skill_name=prompt.skill_name,
                interacting_with_actor_id=prompt.interacting_with_actor_id,
            ),
        )
        self.story_state.pending_check = pending
        self.story_state.pending_exploration_check = prompt.pending_state
        self.story_state.pending_adjudication = None
        self.state.event_log.append(StoryCheckPromptedEvent(request=pending))

    def view_for_controller(self, controller_id: str) -> StoryControllerView:
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        self.encounter_session.control_runtime.validate_actor_bindings(self.state)
        self._sync_progression_state()
        dm_view = binding.role.value == 'dm'
        advancement_choices = self._advancement_available_choices(controller_id, dm_view=dm_view)
        summary_lines = [
            f'Runtime mode: {self.story_state.runtime_mode.value}',
            f'Campaign: {self.story_state.campaign_id}',
            f'Current scene: {self.story_state.current_scene_id}',
        ]
        if self.story_state.canonical_location_id is not None:
            summary_lines.append(f'Location: {self.story_state.canonical_location_id}')
        if self.story_state.current_party_goals:
            summary_lines.append('Party goals: ' + '; '.join(self.story_state.current_party_goals))
        if self.story_state.open_loops:
            summary_lines.append('Open loops: ' + '; '.join(self.story_state.open_loops[:4]))
        travel_state = self.story_state.travel_state
        if travel_state is not None:
            summary_lines.append(f'Travel map: {travel_state.map_id}')
            summary_lines.append(f'Travel hex: ({travel_state.party_coord.q},{travel_state.party_coord.r})')
            summary_lines.append(f'Travel status: {travel_state.status.value}')
            if travel_state.planned_route is not None:
                summary_lines.append(
                    f'Travel route: {travel_state.planned_route.destination_label}; {travel_state.planned_route.estimated_minutes} minutes at current pace.'
                )
            if travel_state.pending_hook is not None:
                summary_lines.append(f'Travel interruption: {travel_state.pending_hook.summary}.')
        progression_lines = self._progression_visible_lines(dm_view=dm_view)
        if progression_lines:
            summary_lines.append('Progression:')
            summary_lines.extend(progression_lines)
        advancement_lines = self._advancement_visible_lines(controller_id, dm_view=dm_view)
        if advancement_lines:
            summary_lines.append('Advancement:')
            summary_lines.extend(advancement_lines)
        transition_lines = self._transition_summary_lines(controller_id, dm_view=dm_view)
        if transition_lines:
            summary_lines.extend(transition_lines)
        if self.story_state.runtime_mode == RuntimeMode.COMBAT:
            encounter_view = self.encounter_session.view_for_controller(controller_id)
            summary_lines.extend(encounter_view.summary_lines)
            available_choices = dict(encounter_view.available_choices)
            available_choices.update(advancement_choices)
            return StoryControllerView(summary_lines=tuple(summary_lines), available_choices=available_choices)
        exploration_lines = self._exploration_summary_lines(controller_id, dm_view=dm_view)
        if exploration_lines:
            summary_lines.extend(exploration_lines)
        social_lines = self._social_visible_lines(dm_view=dm_view)
        if social_lines:
            summary_lines.extend(social_lines)
        pending = self._normalized_pending_check()
        if pending is not None:
            pending_label = 'you' if pending.controller_id == controller_id else self._pending_check_owner_label(pending)
            summary_lines.append(f'Story check pending: waiting on {pending_label}.')
        check_result_lines = self._recent_story_check_result_lines(controller_id, binding.role.value)
        if check_result_lines:
            summary_lines.extend(check_result_lines)
        visible_entries: list[StoryTranscriptEntry] = []
        for entry in self.story_state.transcript_entries[-12:]:
            if entry.visibility == StoryTranscriptVisibility.PUBLIC:
                visible_entries.append(entry)
                continue
            if entry.visibility == StoryTranscriptVisibility.DM_ONLY:
                if dm_view:
                    visible_entries.append(entry)
                continue
            if dm_view or controller_id in entry.controller_ids:
                visible_entries.append(entry)
        if visible_entries:
            summary_lines.append('Story log:')
            for entry in visible_entries[-8:]:
                summary_lines.append(f'{entry.speaker}: {entry.text}')
        return StoryControllerView(summary_lines=tuple(summary_lines), available_choices=advancement_choices)

    def prompt_for_controller(self, controller_id: str):
        if self.story_state.runtime_mode == RuntimeMode.STORYTELLING:
            pending = self._normalized_pending_check()
            if pending is None or pending.controller_id != controller_id:
                return None
            prompt_text = self._format_story_check_prompt(pending)
            return StoryPrompt(
                prompt_id=pending.request_id,
                prompt_kind='story-check',
                controller_id=controller_id,
                prompt=prompt_text,
            )
        return self.encounter_session.prompt_for_controller(controller_id)

    def _format_story_check_prompt(self, pending: StoryCheckRequestState) -> str:
        lines = [pending.prompt.strip()]
        check_label = self._format_check_label(pending.check_request)
        if check_label and check_label.lower() not in pending.prompt.strip().lower():
            lines.append(f'Required check: {check_label}.')
        lines.append(f'DC: {pending.check_request.dc}.')
        opposed_label = self._format_check_opposition_label(pending.check_request.interacting_with_actor_id)
        if opposed_label is not None:
            lines.append(f'Competition / opposed interaction: {opposed_label}.')
        return '\n'.join(line for line in lines if line)


    def _format_check_opposition_label(self, actor_id: str | None) -> str | None:
        if actor_id is None:
            return None
        actor = self.state.actors.get(actor_id)
        if actor is not None:
            return actor.name
        pretty = actor_id.replace('-', ' ').replace('_', ' ').strip()
        if not pretty:
            return None
        return pretty.title()

    def _format_check_label(self, request) -> str:
        ability_names = {
            'STR': 'Strength',
            'DEX': 'Dexterity',
            'CON': 'Constitution',
            'INT': 'Intelligence',
            'WIS': 'Wisdom',
            'CHA': 'Charisma',
        }
        ability_value = getattr(request.ability, 'value', str(request.ability))
        ability_label = ability_names.get(ability_value, ability_value)
        skill_name = getattr(request, 'skill_name', None)
        if skill_name:
            return f'{ability_label} ({skill_name})'
        return ability_label


    def _actors_with_resolved_story_checks_in_scene(self) -> tuple[str, ...]:
        actor_ids: list[str] = []
        seen: set[str] = set()
        for event in self.state.event_log:
            if not isinstance(event, StoryCheckResolvedEvent):
                continue
            if event.scene_id != self.story_state.current_scene_id:
                continue
            if event.actor_id in seen:
                continue
            actor_ids.append(event.actor_id)
            seen.add(event.actor_id)
        return tuple(actor_ids)

    def _recent_story_check_result_lines(self, controller_id: str, role_value: str) -> list[str]:
        owned_actor_id = None
        try:
            owned_actor_id = self._owned_actor_for_controller(controller_id)
        except EncounterPermissionError:
            owned_actor_id = None
        recent_events = [event for event in self.state.event_log[-20:] if isinstance(event, StoryCheckResolvedEvent)]
        visible_events: list[StoryCheckResolvedEvent] = []
        for event in recent_events:
            if role_value == 'dm' or event.actor_id == owned_actor_id:
                visible_events.append(event)
        if not visible_events:
            return []
        lines = ['Recent check results:']
        for event in visible_events[-3:]:
            check_label = self._format_check_result_label(event)
            actor_label = self._format_actor_reference(event.actor_id)
            outcome = 'success' if event.success else 'failure'
            lines.append(
                f'  - {actor_label}: {check_label}, die {event.selected_roll}, total {event.total} vs DC {event.dc} ({outcome}).'
            )
            opposed = self._format_check_opposition_label(event.interacting_with_actor_id)
            if opposed is not None:
                lines.append(f'    Competition / opposed interaction: {opposed}.')
        return lines

    def _format_check_result_label(self, event: StoryCheckResolvedEvent) -> str:
        class _EventCheck:
            def __init__(self, *, ability, skill_name):
                self.ability = ability
                self.skill_name = skill_name
        return self._format_check_label(_EventCheck(ability=event.ability, skill_name=event.skill_name))

    def _format_actor_reference(self, actor_id: str) -> str:
        actor = self.state.actors.get(actor_id)
        if actor is not None:
            return actor.name
        pretty = actor_id.replace('-', ' ').replace('_', ' ').strip()
        if not pretty:
            return actor_id
        return pretty.title()

    def _to_runtime_document(self, document) -> CampaignDocument:
        return CampaignDocument(
            doc_id=document.front_matter.id,
            path=document.path.resolve().relative_to(self.campaign_root).as_posix(),
            title=document.front_matter.title,
            type=document.front_matter.type.value,
            campaign=document.front_matter.campaign,
            content=document.body,
            tags=document.front_matter.tags,
            visibility=document.front_matter.visibility.value,
            canonical_location=document.front_matter.canonical_location,
            involved_npcs=document.front_matter.involved_npcs,
            related_files=document.front_matter.related_files,
            retrieval_keywords=document.front_matter.retrieval_keywords,
            token_budget_hint=document.front_matter.token_budget_hint.value,
        )

    def _promoted_linked_scene_documents(self) -> tuple[CampaignDocument, ...]:
        current_scene_doc = self.retrieval_index.by_id.get(self.story_state.current_scene_id)
        if current_scene_doc is None or current_scene_doc.front_matter.type.value != 'scene':
            return ()
        promoted: list[CampaignDocument] = []
        seen: set[str] = set()
        for link in current_scene_doc.links:
            try:
                relative_path = (current_scene_doc.path.parent / link).resolve().relative_to(self.campaign_root).as_posix()
            except ValueError:
                continue
            linked_doc = self.retrieval_index.by_path.get(relative_path)
            if linked_doc is None or linked_doc.front_matter.type.value != 'scene':
                continue
            if linked_doc.front_matter.id in seen or linked_doc.front_matter.id == self.story_state.current_scene_id:
                continue
            promoted.append(self._to_runtime_document(linked_doc))
            seen.add(linked_doc.front_matter.id)
        return tuple(promoted)

    def select_relevant_documents(self, *, max_results: int = 8) -> tuple[CampaignDocument, ...]:
        query = CampaignRetrievalQuery(
            campaign=self.story_state.campaign_id,
            chapter=self.story_state.current_chapter_id,
            scene_id=self.story_state.current_scene_id,
            location=self.story_state.canonical_location_id,
            npc_ids=self._visible_npc_ids(),
            tags=tuple(tag for tag in self.story_state.metadata.get('retrieval_tags', '').split(',') if tag),
            keywords=self.story_state.open_loops + self.story_state.current_party_goals,
            max_results=max_results,
            include_dm_memory=True,
        )
        result = self.retrieval_index.select_documents(query)
        selected = [self._to_runtime_document(document) for document in result.documents]
        promoted_scenes = self._promoted_linked_scene_documents()
        if not promoted_scenes:
            return tuple(selected)
        ordered: list[CampaignDocument] = []
        seen_ids: set[str] = set()
        inserted = False
        for document in selected:
            ordered.append(document)
            seen_ids.add(document.doc_id)
            if document.doc_id == self.story_state.current_scene_id and not inserted:
                for promoted in promoted_scenes:
                    if promoted.doc_id in seen_ids:
                        continue
                    ordered.append(promoted)
                    seen_ids.add(promoted.doc_id)
                inserted = True
        if not inserted:
            for promoted in promoted_scenes:
                if promoted.doc_id in seen_ids:
                    continue
                ordered.append(promoted)
                seen_ids.add(promoted.doc_id)
        return tuple(ordered[:max_results])

    def system_open_scene(self) -> None:
        if self.story_state.transcript_entries:
            return
        docs = self.select_relevant_documents(max_results=3)
        scene_doc = next((doc for doc in docs if doc.doc_id == self.story_state.current_scene_id), None)
        if scene_doc is None:
            return
        read_aloud = self._extract_markdown_section(scene_doc.content, 'Read Aloud')
        public_summary = self._extract_markdown_section(scene_doc.content, 'Public Summary')
        opening = read_aloud or public_summary
        if opening:
            self._append_transcript((StoryTranscriptEntry(speaker='DM', text=opening.strip(), visibility=StoryTranscriptVisibility.PUBLIC),))
            self.story_state.recent_summary = opening.strip()
            self._sync_memory_files()

    def run_dm_mode_planner(self, documents: tuple[CampaignDocument, ...] | None = None) -> ModeSwitchDecision:
        if self.dm_runtime is None:
            raise EncounterValidationError('No DM storytelling runtime is configured for this session.')
        selected = self.select_relevant_documents() if documents is None else documents
        decision, events = self.dm_runtime.decide_mode_switch(
            self.storytelling_context(),
            selected,
            current_mode=self.story_state.runtime_mode,
            retry_handler=self._story_llm_retry_handler('dm', request_label='DM mode-planner response'),
        )
        self.state.event_log.extend(events)
        return decision

    def handle_input(self, controller_id: str, raw_input: str):
        raw_input = raw_input.strip()
        if not raw_input:
            return self.view_for_controller(controller_id)
        if raw_input.startswith('/'):
            return self.execute_for_controller(controller_id, raw_input)
        if self.story_state.runtime_mode != RuntimeMode.STORYTELLING:
            raise EncounterPermissionError('Natural-language declarations are only supported in storytelling mode.')
        return self.submit_story_action(controller_id, raw_input)

    def execute_for_controller(self, controller_id: str, command: str):
        self.encounter_session.control_runtime.validate_controller(controller_id)
        tokens = command.strip().split(maxsplit=1)
        verb = tokens[0].lower()
        if verb == '/levelup':
            return self._execute_levelup_command(controller_id, command)
        if self.story_state.runtime_mode == RuntimeMode.COMBAT:
            if verb in {'/do', '/improvise'}:
                if len(tokens) < 2 or not tokens[1].strip():
                    raise EncounterPermissionError(f'{verb} requires text after the command.')
                return self.submit_improvised_action(controller_id, tokens[1].strip())
            self.encounter_session.execute_for_controller(controller_id, command)
            self._process_due_reinforcements()
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if verb in {'/status', '/view'}:
            return self.view_for_controller(controller_id)
        if verb == '/check':
            return self.resolve_pending_check(controller_id)
        if verb == '/travel':
            return self._execute_travel_command(controller_id, command)
        if verb == '/progression':
            return self._execute_progression_command(controller_id, command)
        if verb in {'/march', '/watch', '/role', '/camp', '/social', '/trap', '/puzzle', '/downtime'}:
            return self._execute_exploration_command(controller_id, command)
        if verb == '/cast':
            return self.cast_story_spell(controller_id, command)
        if verb in {'/shortrest', '/longrest', '/rest', '/hitdie', '/time'}:
            return self.encounter_session.execute_for_controller(controller_id, command).view
        if verb in {'/do', '/improvise'}:
            if len(tokens) < 2 or not tokens[1].strip():
                raise EncounterPermissionError(f'{verb} requires text after the command.')
            return self.submit_improvised_action(controller_id, tokens[1].strip())
        if verb in {'/say', '/story'}:
            if len(tokens) < 2 or not tokens[1].strip():
                raise EncounterPermissionError(f'{verb} requires text after the command.')
            return self.submit_story_action(controller_id, tokens[1].strip())
        raise EncounterPermissionError('Combat slash commands are only available after the DM runtime enters combat mode. Use plain text, `/say`, `/story`, `/do`, `/improvise`, or `/check` in storytelling mode.')

    def _tool_name_from_tokens(self, tokens: list[str]) -> str | None:
        for token in tokens:
            if token.lower().startswith('tool='):
                return token.split('=', 1)[1].replace('-', ' ').strip() or None
        return None

    def _optional_actor_token(self, controller_id: str, tokens: list[str], *, index: int) -> str | None:
        if len(tokens) <= index:
            return None
        token = tokens[index]
        if token.lower().startswith('tool='):
            return None
        if self._is_dm_controller(controller_id):
            return token
        owned = self._owned_actor_for_controller(controller_id)
        if token == owned:
            return token
        return None

    def _execute_exploration_command(self, controller_id: str, command: str):
        self.encounter_session.control_runtime.validate_controller(controller_id)
        if self.story_state.runtime_mode != RuntimeMode.STORYTELLING:
            raise EncounterPermissionError('Exploration procedures are only available in storytelling mode.')
        self._require_exploration_engine()
        tokens = command.strip().split()
        verb = tokens[0].lower()
        if verb == '/march':
            if len(tokens) == 1 or tokens[1].lower() == 'status':
                return self.view_for_controller(controller_id)
            if tokens[1].lower() != 'set' or len(tokens) < 3:
                raise EncounterValidationError('Usage: /march set <actor-id> <actor-id> ...')
            return self.set_marching_order(controller_id, tuple(tokens[2:]))
        if verb == '/watch':
            if len(tokens) == 1 or tokens[1].lower() == 'status':
                return self.view_for_controller(controller_id)
            if tokens[1].lower() != 'set' or len(tokens) < 3:
                raise EncounterValidationError('Usage: /watch set <actor-id> <actor-id> ...')
            return self.set_watch_order(controller_id, tuple(tokens[2:]))
        if verb == '/role':
            if len(tokens) == 1 or tokens[1].lower() == 'status':
                return self.view_for_controller(controller_id)
            if tokens[1].lower() != 'set' or len(tokens) < 3:
                raise EncounterValidationError('Usage: /role set <navigator|scout|lookout|search|study|sneak> [actor-id ...]')
            return self.assign_exploration_role(controller_id, ExplorationRole(tokens[2].lower()), tuple(tokens[3:]))
        if verb == '/camp':
            if len(tokens) == 1 or tokens[1].lower() == 'status':
                return self.view_for_controller(controller_id)
            if tokens[1].lower() == 'start':
                return self.set_camp_active(controller_id, True)
            if tokens[1].lower() == 'stop':
                return self.set_camp_active(controller_id, False)
            raise EncounterValidationError('Usage: /camp <status|start|stop>')
        if verb in {'/social', '/trap', '/puzzle'}:
            raise EncounterValidationError('Use normal storytelling declarations for social, trap, and puzzle interaction. The backend will prompt any required check.')
        if verb == '/downtime':
            if len(tokens) == 1 or tokens[1].lower() == 'status':
                return self.view_for_controller(controller_id)
            subcommand = tokens[1].lower()
            if subcommand == 'help':
                return self._downtime_help_view(controller_id)
            if subcommand == 'start':
                if len(tokens) < 3:
                    raise EncounterValidationError('Usage: /downtime start <activity-id> [actor-id]')
                actor_id = self._resolve_exploration_actor_id(controller_id, self._optional_actor_token(controller_id, tokens, index=3))
                return self.start_downtime_project(controller_id, actor_id=actor_id, activity_id=tokens[2])
            if subcommand == 'work':
                if len(tokens) < 4:
                    raise EncounterValidationError('Usage: /downtime work <project-id> <hours> [actor-id] [tool=<tool-name>]')
                try:
                    hours = int(tokens[3])
                except ValueError as exc:
                    raise EncounterValidationError('Downtime work hours must be an integer.') from exc
                actor_id = self._resolve_exploration_actor_id(controller_id, self._optional_actor_token(controller_id, tokens, index=4))
                return self.work_downtime_project(controller_id, actor_id=actor_id, project_id=tokens[2], hours=hours, tool_name=self._tool_name_from_tokens(tokens[4:]))
            if subcommand == 'cancel':
                if len(tokens) != 3:
                    raise EncounterValidationError('Usage: /downtime cancel <project-id>')
                return self.cancel_downtime_project(controller_id, project_id=tokens[2])
            raise EncounterValidationError('Usage: /downtime <status|help|start|work|cancel> ...')
        raise EncounterValidationError('Unknown exploration command.')

    def _execute_progression_command(self, controller_id: str, command: str):
        tokens = command.strip().split()
        self._sync_progression_state()
        if len(tokens) == 1 or tokens[1].lower() == 'status':
            return self.view_for_controller(controller_id)
        if not self._is_dm_controller(controller_id):
            raise EncounterPermissionError('Only the DM controller may change progression mode, policy, or awards.')
        subcommand = tokens[1].lower()
        if subcommand == 'mode':
            if len(tokens) != 3:
                raise EncounterValidationError('Usage: /progression mode <xp|milestone>')
            return self.set_progression_mode(controller_id, ProgressionMode(tokens[2].lower()))
        if subcommand == 'policy':
            if len(tokens) != 4:
                raise EncounterValidationError('Usage: /progression policy <xp|milestone> <party-wide|equal-share|individual|subset>')
            category = tokens[2].lower()
            option = tokens[3].lower()
            current = self.story_state.progression_state.policy
            if category == 'xp':
                mapping = {
                    'party-wide': XPDistributionPolicy.PARTY_WIDE,
                    'equal-share': XPDistributionPolicy.EQUAL_SHARE,
                    'individual': XPDistributionPolicy.INDIVIDUAL,
                }
                if option not in mapping:
                    raise EncounterValidationError('XP progression policy must be party-wide, equal-share, or individual.')
                policy = replace(current, xp_distribution=mapping[option])
                return self.set_progression_policy(controller_id, policy)
            if category == 'milestone':
                mapping = {
                    'party-wide': MilestoneDistributionPolicy.PARTY_WIDE,
                    'subset': MilestoneDistributionPolicy.SUBSET,
                }
                if option not in mapping:
                    raise EncounterValidationError('Milestone progression policy must be party-wide or subset.')
                policy = replace(current, milestone_distribution=mapping[option])
                return self.set_progression_policy(controller_id, policy)
            raise EncounterValidationError('Progression policy category must be xp or milestone.')
        if subcommand == 'xp':
            if len(tokens) < 7 or tokens[2].lower() != 'award':
                raise EncounterValidationError('Usage: /progression xp award <party|actor:id|actors:id,id> <amount> <source-type> <source-id> [reason ...]')
            recipient_scope, recipient_actor_ids = self._parse_progression_recipient_spec(tokens[3])
            try:
                amount = int(tokens[4])
            except ValueError as exc:
                raise EncounterValidationError('Progression XP awards require an integer amount.') from exc
            source_type = XPRewardSourceType(tokens[5].lower())
            source_id = tokens[6]
            reason = ' '.join(tokens[7:])
            return self.award_xp(
                controller_id,
                source_type=source_type,
                source_id=source_id,
                recipient_scope=recipient_scope,
                recipient_actor_ids=recipient_actor_ids,
                amount=amount,
                reason=reason,
            )
        if subcommand == 'milestone':
            if len(tokens) < 6 or tokens[2].lower() != 'complete':
                raise EncounterValidationError('Usage: /progression milestone complete <party|actor:id|actors:id,id> <source-type> <source-id> [reason ...]')
            recipient_scope, recipient_actor_ids = self._parse_progression_recipient_spec(tokens[3])
            source_type = MilestoneSourceType(tokens[4].lower())
            source_id = tokens[5]
            reason = ' '.join(tokens[6:])
            return self.complete_milestone(
                controller_id,
                source_type=source_type,
                source_id=source_id,
                recipient_scope=recipient_scope,
                recipient_actor_ids=recipient_actor_ids,
                reason=reason,
            )
        raise EncounterValidationError('Usage: /progression <status|mode|policy|xp|milestone> ...')

    def set_progression_mode(self, controller_id: str, mode: ProgressionMode):
        if not self._is_dm_controller(controller_id):
            raise EncounterPermissionError('Only the DM controller may change progression mode.')
        new_state, events = self.progression_engine.set_mode(
            self.story_state.progression_state,
            mode=mode,
            actor_snapshots=self._progression_actor_snapshots(),
            timestamp_seconds=self.state.clock_seconds,
        )
        self.story_state.progression_state = new_state
        for event in events:
            self._apply_runtime_event(event)
        self._sync_memory_files()
        return self.view_for_controller(controller_id)

    def set_progression_policy(self, controller_id: str, policy: ProgressionPolicy):
        if not self._is_dm_controller(controller_id):
            raise EncounterPermissionError('Only the DM controller may change progression policy.')
        new_state, events = self.progression_engine.set_policy(
            self.story_state.progression_state,
            policy=policy,
            actor_snapshots=self._progression_actor_snapshots(),
        )
        self.story_state.progression_state = new_state
        for event in events:
            self._apply_runtime_event(event)
        self._sync_memory_files()
        return self.view_for_controller(controller_id)

    def award_xp(
        self,
        controller_id: str,
        *,
        source_type: XPRewardSourceType,
        source_id: str,
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        amount: int,
        reason: str = '',
    ):
        if not self._is_dm_controller(controller_id):
            raise EncounterPermissionError('Only the DM controller may award XP.')
        new_state, events = self.progression_engine.log_xp_reward(
            self.story_state.progression_state,
            actor_snapshots=self._progression_actor_snapshots(),
            campaign_id=self.story_state.campaign_id,
            session_id=self.story_state.session_log_id,
            scene_id=self.story_state.current_scene_id,
            location_id=self.story_state.canonical_location_id,
            source_type=source_type,
            source_id=source_id,
            recipient_scope=recipient_scope,
            recipient_actor_ids=recipient_actor_ids,
            amount=amount,
            reason=reason,
            timestamp_seconds=self.state.clock_seconds,
        )
        self.story_state.progression_state = new_state
        for event in events:
            self._apply_runtime_event(event)
        self._sync_memory_files()
        return self.view_for_controller(controller_id)

    def complete_milestone(
        self,
        controller_id: str,
        *,
        source_type: MilestoneSourceType,
        source_id: str,
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        reason: str = '',
        advancement_steps: int = 1,
    ):
        if not self._is_dm_controller(controller_id):
            raise EncounterPermissionError('Only the DM controller may complete milestones.')
        new_state, events = self.progression_engine.complete_milestone(
            self.story_state.progression_state,
            actor_snapshots=self._progression_actor_snapshots(),
            campaign_id=self.story_state.campaign_id,
            session_id=self.story_state.session_log_id,
            scene_id=self.story_state.current_scene_id,
            location_id=self.story_state.canonical_location_id,
            source_type=source_type,
            source_id=source_id,
            recipient_scope=recipient_scope,
            recipient_actor_ids=recipient_actor_ids,
            reason=reason,
            timestamp_seconds=self.state.clock_seconds,
            advancement_steps=advancement_steps,
        )
        self.story_state.progression_state = new_state
        for event in events:
            self._apply_runtime_event(event)
        self._sync_memory_files()
        return self.view_for_controller(controller_id)

    def set_marching_order(self, controller_id: str, actor_ids: tuple[str, ...]):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().set_marching_order(
            state,
            encounter_state=self.state,
            intent=SetMarchingOrderIntent(controller_id=controller_id, actor_ids=actor_ids),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def set_watch_order(self, controller_id: str, actor_ids: tuple[str, ...]):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().set_watch_order(
            state,
            encounter_state=self.state,
            intent=SetWatchOrderIntent(controller_id=controller_id, actor_ids=actor_ids),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def assign_exploration_role(self, controller_id: str, role: ExplorationRole, actor_ids: tuple[str, ...]):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().assign_role(
            state,
            encounter_state=self.state,
            intent=AssignExplorationRoleIntent(controller_id=controller_id, role=role, actor_ids=actor_ids),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def set_camp_active(self, controller_id: str, active: bool):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().set_camp_state(
            state,
            encounter_state=self.state,
            intent=SetCampStateIntent(controller_id=controller_id, active=active),
            travel_active=self._travel_active(),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def attempt_social_influence(self, controller_id: str, *, actor_id: str, npc_id: str, approach: SocialApproachType):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().attempt_social_influence(
            state,
            encounter_state=self.state,
            intent=AttemptSocialInfluenceIntent(controller_id=controller_id, actor_id=actor_id, npc_id=npc_id, approach=approach),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def attempt_trap(self, controller_id: str, *, actor_id: str, trap_id: str, attempt_kind: ProcedureAttemptKind, tool_name: str | None = None):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().attempt_trap(
            state,
            encounter_state=self.state,
            intent=AttemptTrapIntent(controller_id=controller_id, actor_id=actor_id, trap_id=trap_id, attempt_kind=attempt_kind, tool_name=tool_name),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def trigger_trap(self, controller_id: str, *, trap_id: str, actor_id: str | None = None):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().trigger_trap(
            state,
            encounter_state=self.state,
            intent=TriggerTrapIntent(controller_id=controller_id, trap_id=trap_id, actor_id=actor_id),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def bypass_trap(self, controller_id: str, *, actor_id: str, trap_id: str):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().bypass_trap(
            state,
            encounter_state=self.state,
            intent=BypassTrapIntent(controller_id=controller_id, actor_id=actor_id, trap_id=trap_id),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def attempt_puzzle(self, controller_id: str, *, actor_id: str, puzzle_id: str, attempt_kind: ProcedureAttemptKind, tool_name: str | None = None):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().attempt_puzzle(
            state,
            encounter_state=self.state,
            intent=AttemptPuzzleIntent(controller_id=controller_id, actor_id=actor_id, puzzle_id=puzzle_id, attempt_kind=attempt_kind, tool_name=tool_name),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def abandon_puzzle(self, controller_id: str, *, puzzle_id: str):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().abandon_puzzle(
            state,
            intent=AbandonPuzzleIntent(controller_id=controller_id, puzzle_id=puzzle_id),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def start_downtime_project(self, controller_id: str, *, actor_id: str, activity_id: str):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().start_downtime_project(
            state,
            encounter_state=self.state,
            intent=StartDowntimeProjectIntent(controller_id=controller_id, actor_id=actor_id, activity_id=activity_id),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def work_downtime_project(self, controller_id: str, *, actor_id: str, project_id: str, hours: int, tool_name: str | None = None):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().work_downtime_project(
            state,
            encounter_state=self.state,
            intent=WorkDowntimeProjectIntent(controller_id=controller_id, actor_id=actor_id, project_id=project_id, hours=hours, tool_name=tool_name),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def cancel_downtime_project(self, controller_id: str, *, project_id: str):
        state = self.story_state.exploration_state
        if state is None:
            raise EncounterValidationError('No exploration state is configured for this session.')
        new_state, events = self._require_exploration_engine().cancel_downtime_project(
            state,
            intent=CancelDowntimeProjectIntent(controller_id=controller_id, project_id=project_id),
        )
        self._commit_exploration_result(new_state, list(events))
        return self.view_for_controller(controller_id)

    def _execute_travel_command(self, controller_id: str, command: str):
        self.encounter_session.control_runtime.validate_controller(controller_id)
        if self.story_state.runtime_mode == RuntimeMode.COMBAT:
            raise EncounterPermissionError('Travel commands are not available during combat.')
        engine = self._require_travel_engine()
        tokens = command.strip().split()
        if len(tokens) == 1 or tokens[1].lower() == 'status':
            return self.view_for_controller(controller_id)
        subcommand = tokens[1].lower()
        if subcommand == 'pace':
            if len(tokens) != 3:
                raise EncounterValidationError('Usage: /travel pace <cautious|normal|fast>.')
            return self.travel_set_pace(controller_id, TravelPace(tokens[2].lower()))
        if subcommand == 'route':
            if len(tokens) < 3:
                raise EncounterValidationError('Usage: /travel route <location-id|q r>.')
            destination = self._parse_travel_destination(tokens[2:])
            return self.travel_plan_route(controller_id, destination_coord=destination[0], destination_location_id=destination[1])
        if subcommand == 'advance':
            steps = 1 if len(tokens) == 2 else int(tokens[2])
            return self.travel_advance(controller_id, steps=steps)
        if subcommand == 'resume':
            return self.travel_resume(controller_id)
        if subcommand == 'engage':
            return self.travel_engage_pending_hook(controller_id)
        raise EncounterValidationError('Unknown travel command. Use /travel status|pace|route|advance|resume|engage.')

    def _parse_travel_destination(self, tokens: list[str]) -> tuple[HexCoord | None, str | None]:
        if len(tokens) == 1:
            return None, tokens[0]
        if len(tokens) == 2:
            try:
                return HexCoord(int(tokens[0]), int(tokens[1])), None
            except ValueError as exc:
                raise EncounterValidationError('Travel route coordinates must be integers: /travel route <q> <r>.') from exc
        raise EncounterValidationError('Travel route destination must be a location id or axial coordinates.')

    def travel_inspect_hex(self, controller_id: str, *, q: int, r: int):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        return self._require_travel_engine().inspect_hex(state, coord=HexCoord(q, r), dm_view=(binding.role.value == 'dm'))

    def travel_preview_route(self, controller_id: str, *, q: int | None = None, r: int | None = None, destination_location_id: str | None = None):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        destination = HexCoord(q, r) if q is not None and r is not None else None
        intent = PlanTravelRouteIntent(controller_id=controller_id, destination=destination, destination_location_id=destination_location_id)
        return self._require_travel_engine().preview_route(state, intent, dm_view=(binding.role.value == 'dm'))

    def travel_plan_route(self, controller_id: str, *, destination_coord: HexCoord | None = None, destination_location_id: str | None = None):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        intent = PlanTravelRouteIntent(controller_id=controller_id, destination=destination_coord, destination_location_id=destination_location_id)
        new_state, events = self._require_travel_engine().plan_route(state, intent, dm_view=(binding.role.value == 'dm'))
        self._commit_travel_result(new_state, events)
        return self.view_for_controller(controller_id)

    def travel_set_pace(self, controller_id: str, pace: TravelPace):
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        new_state, events = self._require_travel_engine().set_pace(state, SetTravelPaceIntent(controller_id=controller_id, pace=pace))
        self._commit_travel_result(new_state, events)
        return self.view_for_controller(controller_id)

    def travel_advance(self, controller_id: str, *, steps: int = 1):
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        new_state, events = self._require_travel_engine().advance(state, AdvanceTravelIntent(controller_id=controller_id, steps=steps))
        self._commit_travel_result(new_state, events)
        return self.view_for_controller(controller_id)

    def travel_resume(self, controller_id: str):
        state = self.story_state.travel_state
        if state is None:
            raise EncounterValidationError('No travel state is configured for this session.')
        new_state, events = self._require_travel_engine().resume(state, ResumeTravelIntent(controller_id=controller_id))
        self._commit_travel_result(new_state, events)
        return self.view_for_controller(controller_id)

    def travel_engage_pending_hook(self, controller_id: str):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        if binding.role.value != 'dm':
            raise EncounterPermissionError('Only the DM may engage a travel hook into combat.')
        state = self.story_state.travel_state
        if state is None or state.pending_hook is None:
            raise EncounterValidationError('There is no pending travel hook to engage.')
        hook = state.pending_hook
        if hook.battlefield_map_id is None:
            raise EncounterValidationError('The pending travel hook does not define a combat battlefield.')
        player_actor_ids = tuple(actor_id for actor_id in self.state.actors if actor_id.startswith('player-'))
        monster_actor_ids = tuple(actor_id for actor_id, actor in self.state.actors.items() if actor.side == ActorSide.MONSTER)
        self.enter_combat(
            EnterCombatPlan(
                reason=hook.summary,
                participant_ids=player_actor_ids + monster_actor_ids,
                scene_id=hook.scene_id,
                location_id=hook.location_id,
                ambush=True,
                battlefield_map_id=hook.battlefield_map_id,
            )
        )
        return self.view_for_controller(controller_id)

    def _append_public_travel_entry(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        self.story_state.transcript_entries = self.story_state.transcript_entries + (
            StoryTranscriptEntry(speaker='Travel', text=text, visibility=StoryTranscriptVisibility.PUBLIC),
        )

    def _merge_metadata_list(self, key: str, values: tuple[str, ...]) -> None:
        existing = tuple(item for item in self.story_state.metadata.get(key, '').split('|') if item)
        merged = unique_strings(existing + values)
        if merged:
            self.story_state.metadata[key] = '|'.join(merged)

    def _apply_travel_hook_story_updates(self, hook: TravelHookDefinition) -> None:
        if hook.scene_id is not None:
            self.story_state.current_scene_id = hook.scene_id
        if hook.location_id is not None:
            self.story_state.canonical_location_id = hook.location_id
        if hook.suggested_open_loops:
            self.story_state.open_loops = unique_strings(self.story_state.open_loops + hook.suggested_open_loops)
        if hook.suggested_party_goals:
            self.story_state.current_party_goals = hook.suggested_party_goals
        self.story_state.recent_summary = hook.summary

    def _commit_travel_result(self, new_state: TravelState, events: list[object]) -> None:
        self.story_state.travel_state = new_state
        for event in events:
            self.state.event_log.append(event)
            if isinstance(event, HexMapLoadedEvent):
                self.story_state.metadata['travel_map_id'] = event.map_id
            elif isinstance(event, TravelPaceChangedEvent):
                self._append_public_travel_entry(f'Travel pace changes to {event.new_pace.value}.')
            elif isinstance(event, TravelRoutePlannedEvent):
                self._append_public_travel_entry(f'Route planned toward {event.route.destination_label} ({event.route.estimated_minutes} minutes at current pace).')
            elif isinstance(event, TravelStartedEvent):
                self._append_public_travel_entry('Travel begins along the planned route.')
            elif isinstance(event, TravelStepAdvancedEvent):
                self.story_state.recent_summary = f'The party advances to hex {event.to_coord.q},{event.to_coord.r}.'
            elif isinstance(event, LandmarkDiscoveredEvent):
                self._append_public_travel_entry(f'Landmark discovered: {event.name}.')
                self._merge_metadata_list('scene_state_notes', (f'Landmark discovered: {event.name}.',))
            elif isinstance(event, LocationReachedEvent):
                self.story_state.canonical_location_id = event.location_id
                self._append_public_travel_entry(f'The party reaches {event.name}.')
            elif isinstance(event, TravelEventHookTriggeredEvent):
                self._apply_travel_hook_story_updates(event.hook)
                self._append_public_travel_entry(event.hook.summary)
                self._merge_metadata_list('scene_state_notes', (event.hook.summary,))
            elif isinstance(event, TravelInterruptedEvent):
                self._append_public_travel_entry(f'Travel is interrupted: {event.reason}')
            elif isinstance(event, TravelResumedEvent):
                self._append_public_travel_entry('Travel resumes.')
            elif isinstance(event, TravelModeProjectionUpdatedEvent):
                self.story_state.metadata['travel_status'] = event.status.value
            elif isinstance(event, HexDiscoveredEvent):
                continue
        self._refresh_exploration_context(sync_memory=False)
        self._sync_memory_files()

    def submit_story_action(self, controller_id: str, declaration: str):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        if binding.role.value == 'dm':
            raise EncounterPermissionError('DM storytelling is handled by the LLM runtime in this demo. Use the DM client for observation in storytelling mode and combat control after initiative starts.')
        pending_check = self._normalized_pending_check()
        if pending_check is not None:
            if pending_check.controller_id == controller_id:
                raise EncounterPermissionError('Resolve your pending story check before taking a new storytelling action.')
            raise EncounterPermissionError(self._pending_check_waiting_message(pending_check))
        if self.dm_runtime is None:
            raise EncounterValidationError('No DM storytelling runtime is configured for this session.')
        actor_id = self._owned_actor_for_controller(controller_id)
        self.state.event_log.append(StoryActionDeclaredEvent(controller_id=controller_id, actor_id=actor_id, declaration=declaration))
        exploration_state = self.story_state.exploration_state
        if exploration_state is not None and self.exploration_engine is not None:
            prompt = self.exploration_engine.interpret_declaration(
                exploration_state,
                encounter_state=self.state,
                actor_id=actor_id,
                declaration=declaration,
            )
            if prompt is not None:
                if self.social_engine is not None and prompt.pending_state.kind.value == 'social':
                    prompt = self.social_engine.adjust_social_prompt(self.story_state.social_state, prompt, now_seconds=self.state.clock_seconds)
                self._open_exploration_pending_check(controller_id, prompt)
                return self.view_for_controller(controller_id)
        escalation = self._evaluate_hostile_story_declaration(actor_id=actor_id, declaration=declaration)
        self.state.event_log.append(HostileEscalationEvaluatedEvent(decision=escalation))
        if escalation.outcome == HostileEscalationOutcome.CLARIFICATION_REQUIRED:
            raise EncounterClarificationRequiredError(escalation.clarification_prompt or escalation.reason)
        if escalation.outcome != HostileEscalationOutcome.REMAIN_IN_STORY_MODE:
            self.state.event_log.append(HostileEscalationTriggeredEvent(decision=escalation))
            self._apply_story_combat_transition(escalation)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        documents = self.select_relevant_documents()
        self._emit_llm_feedback(controller_id, 'info', 'DM is thinking...')
        stream_handler = self._story_llm_stream_handler(controller_id)
        retry_handler = self._story_llm_retry_handler(controller_id, request_label='DM response')
        try:
            decision, events = self.dm_runtime.plan_story_turn(
                self.storytelling_context(),
                documents,
                controller_id=controller_id,
                actor_id=actor_id,
                declaration=declaration,
                available_actor_ids=self._player_actor_ids(),
                available_combatant_actor_ids=self._available_story_combatant_actor_ids(),
                actors_with_resolved_scene_checks=self._actors_with_resolved_story_checks_in_scene(),
                stream_handler=stream_handler,
                retry_handler=retry_handler,
            )
        finally:
            flush = getattr(stream_handler, 'flush', None)
            if callable(flush):
                flush()
        self.state.event_log.extend(events)
        self._apply_story_turn_decision(decision, triggering_declaration=declaration)
        return self.view_for_controller(controller_id)


    def _story_mode_cast_intent(self, command: str) -> CastSpellIntent:
        intent = self.encounter_session.command_interface.parse_command(command)
        if not isinstance(intent, CastSpellIntent):
            raise EncounterValidationError('Story-mode spellcasting requires a /cast command.')
        return intent

    def _build_story_cast_context(self, controller_id: str, intent: CastSpellIntent, spell: RuntimeSpellState) -> StoryModeCastContext:
        return StoryModeCastContext(
            attempt=StoryModeCastAttempt(
                actor_id=intent.actor_id,
                spell_id=intent.spell_id,
                controller_id=controller_id,
                scene_id=self.story_state.current_scene_id,
                location_id=self.story_state.canonical_location_id,
                target_id=intent.target_id,
                point=((intent.x, intent.y, intent.z or 0) if intent.x is not None and intent.y is not None else None),
                casting_time_seconds=spell.casting_time_seconds,
                ritual_cast=intent.ritual_cast,
            ),
            spell_name=spell.name,
            spell_level=spell.level,
            action_cost=spell.action_cost,
            perceptibility=spell.perceptibility,
            current_scene_summary=self.story_state.recent_summary,
            recent_session_summary=self.story_state.recent_summary,
            party_goal_summary='; '.join(self.story_state.current_party_goals),
            unresolved_hooks=self.story_state.open_loops,
            visible_npc_ids=self._visible_npc_ids(),
            nearby_tags=tuple(tag for tag in self.story_state.metadata.get('nearby_tags', '').split(',') if tag),
        )

    def _story_casting_act_perceptible(self, spell: RuntimeSpellState) -> bool:
        profile = spell.perceptibility
        if profile.componentless_casting:
            return False
        return bool(
            profile.has_verbal_component
            or profile.has_somatic_component
            or profile.has_material_component
            or profile.casting_visual_manifestation
            or profile.casting_auditory_manifestation
        )

    def _story_spell_effect_perceptible(self, spell: RuntimeSpellState) -> bool:
        profile = spell.perceptibility
        return bool(profile.effect_visible or profile.effect_audible)

    def _spell_effect_signal_tags(self, effect) -> set[str]:
        tags: set[str] = set()
        if effect is None:
            return tags
        if isinstance(effect, CompositeEffect):
            for item in effect.effects:
                tags.update(self._spell_effect_signal_tags(item))
            return tags
        if isinstance(effect, DamageEffectDef):
            tags.add('harmful')
            return tags
        if isinstance(effect, HealingEffectDef):
            tags.add('healing')
            return tags
        if isinstance(effect, ConditionEffectDef):
            if effect.condition_type in {ConditionType.CHARMED, ConditionType.FRIGHTENED}:
                tags.add('manipulative')
            elif effect.condition_type in {ConditionType.PARALYZED, ConditionType.INCAPACITATED, ConditionType.POISONED, ConditionType.RESTRAINED, ConditionType.UNCONSCIOUS}:
                tags.add('harmful')
            else:
                tags.add('control')
            return tags
        if isinstance(effect, AttackRollGateEffect):
            if effect.damaging:
                tags.add('harmful')
            for item in effect.on_hit:
                tags.update(self._spell_effect_signal_tags(item))
            for item in effect.on_miss:
                tags.update(self._spell_effect_signal_tags(item))
            return tags
        if isinstance(effect, SaveGateEffect):
            for item in effect.on_success:
                tags.update(self._spell_effect_signal_tags(item))
            for item in effect.on_failure:
                tags.update(self._spell_effect_signal_tags(item))
            for item in effect.on_partial_success:
                tags.update(self._spell_effect_signal_tags(item))
            return tags
        if isinstance(effect, StartActiveEffectDef):
            active = effect.active_effect
            if active.armor_class_bonus > 0 or active.speed_override_ft is not None or active.damage_resistances or active.melee_attack_damage_bonus:
                tags.add('supportive')
            if active.information_payloads:
                tags.add('divination')
            if active.illusions:
                tags.add('illusion')
            if active.created_objects or active.summoned_creatures or active.persistent_areas:
                tags.add('utility')
            for item in active.on_start:
                tags.update(self._spell_effect_signal_tags(item))
            for item in active.on_end:
                tags.update(self._spell_effect_signal_tags(item))
            for trigger in active.ongoing_triggers:
                for item in trigger.on_success:
                    tags.update(self._spell_effect_signal_tags(item))
                for item in trigger.on_failure:
                    tags.update(self._spell_effect_signal_tags(item))
            return tags
        return tags

    def _story_spell_signal_tags(self, spell: RuntimeSpellState) -> tuple[str, ...]:
        tags = self._spell_effect_signal_tags(spell.capability.effect if spell.capability is not None else None)
        lowered_name = spell.name.casefold()
        if 'charm' in lowered_name:
            tags.add('manipulative')
        if 'detect' in lowered_name:
            tags.add('divination')
        if spell.effect_type is not None and spell.effect_type.value == 'magic-missile':
            tags.add('harmful')
        return tuple(sorted(tags))

    def _spell_concern_level(self, spell: RuntimeSpellState) -> SpellcastingConcernLevel:
        tags = set(self._story_spell_signal_tags(spell))
        if 'harmful' in tags or 'manipulative' in tags:
            return SpellcastingConcernLevel.HIGH
        if 'divination' in tags or 'illusion' in tags or 'control' in tags:
            return SpellcastingConcernLevel.MODERATE
        if 'healing' in tags or 'supportive' in tags or 'utility' in tags:
            return SpellcastingConcernLevel.LOW
        if spell.level == 0:
            return SpellcastingConcernLevel.LOW
        return SpellcastingConcernLevel.MODERATE

    def _evaluate_hostile_story_spellcast(self, context: StoryModeCastContext, witness_packet: WitnessObservationPacket, spell: RuntimeSpellState) -> HostileEscalationDecision:
        return self.hostile_escalation_engine.evaluate_spellcast(
            encounter_state=self.state,
            story_state=self.story_state,
            exploration_state=self.story_state.exploration_state,
            context=context,
            witness_packet=witness_packet,
            spell_signal_tags=self._story_spell_signal_tags(spell),
        )

    def _evaluate_hostile_story_declaration(self, *, actor_id: str, declaration: str) -> HostileEscalationDecision:
        return self.hostile_escalation_engine.evaluate_declaration(
            encounter_state=self.state,
            story_state=self.story_state,
            exploration_state=self.story_state.exploration_state,
            actor_id=actor_id,
            declaration=declaration,
            visible_npc_ids=self._visible_npc_ids(),
        )

    def _hydrate_hostile_escalation_decision(self, decision: HostileEscalationDecision) -> HostileEscalationDecision:
        return self.hostile_escalation_engine.hydrate_decision(
            encounter_state=self.state,
            story_state=self.story_state,
            exploration_state=self.story_state.exploration_state,
            decision=decision,
            visible_npc_ids=self._visible_npc_ids(),
        )

    def _position_for_synthesized_combatant(self, scene_plan, spec, *, index: int):
        battlefield = scene_plan.battlefield
        if spec.source_npc_id == 'gundren-rockseeker' and 'gundren-zone' in battlefield.spawn_zones:
            return battlefield.spawn_zones['gundren-zone'][0]
        if spec.source_npc_id == 'sildar-hallwinter' and 'sildar-zone' in battlefield.spawn_zones:
            return battlefield.spawn_zones['sildar-zone'][0]
        hosts = battlefield.spawn_zones.get('hosts', ())
        if hosts:
            return hosts[min(index, len(hosts) - 1)]
        for zone_id in scene_plan.primary_hostile_zone_ids:
            positions = battlefield.spawn_zones.get(zone_id, ())
            if positions:
                return positions[min(index, len(positions) - 1)]
        hostiles = battlefield.spawn_zones.get('hostiles', ())
        if hostiles:
            return hostiles[min(index, len(hostiles) - 1)]
        players = battlefield.spawn_zones.get('players', ())
        if players:
            return players[min(index, len(players) - 1)]
        raise EncounterValidationError('Synthesized battlefield does not provide any legal spawn positions.')

    def _apply_story_combat_transition(self, decision: HostileEscalationDecision) -> None:
        decision = self._hydrate_hostile_escalation_decision(decision)
        scene_plan = decision.scene_plan
        if scene_plan is None:
            raise EncounterValidationError('Hostile escalation requires a synthesized or authored tactical scene plan.')
        self.state.event_log.append(AdHocEncounterSceneSynthesizedEvent(scene_plan=scene_plan))
        self.state.battlefield = scene_plan.battlefield
        player_actor_ids = self._player_actor_ids()
        player_positions = scene_plan.battlefield.spawn_zones.get('players', ())
        if len(player_positions) < len(player_actor_ids):
            raise EncounterValidationError('Synthesized battlefield does not provide enough player spawn positions.')
        for index, actor_id in enumerate(player_actor_ids):
            self.state.actors[actor_id].position = player_positions[index]
        synthesized_actor_ids: list[str] = []
        for index, spec in enumerate(decision.synthesized_combatants):
            actor = self.hostile_escalation_engine.synthesize_actor(
                self.encounter_session.runtime_services,
                spec,
                position=self._position_for_synthesized_combatant(scene_plan, spec, index=index),
            )
            self.state.actors[actor.actor_id] = actor
            self.encounter_session.control_runtime.actor_controllers[actor.actor_id] = 'dm'
            synthesized_actor_ids.append(actor.actor_id)
            self.state.event_log.append(StoryNPCCombatantSynthesizedEvent(combatant=spec))
            if actor.fallback_synthesized:
                self.state.event_log.append(StoryNPCCombatantFallbackUsedEvent(combatant=spec))
        for plan in decision.reinforcement_plans:
            self.state.event_log.append(ReinforcementScheduledEvent(schedule=plan))
        metadata_lines = list((decision.transition_state.metadata_lines if decision.transition_state is not None else ()))
        if decision.opening_action_summary and decision.opening_action_summary not in metadata_lines:
            metadata_lines.append(decision.opening_action_summary)
        transition = replace(
            decision.transition_state or CombatTransitionState(
                reason=decision.reason,
                source_scene_id=self.story_state.current_scene_id,
                source_location_id=self.story_state.canonical_location_id,
                opening_action_summary=decision.opening_action_summary,
                battlefield_map_id=scene_plan.map_id,
                scene_kind=scene_plan.scene_kind,
                fallback_scene=scene_plan.fallback_used,
            ),
            reason=decision.reason,
            source_scene_id=self.story_state.current_scene_id,
            source_location_id=self.story_state.canonical_location_id,
            opening_action_summary=decision.opening_action_summary,
            battlefield_map_id=scene_plan.map_id,
            scene_kind=scene_plan.scene_kind,
            fallback_scene=scene_plan.fallback_used,
            synthesized_actor_ids=tuple(synthesized_actor_ids),
            witness_ids=decision.witness_ids,
            reinforcement_plans=decision.reinforcement_plans,
            bystander_npc_ids=decision.noncombatant_npc_ids,
            metadata_lines=tuple(metadata_lines),
        )
        self.story_state.combat_transition = transition
        if transition.metadata_lines:
            self._merge_metadata_list('scene_state_notes', transition.metadata_lines)
        self.state.event_log.append(StorySceneCommittedToCombatEvent(context=transition))
        if decision.outcome == HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_SURPRISE_CHECK:
            self.state.event_log.append(SurpriseEvaluationTriggeredEvent(actor_id=decision.hostile_actor_id, reason=decision.reason))
        if decision.surprised_actor_ids:
            self.state.event_log.append(SurpriseStateComputedEvent(surprised_actor_ids=decision.surprised_actor_ids, reason=decision.reason))
        plan = EnterCombatPlan(
            reason=decision.reason,
            participant_ids=decision.participant_actor_ids,
            scene_id=self.story_state.current_scene_id,
            location_id=self.story_state.canonical_location_id,
            ambush=(decision.outcome == HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_SURPRISE_CHECK),
            battlefield_map_id=scene_plan.map_id,
            surprised_actor_ids=decision.surprised_actor_ids,
            synthesized_combatants=decision.synthesized_combatants,
            reinforcement_plans=decision.reinforcement_plans,
            scene_plan=scene_plan,
            transition_state=transition,
        )
        self.enter_combat(plan, surprised_actor_ids=decision.surprised_actor_ids)
        self.state.event_log.append(
            CombatStartedFromStorySceneEvent(
                scene_id=self.story_state.current_scene_id,
                location_id=self.story_state.canonical_location_id,
                participant_actor_ids=decision.participant_actor_ids,
                reason=decision.reason,
            )
        )

    def _transition_summary_lines(self, controller_id: str, *, dm_view: bool) -> list[str]:
        transition = self.story_state.combat_transition
        if transition is None:
            return []
        lines = [f'Combat transition: {transition.reason}']
        if transition.opening_action_summary:
            lines.append(f'Opening hostile act: {transition.opening_action_summary}')
        if transition.fallback_scene:
            lines.append(f'Tactical scene: synthesized {transition.scene_kind.value} ({transition.battlefield_map_id}).')
        for plan in self.hostile_escalation_engine.visible_reinforcements(transition, dm_view=dm_view):
            remaining_rounds = max(0, plan.rounds_until_arrival - max(0, self.state.round_number - 1))
            lines.append(f'Reinforcement timer: {plan.label} in {remaining_rounds} rounds via {plan.entry_zone_id}.')
        return lines

    def _scene_npc_witness_observations(self, context: StoryModeCastContext) -> tuple[WitnessObservation, ...]:
        state = self.story_state.exploration_state
        engine = self.exploration_engine
        if state is None or engine is None:
            return ()
        caster = self.state.actors[context.attempt.actor_id]
        spell = caster.spells[context.attempt.spell_id]
        can_notice_casting = self._story_casting_act_perceptible(spell) and not caster.hidden
        can_notice_effect = self._story_spell_effect_perceptible(spell)
        if not can_notice_casting and not can_notice_effect:
            return ()
        concern = self._spell_concern_level(spell)
        location_id = context.attempt.location_id or self.story_state.canonical_location_id
        observations: list[WitnessObservation] = []
        for npc_state in engine.visible_npc_states(state):
            if npc_state.npc_id not in context.visible_npc_ids:
                continue
            perceived_casting_act = can_notice_casting
            perceived_spell_effect = can_notice_effect
            if not perceived_casting_act and not perceived_spell_effect:
                continue
            confidence = SpellcastingObservationConfidence.CLEAR if perceived_casting_act else SpellcastingObservationConfidence.EFFECT_ONLY
            norm_profiles = self.social_engine.norms_for_observer(self.story_state.social_state, npc_state.npc_id, location_id, scene_id=self.story_state.current_scene_id) if self.social_engine is not None else ()
            relationship = self.social_engine.relationship_for_npc(self.story_state.social_state, npc_state.npc_id) if self.social_engine is not None else None
            observations.append(
                WitnessObservation(
                    observer_id=npc_state.npc_id,
                    observer_kind=StoryWitnessKind.SCENE_NPC,
                    display_name=npc_state.display_name,
                    paying_attention=True,
                    perceived_casting_act=perceived_casting_act,
                    perceived_spell_effect=perceived_spell_effect,
                    confidence=confidence,
                    concern_level=concern,
                    attitude=npc_state.attitude,
                    current_stance=npc_state.current_stance,
                    applicable_norm_ids=tuple(profile.norm_id for profile in norm_profiles),
                    norm_tags=tuple(sorted({tag.value for profile in norm_profiles for tag in profile.tags})),
                    relationship_trust=(relationship.trust if relationship is not None else npc_state.trust),
                    relationship_suspicion=(relationship.suspicion if relationship is not None else max(0, npc_state.hostility)),
                    relationship_fear=(relationship.fear if relationship is not None else npc_state.fear),
                    relationship_respect=(relationship.respect if relationship is not None else 0),
                )
            )
        return tuple(observations)

    def _build_story_spell_witness_packet(self, context: StoryModeCastContext) -> WitnessObservationPacket:
        return WitnessObservationPacket(
            caster_actor_id=context.attempt.actor_id,
            spell_id=context.attempt.spell_id,
            spell_name=context.spell_name,
            spell_level=context.spell_level,
            action_cost=context.action_cost,
            target_actor_id=context.attempt.target_id,
            point=context.attempt.point,
            witnesses=self._scene_npc_witness_observations(context),
        )

    def _observer_facing_spell_results(
        self,
        context: StoryModeCastContext,
        witness_packet: WitnessObservationPacket,
    ) -> tuple[ObserverFacingSpellcastResult, ...]:
        results: list[ObserverFacingSpellcastResult] = [
            ObserverFacingSpellcastResult(
                observer_id=context.attempt.actor_id,
                observer_kind=StoryWitnessKind.RUNTIME_ACTOR,
                awareness=StorySpellObserverAwareness.CASTER_CONFIRMED,
            )
        ]
        if context.attempt.target_id is not None and context.attempt.target_id != context.attempt.actor_id:
            results.append(
                ObserverFacingSpellcastResult(
                    observer_id=context.attempt.target_id,
                    observer_kind=StoryWitnessKind.RUNTIME_ACTOR,
                    awareness=StorySpellObserverAwareness.TARGET_AFFECTED,
                )
            )
        for witness in witness_packet.witnesses:
            if witness.perceived_casting_act:
                awareness = StorySpellObserverAwareness.SAW_CASTING
            elif witness.perceived_spell_effect:
                awareness = StorySpellObserverAwareness.SAW_EFFECT_ONLY
            elif witness.confidence == SpellcastingObservationConfidence.SUSPECTED:
                awareness = StorySpellObserverAwareness.NOTICED_UNUSUAL
            else:
                awareness = StorySpellObserverAwareness.UNAWARE
            results.append(
                ObserverFacingSpellcastResult(
                    observer_id=witness.observer_id,
                    observer_kind=witness.observer_kind,
                    awareness=awareness,
                )
            )
        return tuple(results)

    def _spell_reaction_transcript_entries(
        self,
        plan: SpellcastingSocialReactionPlan,
        witness_packet: WitnessObservationPacket,
    ) -> tuple[StoryTranscriptEntry, ...]:
        if not plan.public_narration and not any(reaction.public_text for reaction in plan.witness_reactions):
            return ()
        name_by_id = {witness.observer_id: witness.display_name for witness in witness_packet.witnesses}
        entries: list[StoryTranscriptEntry] = []
        if plan.public_narration:
            entries.append(StoryTranscriptEntry(speaker='DM', text=plan.public_narration, visibility=StoryTranscriptVisibility.PUBLIC))
        for reaction in plan.witness_reactions:
            if not reaction.public_text:
                continue
            entries.append(
                StoryTranscriptEntry(
                    speaker=name_by_id.get(reaction.witness_id, reaction.witness_id),
                    text=reaction.public_text,
                    visibility=StoryTranscriptVisibility.PUBLIC,
                )
            )
        return tuple(entries)

    def _story_spell_parameters(self, intent: CastSpellIntent) -> dict[str, str]:
        return {parameter.key: parameter.value for parameter in intent.parameters}

    def _required_story_spell_parameter(self, intent: CastSpellIntent, key: str, *, label: str | None = None) -> str:
        value = self._story_spell_parameters(intent).get(key)
        if value is None or not value.strip():
            requirement = label or key
            raise EncounterValidationError(f'Story-mode spellcasting for this spell requires --{key} to specify {requirement}.')
        return value.strip()

    def _story_spell_target_summary(self, intent: CastSpellIntent) -> str:
        if intent.target_id is not None:
            target = self.state.actors.get(intent.target_id)
            return target.name if target is not None else intent.target_id
        if intent.x is not None and intent.y is not None:
            return f'point ({intent.x}, {intent.y}, {intent.z or 0})'
        recipient = self._story_spell_parameters(intent).get('recipient')
        if recipient is not None and recipient.strip():
            return recipient.strip()
        return 'no explicit target'

    def _story_spell_adjudication_declaration(self, spell: RuntimeSpellState, intent: CastSpellIntent) -> str:
        parameters = self._story_spell_parameters(intent)
        spec = _STORY_UTILITY_CANTRIP_SPECS.get(spell.name)
        if spec is None:
            if intent.target_id is not None:
                target = self.state.actors.get(intent.target_id)
                target_label = target.name if target is not None else intent.target_id
                return f'Cast the spell {spell.name} on {target_label}.'
            if intent.x is not None and intent.y is not None:
                z = intent.z or 0
                return f'Cast the spell {spell.name} at point ({intent.x}, {intent.y}, {z}).'
            return f'Cast the spell {spell.name}.'
        lines = [f'Cast the spell {spell.name}.', f'Targeting: {self._story_spell_target_summary(intent)}.']
        effect_map = spec.get('effects')
        if isinstance(effect_map, dict) and effect_map:
            requested_effect = parameters.get('effect', '').strip()
            if not requested_effect:
                options = ', '.join(sorted(effect_map))
                raise EncounterValidationError(f'{spell.name} requires --effect with one of: {options}.')
            if requested_effect not in effect_map:
                options = ', '.join(sorted(effect_map))
                raise EncounterValidationError(f'Invalid --effect for {spell.name}. Choose one of: {options}.')
            lines.append(f'Requested spell option: {requested_effect}. {effect_map[requested_effect]}')
        if spec.get('requires_message'):
            message_text = self._required_story_spell_parameter(intent, 'message', label='the whispered message')
            lines.append(f'Requested whispered message: {message_text}')
            reply_text = parameters.get('reply', '').strip()
            if reply_text:
                lines.append(f'Expected whispered reply: {reply_text}')
        elif spec.get('requires_description', True):
            description = parameters.get('description', '').strip() or parameters.get('request', '').strip()
            if not description:
                raise EncounterValidationError(f'{spell.name} requires --description to describe the requested use in storytelling mode.')
            lines.append(f"Player's requested use: {description}")
        lines.append('Exact local XPHB constraints:')
        for rule in spec.get('rules', ()):  # type: ignore[arg-type]
            lines.append(f'- {rule}')
        return '\n'.join(lines)

    def _execute_story_message(self, controller_id: str, *, actor_id: str, intent: CastSpellIntent) -> None:
        caster = self.state.actors[actor_id]
        message_text = self._required_story_spell_parameter(intent, 'message', label='the whispered message')
        parameters = self._story_spell_parameters(intent)
        controller_ids = [controller_id, 'dm']
        recipient_label = parameters.get('recipient', '').strip()
        if intent.target_id is not None:
            target = self.state.actors.get(intent.target_id)
            if target is None:
                raise EncounterValidationError('Message target must be a known runtime actor in this path.')
            recipient_label = target.name
            try:
                recipient_controller_id = self.encounter_session.control_runtime.controller_for_actor(target.actor_id)
            except EncounterOwnershipError:
                recipient_controller_id = None
            if recipient_controller_id is not None and recipient_controller_id not in controller_ids:
                controller_ids.append(recipient_controller_id)
        elif not recipient_label:
            raise EncounterValidationError('Message requires a target actor id or --recipient in storytelling mode.')
        reply_text = parameters.get('reply', '').strip()
        entries = [
            StoryTranscriptEntry(
                speaker=f'{caster.name} (Message)',
                text=f'To {recipient_label}: {message_text}',
                visibility=StoryTranscriptVisibility.PRIVATE_CONTROLLERS,
                controller_ids=tuple(controller_ids),
            )
        ]
        if reply_text:
            entries.append(
                StoryTranscriptEntry(
                    speaker=f'{recipient_label} (Reply)',
                    text=reply_text,
                    visibility=StoryTranscriptVisibility.PRIVATE_CONTROLLERS,
                    controller_ids=tuple(controller_ids),
                )
            )
        self._append_transcript(tuple(entries))

    def _execute_story_spell_adjudication(self, controller_id: str, *, actor_id: str, spell: RuntimeSpellState, intent: CastSpellIntent) -> None:
        if spell.name == 'Message':
            self._execute_story_message(controller_id, actor_id=actor_id, intent=intent)
            return
        if self.adjudication_planner is None:
            raise EncounterValidationError('No DM adjudication planner is configured for story-supported spell effects.')
        declaration = self._story_spell_adjudication_declaration(spell, intent)
        documents = self.select_relevant_documents()
        context = self._build_adjudication_context(controller_id=controller_id, actor_id=actor_id, declaration=declaration)
        self.state.event_log.append(AdjudicationRequestedEvent(controller_id=controller_id, actor_id=actor_id, runtime_mode=self.story_state.runtime_mode, declaration=declaration))
        self.state.event_log.append(AdjudicationContextBuiltEvent(actor_id=actor_id, runtime_mode=self.story_state.runtime_mode, scene_id=self.story_state.current_scene_id, location_id=self.story_state.canonical_location_id, document_ids=tuple(document.doc_id for document in documents)))
        self._emit_llm_feedback(controller_id, 'info', f'DM is resolving the effect of {spell.name}...')
        stream_handler = self._story_llm_stream_handler(controller_id)
        retry_handler = self._story_llm_retry_handler(controller_id, request_label='DM spell-effect response')

        def _validation_callback(plan):
            self.state.event_log.append(AdjudicationPlanReceivedEvent(actor_id=actor_id, plan=plan))
            try:
                validated = self.adjudication_runtime.validate_plan(
                    self.state,
                    runtime_mode=self.story_state.runtime_mode,
                    controller_id=controller_id,
                    actor_id=actor_id,
                    plan=plan,
                )
            except EncounterValidationError as exc:
                self.state.event_log.append(AdjudicationPlanRejectedEvent(actor_id=actor_id, reason=str(exc)))
                raise DMRuntimeError(str(exc)) from exc
            self.state.event_log.append(AdjudicationPlanValidatedEvent(actor_id=actor_id, plan=validated))
            return validated

        try:
            plan, events = self.adjudication_planner.plan_action(
                context,
                documents,
                validation_callback=_validation_callback,
                stream_handler=stream_handler,
                retry_handler=retry_handler,
            )
        finally:
            flush = getattr(stream_handler, 'flush', None)
            if callable(flush):
                flush()
        self.state.event_log.extend(events)
        result = self.adjudication_runtime.execute_plan(
            self.state,
            runtime_mode=self.story_state.runtime_mode,
            controller_id=controller_id,
            actor_id=actor_id,
            plan=plan,
        )
        self._apply_adjudication_result(actor_id=actor_id, result=result)

    def cast_story_spell(self, controller_id: str, command: str):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        if binding.role.value == 'dm':
            raise EncounterPermissionError('DM storytelling is handled by the LLM runtime in this demo. Use the DM client for observation in storytelling mode and combat control after initiative starts.')
        pending_check = self._normalized_pending_check()
        if pending_check is not None:
            if pending_check.controller_id == controller_id:
                raise EncounterPermissionError('Resolve your pending story check before casting a spell in storytelling mode.')
            raise EncounterPermissionError(self._pending_check_waiting_message(pending_check))
        intent = self._story_mode_cast_intent(command)
        owned_actor_id = self._owned_actor_for_controller(controller_id)
        if intent.actor_id != owned_actor_id:
            raise EncounterPermissionError('Controllers may only cast story-mode spells for their owned actor.')
        actor = self.state.actors.get(intent.actor_id)
        if actor is None:
            raise EncounterValidationError(f'Unknown actor: {intent.actor_id}.')
        spell = actor.spells.get(intent.spell_id)
        if spell is None:
            raise EncounterValidationError(f'{actor.name} does not know spell {intent.spell_id}.')
        self.state.event_log.append(
            StoryModeSpellcastDeclaredEvent(
                actor_id=intent.actor_id,
                spell_id=intent.spell_id,
                scene_id=self.story_state.current_scene_id,
                location_id=self.story_state.canonical_location_id,
                ritual_cast=intent.ritual_cast,
                target_id=intent.target_id,
            )
        )
        context = self._build_story_cast_context(controller_id, intent, spell)
        witness_packet = self._build_story_spell_witness_packet(context)
        escalation = self._evaluate_hostile_story_spellcast(context, witness_packet, spell)
        self.state.event_log.append(HostileEscalationEvaluatedEvent(decision=escalation))
        if escalation.outcome == HostileEscalationOutcome.CLARIFICATION_REQUIRED:
            raise EncounterClarificationRequiredError(escalation.clarification_prompt or escalation.reason)
        if escalation.outcome != HostileEscalationOutcome.REMAIN_IN_STORY_MODE:
            self.state.event_log.append(HostileEscalationTriggeredEvent(decision=escalation))
            self._apply_story_combat_transition(escalation)
            self._sync_memory_files()
            return self.view_for_controller(controller_id)
        if intent.target_id is not None and intent.target_id not in self.state.actors:
            raise EncounterValidationError('Story-mode spell resolution only supports runtime actor targets unless the cast escalates into combat.')
        clock_before = self.state.clock_seconds
        point = GridPosition(intent.x, intent.y, intent.z or 0) if intent.x is not None and intent.y is not None else None
        try:
            support = spell.runtime_support
            if spell.capability is None and support is not None and support.support_mode == SpellRuntimeSupportMode.STORY_ADJUDICATED:
                events = self.encounter_session.control_runtime.kernel.prepare_story_supported_spellcast_events(
                    self.state,
                    actor_id=intent.actor_id,
                    spell_id=intent.spell_id,
                    target_id=intent.target_id,
                    point=point,
                    ritual_cast=intent.ritual_cast,
                    parameters=self._story_spell_parameters(intent),
                )
                for event in events:
                    self.state.event_log.append(event)
                    self._apply_runtime_event(event)
                self._execute_story_spell_adjudication(controller_id, actor_id=intent.actor_id, spell=spell, intent=intent)
            else:
                self.encounter_session.control_runtime.submit_intent(self.state, controller_id, intent)
        except Exception as exc:
            self.state.event_log.append(
                StoryModeSpellcastRejectedEvent(
                    actor_id=intent.actor_id,
                    spell_id=intent.spell_id,
                    reason=str(exc),
                )
            )
            raise
        self.state.event_log.append(
            StoryModeSpellcastValidatedEvent(
                actor_id=intent.actor_id,
                spell_id=intent.spell_id,
                casting_time_seconds=spell.casting_time_seconds,
                ritual_cast=intent.ritual_cast,
            )
        )
        self.state.event_log.append(SpellcastingWitnessPacketCreatedEvent(packet=witness_packet))
        observer_results = self._observer_facing_spell_results(context, witness_packet)
        for witness in witness_packet.witnesses:
            if witness.perceived_casting_act:
                self.state.event_log.append(
                    StoryModeSpellcastingPerceivedEvent(
                        observer_id=witness.observer_id,
                        observer_kind=witness.observer_kind,
                        spell_id=intent.spell_id,
                        confidence=witness.confidence,
                        concern_level=witness.concern_level,
                    )
                )
            if witness.perceived_casting_act:
                awareness = StorySpellObserverAwareness.SAW_CASTING
            elif witness.perceived_spell_effect:
                awareness = StorySpellObserverAwareness.SAW_EFFECT_ONLY
            elif witness.confidence == SpellcastingObservationConfidence.SUSPECTED:
                awareness = StorySpellObserverAwareness.NOTICED_UNUSUAL
            else:
                awareness = StorySpellObserverAwareness.UNAWARE
            if awareness != StorySpellObserverAwareness.UNAWARE:
                self.state.event_log.append(
                    StoryModeSpellEffectPerceivedEvent(
                        observer_id=witness.observer_id,
                        observer_kind=witness.observer_kind,
                        spell_id=intent.spell_id,
                        awareness=awareness,
                    )
                )
        social_reaction_plan = None
        if witness_packet.witnesses and spell.name != 'Message':
            if self.dm_runtime is None:
                raise EncounterValidationError('Witnessed story-mode spellcasting requires a DM storytelling runtime.')
            documents = self.select_relevant_documents()
            self._emit_llm_feedback(controller_id, 'info', 'DM is judging how the witnesses react to the spellcasting...')
            stream_handler = self._story_llm_stream_handler(controller_id)
            retry_handler = self._story_llm_retry_handler(controller_id, request_label='DM spellcasting-reaction response')
            try:
                social_reaction_plan, events = self.dm_runtime.plan_spellcasting_reaction(
                    context,
                    documents,
                    witness_packet=witness_packet,
                    stream_handler=stream_handler,
                    retry_handler=retry_handler,
                )
            finally:
                flush = getattr(stream_handler, 'flush', None)
                if callable(flush):
                    flush()
            self.state.event_log.extend(events)
            self.state.event_log.append(SpellcastingSocialReactionResolvedEvent(plan=social_reaction_plan))
            if social_reaction_plan.witness_reactions and self.story_state.exploration_state is not None and self.exploration_engine is not None:
                new_state, events = self.exploration_engine.apply_spellcasting_reactions(
                    self.story_state.exploration_state,
                    reactions=social_reaction_plan.witness_reactions,
                )
                self._commit_exploration_result(new_state, list(events), sync_memory=False)
            transcript_entries = self._spell_reaction_transcript_entries(social_reaction_plan, witness_packet)
            if transcript_entries:
                self._append_transcript(transcript_entries)
            if social_reaction_plan.scene_note:
                self._merge_metadata_list('scene_state_notes', (social_reaction_plan.scene_note,))
            if social_reaction_plan.dm_note:
                self._merge_metadata_list('scene_state_notes', (social_reaction_plan.dm_note,))
            suspicious_categories = {
                SpellcastingReactionCategory.SUSPICIOUS,
                SpellcastingReactionCategory.ALARMED,
                SpellcastingReactionCategory.CONFRONTATIONAL,
                SpellcastingReactionCategory.REPORT_TO_AUTHORITY,
                SpellcastingReactionCategory.HOSTILE,
                SpellcastingReactionCategory.ESCALATES_TO_MODE_SWITCH_CANDIDATE,
            }
            noteworthy_reaction = False
            for reaction in social_reaction_plan.witness_reactions:
                if reaction.reaction_category in suspicious_categories:
                    noteworthy_reaction = True
                    self.state.event_log.append(
                        StoryModeSpellcastCausedSuspicionEvent(
                            witness_id=reaction.witness_id,
                            spell_id=intent.spell_id,
                            reaction_category=reaction.reaction_category,
                        )
                    )
            if not noteworthy_reaction:
                self.state.event_log.append(
                    StoryModeSpellcastIgnoredEvent(
                        actor_id=intent.actor_id,
                        spell_id=intent.spell_id,
                        reason='Witnesses noticed the spellcasting but did not create meaningful social fallout.',
                    )
                )
            if social_reaction_plan.escalation is not None and social_reaction_plan.escalation.recommended:
                self.state.event_log.append(
                    StoryModeSpellcastEscalationRecommendedEvent(
                        actor_id=intent.actor_id,
                        spell_id=intent.spell_id,
                        decision=social_reaction_plan.escalation,
                    )
                )
                if social_reaction_plan.escalation.mode_switch_decision is not None:
                    self.apply_mode_switch_decision(social_reaction_plan.escalation.mode_switch_decision)
        else:
            self.state.event_log.append(
                StoryModeSpellcastIgnoredEvent(
                    actor_id=intent.actor_id,
                    spell_id=intent.spell_id,
                    reason='No witnesses perceived the casting act or any meaningful spell effect.',
                )
            )
        if self.social_engine is not None:
            social_state, synced_exploration_state, social_events, social_entries, social_notes, social_open_loops = self.social_engine.log_story_spellcast_incident(
                self.story_state.social_state,
                exploration_state=self.story_state.exploration_state,
                context=context,
                witness_packet=witness_packet,
                social_reaction_plan=social_reaction_plan,
                clock_seconds=self.state.clock_seconds,
                location_id=self.story_state.canonical_location_id,
                scene_id=self.story_state.current_scene_id,
            )
            self.story_state.social_state = social_state
            if synced_exploration_state is not None:
                self.story_state.exploration_state = synced_exploration_state
            self.state.event_log.extend(social_events)
            if social_entries:
                self._append_transcript(social_entries)
            for note in social_notes:
                self._merge_metadata_list('scene_state_notes', (note,))
            if social_open_loops:
                self.story_state.open_loops = unique_strings(self.story_state.open_loops + social_open_loops)
        resolution = StoryModeCastResolution(
            attempt=context.attempt,
            context=context,
            witness_packet=witness_packet,
            observer_results=observer_results,
            social_reaction_plan=social_reaction_plan,
            remained_in_storytelling=(self.story_state.runtime_mode == RuntimeMode.STORYTELLING),
            time_advanced_seconds=max(0, self.state.clock_seconds - clock_before),
        )
        self.state.event_log.append(StoryModeSpellcastResolvedEvent(resolution=resolution))
        self._sync_memory_files()
        return self.view_for_controller(controller_id)

    def submit_improvised_action(self, controller_id: str, declaration: str):
        binding = self.encounter_session.control_runtime.validate_controller(controller_id)
        if binding.role.value == 'dm':
            raise EncounterPermissionError('The DM client observes adjudication but does not submit improvised player actions in this demo.')
        pending_check = self._normalized_pending_check()
        if pending_check is not None:
            if pending_check.controller_id == controller_id:
                raise EncounterPermissionError('Resolve your pending story check before taking a new storytelling action.')
            raise EncounterPermissionError(self._pending_check_waiting_message(pending_check))
        if self.adjudication_planner is None:
            raise EncounterValidationError('No DM adjudication planner is configured for this session.')
        actor_id = self._owned_actor_for_controller(controller_id)
        documents = self.select_relevant_documents()
        context = self._build_adjudication_context(controller_id=controller_id, actor_id=actor_id, declaration=declaration)
        self.state.event_log.append(AdjudicationRequestedEvent(controller_id=controller_id, actor_id=actor_id, runtime_mode=self.story_state.runtime_mode, declaration=declaration))
        self.state.event_log.append(AdjudicationContextBuiltEvent(actor_id=actor_id, runtime_mode=self.story_state.runtime_mode, scene_id=self.story_state.current_scene_id, location_id=self.story_state.canonical_location_id, document_ids=tuple(document.doc_id for document in documents)))
        self._emit_llm_feedback(controller_id, 'info', 'DM is thinking...')
        stream_handler = self._story_llm_stream_handler(controller_id)
        retry_handler = self._story_llm_retry_handler(controller_id, request_label='DM adjudication response')

        def _validation_callback(plan):
            self.state.event_log.append(AdjudicationPlanReceivedEvent(actor_id=actor_id, plan=plan))
            try:
                validated = self.adjudication_runtime.validate_plan(
                    self.state,
                    runtime_mode=self.story_state.runtime_mode,
                    controller_id=controller_id,
                    actor_id=actor_id,
                    plan=plan,
                )
            except EncounterValidationError as exc:
                self.state.event_log.append(AdjudicationPlanRejectedEvent(actor_id=actor_id, reason=str(exc)))
                raise DMRuntimeError(str(exc)) from exc
            self.state.event_log.append(AdjudicationPlanValidatedEvent(actor_id=actor_id, plan=validated))
            return validated

        try:
            plan, events = self.adjudication_planner.plan_action(
                context,
                documents,
                validation_callback=_validation_callback,
                stream_handler=stream_handler,
                retry_handler=retry_handler,
            )
        finally:
            flush = getattr(stream_handler, 'flush', None)
            if callable(flush):
                flush()
        self.state.event_log.extend(events)
        result = self.adjudication_runtime.execute_plan(
            self.state,
            runtime_mode=self.story_state.runtime_mode,
            controller_id=controller_id,
            actor_id=actor_id,
            plan=plan,
        )
        self._apply_adjudication_result(actor_id=actor_id, result=result)
        return self.view_for_controller(controller_id)

    def _apply_adjudication_result(self, *, actor_id: str, result) -> None:
        if result.clarification_error is not None:
            self.state.event_log.append(
                ClarificationRequestedEvent(
                    actor_id=actor_id,
                    question_to_player=str(result.clarification_error),
                    missing_parameters=(),
                )
            )
            raise result.clarification_error
        if result.transcript_entries:
            self._append_transcript(result.transcript_entries)
        self.story_state.pending_adjudication = None
        self.story_state.pending_exploration_check = None
        if result.pending_check is not None:
            controller_id = self.encounter_session.control_runtime.controller_for_actor(result.pending_check.actor_id)
            pending = replace(result.pending_check, controller_id=controller_id)
            self.story_state.pending_check = pending
            self.story_state.pending_adjudication = result.pending_adjudication
            self.state.event_log.append(StoryCheckPromptedEvent(request=pending))
        if result.scene_state_notes:
            existing = tuple(item for item in self.story_state.metadata.get('scene_state_notes', '').split('|') if item)
            self.story_state.metadata['scene_state_notes'] = '|'.join(existing + result.scene_state_notes)
        if result.terrain_change_lines:
            existing_terrain = tuple(item for item in self.story_state.metadata.get('terrain_change_lines', '').split('|') if item)
            self.story_state.metadata['terrain_change_lines'] = '|'.join(existing_terrain + result.terrain_change_lines)
        if result.mode_switch_decision is not None:
            self.apply_mode_switch_decision(result.mode_switch_decision)
        self._sync_memory_files()

    def resolve_pending_check(self, controller_id: str):
        pending = self._normalized_pending_check()
        if pending is None:
            raise EncounterPermissionError('There is no pending story check for this controller.')
        if pending.controller_id != controller_id:
            raise EncounterPermissionError(f'There is no pending story check for this controller. {self._pending_check_waiting_message(pending)}')
        resolution, _events = self.encounter_session.control_runtime.kernel.resolve_check_consumer(
            self.state,
            pending.check_request,
            apply=True,
        )
        random_counter_used = next((event.random_counter_used for event in _events if isinstance(event, CheckRolledEvent)), self.state.random_counter)
        pending_exploration = self.story_state.pending_exploration_check
        pending_adjudication = self.story_state.pending_adjudication
        self.story_state.pending_check = None
        self.story_state.pending_exploration_check = None
        self.story_state.pending_adjudication = None
        if pending_exploration is not None:
            new_state, events = self._require_exploration_engine().resolve_pending_exploration_check(
                self.story_state.exploration_state,
                encounter_state=self.state,
                pending=pending_exploration,
                check_request=pending.check_request,
                d20_result=resolution.result,
                random_counter_used=random_counter_used,
            )
            self._commit_exploration_result(new_state, list(events))
            return self.view_for_controller(controller_id)
        self.state.event_log.append(
            StoryCheckResolvedEvent(
                request_id=pending.request_id,
                actor_id=pending.actor_id,
                scene_id=self.story_state.current_scene_id,
                ability=pending.check_request.ability,
                skill_name=pending.check_request.skill_name,
                dc=pending.check_request.dc,
                selected_roll=resolution.result.selected_roll,
                total=resolution.result.total,
                success=bool(resolution.result.success),
                interacting_with_actor_id=pending.check_request.interacting_with_actor_id,
            )
        )
        if pending_adjudication is not None:
            result = self.adjudication_runtime.resolve_pending_check(
                self.state,
                pending=pending_adjudication,
                success=bool(resolution.result.success),
            )
            self._apply_adjudication_result(actor_id=pending.actor_id, result=result)
            return self.view_for_controller(controller_id)
        if self.dm_runtime is None:
            return self.view_for_controller(controller_id)
        documents = self.select_relevant_documents()
        self._emit_llm_feedback(controller_id, 'info', 'DM is resolving the check...')
        stream_handler = self._story_llm_stream_handler(controller_id)
        retry_handler = self._story_llm_retry_handler(controller_id, request_label='DM check-resolution response')
        try:
            decision, events = self.dm_runtime.plan_check_outcome(
                self.storytelling_context(),
                documents,
                pending_check=pending,
                result_total=resolution.result.total,
                success=bool(resolution.result.success),
                selected_roll=resolution.result.selected_roll,
                declaration=pending.reason,
                available_combatant_actor_ids=self._available_story_combatant_actor_ids(),
                actors_with_resolved_scene_checks=self._actors_with_resolved_story_checks_in_scene(),
                stream_handler=stream_handler,
                retry_handler=retry_handler,
            )
        finally:
            flush = getattr(stream_handler, 'flush', None)
            if callable(flush):
                flush()
        self.state.event_log.extend(events)
        self._apply_story_turn_decision(decision)
        return self.view_for_controller(controller_id)

    def _apply_story_turn_decision(self, decision: StoryTurnDecision, *, triggering_declaration: str | None = None) -> None:
        if decision.check_request is not None and decision.mode_switch_decision is not None and decision.mode_switch_decision.decision_type == ModeSwitchAction.ENTER_COMBAT:
            raise EncounterValidationError('A storytelling turn cannot both request a check and enter combat immediately.')
        transcript_entries = _without_echoed_player_declaration(decision.transcript_entries, triggering_declaration)
        if transcript_entries:
            self._append_transcript(transcript_entries)
        if decision.scene_update is not None:
            self._apply_scene_update(decision.scene_update)
        self.story_state.pending_adjudication = None
        self.story_state.pending_exploration_check = None
        if decision.check_request is not None:
            controller_id = self.encounter_session.control_runtime.controller_for_actor(decision.check_request.actor_id)
            pending = replace(decision.check_request, controller_id=controller_id)
            self.story_state.pending_check = pending
            self.state.event_log.append(StoryCheckPromptedEvent(request=pending))
        if decision.mode_switch_decision is not None:
            self.apply_mode_switch_decision(decision.mode_switch_decision)
        if decision.memory_note:
            self.story_state.metadata['last_memory_note'] = decision.memory_note
        self._sync_memory_files()

    def _append_transcript(self, entries: tuple[StoryTranscriptEntry, ...]) -> None:
        transcript = list(self.story_state.transcript_entries)
        transcript.extend(entries)
        self.story_state.transcript_entries = tuple(transcript[-40:])
        self.state.event_log.append(StoryTranscriptAppendedEvent(entries=entries))
        public_lines = [entry.text for entry in entries if entry.visibility == StoryTranscriptVisibility.PUBLIC]
        if public_lines:
            self.story_state.recent_summary = public_lines[-1]

    def _apply_scene_update(self, update: StorySceneUpdate) -> None:
        if update.scene_id is not None:
            self.story_state.current_scene_id = update.scene_id
        if update.location_id is not None:
            self.story_state.canonical_location_id = update.location_id
        if update.summary is not None:
            self.story_state.recent_summary = update.summary
        if update.open_loops is not None:
            self.story_state.open_loops = update.open_loops
        if update.party_goals is not None:
            self.story_state.current_party_goals = update.party_goals
        if update.party_beliefs is not None:
            self.story_state.metadata['party_beliefs'] = '|'.join(update.party_beliefs)
        self.state.event_log.append(StorySceneUpdatedEvent(scene_id=update.scene_id, location_id=update.location_id, summary=update.summary))
        self._refresh_exploration_context(sync_memory=False)

    def apply_mode_switch_decision(self, decision: ModeSwitchDecision) -> None:
        self.state.event_log.append(
            ModeSwitchRequestedEvent(
                action=decision.decision_type,
                from_mode=self.story_state.runtime_mode,
                rationale=decision.reason,
            )
        )
        if decision.decision_type == ModeSwitchAction.STAY_IN_STORYTELLING:
            self.story_state.runtime_mode = RuntimeMode.STORYTELLING
            return
        if decision.decision_type == ModeSwitchAction.REMAIN_IN_COMBAT:
            self.story_state.runtime_mode = RuntimeMode.COMBAT
            return
        if decision.decision_type == ModeSwitchAction.ENTER_COMBAT:
            if decision.enter_combat_plan is None:
                raise EncounterValidationError('Enter-combat decision is missing its combat plan.')
            self.enter_combat(decision.enter_combat_plan)
            return
        if decision.decision_type == ModeSwitchAction.EXIT_COMBAT:
            if decision.exit_combat_plan is None:
                raise EncounterValidationError('Exit-combat decision is missing its exit plan.')
            self.exit_combat(decision.exit_combat_plan)
            return
        raise EncounterValidationError('Unknown mode-switch action.')

    def enter_combat(self, plan: EnterCombatPlan, *, surprised_actor_ids: tuple[str, ...] = ()) -> None:
        if self.story_state.runtime_mode == RuntimeMode.COMBAT:
            raise EncounterValidationError('Session is already in combat mode.')
        for actor_id in plan.participant_ids:
            if actor_id not in self.state.actors:
                raise EncounterValidationError(f'Enter-combat plan references unknown actor: {actor_id}.')
        self.story_state.pending_check = None
        self.story_state.pending_exploration_check = None
        self.story_state.pending_adjudication = None
        self.state.event_log.append(EnterCombatPlannedEvent(plan=plan))
        result = self.encounter_session.control_runtime.dispatch_intent(
            self.state,
            StartEncounterIntent(participant_actor_ids=plan.participant_ids, surprised_actor_ids=surprised_actor_ids),
        )
        self.story_state.runtime_mode = RuntimeMode.COMBAT
        if plan.scene_id is not None:
            self.story_state.current_scene_id = plan.scene_id
        if plan.location_id is not None:
            self.story_state.canonical_location_id = plan.location_id
        self.story_state.active_battlefield_map_id = plan.battlefield_map_id
        self.state.event_log.append(
            CombatStartedEvent(
                participant_actor_ids=plan.participant_ids,
                initiative_order=result.state.initiative_order,
                rationale=plan.reason,
            )
        )
        self._refresh_exploration_context(sync_memory=False)
        self._sync_memory_files()

    def exit_combat(self, plan: ExitCombatPlan) -> None:
        if self.story_state.runtime_mode != RuntimeMode.COMBAT:
            raise EncounterValidationError('Session is not currently in combat mode.')
        if self.state.pending_reaction_window is not None:
            raise EncounterValidationError('Cannot exit combat while a reaction window is open.')
        self.story_state.pending_adjudication = None
        self.story_state.pending_exploration_check = None
        self.story_state.combat_transition = None
        self.state.event_log.append(CombatEndedEvent(rationale=plan.reason))
        self.state.phase = EncounterPhase.READY
        self.state.round_number = 0
        self.state.turn_index = 0
        self.state.active_actor_id = None
        self.state.initiative_order = ()
        self.state.winning_side = None
        self.story_state.runtime_mode = RuntimeMode.STORYTELLING
        if plan.resulting_scene_id is not None:
            self.story_state.current_scene_id = plan.resulting_scene_id
        if plan.follow_up_summary:
            self.story_state.recent_summary = plan.follow_up_summary
        self.state.event_log.append(
            ReturnedToStorytellingEvent(scene_id=self.story_state.current_scene_id, rationale=plan.reason)
        )
        self._refresh_exploration_context(sync_memory=False)
        self._sync_memory_files()

    def _process_due_reinforcements(self) -> None:
        if self.story_state.runtime_mode != RuntimeMode.COMBAT:
            return
        transition = self.story_state.combat_transition
        if transition is None:
            return
        entered_ids = set(transition.entered_reinforcement_ids)
        updated = False
        for plan in transition.reinforcement_plans:
            if plan.reinforcement_id in entered_ids:
                continue
            if self.state.round_number < plan.rounds_until_arrival + 1:
                continue
            actors = self.hostile_escalation_engine.reinforcement_actors_for_plan(plan, battlefield=self.state.battlefield)
            actor_ids: list[str] = []
            for actor, spec in zip(actors, plan.participant_specs):
                self.state.actors[actor.actor_id] = actor
                self.encounter_session.control_runtime.actor_controllers[actor.actor_id] = 'dm'
                actor_ids.append(actor.actor_id)
                self.state.event_log.append(StoryNPCCombatantSynthesizedEvent(combatant=spec))
                if actor.fallback_synthesized:
                    self.state.event_log.append(StoryNPCCombatantFallbackUsedEvent(combatant=spec))
            for actor_id in actor_ids:
                self.encounter_session.control_runtime.kernel.insert_reinforcement_into_initiative(self.state, actor_id=actor_id)
            self.state.event_log.append(
                ReinforcementEnteredEvent(
                    reinforcement_id=plan.reinforcement_id,
                    actor_ids=tuple(actor_ids),
                    round_number=self.state.round_number,
                    entry_zone_id=plan.entry_zone_id,
                )
            )
            self._merge_metadata_list('scene_state_notes', (f'Reinforcement arrived: {plan.label}.',))
            entered_ids.add(plan.reinforcement_id)
            updated = True
        if updated:
            self.story_state.combat_transition = replace(transition, entered_reinforcement_ids=tuple(sorted(entered_ids)))

    def _process_due_social_propagation(self) -> None:
        if self.social_engine is None:
            return
        social_state, social_events, social_entries, social_notes, social_open_loops = self.social_engine.process_due_propagation(
            self.story_state.social_state,
            clock_seconds=self.state.clock_seconds,
            scene_id=self.story_state.current_scene_id,
            location_id=self.story_state.canonical_location_id,
        )
        if not social_events and not social_entries and not social_notes and not social_open_loops:
            return
        self.story_state.social_state = social_state
        self.state.event_log.extend(social_events)
        if self.story_state.exploration_state is not None:
            self.story_state.exploration_state = self.social_engine.sync_exploration_projection(self.story_state.exploration_state, self.story_state.social_state)
        if social_entries:
            self._append_transcript(social_entries)
        for note in social_notes:
            self._merge_metadata_list('scene_state_notes', (note,))
        if social_open_loops:
            self.story_state.open_loops = unique_strings(self.story_state.open_loops + social_open_loops)

    def _sync_memory_files(self) -> None:
        self._process_due_social_propagation()
        self._sync_progression_state()
        occupants = tuple(f'{actor.actor_id}: {actor.name}' for actor in self.state.actors.values() if actor.side == ActorSide.PLAYER or self.story_state.runtime_mode == RuntimeMode.COMBAT)
        recent_public = tuple(entry.text for entry in self.story_state.transcript_entries[-8:] if entry.visibility == StoryTranscriptVisibility.PUBLIC)
        hidden_lines = tuple(entry.text for entry in self.story_state.transcript_entries[-4:] if entry.visibility == StoryTranscriptVisibility.DM_ONLY)
        terrain_change_lines = tuple(item for item in self.story_state.metadata.get('terrain_change_lines', '').split('|') if item)
        scene_state_notes = tuple(item for item in self.story_state.metadata.get('scene_state_notes', '').split('|') if item)
        exploration_state = self.story_state.exploration_state
        exploration_notes: tuple[str, ...] = ()
        exploration_hidden_lines: tuple[str, ...] = ()
        if exploration_state is not None:
            if exploration_state.marching_order:
                ordered = ' -> '.join(
                    f"{self._format_actor_reference(entry.actor_id)} ({entry.position.value})"
                    for entry in sorted(exploration_state.marching_order, key=lambda item: item.ordinal)
                )
                exploration_notes = exploration_notes + (f'Marching order: {ordered}',)
            if exploration_state.camp_active:
                active_shift = self.exploration_engine.active_watch_shift_index(exploration_state, encounter_state=self.state) if self.exploration_engine is not None else None
                watchers = self.exploration_engine.active_watchers(exploration_state, encounter_state=self.state) if self.exploration_engine is not None else ()
                watcher_text = ', '.join(self._format_actor_reference(actor_id) for actor_id in watchers) or 'none'
                exploration_notes = exploration_notes + (f'Camp active; watch shift {active_shift if active_shift is not None else 0}: {watcher_text}',)
            if self.exploration_engine is not None:
                trap_lines = tuple(
                    f'Trap {definition.title}: {runtime.status.value}; {(runtime.last_summary or definition.hidden_summary)}'
                    for definition, runtime in self.exploration_engine.visible_trap_states(exploration_state, dm_view=True)
                )
                puzzle_lines = tuple(
                    f'Puzzle {definition.title}: {runtime.status.value}; {(runtime.last_summary or definition.summary)}'
                    for definition, runtime in self.exploration_engine.visible_puzzle_states(exploration_state, dm_view=True)
                )
                npc_lines = tuple(
                    f'NPC {npc_state.display_name}: {npc_state.attitude.value}; {npc_state.current_stance}'
                    for npc_state in self.exploration_engine.visible_npc_states(exploration_state)
                )
                exploration_hidden_lines = trap_lines + puzzle_lines + npc_lines
        social_projection_lines = self.social_engine.visible_projection_lines(self.story_state.social_state, dm_view=True) if self.social_engine is not None else ()
        social_dm_lines = self.social_engine.dm_status_lines(self.story_state.social_state) if self.social_engine is not None else ()
        progression_lines = self.progression_engine.visible_projection_lines(self.story_state.progression_state, actor_snapshots=self._progression_actor_snapshots(), dm_view=True)
        progression_dm_lines = self.progression_engine.dm_status_lines(self.story_state.progression_state, actor_snapshots=self._progression_actor_snapshots())
        advancement_lines = self._advancement_writeback_lines()
        self.memory_writer.write_campaign_state(
            CampaignStateSummary(
                campaign=self.story_state.campaign_id,
                title='Campaign State',
                current_location=self.story_state.canonical_location_id or 'unknown',
                party_goal_lines=self.story_state.current_party_goals,
                unresolved_consequence_lines=self.story_state.open_loops,
                party_belief_lines=tuple(item for item in self.story_state.metadata.get('party_beliefs', '').split('|') if item),
                recent_change_lines=(recent_public + social_projection_lines + advancement_lines)[-6:],
                progression_lines=progression_lines + progression_dm_lines[-4:] + advancement_lines[-4:],
            )
        )
        self.memory_writer.write_open_loops(
            OpenLoopsSummary(
                campaign=self.story_state.campaign_id,
                title='Open Loops',
                loop_lines=self.story_state.open_loops or ('No unresolved hooks recorded.',),
            )
        )
        discovered = unique_strings(tuple(item for item in self.story_state.metadata.get('discovered_secrets', '').split('|') if item) + ((exploration_state.known_discoveries) if exploration_state is not None else ()))
        self.memory_writer.write_discovered_secrets(
            DiscoveredSecretsSummary(
                campaign=self.story_state.campaign_id,
                title='Discovered Secrets',
                secret_lines=discovered or ('No confirmed secrets logged yet.',),
            )
        )
        self.memory_writer.write_scene_state(
            SceneState(
                scene_id=self.story_state.current_scene_id,
                campaign=self.story_state.campaign_id,
                title=self.story_state.current_scene_id.replace('-', ' ').title(),
                canonical_location=self.story_state.canonical_location_id or 'unknown',
                occupant_lines=occupants,
                terrain_change_lines=terrain_change_lines + exploration_notes,
                discovered_clue_lines=tuple(item for item in discovered[-4:]),
                triggered_event_lines=recent_public[-4:],
                unresolved_tension_lines=self.story_state.open_loops,
                exit_lines=self.story_state.current_party_goals,
                described_to_players_lines=recent_public[-6:],
                hidden_state_lines=hidden_lines + scene_state_notes[-4:] + exploration_hidden_lines[-6:] + social_dm_lines[-6:],
            )
        )
        self.memory_writer.write_session_log(
            SessionLogEntry(
                session_id=self.story_state.session_log_id,
                campaign=self.story_state.campaign_id,
                title='Demo Session Log',
                recap_lines=recent_public[-8:] or ('Session initialized.',),
                changes_lines=(terrain_change_lines + scene_state_notes + exploration_notes + social_projection_lines + social_dm_lines + advancement_lines)[-8:],
                unresolved_hook_lines=self.story_state.open_loops,
                next_scene_lines=(self.story_state.current_scene_id,),
                progression_lines=progression_lines + progression_dm_lines[-4:] + advancement_lines[-4:],
            )
        )
        for npc_id in ('gundren-rockseeker', 'sildar-hallwinter'):
            if npc_id not in self._visible_npc_ids() and npc_id not in self.story_state.current_scene_id:
                continue
            npc_state = exploration_state.npc_states.get(npc_id) if exploration_state is not None else None
            recent_interactions = recent_public[-3:]
            if npc_state is not None and npc_state.last_summary:
                recent_interactions = (npc_state.last_summary,) + recent_interactions
            trust_lines: tuple[str, ...] = ()
            warning_lines = ('Stay inside the current reveal ladder.',)
            if self.social_engine is not None:
                trust_lines, social_recent_lines, social_warning_lines = self.social_engine.npc_playbook_lines(self.story_state.social_state, npc_id=npc_id)
                if social_recent_lines:
                    recent_interactions = social_recent_lines + recent_interactions
                if social_warning_lines:
                    warning_lines = warning_lines + social_warning_lines
            self.memory_writer.write_npc_playbook(
                NpcPlaybook(
                    npc_id=npc_id,
                    campaign=self.story_state.campaign_id,
                    title=f'{npc_id.replace('-', ' ').title()} Playbook',
                    voice_lines=('Keep the voice aligned with the canonical NPC markdown file.',),
                    current_stance=(npc_state.current_stance if npc_state is not None else 'Cautiously cooperative.'),
                    trust_lines=trust_lines,
                    reveal_lines=('Reveal only what the current scene makes immediately relevant.',),
                    withholding_lines=('Do not volunteer hidden campaign spoilers.',),
                    recent_interaction_lines=recent_interactions or ('No direct interaction yet.',),
                    local_goal_lines=self.story_state.current_party_goals or ('Move the scene toward Phandalin.',),
                    warning_lines=warning_lines,
                )
            )
        self.refresh_retrieval_index()

    def _extract_markdown_section(self, body: str, heading: str) -> str:
        target = f'# {heading}'
        lines = body.splitlines()
        collecting = False
        collected: list[str] = []
        for line in lines:
            if line.strip() == target:
                collecting = True
                continue
            if collecting and line.startswith('# '):
                break
            if collecting:
                collected.append(line)
        return '\n'.join(line.strip() for line in collected if line.strip()).strip()










































