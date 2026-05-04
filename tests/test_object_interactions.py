from __future__ import annotations

import copy
import unittest

from encounter_runtime import build_default_encounter_runtime
from encounter_runtime.equipment import refresh_actor_equipment_state
from player_interface import EncounterSlashCommandInterface
from rules_engine.encounter_math import ability_modifier
from session_server.bootstrap import build_default_character_record
from session_server.encounter_session import EncounterSession
from session_server.web_projection import project_encounter_session_view
from shared_types.battlefield import BattlefieldFeature, BattlefieldGridSpec, BattlefieldState, BattlefieldTile, CoverLevel, LightingLevel, ObscurementLevel, TraversalMode
from shared_types.encounter_control import ControllerBinding, ControllerRole
from shared_types.encounter_events import (
    AmmunitionConsumedEvent,
    ArmorDoffedEvent,
    ArmorDonnedEvent,
    AttackRolledEvent,
    ConditionAddedEvent,
    EnvironmentObjectUsedEvent,
    GroundItemCreatedEvent,
    GroundItemRemovedEvent,
    ImprovisedWeaponUsedEvent,
    ItemPickedUpEvent,
    ObjectInteractionUsedEvent,
    ShieldDoffedEvent,
    ShieldDonnedEvent,
    UtilizeActionUsedEvent,
)
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.conditions import ConditionType
from shared_types.equipment import EnvironmentObjectAction, EnvironmentObjectState
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class ObjectInteractionSubsystemTests(unittest.TestCase):
    def _build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str, source: str) -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _custom_record(
        self,
        *,
        record_id: str,
        class_id: str,
        ability_scores: dict[Ability, int],
        max_hit_points: int,
        inventory: dict[str, int],
        class_skills: tuple[str, ...] = ('Athletics',),
        background_skills: tuple[str, ...] = (),
        saving_throw_proficiencies: tuple[Ability, ...] = (Ability.STR, Ability.CON),
        armor_training: tuple[str, ...] = ('light', 'medium', 'heavy', 'shield'),
        weapon_proficiencies: tuple[str, ...] = ('simple weapons', 'martial weapons'),
    ):
        record = copy.deepcopy(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL))
        record.record_id = record_id
        record.class_id = class_id
        record.level = 1
        record.max_hit_points = max_hit_points
        record.proficiency_bonus = 2
        record.ability_scores = dict(ability_scores)
        record.ability_modifiers = {ability: ability_modifier(score) for ability, score in ability_scores.items()}
        record.class_skill_proficiencies = class_skills
        record.background_skill_proficiencies = background_skills
        record.saving_throw_proficiencies = saving_throw_proficiencies
        record.armor_training = armor_training
        record.weapon_proficiencies = weapon_proficiencies
        record.inventory = dict(inventory)
        return record

    def _fighter_record(self, *, record_id: str = 'fighter-object-test', inventory: dict[str, int]):
        return self._custom_record(
            record_id=record_id,
            class_id='fighter',
            ability_scores={
                Ability.STR: 16,
                Ability.DEX: 14,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 12,
                Ability.CHA: 8,
            },
            max_hit_points=12,
            inventory=inventory,
        )

    def _build_state(
        self,
        *,
        player_record,
        player_position: GridPosition = GridPosition(0, 0, 0),
        monster_position: GridPosition = GridPosition(1, 0, 0),
        battlefield: BattlefieldState | None = None,
    ):
        runtime = self._build_runtime()
        monster_id = self._monster_id(runtime, name='Skeleton', source='XMM')
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=player_record, position=player_position),),
            monsters=(MonsterPlacement(actor_id='monster-1', monster_id=monster_id, position=monster_position),),
            battlefield=battlefield,
        )
        return runtime, state

    def _advance_to_actor(self, ui: EncounterSlashCommandInterface, state, actor_id: str):
        guard = 0
        while state.active_actor_id != actor_id:
            guard += 1
            if guard > 10:
                raise AssertionError(f'Could not reach actor turn: {actor_id}')
            state, _ = ui.execute(state, f'/endturn {state.active_actor_id}')
        return state

    def _build_control_runtime(self, runtime):
        controllers = {
            'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
            'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
        }
        actor_controllers = {
            'player-1': 'player-1-controller',
            'monster-1': 'dm',
        }
        return runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)

    def _build_projection_session(self, runtime, state):
        return EncounterSession(
            state=state,
            control_runtime=self._build_control_runtime(runtime),
            command_interface=EncounterSlashCommandInterface(runtime.kernel),
        )

    def _clear_default_equipment(self, runtime, state, *, actor_id: str = 'player-1'):
        actor = state.actors[actor_id]
        actor.main_hand_item_id = None
        actor.off_hand_item_id = None
        actor.equipped_armor_item_id = None
        actor.held_item_ids = ()
        actor.worn_armor_item_id = None
        actor.worn_shield_item_id = None
        refresh_actor_equipment_state(actor, runtime.monster_runtime.character_catalog.items, unarmed_attack=actor.attacks['unarmed-strike'])

    def _build_door_battlefield(self) -> BattlefieldState:
        def _tile(x: int) -> BattlefieldTile:
            return BattlefieldTile(
                position=GridPosition(x, 0),
                terrain_id='stone-floor',
                elevation_ft=0,
                ceiling_ft=20,
                traversable=True,
                occupiable=True,
                movement_cost_feet_per_5ft=5,
                difficult_terrain=False,
                lightly_obscured=False,
                lighting=LightingLevel.BRIGHT,
                obscurement=ObscurementLevel.NONE,
                blocks_los=False,
                blocks_loe=False,
                base_cover=CoverLevel.NONE,
                supported_modes=(TraversalMode.WALK, TraversalMode.CLIMB, TraversalMode.FLY),
            )

        tiles = {
            GridPosition(0, 0): _tile(0),
            GridPosition(1, 0): _tile(1),
            GridPosition(2, 0): _tile(2),
        }
        return BattlefieldState(
            map_id='door-test',
            name='Door Test',
            grid=BattlefieldGridSpec(
                cell_size_feet=5,
                width=3,
                height=1,
                origin='top-left',
                coordinates='xy',
                min_x=0,
                min_y=0,
                max_x=2,
                max_y=0,
            ),
            tiles=dict(tiles),
            base_tiles=dict(tiles),
            features={
                'door-feature': BattlefieldFeature(
                    feature_id='door-feature',
                    feature_type='door',
                    cells=(GridPosition(1, 0, 0),),
                    elevation_ft=0,
                    traversable=False,
                    occupiable=False,
                    blocks_los=True,
                    blocks_loe=True,
                    cover_provided=CoverLevel.HALF,
                )
            },
            object_ids=('door-feature',),
            blocker_ids=('door-feature',),
        )

    def test_one_free_object_interaction_per_turn_and_second_requires_utilize(self) -> None:
        record = self._fighter_record(inventory={'dagger': 1, 'club': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/interact player-1 draw dagger')
        actor = state.actors['player-1']
        self.assertEqual(actor.held_item_ids, ('dagger',))
        self.assertFalse(actor.remaining_free_object_interaction)
        self.assertTrue(any(isinstance(event, ObjectInteractionUsedEvent) for event in state.event_log))

        with self.assertRaisesRegex(EncounterValidationError, 'already used its free object interaction'):
            ui.execute(state, '/interact player-1 draw club')

        state, _ = ui.execute(state, '/utilize player-1 draw club')
        actor = state.actors['player-1']
        self.assertCountEqual(actor.held_item_ids, ('dagger', 'club'))
        self.assertFalse(actor.action_available)
        self.assertTrue(any(isinstance(event, UtilizeActionUsedEvent) for event in state.event_log))

        state, _ = ui.execute(state, '/endturn player-1')
        state, _ = ui.execute(state, '/endturn monster-1')
        self.assertEqual(state.active_actor_id, 'player-1')
        self.assertTrue(state.actors['player-1'].remaining_free_object_interaction)

    def test_attack_action_supports_before_draw_without_spending_free_object_interaction(self) -> None:
        record = self._fighter_record(inventory={'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/attack player-1 dagger-melee-dex monster-1 --before draw:dagger')
        actor = state.actors['player-1']
        self.assertEqual(actor.held_item_ids, ('dagger',))
        self.assertTrue(actor.remaining_free_object_interaction)

    def test_attack_action_supports_after_stow_even_after_free_interaction_was_used(self) -> None:
        record = self._fighter_record(inventory={'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/interact player-1 draw dagger')
        self.assertFalse(state.actors['player-1'].remaining_free_object_interaction)
        state, _ = ui.execute(state, '/attack player-1 dagger-melee-dex monster-1 --after stow:dagger')
        actor = state.actors['player-1']
        self.assertEqual(actor.held_item_ids, ())
        self.assertFalse(actor.remaining_free_object_interaction)

    def test_shield_don_and_doff_require_utilize_and_update_armor_class(self) -> None:
        record = self._fighter_record(inventory={'shield': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        with self.assertRaisesRegex(EncounterValidationError, 'require the Utilize action'):
            ui.execute(state, '/interact player-1 don-shield shield')

        start_ac = state.actors['player-1'].effective_armor_class
        state, _ = ui.execute(state, '/utilize player-1 don-shield shield')
        actor = state.actors['player-1']
        self.assertEqual(actor.worn_shield_item_id, 'shield')
        self.assertEqual(actor.effective_armor_class, start_ac + 2)
        self.assertTrue(any(isinstance(event, ShieldDonnedEvent) for event in state.event_log))

        state, _ = ui.execute(state, '/endturn player-1')
        state, _ = ui.execute(state, '/endturn monster-1')
        state, _ = ui.execute(state, '/utilize player-1 doff-shield shield')
        actor = state.actors['player-1']
        self.assertIsNone(actor.worn_shield_item_id)
        self.assertEqual(actor.effective_armor_class, start_ac)
        self.assertTrue(any(isinstance(event, ShieldDoffedEvent) for event in state.event_log))

    def test_armor_don_and_doff_time_advances_clock_and_combat_don_is_illegal(self) -> None:
        record = self._fighter_record(inventory={'chain-mail': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/utilize player-1 don-armor chain-mail')
        actor = state.actors['player-1']
        self.assertEqual(actor.worn_armor_item_id, 'chain-mail')
        self.assertEqual(actor.effective_armor_class, 16)
        self.assertEqual(state.clock_seconds, 600)
        self.assertTrue(any(isinstance(event, ArmorDonnedEvent) for event in state.event_log))

        state, _ = ui.execute(state, '/utilize player-1 doff-armor chain-mail')
        actor = state.actors['player-1']
        self.assertIsNone(actor.worn_armor_item_id)
        self.assertEqual(state.clock_seconds, 900)
        self.assertTrue(any(isinstance(event, ArmorDoffedEvent) for event in state.event_log))

        combat_runtime, combat_state = self._build_state(player_record=record)
        combat_ui = EncounterSlashCommandInterface(combat_runtime.kernel)
        combat_state, _ = combat_ui.execute(combat_state, '/encounter start')
        combat_state = self._advance_to_actor(combat_ui, combat_state, 'player-1')
        self._clear_default_equipment(combat_runtime, combat_state)
        with self.assertRaisesRegex(EncounterValidationError, 'too long for this in-combat deterministic slice'):
            combat_ui.execute(combat_state, '/utilize player-1 don-armor chain-mail')

    def test_default_equipment_slots_apply_to_armor_class(self) -> None:
        record = self._fighter_record(inventory={'chain-mail': 1, 'shield': 1, 'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        actor = state.actors['player-1']
        self.assertEqual(actor.main_hand_item_id, 'dagger')
        self.assertEqual(actor.off_hand_item_id, 'shield')
        self.assertEqual(actor.equipped_armor_item_id, 'chain-mail')
        self.assertEqual(actor.effective_armor_class, 18)

    def test_equip_command_assigns_slots_without_spending_action_for_weapons(self) -> None:
        record = self._fighter_record(inventory={'chain-mail': 1, 'shield': 1, 'dagger': 1, 'club': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/equip player-1 chain-mail armor')
        state, _ = ui.execute(state, '/equip player-1 club main-hand')
        state, _ = ui.execute(state, '/equip player-1 shield off-hand')
        actor = state.actors['player-1']
        self.assertEqual(actor.equipped_armor_item_id, 'chain-mail')
        self.assertEqual(actor.main_hand_item_id, 'club')
        self.assertEqual(actor.off_hand_item_id, 'shield')
        self.assertEqual(actor.effective_armor_class, 18)
        self.assertTrue(actor.action_available)
        self.assertTrue(actor.remaining_free_object_interaction)

    def test_long_rest_start_clears_equipped_slots(self) -> None:
        record = self._fighter_record(inventory={'chain-mail': 1, 'shield': 1, 'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)

        state, _ = ui.execute(state, '/longrest player-1')
        actor = state.actors['player-1']
        self.assertIsNone(actor.main_hand_item_id)
        self.assertIsNone(actor.off_hand_item_id)
        self.assertIsNone(actor.equipped_armor_item_id)
        self.assertEqual(actor.effective_armor_class, 12)

    def test_ammunition_consumption_and_loading_limit(self) -> None:
        record = self._fighter_record(inventory={'light-crossbow': 1, 'bolt': 5})
        runtime, state = self._build_state(player_record=record, monster_position=GridPosition(3, 0, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)
        state, _ = ui.execute(state, '/interact player-1 draw light-crossbow')

        state, _ = ui.execute(state, '/attack player-1 light-crossbow-ranged monster-1')
        actor = state.actors['player-1']
        self.assertEqual(actor.carried_item_counts['bolt'], 4)
        self.assertIn('action', actor.loading_spent_resources)
        self.assertTrue(any(isinstance(event, AmmunitionConsumedEvent) for event in state.event_log))

        actor.action_available = True
        with self.assertRaisesRegex(EncounterValidationError, 'already been fired with this resource'):
            ui.execute(state, '/attack player-1 light-crossbow-ranged monster-1')

    def test_thrown_weapon_creates_ground_item_and_pickup_uses_interaction_system(self) -> None:
        record = self._fighter_record(inventory={'dagger': 2})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/attack player-1 dagger-thrown-str monster-1 --before draw:dagger')
        actor = state.actors['player-1']
        self.assertEqual(actor.carried_item_counts['dagger'], 1)
        self.assertEqual(actor.held_item_ids, ())
        self.assertEqual(len(state.ground_items), 1)
        ground_item_id = next(iter(state.ground_items))
        ground_item = state.ground_items[ground_item_id]
        self.assertEqual(ground_item.item_id, 'dagger')
        self.assertEqual(ground_item.position, state.actors['monster-1'].position)
        self.assertTrue(any(isinstance(event, GroundItemCreatedEvent) for event in state.event_log))

        state, _ = ui.execute(state, f'/interact player-1 pickup {ground_item_id}')
        actor = state.actors['player-1']
        self.assertEqual(actor.carried_item_counts['dagger'], 2)
        self.assertEqual(actor.held_item_ids, ('dagger',))
        self.assertNotIn(ground_item_id, state.ground_items)
        self.assertTrue(any(isinstance(event, ItemPickedUpEvent) for event in state.event_log))
        self.assertTrue(any(isinstance(event, GroundItemRemovedEvent) for event in state.event_log))

    def test_improvised_weapon_defaults_to_d4_without_weapon_proficiency_bonus(self) -> None:
        record = self._fighter_record(inventory={'club': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)
        state, _ = ui.execute(state, '/interact player-1 draw club')

        state, _ = ui.execute(state, '/improvise player-1 monster-1 item:club')
        rolled_event = next(event for event in reversed(state.event_log) if isinstance(event, AttackRolledEvent))
        self.assertEqual(rolled_event.attack_total - rolled_event.attack_rolls[0], state.actors['player-1'].ability_modifiers[Ability.STR])
        self.assertTrue(any(isinstance(event, ImprovisedWeaponUsedEvent) for event in state.event_log))

    def test_snapshot_hides_stowed_weapon_attacks_until_weapon_is_held(self) -> None:
        record = self._fighter_record(inventory={'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        snapshot = runtime.kernel.snapshot(state)
        attack_ids = {choice.option_id for choice in snapshot.available_choices.get('attacks', ())}
        self.assertIn('unarmed-strike', attack_ids)
        self.assertNotIn('dagger-melee-dex', attack_ids)

        state, _ = ui.execute(state, '/interact player-1 draw dagger')
        snapshot = runtime.kernel.snapshot(state)
        attack_ids = {choice.option_id for choice in snapshot.available_choices.get('attacks', ())}
        self.assertIn('dagger-melee-dex', attack_ids)

    def test_shield_blocks_two_handed_versatile_attack(self) -> None:
        record = self._fighter_record(inventory={'quarterstaff': 1, 'shield': 1})
        runtime, state = self._build_state(player_record=record)
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        self._clear_default_equipment(runtime, state)

        state, _ = ui.execute(state, '/utilize player-1 don-shield shield')
        state, _ = ui.execute(state, '/endturn player-1')
        state, _ = ui.execute(state, '/endturn monster-1')
        state, _ = ui.execute(state, '/interact player-1 draw quarterstaff')

        with self.assertRaisesRegex(EncounterValidationError, 'required free hands'):
            ui.execute(state, '/attack player-1 quarterstaff-versatile-str monster-1')

    def test_unconscious_condition_drops_held_items_to_ground(self) -> None:
        record = self._fighter_record(inventory={'dagger': 1})
        runtime, state = self._build_state(player_record=record)
        actor = state.actors['player-1']
        self._clear_default_equipment(runtime, state)
        actor.main_hand_item_id = 'dagger'
        refresh_actor_equipment_state(actor, runtime.monster_runtime.character_catalog.items, unarmed_attack=actor.attacks['unarmed-strike'])

        runtime.kernel._apply_event(
            state,
            ConditionAddedEvent(
                actor_id='player-1',
                instance=runtime.kernel._make_condition_instance(target_actor_id='player-1', condition_type=ConditionType.UNCONSCIOUS, source_label='test-unconscious'),
            ),
        )

        self.assertEqual(state.actors['player-1'].held_item_ids, ())
        self.assertEqual(state.actors['player-1'].carried_item_counts.get('dagger', 0), 0)
        self.assertEqual(len(state.ground_items), 1)
        ground_item = next(iter(state.ground_items.values()))
        self.assertEqual(ground_item.item_id, 'dagger')
        self.assertEqual(ground_item.position, state.actors['player-1'].position)

    def test_environment_object_use_in_combat_runs_through_utilize(self) -> None:
        battlefield = self._build_door_battlefield()
        record = self._fighter_record(inventory={'dagger': 1})
        runtime, state = self._build_state(
            player_record=record,
            player_position=GridPosition(0, 0, 0),
            monster_position=GridPosition(2, 0, 0),
            battlefield=battlefield,
        )
        state.environment_objects['door-1'] = EnvironmentObjectState(
            object_id='door-1',
            feature_id='door-feature',
            label='Stone Door',
            allowed_actions=(EnvironmentObjectAction.OPEN, EnvironmentObjectAction.CLOSE),
            position_cells=(GridPosition(1, 0, 0),),
            open_state=False,
            closed_traversable=False,
            open_traversable=True,
            closed_occupiable=False,
            open_occupiable=True,
            closed_blocks_los=True,
            open_blocks_los=False,
            closed_blocks_loe=True,
            open_blocks_loe=False,
            closed_cover_provided=CoverLevel.HALF,
            open_cover_provided=CoverLevel.NONE,
        )
        runtime.kernel._apply_environment_object_projection(state, 'door-1')
        self.assertFalse(state.battlefield.tiles[GridPosition(1, 0)].traversable)

        ui = EncounterSlashCommandInterface(runtime.kernel)
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/utilize player-1 open door-1')
        actor = state.actors['player-1']
        self.assertFalse(actor.action_available)
        self.assertTrue(state.environment_objects['door-1'].open_state)
        self.assertTrue(state.battlefield.tiles[GridPosition(1, 0)].traversable)
        self.assertTrue(any(isinstance(event, EnvironmentObjectUsedEvent) for event in state.event_log))

    def test_projection_includes_equipment_state_and_free_object_interaction(self) -> None:
        record = self._fighter_record(inventory={'dagger': 2, 'shield': 1})
        runtime, state = self._build_state(player_record=record)
        actor = state.actors['player-1']
        actor.main_hand_item_id = 'dagger'
        actor.off_hand_item_id = 'shield'
        actor.remaining_free_object_interaction = False
        refresh_actor_equipment_state(actor, runtime.monster_runtime.character_catalog.items, unarmed_attack=actor.attacks['unarmed-strike'])

        session = self._build_projection_session(runtime, state)
        view = project_encounter_session_view(session, 'player-1-controller', session_id='object-test')
        self.assertEqual(len(view.character_cards), 1)
        card = view.character_cards[0]
        self.assertFalse(card.free_object_interaction_available)
        self.assertTrue(any(resource.label == 'Free Object Interaction' and resource.remaining_uses == 0 for resource in card.resources))
        self.assertEqual(card.main_hand_label, 'Dagger')
        self.assertEqual(card.off_hand_label, 'Shield')
        self.assertTrue(any(item.label == 'Dagger' and item.state_label is not None and 'main hand' in item.state_label and 'stowed 1' in item.state_label for item in card.items))
        self.assertTrue(any(item.label == 'Shield' and item.state_label is not None and 'off hand' in item.state_label for item in card.items))


if __name__ == '__main__':
    unittest.main()
