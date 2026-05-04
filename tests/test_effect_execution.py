from __future__ import annotations

import copy
import unittest

from player_interface import EncounterSlashCommandInterface
from shared_types.capabilities import AttackBonusSource, AttackExecutionKind, AttackRollGateEffect, CapabilityDefinition, CapabilityKind, ConditionEffectDef, DamageEffectDef, TargetAffinity, TargetSelectionKind, TargetingSpec
from shared_types.conditions import ConditionType
from shared_types.encounter_events import ActiveEffectEndedEvent, ActiveEffectStartedEvent, AreaResolvedEvent, ArmorClassAdjustedEvent, AttackRollRequestedEvent, CapabilityDeclaredEvent, DamageAppliedEvent, TargetsResolvedEvent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement, RuntimeSpellState
from shared_types.models import slugify
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from session_server.bootstrap import build_default_character_record
from tests.test_encounter_kernel import EncounterKernelTests, LOCAL_MIRROR_BASE_URL


class EffectExecutionTests(unittest.TestCase):
    def _helper(self) -> EncounterKernelTests:
        helper = EncounterKernelTests()
        helper.setUp = lambda: None
        return helper

    def _build_state(
        self,
        *,
        player_position=GridPosition(0, 0),
        skeleton_position=GridPosition(6, 0),
        mage_position=GridPosition(8, 2),
        battlefield=None,
    ):
        helper = self._helper()
        runtime = helper._build_runtime()
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        skeleton_id = helper._monster_id(runtime, name='Skeleton', source='XMM')
        mage_id = helper._monster_id(runtime, name='Mage', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=player_position),),
            monsters=(
                MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=skeleton_position),
                MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=mage_position),
            ),
            battlefield=battlefield,
        )
        return runtime, state

    def _advance_to_actor(self, ui, state, actor_id: str):
        return self._helper()._advance_to_actor(ui, state, actor_id)

    def _grant_spell(self, runtime, state, actor_id: str, *, name: str, source: str = 'XPHB', uses: int | None = None) -> str:
        record = next(spell for spell in runtime.encounter_catalog.spells.values() if spell.name == name and spell.source == source)
        option_id = slugify(record.name)
        state.actors[actor_id].spells[option_id] = RuntimeSpellState(
            option_id=option_id,
            name=record.name,
            source=record.source,
            effect_type=record.effect_type,
            action_cost=record.action_cost,
            range_ft=record.range_ft,
            remaining_uses=uses,
            concentration=record.concentration,
            capability=record.capability,
        )
        return option_id

    def test_fire_bolt_attack_roll_spell_executes_through_generic_layer(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        spell_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Fire Bolt')
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        state, _ = ui.execute(state, f'/cast monster-mage-1 {spell_id} player-1')
        event_types = {type(event) for event in state.event_log}
        self.assertIn(CapabilityDeclaredEvent, event_types)
        self.assertIn(TargetsResolvedEvent, event_types)
        self.assertIn(AttackRollRequestedEvent, event_types)

    def test_magic_missile_auto_hits_without_attack_roll(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        spell_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Magic Missile')
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        start_hp = state.actors['player-1'].current_hit_points
        state, _ = ui.execute(state, f'/cast monster-mage-1 {spell_id} player-1')
        self.assertLess(state.actors['player-1'].current_hit_points, start_hp)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) for event in state.event_log))
        self.assertFalse(any(isinstance(event, AttackRollRequestedEvent) for event in state.event_log if getattr(event, 'capability_id', '') == 'magic-missile'))

    def test_generic_monster_action_capability_executes_attack_rider(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(1, 0, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        actor = state.actors['monster-skeleton-1']
        target = state.actors['player-1']
        state.random_counter = 1
        start_hp = target.current_hit_points
        capability = CapabilityDefinition(
            capability_id='bone-club',
            name='Bone Club',
            kind=CapabilityKind.MONSTER_ACTION,
            source='TEST',
            action_cost='action',
            targeting=TargetingSpec(
                selection_kind=TargetSelectionKind.CREATURE,
                range_ft=5,
                affinity=TargetAffinity.ENEMY,
                requires_target_to_be_seen=True,
            ),
            effect=AttackRollGateEffect(
                attack_kind=AttackExecutionKind.MELEE_WEAPON,
                attack_bonus_source=AttackBonusSource.FLAT,
                flat_attack_bonus=99,
                reach_ft=5,
                on_hit=(
                    DamageEffectDef(dice_count=1, die_faces=6, bonus=2, damage_type='bludgeoning'),
                    ConditionEffectDef(condition_type=ConditionType.PRONE, source_label='bone-club'),
                ),
            ),
        )
        events = runtime.kernel.effect_executor.execute_capability(state, actor=actor, capability=capability, target_id='player-1')
        for event in events:
            runtime.kernel._apply_event(state, event)
        self.assertLess(state.actors['player-1'].current_hit_points, start_hp)
        self.assertIn(ConditionType.PRONE, {instance.condition_type for instance in state.actors['player-1'].condition_instances})
        self.assertTrue(any(isinstance(event, CapabilityDeclaredEvent) and event.capability_id == 'bone-club' for event in events))
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) for event in events))

    def test_sacred_flame_save_negates_damage(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        spell_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Sacred Flame')
        state.actors['monster-mage-1'].spell_save_dc = 0
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        start_hp = state.actors['player-1'].current_hit_points
        state, _ = ui.execute(state, f'/cast monster-mage-1 {spell_id} player-1')
        self.assertEqual(state.actors['player-1'].current_hit_points, start_hp)

    def test_thunderwave_area_half_on_success_and_push_on_failure(self) -> None:
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        runtime, fail_state = self._build_state(
            player_position=GridPosition(9, 4, 10),
            skeleton_position=GridPosition(0, 0, 0),
            mage_position=GridPosition(9, 2, 0),
            battlefield=copy.deepcopy(battlefield),
        )
        fail_ui = EncounterSlashCommandInterface(runtime.kernel)
        spell_id = self._grant_spell(runtime, fail_state, 'monster-mage-1', name='Thunderwave')
        fail_state.actors['monster-mage-1'].spell_save_dc = 99
        fail_state, _ = fail_ui.execute(fail_state, '/encounter start')
        fail_state, _ = self._advance_to_actor(fail_ui, fail_state, 'monster-mage-1')
        fail_state, _ = fail_ui.execute(fail_state, f'/cast monster-mage-1 {spell_id} 9 3 0')
        self.assertEqual(fail_state.actors['player-1'].position, GridPosition(9, 6, 10))
        self.assertTrue(any(isinstance(event, AreaResolvedEvent) for event in fail_state.event_log))

        runtime_two, success_state = self._build_state(
            player_position=GridPosition(9, 4, 10),
            skeleton_position=GridPosition(0, 0, 0),
            mage_position=GridPosition(9, 2, 0),
            battlefield=copy.deepcopy(battlefield),
        )
        success_ui = EncounterSlashCommandInterface(runtime_two.kernel)
        spell_id_two = self._grant_spell(runtime_two, success_state, 'monster-mage-1', name='Thunderwave')
        success_state.actors['monster-mage-1'].spell_save_dc = 0
        success_state, _ = success_ui.execute(success_state, '/encounter start')
        success_state, _ = self._advance_to_actor(success_ui, success_state, 'monster-mage-1')
        start_hp = success_state.actors['player-1'].current_hit_points
        success_state, _ = success_ui.execute(success_state, f'/cast monster-mage-1 {spell_id_two} 9 3 0')
        self.assertEqual(success_state.actors['player-1'].position, GridPosition(9, 4, 10))
        self.assertLess(success_state.actors['player-1'].current_hit_points, start_hp)

    def test_hold_person_repeats_save_at_end_of_turn(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        spell_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Hold Person')
        state.actors['monster-mage-1'].spell_save_dc = 99
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        state, _ = ui.execute(state, f'/cast monster-mage-1 {spell_id} player-1')
        self.assertTrue(any(instance.condition_type == ConditionType.PARALYZED for instance in state.actors['player-1'].condition_instances))
        self.assertTrue(state.active_effects)
        state.actors['monster-mage-1'].spell_save_dc = 0
        state, _ = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/endturn player-1')
        self.assertFalse(any(instance.condition_type == ConditionType.PARALYZED for instance in state.actors['player-1'].condition_instances))
        self.assertFalse(state.active_effects)
        self.assertTrue(any(isinstance(event, ActiveEffectEndedEvent) for event in state.event_log))

    def test_concentration_replacement_ends_previous_effect(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        hold_person_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Hold Person')
        shield_of_faith_id = self._grant_spell(runtime, state, 'monster-mage-1', name='Shield of Faith')
        state.actors['monster-mage-1'].spell_save_dc = 99
        state, _ = ui.execute(state, '/encounter start')
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        state, _ = ui.execute(state, f'/cast monster-mage-1 {hold_person_id} player-1')
        first_effect_id = state.actors['monster-mage-1'].concentrating_effect_id
        self.assertIsNotNone(first_effect_id)
        state, _ = ui.execute(state, f'/cast monster-mage-1 {shield_of_faith_id} monster-mage-1')
        self.assertNotEqual(first_effect_id, state.actors['monster-mage-1'].concentrating_effect_id)
        self.assertFalse(any(instance.condition_type == ConditionType.PARALYZED for instance in state.actors['player-1'].condition_instances))
        self.assertEqual(state.actors['monster-mage-1'].armor_class_modifier, 2)
        self.assertTrue(any(isinstance(event, ArmorClassAdjustedEvent) and event.delta == 2 for event in state.event_log))

    def test_shield_expires_on_start_of_next_turn(self) -> None:
        runtime, state = self._build_state(player_position=GridPosition(9, 9, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(1, 0, 0))
        state.actors['monster-mage-1'].side = state.actors['monster-skeleton-1'].side
        state.actors['monster-mage-1'].side = state.actors['player-1'].side
        state.actors['monster-mage-1'].armor_class = 10
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state, _ = ui.execute(state, '/attack monster-skeleton-1 shortsword monster-mage-1')
        option_id = next(option.option_id for option in state.pending_reaction_window.options if option.actor_id == 'monster-mage-1')
        state, _ = ui.execute(state, f'/react monster-mage-1 {option_id}')
        self.assertEqual(state.actors['monster-mage-1'].armor_class_modifier, 5)
        state, _ = self._advance_to_actor(ui, state, 'monster-mage-1')
        self.assertEqual(state.actors['monster-mage-1'].armor_class_modifier, 0)
        self.assertFalse(state.active_effects)

    def test_spell_execution_is_deterministic_for_same_seed(self) -> None:
        runtime_one, state_one = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        runtime_two, state_two = self._build_state(player_position=GridPosition(12, 2, 0), skeleton_position=GridPosition(0, 0, 0), mage_position=GridPosition(8, 2, 0))
        ui_one = EncounterSlashCommandInterface(runtime_one.kernel)
        ui_two = EncounterSlashCommandInterface(runtime_two.kernel)
        spell_id_one = self._grant_spell(runtime_one, state_one, 'monster-mage-1', name='Fire Bolt')
        spell_id_two = self._grant_spell(runtime_two, state_two, 'monster-mage-1', name='Fire Bolt')
        state_one, _ = ui_one.execute(state_one, '/encounter start')
        state_two, _ = ui_two.execute(state_two, '/encounter start')
        state_one, _ = self._advance_to_actor(ui_one, state_one, 'monster-mage-1')
        state_two, _ = self._advance_to_actor(ui_two, state_two, 'monster-mage-1')
        state_one, out_one = ui_one.execute(state_one, f'/cast monster-mage-1 {spell_id_one} player-1')
        state_two, out_two = ui_two.execute(state_two, f'/cast monster-mage-1 {spell_id_two} player-1')
        self.assertEqual(out_one, out_two)
        self.assertEqual(state_one.event_log, state_two.event_log)


if __name__ == '__main__':
    unittest.main()
