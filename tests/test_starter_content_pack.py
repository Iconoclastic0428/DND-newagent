from __future__ import annotations

import copy
import unittest

from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface
from rules_engine.battlefield_loader import DEFAULT_GOBLIN_AMBUSH_MAP_PATH, load_battlefield_state_from_json
from rules_engine.encounter_math import ability_modifier
from session_server.bootstrap import build_default_character_record
from shared_types.conditions import ConditionType
from shared_types.encounter_events import CapabilityRechargeRolledEvent, DamageAppliedEvent, HazardTriggeredEvent, TerrainEffectCreatedEvent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement, RuntimeSpellState
from shared_types.models import ABILITY_ORDER, Ability, slugify
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class StarterContentPackTests(unittest.TestCase):
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
        class_skills: tuple[str, ...] = (),
        background_skills: tuple[str, ...] = (),
        saving_throw_proficiencies: tuple[Ability, ...] = (),
        inventory: dict[str, int] | None = None,
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
        record.inventory = dict(inventory or {})
        return record

    def _build_state(self, *, player_record, player_position=GridPosition(0, 0, 0), monster_name='Skeleton', monster_source='XMM', monster_actor_id='monster-1', monster_position=GridPosition(6, 0, 0), battlefield=None):
        runtime = self._build_runtime()
        monster_id = self._monster_id(runtime, name=monster_name, source=monster_source)
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=player_record, position=player_position),),
            monsters=(MonsterPlacement(actor_id=monster_actor_id, monster_id=monster_id, position=monster_position),),
            battlefield=battlefield,
        )
        return runtime, state

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

    def _advance_to_actor(self, ui, state, actor_id: str):
        guard = 0
        while state.active_actor_id != actor_id:
            guard += 1
            if guard > 20:
                raise AssertionError(f'Could not advance to actor {actor_id}')
            state, _ = ui.execute(state, f'/endturn {state.active_actor_id}')
        return state

    def test_second_wind_uses_bonus_action_and_heals(self) -> None:
        record = self._custom_record(
            record_id='fighter-test',
            class_id='fighter',
            ability_scores={
                Ability.STR: 16,
                Ability.DEX: 12,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 12,
                Ability.CHA: 8,
            },
            max_hit_points=12,
            class_skills=('Athletics',),
            saving_throw_proficiencies=(Ability.STR, Ability.CON),
        )
        runtime, state = self._build_state(player_record=record, player_position=GridPosition(0, 0, 0), monster_position=GridPosition(10, 0, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state.actors['player-1'].current_hit_points = 4
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        start_hp = state.actors['player-1'].current_hit_points
        state, _ = ui.execute(state, '/feature player-1 second-wind')
        self.assertGreater(state.actors['player-1'].current_hit_points, start_hp)
        self.assertFalse(state.actors['player-1'].bonus_action_available)
        self.assertEqual(state.actors['player-1'].capabilities['second-wind'].remaining_uses, 1)

    def test_rage_applies_resistances_and_blocks_spellcasting(self) -> None:
        record = self._custom_record(
            record_id='barbarian-test',
            class_id='barbarian',
            ability_scores={
                Ability.STR: 16,
                Ability.DEX: 14,
                Ability.CON: 16,
                Ability.INT: 8,
                Ability.WIS: 12,
                Ability.CHA: 10,
            },
            max_hit_points=14,
            class_skills=('Athletics',),
            saving_throw_proficiencies=(Ability.STR, Ability.CON),
        )
        runtime, state = self._build_state(player_record=record, player_position=GridPosition(0, 0, 0), monster_position=GridPosition(10, 0, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        misty_step_id = self._grant_spell(runtime, state, 'player-1', name='Misty Step')
        state.actors['player-1'].spellcasting_ability = Ability.CHA
        state.actors['player-1'].spell_attack_bonus = 4
        state.actors['player-1'].spell_save_dc = 12
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/feature player-1 rage')
        player = state.actors['player-1']
        self.assertIn('bludgeoning', player.damage_resistances)
        self.assertTrue(player.cannot_cast_spells)
        self.assertIn(Ability.STR, player.ability_check_advantage_abilities)
        self.assertIn(Ability.STR, player.saving_throw_advantage_abilities)
        with self.assertRaisesRegex(Exception, 'cannot cast spells'):
            ui.execute(state, f'/cast player-1 {misty_step_id} 1 0 0')

    def test_thaumaturge_adds_wisdom_modifier_to_arcana_and_religion(self) -> None:
        record = self._custom_record(
            record_id='cleric-test',
            class_id='cleric',
            ability_scores={
                Ability.STR: 10,
                Ability.DEX: 12,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 16,
                Ability.CHA: 12,
            },
            max_hit_points=10,
            class_skills=('Insight',),
            background_skills=('Medicine',),
            saving_throw_proficiencies=(Ability.WIS, Ability.CHA),
        )
        runtime, state = self._build_state(player_record=record)
        actor = state.actors['player-1']
        self.assertEqual(actor.skill_bonuses['Arcana'], 3)
        self.assertEqual(actor.skill_bonuses['Religion'], 3)

    def test_healing_word_and_cure_wounds_use_starter_spell_mapping(self) -> None:
        record = self._custom_record(
            record_id='healer-test',
            class_id='cleric',
            ability_scores={
                Ability.STR: 10,
                Ability.DEX: 12,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 16,
                Ability.CHA: 12,
            },
            max_hit_points=10,
            class_skills=('Insight',),
            saving_throw_proficiencies=(Ability.WIS, Ability.CHA),
        )
        runtime, state = self._build_state(player_record=record, monster_position=GridPosition(20, 0, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        healing_word_id = self._grant_spell(runtime, state, 'player-1', name='Healing Word')
        cure_wounds_id = self._grant_spell(runtime, state, 'player-1', name='Cure Wounds')
        actor = state.actors['player-1']
        actor.spellcasting_ability = Ability.WIS
        actor.current_hit_points = 2
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, f'/cast player-1 {healing_word_id} player-1')
        after_healing_word = state.actors['player-1'].current_hit_points
        self.assertGreater(after_healing_word, 2)
        self.assertFalse(state.actors['player-1'].bonus_action_available)
        state.actors['player-1'].action_available = True
        state.actors['player-1'].current_hit_points = 2
        state, _ = ui.execute(state, f'/cast player-1 {cure_wounds_id} player-1')
        self.assertGreater(state.actors['player-1'].current_hit_points, 2)
        self.assertFalse(state.actors['player-1'].action_available)

    def test_potion_of_healing_and_acid_use_item_capabilities(self) -> None:
        record = self._custom_record(
            record_id='item-test',
            class_id='fighter',
            ability_scores={
                Ability.STR: 14,
                Ability.DEX: 16,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 12,
                Ability.CHA: 8,
            },
            max_hit_points=12,
            class_skills=('Athletics',),
            saving_throw_proficiencies=(Ability.STR, Ability.CON),
            inventory={'potion-of-healing': 1, 'acid': 1},
        )
        runtime, state = self._build_state(player_record=record, player_position=GridPosition(0, 0, 0), monster_position=GridPosition(3, 0, 0))
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state.actors['player-1'].current_hit_points = 3
        state.actors['monster-1'].armor_class = 1
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/use player-1 potion-of-healing')
        self.assertGreater(state.actors['player-1'].current_hit_points, 3)
        self.assertEqual(state.actors['player-1'].capabilities['potion-of-healing'].remaining_uses, 0)
        state.actors['player-1'].bonus_action_available = True
        state.actors['player-1'].action_available = True
        state, _ = ui.execute(state, '/use player-1 acid monster-1')
        self.assertEqual(state.actors['player-1'].capabilities['acid'].remaining_uses, 0)
        self.assertTrue(any(isinstance(event, DamageAppliedEvent) and event.target_id == 'monster-1' for event in state.event_log))

    def test_ball_bearings_create_hazard_and_can_prone_on_entry(self) -> None:
        record = self._custom_record(
            record_id='hazard-test',
            class_id='fighter',
            ability_scores={
                Ability.STR: 14,
                Ability.DEX: 14,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 12,
                Ability.CHA: 8,
            },
            max_hit_points=12,
            class_skills=('Athletics',),
            saving_throw_proficiencies=(Ability.STR, Ability.CON),
            inventory={'ball-bearings': 1},
        )
        battlefield = load_battlefield_state_from_json(DEFAULT_GOBLIN_AMBUSH_MAP_PATH)
        runtime, state = self._build_state(
            player_record=record,
            player_position=GridPosition(15, 17, 0),
            monster_position=GridPosition(13, 17, 0),
            battlefield=battlefield,
        )
        ui = EncounterSlashCommandInterface(runtime.kernel)
        state.actors['monster-1'].saving_throw_bonuses[Ability.DEX] = -100
        state, _ = ui.execute(state, '/encounter start')
        state = self._advance_to_actor(ui, state, 'player-1')
        state, _ = ui.execute(state, '/use player-1 ball-bearings 15 16 0')
        self.assertTrue(any(isinstance(event, TerrainEffectCreatedEvent) and event.template_id == 'ball_bearings_patch' for event in state.event_log))
        state, _ = ui.execute(state, '/endturn player-1')
        state = self._advance_to_actor(ui, state, 'monster-1')
        state, _ = ui.execute(state, '/move monster-1 16 17 0')
        self.assertIn(ConditionType.PRONE, {instance.condition_type for instance in state.actors['monster-1'].condition_instances})
        self.assertTrue(any(isinstance(event, HazardTriggeredEvent) for event in state.event_log))

    def test_ghoul_claw_and_giant_spider_web_use_monster_capabilities(self) -> None:
        record = self._custom_record(
            record_id='victim-test',
            class_id='fighter',
            ability_scores={
                Ability.STR: 14,
                Ability.DEX: 12,
                Ability.CON: 12,
                Ability.INT: 10,
                Ability.WIS: 10,
                Ability.CHA: 8,
            },
            max_hit_points=12,
            class_skills=('Athletics',),
            saving_throw_proficiencies=(Ability.STR, Ability.CON),
        )
        runtime, ghoul_state = self._build_state(player_record=record, player_position=GridPosition(1, 0, 0), monster_name='Ghoul', monster_source='XMM', monster_actor_id='ghoul-1', monster_position=GridPosition(0, 0, 0))
        ghoul_ui = EncounterSlashCommandInterface(runtime.kernel)
        ghoul_state.actors['player-1'].armor_class = 1
        ghoul_state.actors['player-1'].saving_throw_bonuses[Ability.CON] = -100
        ghoul_state, _ = ghoul_ui.execute(ghoul_state, '/encounter start')
        ghoul_state = self._advance_to_actor(ghoul_ui, ghoul_state, 'ghoul-1')
        ghoul_state, _ = ghoul_ui.execute(ghoul_state, '/feature ghoul-1 ghoul-claw player-1')
        self.assertIn(ConditionType.PARALYZED, {instance.condition_type for instance in ghoul_state.actors['player-1'].condition_instances})

        runtime_two, spider_state = self._build_state(player_record=record, player_position=GridPosition(3, 0, 0), monster_name='Giant Spider', monster_source='XMM', monster_actor_id='spider-1', monster_position=GridPosition(0, 0, 0))
        spider_ui = EncounterSlashCommandInterface(runtime_two.kernel)
        spider_state.actors['player-1'].saving_throw_bonuses[Ability.DEX] = -100
        spider_state, _ = spider_ui.execute(spider_state, '/encounter start')
        spider_state = self._advance_to_actor(spider_ui, spider_state, 'spider-1')
        spider_state, _ = spider_ui.execute(spider_state, '/feature spider-1 giant-spider-web player-1')
        self.assertIn(ConditionType.RESTRAINED, {instance.condition_type for instance in spider_state.actors['player-1'].condition_instances})
        self.assertEqual(spider_state.actors['spider-1'].capabilities['giant-spider-web'].remaining_uses, 0)
        spider_state, _ = spider_ui.execute(spider_state, '/endturn spider-1')
        spider_state = self._advance_to_actor(spider_ui, spider_state, 'spider-1')
        self.assertTrue(any(isinstance(event, CapabilityRechargeRolledEvent) and event.actor_id == 'spider-1' for event in spider_state.event_log))


if __name__ == '__main__':
    unittest.main()
