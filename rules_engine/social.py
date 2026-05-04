from __future__ import annotations

from dataclasses import replace

from shared_types.encounter_events import (
    FactionMemoryUpdatedEvent,
    FactionRelationshipChangedEvent,
    ImmediateSocialConsequenceAppliedEvent,
    IncidentConsequenceTemplateSelectedEvent,
    InfluenceRetryCooldownSetEvent,
    KnownConsequenceProjectionUpdatedEvent,
    MagicalNormConsultedEvent,
    NPCAttitudeChangedEvent,
    NPCSuspicionChangedEvent,
    NPCTrustChangedEvent,
    NormProfileResolvedEvent,
    PropagationChainExecutedEvent,
    PropagationChainScheduledEvent,
    ReputationChangedEvent,
    SocialConsequenceAppliedEvent,
    SocialIncidentLoggedEvent,
    SocialPropagationExecutedEvent,
    SocialPropagationScheduledEvent,
    SocialStateProjectionUpdatedEvent,
    WitnessArchetypeResolvedEvent,
    WitnessInterpretationResolvedEvent,
    WitnessObservedIncidentEvent,
    WitnessReactionEvaluatedEvent,
    AuthorityAttentionRaisedEvent,
)
from shared_types.exploration import ExplorationState, NpcAttitude, NpcInfluenceState, SocialApproachType, SocialOutcome
from shared_types.social import (
    FactionRelationshipState,
    IncidentInterpretationRecord,
    IncidentNormEvaluation,
    IncidentPropagationRecord,
    IncidentWitnessRecord,
    InfluenceCooldownState,
    InfluenceWillingnessState,
    KnownReputationProjection,
    LocationAuthorityState,
    MagicalNormTag,
    NormProfile,
    NormScope,
    PropagationStatus,
    ReputationState,
    SocialImmediateReaction,
    SocialIncident,
    SocialIncidentCategory,
    SocialIncidentSeverity,
    SocialInterpretationCategory,
    SocialKnowledgeAudience,
    SocialPropagationKind,
    SocialPropagationTask,
    SocialPublicityScope,
    SocialRelationshipState,
    SocialRuntimeState,
    WitnessMemoryState,
    WitnessPerceptionLevel,
    WitnessReactionCategory,
)
from shared_types.storytelling import SpellcastingReactionCategory, SpellcastingSocialReactionPlan, StoryModeCastContext, StoryTranscriptEntry, StoryTranscriptVisibility, WitnessObservationPacket
from shared_types.social_content import CampaignSocialContentPack, FactionAuthorityTemplate, IncidentConsequenceTemplate, NpcSocialTemplate, PropagationChainTemplate, WitnessArchetypeTemplate


from rules_engine.social_content import build_campaign_social_content_pack


class SocialConsequenceEngine:
    PARTY_ID = 'party'
    PARTY_LABEL = 'The party'

    def __init__(self, *, campaign_id: str = 'lmop', content_pack: CampaignSocialContentPack | None = None) -> None:
        self.campaign_id = campaign_id
        self.content_pack = content_pack or build_campaign_social_content_pack(campaign_id=campaign_id)
        self.location_labels = dict(self.content_pack.location_labels)
        self.faction_labels = dict(self.content_pack.faction_labels)
        self.npc_factions = dict(self.content_pack.npc_factions)
        self.authority_by_location = dict(self.content_pack.authority_by_location)
        self.norm_profiles = dict(self.content_pack.norm_profiles)

    def initial_state(self, *, exploration_state: ExplorationState | None, current_location_id: str | None) -> SocialRuntimeState:
        state = SocialRuntimeState(norm_profiles=dict(self.norm_profiles))
        for location_id, label in self.location_labels.items():
            state.location_reputations[location_id] = ReputationState(holder_id=location_id, holder_label=label, subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
        for authority_id in sorted(set(self.authority_by_location.values())):
            state.authority_reputations[authority_id] = ReputationState(holder_id=authority_id, holder_label=self.faction_labels.get(authority_id, authority_id), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
        for faction_id, label in self.faction_labels.items():
            state.faction_relationships[faction_id] = FactionRelationshipState(faction_id=faction_id, faction_label=label, subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
        for location_id, authority_id in self.authority_by_location.items():
            authority_label = self.faction_labels.get(authority_id, authority_id.replace('-', ' ').title())
            state.location_authorities[self._location_authority_id(location_id, authority_id)] = LocationAuthorityState(
                authority_state_id=self._location_authority_id(location_id, authority_id),
                location_id=location_id,
                location_label=self.location_labels.get(location_id, location_id.replace('-', ' ').title()),
                authority_id=authority_id,
                authority_label=authority_label,
                subject_id=self.PARTY_ID,
                subject_label=self.PARTY_LABEL,
            )
        if exploration_state is not None:
            state = self.sync_from_exploration_state(state, exploration_state, timestamp_seconds=0)
            if current_location_id is not None:
                state.known_projections[f'projection:location:{current_location_id}:baseline'] = KnownReputationProjection(
                    projection_id=f'projection:location:{current_location_id}:baseline',
                    audience=SocialKnowledgeAudience.PARTY_KNOWN,
                    label=self.location_labels.get(current_location_id, current_location_id.replace('-', ' ').title()),
                    summary='People here are forming first impressions of the party.',
                    last_updated_seconds=0,
                )
        return state

    def sync_from_exploration_state(self, state: SocialRuntimeState, exploration_state: ExplorationState, *, timestamp_seconds: int) -> SocialRuntimeState:
        updated = self._copy_state(state)
        for npc_state in exploration_state.npc_states.values():
            relationship = updated.relationships.get(self._npc_relationship_id(npc_state.npc_id))
            updated.relationships[self._npc_relationship_id(npc_state.npc_id)] = self._relationship_from_npc_state(npc_state, existing=relationship, timestamp_seconds=timestamp_seconds)
        return updated

    def sync_exploration_projection(self, exploration_state: ExplorationState, state: SocialRuntimeState) -> ExplorationState:
        npc_states = dict(exploration_state.npc_states)
        changed = False
        for npc_id, npc_state in npc_states.items():
            relationship = state.relationships.get(self._npc_relationship_id(npc_id))
            if relationship is None:
                continue
            replacement = replace(npc_state, attitude=relationship.attitude, current_stance=(relationship.current_stance or npc_state.current_stance), trust=relationship.trust, hostility=relationship.suspicion, leverage=relationship.leverage, obligation=relationship.obligation, fear=relationship.fear, last_summary=(relationship.last_summary or npc_state.last_summary))
            if replacement != npc_state:
                npc_states[npc_id] = replacement
                changed = True
        if not changed:
            return exploration_state
        return replace(exploration_state, npc_states=npc_states)

    def norms_for_observer(
        self,
        state: SocialRuntimeState,
        observer_id: str,
        location_id: str | None,
        *,
        scene_id: str | None = None,
        scene_override_ids: tuple[str, ...] = (),
        institution_ids: tuple[str, ...] = (),
        npc_specific_ids: tuple[str, ...] = (),
    ) -> tuple[NormProfile, ...]:
        norms: list[NormProfile] = []
        scene_binding = self.content_pack.scene_bindings.get(scene_id or '') if scene_id is not None else None
        location_binding = self.content_pack.location_bindings.get(location_id or '') if location_id is not None else None
        npc_template = self.content_pack.npc_templates.get(observer_id)
        archetype = self.witness_archetype_for(observer_id, scene_id=scene_id, location_id=location_id)
        resolved_scene_override_ids = scene_override_ids + ((scene_binding.norm_ids) if scene_binding is not None else ())
        resolved_institution_ids = institution_ids + ((scene_binding.institution_ids) if scene_binding is not None else ())
        resolved_npc_specific_ids = npc_specific_ids + ((npc_template.personal_norm_ids) if npc_template is not None else ()) + ((archetype.default_norm_ids) if archetype is not None else ())
        resolved_location_ids = ()
        if location_binding is not None:
            resolved_location_ids = location_binding.default_norm_ids + location_binding.settlement_default_norm_ids
        for norm_id in resolved_scene_override_ids + resolved_location_ids + resolved_npc_specific_ids:
            profile = state.norm_profiles.get(norm_id)
            if profile is not None:
                norms.append(profile)
        for profile in state.norm_profiles.values():
            effective_scope = self._effective_norm_scope(profile)
            if effective_scope == NormScope.NPC and (profile.applies_to_id == observer_id or profile.norm_id in resolved_npc_specific_ids):
                norms.append(profile)
            elif effective_scope == NormScope.INSTITUTION and (profile.applies_to_id in resolved_institution_ids or profile.norm_id in resolved_institution_ids):
                norms.append(profile)
            elif effective_scope == NormScope.FACTION and profile.applies_to_id in self.npc_factions.get(observer_id, ()): 
                norms.append(profile)
            elif effective_scope == NormScope.LOCATION and location_id is not None and profile.applies_to_id == location_id:
                norms.append(profile)
            elif effective_scope == NormScope.SETTLEMENT_DEFAULT and location_id is not None and profile.applies_to_id == location_id:
                norms.append(profile)
        deduped: dict[str, NormProfile] = {}
        for profile in norms:
            deduped[profile.norm_id] = profile
        ordered = sorted(
            deduped.values(),
            key=lambda item: (self._norm_scope_rank(state, self._effective_norm_scope(item)), -item.priority, item.norm_id),
        )
        return tuple(ordered)

    def evaluate_norms(
        self,
        state: SocialRuntimeState,
        *,
        incident_id: str,
        witness_id: str,
        norm_ids: tuple[str, ...] = (),
        location_id: str | None = None,
        scene_id: str | None = None,
        scene_override_ids: tuple[str, ...] = (),
        institution_ids: tuple[str, ...] = (),
        npc_specific_ids: tuple[str, ...] = (),
    ) -> IncidentNormEvaluation:
        if norm_ids:
            profiles = tuple(profile for norm_id in norm_ids if (profile := state.norm_profiles.get(norm_id)) is not None)
        else:
            profiles = self.norms_for_observer(
                state,
                witness_id,
                location_id,
                scene_id=scene_id,
                scene_override_ids=scene_override_ids,
                institution_ids=institution_ids,
                npc_specific_ids=npc_specific_ids,
            )
        applied_ids = tuple(profile.norm_id for profile in profiles)
        applied_tags = tuple(sorted({tag.value for profile in profiles for tag in profile.tags}))
        return IncidentNormEvaluation(
            witness_id=witness_id,
            incident_id=incident_id,
            applied_norm_ids=applied_ids,
            applied_tags=applied_tags,
            helpful_magic_modifier=sum(profile.helpful_magic_modifier for profile in profiles),
            suspicious_magic_modifier=sum(profile.suspicious_magic_modifier for profile in profiles),
            hostile_magic_modifier=sum(profile.hostile_magic_modifier for profile in profiles),
        )

    def relationship_for_npc(self, state: SocialRuntimeState, npc_id: str) -> SocialRelationshipState | None:
        return state.relationships.get(self._npc_relationship_id(npc_id))

    def npc_template_for(self, npc_id: str) -> NpcSocialTemplate | None:
        return self.content_pack.npc_templates.get(npc_id)

    def witness_archetype_for(self, observer_id: str, *, scene_id: str | None, location_id: str | None) -> WitnessArchetypeTemplate | None:
        scene_binding = self.content_pack.scene_bindings.get(scene_id or '') if scene_id is not None else None
        if scene_binding is not None:
            override_id = scene_binding.witness_archetype_overrides.get(observer_id)
            if override_id is not None:
                return self.content_pack.witness_archetypes.get(override_id)
        npc_template = self.content_pack.npc_templates.get(observer_id)
        if npc_template is not None:
            return self.content_pack.witness_archetypes.get(npc_template.witness_archetype_id)
        scene_type = scene_binding.scene_type_id if scene_binding is not None else ''
        fallback_map = {
            'tavern_common_room': 'tavern_patron',
            'open_market': 'merchant',
            'city_guard_checkpoint': 'guard',
            'wilderness_campsite': 'traveler',
            'roadside_inn': 'traveler',
        }
        fallback_id = fallback_map.get(scene_type, 'common_townsfolk')
        return self.content_pack.witness_archetypes.get(fallback_id)

    def faction_template_for(self, faction_id: str) -> FactionAuthorityTemplate | None:
        return self.content_pack.faction_templates.get(faction_id)

    def scene_binding_for(self, scene_id: str | None):
        if scene_id is None:
            return None
        return self.content_pack.scene_bindings.get(scene_id)

    def location_binding_for(self, location_id: str | None):
        if location_id is None:
            return None
        return self.content_pack.location_bindings.get(location_id)

    def applicable_consequence_templates(
        self,
        *,
        incident: SocialIncident,
        witness_id: str,
        scene_id: str | None,
        location_id: str | None,
        reaction_category: WitnessReactionCategory,
        norm_evaluation: IncidentNormEvaluation,
    ) -> tuple[IncidentConsequenceTemplate, ...]:
        archetype = self.witness_archetype_for(witness_id, scene_id=scene_id, location_id=location_id)
        witness_factions = set(self.npc_factions.get(witness_id, ()))
        matches: list[IncidentConsequenceTemplate] = []
        for template in self.content_pack.consequence_templates.values():
            if incident.category not in template.incident_categories:
                continue
            if self._severity_rank(incident.severity) < self._severity_rank(template.minimum_severity):
                continue
            if template.reaction_categories and reaction_category not in template.reaction_categories:
                continue
            if template.required_norm_tags and not set(template.required_norm_tags).issubset({MagicalNormTag(tag) if not isinstance(tag, MagicalNormTag) else tag for tag in norm_evaluation.applied_tags}):
                continue
            if template.witness_archetype_ids and (archetype is None or archetype.archetype_id not in template.witness_archetype_ids):
                continue
            if template.location_ids and (location_id is None or location_id not in template.location_ids):
                continue
            if template.scene_ids and (scene_id is None or scene_id not in template.scene_ids):
                continue
            if template.faction_ids and not witness_factions.intersection(template.faction_ids):
                continue
            matches.append(template)
        return tuple(matches)

    def propagation_chain_for(self, chain_id: str) -> PropagationChainTemplate | None:
        return self.content_pack.propagation_chains.get(chain_id)

    def adjust_social_prompt(self, state: SocialRuntimeState, prompt, *, now_seconds: int):
        pending = prompt.pending_state
        if pending.npc_id is None or pending.approach is None:
            return prompt
        relationship = state.relationships.get(self._npc_relationship_id(pending.npc_id))
        adjusted_dc = prompt.dc
        notes: list[str] = []
        if relationship is not None:
            if relationship.willingness == InfluenceWillingnessState.HESITANT:
                adjusted_dc += 1
                notes.append('They seem hesitant after recent events.')
            elif relationship.willingness == InfluenceWillingnessState.REFUSING:
                adjusted_dc += 2
                notes.append('They are strongly resistant right now.')
            adjusted_dc += max(0, relationship.suspicion - relationship.trust // 2)
        cooldown = state.retry_cooldowns.get(self._cooldown_id(pending.actor_id, pending.npc_id, pending.approach))
        if cooldown is not None and cooldown.until_seconds > now_seconds:
            adjusted_dc += 2
            notes.append(cooldown.reason)
        if adjusted_dc == prompt.dc and not notes:
            return prompt
        suffix = f" {' '.join(notes)}" if notes else ''
        return replace(prompt, dc=max(5, adjusted_dc), prompt=f'{prompt.prompt}{suffix}')

    def integrate_exploration_update(self, state: SocialRuntimeState, *, previous_state: ExplorationState | None, new_state: ExplorationState, events: tuple[object, ...], clock_seconds: int, location_id: str | None, scene_id: str | None) -> tuple[SocialRuntimeState, ExplorationState, tuple[object, ...], tuple[StoryTranscriptEntry, ...], tuple[str, ...], tuple[str, ...]]:
        updated = self.sync_from_exploration_state(state, new_state, timestamp_seconds=clock_seconds)
        emitted: list[object] = []
        notes: list[str] = []
        open_loops: list[str] = []
        for event in events:
            if event.__class__.__name__ != 'SocialInfluenceResolvedEvent':
                continue
            dedupe_key = f'influence:{scene_id or ""}:{location_id or ""}:{event.actor_id}:{event.npc_id}:{event.approach.value}:{clock_seconds}:{event.outcome.value}'
            incident = SocialIncident(
                incident_id=f'incident:social:{event.npc_id}:{event.approach.value}:{clock_seconds}:{len(updated.incidents) + 1}',
                category=(SocialIncidentCategory.INTIMIDATION if event.approach == SocialApproachType.INTIMIDATE else SocialIncidentCategory.DECEPTION_EXPOSED if event.approach == SocialApproachType.DECEIVE and event.outcome == SocialOutcome.FAILURE else SocialIncidentCategory.SOCIAL_INFLUENCE),
                scene_id=scene_id,
                location_id=location_id,
                timestamp_seconds=clock_seconds,
                source_actor_ids=(event.actor_id,),
                target_actor_ids=(event.npc_id,),
                witness_ids=(event.npc_id,),
                severity=(SocialIncidentSeverity.LOW if event.outcome != SocialOutcome.FAILURE else SocialIncidentSeverity.MODERATE),
                publicity_scope=SocialPublicityScope.PARTY_KNOWN,
                related_event_refs=(f'{event.__class__.__name__}:{event.actor_id}:{event.npc_id}:{event.approach.value}:{clock_seconds}',),
                dedupe_key=dedupe_key,
                summary=event.summary,
                public_summary=event.summary,
            )
            incident, created = self._register_incident(updated, incident)
            if created:
                emitted.append(SocialIncidentLoggedEvent(incident=incident))
            norm_evaluation = self.evaluate_norms(updated, incident_id=incident.incident_id, witness_id=event.npc_id, location_id=location_id, scene_id=scene_id)
            witness_archetype = self.witness_archetype_for(event.npc_id, scene_id=scene_id, location_id=location_id)
            witness_record = self._attach_witness_record(
                updated,
                incident.incident_id,
                IncidentWitnessRecord(
                    record_id=f'witness:{incident.incident_id}:{event.npc_id}',
                    incident_id=incident.incident_id,
                    witness_id=event.npc_id,
                    display_name=self._npc_label(event.npc_id),
                    paying_attention=True,
                    perceived_act=True,
                    perceived_effect=False,
                    heard_event=True,
                    confidence='clear',
                    perception_level=WitnessPerceptionLevel.CLEAR_ACT,
                    cared=True,
                    hidden_from_party=False,
                    archetype_id=(witness_archetype.archetype_id if witness_archetype is not None else ''),
                    applicable_norm_ids=norm_evaluation.applied_norm_ids,
                    norm_tags=norm_evaluation.applied_tags,
                    summary=event.summary,
                ),
            )
            if created and witness_archetype is not None:
                emitted.append(WitnessArchetypeResolvedEvent(incident_id=incident.incident_id, witness_id=event.npc_id, archetype_id=witness_archetype.archetype_id, label=witness_archetype.label))
            emitted.append(NormProfileResolvedEvent(incident_id=incident.incident_id, witness_id=event.npc_id, norm_ids=norm_evaluation.applied_norm_ids))
            if created:
                memory = WitnessMemoryState(
                    memory_id=f'memory:{incident.incident_id}:{event.npc_id}',
                    incident_id=incident.incident_id,
                    witness_id=event.npc_id,
                    reaction_category=(WitnessReactionCategory.SUSPICIOUS if event.outcome == SocialOutcome.FAILURE else WitnessReactionCategory.IGNORE),
                    confidence='clear',
                    cared=True,
                    reportable=False,
                    summary=event.summary,
                )
                updated.witness_memories[memory.memory_id] = memory
                emitted.append(WitnessObservedIncidentEvent(memory=memory))
            interpretation_category = SocialInterpretationCategory.FORGIVABLE
            reaction_category = WitnessReactionCategory.IGNORE
            if event.outcome == SocialOutcome.FAILURE and event.approach in {SocialApproachType.DECEIVE, SocialApproachType.INTIMIDATE}:
                interpretation_category = SocialInterpretationCategory.SUSPICIOUS
                reaction_category = WitnessReactionCategory.SUSPICIOUS
            elif event.outcome == SocialOutcome.FAILURE:
                interpretation_category = SocialInterpretationCategory.ODD
                reaction_category = WitnessReactionCategory.MILDLY_WARY
            interpretation = self._attach_interpretation_record(
                updated,
                incident.incident_id,
                IncidentInterpretationRecord(
                    record_id=f'interpretation:{incident.incident_id}:{event.npc_id}',
                    incident_id=incident.incident_id,
                    witness_id=event.npc_id,
                    interpretation=interpretation_category,
                    immediate_reaction=self._immediate_reaction_from_witness_category(reaction_category),
                    reaction_category=reaction_category,
                    summary=event.summary,
                    public_text=event.summary,
                ),
            )
            if created:
                emitted.append(WitnessInterpretationResolvedEvent(record=interpretation))
                emitted.append(WitnessReactionEvaluatedEvent(incident_id=incident.incident_id, witness_id=event.npc_id, reaction_category=reaction_category, summary=event.summary))
            relationship = updated.relationships.get(self._npc_relationship_id(event.npc_id))
            if relationship is not None:
                updated.relationships[relationship.relationship_id] = self._link_relationship_incident(
                    replace(relationship, willingness=self._willingness_from_metrics(relationship)),
                    incident_id=incident.incident_id,
                    incident_category=incident.category,
                    scene_id=scene_id,
                    summary=event.summary,
                    timestamp_seconds=clock_seconds,
                )
            if event.outcome == SocialOutcome.FAILURE:
                cooldown = InfluenceCooldownState(
                    cooldown_id=self._cooldown_id(event.actor_id, event.npc_id, event.approach),
                    actor_id=event.actor_id,
                    npc_id=event.npc_id,
                    approach=event.approach,
                    until_seconds=clock_seconds + 10 * 60,
                    reason=f'{self._npc_label(event.npc_id)} is tired of that line of pressure for now.',
                    related_incident_id=incident.incident_id,
                )
                updated.retry_cooldowns[cooldown.cooldown_id] = cooldown
                emitted.append(InfluenceRetryCooldownSetEvent(cooldown=cooldown))
                updated.known_projections[f'projection:cooldown:{cooldown.cooldown_id}'] = KnownReputationProjection(
                    projection_id=f'projection:cooldown:{cooldown.cooldown_id}',
                    audience=SocialKnowledgeAudience.PARTY_KNOWN,
                    label=self._npc_label(event.npc_id),
                    summary=cooldown.reason,
                    related_incident_id=incident.incident_id,
                    last_updated_seconds=clock_seconds,
                )
                notes.append(cooldown.reason)
            if created:
                updated.known_projections[f'projection:influence:{incident.incident_id}'] = KnownReputationProjection(
                    projection_id=f'projection:influence:{incident.incident_id}',
                    audience=SocialKnowledgeAudience.PARTY_KNOWN,
                    label=self._npc_label(event.npc_id),
                    summary=event.summary,
                    related_incident_id=incident.incident_id,
                    last_updated_seconds=clock_seconds,
                )
            if event.approach == SocialApproachType.INTIMIDATE and event.outcome == SocialOutcome.FAILURE:
                open_loops.append(f'{self._npc_label(event.npc_id)} may remember the failed intimidation attempt.')
            self._apply_consequence_templates(
                updated,
                incident_id=incident.incident_id,
                witness_id=event.npc_id,
                witness_label=self._npc_label(event.npc_id),
                scene_id=scene_id,
                location_id=location_id,
                reaction_category=reaction_category,
                norm_evaluation=norm_evaluation,
                clock_seconds=clock_seconds,
                emitted=emitted,
                notes=notes,
                open_loops=open_loops,
            )
            for norm_id in witness_record.applicable_norm_ids:
                emitted.append(MagicalNormConsultedEvent(observer_id=event.npc_id, norm_id=norm_id, norm_tags=witness_record.norm_tags))
        if emitted:
            emitted.append(SocialStateProjectionUpdatedEvent(scene_id=scene_id, location_id=location_id))
        synced = self.sync_exploration_projection(new_state, updated)
        return updated, synced, tuple(emitted), (), tuple(notes), tuple(self._unique(open_loops))

    def log_story_spellcast_incident(self, state: SocialRuntimeState, *, exploration_state: ExplorationState | None, context: StoryModeCastContext, witness_packet: WitnessObservationPacket, social_reaction_plan: SpellcastingSocialReactionPlan | None, clock_seconds: int, location_id: str | None, scene_id: str | None) -> tuple[SocialRuntimeState, ExplorationState | None, tuple[object, ...], tuple[StoryTranscriptEntry, ...], tuple[str, ...], tuple[str, ...]]:
        updated = state
        if exploration_state is not None:
            updated = self.sync_from_exploration_state(updated, exploration_state, timestamp_seconds=clock_seconds)
        emitted: list[object] = []
        transcript_entries: list[StoryTranscriptEntry] = []
        notes: list[str] = []
        open_loops: list[str] = []
        witness_ids = tuple(witness.observer_id for witness in witness_packet.witnesses)
        dedupe_key = f'spell:{scene_id or ""}:{location_id or ""}:{clock_seconds}:{context.attempt.actor_id}:{context.attempt.spell_id}:{context.attempt.target_id or ""}:{"|".join(witness_ids)}'
        incident = SocialIncident(
            incident_id=f'incident:spell:{context.attempt.spell_id}:{clock_seconds}:{len(updated.incidents) + 1}',
            category=self._spell_incident_category(context, social_reaction_plan),
            scene_id=scene_id,
            location_id=location_id,
            timestamp_seconds=clock_seconds,
            source_actor_ids=(context.attempt.actor_id,),
            target_actor_ids=((context.attempt.target_id,) if context.attempt.target_id is not None else ()),
            witness_ids=witness_ids,
            severity=self._spell_incident_severity(social_reaction_plan),
            publicity_scope=(SocialPublicityScope.WITNESSES_ONLY if witness_ids else SocialPublicityScope.PRIVATE),
            magic_tags=('magic', 'spellcasting'),
            spell_tags=(context.spell_name.lower().replace(' ', '-'),),
            visible_effect_tags=(('obvious-effect',) if any(witness.perceived_spell_effect for witness in witness_packet.witnesses) else ()),
            related_event_refs=(f'story-spell:{context.attempt.actor_id}:{context.attempt.spell_id}:{clock_seconds}',),
            dedupe_key=dedupe_key,
            summary=f'{context.spell_name} was cast in story mode at {location_id or "an unknown location"}.',
            public_summary=(social_reaction_plan.public_narration if social_reaction_plan is not None else ''),
            dm_note=(social_reaction_plan.dm_note if social_reaction_plan is not None else ''),
        )
        incident, created = self._register_incident(updated, incident)
        if not created:
            synced = None if exploration_state is None else self.sync_exploration_projection(exploration_state, updated)
            return updated, synced, (), (), (), ()
        emitted.append(SocialIncidentLoggedEvent(incident=incident))
        reactions_by_id = {reaction.witness_id: reaction for reaction in ((social_reaction_plan.witness_reactions) if social_reaction_plan is not None else ())}
        for witness in witness_packet.witnesses:
            reaction = reactions_by_id.get(witness.observer_id)
            mapped_category = self._witness_reaction_category(reaction.reaction_category if reaction is not None else None)
            norm_evaluation = self.evaluate_norms(
                updated,
                incident_id=incident.incident_id,
                witness_id=witness.observer_id,
                norm_ids=witness.applicable_norm_ids,
                location_id=location_id,
                scene_id=scene_id,
            )
            witness_archetype = self.witness_archetype_for(witness.observer_id, scene_id=scene_id, location_id=location_id)
            witness_record = self._attach_witness_record(
                updated,
                incident.incident_id,
                IncidentWitnessRecord(
                    record_id=f'witness:{incident.incident_id}:{witness.observer_id}',
                    incident_id=incident.incident_id,
                    witness_id=witness.observer_id,
                    display_name=witness.display_name,
                    paying_attention=witness.paying_attention,
                    perceived_act=witness.perceived_casting_act,
                    perceived_effect=witness.perceived_spell_effect,
                    heard_event=False,
                    confidence=witness.confidence.value,
                    perception_level=self._perception_level(witness),
                    cared=(mapped_category not in {WitnessReactionCategory.NONE, WitnessReactionCategory.IGNORE}),
                    hidden_from_party=False,
                    archetype_id=(witness_archetype.archetype_id if witness_archetype is not None else ''),
                    applicable_norm_ids=norm_evaluation.applied_norm_ids,
                    norm_tags=norm_evaluation.applied_tags,
                    summary=(reaction.summary if reaction is not None else f'{witness.display_name} noticed the spellcasting.'),
                ),
            )
            if witness_archetype is not None:
                emitted.append(WitnessArchetypeResolvedEvent(incident_id=incident.incident_id, witness_id=witness.observer_id, archetype_id=witness_archetype.archetype_id, label=witness_archetype.label))
            emitted.append(NormProfileResolvedEvent(incident_id=incident.incident_id, witness_id=witness.observer_id, norm_ids=norm_evaluation.applied_norm_ids))
            memory = WitnessMemoryState(
                memory_id=f'memory:{incident.incident_id}:{witness.observer_id}',
                incident_id=incident.incident_id,
                witness_id=witness.observer_id,
                reaction_category=mapped_category,
                confidence=witness.confidence.value,
                cared=witness_record.cared,
                reportable=(mapped_category in {WitnessReactionCategory.REPORT_TO_AUTHORITY, WitnessReactionCategory.ALARMED, WitnessReactionCategory.CONFRONTATIONAL, WitnessReactionCategory.HOSTILE, WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE}),
                summary=witness_record.summary,
            )
            updated.witness_memories[memory.memory_id] = memory
            interpretation = self._attach_interpretation_record(
                updated,
                incident.incident_id,
                IncidentInterpretationRecord(
                    record_id=f'interpretation:{incident.incident_id}:{witness.observer_id}',
                    incident_id=incident.incident_id,
                    witness_id=witness.observer_id,
                    interpretation=self._interpretation_from_reaction(mapped_category, incident, norm_evaluation),
                    immediate_reaction=self._immediate_reaction_from_witness_category(mapped_category),
                    reaction_category=mapped_category,
                    summary=(reaction.summary if reaction is not None else witness_record.summary),
                    public_text=(reaction.public_text if reaction is not None else ''),
                    private_note=(reaction.private_note if reaction is not None else ''),
                ),
            )
            emitted.append(WitnessObservedIncidentEvent(memory=memory))
            emitted.append(WitnessReactionEvaluatedEvent(incident_id=incident.incident_id, witness_id=witness.observer_id, reaction_category=mapped_category, summary=memory.summary))
            emitted.append(WitnessInterpretationResolvedEvent(record=interpretation))
            relationship_id = self._npc_relationship_id(witness.observer_id)
            relationship = updated.relationships.get(relationship_id) or SocialRelationshipState(
                relationship_id=relationship_id,
                source_id=witness.observer_id,
                source_label=witness.display_name,
                target_id=self.PARTY_ID,
                target_label=self.PARTY_LABEL,
                current_stance=(witness.current_stance or ''),
                attitude=(witness.attitude or NpcAttitude.RESERVED),
                trust=max(0, witness.relationship_trust),
                suspicion=max(0, witness.relationship_suspicion),
                fear=max(0, witness.relationship_fear),
                respect=max(0, witness.relationship_respect),
                willingness=InfluenceWillingnessState.HESITANT,
            )
            applied = self._link_relationship_incident(
                self._apply_witness_reaction(relationship, mapped_category, summary=memory.summary, timestamp_seconds=clock_seconds),
                incident_id=incident.incident_id,
                incident_category=incident.category,
                scene_id=scene_id,
                summary=memory.summary,
                timestamp_seconds=clock_seconds,
            )
            updated.relationships[relationship_id] = applied
            emitted.append(SocialConsequenceAppliedEvent(incident_id=incident.incident_id, target_kind='npc', target_id=witness.observer_id, summary=applied.last_summary or memory.summary))
            if applied.attitude != relationship.attitude:
                emitted.append(NPCAttitudeChangedEvent(npc_id=witness.observer_id, old_attitude=relationship.attitude, new_attitude=applied.attitude, summary=applied.last_summary or memory.summary))
            if applied.trust != relationship.trust:
                emitted.append(NPCTrustChangedEvent(npc_id=witness.observer_id, old_value=relationship.trust, new_value=applied.trust, summary=applied.last_summary or memory.summary))
            if applied.suspicion != relationship.suspicion:
                emitted.append(NPCSuspicionChangedEvent(npc_id=witness.observer_id, old_value=relationship.suspicion, new_value=applied.suspicion, summary=applied.last_summary or memory.summary))
            updated = self._apply_reputation_from_spell_reaction(updated, incident, witness.observer_id, mapped_category, clock_seconds, emitted, location_id)
            for norm_id in witness_record.applicable_norm_ids:
                emitted.append(MagicalNormConsultedEvent(observer_id=witness.observer_id, norm_id=norm_id, norm_tags=witness_record.norm_tags))
            if mapped_category in {WitnessReactionCategory.REPORT_TO_AUTHORITY, WitnessReactionCategory.ALARMED, WitnessReactionCategory.CONFRONTATIONAL, WitnessReactionCategory.HOSTILE, WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE}:
                authority_id = self.authority_by_location.get(location_id or '', None)
                if authority_id is not None:
                    task = self._schedule_propagation(
                        updated,
                        incident_id=incident.incident_id,
                        propagation_kind=SocialPropagationKind.AUTHORITY_REPORT,
                        source_id=witness.observer_id,
                        target_id=authority_id,
                        due_at_seconds=clock_seconds + 5 * 60,
                        summary=f'{witness.display_name} may report the spellcasting to {self.faction_labels.get(authority_id, authority_id)}.',
                        chain_id='chain:authority-report',
                    )
                    if task is not None:
                        emitted.append(SocialPropagationScheduledEvent(task=task))
                        notes.append(task.summary)
                for faction_id in self.npc_factions.get(witness.observer_id, ()): 
                    task = self._schedule_propagation(
                        updated,
                        incident_id=incident.incident_id,
                        propagation_kind=SocialPropagationKind.FACTION_PROPAGATION,
                        source_id=witness.observer_id,
                        target_id=faction_id,
                        due_at_seconds=clock_seconds + 15 * 60,
                        summary=f'{witness.display_name} may spread word of the incident within {self.faction_labels.get(faction_id, faction_id)}.',
                        chain_id='chain:faction-notice',
                    )
                    if task is not None:
                        emitted.append(SocialPropagationScheduledEvent(task=task))
            self._apply_consequence_templates(
                updated,
                incident_id=incident.incident_id,
                witness_id=witness.observer_id,
                witness_label=witness.display_name,
                scene_id=scene_id,
                location_id=location_id,
                reaction_category=mapped_category,
                norm_evaluation=norm_evaluation,
                clock_seconds=clock_seconds,
                emitted=emitted,
                notes=notes,
                open_loops=open_loops,
            )
            if mapped_category == WitnessReactionCategory.CURIOUS and incident.category == SocialIncidentCategory.AID_OR_HEALING:
                updated.known_projections[f'projection:helpful:{incident.incident_id}:{witness.observer_id}'] = KnownReputationProjection(
                    projection_id=f'projection:helpful:{incident.incident_id}:{witness.observer_id}',
                    audience=SocialKnowledgeAudience.PUBLIC,
                    label=witness.display_name,
                    summary=f'{witness.display_name} seemed relieved rather than threatened by the magic.',
                    related_incident_id=incident.incident_id,
                    last_updated_seconds=clock_seconds,
                )
        if not witness_ids:
            updated.known_projections[f'projection:private:{incident.incident_id}'] = KnownReputationProjection(
                projection_id=f'projection:private:{incident.incident_id}',
                audience=SocialKnowledgeAudience.DM_ONLY,
                label='Unwitnessed magic',
                summary='No one in the scene clearly witnessed the spellcasting.',
                related_incident_id=incident.incident_id,
                last_updated_seconds=clock_seconds,
            )
        elif incident.public_summary:
            updated.known_projections[f'projection:spell:{incident.incident_id}'] = KnownReputationProjection(
                projection_id=f'projection:spell:{incident.incident_id}',
                audience=SocialKnowledgeAudience.PARTY_KNOWN,
                label=context.spell_name,
                summary=incident.public_summary,
                related_incident_id=incident.incident_id,
                last_updated_seconds=clock_seconds,
            )
        emitted.append(SocialStateProjectionUpdatedEvent(scene_id=scene_id, location_id=location_id))
        synced = None if exploration_state is None else self.sync_exploration_projection(exploration_state, updated)
        if social_reaction_plan is not None and social_reaction_plan.dm_note:
            transcript_entries.append(StoryTranscriptEntry(speaker='DM Memory', text=social_reaction_plan.dm_note, visibility=StoryTranscriptVisibility.DM_ONLY))
        return updated, synced, tuple(emitted), tuple(transcript_entries), tuple(self._unique(notes)), tuple(self._unique(open_loops))

    def process_due_propagation(self, state: SocialRuntimeState, *, clock_seconds: int, scene_id: str | None, location_id: str | None) -> tuple[SocialRuntimeState, tuple[object, ...], tuple[StoryTranscriptEntry, ...], tuple[str, ...], tuple[str, ...]]:
        if not state.propagation_queue:
            return state, (), (), (), ()
        updated = self._copy_state(state)
        emitted: list[object] = []
        transcript_entries: list[StoryTranscriptEntry] = []
        notes: list[str] = []
        open_loops: list[str] = []
        remaining: dict[str, SocialPropagationTask] = {}
        for task_id, task in sorted(updated.propagation_queue.items(), key=lambda item: item[1].due_at_seconds):
            if task.cancelled:
                self._mark_propagation_record(updated, record_id=task.related_record_id, status=PropagationStatus.CANCELLED)
                continue
            if task.due_at_seconds > clock_seconds:
                remaining[task_id] = task
                continue
            incident = updated.incidents.get(task.incident_id)
            if task.propagation_kind == SocialPropagationKind.AUTHORITY_REPORT:
                reputation = updated.authority_reputations.get(task.target_id) or ReputationState(holder_id=task.target_id, holder_label=self.faction_labels.get(task.target_id, task.target_id.replace('-', ' ').title()), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
                changed = replace(
                    reputation,
                    suspicion=min(10, reputation.suspicion + 2),
                    respect=max(0, reputation.respect - 1),
                    attitude=self._attitude_from_metrics(trust=reputation.trust, suspicion=min(10, reputation.suspicion + 2), fear=reputation.fear, respect=max(0, reputation.respect - 1), gratitude=reputation.gratitude),
                )
                updated.authority_reputations[task.target_id] = self._link_reputation_incident(changed, incident_id=task.incident_id, summary=task.summary, timestamp_seconds=clock_seconds)
                for loc_id, authority_id in self.authority_by_location.items():
                    if authority_id != task.target_id:
                        continue
                    authority_key = self._location_authority_id(loc_id, authority_id)
                    authority_state = updated.location_authorities.get(authority_key) or LocationAuthorityState(
                        authority_state_id=authority_key,
                        location_id=loc_id,
                        location_label=self.location_labels.get(loc_id, loc_id.replace('-', ' ').title()),
                        authority_id=authority_id,
                        authority_label=self.faction_labels.get(authority_id, authority_id.replace('-', ' ').title()),
                        subject_id=self.PARTY_ID,
                        subject_label=self.PARTY_LABEL,
                    )
                    authority_state = replace(authority_state, suspicion=min(10, authority_state.suspicion + 2), respect=max(0, authority_state.respect - 1))
                    updated.location_authorities[authority_key] = self._link_location_authority_incident(authority_state, incident_id=task.incident_id, summary=task.summary, timestamp_seconds=clock_seconds, current_alert=task.summary)
                emitted.append(SocialPropagationExecutedEvent(task_id=task.task_id, incident_id=task.incident_id, target_id=task.target_id, summary=task.summary))
                if task.chain_id:
                    emitted.append(PropagationChainExecutedEvent(incident_id=task.incident_id, chain_id=task.chain_id, target_id=task.target_id, summary=task.summary))
                emitted.append(ReputationChangedEvent(holder_id=task.target_id, holder_label=updated.authority_reputations[task.target_id].holder_label, summary=task.summary, suspicion=updated.authority_reputations[task.target_id].suspicion, respect=updated.authority_reputations[task.target_id].respect, fear=updated.authority_reputations[task.target_id].fear, trust=updated.authority_reputations[task.target_id].trust))
                updated.known_projections[f'projection:authority:{task.task_id}'] = KnownReputationProjection(projection_id=f'projection:authority:{task.task_id}', audience=SocialKnowledgeAudience.DM_ONLY, label=updated.authority_reputations[task.target_id].holder_label, summary=task.summary, related_incident_id=task.incident_id, last_updated_seconds=clock_seconds)
                emitted.append(AuthorityAttentionRaisedEvent(authority_id=task.target_id, location_id=location_id, summary=task.summary))
                emitted.append(KnownConsequenceProjectionUpdatedEvent(projection_id=f'projection:authority:{task.task_id}', audience=SocialKnowledgeAudience.DM_ONLY.value, summary=task.summary))
                transcript_entries.append(StoryTranscriptEntry(speaker='DM', text=task.summary, visibility=StoryTranscriptVisibility.DM_ONLY))
                notes.append(task.summary)
            elif task.propagation_kind == SocialPropagationKind.LOCAL_RUMOR:
                reputation = updated.location_reputations.get(task.target_id) or ReputationState(holder_id=task.target_id, holder_label=self.location_labels.get(task.target_id, task.target_id.replace('-', ' ').title()), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
                suspicion = reputation.suspicion + (1 if incident is not None and incident.category != SocialIncidentCategory.AID_OR_HEALING else 0)
                respect = reputation.respect + (1 if incident is not None and incident.category == SocialIncidentCategory.AID_OR_HEALING else 0)
                changed = replace(reputation, suspicion=min(10, suspicion), respect=min(10, respect), attitude=self._attitude_from_metrics(trust=reputation.trust, suspicion=min(10, suspicion), fear=reputation.fear, respect=min(10, respect), gratitude=reputation.gratitude))
                updated.location_reputations[task.target_id] = self._link_reputation_incident(changed, incident_id=task.incident_id, summary=task.summary, timestamp_seconds=clock_seconds)
                emitted.append(SocialPropagationExecutedEvent(task_id=task.task_id, incident_id=task.incident_id, target_id=task.target_id, summary=task.summary))
                if task.chain_id:
                    emitted.append(PropagationChainExecutedEvent(incident_id=task.incident_id, chain_id=task.chain_id, target_id=task.target_id, summary=task.summary))
                emitted.append(ReputationChangedEvent(holder_id=task.target_id, holder_label=updated.location_reputations[task.target_id].holder_label, summary=task.summary, suspicion=updated.location_reputations[task.target_id].suspicion, respect=updated.location_reputations[task.target_id].respect, fear=updated.location_reputations[task.target_id].fear, trust=updated.location_reputations[task.target_id].trust))
                updated.known_projections[f'projection:rumor:{task.task_id}'] = KnownReputationProjection(projection_id=f'projection:rumor:{task.task_id}', audience=(SocialKnowledgeAudience.PUBLIC if task.public_visible else SocialKnowledgeAudience.PARTY_KNOWN), label=updated.location_reputations[task.target_id].holder_label, summary=task.summary, related_incident_id=task.incident_id, last_updated_seconds=clock_seconds)
                emitted.append(KnownConsequenceProjectionUpdatedEvent(projection_id=f'projection:rumor:{task.task_id}', audience=(SocialKnowledgeAudience.PUBLIC.value if task.public_visible else SocialKnowledgeAudience.PARTY_KNOWN.value), summary=task.summary))
                transcript_entries.append(StoryTranscriptEntry(speaker='DM', text=task.summary, visibility=(StoryTranscriptVisibility.PUBLIC if task.public_visible else StoryTranscriptVisibility.DM_ONLY)))
                notes.append(task.summary)
            elif task.propagation_kind == SocialPropagationKind.FACTION_PROPAGATION:
                relationship = updated.faction_relationships.get(task.target_id) or FactionRelationshipState(faction_id=task.target_id, faction_label=self.faction_labels.get(task.target_id, task.target_id.replace('-', ' ').title()), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
                suspicion_delta = 1 if incident is None or incident.category != SocialIncidentCategory.AID_OR_HEALING else 0
                respect_delta = 1 if incident is not None and incident.category == SocialIncidentCategory.AID_OR_HEALING else 0
                changed = replace(
                    relationship,
                    suspicion=min(10, relationship.suspicion + suspicion_delta),
                    respect=min(10, relationship.respect + respect_delta),
                    attitude=self._attitude_from_metrics(trust=relationship.trust, suspicion=min(10, relationship.suspicion + suspicion_delta), fear=relationship.fear, respect=min(10, relationship.respect + respect_delta), gratitude=relationship.gratitude),
                )
                updated.faction_relationships[task.target_id] = self._link_faction_incident(changed, incident_id=task.incident_id, summary=task.summary, timestamp_seconds=clock_seconds)
                emitted.append(SocialPropagationExecutedEvent(task_id=task.task_id, incident_id=task.incident_id, target_id=task.target_id, summary=task.summary))
                if task.chain_id:
                    emitted.append(PropagationChainExecutedEvent(incident_id=task.incident_id, chain_id=task.chain_id, target_id=task.target_id, summary=task.summary))
                emitted.append(FactionRelationshipChangedEvent(faction_id=task.target_id, faction_label=updated.faction_relationships[task.target_id].faction_label, summary=task.summary, suspicion=updated.faction_relationships[task.target_id].suspicion, respect=updated.faction_relationships[task.target_id].respect, fear=updated.faction_relationships[task.target_id].fear, trust=updated.faction_relationships[task.target_id].trust))
                updated.known_projections[f'projection:faction:{task.task_id}'] = KnownReputationProjection(projection_id=f'projection:faction:{task.task_id}', audience=SocialKnowledgeAudience.DM_ONLY, label=updated.faction_relationships[task.target_id].faction_label, summary=task.summary, related_incident_id=task.incident_id, last_updated_seconds=clock_seconds)
                emitted.append(FactionMemoryUpdatedEvent(faction_id=task.target_id, summary=task.summary))
                emitted.append(KnownConsequenceProjectionUpdatedEvent(projection_id=f'projection:faction:{task.task_id}', audience=SocialKnowledgeAudience.DM_ONLY.value, summary=task.summary))
                notes.append(task.summary)
            self._mark_propagation_record(updated, record_id=task.related_record_id, status=PropagationStatus.EXECUTED)
        updated.propagation_queue = remaining
        if emitted:
            emitted.append(SocialStateProjectionUpdatedEvent(scene_id=scene_id, location_id=location_id))
        return updated, tuple(emitted), tuple(transcript_entries), tuple(self._unique(notes)), tuple(self._unique(open_loops))

    def visible_projection_lines(self, state: SocialRuntimeState, *, dm_view: bool) -> tuple[str, ...]:
        audiences = {SocialKnowledgeAudience.PUBLIC, SocialKnowledgeAudience.PARTY_KNOWN}
        if dm_view:
            audiences.add(SocialKnowledgeAudience.DM_ONLY)
        projections = [projection.summary for projection in sorted(state.known_projections.values(), key=lambda item: (item.last_updated_seconds, item.projection_id)) if projection.audience in audiences]
        return tuple(projections[-8:])

    def dm_status_lines(self, state: SocialRuntimeState) -> tuple[str, ...]:
        lines: list[str] = []
        for relationship in sorted(state.relationships.values(), key=lambda item: item.source_label):
            lines.append(f'{relationship.source_label}: attitude {relationship.attitude.value}; trust {relationship.trust}; suspicion {relationship.suspicion}; fear {relationship.fear}; respect {relationship.respect}; willingness {relationship.willingness.value}.')
        for cooldown in sorted(state.retry_cooldowns.values(), key=lambda item: (item.until_seconds, item.npc_id, item.actor_id)):
            lines.append(f'Retry cooldown: {self._npc_label(cooldown.npc_id)} vs {cooldown.actor_id} {cooldown.approach.value} until {cooldown.until_seconds}.')
        for task in sorted(state.propagation_queue.values(), key=lambda item: (item.due_at_seconds, item.task_id)):
            lines.append(f'Pending propagation: {task.summary} at {task.due_at_seconds}.')
        return tuple(lines[-12:])

    def npc_playbook_lines(self, state: SocialRuntimeState, *, npc_id: str) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
        relationship = state.relationships.get(self._npc_relationship_id(npc_id))
        if relationship is None:
            return (), (), ()
        trust_lines = (f'Trust {relationship.trust}, suspicion {relationship.suspicion}, fear {relationship.fear}, respect {relationship.respect}.', f'Current willingness: {relationship.willingness.value}.')
        recent = tuple(incident.summary for incident in sorted(state.incidents.values(), key=lambda item: item.timestamp_seconds) if npc_id in incident.witness_ids or npc_id in incident.target_actor_ids)[-3:]
        warnings = tuple(projection.summary for projection in state.known_projections.values() if projection.audience == SocialKnowledgeAudience.DM_ONLY and npc_id.replace('-', ' ')[:4].lower() in projection.summary.lower())[-2:]
        template = self.content_pack.npc_templates.get(npc_id)
        if template is not None:
            authored_warnings: list[str] = []
            if template.special_tags:
                authored_warnings.append(f"Special social tags: {', '.join(template.special_tags)}.")
            if template.unforgivable_incidents:
                authored_warnings.append('Unforgivable incidents: ' + ', '.join(item.value for item in template.unforgivable_incidents) + '.')
            warnings = tuple(authored_warnings) + warnings
        return trust_lines, recent, warnings

    def _apply_reputation_from_spell_reaction(self, state: SocialRuntimeState, incident: SocialIncident, witness_id: str, reaction_category: WitnessReactionCategory, clock_seconds: int, emitted: list[object], location_id: str | None) -> SocialRuntimeState:
        updated = state
        for faction_id in self.npc_factions.get(witness_id, ()): 
            relationship = updated.faction_relationships.get(faction_id) or FactionRelationshipState(faction_id=faction_id, faction_label=self.faction_labels.get(faction_id, faction_id.replace('-', ' ').title()), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
            suspicion_delta = 1 if reaction_category in {WitnessReactionCategory.SUSPICIOUS, WitnessReactionCategory.ALARMED, WitnessReactionCategory.CONFRONTATIONAL, WitnessReactionCategory.REPORT_TO_AUTHORITY, WitnessReactionCategory.HOSTILE, WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE} else 0
            respect_delta = 1 if incident.category == SocialIncidentCategory.AID_OR_HEALING and reaction_category == WitnessReactionCategory.CURIOUS else 0
            if suspicion_delta == 0 and respect_delta == 0:
                continue
            changed = replace(relationship, suspicion=min(10, relationship.suspicion + suspicion_delta), respect=min(10, relationship.respect + respect_delta), attitude=self._attitude_from_metrics(trust=relationship.trust, suspicion=min(10, relationship.suspicion + suspicion_delta), fear=relationship.fear, respect=min(10, relationship.respect + respect_delta), gratitude=relationship.gratitude))
            updated.faction_relationships[faction_id] = self._link_faction_incident(changed, incident_id=incident.incident_id, summary=incident.summary, timestamp_seconds=clock_seconds)
            emitted.append(FactionRelationshipChangedEvent(faction_id=faction_id, faction_label=updated.faction_relationships[faction_id].faction_label, summary=incident.summary, suspicion=updated.faction_relationships[faction_id].suspicion, respect=updated.faction_relationships[faction_id].respect, fear=updated.faction_relationships[faction_id].fear, trust=updated.faction_relationships[faction_id].trust))
        if location_id is not None:
            reputation = updated.location_reputations.get(location_id) or ReputationState(holder_id=location_id, holder_label=self.location_labels.get(location_id, location_id.replace('-', ' ').title()), subject_id=self.PARTY_ID, subject_label=self.PARTY_LABEL)
            suspicion_delta = 1 if reaction_category in {WitnessReactionCategory.ALARMED, WitnessReactionCategory.CONFRONTATIONAL, WitnessReactionCategory.REPORT_TO_AUTHORITY, WitnessReactionCategory.HOSTILE, WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE} else 0
            respect_delta = 1 if incident.category == SocialIncidentCategory.AID_OR_HEALING and reaction_category in {WitnessReactionCategory.CURIOUS, WitnessReactionCategory.IGNORE} else 0
            if suspicion_delta or respect_delta:
                changed = replace(reputation, suspicion=min(10, reputation.suspicion + suspicion_delta), respect=min(10, reputation.respect + respect_delta), attitude=self._attitude_from_metrics(trust=reputation.trust, suspicion=min(10, reputation.suspicion + suspicion_delta), fear=reputation.fear, respect=min(10, reputation.respect + respect_delta), gratitude=reputation.gratitude))
                updated.location_reputations[location_id] = self._link_reputation_incident(changed, incident_id=incident.incident_id, summary=incident.summary, timestamp_seconds=clock_seconds)
                emitted.append(ReputationChangedEvent(holder_id=location_id, holder_label=updated.location_reputations[location_id].holder_label, summary=incident.summary, suspicion=updated.location_reputations[location_id].suspicion, respect=updated.location_reputations[location_id].respect, fear=updated.location_reputations[location_id].fear, trust=updated.location_reputations[location_id].trust))
                if incident.category == SocialIncidentCategory.AID_OR_HEALING:
                    task = self._schedule_propagation(updated, incident_id=incident.incident_id, propagation_kind=SocialPropagationKind.LOCAL_RUMOR, source_id=witness_id, target_id=location_id, due_at_seconds=clock_seconds + 30 * 60, summary=f'Word of the party\'s magic begins to circulate around {updated.location_reputations[location_id].holder_label}.', public_visible=True, chain_id='chain:local-rumor')
                    if task is not None:
                        emitted.append(SocialPropagationScheduledEvent(task=task))
        return updated

    def _relationship_from_npc_state(self, npc_state: NpcInfluenceState, *, existing: SocialRelationshipState | None, timestamp_seconds: int) -> SocialRelationshipState:
        respect = 0 if existing is None else existing.respect
        gratitude = 0 if existing is None else existing.gratitude
        known_incident_ids = () if existing is None else existing.known_incident_ids
        return SocialRelationshipState(
            relationship_id=self._npc_relationship_id(npc_state.npc_id),
            source_id=npc_state.npc_id,
            source_label=npc_state.display_name,
            target_id=self.PARTY_ID,
            target_label=self.PARTY_LABEL,
            current_stance=npc_state.current_stance,
            attitude=npc_state.attitude,
            willingness=self._willingness_from_raw(attitude=npc_state.attitude, trust=npc_state.trust, suspicion=max(0, npc_state.hostility), fear=npc_state.fear, respect=respect, gratitude=gratitude, obligation=npc_state.obligation, leverage=npc_state.leverage),
            trust=max(0, npc_state.trust),
            suspicion=max(0, npc_state.hostility),
            fear=max(0, npc_state.fear),
            respect=respect,
            gratitude=gratitude,
            leverage=max(0, npc_state.leverage),
            obligation=max(0, npc_state.obligation),
            temporary_tags=(() if existing is None else existing.temporary_tags),
            known_incident_ids=known_incident_ids,
            last_interaction_incident_id=(None if existing is None else existing.last_interaction_incident_id),
            last_interaction_scene_id=(None if existing is None else existing.last_interaction_scene_id),
            last_interaction_kind=(None if existing is None else existing.last_interaction_kind),
            last_updated_seconds=timestamp_seconds,
            last_summary=npc_state.last_summary,
        )

    def _apply_witness_reaction(self, relationship: SocialRelationshipState, reaction_category: WitnessReactionCategory, *, summary: str, timestamp_seconds: int) -> SocialRelationshipState:
        trust = relationship.trust
        suspicion = relationship.suspicion
        fear = relationship.fear
        respect = relationship.respect
        gratitude = relationship.gratitude
        if reaction_category == WitnessReactionCategory.CURIOUS:
            respect += 1
        elif reaction_category == WitnessReactionCategory.MILDLY_WARY:
            suspicion += 1
        elif reaction_category == WitnessReactionCategory.SUSPICIOUS:
            suspicion += 2
            trust = max(0, trust - 1)
        elif reaction_category == WitnessReactionCategory.ALARMED:
            suspicion += 2
            fear += 1
            trust = max(0, trust - 1)
        elif reaction_category == WitnessReactionCategory.CONFRONTATIONAL:
            suspicion += 3
            fear += 1
            respect = max(0, respect - 1)
        elif reaction_category == WitnessReactionCategory.REPORT_TO_AUTHORITY:
            suspicion += 2
            respect = max(0, respect - 1)
        elif reaction_category == WitnessReactionCategory.HOSTILE:
            suspicion += 4
            fear += 2
            trust = max(0, trust - 2)
            respect = max(0, respect - 1)
        elif reaction_category == WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE:
            suspicion += 3
            fear += 2
            trust = max(0, trust - 2)
            respect = max(0, respect - 1)
        attitude = self._attitude_from_metrics(trust=trust, suspicion=suspicion, fear=fear, respect=respect, gratitude=gratitude)
        return replace(relationship, attitude=attitude, willingness=self._willingness_from_raw(attitude=attitude, trust=trust, suspicion=suspicion, fear=fear, respect=respect, gratitude=gratitude, obligation=relationship.obligation, leverage=relationship.leverage), trust=min(10, trust), suspicion=min(10, suspicion), fear=min(10, fear), respect=min(10, respect), gratitude=min(10, gratitude), last_updated_seconds=timestamp_seconds, last_summary=summary, current_stance=(summary if summary else relationship.current_stance))

    def _spell_incident_category(self, context: StoryModeCastContext, social_reaction_plan: SpellcastingSocialReactionPlan | None) -> SocialIncidentCategory:
        lower = context.spell_name.lower()
        if lower in {'cure wounds', 'healing word', 'spare the dying', 'goodberry'}:
            return SocialIncidentCategory.AID_OR_HEALING
        if social_reaction_plan is not None:
            categories = {reaction.reaction_category for reaction in social_reaction_plan.witness_reactions}
            if categories.intersection({SpellcastingReactionCategory.HOSTILE, SpellcastingReactionCategory.ESCALATES_TO_MODE_SWITCH_CANDIDATE}):
                return SocialIncidentCategory.HOSTILE_SPELLCASTING
            if categories.intersection({SpellcastingReactionCategory.SUSPICIOUS, SpellcastingReactionCategory.ALARMED, SpellcastingReactionCategory.CONFRONTATIONAL, SpellcastingReactionCategory.REPORT_TO_AUTHORITY}):
                return SocialIncidentCategory.SUSPICIOUS_SPELLCASTING
        return SocialIncidentCategory.WITNESSED_SPELLCASTING

    def _spell_incident_severity(self, social_reaction_plan: SpellcastingSocialReactionPlan | None) -> SocialIncidentSeverity:
        if social_reaction_plan is None or not social_reaction_plan.witness_reactions:
            return SocialIncidentSeverity.LOW
        categories = {reaction.reaction_category for reaction in social_reaction_plan.witness_reactions}
        if SpellcastingReactionCategory.HOSTILE in categories or SpellcastingReactionCategory.ESCALATES_TO_MODE_SWITCH_CANDIDATE in categories:
            return SocialIncidentSeverity.HIGH
        if categories.intersection({SpellcastingReactionCategory.CONFRONTATIONAL, SpellcastingReactionCategory.ALARMED, SpellcastingReactionCategory.REPORT_TO_AUTHORITY}):
            return SocialIncidentSeverity.MODERATE
        return SocialIncidentSeverity.LOW

    def _witness_reaction_category(self, reaction_category: SpellcastingReactionCategory | None) -> WitnessReactionCategory:
        if reaction_category is None:
            return WitnessReactionCategory.NONE
        mapping = {
            SpellcastingReactionCategory.NO_REACTION: WitnessReactionCategory.NONE,
            SpellcastingReactionCategory.NOTICES_BUT_IGNORES: WitnessReactionCategory.IGNORE,
            SpellcastingReactionCategory.CURIOUS: WitnessReactionCategory.CURIOUS,
            SpellcastingReactionCategory.MILDLY_WARY: WitnessReactionCategory.MILDLY_WARY,
            SpellcastingReactionCategory.SOCIALLY_DISAPPROVING: WitnessReactionCategory.SUSPICIOUS,
            SpellcastingReactionCategory.SUSPICIOUS: WitnessReactionCategory.SUSPICIOUS,
            SpellcastingReactionCategory.ALARMED: WitnessReactionCategory.ALARMED,
            SpellcastingReactionCategory.CONFRONTATIONAL: WitnessReactionCategory.CONFRONTATIONAL,
            SpellcastingReactionCategory.REPORT_TO_AUTHORITY: WitnessReactionCategory.REPORT_TO_AUTHORITY,
            SpellcastingReactionCategory.HOSTILE: WitnessReactionCategory.HOSTILE,
            SpellcastingReactionCategory.ESCALATES_TO_MODE_SWITCH_CANDIDATE: WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE,
        }
        return mapping[reaction_category]

    def _npc_relationship_id(self, npc_id: str) -> str:
        return f'relationship:{npc_id}:{self.PARTY_ID}'

    def _location_authority_id(self, location_id: str, authority_id: str) -> str:
        return f'authority-state:{location_id}:{authority_id}:{self.PARTY_ID}'

    def _cooldown_id(self, actor_id: str, npc_id: str, approach: SocialApproachType) -> str:
        return f'cooldown:{actor_id}:{npc_id}:{approach.value}'

    def _npc_label(self, npc_id: str) -> str:
        template = self.content_pack.npc_templates.get(npc_id)
        if template is not None:
            return template.label
        return npc_id.replace('-', ' ').title()

    def _effective_norm_scope(self, profile: NormProfile) -> NormScope:
        if profile.scope != NormScope.LOCATION:
            return profile.scope
        mapping = {
            'scene': NormScope.SCENE_OVERRIDE,
            'scene_override': NormScope.SCENE_OVERRIDE,
            'npc': NormScope.NPC,
            'institution': NormScope.INSTITUTION,
            'faction': NormScope.FACTION,
            'location': NormScope.LOCATION,
            'settlement': NormScope.SETTLEMENT_DEFAULT,
            'settlement_default': NormScope.SETTLEMENT_DEFAULT,
        }
        return mapping.get(profile.applies_to_kind, profile.scope)

    def _norm_scope_rank(self, state: SocialRuntimeState, scope: NormScope) -> int:
        ordered = state.norm_merge_policy.ordered_scopes
        try:
            return ordered.index(scope)
        except ValueError:
            return len(ordered)

    def _attitude_from_metrics(self, *, trust: int, suspicion: int, fear: int, respect: int, gratitude: int) -> NpcAttitude:
        if suspicion + fear >= 6:
            return NpcAttitude.HOSTILE
        if trust + respect + gratitude >= 6:
            return NpcAttitude.FRIENDLY
        if trust + respect >= 2:
            return NpcAttitude.COOPERATIVE
        if suspicion >= 2 or fear >= 1:
            return NpcAttitude.WARY
        return NpcAttitude.RESERVED

    def _willingness_from_metrics(self, relationship: SocialRelationshipState) -> InfluenceWillingnessState:
        return self._willingness_from_raw(
            attitude=relationship.attitude,
            trust=relationship.trust,
            suspicion=relationship.suspicion,
            fear=relationship.fear,
            respect=relationship.respect,
            gratitude=relationship.gratitude,
            obligation=relationship.obligation,
            leverage=relationship.leverage,
        )

    def _willingness_from_raw(self, *, attitude: NpcAttitude, trust: int, suspicion: int, fear: int, respect: int, gratitude: int, obligation: int, leverage: int) -> InfluenceWillingnessState:
        if attitude == NpcAttitude.HOSTILE or suspicion >= 4:
            return InfluenceWillingnessState.REFUSING
        if trust + respect + gratitude + obligation + leverage >= 4 and suspicion <= 1 and fear <= 1:
            return InfluenceWillingnessState.WILLING
        return InfluenceWillingnessState.HESITANT

    def _register_incident(self, state: SocialRuntimeState, incident: SocialIncident) -> tuple[SocialIncident, bool]:
        dedupe_key = incident.dedupe_key or incident.incident_id
        existing_id = state.incident_dedupe.get(dedupe_key)
        if existing_id is not None and existing_id in state.incidents:
            return state.incidents[existing_id], False
        state.incidents[incident.incident_id] = incident
        state.incident_dedupe[dedupe_key] = incident.incident_id
        return incident, True

    def _attach_witness_record(self, state: SocialRuntimeState, incident_id: str, record: IncidentWitnessRecord) -> IncidentWitnessRecord:
        existing = state.incident_witness_records.get(record.record_id)
        if existing is not None:
            return existing
        state.incident_witness_records[record.record_id] = record
        incident = state.incidents[incident_id]
        state.incidents[incident_id] = replace(
            incident,
            witness_ids=self._append_unique_tuple(incident.witness_ids, record.witness_id),
            witness_record_ids=self._append_unique_tuple(incident.witness_record_ids, record.record_id),
        )
        return record

    def _attach_interpretation_record(self, state: SocialRuntimeState, incident_id: str, record: IncidentInterpretationRecord) -> IncidentInterpretationRecord:
        existing = state.incident_interpretations.get(record.record_id)
        if existing is not None:
            return existing
        state.incident_interpretations[record.record_id] = record
        incident = state.incidents[incident_id]
        state.incidents[incident_id] = replace(incident, interpretation_record_ids=self._append_unique_tuple(incident.interpretation_record_ids, record.record_id))
        return record

    def _schedule_propagation(
        self,
        state: SocialRuntimeState,
        *,
        incident_id: str,
        propagation_kind: SocialPropagationKind,
        source_id: str,
        target_id: str,
        due_at_seconds: int,
        summary: str,
        public_visible: bool = False,
        chain_id: str = '',
    ) -> SocialPropagationTask | None:
        for task in state.propagation_queue.values():
            if task.cancelled:
                continue
            if task.incident_id == incident_id and task.propagation_kind == propagation_kind and task.source_id == source_id and task.target_id == target_id:
                return None
        for record in state.incident_propagations.values():
            if record.incident_id == incident_id and record.propagation_kind == propagation_kind and record.source_id == source_id and record.target_id == target_id and record.status != PropagationStatus.CANCELLED:
                return None
        record_id = f'propagation-record:{incident_id}:{propagation_kind.value}:{target_id}:{len(state.incident_propagations) + 1}'
        task = SocialPropagationTask(
            task_id=f'task:{incident_id}:{propagation_kind.value}:{target_id}:{len(state.propagation_queue) + 1}',
            incident_id=incident_id,
            propagation_kind=propagation_kind,
            source_id=source_id,
            target_id=target_id,
            due_at_seconds=due_at_seconds,
            summary=summary,
            public_visible=public_visible,
            related_record_id=record_id,
            chain_id=chain_id,
        )
        record = IncidentPropagationRecord(
            record_id=record_id,
            incident_id=incident_id,
            propagation_kind=propagation_kind,
            source_id=source_id,
            target_id=target_id,
            due_at_seconds=due_at_seconds,
            status=PropagationStatus.SCHEDULED,
            summary=summary,
            public_visible=public_visible,
            chain_id=chain_id,
        )
        state.incident_propagations[record_id] = record
        state.propagation_queue[task.task_id] = task
        incident = state.incidents[incident_id]
        state.incidents[incident_id] = replace(incident, propagation_record_ids=self._append_unique_tuple(incident.propagation_record_ids, record_id))
        return task

    def _mark_propagation_record(self, state: SocialRuntimeState, *, record_id: str | None, status: PropagationStatus) -> None:
        if record_id is None:
            return
        record = state.incident_propagations.get(record_id)
        if record is None:
            return
        state.incident_propagations[record_id] = replace(record, status=status)

    def _link_relationship_incident(self, relationship: SocialRelationshipState, *, incident_id: str, incident_category: SocialIncidentCategory | None, scene_id: str | None, summary: str, timestamp_seconds: int) -> SocialRelationshipState:
        return replace(
            relationship,
            known_incident_ids=self._append_unique_tuple(relationship.known_incident_ids, incident_id),
            last_interaction_incident_id=incident_id,
            last_interaction_scene_id=scene_id,
            last_interaction_kind=incident_category,
            last_updated_seconds=timestamp_seconds,
            last_summary=summary or relationship.last_summary,
        )

    def _link_reputation_incident(self, reputation: ReputationState, *, incident_id: str, summary: str, timestamp_seconds: int) -> ReputationState:
        return replace(
            reputation,
            known_incident_ids=self._append_unique_tuple(reputation.known_incident_ids, incident_id),
            last_updated_seconds=timestamp_seconds,
            last_summary=summary or reputation.last_summary,
        )

    def _link_faction_incident(self, relationship: FactionRelationshipState, *, incident_id: str, summary: str, timestamp_seconds: int) -> FactionRelationshipState:
        return replace(
            relationship,
            known_incident_ids=self._append_unique_tuple(relationship.known_incident_ids, incident_id),
            last_updated_seconds=timestamp_seconds,
            last_summary=summary or relationship.last_summary,
        )

    def _link_location_authority_incident(self, state: LocationAuthorityState, *, incident_id: str, summary: str, timestamp_seconds: int, current_alert: str = '') -> LocationAuthorityState:
        return replace(
            state,
            known_incident_ids=self._append_unique_tuple(state.known_incident_ids, incident_id),
            current_alert=current_alert or state.current_alert,
            last_updated_seconds=timestamp_seconds,
            last_summary=summary or state.last_summary,
        )

    def _perception_level(self, witness) -> WitnessPerceptionLevel:
        if witness.perceived_casting_act:
            return WitnessPerceptionLevel.CLEAR_ACT
        if witness.perceived_spell_effect:
            return WitnessPerceptionLevel.EFFECT_ONLY
        return WitnessPerceptionLevel.NONE

    def _interpretation_from_reaction(self, reaction_category: WitnessReactionCategory, incident: SocialIncident, norm_evaluation: IncidentNormEvaluation) -> SocialInterpretationCategory:
        if reaction_category == WitnessReactionCategory.NONE or reaction_category == WitnessReactionCategory.IGNORE:
            if incident.category == SocialIncidentCategory.AID_OR_HEALING:
                return SocialInterpretationCategory.HEROIC
            return SocialInterpretationCategory.HARMLESS
        if reaction_category == WitnessReactionCategory.CURIOUS:
            return SocialInterpretationCategory.ODD
        if reaction_category == WitnessReactionCategory.MILDLY_WARY:
            return SocialInterpretationCategory.ALARMING_BUT_NOT_HOSTILE
        if reaction_category == WitnessReactionCategory.SUSPICIOUS:
            if 'anti_enchantment' in norm_evaluation.applied_tags:
                return SocialInterpretationCategory.MANIPULATIVE
            return SocialInterpretationCategory.SUSPICIOUS
        if reaction_category == WitnessReactionCategory.ALARMED:
            if 'restricted_magic' in norm_evaluation.applied_tags or 'public_order_sensitive' in norm_evaluation.applied_tags:
                return SocialInterpretationCategory.CRIMINAL
            return SocialInterpretationCategory.ALARMING_BUT_NOT_HOSTILE
        if reaction_category == WitnessReactionCategory.REPORT_TO_AUTHORITY:
            return SocialInterpretationCategory.CRIMINAL
        if reaction_category in {WitnessReactionCategory.CONFRONTATIONAL, WitnessReactionCategory.HOSTILE, WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE}:
            return SocialInterpretationCategory.HOSTILE
        return SocialInterpretationCategory.FORGIVABLE

    def _immediate_reaction_from_witness_category(self, reaction_category: WitnessReactionCategory) -> SocialImmediateReaction:
        mapping = {
            WitnessReactionCategory.NONE: SocialImmediateReaction.NO_REACTION,
            WitnessReactionCategory.IGNORE: SocialImmediateReaction.NOTICES_BUT_IGNORES,
            WitnessReactionCategory.CURIOUS: SocialImmediateReaction.WATCHES_CLOSELY,
            WitnessReactionCategory.MILDLY_WARY: SocialImmediateReaction.BECOMES_WARY,
            WitnessReactionCategory.SUSPICIOUS: SocialImmediateReaction.WATCHES_CLOSELY,
            WitnessReactionCategory.ALARMED: SocialImmediateReaction.CALLS_AUTHORITY,
            WitnessReactionCategory.CONFRONTATIONAL: SocialImmediateReaction.CONFRONTS,
            WitnessReactionCategory.REPORT_TO_AUTHORITY: SocialImmediateReaction.REPORTS_LATER,
            WitnessReactionCategory.HOSTILE: SocialImmediateReaction.THREATENS,
            WitnessReactionCategory.ESCALATE_TO_COMBAT_CANDIDATE: SocialImmediateReaction.ESCALATES_TO_COMBAT_CANDIDATE,
        }
        return mapping[reaction_category]

    def _severity_rank(self, severity: SocialIncidentSeverity) -> int:
        order = {
            SocialIncidentSeverity.TRIVIAL: 0,
            SocialIncidentSeverity.LOW: 1,
            SocialIncidentSeverity.MODERATE: 2,
            SocialIncidentSeverity.HIGH: 3,
            SocialIncidentSeverity.EXTREME: 4,
        }
        return order[severity]

    def _apply_consequence_templates(
        self,
        state: SocialRuntimeState,
        *,
        incident_id: str,
        witness_id: str,
        witness_label: str,
        scene_id: str | None,
        location_id: str | None,
        reaction_category: WitnessReactionCategory,
        norm_evaluation: IncidentNormEvaluation,
        clock_seconds: int,
        emitted: list[object],
        notes: list[str],
        open_loops: list[str],
    ) -> None:
        incident = state.incidents[incident_id]
        templates = self.applicable_consequence_templates(
            incident=incident,
            witness_id=witness_id,
            scene_id=scene_id,
            location_id=location_id,
            reaction_category=reaction_category,
            norm_evaluation=norm_evaluation,
        )
        if not templates:
            return
        relationship_id = self._npc_relationship_id(witness_id)
        relationship = state.relationships.get(relationship_id)
        for template in templates:
            incident = state.incidents[incident_id]
            state.incidents[incident_id] = replace(incident, consequence_template_ids=self._append_unique_tuple(incident.consequence_template_ids, template.template_id))
            emitted.append(IncidentConsequenceTemplateSelectedEvent(incident_id=incident_id, template_id=template.template_id, summary=template.label))
            if relationship is not None and template.relationship_tags:
                tagged_relationship = replace(relationship, temporary_tags=self._append_unique_values(relationship.temporary_tags, template.relationship_tags))
                state.relationships[relationship_id] = tagged_relationship
                relationship = tagged_relationship
                emitted.append(ImmediateSocialConsequenceAppliedEvent(incident_id=incident_id, template_id=template.template_id, target_kind='npc', target_id=witness_id, summary=template.label))
            for faction_id in set(self.npc_factions.get(witness_id, ())).intersection(template.faction_ids or set(self.npc_factions.get(witness_id, ()))):
                faction_state = state.faction_relationships.get(faction_id)
                if faction_state is None or not template.faction_tags:
                    continue
                state.faction_relationships[faction_id] = replace(faction_state, temporary_tags=self._append_unique_values(faction_state.temporary_tags, template.faction_tags))
                emitted.append(FactionMemoryUpdatedEvent(faction_id=faction_id, summary=template.label))
            if template.authority_tags and location_id is not None:
                authority_id = self.authority_by_location.get(location_id)
                if authority_id is not None:
                    authority_key = self._location_authority_id(location_id, authority_id)
                    authority_state = state.location_authorities.get(authority_key)
                    if authority_state is not None:
                        state.location_authorities[authority_key] = replace(authority_state, temporary_tags=self._append_unique_values(authority_state.temporary_tags, template.authority_tags))
                        emitted.append(AuthorityAttentionRaisedEvent(authority_id=authority_id, location_id=location_id, summary=template.label))
            if template.party_summary:
                projection_id = f'projection:consequence:{incident_id}:{template.template_id}:party'
                state.known_projections[projection_id] = KnownReputationProjection(
                    projection_id=projection_id,
                    audience=SocialKnowledgeAudience.PARTY_KNOWN,
                    label=template.label,
                    summary=template.party_summary,
                    related_incident_id=incident_id,
                    last_updated_seconds=clock_seconds,
                )
                emitted.append(KnownConsequenceProjectionUpdatedEvent(projection_id=projection_id, audience=SocialKnowledgeAudience.PARTY_KNOWN.value, summary=template.party_summary))
            if template.dm_summary:
                projection_id = f'projection:consequence:{incident_id}:{template.template_id}:dm'
                state.known_projections[projection_id] = KnownReputationProjection(
                    projection_id=projection_id,
                    audience=SocialKnowledgeAudience.DM_ONLY,
                    label=template.label,
                    summary=template.dm_summary,
                    related_incident_id=incident_id,
                    last_updated_seconds=clock_seconds,
                )
                emitted.append(KnownConsequenceProjectionUpdatedEvent(projection_id=projection_id, audience=SocialKnowledgeAudience.DM_ONLY.value, summary=template.dm_summary))
            if template.open_loop:
                open_loops.append(template.open_loop)
            for chain_id in template.propagation_chain_ids:
                chain = self.propagation_chain_for(chain_id)
                if chain is None:
                    continue
                self._schedule_chain_template(
                    state,
                    incident_id=incident_id,
                    witness_id=witness_id,
                    witness_label=witness_label,
                    location_id=location_id,
                    chain=chain,
                    clock_seconds=clock_seconds,
                    emitted=emitted,
                    notes=notes,
                    norm_evaluation=norm_evaluation,
                    reaction_category=reaction_category,
                )

    def _schedule_chain_template(
        self,
        state: SocialRuntimeState,
        *,
        incident_id: str,
        witness_id: str,
        witness_label: str,
        location_id: str | None,
        chain: PropagationChainTemplate,
        clock_seconds: int,
        emitted: list[object],
        notes: list[str],
        norm_evaluation: IncidentNormEvaluation,
        reaction_category: WitnessReactionCategory,
    ) -> None:
        applied_tags = {MagicalNormTag(tag) if not isinstance(tag, MagicalNormTag) else tag for tag in norm_evaluation.applied_tags}
        if chain.required_norm_tags and not set(chain.required_norm_tags).issubset(applied_tags):
            return
        if chain.reaction_categories and reaction_category not in chain.reaction_categories:
            return
        witness_archetype = self.witness_archetype_for(witness_id, scene_id=state.incidents[incident_id].scene_id, location_id=location_id)
        if chain.witness_archetype_ids and (witness_archetype is None or witness_archetype.archetype_id not in chain.witness_archetype_ids):
            return
        witness_factions = self.npc_factions.get(witness_id, ())
        if chain.required_faction_ids and not set(witness_factions).intersection(chain.required_faction_ids):
            return
        targets: list[str] = []
        if chain.target_mode == 'location' and location_id is not None:
            targets.append(location_id)
        elif chain.target_mode == 'location_authority' and location_id is not None:
            authority_id = self.authority_by_location.get(location_id)
            if authority_id is not None:
                targets.append(authority_id)
        elif chain.target_mode == 'witness_factions':
            targets.extend(witness_factions)
        elif chain.target_mode == 'specific_faction' and chain.target_id:
            targets.append(chain.target_id)
        for target_id in self._unique(list(targets)):
            target_label = self.location_labels.get(target_id) or self.faction_labels.get(target_id) or target_id.replace('-', ' ').title()
            summary = chain.summary_template.format(
                witness_label=witness_label,
                target_label=target_label,
                location_label=(self.location_labels.get(location_id, location_id.replace('-', ' ').title()) if location_id is not None else 'the area'),
            )
            task = self._schedule_propagation(
                state,
                incident_id=incident_id,
                propagation_kind=chain.propagation_kind,
                source_id=witness_id,
                target_id=target_id,
                due_at_seconds=clock_seconds + chain.delay_seconds,
                summary=summary,
                public_visible=chain.public_visible,
                chain_id=chain.chain_id,
            )
            if task is None:
                continue
            emitted.append(SocialPropagationScheduledEvent(task=task))
            emitted.append(PropagationChainScheduledEvent(incident_id=incident_id, chain_id=chain.chain_id, target_id=target_id, summary=summary))
            notes.append(summary)

    def _append_unique_tuple(self, values: tuple[str, ...], value: str | None) -> tuple[str, ...]:
        if value is None:
            return values
        normalized = value.strip()
        if not normalized or normalized in values:
            return values
        return values + (normalized,)

    def _append_unique_values(self, values: tuple[str, ...], additions: tuple[str, ...]) -> tuple[str, ...]:
        updated = values
        for item in additions:
            updated = self._append_unique_tuple(updated, item)
        return updated

    def _copy_state(self, state: SocialRuntimeState) -> SocialRuntimeState:
        return SocialRuntimeState(
            relationships=dict(state.relationships),
            location_reputations=dict(state.location_reputations),
            authority_reputations=dict(state.authority_reputations),
            faction_relationships=dict(state.faction_relationships),
            location_authorities=dict(state.location_authorities),
            incidents=dict(state.incidents),
            incident_witness_records=dict(state.incident_witness_records),
            incident_interpretations=dict(state.incident_interpretations),
            incident_propagations=dict(state.incident_propagations),
            incident_dedupe=dict(state.incident_dedupe),
            witness_memories=dict(state.witness_memories),
            norm_profiles=dict(state.norm_profiles),
            norm_merge_policy=state.norm_merge_policy,
            propagation_queue=dict(state.propagation_queue),
            retry_cooldowns=dict(state.retry_cooldowns),
            known_projections=dict(state.known_projections),
        )

    def _unique(self, values: list[str]) -> tuple[str, ...]:
        seen: set[str] = set()
        ordered: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            ordered.append(normalized)
        return tuple(ordered)


