from __future__ import annotations

import unittest

from shared_types.battlefield import CoverLevel
from shared_types.capabilities import (
    ActiveEffectDefinition,
    CapabilityDefinition,
    CapabilityKind,
    DurationAnchor,
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
    PersistentObserverFilter,
    PersistentObserverMode,
    StartActiveEffectDef,
    TargetSelectionKind,
    TargetingSpec,
)
from shared_types.encounter_events import ActiveEffectEndedEvent
from shared_types.encounter_intents import ResolveIllusionInteractionIntent
from shared_types.encounter_models import GridPosition, RuntimeSpellState, IllusionObserverStatus
from session_server.bootstrap import build_default_character_record, build_lmop_story_demo_encounter_session_from_records
from session_server.web_projection import inspect_cell, project_encounter_session_view
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class SilentImageLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Silent Image'
    SPELL_SLUG = 'silent-image'

    def _capability(self) -> CapabilityDefinition:
        return CapabilityDefinition(
            capability_id='silent-image',
            name='Silent Image',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.POINT,
                range_ft=60,
                requires_line_of_effect=False,
                point_must_be_visible=True,
            ),
            effect=StartActiveEffectDef(
                active_effect=ActiveEffectDefinition(
                    name='Silent Image',
                    duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=100, anchor=DurationAnchor.SOURCE),
                    concentration=True,
                    replace_existing_same_name_from_source=True,
                    illusions=(
                        IllusionDefinition(
                            template_id=IllusionTemplateId.MINOR_VISUAL_DOOR,
                            subtype=IllusionSubtype.SMALL_STATIC_VISUAL,
                            modality=IllusionModality.VISUAL,
                            display_name='Painted Door',
                            display_description='A convincing painted door set into the stone wall.',
                            width_ft=5,
                            depth_ft=1,
                            height_ft=8,
                            semantic_tags=('silent-image', 'door', 'visual'),
                            observer_filter=PersistentObserverFilter(
                                observer_mode=PersistentObserverMode.SELECTED_OBSERVERS,
                                observer_actor_ids=('player-1',),
                            ),
                            apparent_properties=IllusionApparentProperties(
                                apparent_cover=CoverLevel.HALF,
                                apparent_blocker=True,
                                apparent_door=True,
                                apparent_object_category='door',
                            ),
                            actual_properties=IllusionActualProperties(),
                            reveal_policies=(IllusionRevealPolicy.ON_STUDY_SUCCESS, IllusionRevealPolicy.ON_PHYSICAL_INTERACTION),
                        ),
                    ),
                )
            ),
        )

    def _inject_spell(self, session) -> None:
        session.state.actors['player-1'].spells[self.SPELL_SLUG] = RuntimeSpellState(
            option_id=self.SPELL_SLUG,
            name=self.SPELL_NAME,
            source='XPHB',
            action_cost='action',
            range_ft=60,
            remaining_uses=None,
            level=1,
            concentration=True,
            capability=self._capability(),
        )

    def _setup_session(self):
        records = tuple(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL) for _ in range(4))
        session = build_lmop_story_demo_encounter_session_from_records(player_records=records, base_url=LOCAL_MIRROR_BASE_URL)
        self._inject_spell(session)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['player-2'].position = GridPosition(2, 0, 0)
        session.state.actors['player-3'].position = GridPosition(4, 0, 0)
        return session

    def _apply_events(self, session, events):
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)

    def _illusion_id(self, session) -> str:
        return next(iter(session.state.illusions))

    def test_metadata_and_command_shape_are_present(self) -> None:
        session = self.build_default_session()
        self._inject_spell(session)
        intent = session.command_interface.parse_command('/cast player-1 silent-image 2 3 --template minor_visual_door --label Door --description "Painted door"')
        self.assertEqual(intent.actor_id, 'player-1')
        self.assertEqual(intent.spell_id, self.SPELL_SLUG)
        self.assertEqual((intent.x, intent.y), (2, 3))
        self.assertEqual({parameter.key: parameter.value for parameter in intent.parameters}, {
            'template': 'minor_visual_door',
            'label': 'Door',
            'description': '"Painted door"',
        })

    def test_cast_creates_the_illusion_for_the_selected_observer(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 3, 0))
        illusion_id = self._illusion_id(session)
        view = project_encounter_session_view(session, 'player-1-controller', session_id='test')
        self.assertTrue(any(feature.feature_type == 'illusion' and feature.display_name == 'Painted Door' for feature in view.map.features))
        self.assertEqual(session.state.illusions[illusion_id].observer_states['player-1'].status, IllusionObserverStatus.INTENDED)

    def test_nonselected_observer_does_not_see_the_illusion(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 3, 0))
        view = project_encounter_session_view(session, 'player-2-controller', session_id='test')
        self.assertFalse(any(feature.feature_type == 'illusion' for feature in view.map.features))

    def test_study_success_reveals_the_false_door(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 3, 0))
        illusion_id = self._illusion_id(session)
        before = inspect_cell(session, 'player-1-controller', x=2, y=3, z=0)
        self.assertTrue(before.apparent_blocked)
        session.command_interface.kernel.dispatch(
            session.state,
            ResolveIllusionInteractionIntent(
                actor_id='player-1',
                illusion_id=illusion_id,
                interaction_kind=IllusionInteractionKind.STUDY_SUCCESS,
            ),
        )
        after = inspect_cell(session, 'player-1-controller', x=2, y=3, z=0)
        self.assertFalse(after.apparent_blocked)
        self.assertEqual(session.state.illusions[illusion_id].observer_states['player-1'].status, IllusionObserverStatus.PIERCED)

    def test_physical_interaction_marks_the_illusion_as_disbelieved(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 3, 0))
        illusion_id = self._illusion_id(session)
        session.command_interface.kernel.dispatch(
            session.state,
            ResolveIllusionInteractionIntent(
                actor_id='player-1',
                illusion_id=illusion_id,
                interaction_kind=IllusionInteractionKind.PHYSICAL_INTERACTION,
            ),
        )
        self.assertEqual(session.state.illusions[illusion_id].observer_states['player-1'].status, IllusionObserverStatus.DISBELIEVED)

    def test_ending_the_effect_clears_the_illusion_and_projection(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG, point=GridPosition(2, 3, 0))
        effect = next(effect for effect in session.state.active_effects.values() if effect.name == 'Silent Image')
        events = session.command_interface.kernel.effect_executor.end_active_effect(session.state, effect_id=effect.effect_instance_id, reason='test-end')
        self._apply_events(session, events)
        self.assertFalse(session.state.active_effects)
        self.assertFalse(session.state.illusions)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) for event in events))


if __name__ == '__main__':
    unittest.main()