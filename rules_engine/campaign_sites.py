"""Transactional, deterministic site progression. Campaign specifics are data only."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from math import isfinite

from shared_types.battlefield import (
    BattlefieldState,
    BattlefieldEdge,
    EdgeTransitionType,
    EdgeTraversalRequirement,
    CoverLevel,
    FallReason,
    MovementIntentMode,
    edge_key,
)
from shared_types.campaign_site import (
    CampaignSiteDefinition,
    CampaignSiteIntent,
    CampaignSiteProgress,
    CampaignSiteState,
    CampaignSiteProgressedEvent,
    CampaignSiteResolution,
    SiteAction,
    SiteCheckResolvedEvent,
    SiteSceneActivatedEvent,
    SiteDoorChangedEvent,
    SiteCombatEndedEvent,
    SiteHazardTriggeredEvent,
    SiteEdgeCaughtEvent,
    SiteActorWeightSetEvent,
    SiteMovementWatch,
    SiteMovementWatchSetEvent,
)
from shared_types.conditions import ConditionInstance, ConditionType
from shared_types.effects import SaveRequest, ResolutionContext
from encounter_runtime.conditions import get_effective_speed
from encounter_runtime.equipment import supported_actor_weight_lb
from monster_runtime.compiler import configure_prepared_monster_spells
from shared_types.encounter_events import ConditionAddedEvent, TimeAdvancedEvent
from shared_types.encounter_intents import ExploreMoveIntent, MoveActorIntent, StartEncounterIntent
from shared_types.encounter_models import EncounterState, EncounterPhase, GridPosition
from shared_types.errors import EncounterValidationError, EncounterClarificationRequiredError
from shared_types.models import Ability
from shared_types.rest import RestActivityType
from shared_types.equipment import ObjectInteractionCostMode, ObjectInteractionKind

from .battlefield_loader import load_battlefield_state_from_json


_SCENE_FIELDS = (
    'battlefield',
    'environment_objects',
    'ground_items',
    'persistent_effects',
    'summoned_creatures',
    'created_objects',
    'illusions',
    'informational_payloads',
    'persistent_areas',
)


class CampaignSiteEngine:
    def __init__(self, definition: CampaignSiteDefinition, *, kernel, asset_root: Path):
        self.definition = definition
        self.kernel = kernel
        self.asset_root = asset_root.resolve()

    def initial_state(self) -> CampaignSiteState:
        return CampaignSiteState(CampaignSiteProgress(site_id=self.definition.site_id))

    def resolve(
        self,
        state: EncounterState,
        site: CampaignSiteState,
        intent: CampaignSiteIntent,
        *,
        party_actor_ids: tuple[str, ...],
        current_location_id: str,
    ) -> CampaignSiteResolution:
        """Resolve on copies. Callers commit both returned stores only on success."""
        self._require_party_actor(state, intent.actor_id, party_actor_ids)
        working, progress = deepcopy(state), deepcopy(site)
        start = len(working.event_log)
        self._resolve(working, progress, intent, party_actor_ids, current_location_id)
        return self._result(working, progress, start)

    def move(
        self,
        state: EncounterState,
        site: CampaignSiteState,
        intent: ExploreMoveIntent | MoveActorIntent,
        *,
        party_actor_ids: tuple[str, ...],
    ) -> CampaignSiteResolution:
        if isinstance(intent, ExploreMoveIntent):
            self._require_party_actor(state, intent.actor_id, party_actor_ids)
        if not site.progress.in_dungeon:
            raise EncounterValidationError('A tactical exploration move requires an active dungeon.')
        working, progress = deepcopy(state), deepcopy(site)
        start = len(working.event_log)
        actor = working.actors[intent.actor_id]
        preview_actor = (
            replace(
                actor, movement_spent_ft=0, dash_bonus_ft=0, remaining_movement_ft=get_effective_speed(actor)
            )
            if isinstance(intent, ExploreMoveIntent)
            else actor
        )
        destination = self.kernel.battlefield_rules.resolve_ground_destination(
            working,
            preview_actor,
            intent.x,
            intent.y,
            intent.z,
            movement_intent_mode=intent.movement_intent_mode,
        )
        preview = self.kernel.battlefield_rules.preview_move(
            working, preview_actor, destination, movement_intent_mode=intent.movement_intent_mode
        )
        triggered = None
        edge_position = actor.position
        if preview.plan is not None:
            for position in preview.plan.path:
                if position == actor.position:
                    continue
                for hazard in self.definition.hazards.values():
                    if (
                        hazard.hazard_id in progress.progress.triggered_hazards
                        or position.horizontal() not in hazard.cells
                        or position.z < 0
                        or intent.movement_intent_mode == MovementIntentMode.ALLOW_FLY
                    ):
                        continue
                    if hazard.weight_threshold_lb and actor.body_weight_lb <= 0:
                        raise EncounterClarificationRequiredError(
                            'This route depends on body weight. Record it with /site weight <lb> before proceeding.'
                        )
                    load = supported_actor_weight_lb(working, actor.actor_id, self.kernel.item_catalog)
                    if load > hazard.weight_threshold_lb or (
                        hazard.weight_threshold_inclusive and load == hazard.weight_threshold_lb
                    ):
                        triggered = hazard
                        break
                room_trigger = intent.actor_id in party_actor_ids and any(
                    e.automatic
                    and e.encounter_id not in progress.progress.resolved_encounters
                    and not (e.bypass_flag and e.bypass_flag in progress.progress.flags)
                    and position.horizontal() in e.trigger_cells
                    for e in self.definition.encounters.values()
                )
                if triggered is not None or (room_trigger and working.phase == EncounterPhase.READY):
                    intent = replace(intent, x=position.x, y=position.y, z=position.z)
                    break
                edge_position = position
        self._emit(
            working,
            progress,
            SiteMovementWatchSetEvent(
                SiteMovementWatch(
                    intent.actor_id,
                    GridPosition(intent.x, intent.y, destination.z if intent.z is None else intent.z),
                    edge_position,
                    None if triggered is None else triggered.hazard_id,
                )
            ),
        )
        self.kernel.dispatch(working, intent)
        self._finish_movement(working, progress, party_actor_ids)
        return self._result(working, progress, start)

    def resume_movement(
        self, state: EncounterState, site: CampaignSiteState, *, party_actor_ids: tuple[str, ...]
    ) -> CampaignSiteResolution:
        working, progress = deepcopy(state), deepcopy(site)
        start = len(working.event_log)
        self._finish_movement(working, progress, party_actor_ids)
        return self._result(working, progress, start)

    def _finish_movement(self, state, site, party):
        watch = site.pending_movement
        if (
            watch is None
            or state.pending_reaction_window is not None
            or state.pending_timing_queue is not None
        ):
            return
        self._emit(state, site, SiteMovementWatchSetEvent(None))
        actor = state.actors[watch.actor_id]
        if actor.position != watch.destination:
            return  # An interruption stopped the declared movement before the watched cell.
        if watch.hazard_id is not None:
            self._trigger_hazard(
                state, site, self.definition.hazards[watch.hazard_id], watch.actor_id, watch.edge_position
            )
        if watch.actor_id in party and actor.current_hit_points > 0 and state.pending_reaction_window is None:
            self._observe(state, site, watch.actor_id, party)

    def _trigger_hazard(self, state, site, hazard, actor_id, edge_position):
        self._emit(state, site, SiteHazardTriggeredEvent(hazard.hazard_id))
        caught = False
        if hazard.save_dc is not None:
            result, events = self.kernel.resolve_save_consumer(
                state,
                SaveRequest(
                    context=ResolutionContext(hazard.hazard_id, None, actor_id, 'Catch the pit edge'),
                    ability=Ability.DEX,
                    dc=hazard.save_dc,
                ),
                apply=False,
            )
            for event in events:
                self._emit(state, site, event)
            caught = result.result.total >= hazard.save_dc
        if caught:
            self._emit(state, site, SiteEdgeCaughtEvent(actor_id, edge_position))
        else:
            for event in self.kernel._support_reconciliation_events(
                state, actor_id=actor_id, reason=FallReason.STATE_CHANGE
            ):
                self._emit(state, site, event)
        self._progress(
            state,
            site,
            CampaignSiteIntent(actor_id, SiteAction.OBSERVE),
            f'{hazard.label} gives way. '
            + ('You catch the edge.' if caught else 'The rules engine resolves the fall.'),
            triggered_hazards=site.progress.triggered_hazards | {hazard.hazard_id},
            detected_hazards=site.progress.detected_hazards | {hazard.hazard_id},
        )

    def _result(self, state, site, start):
        events = tuple(state.event_log[start:])
        return CampaignSiteResolution(
            state,
            site,
            events,
            tuple(
                event.public_text
                for event in events
                if isinstance(event, CampaignSiteProgressedEvent) and event.public_text
            ),
        )

    def _require_party_actor(self, state, actor_id, party_actor_ids):
        if actor_id not in party_actor_ids or actor_id not in state.actors:
            raise EncounterValidationError('A site action requires a controlled party actor.')
        self.kernel._require_conscious(state.actors[actor_id])
        if state.pending_reaction_window is not None or state.pending_timing_queue is not None:
            raise EncounterValidationError('Resolve the pending reaction or timing choice first.')

    def _resolve(self, state, site, intent, party, current_location_id):
        action, target = intent.action, intent.target_id
        p = site.progress
        if action == SiteAction.SET_WEIGHT:
            self._require_peace(state)
            if intent.weight_lb is None or not isfinite(intent.weight_lb) or intent.weight_lb <= 0:
                raise EncounterClarificationRequiredError(
                    'Supply a positive body weight in pounds: /site weight <lb>.'
                )
            if state.actors[intent.actor_id].body_weight_lb > 0:
                raise EncounterValidationError('Body weight has already been recorded for this character.')
            self._emit(state, site, SiteActorWeightSetEvent(intent.actor_id, intent.weight_lb))
            self._progress(
                state,
                site,
                intent,
                f'Body weight recorded: {intent.weight_lb:g} lb; equipment is counted separately.',
            )
            return
        if action == SiteAction.ARRIVE:
            if p.in_dungeon:
                raise EncounterValidationError('Leave the dungeon before regional arrival.')
            if current_location_id != self.definition.town_location_id:
                raise EncounterValidationError(
                    'Site arrival requires authoritative regional arrival at the town.'
                )
            self._require_peace(state)
            town = (
                site.scenes[self.definition.town_location_id]
                if p.arrived
                else EncounterState(
                    battlefield=BattlefieldState(map_id=self.definition.town_location_id, name='Town')
                )
            )
            self._activate_scene(
                state,
                site,
                self.definition.town_location_id,
                town,
                party,
                tuple(state.actors[a].position for a in party),
            )
            self._progress(state, site, intent, self.definition.arrival_text, arrived=True)
            return
        if not p.arrived:
            raise EncounterValidationError('The party has not arrived at this site.')
        if not p.in_dungeon and current_location_id != self.definition.town_location_id:
            raise EncounterValidationError('Return to the town before using its site actions.')
        if action == SiteAction.VISIT:
            self._require_town(state, site)
            place = self.definition.places.get(target)
            if place is None:
                raise EncounterValidationError('Unknown town destination; choose a projected location id.')
            self._emit(state, site, TimeAdvancedEvent(60, RestActivityType.EXERTION))
            self._progress(state, site, intent, f'{place.name}: {place.description}', place_id=place.place_id)
            return
        if action == SiteAction.TALK:
            self._require_town(state, site)
            place = self.definition.places.get(p.place_id)
            conversation = (
                None if place is None else next((c for c in place.conversations if c.npc_id == target), None)
            )
            if conversation is None:
                raise EncounterValidationError('Visit the speaker’s location before this conversation.')
            self._progress(
                state, site, intent, conversation.text, flags=p.flags | frozenset(conversation.grants)
            )
            return
        if action == SiteAction.ENTER:
            self._require_town(state, site)
            entrance = self.definition.entrances.get(target)
            if entrance is None or (entrance.required_flag and entrance.required_flag not in p.flags):
                raise EncounterValidationError('That entrance has not been discovered.')
            if p.place_id != entrance.place_id:
                raise EncounterValidationError('Visit the entrance’s town location first.')
            if len(party) > len(entrance.positions):
                raise EncounterValidationError('The authored entrance has too few distinct party positions.')
            scene = site.scenes.get(self.definition.dungeon_location_id)
            if scene is None:
                scene = self._new_dungeon()
            self._activate_scene(
                state,
                site,
                self.definition.dungeon_location_id,
                scene,
                party,
                entrance.positions[: len(party)],
            )
            self._progress(
                state, site, intent, f'You enter through the {entrance.label.lower()}.', in_dungeon=True
            )
            self._observe(state, site, intent.actor_id, party)
            return
        if not p.in_dungeon:
            raise EncounterValidationError('This action requires entering the dungeon.')
        if action == SiteAction.LEAVE:
            self._require_peace(state)
            entrances = [
                entry
                for entry in self.definition.entrances.values()
                if self._near(state.actors[intent.actor_id].position, entry.positions, 5)
            ]
            if not entrances:
                raise EncounterValidationError('Reach an entrance before leaving the dungeon.')
            entrance = entrances[0]
            if any(not self._near(state.actors[a].position, entrance.positions, 15) for a in party):
                raise EncounterValidationError('Gather the party at the same entrance before leaving.')
            town = site.scenes[self.definition.town_location_id]
            self._activate_scene(
                state,
                site,
                self.definition.town_location_id,
                town,
                party,
                tuple(GridPosition(i, 0) for i in range(len(party))),
            )
            flags = p.flags | {
                granted for required, granted in self.definition.return_grants if required in p.flags
            }
            self._progress(
                state,
                site,
                intent,
                f'You return to {self.definition.places[entrance.place_id].name}.',
                in_dungeon=False,
                place_id=entrance.place_id,
                flags=frozenset(flags),
            )
            return
        if action in {SiteAction.OPEN, SiteAction.CLOSE, SiteAction.PICK_LOCK, SiteAction.FORCE}:
            self._door_action(state, site, intent)
            return
        if action == SiteAction.SEARCH:
            self._require_peace(state)
            if target != 'here':
                raise EncounterValidationError('Search requires the explicit target “here”.')
            actor = state.actors[intent.actor_id]
            found = set(p.discovered_doors)
            labels = []
            for door in self.definition.doors.values():
                if door.secret and door.door_id not in found and self._near(actor.position, door.cells, 5):
                    if self._check(
                        state, site, intent.actor_id, door.door_id, 'WIS', 'Perception', door.search_dc
                    ):
                        found.add(door.door_id)
                        labels.append(door.label)
            detected = set(p.detected_hazards)
            for hazard in self.definition.hazards.values():
                if hazard.hazard_id not in detected and self._near(actor.position, hazard.cells, 5):
                    if self._check(
                        state,
                        site,
                        intent.actor_id,
                        hazard.hazard_id,
                        hazard.detection_ability,
                        hazard.detection_skill,
                        hazard.detection_dc,
                    ):
                        detected.add(hazard.hazard_id)
                        labels.append(hazard.label)
            self._emit(state, site, TimeAdvancedEvent(60, RestActivityType.LIGHT_ACTIVITY))
            text = (
                'You discover: ' + ', '.join(labels) + '.'
                if labels
                else 'You find no additional concealed features nearby.'
            )
            self._progress(
                state,
                site,
                intent,
                text,
                discovered_doors=frozenset(found),
                detected_hazards=frozenset(detected),
            )
            return
        if action == SiteAction.INTERACT:
            self._interact(state, site, intent)
            return
        if action == SiteAction.ENGAGE:
            self._require_peace(state)
            encounter = self.definition.encounters.get(target)
            if encounter is None or target in p.resolved_encounters:
                raise EncounterValidationError('No unresolved local encounter matches that choice.')
            if self.room_for(state.actors[intent.actor_id].position) != encounter.room_id:
                raise EncounterValidationError('Approach the encounter before engaging it.')
            self._start_combat(state, site, intent.actor_id, encounter, party)
            return
        if action == SiteAction.RESOLVE_COMBAT:
            if p.active_encounter_id is None:
                raise EncounterValidationError('No site encounter is active.')
            encounter = self.definition.encounters[p.active_encounter_id]
            if any(state.actors[m.actor_id].current_hit_points > 0 for m in encounter.monsters):
                raise EncounterValidationError('Living hostiles remain in this encounter.')
            self._emit(state, site, SiteCombatEndedEvent(encounter.encounter_id))
            self._progress(
                state,
                site,
                intent,
                f'{encounter.label}: the encounter is resolved.',
                active_encounter_id=None,
                resolved_encounters=p.resolved_encounters | {encounter.encounter_id},
                flags=p.flags | frozenset(encounter.resolved_grants),
            )
            return
        if action == SiteAction.OBSERVE:
            self._observe(state, site, intent.actor_id, party)
            return
        raise EncounterValidationError('Unknown site action.')

    def _door_action(self, state, site, intent):
        p, actor = site.progress, state.actors[intent.actor_id]
        door = self.definition.doors.get(intent.target_id)
        if door is None or (door.secret and door.door_id not in p.discovered_doors):
            raise EncounterValidationError('No discovered door matches that choice.')
        if not self._near(actor.position, door.cells, 5):
            raise EncounterValidationError('Approach the door before interacting with it.')
        if not any(
            self.kernel.battlefield_rules.has_line_of_effect_to_position(state, actor, cell)
            for cell in door.cells
        ):
            raise EncounterValidationError('A wall blocks access to that door.')
        locked = (
            door.locked
            and door.door_id not in p.unlocked_doors
            and (door.key_flag is None or door.key_flag not in p.flags)
        )
        if intent.action == SiteAction.OPEN and locked:
            raise EncounterValidationError('The door is locked; use a key, thieves’ tools, or force.')
        if intent.action == SiteAction.PICK_LOCK:
            tools = [
                self.kernel.item_catalog[item]
                for item, count in actor.carried_item_counts.items()
                if count > 0 and item in self.kernel.item_catalog
            ]
            if not any(item.name.casefold() == "thieves' tools" for item in tools):
                raise EncounterValidationError('Picking this lock requires carried thieves’ tools.')
        cost_mode = (
            ObjectInteractionCostMode.UTILIZE
            if intent.action in {SiteAction.PICK_LOCK, SiteAction.FORCE}
            else intent.cost_mode
        )
        self._spend_interaction(state, site, actor.actor_id, cost_mode)
        if intent.action in {SiteAction.PICK_LOCK, SiteAction.FORCE}:
            ability = 'DEX' if intent.action == SiteAction.PICK_LOCK else 'STR'
            dc = door.lock_dc if intent.action == SiteAction.PICK_LOCK else door.force_dc
            if not self._check(state, site, actor.actor_id, door.door_id, ability, None, dc):
                self._progress(state, site, intent, f'{door.label}: the attempt fails.')
                return
            p = replace(p, unlocked_doors=p.unlocked_doors | {door.door_id})
        opened = intent.action != SiteAction.CLOSE
        self._emit(state, site, SiteDoorChangedEvent(door.door_id, opened))
        self._progress(
            state,
            site,
            intent,
            f'{door.label} is now {"open" if opened else "closed"}.',
            unlocked_doors=p.unlocked_doors,
            opened_doors=(p.opened_doors | {door.door_id} if opened else p.opened_doors - {door.door_id}),
        )

    def _interact(self, state, site, intent):
        self._require_peace(state)
        p = site.progress
        item = self.definition.interactions.get(intent.target_id)
        if item is None or self.room_for(state.actors[intent.actor_id].position) != item.room_id:
            raise EncounterValidationError('No local interaction matches that choice.')
        if item.interaction_id in p.completed_interactions:
            raise EncounterValidationError('This interaction is already completed.')
        if not set(item.requires) <= p.flags:
            raise EncounterValidationError('Resolve the local guards or prerequisite discovery first.')
        if not set(item.required_open_doors) <= p.opened_doors:
            raise EncounterValidationError('Open the required doors before completing this interaction.')
        if item.required_living_encounter is not None:
            encounter = self.definition.encounters[item.required_living_encounter]
            if not any(state.actors[m.actor_id].current_hit_points > 0 for m in encounter.monsters):
                raise EncounterValidationError('The creature is no longer available for negotiation.')
        self._emit(state, site, TimeAdvancedEvent(60, RestActivityType.LIGHT_ACTIVITY))
        if item.dc is not None and not self._check(
            state, site, intent.actor_id, item.interaction_id, item.ability, item.skill, item.dc
        ):
            self._progress(state, site, intent, f'{item.label}: the check fails.')
            return
        flags = p.flags | frozenset(item.grants)
        discovered = p.discovered_doors | frozenset(item.reveals_doors)
        self._progress(
            state,
            site,
            intent,
            item.text,
            flags=flags,
            discovered_doors=discovered,
            completed_interactions=p.completed_interactions | {item.interaction_id},
        )

    def _observe(self, state, site, actor_id, party):
        room_id = self.room_for(state.actors[actor_id].position)
        if room_id is not None and room_id not in site.progress.visited_rooms:
            room = self.definition.rooms[room_id]
            self._progress(
                state,
                site,
                CampaignSiteIntent(actor_id, SiteAction.OBSERVE),
                room.description,
                visited_rooms=site.progress.visited_rooms | {room_id},
            )
        if state.phase != EncounterPhase.READY or site.progress.active_encounter_id is not None:
            return
        position = state.actors[actor_id].position.horizontal()
        for encounter in self.definition.encounters.values():
            if not encounter.automatic or encounter.encounter_id in site.progress.resolved_encounters:
                continue
            if encounter.bypass_flag and encounter.bypass_flag in site.progress.flags:
                continue
            if position in encounter.trigger_cells and any(
                state.actors[m.actor_id].current_hit_points > 0 for m in encounter.monsters
            ):
                self._start_combat(state, site, actor_id, encounter, party)
                return

    def _start_combat(self, state, site, actor_id, encounter, party):
        enemies = tuple(
            m.actor_id for m in encounter.monsters if state.actors[m.actor_id].current_hit_points > 0
        )
        self.kernel.dispatch(state, StartEncounterIntent(participant_actor_ids=tuple(party) + enemies))
        self._progress(
            state,
            site,
            CampaignSiteIntent(actor_id, SiteAction.ENGAGE, encounter.encounter_id),
            'Hostile activity triggers initiative. Resolve actions through the combat rules.',
            active_encounter_id=encounter.encounter_id,
        )

    def _check(self, state, site, actor_id, target, ability, skill, dc):
        resolution = self.kernel.resolve_ability_check(
            state, actor_id=actor_id, ability=Ability(ability), dc=dc, skill_name=skill
        )
        result = resolution.result
        self._emit(
            state,
            site,
            SiteCheckResolvedEvent(
                actor_id,
                target,
                ability,
                skill,
                dc,
                result.selected_roll,
                result.total,
                result.total >= dc,
                resolution.random_counter_used,
            ),
        )
        return result.total >= dc

    def _spend_interaction(self, state, site, actor_id, cost_mode):
        if state.phase == EncounterPhase.IN_PROGRESS:
            actor = self.kernel._resolve_interaction_actor(
                state, actor_id=actor_id, cost_mode=cost_mode, allow_attack_timing=False
            )
            for event in self.kernel._interaction_cost_events(
                state,
                actor=actor,
                interaction_kind=ObjectInteractionKind.USE_ENVIRONMENT_OBJECT,
                cost_mode=cost_mode,
            ):
                self._emit(state, site, event)
        else:
            self._emit(state, site, TimeAdvancedEvent(6, RestActivityType.LIGHT_ACTIVITY))

    def room_for(self, position):
        return next(
            (r.room_id for r in self.definition.rooms.values() if position.horizontal() in r.cells), None
        )

    def _near(self, position, cells, radius):
        return any(self.kernel.battlefield_rules.get_distance3d(position, cell) <= radius for cell in cells)

    def _require_peace(self, state):
        if state.phase == EncounterPhase.IN_PROGRESS:
            raise EncounterValidationError('Finish the current combat before this site action.')

    def _require_town(self, state, site):
        self._require_peace(state)
        if site.progress.in_dungeon:
            raise EncounterValidationError('Leave the dungeon before visiting the town.')

    def _new_dungeon(self):
        path = (self.asset_root / self.definition.battlefield_path).resolve()
        if not path.is_relative_to(self.asset_root):
            raise EncounterValidationError('Site map path is outside the asset root.')
        scene = EncounterState(battlefield=load_battlefield_state_from_json(path))
        for encounter in self.definition.encounters.values():
            for spec in encounter.monsters:
                actor = self.kernel.monster_runtime.compile_monster(
                    monster_id=spec.monster_id, actor_id=spec.actor_id, position=spec.position
                )
                if spec.prepared_spell_ids:
                    configure_prepared_monster_spells(
                        actor,
                        spell_ids=spec.prepared_spell_ids,
                        slot_counts=spec.spell_slot_counts,
                        encounter_catalog=self.kernel.monster_runtime.monster_catalog,
                    )
                if not (actor.attacks or actor.spells or actor.capabilities):
                    raise EncounterValidationError(f'Site actor {spec.actor_id} has no executable actions.')
                actor.name = spec.name
                scene.actors[spec.actor_id] = actor
                for condition in spec.conditions:
                    self.kernel._apply_event(
                        scene,
                        ConditionAddedEvent(
                            actor_id=spec.actor_id,
                            instance=ConditionInstance(
                                instance_id=f'site:{spec.actor_id}:{condition}',
                                condition_type=ConditionType(condition),
                                source_label=self.definition.site_id,
                            ),
                        ),
                    )
        scene.event_log = []
        return scene

    def _activate_scene(self, state, site, scene_id, scene, party, positions):
        if state.ritual_casts:
            raise EncounterValidationError('Finish the active ritual before changing maps.')
        party_ids = set(party)
        for effect in state.active_effects.values():
            source_travels = effect.source_actor_id in party_ids
            targets_travel = bool(set(effect.target_actor_ids) & party_ids)
            if source_travels or targets_travel:
                if (
                    not source_travels
                    or not set(effect.target_actor_ids) <= party_ids
                    or effect.origin_point is not None
                    or any(
                        p.source_effect_id == effect.effect_instance_id
                        for p in state.persistent_effects.values()
                    )
                ):
                    raise EncounterValidationError(
                        'End scene-bound effects before changing maps; personal party effects remain active.'
                    )
        previous = (
            self.definition.dungeon_location_id
            if site.progress.in_dungeon
            else (
                self.definition.town_location_id
                if site.progress.arrived
                else state.battlefield.map_id or 'previous-scene'
            )
        )
        self._emit(
            state,
            site,
            SiteSceneActivatedEvent(previous, scene_id, deepcopy(scene), tuple(zip(party, positions))),
        )

    def _progress(self, state, site, intent, text, **changes):
        self._emit(state, site, CampaignSiteProgressedEvent(intent, replace(site.progress, **changes), text))

    def _emit(self, state, site, event):
        if isinstance(event, CampaignSiteProgressedEvent):
            state.event_log.append(event)
            site.progress = event.progress
        elif isinstance(event, SiteCheckResolvedEvent):
            state.event_log.append(event)
            state.random_counter = event.random_counter_used + 1
        elif isinstance(event, SiteDoorChangedEvent):
            state.event_log.append(event)
            cells = self.definition.doors[event.door_id].cells
            for a, b in zip(cells[::2], cells[1::2]):
                dz = (
                    state.battlefield.tiles[b.horizontal()].elevation_ft
                    - state.battlefield.tiles[a.horizontal()].elevation_ft
                )
                state.battlefield.edges[edge_key(a, b)] = BattlefieldEdge(
                    cells=(a, b),
                    transition_type=(
                        (EdgeTransitionType.SLOPE if dz else EdgeTransitionType.FLAT)
                        if event.opened
                        else EdgeTransitionType.BLOCKED
                    ),
                    traversal_requirement=(
                        EdgeTraversalRequirement.NONE if event.opened else EdgeTraversalRequirement.BLOCKED
                    ),
                    height_change_ft=dz,
                    extra_movement_cost_feet=0,
                    extra_movement_cost_with_climb_speed_feet=None,
                    blocks_los=not event.opened,
                    blocks_loe=not event.opened,
                    requires_vertical_confirmation=False,
                    cover_from_low_to_high=CoverLevel.NONE,
                    cover_from_high_to_low=CoverLevel.NONE,
                    blocks_diagonal_corner_cutting=True,
                )
        elif isinstance(event, SiteMovementWatchSetEvent):
            state.event_log.append(event)
            site.pending_movement = event.watch
        elif isinstance(event, SiteActorWeightSetEvent):
            state.event_log.append(event)
            state.actors[event.actor_id].body_weight_lb = event.weight_lb
        elif isinstance(event, SiteEdgeCaughtEvent):
            state.event_log.append(event)
            state.actors[event.actor_id].position = event.position
        elif isinstance(event, SiteHazardTriggeredEvent):
            state.event_log.append(event)
            hazard = self.definition.hazards[event.hazard_id]
            battlefield = state.battlefield
            if hazard.feature_id is not None:
                battlefield.features.pop(hazard.feature_id)
                battlefield.object_ids = tuple(
                    fid for fid in battlefield.object_ids if fid != hazard.feature_id
                )
            else:
                for cell in hazard.cells:
                    tile = battlefield.base_tiles[cell]
                    battlefield.base_tiles[cell] = replace(
                        tile,
                        elevation_ft=tile.elevation_ft - hazard.depth_ft,
                        difficult_terrain=True,
                        movement_cost_feet_per_5ft=10,
                    )
            for cell in hazard.cells:
                self.kernel._rebuild_battlefield_cell_from_features(battlefield, cell)
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    neighbor = GridPosition(cell.x + dx, cell.y + dy)
                    if neighbor not in battlefield.tiles or not battlefield.tiles[neighbor].traversable:
                        continue
                    key = edge_key(cell, neighbor)
                    old = battlefield.edges.get(key)
                    if old is not None and old.traversal_requirement == EdgeTraversalRequirement.BLOCKED:
                        continue
                    dz = battlefield.tiles[neighbor].elevation_ft - battlefield.tiles[cell].elevation_ft
                    battlefield.edges[key] = BattlefieldEdge(
                        cells=(cell, neighbor),
                        transition_type=EdgeTransitionType.CLIMBABLE_LEDGE if dz else EdgeTransitionType.FLAT,
                        traversal_requirement=(
                            EdgeTraversalRequirement.CLIMB if dz else EdgeTraversalRequirement.NONE
                        ),
                        height_change_ft=dz,
                        extra_movement_cost_feet=0,
                        extra_movement_cost_with_climb_speed_feet=None,
                        blocks_los=False,
                        blocks_loe=False,
                        requires_vertical_confirmation=bool(dz),
                        cover_from_low_to_high=CoverLevel.NONE,
                        cover_from_high_to_low=CoverLevel.NONE,
                    )
        elif isinstance(event, SiteCombatEndedEvent):
            state.event_log.append(event)
            state.phase = EncounterPhase.READY
            state.round_number = state.turn_index = 0
            state.active_actor_id = state.winning_side = None
            state.initiative_order = ()
        elif isinstance(event, SiteSceneActivatedEvent):
            state.event_log.append(event)
            party_ids = {actor_id for actor_id, _ in event.party_positions}
            previous = deepcopy(state)
            previous.event_log = []
            previous.actors = {k: v for k, v in previous.actors.items() if k not in party_ids}
            personal = {k: v for k, v in state.active_effects.items() if v.source_actor_id in party_ids}
            previous.active_effects = {k: v for k, v in previous.active_effects.items() if k not in personal}
            site.scenes[event.previous_scene_id] = previous
            retained = {k: v for k, v in state.actors.items() if k in party_ids}
            state.actors = {**retained, **deepcopy(event.scene.actors)}
            state.active_effects = {**personal, **deepcopy(event.scene.active_effects)}
            for key in _SCENE_FIELDS:
                setattr(state, key, deepcopy(getattr(event.scene, key)))
            for actor_id, position in event.party_positions:
                state.actors[actor_id].position = position
        else:
            self.kernel._apply_event(state, event)

    def replay(self, initial_state, initial_site, events):
        """Replay event data, consuming kernel-generated follow-ups exactly once."""
        state, site = deepcopy(initial_state), deepcopy(initial_site)
        events = tuple(events)
        index = 0
        while index < len(events):
            start = len(state.event_log)
            self._emit(state, site, deepcopy(events[index]))
            emitted = tuple(state.event_log[start:])
            if emitted != events[index : index + len(emitted)]:
                raise EncounterValidationError(
                    'Replay event sequence diverged from deterministic follow-up events.'
                )
            index += len(emitted)
        return self._result(state, site, 0)
