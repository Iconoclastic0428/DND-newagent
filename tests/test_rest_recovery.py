from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import unittest

from character_creation import build_default_kernel
from encounter_runtime import build_default_encounter_runtime
from player_interface import SlashCommandInterface
from shared_types.capabilities import CapabilityDefinition, CapabilityKind, CompositeEffect, TargetAffinity, TargetSelectionKind, TargetingSpec
from shared_types.conditions import ConditionType
from shared_types.encounter_events import (
    DamageAppliedEvent,
    LongRestCompletedEvent,
    LongRestInterruptedEvent,
    ResourceRecoveredFromRestEvent,
    SpellCastEvent,
    ShortRestCompletedEvent,
    ShortRestInterruptedEvent,
    SpellSlotsRecoveredFromRestEvent,
)
from shared_types.encounter_intents import AdvanceTimeIntent, ResumeRestIntent, StartEncounterIntent, StartLongRestIntent, StartShortRestIntent, SpendHitPointDieIntent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement, RuntimeCapabilityState, RuntimeSpellState
from shared_types.rest import RestActivityType, RestRecoveryMode, RestRecoveryRule, RestRecoverySpec, RestStateStatus


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class RestRecoveryTests(unittest.TestCase):
    def _build_creation_record(self, *, class_id: str, class_skills: str, background_id: str = 'acolyte', extra_commands: tuple[str, ...] = ()):
        kernel = build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)
        ui = SlashCommandInterface(kernel)
        state = kernel.new_state()
        commands = [
            '/create begin',
            '/create choose species aasimar',
            f'/create choose class {class_id}',
            f'/create choose class-skills {class_skills}',
            f'/create choose background {background_id}',
            *extra_commands,
            '/create ability generate point-buy 15 14 13 12 10 8',
            '/create ability assign 8 14 13 15 12 10',
            '/create background-asi choose acolyte-int2-wis1',
            '/create equipment background gold',
            '/create equipment class package ' + (f'{class_id}-package-1' if class_id != 'wizard' else 'wizard-package-1'),
            '/create confirm',
        ]
        for command in commands:
            state, _ = ui.execute(state, command)
        assert state.character_record is not None
        return state.character_record

    def _build_wizard_record(self):
        return self._build_creation_record(
            class_id='wizard',
            class_skills='Arcana History',
            extra_commands=(
                '/create choose choice class:wizard:cantrips fire-bolt mage-hand light',
                '/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person',
                '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS',
                '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance',
                '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds',
            ),
        )

    def _build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _build_player_state(self, record):
        runtime = self._build_runtime()
        state = runtime.new_state(characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),), monsters=())
        return runtime, state

    def _build_player_and_monster_state(self, record):
        runtime = self._build_runtime()
        skeleton_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),),
            monsters=(MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),),
        )
        return runtime, state

    def test_cannot_start_rest_at_zero_hit_points(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        state.actors['player-1'].current_hit_points = 0

        with self.assertRaisesRegex(Exception, 'at least 1 HP'):
            runtime.kernel.dispatch(state, StartShortRestIntent(actor_id='player-1'))
        with self.assertRaisesRegex(Exception, 'at least 1 HP'):
            runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))

    def test_short_rest_completes_after_one_hour_and_recovers_feature(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.capabilities['test-short-rest-feature'] = RuntimeCapabilityState(
            option_id='test-short-rest-feature',
            name='Test Recovery Feature',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=0,
            capability=CapabilityDefinition(
                capability_id='test-short-rest-feature',
                name='Test Recovery Feature',
                kind=CapabilityKind.CLASS_FEATURE,
                source='XPHB',
                action_cost='bonus',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
                effect=CompositeEffect(effects=()),
            ),
            max_uses=2,
            rest_recovery=RestRecoverySpec(
                short_rest=RestRecoveryRule(mode=RestRecoveryMode.FIXED, amount=1),
                long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL),
            ),
        )

        runtime.kernel.dispatch(state, StartShortRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.LIGHT_ACTIVITY))

        self.assertEqual(actor.rest_state.status, RestStateStatus.SHORT_REST_COMPLETED)
        self.assertTrue(actor.rest_state.hit_dice_window_open)
        self.assertEqual(actor.capabilities['test-short-rest-feature'].remaining_uses, 1)
        self.assertTrue(any(isinstance(event, ShortRestCompletedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, ResourceRecoveredFromRestEvent) and event.resource_id == 'test-short-rest-feature' for event in state.event_log))

    def test_short_rest_interruption_gives_no_benefits(self) -> None:
        runtime, state = self._build_player_and_monster_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.capabilities['test-short-rest-feature'] = RuntimeCapabilityState(
            option_id='test-short-rest-feature',
            name='Test Recovery Feature',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=0,
            capability=CapabilityDefinition(
                capability_id='test-short-rest-feature',
                name='Test Recovery Feature',
                kind=CapabilityKind.CLASS_FEATURE,
                source='XPHB',
                action_cost='bonus',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
                effect=CompositeEffect(effects=()),
            ),
            max_uses=2,
            rest_recovery=RestRecoverySpec(
                short_rest=RestRecoveryRule(mode=RestRecoveryMode.FIXED, amount=1),
                long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL),
            ),
        )

        runtime.kernel.dispatch(state, StartShortRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=30, activity_type=RestActivityType.LIGHT_ACTIVITY))
        runtime.kernel.dispatch(state, StartEncounterIntent())

        self.assertEqual(actor.rest_state.status, RestStateStatus.INTERRUPTED)
        self.assertEqual(actor.capabilities['test-short-rest-feature'].remaining_uses, 0)
        self.assertFalse(actor.rest_state.hit_dice_window_open)
        self.assertTrue(any(isinstance(event, ShortRestInterruptedEvent) for event in state.event_log))

    def test_hit_point_die_spending_recovers_hit_points_and_tracks_remaining_dice(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.current_hit_points = max(1, actor.current_hit_points - 5)

        runtime.kernel.dispatch(state, StartShortRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.LIGHT_ACTIVITY))
        before_hit_points = actor.current_hit_points
        before_dice = actor.remaining_hit_dice
        runtime.kernel.dispatch(state, SpendHitPointDieIntent(actor_id='player-1'))

        self.assertLess(actor.remaining_hit_dice, before_dice)
        self.assertGreater(actor.current_hit_points, before_hit_points)

    def test_long_rest_completes_and_restores_hp_hit_dice_spell_slots_and_exhaustion(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.current_hit_points = 1
        actor.remaining_hit_dice = 0
        actor.resource_pools['spell-slot-1'].current = 0
        actor.condition_instances = actor.condition_instances + (
            runtime.kernel._make_condition_instance(target_actor_id='player-1', condition_type=ConditionType.EXHAUSTION, source_label='test'),
        )

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=360, activity_type=RestActivityType.SLEEP))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=120, activity_type=RestActivityType.LIGHT_ACTIVITY))

        self.assertEqual(actor.rest_state.status, RestStateStatus.LONG_REST_COMPLETED)
        self.assertEqual(actor.current_hit_points, actor.max_hit_points)
        self.assertEqual(actor.remaining_hit_dice, actor.total_hit_dice)
        self.assertEqual(actor.resource_pools['spell-slot-1'].current, actor.resource_pools['spell-slot-1'].maximum)
        self.assertFalse(any(instance.condition_type == ConditionType.EXHAUSTION for instance in actor.condition_instances))
        self.assertTrue(any(isinstance(event, LongRestCompletedEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, SpellSlotsRecoveredFromRestEvent) and event.resource_id == 'spell-slot-1' for event in state.event_log))

    def test_long_rest_lockout_is_enforced(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=360, activity_type=RestActivityType.SLEEP))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=120, activity_type=RestActivityType.LIGHT_ACTIVITY))
        self.assertEqual(actor.rest_state.status, RestStateStatus.LONG_REST_COMPLETED)

        with self.assertRaisesRegex(Exception, '16 hours'):
            runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))

    def test_interrupted_long_rest_after_one_hour_grants_short_rest_benefits(self) -> None:
        runtime, state = self._build_player_and_monster_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.capabilities['test-short-rest-feature'] = RuntimeCapabilityState(
            option_id='test-short-rest-feature',
            name='Test Recovery Feature',
            source='XPHB',
            kind=CapabilityKind.CLASS_FEATURE,
            action_cost='bonus',
            remaining_uses=0,
            capability=CapabilityDefinition(
                capability_id='test-short-rest-feature',
                name='Test Recovery Feature',
                kind=CapabilityKind.CLASS_FEATURE,
                source='XPHB',
                action_cost='bonus',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
                effect=CompositeEffect(effects=()),
            ),
            max_uses=2,
            rest_recovery=RestRecoverySpec(
                short_rest=RestRecoveryRule(mode=RestRecoveryMode.FIXED, amount=1),
                long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL),
            ),
        )

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.SLEEP))
        runtime.kernel.dispatch(state, StartEncounterIntent())

        self.assertEqual(actor.rest_state.status, RestStateStatus.INTERRUPTED)
        self.assertTrue(actor.rest_state.hit_dice_window_open)
        self.assertEqual(actor.capabilities['test-short-rest-feature'].remaining_uses, 1)
        self.assertTrue(any(isinstance(event, LongRestInterruptedEvent) and event.granted_short_rest_benefits for event in state.event_log))

    def test_resumed_long_rest_adds_one_hour_per_interruption(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.SLEEP))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.EXERTION))
        self.assertEqual(actor.rest_state.status, RestStateStatus.INTERRUPTED)
        self.assertEqual(actor.rest_state.required_rest_seconds, 9 * 60 * 60)

        runtime.kernel.dispatch(state, ResumeRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=360, activity_type=RestActivityType.SLEEP))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=120, activity_type=RestActivityType.LIGHT_ACTIVITY))

        self.assertEqual(actor.rest_state.status, RestStateStatus.LONG_REST_COMPLETED)
        self.assertTrue(any(isinstance(event, LongRestInterruptedEvent) for event in state.event_log))

    def test_non_cantrip_spell_interrupts_long_rest(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=30, activity_type=RestActivityType.SLEEP))
        actor.spells['rest-test-spell'] = RuntimeSpellState(
            option_id='rest-test-spell',
            name='Rest Test Spell',
            source='XPHB',
            action_cost='action',
            range_ft=60,
            remaining_uses=1,
            level=1,
        )
        runtime.kernel._apply_event(
            state,
            SpellCastEvent(
                actor_id='player-1',
                spell_id='rest-test-spell',
                action_cost='action',
                from_position=actor.position,
                remaining_uses=0,
            ),
        )

        self.assertEqual(actor.rest_state.status, RestStateStatus.INTERRUPTED)

    def test_damage_interrupts_long_rest(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']

        runtime.kernel.dispatch(state, StartLongRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=30, activity_type=RestActivityType.SLEEP))
        hit_points_after, temp_hit_points_after, applied_damage_total, effect_events = runtime.kernel._damage_preview(state, actor, 3, damage_type='slashing')
        for event in effect_events:
            runtime.kernel._apply_event(state, event)
        runtime.kernel._apply_event(
            state,
            DamageAppliedEvent(
                source_actor_id='test-source',
                target_id='player-1',
                damage_total=3,
                applied_damage_total=applied_damage_total,
                target_hit_points_after=hit_points_after,
                target_temp_hit_points_after=temp_hit_points_after,
                damage_type='slashing',
            ),
        )

        self.assertEqual(actor.rest_state.status, RestStateStatus.INTERRUPTED)

    def test_item_charge_recovery_uses_same_shared_framework(self) -> None:
        runtime, state = self._build_player_state(self._build_wizard_record())
        actor = state.actors['player-1']
        actor.capabilities['test-item-charge'] = RuntimeCapabilityState(
            option_id='test-item-charge',
            name='Test Wand',
            source='XPHB',
            kind=CapabilityKind.ITEM,
            action_cost='action',
            remaining_uses=0,
            capability=CapabilityDefinition(
                capability_id='test-item-charge',
                name='Test Wand',
                kind=CapabilityKind.ITEM,
                source='XPHB',
                action_cost='action',
                targeting=TargetingSpec(selection_kind=TargetSelectionKind.SELF, affinity=TargetAffinity.SELF_ONLY),
                effect=CompositeEffect(effects=()),
            ),
            max_uses=1,
            rest_recovery=RestRecoverySpec(short_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL)),
        )

        runtime.kernel.dispatch(state, StartShortRestIntent(actor_id='player-1'))
        runtime.kernel.dispatch(state, AdvanceTimeIntent(minutes=60, activity_type=RestActivityType.LIGHT_ACTIVITY))

        self.assertEqual(actor.capabilities['test-item-charge'].remaining_uses, 1)


if __name__ == '__main__':
    unittest.main()
