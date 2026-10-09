"""Controller/command and presentation adapter for a rules-owned campaign site."""

from __future__ import annotations

from dataclasses import replace
from encounter_runtime.conditions import has_condition
from shared_types.conditions import ConditionType
from shared_types.equipment import ObjectInteractionCostMode
import re

from shared_types.campaign_site import CampaignSiteIntent, SiteAction, SiteCheckResolvedEvent
from shared_types.encounter_intents import ExploreMoveIntent, MoveActorIntent
from shared_types.encounter_models import ActorSide, EncounterPhase
from shared_types.errors import (
    EncounterClarificationRequiredError,
    EncounterPermissionError,
    EncounterValidationError,
)
from shared_types.storytelling import RuntimeMode, StoryTranscriptEntry, StoryTranscriptVisibility
from shared_types.web_ui import WebCampaignSiteView, WebTownPlaceView, WebSiteActionView


class CampaignSiteSession:
    def __init__(self, session, engine):
        self.session = session
        self.engine = engine
        self.state = engine.initial_state()

    @property
    def active(self):
        return self.state.progress.arrived and self.session.story_state.canonical_location_id in {
            self.engine.definition.town_location_id,
            self.engine.definition.dungeon_location_id,
        }

    def arrive(self):
        party = self.session._player_actor_ids()
        actor_id = next((a for a in party if self.session.state.actors[a].current_hit_points > 0), None)
        if actor_id is None:
            raise EncounterValidationError('Site arrival requires a conscious party member.')
        self._execute_intent(CampaignSiteIntent(actor_id, SiteAction.ARRIVE))

    def owns_command(self, command):
        verb = command.strip().split(maxsplit=1)[0].lower()
        return verb in {'/visit', '/talk', '/site'} or (
            self.active and self.state.progress.in_dungeon and verb in {'/move', '/climb', '/fly', '/stand'}
        )

    def actor_for(self, controller_id):
        control = self.session.encounter_session.control_runtime
        control.validate_controller(controller_id)
        actors = [
            a for a in self.session._player_actor_ids() if control.actor_controllers.get(a) == controller_id
        ]
        if len(actors) != 1:
            raise EncounterClarificationRequiredError(
                'Site choices require exactly one controlled player character.'
            )
        return actors[0]

    def execute(self, controller_id, command):
        tokens = command.strip().split()
        verb = tokens[0].lower()
        session = self.session
        if verb == '/stand':
            parsed = session.encounter_session.command_interface.parse_command(command)
            session.encounter_session.control_runtime._authorize_intent(controller_id, parsed)
            session.encounter_session.control_runtime.kernel.dispatch(session.state, parsed)
        elif verb in {'/move', '/climb', '/fly'}:
            parsed = session.encounter_session.command_interface.parse_command(command)
            if not isinstance(parsed, MoveActorIntent):
                raise EncounterValidationError('Movement requires an actor id and explicit coordinates.')
            control = session.encounter_session.control_runtime
            control._authorize_intent(controller_id, parsed)
            if session.story_state.runtime_mode == RuntimeMode.STORYTELLING:
                parsed = ExploreMoveIntent(
                    parsed.actor_id, parsed.x, parsed.y, parsed.z, parsed.movement_intent_mode
                )
            result = self.engine.move(
                session.state, self.state, parsed, party_actor_ids=session._player_actor_ids()
            )
            self._commit(result)
        else:
            actor_id = self.actor_for(controller_id)
            if verb in {'/visit', '/talk'}:
                if len(tokens) != 2:
                    raise EncounterClarificationRequiredError(
                        f'Usage: {verb} <destination-id or speaker-id>. Choose a displayed option.'
                    )
                intent = CampaignSiteIntent(
                    actor_id, SiteAction.VISIT if verb == '/visit' else SiteAction.TALK, tokens[1]
                )
            else:
                if len(tokens) < 2:
                    raise EncounterClarificationRequiredError(
                        'Usage: /site <enter|leave|search|open|close|pick-lock|force|interact|engage> [target-id].'
                    )
                try:
                    action = SiteAction(tokens[1])
                except ValueError as exc:
                    raise EncounterValidationError('Unknown site command.') from exc
                allowed = {
                    SiteAction.ENTER,
                    SiteAction.LEAVE,
                    SiteAction.SEARCH,
                    SiteAction.OPEN,
                    SiteAction.CLOSE,
                    SiteAction.PICK_LOCK,
                    SiteAction.FORCE,
                    SiteAction.INTERACT,
                    SiteAction.ENGAGE,
                    SiteAction.SET_WEIGHT,
                }
                if action not in allowed:
                    raise EncounterPermissionError('This site transition is managed by the server.')
                expected = 2 if action == SiteAction.LEAVE else 3
                utilize = (
                    action in {SiteAction.OPEN, SiteAction.CLOSE}
                    and len(tokens) == 4
                    and tokens[3] == 'utilize'
                )
                if len(tokens) != expected and not utilize:
                    raise EncounterClarificationRequiredError(
                        'Select an explicit site target from the available choices.'
                    )
                if action == SiteAction.SET_WEIGHT:
                    try:
                        weight = float(tokens[2])
                    except ValueError as exc:
                        raise EncounterClarificationRequiredError(
                            'Supply a body weight in pounds: /site weight <lb>.'
                        ) from exc
                    intent = CampaignSiteIntent(actor_id, action, weight_lb=weight)
                else:
                    intent = CampaignSiteIntent(
                        actor_id,
                        action,
                        None if expected == 2 else tokens[2],
                        cost_mode=(
                            ObjectInteractionCostMode.UTILIZE if utilize else ObjectInteractionCostMode.FREE
                        ),
                    )
            self._execute_intent(intent)
        self.after_combat_action()
        return session.view_for_controller(controller_id)

    def natural_command(self, controller_id, text):
        """Resolve exact displayed choices; ambiguous action language has no side effects."""

        def normalized(value):
            return ' '.join(value.casefold().strip(' .!?').split())

        value = normalized(text)
        view = self.project(controller_id)
        choices = {}
        for place in view.places:
            for label in (f'Visit {place.name}', f'Go to {place.name}', f'Travel to {place.name}'):
                choices.setdefault(normalized(label), set()).add(place.command)
        for action in view.actions:
            choices.setdefault(normalized(action.label), set()).add(action.command)
        matches = choices.get(value, set())
        if len(matches) == 1:
            return next(iter(matches))
        if matches or re.match(
            r'^(?:i |we |please )?(?:go|visit|travel|enter|leave|open|close|search|move|climb|fly|attack|free|rescue|force|pick|talk|speak|ask|question|offer|read|collect|recover)\b',
            value,
        ):
            raise EncounterClarificationRequiredError(
                'Choose one explicit displayed action or supply the complete slash command; no action was taken.'
            )
        return None

    def validate_story_decision(self, decision):
        if decision.scene_update is not None:
            self.validate_scene_update(decision.scene_update)
        if decision.mode_switch_decision is not None:
            self.validate_mode_decision(decision.mode_switch_decision)

    def validate_scene_update(self, update):
        story = self.session.story_state
        if (update.location_id is not None and update.location_id != story.canonical_location_id) or (
            update.scene_id is not None and update.scene_id != story.current_scene_id
        ):
            raise EncounterValidationError(
                'Site locations and scenes change only through typed site actions.'
            )

    def validate_mode_decision(self, decision):
        action = decision.decision_type.value
        expected = 'remain_in_combat' if self.state.progress.active_encounter_id else 'stay_in_storytelling'
        if action != expected:
            raise EncounterValidationError('Site combat transitions are resolved by the campaign-site rules.')

    def _execute_intent(self, intent):
        self._commit(
            self.engine.resolve(
                self.session.state,
                self.state,
                intent,
                party_actor_ids=self.session._player_actor_ids(),
                current_location_id=self.session.story_state.canonical_location_id,
            )
        )

    def _commit(self, result):
        session = self.session
        control = session.encounter_session.control_runtime
        dm_ids = [key for key, value in control.controllers.items() if value.role.value == 'dm']
        if len(dm_ids) != 1:
            raise EncounterValidationError('A campaign site requires exactly one DM controller for its NPCs.')
        bindings = {
            key: value
            for key, value in control.actor_controllers.items()
            if key in result.encounter_state.actors
        }
        for actor_id, actor in result.encounter_state.actors.items():
            if actor_id not in bindings:
                if actor.side != ActorSide.MONSTER:
                    raise EncounterValidationError(
                        'A new player actor requires an explicit controller binding.'
                    )
                bindings[actor_id] = dm_ids[0]
        arriving = not self.state.progress.arrived and result.site_state.progress.arrived
        session.encounter_session.state = result.encounter_state
        self.state = result.site_state
        control.actor_controllers = bindings
        control.validate_actor_bindings(session.state)
        p = self.state.progress
        definition = self.engine.definition
        story = session.story_state
        story.canonical_location_id = (
            definition.dungeon_location_id if p.in_dungeon else definition.town_location_id
        )
        story.current_chapter_id = definition.chapter_id
        if arriving:
            story.current_party_goals = definition.arrival_goals
            story.open_loops = tuple(dict.fromkeys(story.open_loops + definition.arrival_open_loops))
        story.runtime_mode = RuntimeMode.COMBAT if p.active_encounter_id else RuntimeMode.STORYTELLING
        story.active_battlefield_map_id = session.state.battlefield.map_id if p.in_dungeon else None
        story.current_scene_id = definition.dungeon_scene_id if p.in_dungeon else definition.arrival_scene_id
        story.metadata['story_slice'] = definition.site_id
        story.metadata['retrieval_tags'] = (
            definition.site_id
            + ','
            + (definition.dungeon_location_id if p.in_dungeon else p.place_id or definition.town_location_id)
        )
        story.metadata['nearby_tags'] = (
            definition.dungeon_location_id if p.in_dungeon else p.place_id or definition.town_location_id
        )
        place = definition.places.get(p.place_id)
        story.metadata['visible_npc_ids'] = (
            ','.join(c.npc_id for c in place.conversations) if place is not None and not p.in_dungeon else ''
        )
        story.metadata['site_discoveries'] = '|'.join(sorted(p.flags))
        if result.public_text:
            story.recent_summary = result.public_text[-1]
        entries = [
            StoryTranscriptEntry(speaker='DM', text=text, visibility=StoryTranscriptVisibility.PUBLIC)
            for text in result.public_text
        ]
        for event in result.events:
            if isinstance(event, SiteCheckResolvedEvent):
                entries.append(
                    StoryTranscriptEntry(
                        speaker='Rules',
                        text=f'{event.ability}'
                        + (f' ({event.skill})' if event.skill else '')
                        + f' DC {event.dc}: roll {event.roll}, total {event.total} — '
                        + ('success.' if event.success else 'failure.'),
                        visibility=StoryTranscriptVisibility.PUBLIC,
                    )
                )
        if entries:
            session._append_transcript(tuple(entries))
        session._refresh_exploration_context(sync_memory=False)
        session._sync_memory_files()

    def after_combat_action(self):
        if self.state.pending_movement is not None and self.session.state.pending_reaction_window is None:
            self._commit(
                self.engine.resume_movement(
                    self.session.state, self.state, party_actor_ids=self.session._player_actor_ids()
                )
            )
        p = self.state.progress
        if p.active_encounter_id is None or self.session.state.pending_reaction_window is not None:
            return
        encounter = self.engine.definition.encounters[p.active_encounter_id]
        if all(self.session.state.actors[m.actor_id].current_hit_points <= 0 for m in encounter.monsters):
            actor_id = next(
                (
                    a
                    for a in self.session._player_actor_ids()
                    if self.session.state.actors[a].current_hit_points > 0
                ),
                None,
            )
            if actor_id is not None:
                self._execute_intent(CampaignSiteIntent(actor_id, SiteAction.RESOLVE_COMBAT))

    def feature_is_known(self, feature_id, *, dm_view):
        door = self.engine.definition.doors.get(feature_id)
        return (
            dm_view or door is None or not door.secret or feature_id in self.state.progress.discovered_doors
        )

    def project(self, controller_id):
        if not self.active:
            return None
        definition = self.engine.definition
        p = self.state.progress
        control = self.session.encounter_session.control_runtime
        binding = control.validate_controller(controller_id)
        actions = []

        def add(key, label, command):
            actions.append(WebSiteActionView(key, label, command))

        owned = [
            a for a in self.session._player_actor_ids() if control.actor_controllers.get(a) == controller_id
        ]
        actor = self.session.state.actors[owned[0]] if len(owned) == 1 else None
        if actor is not None and actor.current_hit_points > 0:
            if not p.in_dungeon:
                place = definition.places.get(p.place_id)
                if place is not None:
                    for conversation in place.conversations:
                        add(conversation.npc_id, conversation.label, f'/talk {conversation.npc_id}')
                for entrance in definition.entrances.values():
                    if entrance.place_id == p.place_id and (
                        not entrance.required_flag or entrance.required_flag in p.flags
                    ):
                        add(entrance.entrance_id, entrance.label, f'/site enter {entrance.entrance_id}')
            else:
                if p.active_encounter_id is None:
                    add('search', 'Search nearby surfaces (1 minute)', '/site search here')
                    if has_condition(actor, ConditionType.PRONE):
                        add('stand', 'Stand up', f'/stand {actor.actor_id}')
                    for entrance in definition.entrances.values():
                        if self.engine._near(actor.position, entrance.positions, 5):
                            add('leave', 'Return to Phandalin', '/site leave')
                            break
                    for item in definition.interactions.values():
                        if (
                            self.engine.room_for(actor.position) == item.room_id
                            and item.interaction_id not in p.completed_interactions
                            and set(item.requires) <= p.flags
                        ):
                            add(item.interaction_id, item.label, f'/site interact {item.interaction_id}')
                    for encounter in definition.encounters.values():
                        if (
                            not encounter.automatic
                            and encounter.encounter_id not in p.resolved_encounters
                            and self.engine.room_for(actor.position) == encounter.room_id
                        ):
                            add(
                                encounter.encounter_id,
                                f'Attack: {encounter.label}',
                                f'/site engage {encounter.encounter_id}',
                            )
                if p.active_encounter_id is None or self.session.state.active_actor_id == actor.actor_id:
                    for door in definition.doors.values():
                        if self.feature_is_known(door.door_id, dm_view=False) and self.engine._near(
                            actor.position, door.cells, 5
                        ):
                            action = 'close' if door.door_id in p.opened_doors else 'open'
                            utilize = (
                                p.active_encounter_id is not None
                                and not actor.remaining_free_object_interaction
                            )
                            add(
                                door.door_id,
                                f'{action.title()}: {door.label}' + (' (Utilize action)' if utilize else ''),
                                f'/site {action} {door.door_id}' + (' utilize' if utilize else ''),
                            )
                            if (
                                door.locked
                                and door.door_id not in p.unlocked_doors
                                and (door.key_flag is None or door.key_flag not in p.flags)
                            ):
                                add(
                                    door.door_id + '-pick',
                                    f'Pick lock: {door.label}',
                                    f'/site pick-lock {door.door_id}',
                                )
                                add(
                                    door.door_id + '-force',
                                    f'Force: {door.label}',
                                    f'/site force {door.door_id}',
                                )
        return WebCampaignSiteView(
            definition.site_id,
            p.in_dungeon,
            p.place_id,
            definition.town_image,
            definition.town_width_px,
            definition.town_height_px,
            (
                tuple(
                    WebTownPlaceView(
                        place.place_id,
                        place.name,
                        place.x,
                        place.y,
                        place.place_id == p.place_id,
                        f'/visit {place.place_id}',
                    )
                    for place in definition.places.values()
                )
                if not p.in_dungeon
                else ()
            ),
            tuple(actions),
            tuple(sorted(p.flags)),
            None if actor is None else actor.body_weight_lb,
        )
