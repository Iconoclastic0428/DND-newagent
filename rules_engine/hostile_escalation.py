from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import json
from pathlib import Path
import re
from types import SimpleNamespace

from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from shared_types.battlefield import BattlefieldFeature, BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, TraversalMode
from shared_types.encounter_models import ActorSide, EncounterState, GridPosition, RuntimeActorState
from shared_types.exploration import ExplorationState
from shared_types.hostile_escalation import (
    AdHocEncounterSceneKind,
    AdHocEncounterScenePlan,
    CombatParticipantGoal,
    CombatTransitionState,
    FallbackNpcCombatArchetype,
    HostileActionKind,
    HostileEscalationDecision,
    HostileEscalationOutcome,
    ReinforcementPlan,
    StoryCombatantContext,
    SynthesizedCombatantSourceKind,
    SynthesizedCombatantSpec,
)
from shared_types.storytelling import EnterCombatPlan, StoryModeCastContext, WitnessObservationPacket


_HOSTILE_ACTION_PATTERNS = (
    re.compile(r'\b(attack|stab|slash|strike|shoot|punch|kick|smash|tackle)\b'),
    re.compile(r'\b(grapple|grab|seize|wrestle|shove)\b'),
    re.compile(r'\b(block|bar)\b.*\b(door|exit|path|way)\b'),
)
_THREAT_ONLY_PATTERNS = (
    re.compile(r'\b(threaten|warn|promise|tell)\b'),
    re.compile(r'\bkill you\b'),
    re.compile(r'\bwe should fight\b'),
)


@dataclass(frozen=True)
class SceneNpcCombatHint:
    npc_id: str
    display_name: str
    preferred_monster_names: tuple[str, ...]
    fallback_archetype: FallbackNpcCombatArchetype
    goal: CombatParticipantGoal
    protects_npc_ids: tuple[str, ...] = ()
    faction_tags: tuple[str, ...] = ()
    authority_tags: tuple[str, ...] = ()
    preferred_monster_ids: tuple[str, ...] = ()
    current_stance: str | None = None
    calls_watch: bool = False


@dataclass(frozen=True)
class HydratedEnterCombatPlan:
    plan: EnterCombatPlan
    battlefield: BattlefieldState


class HostileEscalationEngine:
    def __init__(self, *, runtime_services=None, campaign_id: str = 'lmop', campaign_root: str | Path | None = None) -> None:
        self.runtime_services = None
        self.campaign_id = campaign_id
        self.campaign_root: Path | None = None
        self.npc_hints: dict[str, SceneNpcCombatHint] = {}
        self.archetype_monster_ids: dict[FallbackNpcCombatArchetype, str] = {}
        self.configure(runtime_services=runtime_services, campaign_id=campaign_id, campaign_root=campaign_root)

    def configure(self, *, runtime_services=None, campaign_id: str | None = None, campaign_root: str | Path | None = None) -> None:
        if campaign_id is not None:
            self.campaign_id = campaign_id
        if runtime_services is not None:
            self.runtime_services = runtime_services
        if campaign_root is not None:
            self.campaign_root = Path(campaign_root).resolve()
        self.npc_hints = self._load_npc_hints()
        self.archetype_monster_ids = self._resolve_archetype_monster_ids() if self.runtime_services is not None else {}

    def evaluate_declaration(
        self,
        *,
        encounter_state: EncounterState,
        story_state,
        exploration_state: ExplorationState | None,
        actor_id: str,
        declaration: str,
        visible_npc_ids: tuple[str, ...],
    ) -> HostileEscalationDecision:
        lowered = declaration.strip().casefold()
        if not lowered:
            return HostileEscalationDecision(
                outcome=HostileEscalationOutcome.REMAIN_IN_STORY_MODE,
                action_kind=HostileActionKind.INITIATIVE_SENSITIVE_STANDOFF,
                reason='Empty declaration.',
                hostile_actor_id=actor_id,
            )
        overt_hostile = any(pattern.search(lowered) for pattern in _HOSTILE_ACTION_PATTERNS)
        threat_only = any(pattern.search(lowered) for pattern in _THREAT_ONLY_PATTERNS) and not overt_hostile
        if threat_only or not overt_hostile:
            return HostileEscalationDecision(
                outcome=HostileEscalationOutcome.REMAIN_IN_STORY_MODE,
                action_kind=HostileActionKind.INITIATIVE_SENSITIVE_STANDOFF,
                reason='The declaration is threatening or tense, but no overt hostile act has begun yet.',
                hostile_actor_id=actor_id,
            )
        target_npc_id = self._extract_target_npc_id(declaration, visible_npc_ids)
        target_actor_id = self._extract_target_actor_id(encounter_state, declaration, actor_id=actor_id)
        if target_npc_id is None and target_actor_id is None:
            return HostileEscalationDecision(
                outcome=HostileEscalationOutcome.CLARIFICATION_REQUIRED,
                action_kind=HostileActionKind.ATTACK_ATTEMPT,
                reason='The declaration is overtly hostile, but the target is not clear enough to synthesize combat.',
                hostile_actor_id=actor_id,
                clarification_prompt='Who are you trying to attack or physically force into the fight?',
            )
        outcome = self._scene_reinforcement_outcome(story_state=story_state)
        action_kind = HostileActionKind.ATTACK_ATTEMPT
        if any(token in lowered for token in ('grapple', 'grab', 'seize', 'wrestle', 'shove')):
            action_kind = HostileActionKind.GRAPPLE_ATTEMPT
        elif 'block' in lowered or 'bar' in lowered:
            action_kind = HostileActionKind.BLOCK_PATH
        return HostileEscalationDecision(
            outcome=outcome,
            action_kind=action_kind,
            reason='An overt hostile action makes order of actions matter now.',
            hostile_actor_id=actor_id,
            target_actor_id=target_actor_id,
            target_npc_id=target_npc_id,
            scene_tension='hostile',
            order_now_matters=True,
            witnesses_notice=bool(visible_npc_ids),
            witness_ids=visible_npc_ids,
            opening_action_summary=declaration.strip(),
        )

    def evaluate_spellcast(
        self,
        *,
        encounter_state: EncounterState,
        story_state,
        exploration_state: ExplorationState | None,
        context: StoryModeCastContext,
        witness_packet: WitnessObservationPacket,
        spell_signal_tags: tuple[str, ...],
    ) -> HostileEscalationDecision:
        tags = set(spell_signal_tags)
        if 'harmful' not in tags and 'manipulative' not in tags:
            return HostileEscalationDecision(
                outcome=HostileEscalationOutcome.REMAIN_IN_STORY_MODE,
                action_kind=HostileActionKind.HARMFUL_SPELL,
                reason='The spell is not overtly harmful or coercive enough to require immediate initiative.',
                hostile_actor_id=context.attempt.actor_id,
                target_actor_id=context.attempt.target_id if context.attempt.target_id in encounter_state.actors else None,
                target_npc_id=(context.attempt.target_id if context.attempt.target_id not in encounter_state.actors else None),
            )
        witnesses_notice = bool(witness_packet.witnesses)
        outcome = self._scene_reinforcement_outcome(story_state=story_state) if witnesses_notice else HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_SURPRISE_CHECK
        return HostileEscalationDecision(
            outcome=outcome,
            action_kind=HostileActionKind.HARMFUL_SPELL,
            reason='A harmful or coercive spell attempt should enter initiative before the spell resolves.',
            hostile_actor_id=context.attempt.actor_id,
            target_actor_id=(context.attempt.target_id if context.attempt.target_id in encounter_state.actors else None),
            target_npc_id=(context.attempt.target_id if context.attempt.target_id not in encounter_state.actors else None),
            scene_tension='hostile',
            order_now_matters=True,
            witnesses_notice=witnesses_notice,
            witness_ids=tuple(w.observer_id for w in witness_packet.witnesses),
            surprised_actor_ids=((context.attempt.target_id,) if not witnesses_notice and context.attempt.target_id in encounter_state.actors else ()),
            opening_action_summary=f'{encounter_state.actors[context.attempt.actor_id].name} begins casting {context.spell_name}.',
        )

    def build_scene_plan(self, *, scene_id: str | None, location_id: str | None) -> AdHocEncounterScenePlan:
        story_state = SimpleNamespace(current_scene_id=scene_id, canonical_location_id=location_id, metadata={})
        plan = EnterCombatPlan(reason='Hostile escalation test scene plan.', participant_ids=(), scene_id=scene_id, location_id=location_id)
        return self._resolve_scene_plan(story_state=story_state, plan=plan)
    def hydrate_decision(
        self,
        *,
        encounter_state: EncounterState,
        story_state,
        exploration_state: ExplorationState | None,
        decision: HostileEscalationDecision,
        visible_npc_ids: tuple[str, ...] = (),
    ) -> HostileEscalationDecision:
        if decision.outcome in {HostileEscalationOutcome.REMAIN_IN_STORY_MODE, HostileEscalationOutcome.CLARIFICATION_REQUIRED}:
            return decision
        if decision.scene_plan is not None and decision.participant_actor_ids:
            return decision
        participant_ids = list(decision.participant_actor_ids)
        if not participant_ids:
            participant_ids.append(decision.hostile_actor_id)
            if decision.target_actor_id is not None:
                participant_ids.append(decision.target_actor_id)
            elif decision.target_npc_id is not None:
                participant_ids.append(decision.target_npc_id)
        hydrated = self.hydrate_enter_combat_plan(
            encounter_state=encounter_state,
            story_state=story_state,
            exploration_state=exploration_state,
            plan=EnterCombatPlan(
                reason=decision.reason,
                participant_ids=tuple(dict.fromkeys(participant_ids)),
                scene_id=story_state.current_scene_id,
                location_id=story_state.canonical_location_id,
                ambush=(decision.outcome == HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_SURPRISE_CHECK),
                battlefield_map_id=(decision.scene_plan.map_id if decision.scene_plan is not None else None),
                surprised_actor_ids=decision.surprised_actor_ids,
                synthesized_combatants=decision.synthesized_combatants,
                reinforcement_plans=decision.reinforcement_plans,
                scene_plan=decision.scene_plan,
                transition_state=decision.transition_state,
            ),
        )
        transition = hydrated.plan.transition_state
        witness_ids = decision.witness_ids or tuple(witness_id for witness_id in visible_npc_ids if witness_id)
        surprised_actor_ids = hydrated.plan.surprised_actor_ids
        if not surprised_actor_ids and hydrated.plan.ambush:
            surprised_actor_ids = tuple(actor_id for actor_id in hydrated.plan.participant_ids if actor_id != decision.hostile_actor_id)
        if transition is not None:
            transition = replace(
                transition,
                witness_ids=(transition.witness_ids or witness_ids),
                synthesized_actor_ids=tuple(spec.actor_id for spec in hydrated.plan.synthesized_combatants),
            )
        return replace(
            decision,
            participant_actor_ids=hydrated.plan.participant_ids,
            synthesized_combatants=hydrated.plan.synthesized_combatants,
            noncombatant_npc_ids=(transition.bystander_npc_ids if transition is not None else decision.noncombatant_npc_ids),
            witness_ids=(transition.witness_ids if transition is not None else witness_ids),
            surprised_actor_ids=surprised_actor_ids,
            reinforcement_plans=hydrated.plan.reinforcement_plans,
            scene_plan=hydrated.plan.scene_plan,
            transition_state=transition,
        )

    def hydrate_enter_combat_plan(
        self,
        *,
        encounter_state: EncounterState,
        story_state,
        exploration_state: ExplorationState | None,
        plan: EnterCombatPlan,
    ) -> HydratedEnterCombatPlan:
        participant_ids = list(plan.participant_ids)
        synthesized_specs = list(plan.synthesized_combatants)
        reinforcement_plans = list(plan.reinforcement_plans)
        social_snapshots = []
        if exploration_state is not None:
            for npc_id, npc_state in exploration_state.npc_states.items():
                social_snapshots.append(
                    StoryCombatantContext(
                        source_label=npc_state.display_name,
                        source_npc_id=npc_id,
                        current_goal=CombatParticipantGoal.BYSTAND,
                        attitude=npc_state.attitude,
                        current_stance=npc_state.current_stance,
                        synthesized=False,
                    )
                )
        if not participant_ids:
            participant_ids.extend(self._default_player_actor_ids(encounter_state))
        unresolved: list[str] = []
        known_npc_ids = {spec.source_npc_id for spec in synthesized_specs if spec.source_npc_id is not None}
        for participant_id in list(participant_ids):
            if participant_id in encounter_state.actors:
                continue
            hint = self.npc_hints.get(participant_id)
            if hint is None:
                unresolved.append(participant_id)
                continue
            spec = self._apply_exploration_npc_context(self._synthesized_spec_from_hint(participant_id, hint), exploration_state)
            if spec.source_npc_id not in known_npc_ids:
                synthesized_specs.append(spec)
                known_npc_ids.add(spec.source_npc_id)
            if spec.actor_id not in participant_ids:
                participant_ids.append(spec.actor_id)
            if spec.actor_id != participant_id and participant_id in participant_ids:
                participant_ids.remove(participant_id)
        if unresolved:
            raise ValueError(f'Cannot synthesize combatants for unknown scene npc ids: {", ".join(unresolved)}.')
        if any(spec.source_npc_id == 'gundren-rockseeker' for spec in synthesized_specs) and all(spec.source_npc_id != 'sildar-hallwinter' for spec in synthesized_specs):
            sildar_hint = self.npc_hints.get('sildar-hallwinter')
            if sildar_hint is not None:
                sildar_spec = self._apply_exploration_npc_context(self._synthesized_spec_from_hint('sildar-hallwinter', sildar_hint), exploration_state)
                participant_ids.append(sildar_spec.actor_id)
                synthesized_specs.append(sildar_spec)
        scene_plan = plan.scene_plan or self._resolve_scene_plan(story_state=story_state, plan=plan)
        if not reinforcement_plans and scene_plan.scene_kind == AdHocEncounterSceneKind.FALLBACK_TAVERN_COMMON_ROOM:
            reinforcement_plans.extend(self._default_watch_reinforcements())
        source_npc_ids = {spec.source_npc_id for spec in synthesized_specs if spec.source_npc_id is not None}
        bystander_npc_ids = ()
        if exploration_state is not None:
            bystander_npc_ids = tuple(npc_id for npc_id in exploration_state.npc_states if npc_id not in source_npc_ids)
        metadata_lines = [scene_plan.summary]
        metadata_lines.extend(f'{snapshot.source_label}: {snapshot.current_stance}' for snapshot in social_snapshots if snapshot.current_stance)
        transition_state = plan.transition_state or CombatTransitionState(
            reason=plan.reason,
            source_scene_id=story_state.current_scene_id,
            source_location_id=story_state.canonical_location_id,
            opening_action_summary='',
            battlefield_map_id=scene_plan.map_id,
            scene_kind=scene_plan.scene_kind,
            fallback_scene=scene_plan.fallback_used,
            synthesized_actor_ids=tuple(spec.actor_id for spec in synthesized_specs),
            witness_ids=tuple(spec.source_npc_id for spec in synthesized_specs if spec.source_npc_id is not None),
            reinforcement_plans=tuple(reinforcement_plans),
            entered_reinforcement_ids=(),
            bystander_npc_ids=bystander_npc_ids,
            metadata_lines=tuple(metadata_lines),
        )
        resolved = EnterCombatPlan(
            reason=plan.reason,
            participant_ids=tuple(dict.fromkeys(participant_ids)),
            scene_id=plan.scene_id or story_state.current_scene_id,
            location_id=plan.location_id or story_state.canonical_location_id,
            ambush=plan.ambush,
            battlefield_map_id=scene_plan.map_id,
            surprised_actor_ids=plan.surprised_actor_ids,
            synthesized_combatants=tuple(synthesized_specs),
            reinforcement_plans=tuple(reinforcement_plans),
            scene_plan=scene_plan,
            transition_state=transition_state,
        )
        return HydratedEnterCombatPlan(plan=resolved, battlefield=deepcopy(scene_plan.battlefield))

    def synthesize_actor(self, runtime_services, spec: SynthesizedCombatantSpec, *, position: GridPosition) -> RuntimeActorState:
        monster_id = spec.monster_id
        source_kind = spec.source_kind
        fallback_archetype = spec.fallback_archetype
        if monster_id is None:
            if fallback_archetype is None:
                raise ValueError(f'Synthesized combatant {spec.actor_id} is missing monster_id and fallback_archetype.')
            monster_id = self._ensure_archetype_monster_id(fallback_archetype)
            source_kind = SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK
        actor = runtime_services.monster_runtime.compile_monster(monster_id=monster_id, actor_id=spec.actor_id, position=position)
        actor.name = spec.display_name
        actor.side = ActorSide.MONSTER
        story_context = StoryCombatantContext(
            source_label=spec.source_label or spec.display_name,
            source_npc_id=spec.source_npc_id,
            source_kind=source_kind,
            fallback_archetype=(fallback_archetype if source_kind == SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK else None),
            current_goal=spec.current_goal,
            attitude=spec.attitude,
            current_stance=spec.current_stance,
            faction_tags=spec.faction_tags,
            authority_tags=spec.authority_tags,
            witness_ids=spec.witness_ids,
            synthesized=True,
        )
        actor.story_npc_id = spec.source_npc_id
        actor.story_combat_goal = spec.current_goal.value
        actor.story_attitude = (spec.attitude.value if spec.attitude is not None else None)
        actor.story_stance = spec.current_stance
        actor.story_faction_tags = spec.faction_tags
        actor.story_authority_tags = spec.authority_tags
        actor.story_synthesized_source = source_kind.value
        actor.story_fallback_archetype = (fallback_archetype.value if fallback_archetype is not None and source_kind == SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK else None)
        actor.story_goal = spec.current_goal.value
        actor.story_context_tags = tuple(dict.fromkeys(spec.faction_tags + spec.authority_tags))
        actor.story_context = story_context
        actor.fallback_synthesized = source_kind == SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK
        return actor

    def reinforcement_actors_for_plan(self, plan: ReinforcementPlan, *, battlefield: BattlefieldState) -> tuple[RuntimeActorState, ...]:
        if self.runtime_services is None:
            raise ValueError('Reinforcement synthesis requires runtime services.')
        positions = battlefield.spawn_zones.get(plan.entry_zone_id, ())
        if len(positions) < len(plan.participant_specs):
            raise ValueError(f'Reinforcement zone {plan.entry_zone_id!r} does not have enough positions.')
        return tuple(self.synthesize_actor(self.runtime_services, spec, position=positions[index]) for index, spec in enumerate(plan.participant_specs))

    def visible_reinforcements(self, transition: CombatTransitionState, *, dm_view: bool) -> tuple[ReinforcementPlan, ...]:
        return tuple(plan for plan in transition.reinforcement_plans if dm_view or plan.public_visible)
    def _resolve_archetype_monster_ids(self) -> dict[FallbackNpcCombatArchetype, str]:
        return {
            FallbackNpcCombatArchetype.COMMONER_NONCOMBATANT: self._monster_id_for_names('Commoner'),
            FallbackNpcCombatArchetype.GUARD_WATCHMAN: self._monster_id_for_names('Guard'),
            FallbackNpcCombatArchetype.VETERAN_BODYGUARD: self._monster_id_for_names('Veteran'),
            FallbackNpcCombatArchetype.SCOUT: self._monster_id_for_names('Scout'),
            FallbackNpcCombatArchetype.MAGE_APPRENTICE: self._monster_id_for_names('Apprentice Wizard', 'Mage'),
            FallbackNpcCombatArchetype.PRIEST_TEMPLE_AGENT: self._monster_id_for_names('Priest', 'Acolyte'),
            FallbackNpcCombatArchetype.NOBLE_MERCHANT_CIVILIAN: self._monster_id_for_names('Noble'),
        }

    def _ensure_archetype_monster_id(self, archetype: FallbackNpcCombatArchetype) -> str:
        if archetype not in self.archetype_monster_ids:
            if self.runtime_services is None:
                raise ValueError('Fallback archetype resolution requires runtime services.')
            self.archetype_monster_ids = self._resolve_archetype_monster_ids()
        return self.archetype_monster_ids[archetype]

    def _monster_id_for_names(self, *names: str) -> str:
        preferred_sources = ('XMM', 'MPMM', 'MM', 'VGM')
        runtime_services = self.runtime_services
        if runtime_services is None:
            raise ValueError('Hostile escalation fallback archetypes require runtime services.')
        matches = [record for record in runtime_services.encounter_catalog.monsters.values() if record.name in names]
        if not matches:
            raise ValueError(f'Missing fallback monster template for {names!r}.')
        matches.sort(key=lambda record: (preferred_sources.index(record.source) if record.source in preferred_sources else len(preferred_sources), record.record_id))
        return matches[0].record_id

    def _extract_target_npc_id(self, declaration: str, visible_npc_ids: tuple[str, ...]) -> str | None:
        lowered = declaration.casefold()
        for npc_id in visible_npc_ids:
            hint = self.npc_hints.get(npc_id)
            if hint is None:
                continue
            display = hint.display_name.casefold()
            if display in lowered or npc_id.replace('-', ' ') in lowered:
                return npc_id
        return None

    def _extract_target_actor_id(self, state: EncounterState, declaration: str, *, actor_id: str) -> str | None:
        lowered = declaration.casefold()
        for candidate_id, candidate in state.actors.items():
            if candidate_id == actor_id:
                continue
            if candidate.name.casefold() in lowered or candidate_id.replace('-', ' ') in lowered:
                return candidate_id
        return None

    def _scene_reinforcement_outcome(self, *, story_state) -> HostileEscalationOutcome:
        scene_text = ' '.join(filter(None, (story_state.current_scene_id, story_state.canonical_location_id, story_state.metadata.get('nearby_tags', ''), story_state.metadata.get('retrieval_tags', '')))).casefold()
        if any(token in scene_text for token in ('waterdeep', 'tavern', 'taproom', 'common-room', 'common room', 'city', 'checkpoint', 'street', 'market')):
            return HostileEscalationOutcome.ESCALATE_TO_COMBAT_WITH_REINFORCEMENT_TIMER
        return HostileEscalationOutcome.ESCALATE_TO_COMBAT

    def _resolve_scene_plan(self, *, story_state, plan: EnterCombatPlan) -> AdHocEncounterScenePlan:
        if plan.battlefield_map_id == 'goblin-ambush-triboar-trail':
            battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
            return AdHocEncounterScenePlan(
                map_id='goblin-ambush-triboar-trail',
                name=battlefield.name,
                scene_kind=AdHocEncounterSceneKind.AUTHORED_MAP,
                battlefield=battlefield,
                fallback_used=False,
                summary='Authored battlefield map loaded for the combat transition.',
                primary_hostile_zone_ids=tuple(sorted(zone_id for zone_id in battlefield.spawn_zones if zone_id != 'players')),
                reinforcement_entry_zone_ids=(),
                bystander_zone_ids=(),
            )
        scene_text = ' '.join(filter(None, (plan.scene_id, plan.location_id, story_state.current_scene_id, story_state.canonical_location_id, story_state.metadata.get('nearby_tags', ''), story_state.metadata.get('retrieval_tags', '')))).casefold()
        if any(token in scene_text for token in ('tavern', 'taproom', 'common-room', 'common room', 'waterdeep', 'inn')):
            return _build_tavern_scene()
        return _build_open_scene(scene_id=plan.scene_id or story_state.current_scene_id or 'story-scene')

    def _default_player_actor_ids(self, state: EncounterState) -> tuple[str, ...]:
        return tuple(actor_id for actor_id, actor in state.actors.items() if actor.side == ActorSide.PLAYER)

    def _apply_exploration_npc_context(self, spec: SynthesizedCombatantSpec, exploration_state: ExplorationState | None) -> SynthesizedCombatantSpec:
        if exploration_state is None or spec.source_npc_id is None:
            return spec
        npc_state = exploration_state.npc_states.get(spec.source_npc_id)
        if npc_state is None:
            return spec
        return replace(spec, attitude=npc_state.attitude, current_stance=(npc_state.current_stance or spec.current_stance))

    def _synthesized_spec_from_hint(self, npc_id: str, hint: SceneNpcCombatHint) -> SynthesizedCombatantSpec:
        monster_id = next((record_id for record_id in hint.preferred_monster_ids if record_id), None)
        source_kind = SynthesizedCombatantSourceKind.LOCAL_NPC_DATA if monster_id is not None else SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK
        if monster_id is None and self.runtime_services is not None:
            for name in hint.preferred_monster_names:
                try:
                    monster_id = self._monster_id_for_names(name)
                    source_kind = SynthesizedCombatantSourceKind.LOCAL_NPC_DATA
                    break
                except ValueError:
                    continue
        if monster_id is None and self.runtime_services is not None:
            monster_id = self._ensure_archetype_monster_id(hint.fallback_archetype)
            source_kind = SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK
        return SynthesizedCombatantSpec(
            actor_id=f'story-{npc_id}',
            display_name=hint.display_name,
            source_npc_id=npc_id,
            monster_id=monster_id,
            source_kind=source_kind,
            current_goal=hint.goal,
            current_stance=hint.current_stance,
            faction_tags=hint.faction_tags,
            authority_tags=hint.authority_tags,
            fallback_archetype=(hint.fallback_archetype if source_kind == SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK else None),
            source_label=hint.display_name,
        )

    def _default_watch_reinforcements(self) -> tuple[ReinforcementPlan, ...]:
        watch_hint = self.npc_hints.get('waterdeep-watch')
        guard_monster_id = None
        guard_archetype = FallbackNpcCombatArchetype.GUARD_WATCHMAN
        if watch_hint is not None:
            guard_monster_id = next((record_id for record_id in watch_hint.preferred_monster_ids if record_id), None)
            guard_archetype = watch_hint.fallback_archetype
        specs = (
            SynthesizedCombatantSpec(
                actor_id='watch-guard-1',
                display_name='Waterdeep Watch Guard 1',
                source_npc_id='waterdeep-watch',
                monster_id=guard_monster_id,
                source_kind=(SynthesizedCombatantSourceKind.LOCAL_NPC_DATA if guard_monster_id is not None else SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK),
                current_goal=CombatParticipantGoal.ARREST,
                fallback_archetype=(None if guard_monster_id is not None else guard_archetype),
                faction_tags=('watch', 'waterdeep'),
                authority_tags=('watch', 'authority'),
                source_label='Waterdeep Watch',
            ),
            SynthesizedCombatantSpec(
                actor_id='watch-guard-2',
                display_name='Waterdeep Watch Guard 2',
                source_npc_id='waterdeep-watch',
                monster_id=guard_monster_id,
                source_kind=(SynthesizedCombatantSourceKind.LOCAL_NPC_DATA if guard_monster_id is not None else SynthesizedCombatantSourceKind.ARCHETYPE_FALLBACK),
                current_goal=CombatParticipantGoal.ARREST,
                fallback_archetype=(None if guard_monster_id is not None else guard_archetype),
                faction_tags=('watch', 'waterdeep'),
                authority_tags=('watch', 'authority'),
                source_label='Waterdeep Watch',
            ),
        )
        return (
            ReinforcementPlan(
                reinforcement_id='waterdeep-watch',
                label='Waterdeep Watch',
                source_label='Waterdeep Watch',
                rounds_until_arrival=3,
                entry_zone_id='watch-entry',
                trigger_summary='The tavern staff and nearby patrons call for the Watch.',
                participant_specs=specs,
                public_visible=True,
                cancellable=True,
            ),
        )
    def _load_npc_hints(self) -> dict[str, SceneNpcCombatHint]:
        hints = _lmop_npc_hints()
        if self.campaign_id != 'lmop' or self.campaign_root is None:
            return hints
        profiles_path = self.campaign_root / 'npcs' / 'combat-profiles.json'
        if not profiles_path.exists():
            return hints
        payload = json.loads(profiles_path.read_text(encoding='utf-8'))
        for profile in payload.get('profiles', ()):
            npc_id = profile.get('npc_id')
            if not isinstance(npc_id, str) or not npc_id:
                continue
            existing = hints.get(npc_id)
            try:
                fallback = FallbackNpcCombatArchetype(profile.get('preferred_archetype', existing.fallback_archetype.value if existing else FallbackNpcCombatArchetype.COMMONER_NONCOMBATANT.value))
            except ValueError:
                fallback = existing.fallback_archetype if existing is not None else FallbackNpcCombatArchetype.COMMONER_NONCOMBATANT
            try:
                goal = CombatParticipantGoal(profile.get('default_goal', existing.goal.value if existing else CombatParticipantGoal.ATTACK.value))
            except ValueError:
                goal = existing.goal if existing is not None else CombatParticipantGoal.ATTACK
            faction_tags = tuple(profile.get('faction_tags', existing.faction_tags if existing is not None else ()))
            authority_tags = tuple(dict.fromkeys((existing.authority_tags if existing is not None else ()) + tuple(tag for tag in faction_tags if tag in {'authority', 'watch', 'guard', 'temple'})))
            hints[npc_id] = SceneNpcCombatHint(
                npc_id=npc_id,
                display_name=profile.get('display_name', existing.display_name if existing is not None else npc_id.replace('-', ' ').title()),
                preferred_monster_names=(existing.preferred_monster_names if existing is not None else ()),
                fallback_archetype=fallback,
                goal=goal,
                protects_npc_ids=tuple(profile.get('protector_npc_ids', existing.protects_npc_ids if existing is not None else ())),
                faction_tags=faction_tags,
                authority_tags=authority_tags,
                preferred_monster_ids=((profile.get('monster_record_id'),) if profile.get('monster_record_id') else (existing.preferred_monster_ids if existing is not None else ())),
                current_stance=profile.get('current_stance_hint', existing.current_stance if existing is not None else None),
                calls_watch=(existing.calls_watch if existing is not None else False) or npc_id in {'gundren-rockseeker', 'sildar-hallwinter'} or 'watch' in faction_tags or 'authority' in faction_tags,
            )
        return hints


def _tile(position: GridPosition, *, terrain_id: str = 'floor', traversable: bool = True, occupiable: bool = True, cover: CoverLevel = CoverLevel.NONE, tags: tuple[str, ...] = ()) -> BattlefieldTile:
    return BattlefieldTile(
        position=position,
        terrain_id=terrain_id,
        elevation_ft=0,
        ceiling_ft=15,
        traversable=traversable,
        occupiable=occupiable,
        movement_cost_feet_per_5ft=5,
        difficult_terrain=False,
        lightly_obscured=False,
        base_cover=cover,
        object_ids=(),
        blocker_ids=(),
        supported_modes=(TraversalMode.WALK, TraversalMode.CLIMB, TraversalMode.FLY, TraversalMode.TELEPORT),
        tags=tags,
    )


def _build_base_battlefield(*, map_id: str, name: str, width: int, height: int) -> BattlefieldState:
    grid = BattlefieldGridSpec(cell_size_feet=5, width=width, height=height, origin='top-left', coordinates='xy', min_x=0, min_y=0, max_x=width - 1, max_y=height - 1)
    tiles = {GridPosition(x, y): _tile(GridPosition(x, y)) for y in range(height) for x in range(width)}
    return BattlefieldState(map_id=map_id, name=name, grid=grid, tiles=tiles, base_tiles=dict(tiles), default_airspace_top_ft=20)


def _apply_feature(battlefield: BattlefieldState, feature: BattlefieldFeature, *, object_id: bool = True, blocker: bool = True) -> None:
    battlefield.features[feature.feature_id] = feature
    if object_id and feature.feature_id not in battlefield.object_ids:
        battlefield.object_ids = tuple(battlefield.object_ids) + (feature.feature_id,)
    if blocker and feature.feature_id not in battlefield.blocker_ids:
        battlefield.blocker_ids = tuple(battlefield.blocker_ids) + (feature.feature_id,)
    cover_rank = {CoverLevel.NONE: 0, CoverLevel.HALF: 1, CoverLevel.THREE_QUARTERS: 2, CoverLevel.TOTAL: 3}
    for cell in feature.cells:
        key = GridPosition(cell.x, cell.y)
        tile = battlefield.tiles[key]
        object_ids = tuple(dict.fromkeys(tile.object_ids + ((feature.feature_id,) if object_id else ())))
        blocker_ids = tuple(dict.fromkeys(tile.blocker_ids + ((feature.feature_id,) if blocker else ())))
        battlefield.tiles[key] = replace(tile, traversable=feature.traversable, occupiable=feature.occupiable, base_cover=(feature.cover_provided if cover_rank[feature.cover_provided] > cover_rank[tile.base_cover] else tile.base_cover), object_ids=object_ids, blocker_ids=blocker_ids, tags=tuple(dict.fromkeys(tile.tags + feature.tags)))


def _build_tavern_scene() -> AdHocEncounterScenePlan:
    battlefield = _build_base_battlefield(map_id='fallback-tavern-common-room-v1', name='Fallback Tavern Common Room', width=16, height=12)
    battlefield.spawn_zones = {
        'players': (GridPosition(3, 9), GridPosition(4, 9), GridPosition(5, 9), GridPosition(6, 9)),
        'hosts': (GridPosition(10, 4), GridPosition(11, 4), GridPosition(10, 5), GridPosition(11, 5)),
        'bystanders': (GridPosition(13, 8), GridPosition(13, 9), GridPosition(14, 8), GridPosition(14, 9)),
        'watch-entry': (GridPosition(0, 5), GridPosition(0, 6)),
    }
    counter_cells = tuple(GridPosition(x, 1) for x in range(9, 15)) + tuple(GridPosition(x, 2) for x in range(9, 15))
    _apply_feature(battlefield, BattlefieldFeature(feature_id='bar-counter', feature_type='counter', cells=counter_cells, elevation_ft=0, traversable=False, occupiable=False, cover_provided=CoverLevel.HALF, bottom_ft=0, top_ft=5, tags=('tavern', 'counter', 'cover')))
    for index, cells in enumerate(((GridPosition(5, 5), GridPosition(5, 6)), (GridPosition(8, 6), GridPosition(8, 7)), (GridPosition(11, 7), GridPosition(11, 8)))):
        _apply_feature(battlefield, BattlefieldFeature(feature_id=f'table-{index + 1}', feature_type='table', cells=cells, elevation_ft=0, traversable=False, occupiable=False, cover_provided=CoverLevel.HALF, bottom_ft=0, top_ft=4, tags=('table', 'cover')))
    _apply_feature(battlefield, BattlefieldFeature(feature_id='main-door', feature_type='door', cells=(GridPosition(0, 5), GridPosition(0, 6)), elevation_ft=0, traversable=True, occupiable=True, cover_provided=CoverLevel.NONE, bottom_ft=0, top_ft=8, tags=('door', 'exit', 'entry')), object_id=False, blocker=False)
    _apply_feature(battlefield, BattlefieldFeature(feature_id='rear-window', feature_type='window', cells=(GridPosition(15, 2), GridPosition(15, 3)), elevation_ft=0, traversable=False, occupiable=False, cover_provided=CoverLevel.HALF, bottom_ft=3, top_ft=8, tags=('window', 'exit')), object_id=False, blocker=False)
    return AdHocEncounterScenePlan(
        map_id=battlefield.map_id,
        name=battlefield.name,
        scene_kind=AdHocEncounterSceneKind.FALLBACK_TAVERN_COMMON_ROOM,
        battlefield=battlefield,
        fallback_used=True,
        summary='Fallback tavern/common-room battlefield synthesized from story-scene context.',
        primary_hostile_zone_ids=('hosts',),
        reinforcement_entry_zone_ids=('watch-entry',),
        bystander_zone_ids=('bystanders',),
    )


def _build_open_scene(*, scene_id: str) -> AdHocEncounterScenePlan:
    battlefield = _build_base_battlefield(map_id=f'fallback-{scene_id}-open-v1', name='Fallback Open Confrontation', width=14, height=10)
    battlefield.spawn_zones = {
        'players': (GridPosition(2, 2), GridPosition(2, 4), GridPosition(2, 6), GridPosition(2, 8)),
        'hosts': (GridPosition(11, 2), GridPosition(11, 4), GridPosition(11, 6), GridPosition(11, 8)),
        'watch-entry': (GridPosition(13, 4), GridPosition(13, 5)),
    }
    _apply_feature(battlefield, BattlefieldFeature(feature_id='north-exit', feature_type='exit', cells=(GridPosition(6, 0), GridPosition(7, 0)), elevation_ft=0, traversable=True, occupiable=True, cover_provided=CoverLevel.NONE, bottom_ft=0, top_ft=12, tags=('exit',)), object_id=False, blocker=False)
    _apply_feature(battlefield, BattlefieldFeature(feature_id='south-exit', feature_type='exit', cells=(GridPosition(6, 9), GridPosition(7, 9)), elevation_ft=0, traversable=True, occupiable=True, cover_provided=CoverLevel.NONE, bottom_ft=0, top_ft=12, tags=('exit',)), object_id=False, blocker=False)
    return AdHocEncounterScenePlan(
        map_id=battlefield.map_id,
        name=battlefield.name,
        scene_kind=AdHocEncounterSceneKind.FALLBACK_OPEN_AREA,
        battlefield=battlefield,
        fallback_used=True,
        summary='Fallback open-area battlefield synthesized because no authored tactical map exists.',
        primary_hostile_zone_ids=('hosts',),
        reinforcement_entry_zone_ids=('watch-entry',),
        bystander_zone_ids=(),
    )


def _lmop_npc_hints() -> dict[str, SceneNpcCombatHint]:
    return {
        'gundren-rockseeker': SceneNpcCombatHint(
            npc_id='gundren-rockseeker',
            display_name='Gundren Rockseeker',
            preferred_monster_names=('Noble',),
            preferred_monster_ids=('noble-xmm',),
            fallback_archetype=FallbackNpcCombatArchetype.NOBLE_MERCHANT_CIVILIAN,
            goal=CombatParticipantGoal.FLEE,
            faction_tags=('rockseeker', 'civilian', 'employer'),
            current_stance='Protective of the contract and quick to get clear of real violence.',
            calls_watch=True,
        ),
        'sildar-hallwinter': SceneNpcCombatHint(
            npc_id='sildar-hallwinter',
            display_name='Sildar Hallwinter',
            preferred_monster_names=('Veteran', 'Guard'),
            preferred_monster_ids=('veteran',),
            fallback_archetype=FallbackNpcCombatArchetype.VETERAN_BODYGUARD,
            goal=CombatParticipantGoal.PROTECT,
            protects_npc_ids=('gundren-rockseeker',),
            faction_tags=('lords-alliance', 'authority', 'escort'),
            authority_tags=('watch', 'authority'),
            current_stance='Interposes himself to protect Gundren and regain control of the room.',
            calls_watch=True,
        ),
        'waterdeep-watch': SceneNpcCombatHint(
            npc_id='waterdeep-watch',
            display_name='Waterdeep Watch',
            preferred_monster_names=('Guard',),
            preferred_monster_ids=('guard-xmm',),
            fallback_archetype=FallbackNpcCombatArchetype.GUARD_WATCHMAN,
            goal=CombatParticipantGoal.ARREST,
            faction_tags=('watch', 'authority', 'reinforcement'),
            authority_tags=('watch', 'authority'),
            current_stance='Move to arrest or contain the violence, not to kill unless forced.',
            calls_watch=False,
        ),
    }
