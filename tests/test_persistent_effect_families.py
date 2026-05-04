from __future__ import annotations

import unittest

from encounter_runtime.adjudication import EncounterAdjudicationRuntime
from session_server.bootstrap import (
    build_default_character_record,
    build_default_encounter_session,
    build_lmop_story_demo_encounter_session_from_records,
)
from session_server.web_projection import inspect_cell, project_encounter_session_view
from shared_types.adjudication import (
    AdjudicationIllusionSpec,
    AdjudicationOperation,
    AdjudicationOperationType,
    AdjudicationPlan,
    AdjudicationType,
)
from shared_types.battlefield import CoverLevel
from shared_types.capabilities import (
    ActiveEffectDefinition,
    AreaShape,
    CapabilityDefinition,
    CapabilityKind,
    CompositeEffect,
    CreatedObjectDefinition,
    DurationSpec,
    EffectDurationType,
    IllusionActualProperties,
    IllusionApparentProperties,
    IllusionDefinition,
    IllusionInteractionKind,
    IllusionModality,
    IllusionRevealPolicy,
    IllusionSubtype,
    IllusionTemplateId,
    InformationPayloadDefinition,
    InformationPayloadKind,
    InformationShareMode,
    PersistentAreaDefinition,
    PersistentObserverFilter,
    PersistentObserverMode,
    RitualCastingMetadata,
    StartActiveEffectDef,
    SummonedCreatureDefinition,
    TargetSelectionKind,
    TargetingSpec,
    TriggerTiming,
    ZoneTickDefinition,
    DamageEffectDef,
)
from shared_types.encounter_events import (
    ActiveEffectEndedEvent,
    ActiveEffectStartedEvent,
    CreatedCreatureSpawnedEvent,
    CreatedObjectSpawnedEvent,
    PersistentAreaTickedEvent,
    RitualCastCompletedEvent,
)
from shared_types.encounter_intents import AdvanceTimeIntent, ResolveIllusionInteractionIntent, StartRitualCastIntent
from shared_types.encounter_models import RuntimeCapabilityState, TimingEntryKind
from shared_types.rest import RestActivityType
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL
from shared_types.storytelling import RuntimeMode


class PersistentEffectFamilyTests(unittest.TestCase):
    def _build_default_session(self):
        return build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)

    def _build_demo_session(self):
        records = tuple(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL) for _ in range(4))
        return build_lmop_story_demo_encounter_session_from_records(
            player_records=records,
            base_url=LOCAL_MIRROR_BASE_URL,
        )

    def _apply_events(self, session, events):
        kernel = session.command_interface.kernel
        for event in events:
            kernel._apply_event(session.state, event)

    def _start_capability(self, session, *, actor_id: str, capability: CapabilityDefinition, point=None, target_id=None) -> str:
        kernel = session.command_interface.kernel
        actor = session.state.actors[actor_id]
        events = kernel.effect_executor.execute_capability(
            session.state,
            actor=actor,
            capability=capability,
            point=point,
            target_id=target_id,
        )
        self._apply_events(session, events)
        started = next(event for event in events if isinstance(event, ActiveEffectStartedEvent))
        return started.effect.effect_instance_id

    def test_created_object_lifecycle_tracks_battlefield_feature_cleanup(self) -> None:
        session = self._build_default_session()
        player = session.state.actors['player-1']
        capability = CapabilityDefinition(
            capability_id='test-created-object',
            name='Create Test Crate',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=30, requires_line_of_effect=False),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Created Crate',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=2),
                    created_objects=(
                        CreatedObjectDefinition(
                            name='Crate',
                            feature_type='created-crate',
                            traversable=False,
                            occupiable=False,
                            blocks_los=True,
                            blocks_loe=True,
                            cover_provided=CoverLevel.HALF,
                            semantic_tags=('crate', 'created'),
                        ),
                    ),
                )
            ),
        )
        point = player.position
        effect_id = self._start_capability(session, actor_id='player-1', capability=capability, point=point)
        self.assertEqual(len(session.state.created_objects), 1)
        created_object = next(iter(session.state.created_objects.values()))
        self.assertTrue(any(isinstance(event, CreatedObjectSpawnedEvent) for event in session.state.event_log))
        self.assertIsNotNone(created_object.linked_feature_id)
        self.assertIn(created_object.linked_feature_id, session.state.battlefield.features)

        end_events = session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect_id, reason='test-cleanup')
        self._apply_events(session, end_events)
        self.assertFalse(session.state.created_objects)
        self.assertNotIn(created_object.linked_feature_id, session.state.battlefield.features)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) for event in session.state.event_log))

    def test_created_creature_lifecycle_hook_tracks_spawn_and_cleanup(self) -> None:
        session = self._build_default_session()
        capability = CapabilityDefinition(
            capability_id='test-summon',
            name='Summon Test Echo',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Summoned Echo',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=2),
                    summoned_creatures=(
                        SummonedCreatureDefinition(
                            summon_name='Echo Beast',
                            semantic_tags=('summon', 'echo'),
                        ),
                    ),
                )
            ),
        )
        effect_id = self._start_capability(session, actor_id='player-1', capability=capability)
        self.assertEqual(len(session.state.summoned_creatures), 1)
        self.assertTrue(any(isinstance(event, CreatedCreatureSpawnedEvent) for event in session.state.event_log))

        end_events = session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect_id, reason='despawn')
        self._apply_events(session, end_events)
        self.assertFalse(session.state.summoned_creatures)

    def test_persistent_area_ticks_on_affected_actor_turn_not_source_turn_only(self) -> None:
        session = self._build_default_session()
        player = session.state.actors['player-1']
        mage = session.state.actors['monster-mage-1']
        capability = CapabilityDefinition(
            capability_id='test-burning-zone',
            name='Burning Zone',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=60, requires_line_of_effect=False),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Burning Zone',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=3),
                    persistent_areas=(
                        PersistentAreaDefinition(
                            name='Burning Zone',
                            area_shape=AreaShape.CUBE,
                            area_size_ft=5,
                            tick_effects=(
                                ZoneTickDefinition(
                                    timing=TriggerTiming.START_OF_TURN,
                                    effects=(DamageEffectDef(dice_count=1, die_faces=4, bonus=0, damage_type='fire'),),
                                ),
                            ),
                        ),
                    ),
                )
            ),
        )
        self._start_capability(session, actor_id='monster-mage-1', capability=capability, point=player.position)
        start_hp = player.current_hit_points
        entries = session.command_interface.kernel.effect_executor.collect_turn_boundary_entries(
            session.state,
            actor_id='player-1',
            timing=TriggerTiming.START_OF_TURN,
        )
        self.assertTrue(any(entry.kind == TimingEntryKind.PERSISTENT_AREA_TICK for entry in entries))
        tick_entry = next(entry for entry in entries if entry.kind == TimingEntryKind.PERSISTENT_AREA_TICK)
        events = session.command_interface.kernel.effect_executor.resolve_turn_boundary_entry(session.state, tick_entry)
        self._apply_events(session, events)
        self.assertTrue(any(isinstance(event, PersistentAreaTickedEvent) for event in events))
        self.assertLess(session.state.actors['player-1'].current_hit_points, start_hp)
        self.assertNotEqual(mage.actor_id, player.actor_id)

    def test_observer_relative_illusion_projection_and_disbelief(self) -> None:
        session = self._build_demo_session()
        player_one = session.state.actors['player-1']
        point = player_one.position
        capability = CapabilityDefinition(
            capability_id='test-false-door',
            name='False Door',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.POINT, range_ft=30, requires_line_of_effect=False),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='False Door',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=5),
                    illusions=(
                        IllusionDefinition(
                            template_id=IllusionTemplateId.MINOR_VISUAL_DOOR,
                            subtype=IllusionSubtype.SMALL_STATIC_VISUAL,
                            modality=IllusionModality.VISUAL,
                            display_name='False Door',
                            display_description='A painted doorway in the embankment.',
                            semantic_tags=('door', 'illusion'),
                            observer_filter=PersistentObserverFilter(
                                observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
                                observer_actor_ids=('player-1',),
                            ),
                            apparent_properties=IllusionApparentProperties(
                                apparent_cover=CoverLevel.HALF,
                                apparent_blocker=True,
                                apparent_door=True,
                            ),
                            actual_properties=IllusionActualProperties(),
                            reveal_policies=(IllusionRevealPolicy.ON_STUDY_SUCCESS,),
                        ),
                    ),
                )
            ),
        )
        self._start_capability(session, actor_id='player-1', capability=capability, point=point)
        illusion_id = next(iter(session.state.illusions))

        player_one_view = project_encounter_session_view(session, 'player-1-controller', session_id='test')
        player_two_view = project_encounter_session_view(session, 'player-2-controller', session_id='test')
        self.assertTrue(any(feature.feature_type == 'illusion' and feature.display_name == 'False Door' for feature in player_one_view.map.features))
        self.assertFalse(any(feature.feature_type == 'illusion' for feature in player_two_view.map.features))

        inspection_before = inspect_cell(session, 'player-1-controller', x=point.x, y=point.y, z=point.z)
        self.assertTrue(inspection_before.apparent_blocked)
        session.command_interface.kernel.dispatch(
            session.state,
            ResolveIllusionInteractionIntent(
                actor_id='player-1',
                illusion_id=illusion_id,
                interaction_kind=IllusionInteractionKind.STUDY_SUCCESS,
            ),
        )
        inspection_after = inspect_cell(session, 'player-1-controller', x=point.x, y=point.y, z=point.z)
        self.assertFalse(inspection_after.apparent_blocked)

    def test_adjudication_create_illusion_operation_starts_active_effect(self) -> None:
        session = self._build_default_session()
        runtime = EncounterAdjudicationRuntime(kernel=session.command_interface.kernel)
        point = session.state.actors['player-1'].position
        plan = AdjudicationPlan(
            action_summary='Create a false door.',
            doable=True,
            adjudication_type=AdjudicationType.AUTOMATIC_SUCCESS,
            reasoning_summary_for_dm='Minor illusion fits here without a roll.',
            operation_plan=(
                AdjudicationOperation(
                    operation_type=AdjudicationOperationType.CREATE_ILLUSION,
                    x=point.x,
                    y=point.y,
                    z=point.z,
                    duration_rounds=3,
                    illusion_spec=AdjudicationIllusionSpec(
                        template_id=IllusionTemplateId.MINOR_VISUAL_DOOR,
                        display_name='False Door',
                        display_description='A painted false door.',
                        semantic_tags=('door',),
                        apparent_blocker=True,
                        apparent_cover=CoverLevel.HALF,
                    ),
                ),
            ),
        )
        result = runtime.execute_plan(
            session.state,
            runtime_mode=RuntimeMode.STORYTELLING,
            controller_id='player-1-controller',
            actor_id='player-1',
            plan=plan,
        )
        self.assertEqual(result.outcome, 'success')
        self.assertTrue(session.state.active_effects)
        self.assertTrue(session.state.illusions)

    def test_detection_payload_projection_is_private_to_observer_and_dm(self) -> None:
        session = self._build_demo_session()
        capability = CapabilityDefinition(
            capability_id='test-detect',
            name='Arcane Ping',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Arcane Ping',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=3),
                    information_payloads=(
                        InformationPayloadDefinition(
                            kind=InformationPayloadKind.DETECTION,
                            title='Arcane Ping',
                            detail='You sense hidden magic nearby.',
                            observer_filter=PersistentObserverFilter(
                                observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
                                observer_actor_ids=('player-1',),
                            ),
                            share_mode=InformationShareMode.OBSERVER_ONLY,
                        ),
                    ),
                )
            ),
        )
        self._start_capability(session, actor_id='player-1', capability=capability)
        player_one_view = project_encounter_session_view(session, 'player-1-controller', session_id='test')
        player_two_view = project_encounter_session_view(session, 'player-2-controller', session_id='test')
        dm_view = project_encounter_session_view(session, 'dm', session_id='test')
        self.assertTrue(any('Arcane Ping' in entry.text for entry in player_one_view.chat_entries))
        self.assertFalse(any('Arcane Ping' in entry.text for entry in player_two_view.chat_entries))
        self.assertTrue(any('Arcane Ping' in entry.text for entry in dm_view.chat_entries))

    def test_ritual_cast_hook_starts_and_completes_after_time_advance(self) -> None:
        session = self._build_default_session()
        actor = session.state.actors['player-1']
        ritual_capability = CapabilityDefinition(
            capability_id='ritual-mark',
            name='Ritual Mark',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF),
            effect=CompositeEffect(effects=()),
            ritual_casting=RitualCastingMetadata(
                can_cast_as_ritual=True,
                additional_cast_seconds=600,
                no_slot_cost=True,
                non_combat_only=True,
            ),
        )
        actor.capabilities['ritual-mark'] = RuntimeCapabilityState(
            option_id='ritual-mark',
            name='Ritual Mark',
            source='TEST',
            kind=CapabilityKind.SPELL,
            action_cost='action',
            remaining_uses=None,
            capability=ritual_capability,
        )
        session.command_interface.kernel.dispatch(
            session.state,
            StartRitualCastIntent(actor_id='player-1', capability_id='ritual-mark'),
        )
        self.assertTrue(session.state.ritual_casts)
        session.command_interface.kernel.dispatch(
            session.state,
            AdvanceTimeIntent(minutes=10, activity_type=RestActivityType.QUIET),
        )
        self.assertFalse(session.state.ritual_casts)
        self.assertTrue(any(isinstance(event, RitualCastCompletedEvent) for event in session.state.event_log))


if __name__ == '__main__':
    unittest.main()
