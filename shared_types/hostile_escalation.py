from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .battlefield import BattlefieldState
from .exploration import NpcAttitude


class HostileEscalationOutcome(str, Enum):
    REMAIN_IN_STORY_MODE = 'remain_in_story_mode'
    ESCALATE_TO_COMBAT = 'escalate_to_combat'
    ESCALATE_TO_COMBAT_WITH_SURPRISE_CHECK = 'escalate_to_combat_with_surprise_check'
    ESCALATE_TO_COMBAT_WITH_REINFORCEMENT_TIMER = 'escalate_to_combat_with_reinforcement_timer'
    CLARIFICATION_REQUIRED = 'clarification_required'


class HostileActionKind(str, Enum):
    HARMFUL_SPELL = 'harmful_spell'
    ATTACK_ATTEMPT = 'attack_attempt'
    GRAPPLE_ATTEMPT = 'grapple_attempt'
    BLOCK_PATH = 'block_path'
    INITIATIVE_SENSITIVE_STANDOFF = 'initiative_sensitive_standoff'


class CombatParticipantGoal(str, Enum):
    ATTACK = 'attack'
    FLEE = 'flee'
    PROTECT = 'protect'
    SURRENDER = 'surrender'
    ARREST = 'arrest'
    DELAY = 'delay'
    INTERPOSE = 'interpose'
    CALL_REINFORCEMENTS = 'call_reinforcements'
    SUBDUE = 'subdue'
    BYSTAND = 'bystand'


class SynthesizedCombatantSourceKind(str, Enum):
    EXISTING_ACTOR = 'existing_actor'
    FULL_STATBLOCK = 'full_statblock'
    LOCAL_NPC_DATA = 'local_npc_data'
    ARCHETYPE_FALLBACK = 'archetype_fallback'


class FallbackNpcCombatArchetype(str, Enum):
    COMMONER_NONCOMBATANT = 'commoner_noncombatant'
    GUARD_WATCHMAN = 'guard_watchman'
    VETERAN_BODYGUARD = 'veteran_bodyguard'
    SCOUT = 'scout'
    MAGE_APPRENTICE = 'mage_apprentice'
    PRIEST_TEMPLE_AGENT = 'priest_temple_agent'
    NOBLE_MERCHANT_CIVILIAN = 'noble_merchant_civilian'


class AdHocEncounterSceneKind(str, Enum):
    AUTHORED_MAP = 'authored_map'
    STRUCTURED_LOCATION = 'structured_location'
    FALLBACK_TAVERN_COMMON_ROOM = 'fallback_tavern_common_room'
    FALLBACK_OPEN_AREA = 'fallback_open_area'


@dataclass(frozen=True)
class StoryCombatantContext:
    source_label: str
    source_npc_id: str | None = None
    source_kind: SynthesizedCombatantSourceKind = SynthesizedCombatantSourceKind.EXISTING_ACTOR
    fallback_archetype: FallbackNpcCombatArchetype | None = None
    current_goal: CombatParticipantGoal = CombatParticipantGoal.ATTACK
    attitude: NpcAttitude | None = None
    current_stance: str | None = None
    faction_tags: tuple[str, ...] = ()
    authority_tags: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    synthesized: bool = False


@dataclass(frozen=True)
class SynthesizedCombatantSpec:
    actor_id: str
    display_name: str
    source_npc_id: str | None
    monster_id: str | None
    source_kind: SynthesizedCombatantSourceKind
    current_goal: CombatParticipantGoal
    attitude: NpcAttitude | None = None
    current_stance: str | None = None
    faction_tags: tuple[str, ...] = ()
    authority_tags: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    fallback_archetype: FallbackNpcCombatArchetype | None = None
    source_label: str = ''


@dataclass(frozen=True)
class ReinforcementPlan:
    reinforcement_id: str
    label: str
    source_label: str
    rounds_until_arrival: int
    entry_zone_id: str
    trigger_summary: str
    participant_specs: tuple[SynthesizedCombatantSpec, ...] = ()
    public_visible: bool = False
    cancellable: bool = True


@dataclass(frozen=True)
class AdHocEncounterScenePlan:
    map_id: str
    name: str
    scene_kind: AdHocEncounterSceneKind
    battlefield: BattlefieldState
    fallback_used: bool
    summary: str
    primary_hostile_zone_ids: tuple[str, ...] = ()
    reinforcement_entry_zone_ids: tuple[str, ...] = ()
    bystander_zone_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CombatTransitionState:
    reason: str
    source_scene_id: str | None
    source_location_id: str | None
    opening_action_summary: str
    battlefield_map_id: str
    scene_kind: AdHocEncounterSceneKind
    fallback_scene: bool
    synthesized_actor_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    reinforcement_plans: tuple[ReinforcementPlan, ...] = ()
    entered_reinforcement_ids: tuple[str, ...] = ()
    bystander_npc_ids: tuple[str, ...] = ()
    metadata_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class HostileEscalationDecision:
    outcome: HostileEscalationOutcome
    action_kind: HostileActionKind
    reason: str
    hostile_actor_id: str
    target_actor_id: str | None = None
    target_npc_id: str | None = None
    scene_tension: str = 'neutral'
    order_now_matters: bool = False
    witnesses_notice: bool = False
    clarification_prompt: str = ''
    participant_actor_ids: tuple[str, ...] = ()
    synthesized_combatants: tuple[SynthesizedCombatantSpec, ...] = ()
    noncombatant_npc_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    surprised_actor_ids: tuple[str, ...] = ()
    reinforcement_plans: tuple[ReinforcementPlan, ...] = ()
    scene_plan: AdHocEncounterScenePlan | None = None
    transition_state: CombatTransitionState | None = None
    opening_action_summary: str = ''
