from __future__ import annotations

from dataclasses import dataclass, field

from .exploration import NpcAttitude
from .social import (
    MagicalNormTag,
    NormProfile,
    SocialImmediateReaction,
    SocialIncidentCategory,
    SocialIncidentSeverity,
    SocialKnowledgeAudience,
    SocialPropagationKind,
    WitnessReactionCategory,
)


@dataclass(frozen=True)
class WitnessTendencyProfile:
    intervene_directly: int = 0
    call_authority: int = 0
    public_magic_tolerance: int = 0
    threat_sensitivity: int = 0
    rumor_spread: int = 0
    suspicious_casting_misinterpretation: int = 0
    courage: int = 0
    stranger_trust: int = 0
    authority_respect: int = 0


@dataclass(frozen=True)
class WitnessArchetypeTemplate:
    archetype_id: str
    label: str
    tendencies: WitnessTendencyProfile
    description: str = ''
    report_to_faction_ids: tuple[str, ...] = ()
    default_norm_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class FactionAuthorityTemplate:
    template_id: str
    label: str
    cared_incident_categories: tuple[SocialIncidentCategory, ...] = ()
    ignored_incident_categories: tuple[SocialIncidentCategory, ...] = ()
    default_social_tags: tuple[str, ...] = ()
    preferred_immediate_reaction: SocialImmediateReaction | None = None
    response_delay_seconds: int = 0
    prefers_public_response: bool = False
    summary: str = ''


@dataclass(frozen=True)
class NpcSocialTemplate:
    npc_id: str
    label: str
    witness_archetype_id: str
    faction_ids: tuple[str, ...] = ()
    baseline_attitude: NpcAttitude = NpcAttitude.RESERVED
    respect_for_authority: int = 0
    tolerance_for_visible_magic: int = 0
    sensitivity_to_threats: int = 0
    reporting_tendency: int = 0
    rumor_tendency: int = 0
    remembers_aid: bool = True
    remembers_deceit: bool = True
    remembers_charm: bool = True
    unforgivable_incidents: tuple[SocialIncidentCategory, ...] = ()
    personal_norm_ids: tuple[str, ...] = ()
    special_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class IncidentConsequenceTemplate:
    template_id: str
    label: str
    incident_categories: tuple[SocialIncidentCategory, ...]
    reaction_categories: tuple[WitnessReactionCategory, ...] = ()
    minimum_severity: SocialIncidentSeverity = SocialIncidentSeverity.TRIVIAL
    required_norm_tags: tuple[MagicalNormTag, ...] = ()
    witness_archetype_ids: tuple[str, ...] = ()
    location_ids: tuple[str, ...] = ()
    scene_ids: tuple[str, ...] = ()
    faction_ids: tuple[str, ...] = ()
    relationship_tags: tuple[str, ...] = ()
    faction_tags: tuple[str, ...] = ()
    authority_tags: tuple[str, ...] = ()
    party_summary: str = ''
    dm_summary: str = ''
    open_loop: str = ''
    propagation_chain_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PropagationChainTemplate:
    chain_id: str
    label: str
    trigger_incident_categories: tuple[SocialIncidentCategory, ...] = ()
    reaction_categories: tuple[WitnessReactionCategory, ...] = ()
    witness_archetype_ids: tuple[str, ...] = ()
    required_norm_tags: tuple[MagicalNormTag, ...] = ()
    required_faction_ids: tuple[str, ...] = ()
    propagation_kind: SocialPropagationKind = SocialPropagationKind.LOCAL_RUMOR
    target_mode: str = 'location'
    target_id: str = ''
    delay_seconds: int = 0
    public_visible: bool = False
    summary_template: str = ''
    social_tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocationSocialBinding:
    location_id: str
    label: str
    default_norm_ids: tuple[str, ...] = ()
    settlement_default_norm_ids: tuple[str, ...] = ()
    authority_id: str | None = None
    territory_faction_ids: tuple[str, ...] = ()
    scene_type_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class SceneSocialBinding:
    scene_id: str
    location_id: str
    scene_type_id: str
    norm_ids: tuple[str, ...] = ()
    institution_ids: tuple[str, ...] = ()
    faction_ids: tuple[str, ...] = ()
    witness_archetype_overrides: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignSocialContentPack:
    campaign_id: str
    location_labels: dict[str, str]
    faction_labels: dict[str, str]
    npc_factions: dict[str, tuple[str, ...]]
    authority_by_location: dict[str, str]
    norm_profiles: dict[str, NormProfile]
    witness_archetypes: dict[str, WitnessArchetypeTemplate]
    faction_templates: dict[str, FactionAuthorityTemplate]
    npc_templates: dict[str, NpcSocialTemplate]
    consequence_templates: dict[str, IncidentConsequenceTemplate]
    propagation_chains: dict[str, PropagationChainTemplate]
    location_bindings: dict[str, LocationSocialBinding]
    scene_bindings: dict[str, SceneSocialBinding]
    known_projection_audiences: dict[str, SocialKnowledgeAudience] = field(default_factory=dict)
