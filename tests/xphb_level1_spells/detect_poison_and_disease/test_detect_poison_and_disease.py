from __future__ import annotations

from dataclasses import replace
import unittest

from shared_types.capabilities import ActiveEffectDefinition, CapabilityDefinition, CapabilityKind, DurationAnchor, DurationSpec, EffectDurationType, StartActiveEffectDef, TargetSelectionKind, TargetingSpec
from shared_types.conditions import ConditionType
from shared_types.encounter_events import ConditionAddedEvent, DetectionPayloadProducedEvent
from shared_types.encounter_models import GridPosition
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


class DetectPoisonAndDiseaseLevel1SpellTests(EncounterLevel1SpellTestCase):
    SPELL_NAME = 'Detect Poison and Disease'
    SPELL_SLUG = 'detect-poison-and-disease'

    def _setup_session(self):
        session = self.build_default_session()
        self.grant_spell(session, self.SPELL_NAME)
        session.state.actors['player-1'].position = GridPosition(0, 0, 0)
        session.state.actors['monster-skeleton-1'].position = GridPosition(2, 0, 0)
        session.state.actors['monster-mage-1'].position = GridPosition(4, 0, 0)
        return session

    def _payload(self, session):
        return [event for event in session.state.event_log if isinstance(event, DetectionPayloadProducedEvent)][-1].payload

    def _add_disease_effect(self, session, actor_id: str):
        actor = session.state.actors['player-1']
        capability = CapabilityDefinition(
            capability_id='ashen-disease',
            name='Ashen Disease',
            kind=CapabilityKind.SPELL,
            source='TEST',
            action_cost='none',
            targeting=TargetingSpec(selection_kind=TargetSelectionKind.CREATURE),
            effect=StartActiveEffectDef(active_effect=ActiveEffectDefinition(name='Ashen Disease', duration=DurationSpec(duration_type=EffectDurationType.ROUNDS, rounds=10, anchor=DurationAnchor.SOURCE))),
        )
        session.command_interface.kernel.effect_executor._start_active_effect(session.state, [], source_actor_id=actor.actor_id, target_ids=(actor_id,), capability=capability, definition=capability.effect.active_effect, point=session.state.actors[actor_id].position)

    def test_cast_reports_nothing_when_no_poison_or_disease_is_present(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('Nothing relevant is detected in range.', self._payload(session).definition.detail)

    def test_poisoned_condition_is_detected(self) -> None:
        session = self._setup_session()
        instance = session.command_interface.kernel._make_condition_instance(target_actor_id='monster-skeleton-1', condition_type=ConditionType.POISONED, source_label='test-poison')
        session.command_interface.kernel._apply_event(session.state, ConditionAddedEvent(actor_id='monster-skeleton-1', instance=instance))
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('poisoned', self._payload(session).definition.detail)

    def test_poisonous_creatures_are_detected(self) -> None:
        session = self._setup_session()
        attack_id = next(iter(session.state.actors['monster-skeleton-1'].attacks))
        session.state.actors['monster-skeleton-1'].attacks[attack_id] = replace(
            session.state.actors['monster-skeleton-1'].attacks[attack_id],
            damage_type='poison',
        )
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('poisonous creature', self._payload(session).definition.detail)

    def test_disease_effects_are_detected(self) -> None:
        session = self._setup_session()
        self._add_disease_effect(session, 'monster-mage-1')
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertIn('disease effect', self._payload(session).definition.detail)

    def test_inspect_mode_requires_the_spell_to_be_active_first(self) -> None:
        session = self._setup_session()
        with self.assertRaisesRegex(Exception, 'must already be active'):
            self.apply_spell_events(session, spell_id=self.SPELL_SLUG, parameters={'mode': 'inspect'})

    def test_detection_payload_is_private_to_the_caster(self) -> None:
        session = self._setup_session()
        self.apply_spell_events(session, spell_id=self.SPELL_SLUG)
        self.assertEqual(self._payload(session).persistent.observer_actor_ids, ('player-1',))


if __name__ == '__main__':
    unittest.main()
