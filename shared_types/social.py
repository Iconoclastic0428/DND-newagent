from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .exploration import NpcAttitude, SocialApproachType


class InfluenceWillingnessState(str, Enum):
    WILLING = 'willing'
    HESITANT = 'hesitant'
    REFUSING = 'refusing'


class SocialIncidentCategory(str, Enum):
    WITNESSED_SPELLCASTING = 'witnessed_spellcasting'
    SUSPICIOUS_SPELLCASTING = 'suspicious_spellcasting'
    HOSTILE_SPELLCASTING = 'hostile_spellcasting'
    VIOLENCE = 'violence'
    THREAT = 'threat'
    THEFT = 'theft'
    TRESPASS = 'trespass'
    DECEPTION_EXPOSED = 'deception_exposed'
    INTIMIDATION = 'intimidation'
    AID_OR_HEALING = 'aid_or_healing'
    RESCUE = 'rescue'
    TABOO_VIOLATION = 'taboo_violation'
    CONTRACT_BROKEN = 'contract_broken'
    PROMISE_KEPT = 'promise_kept'
    PUBLIC_EMBARRASSMENT = 'public_embarrassment'
    FACTION_INSULT = 'faction_insult'
    GUARD_INTERFERENCE = 'guard_interference'
    UNAUTHORIZED_MAGIC = 'unauthorized_magic'
    ENCHANTMENT_MAGIC_USED = 'enchantment_magic_used'
    NECROMANCY_OR_TABOO_MAGIC_USED = 'necromancy_or_taboo_magic_used'
    SOCIAL_INFLUENCE = 'social_influence'


class SocialIncidentSeverity(str, Enum):
    TRIVIAL = 'trivial'
    LOW = 'low'
    MODERATE = 'moderate'
    HIGH = 'high'
    EXTREME = 'extreme'


class SocialPublicityScope(str, Enum):
    PRIVATE = 'private'
    WITNESSES_ONLY = 'witnesses_only'
    PARTY_KNOWN = 'party_known'
    LOCAL_RUMOR = 'local_rumor'
    AUTHORITY_KNOWN = 'authority_known'
    SETTLEMENT_WIDE = 'settlement_wide'


class MagicalNormTag(str, Enum):
    OPEN_MAGIC = 'open_magic'
    GUARDED_MAGIC = 'guarded_magic'
    RESTRICTED_MAGIC = 'restricted_magic'
    TABOO_MAGIC = 'taboo_magic'
    ANTI_ENCHANTMENT = 'anti_enchantment'
    ANTI_NECROMANCY = 'anti_necromancy'
    ANTI_SUMMONING = 'anti_summoning'
    TEMPLE_SANCTIONED_MAGIC = 'temple_sanctioned_magic'
    NOBLE_COURT_DECORUM = 'noble_court_decorum'
    ANTI_WEAPONS_IN_AUDIENCE_CHAMBER = 'anti_weapons_in_audience_chamber'
    PUBLIC_ORDER_SENSITIVE = 'public_order_sensitive'
    ANTI_PUBLIC_THREATS = 'anti_public_threats'
    ANTI_PROPERTY_DAMAGE = 'anti_property_damage'
    ANTI_VIGILANTE_VIOLENCE = 'anti_vigilante_violence'


class WitnessReactionCategory(str, Enum):
    NONE = 'none'
    IGNORE = 'ignore'
    CURIOUS = 'curious'
    MILDLY_WARY = 'mildly_wary'
    SUSPICIOUS = 'suspicious'
    ALARMED = 'alarmed'
    CONFRONTATIONAL = 'confrontational'
    REPORT_TO_AUTHORITY = 'report_to_authority'
    HOSTILE = 'hostile'
    ESCALATE_TO_COMBAT_CANDIDATE = 'escalate_to_combat_candidate'


class SocialKnowledgeAudience(str, Enum):
    DM_ONLY = 'dm_only'
    PARTY_KNOWN = 'party_known'
    PUBLIC = 'public'


class SocialPropagationKind(str, Enum):
    FACTION_PROPAGATION = 'faction_propagation'
    AUTHORITY_REPORT = 'authority_report'
    LOCAL_RUMOR = 'local_rumor'
    SETTLEMENT_MEMORY = 'settlement_memory'


class NormScope(str, Enum):
    SETTLEMENT_DEFAULT = 'settlement_default'
    LOCATION = 'location'
    FACTION = 'faction'
    INSTITUTION = 'institution'
    NPC = 'npc'
    SCENE_OVERRIDE = 'scene_override'


class WitnessPerceptionLevel(str, Enum):
    NONE = 'none'
    HEARD_ONLY = 'heard_only'
    EFFECT_ONLY = 'effect_only'
    GLIMPSED = 'glimpsed'
    CLEAR_ACT = 'clear_act'


class SocialInterpretationCategory(str, Enum):
    HARMLESS = 'harmless'
    ODD = 'odd'
    RUDE = 'rude'
    SUSPICIOUS = 'suspicious'
    MANIPULATIVE = 'manipulative'
    HOSTILE = 'hostile'
    CRIMINAL = 'criminal'
    HEROIC = 'heroic'
    HOLY_SANCTIONED = 'holy_sanctioned'
    TABOO = 'taboo'
    FORGIVABLE = 'forgivable'
    ALARMING_BUT_NOT_HOSTILE = 'alarming_but_not_hostile'


class SocialImmediateReaction(str, Enum):
    NO_REACTION = 'no_reaction'
    NOTICES_BUT_IGNORES = 'notices_but_ignores'
    WATCHES_CLOSELY = 'watches_closely'
    BECOMES_WARY = 'becomes_wary'
    CONFRONTS = 'confronts'
    FLEES = 'flees'
    CALLS_AUTHORITY = 'calls_authority'
    REPORTS_LATER = 'reports_later'
    REFUSES_SERVICE = 'refuses_service'
    THREATENS = 'threatens'
    ESCALATES_TO_COMBAT_CANDIDATE = 'escalates_to_combat_candidate'


class PropagationStatus(str, Enum):
    SCHEDULED = 'scheduled'
    EXECUTED = 'executed'
    CANCELLED = 'cancelled'


@dataclass(frozen=True)
class NormMergePolicy:
    ordered_scopes: tuple[NormScope, ...] = (
        NormScope.SCENE_OVERRIDE,
        NormScope.NPC,
        NormScope.INSTITUTION,
        NormScope.FACTION,
        NormScope.LOCATION,
        NormScope.SETTLEMENT_DEFAULT,
    )


@dataclass(frozen=True)
class SocialRelationshipState:
    relationship_id: str
    source_id: str
    source_label: str
    target_id: str
    target_label: str
    current_stance: str = ''
    attitude: NpcAttitude = NpcAttitude.RESERVED
    willingness: InfluenceWillingnessState = InfluenceWillingnessState.HESITANT
    trust: int = 0
    suspicion: int = 0
    fear: int = 0
    respect: int = 0
    gratitude: int = 0
    leverage: int = 0
    obligation: int = 0
    temporary_tags: tuple[str, ...] = ()
    known_incident_ids: tuple[str, ...] = ()
    last_interaction_incident_id: str | None = None
    last_interaction_scene_id: str | None = None
    last_interaction_kind: SocialIncidentCategory | None = None
    last_updated_seconds: int = 0
    last_summary: str = ''


@dataclass(frozen=True)
class ReputationState:
    holder_id: str
    holder_label: str
    subject_id: str
    subject_label: str
    attitude: NpcAttitude = NpcAttitude.RESERVED
    trust: int = 0
    suspicion: int = 0
    fear: int = 0
    respect: int = 0
    gratitude: int = 0
    leverage: int = 0
    obligation: int = 0
    temporary_tags: tuple[str, ...] = ()
    known_incident_ids: tuple[str, ...] = ()
    last_updated_seconds: int = 0
    last_summary: str = ''


@dataclass(frozen=True)
class FactionRelationshipState:
    faction_id: str
    faction_label: str
    subject_id: str
    subject_label: str
    attitude: NpcAttitude = NpcAttitude.RESERVED
    trust: int = 0
    suspicion: int = 0
    fear: int = 0
    respect: int = 0
    gratitude: int = 0
    leverage: int = 0
    obligation: int = 0
    temporary_tags: tuple[str, ...] = ()
    known_incident_ids: tuple[str, ...] = ()
    last_updated_seconds: int = 0
    last_summary: str = ''


@dataclass(frozen=True)
class LocationAuthorityState:
    authority_state_id: str
    location_id: str
    location_label: str
    authority_id: str
    authority_label: str
    subject_id: str
    subject_label: str
    attitude: NpcAttitude = NpcAttitude.RESERVED
    trust: int = 0
    suspicion: int = 0
    fear: int = 0
    respect: int = 0
    gratitude: int = 0
    leverage: int = 0
    obligation: int = 0
    temporary_tags: tuple[str, ...] = ()
    known_incident_ids: tuple[str, ...] = ()
    current_alert: str = ''
    last_updated_seconds: int = 0
    last_summary: str = ''


@dataclass(frozen=True)
class KnownReputationProjection:
    projection_id: str
    audience: SocialKnowledgeAudience
    label: str
    summary: str
    related_incident_id: str | None = None
    last_updated_seconds: int = 0


@dataclass(frozen=True)
class NormProfile:
    norm_id: str
    applies_to_kind: str
    applies_to_id: str
    label: str
    scope: NormScope = NormScope.LOCATION
    priority: int = 0
    tags: tuple[MagicalNormTag, ...] = ()
    summary: str = ''
    helpful_magic_modifier: int = 0
    suspicious_magic_modifier: int = 0
    hostile_magic_modifier: int = 0


@dataclass(frozen=True)
class SocialIncident:
    incident_id: str
    category: SocialIncidentCategory
    scene_id: str | None
    location_id: str | None
    timestamp_seconds: int
    source_actor_ids: tuple[str, ...] = ()
    target_actor_ids: tuple[str, ...] = ()
    witness_ids: tuple[str, ...] = ()
    severity: SocialIncidentSeverity = SocialIncidentSeverity.LOW
    publicity_scope: SocialPublicityScope = SocialPublicityScope.WITNESSES_ONLY
    magic_tags: tuple[str, ...] = ()
    spell_tags: tuple[str, ...] = ()
    school_tags: tuple[str, ...] = ()
    visible_effect_tags: tuple[str, ...] = ()
    related_event_refs: tuple[str, ...] = ()
    dedupe_key: str = ''
    witness_record_ids: tuple[str, ...] = ()
    interpretation_record_ids: tuple[str, ...] = ()
    propagation_record_ids: tuple[str, ...] = ()
    consequence_template_ids: tuple[str, ...] = ()
    summary: str = ''
    public_summary: str = ''
    dm_note: str = ''


@dataclass(frozen=True)
class IncidentWitnessRecord:
    record_id: str
    incident_id: str
    witness_id: str
    display_name: str
    paying_attention: bool
    perceived_act: bool
    perceived_effect: bool
    heard_event: bool
    confidence: str
    perception_level: WitnessPerceptionLevel
    cared: bool
    hidden_from_party: bool
    archetype_id: str = ''
    applicable_norm_ids: tuple[str, ...] = ()
    norm_tags: tuple[str, ...] = ()
    summary: str = ''


@dataclass(frozen=True)
class IncidentInterpretationRecord:
    record_id: str
    incident_id: str
    witness_id: str
    interpretation: SocialInterpretationCategory
    immediate_reaction: SocialImmediateReaction
    reaction_category: WitnessReactionCategory
    summary: str
    public_text: str = ''
    private_note: str = ''


@dataclass(frozen=True)
class IncidentPropagationRecord:
    record_id: str
    incident_id: str
    propagation_kind: SocialPropagationKind
    source_id: str
    target_id: str
    due_at_seconds: int
    status: PropagationStatus
    summary: str
    public_visible: bool = False
    chain_id: str = ''


@dataclass(frozen=True)
class WitnessMemoryState:
    memory_id: str
    incident_id: str
    witness_id: str
    reaction_category: WitnessReactionCategory
    confidence: str
    cared: bool
    reportable: bool
    summary: str


@dataclass(frozen=True)
class SocialPropagationTask:
    task_id: str
    incident_id: str
    propagation_kind: SocialPropagationKind
    source_id: str
    target_id: str
    due_at_seconds: int
    summary: str
    public_visible: bool = False
    cancelled: bool = False
    related_record_id: str | None = None
    chain_id: str = ''


@dataclass(frozen=True)
class InfluenceCooldownState:
    cooldown_id: str
    actor_id: str
    npc_id: str
    approach: SocialApproachType
    until_seconds: int
    reason: str
    related_incident_id: str | None = None


InfluenceRetryCooldown = InfluenceCooldownState


@dataclass(frozen=True)
class IncidentNormEvaluation:
    witness_id: str
    incident_id: str
    applied_norm_ids: tuple[str, ...]
    applied_tags: tuple[str, ...]
    helpful_magic_modifier: int = 0
    suspicious_magic_modifier: int = 0
    hostile_magic_modifier: int = 0


@dataclass
class SocialRuntimeState:
    relationships: dict[str, SocialRelationshipState] = field(default_factory=dict)
    location_reputations: dict[str, ReputationState] = field(default_factory=dict)
    authority_reputations: dict[str, ReputationState] = field(default_factory=dict)
    faction_relationships: dict[str, FactionRelationshipState] = field(default_factory=dict)
    location_authorities: dict[str, LocationAuthorityState] = field(default_factory=dict)
    incidents: dict[str, SocialIncident] = field(default_factory=dict)
    incident_witness_records: dict[str, IncidentWitnessRecord] = field(default_factory=dict)
    incident_interpretations: dict[str, IncidentInterpretationRecord] = field(default_factory=dict)
    incident_propagations: dict[str, IncidentPropagationRecord] = field(default_factory=dict)
    incident_dedupe: dict[str, str] = field(default_factory=dict)
    witness_memories: dict[str, WitnessMemoryState] = field(default_factory=dict)
    norm_profiles: dict[str, NormProfile] = field(default_factory=dict)
    norm_merge_policy: NormMergePolicy = field(default_factory=NormMergePolicy)
    propagation_queue: dict[str, SocialPropagationTask] = field(default_factory=dict)
    retry_cooldowns: dict[str, InfluenceCooldownState] = field(default_factory=dict)
    known_projections: dict[str, KnownReputationProjection] = field(default_factory=dict)
