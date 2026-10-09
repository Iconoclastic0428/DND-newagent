from __future__ import annotations

import unittest
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from campaign_ingestion.site_loader import load_campaign_site
from rules_engine.battlefield_loader import load_battlefield_state_from_json
from shared_types.encounter_models import GridPosition

ROOT = Path(__file__).resolve().parents[1]
SITE_PATH = ROOT / 'campaigns/lmop/sites/phandalin-redbrands.json'


class CampaignSiteAssetTests(unittest.TestCase):
    def test_connected_town_and_complete_hideout_contract(self):
        definition = load_campaign_site(SITE_PATH)
        self.assertEqual(definition.site_id, 'phandalin-redbrands')
        self.assertEqual(len(definition.places), 6)
        self.assertEqual(len(definition.rooms), 12)
        self.assertEqual(set(definition.entrances), {'manor', 'tunnel'})
        self.assertEqual(definition.entrances['tunnel'].required_flag, 'secret-tunnel-known')
        self.assertEqual(
            definition.places['alderleaf-farm'].conversations[0].grants,
            ('secret-tunnel-known', 'redbrand-base-known'),
        )
        self.assertEqual(definition.town_image, 'assets/maps/phandalin-player.webp')
        for encounter in definition.encounters.values():
            self.assertIn(encounter.room_id, definition.rooms)
            for monster in encounter.monsters:
                self.assertTrue(monster.monster_id)

    def test_hideout_image_grid_walls_and_continuous_entrance_paths(self):
        battlefield = load_battlefield_state_from_json(ROOT / 'data/maps/redbrand_hideout_map.json')
        image = battlefield.background_image
        self.assertEqual((image.width_px, image.height_px, image.grid_size_px), (4500, 3136, 150))
        self.assertEqual((image.grid_offset_x_px, image.grid_offset_y_px), (2, -7))
        self.assertEqual((battlefield.grid.width, battlefield.grid.height), (30, 21))
        self.assertFalse(battlefield.tiles[GridPosition(1, 5)].traversable)
        self.assertFalse(battlefield.tiles[GridPosition(24, 6)].traversable)
        for xy in (
            (27, 15),
            (27, 14),
            (27, 13),
            (26, 13),
            (25, 13),
            (25, 14),
            (24, 14),
            (23, 14),
            (10, 19),
            (10, 18),
            (10, 17),
            (10, 16),
        ):
            self.assertTrue(battlefield.base_tiles[GridPosition(*xy)].traversable, xy)
        self.assertEqual(battlefield.tiles[GridPosition(27, 15)].elevation_ft, 15)
        self.assertEqual(battlefield.tiles[GridPosition(11, 12)].elevation_ft, -20)
        self.assertEqual(battlefield.features['north-bridge'].elevation_ft, 0)
        self.assertEqual(battlefield.features['south-bridge'].elevation_ft, 0)

    def test_every_authored_room_and_spawn_is_on_valid_map_geometry(self):
        definition = load_campaign_site(SITE_PATH)
        battlefield = load_battlefield_state_from_json(ROOT / definition.battlefield_path)
        for room in definition.rooms.values():
            self.assertTrue(room.cells)
            for cell in room.cells:
                self.assertIn(cell.horizontal(), battlefield.tiles)
        for entrance in definition.entrances.values():
            self.assertEqual(len(entrance.positions), 4)
            for cell in entrance.positions:
                self.assertTrue(battlefield.tiles[cell.horizontal()].traversable, cell)
        for encounter in definition.encounters.values():
            for monster in encounter.monsters:
                self.assertTrue(battlefield.tiles[monster.position.horizontal()].occupiable, monster.actor_id)
        for door in definition.doors.values():
            self.assertIn(door.door_id, battlefield.features)

    def test_progression_prerequisites_and_story_presentation_are_authored(self):
        definition = load_campaign_site(SITE_PATH)
        self.assertEqual(definition.chapter_id, 'chapter-02')
        self.assertEqual(definition.doors['north-cell'].key_flag, 'master-key')
        self.assertEqual(
            set(definition.interactions['free-prisoners'].required_open_doors), {'north-cell', 'south-cell'}
        )
        self.assertEqual(definition.interactions['nothic-bargain'].required_living_encounter, 'nothic')
        self.assertTrue(definition.arrival_goals)


if __name__ == '__main__':
    unittest.main()


class SiteExplorationMovementTests(unittest.TestCase):
    def test_exploration_move_uses_real_speed_and_advances_time(self):
        from encounter_runtime.kernel import EncounterKernel
        from shared_types.encounter_intents import ExploreMoveIntent
        from shared_types.encounter_models import RuntimeActorState, ActorSide
        from shared_types.models import Ability

        kernel = EncounterKernel(seed='site-test')
        actor = RuntimeActorState(
            actor_id='p1',
            name='Scout',
            side=ActorSide.PLAYER,
            source_refs=(),
            size='M',
            alignment=None,
            creature_type='humanoid',
            armor_class=14,
            max_hit_points=20,
            current_hit_points=13,
            position=GridPosition(23, 14),
            speed_ft=30,
            climb_speed_ft=0,
            remaining_movement_ft=0,
            ability_modifiers={a: 0 for a in Ability},
            saving_throw_bonuses={a: 0 for a in Ability},
        )
        state = kernel.new_state(
            {'p1': actor},
            battlefield=load_battlefield_state_from_json(ROOT / 'data/maps/redbrand_hideout_map.json'),
        )
        kernel.dispatch(state, ExploreMoveIntent('p1', 24, 14))
        self.assertEqual(actor.position, GridPosition(24, 14))
        self.assertEqual(actor.current_hit_points, 13)
        self.assertEqual(actor.speed_ft, 30)
        self.assertEqual(state.clock_seconds, 6)
        kernel.dispatch(state, ExploreMoveIntent('p1', 23, 14))
        self.assertEqual(state.clock_seconds, 12)
        before = deepcopy(state)
        from shared_types.errors import EncounterValidationError

        with self.assertRaises(EncounterValidationError):
            kernel.dispatch(state, ExploreMoveIntent('p1', 1, 5))
        self.assertEqual(state, before)

    def test_exploration_move_is_rejected_during_combat(self):
        from encounter_runtime.kernel import EncounterKernel
        from shared_types.encounter_intents import ExploreMoveIntent
        from shared_types.encounter_models import EncounterState, EncounterPhase
        from shared_types.errors import EncounterValidationError

        state = EncounterState(phase=EncounterPhase.IN_PROGRESS)
        with self.assertRaisesRegex(EncounterValidationError, 'combat'):
            EncounterKernel(seed='site-test').dispatch(state, ExploreMoveIntent('p1', 0, 0))


class CampaignSiteRulesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from encounter_runtime import build_default_encounter_runtime
        from rules_engine.campaign_sites import CampaignSiteEngine

        cls.runtime = build_default_encounter_runtime(
            base_url=Path('D:/5etools-mirror-2.github.io').as_uri() + '/'
        )
        cls.engine = CampaignSiteEngine(
            load_campaign_site(SITE_PATH), kernel=cls.runtime.kernel, asset_root=ROOT
        )

    def setUp(self):
        from shared_types.encounter_models import RuntimeActorState, ActorSide
        from shared_types.models import Ability

        self.actor = RuntimeActorState(
            actor_id='p1',
            name='Scout',
            side=ActorSide.PLAYER,
            source_refs=(),
            size='M',
            alignment=None,
            creature_type='humanoid',
            armor_class=14,
            max_hit_points=20,
            current_hit_points=13,
            position=GridPosition(0, 0),
            speed_ft=30,
            climb_speed_ft=0,
            remaining_movement_ft=30,
            body_weight_lb=150,
            ability_modifiers={a: 0 for a in Ability},
            saving_throw_bonuses={a: 0 for a in Ability},
        )
        self.state = self.runtime.kernel.new_state({'p1': self.actor})
        self.site = self.engine.initial_state()

    def act(self, action, target=None, location='phandalin'):
        from shared_types.campaign_site import CampaignSiteIntent, SiteAction

        result = self.engine.resolve(
            self.state,
            self.site,
            CampaignSiteIntent('p1', SiteAction(action), target),
            party_actor_ids=('p1',),
            current_location_id=location,
        )
        self.state, self.site = result.encounter_state, result.site_state
        return result

    def arrive_and_enter(self, entrance='manor'):
        self.act('arrive')
        if entrance == 'tunnel':
            self.act('visit', 'alderleaf-farm')
            self.act('talk', 'carp-alderleaf')
        self.act('visit', 'tresendar-manor')
        self.act('talk', 'manor-tracks')
        self.act('enter', entrance)

    def test_arrival_requires_real_location_and_preserves_party(self):
        from shared_types.errors import EncounterValidationError

        before = deepcopy(self.state)
        with self.assertRaisesRegex(EncounterValidationError, 'arrival'):
            self.act('arrive', location='cragmaw-hideout')
        self.assertEqual(before, self.state)
        self.act('arrive')
        self.assertEqual(self.state.actors['p1'].current_hit_points, 13)
        self.assertTrue(self.site.progress.arrived)
        self.assertFalse(self.site.progress.in_dungeon)

    def test_authored_monsters_have_executable_attacks_and_caster_resources(self):
        self.arrive_and_enter()
        for encounter in self.engine.definition.encounters.values():
            for spec in encounter.monsters:
                actor = self.state.actors[spec.actor_id]
                self.assertTrue(actor.attacks or actor.spells or actor.capabilities, spec.actor_id)
        ruffian = self.state.actors['redbrand-barracks-1']
        attack = ruffian.attacks['shortsword']
        self.assertEqual((attack.to_hit_bonus, attack.reach_ft, attack.damage_type), (4, 5, 'piercing'))
        self.assertIn('multiattack', ruffian.capabilities)
        self.assertIn('rotting-gaze', self.state.actors['nothic-1'].capabilities)
        caster = self.state.actors['glasstaff-1']
        self.assertEqual(caster.resource_pools['spell-slot-1'].current, 4)
        self.assertEqual(caster.resource_pools['spell-slot-2'].current, 3)
        self.assertIn('magic-missile', caster.spells)
        self.assertIn('misty-step', caster.spells)

    def test_monster_actions_and_prepared_slots_execute_through_kernel(self):
        from shared_types.encounter_intents import StartEncounterIntent, UseCapabilityIntent, CastSpellIntent
        from shared_types.encounter_events import AttackRolledEvent
        from shared_types.encounter_models import EncounterPhase

        self.arrive_and_enter()
        hero = self.state.actors['p1']
        hero.position = GridPosition(18, 14)
        hero.current_hit_points = hero.max_hit_points = 100
        ruffian = self.state.actors['redbrand-barracks-1']
        ruffian.position = GridPosition(19, 14)
        self.runtime.kernel.dispatch(self.state, StartEncounterIntent(('p1', ruffian.actor_id)))
        self.state.active_actor_id = ruffian.actor_id
        ruffian.action_available = True
        offset = len(self.state.event_log)
        self.runtime.kernel.dispatch(self.state, UseCapabilityIntent(ruffian.actor_id, 'multiattack', 'p1'))
        self.assertEqual(sum(isinstance(e, AttackRolledEvent) for e in self.state.event_log[offset:]), 2)
        self.assertFalse(ruffian.action_available)
        # A separate spell execution fixture: no changed statistics or replenished slots.
        self.state.phase = EncounterPhase.READY
        hero.position = GridPosition(7, 3)
        caster = self.state.actors['glasstaff-1']
        caster.position = GridPosition(8, 3)
        self.runtime.kernel.dispatch(self.state, StartEncounterIntent(('p1', caster.actor_id)))
        self.state.active_actor_id = caster.actor_id
        caster.action_available = True
        hp = hero.current_hit_points
        self.runtime.kernel.dispatch(self.state, CastSpellIntent(caster.actor_id, 'magic-missile', 'p1'))
        self.assertLess(hero.current_hit_points, hp)
        self.assertEqual(caster.resource_pools['spell-slot-1'].current, 3)
        self.assertEqual(caster.resource_pools['spell-slot-2'].current, 3)

    def test_glasstaff_material_spell_and_bonus_teleport_are_executable(self):
        from shared_types.encounter_intents import StartEncounterIntent, CastSpellIntent

        self.arrive_and_enter()
        hero = self.state.actors['p1']
        hero.position = GridPosition(7, 3)
        caster = self.state.actors['glasstaff-1']
        self.runtime.kernel.dispatch(self.state, StartEncounterIntent(('p1', caster.actor_id)))
        self.state.active_actor_id = caster.actor_id
        self.runtime.kernel.dispatch(self.state, CastSpellIntent(caster.actor_id, 'hold-person', 'p1'))
        self.assertEqual(caster.resource_pools['spell-slot-2'].current, 2)
        # A separate turn follows the same authoritative action/slot budget.
        from shared_types.encounter_intents import EndTurnIntent

        self.runtime.kernel.dispatch(self.state, EndTurnIntent(caster.actor_id))
        self.runtime.kernel.dispatch(self.state, EndTurnIntent('p1'))
        self.runtime.kernel.dispatch(self.state, CastSpellIntent(caster.actor_id, 'misty-step', x=9, y=4))
        self.assertEqual(caster.position.horizontal(), GridPosition(9, 4))
        self.assertEqual(caster.resource_pools['spell-slot-2'].current, 1)

    def test_clues_unlock_routes_without_moving_party_or_forcing_combat(self):
        from shared_types.errors import EncounterValidationError

        self.act('arrive')
        self.act('visit', 'tresendar-manor')
        with self.assertRaises(EncounterValidationError):
            self.act('enter', 'tunnel')
        self.act('visit', 'alderleaf-farm')
        self.act('talk', 'carp-alderleaf')
        self.assertIn('secret-tunnel-known', self.site.progress.flags)
        self.assertEqual(self.site.progress.place_id, 'alderleaf-farm')
        self.assertFalse(self.site.progress.in_dungeon)
        self.act('visit', 'tresendar-manor')
        self.act('enter', 'tunnel')
        self.assertEqual(self.state.actors['p1'].position, GridPosition(10, 16))
        self.assertEqual(self.state.actors['p1'].current_hit_points, 13)
        self.assertIsNone(self.site.progress.active_encounter_id)

    def test_failed_door_action_does_not_mutate_state(self):
        from shared_types.errors import EncounterValidationError

        self.arrive_and_enter()
        before = deepcopy((self.state, self.site))
        with self.assertRaises(EncounterValidationError):
            self.act('open', 'quarters-secret')
        self.assertEqual((self.state, self.site), before)
        with self.assertRaises(EncounterValidationError):
            self.act('open', 'guard-door')
        self.assertEqual((self.state, self.site), before)

    def test_door_changes_edge_and_room_combat_is_explicitly_scoped(self):
        from shared_types.encounter_models import EncounterPhase
        from shared_types.battlefield import edge_key, EdgeTraversalRequirement

        self.arrive_and_enter()
        self.state.actors['p1'].position = GridPosition(20, 14)
        self.act('open', 'cellar-barracks')
        edge = self.state.battlefield.edges[edge_key(GridPosition(19, 14), GridPosition(20, 14))]
        self.assertEqual(edge.traversal_requirement, EdgeTraversalRequirement.NONE)
        from shared_types.encounter_intents import ExploreMoveIntent

        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 19, 14), party_actor_ids=('p1',)
        )
        self.state, self.site = result.encounter_state, result.site_state
        self.assertEqual(self.state.phase, EncounterPhase.IN_PROGRESS)
        self.assertEqual(
            set(self.state.initiative_order),
            {'p1', 'redbrand-barracks-1', 'redbrand-barracks-2', 'redbrand-barracks-3'},
        )
        self.assertEqual(self.site.progress.active_encounter_id, 'redbrand-barracks')

    def test_manor_stairs_reach_cellar_and_door_beneath_landing(self):
        from shared_types.encounter_intents import ExploreMoveIntent

        self.arrive_and_enter()
        for x, y, z in ((26, 13, 15), (25, 13, 15), (25, 14, 5), (25, 15, 0), (26, 14, 0), (26, 13, 0)):
            result = self.engine.move(
                self.state, self.site, ExploreMoveIntent('p1', x, y, z), party_actor_ids=('p1',)
            )
            self.state, self.site = result.encounter_state, result.site_state
            self.assertEqual(self.state.actors['p1'].position, GridPosition(x, y, z))
        self.act('open', 'cellar-hall')
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 26, 12), party_actor_ids=('p1',)
        )
        self.assertEqual(result.encounter_state.actors['p1'].position, GridPosition(26, 12))

    def test_revisit_preserves_enemy_hp_doors_and_player_resources(self):
        self.arrive_and_enter('tunnel')
        self.state.actors['glasstaff-1'].current_hit_points = 9
        self.state.actors['p1'].current_hit_points = 7
        self.act('leave')
        self.assertNotIn('glasstaff-1', self.state.actors)
        self.act('enter', 'tunnel')
        self.assertEqual(self.state.actors['glasstaff-1'].current_hit_points, 9)
        self.assertEqual(self.state.actors['p1'].current_hit_points, 7)
        self.assertEqual(self.state.actors['p1'].speed_ft, 30)

    def test_nothic_parley_and_prisoner_rescue_require_local_evidence(self):
        from shared_types.errors import EncounterValidationError

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 13)
        self.act('interact', 'nothic-bargain')
        self.assertIn('nothic-truce', self.site.progress.flags)
        self.assertIsNone(self.site.progress.active_encounter_id)
        with self.assertRaises(EncounterValidationError):
            self.act('interact', 'free-prisoners')
        self.state.actors['p1'].position = GridPosition(21, 6)
        with self.assertRaises(EncounterValidationError):
            self.act('interact', 'free-prisoners')

    def test_combat_completion_rejects_living_hostiles(self):
        from shared_types.errors import EncounterValidationError

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(8, 13)
        self.act('engage', 'nothic')
        before = deepcopy((self.state, self.site))
        with self.assertRaises(EncounterValidationError):
            self.act('resolve-combat')
        self.assertEqual((self.state, self.site), before)
        self.state.actors['nothic-1'].current_hit_points = 0
        self.act('resolve-combat')
        self.assertIn('nothic', self.site.progress.resolved_encounters)
        self.assertIn('nothic-resolved', self.site.progress.flags)

    def test_event_replay_reconstructs_site_and_mechanical_state(self):
        initial_state, initial_site = deepcopy(self.state), deepcopy(self.site)
        self.arrive_and_enter('tunnel')
        result = self.engine.replay(initial_state, initial_site, self.state.event_log)
        self.assertEqual(result.site_state.progress, self.site.progress)
        self.assertEqual(result.encounter_state.actors, self.state.actors)
        self.assertEqual(result.encounter_state.battlefield, self.state.battlefield)

    def test_crossing_rigged_bridge_stops_movement_and_uses_real_fall_rules(self):
        from shared_types.encounter_intents import ExploreMoveIntent
        from shared_types.conditions import ConditionType
        from encounter_runtime.conditions import has_condition

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 15)
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 12, 15), party_actor_ids=('p1',)
        )
        self.state, self.site = result.encounter_state, result.site_state
        self.assertIn('rigged-bridge', self.site.progress.triggered_hazards)
        self.assertNotIn('south-bridge', self.state.battlefield.features)
        self.assertEqual(self.state.actors['p1'].position.z, -20)
        self.assertLess(self.state.actors['p1'].current_hit_points, 13)
        self.assertTrue(has_condition(self.state.actors['p1'], ConditionType.PRONE))
        self.assertNotEqual(self.state.actors['p1'].position.horizontal(), GridPosition(12, 15))

    def test_concealed_pit_checks_path_not_only_final_destination(self):
        from shared_types.encounter_intents import ExploreMoveIntent
        from shared_types.models import Ability

        self.arrive_and_enter()
        self.state.actors['p1'].position = GridPosition(24, 10)
        self.state.actors['p1'].saving_throw_bonuses[Ability.DEX] = -100
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 21, 10), party_actor_ids=('p1',)
        )
        self.state, self.site = result.encounter_state, result.site_state
        self.assertIn('hall-pit', self.site.progress.triggered_hazards)
        self.assertEqual(self.state.actors['p1'].position.z, -20)
        self.assertLess(self.state.actors['p1'].current_hit_points, 13)

    def test_search_is_seeded_and_replay_keeps_roll_counter(self):
        from shared_types.models import Ability

        self.arrive_and_enter()
        self.state.actors['p1'].position = GridPosition(20, 18)
        self.state.actors['p1'].ability_modifiers[Ability.WIS] = 50
        initial, initial_site = deepcopy(self.state), deepcopy(self.site)
        offset = len(self.state.event_log)
        self.act('search', 'here')
        self.assertIn('cellar-secret', self.site.progress.discovered_doors)
        self.assertGreater(self.state.random_counter, initial.random_counter)
        replay = self.engine.replay(initial, initial_site, self.state.event_log[offset:])
        self.assertEqual(replay.encounter_state.random_counter, self.state.random_counter)
        self.assertEqual(replay.site_state.progress, self.site.progress)

    def test_scene_change_retains_personal_effects_and_isolates_npc_effects(self):
        from shared_types.encounter_models import ActiveEffectState
        from shared_types.capabilities import ActiveEffectDefinition, DurationSpec, EffectDurationType

        self.arrive_and_enter('tunnel')
        definition = ActiveEffectDefinition(
            name='Fixture ward', duration=DurationSpec(EffectDurationType.ROUNDS, rounds=100)
        )
        personal = ActiveEffectState(
            'party-ward', 'fixture', 'Ward', 'p1', ('p1',), definition, remaining_rounds=100
        )
        npc = replace(
            personal,
            effect_instance_id='npc-ward',
            source_actor_id='glasstaff-1',
            target_actor_ids=('glasstaff-1',),
        )
        self.state.active_effects = {'party-ward': personal, 'npc-ward': npc}
        self.act('leave')
        self.assertEqual(set(self.state.active_effects), {'party-ward'})
        self.act('enter', 'tunnel')
        self.assertEqual(set(self.state.active_effects), {'party-ward', 'npc-ward'})

    def test_missing_bridge_load_requires_explicit_weight_and_failed_move_is_atomic(self):
        from shared_types.encounter_intents import ExploreMoveIntent
        from shared_types.errors import EncounterClarificationRequiredError

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 15)
        self.state.actors['p1'].body_weight_lb = 0
        before = deepcopy((self.state, self.site))
        with self.assertRaises(EncounterClarificationRequiredError):
            self.engine.move(self.state, self.site, ExploreMoveIntent('p1', 12, 15), party_actor_ids=('p1',))
        self.assertEqual((self.state, self.site), before)

    def test_standing_after_exploration_fall_uses_real_rules_without_combat(self):
        from shared_types.encounter_intents import ExploreMoveIntent, StandFromProneIntent
        from shared_types.conditions import ConditionType
        from encounter_runtime.conditions import has_condition

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 15)
        before_clock = self.state.clock_seconds
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 12, 15), party_actor_ids=('p1',)
        )
        self.state, self.site = result.encounter_state, result.site_state
        self.runtime.kernel.dispatch(self.state, StandFromProneIntent('p1'))
        self.assertFalse(has_condition(self.state.actors['p1'], ConditionType.PRONE))
        self.assertEqual(self.state.clock_seconds, before_clock + 12)

    def test_hazard_resumes_after_opportunity_reaction_and_replays(self):
        from shared_types.encounter_intents import MoveActorIntent, ChooseReactionIntent

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 15)
        self.state.actors['nothic-1'].position = GridPosition(8, 15)
        self.act('engage', 'nothic')
        self.state.active_actor_id = 'p1'
        self.state.actors['p1'].remaining_movement_ft = 30
        result = self.engine.move(
            self.state, self.site, MoveActorIntent('p1', 12, 15), party_actor_ids=('p1',)
        )
        self.state, self.site = result.encounter_state, result.site_state
        self.assertIsNotNone(self.state.pending_reaction_window)
        self.assertNotIn('rigged-bridge', self.site.progress.triggered_hazards)
        self.runtime.kernel.dispatch(self.state, ChooseReactionIntent('nothic-1', 'decline'))
        initial, initial_site = deepcopy(self.state), deepcopy(self.site)
        result = self.engine.resume_movement(self.state, self.site, party_actor_ids=('p1',))
        self.state, self.site = result.encounter_state, result.site_state
        self.assertIn('rigged-bridge', self.site.progress.triggered_hazards)
        self.assertEqual(self.state.actors['p1'].position.z, -20)
        replay = self.engine.replay(initial, initial_site, result.events)
        self.assertEqual(replay.site_state, self.site)
        self.assertEqual(replay.encounter_state, self.state)

    def test_pit_triggers_at_exactly_one_hundred_pounds(self):
        from shared_types.encounter_intents import ExploreMoveIntent

        self.arrive_and_enter()
        self.state.actors['p1'].position = GridPosition(24, 10)
        self.state.actors['p1'].body_weight_lb = 100
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 23, 10), party_actor_ids=('p1',)
        )
        self.assertIn('hall-pit', result.site_state.progress.triggered_hazards)

    def test_bridge_supports_exactly_fifty_pounds(self):
        from shared_types.encounter_intents import ExploreMoveIntent

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(9, 15)
        self.state.actors['p1'].body_weight_lb = 50
        result = self.engine.move(
            self.state, self.site, ExploreMoveIntent('p1', 10, 15), party_actor_ids=('p1',)
        )
        self.assertNotIn('rigged-bridge', result.site_state.progress.triggered_hazards)

    def test_unengaged_room_monsters_do_not_receive_opportunity_reactions(self):
        from encounter_runtime.capabilities import discover_leave_reach_reactions

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(8, 13)
        self.act('engage', 'nothic')
        self.state.actors['redbrand-barracks-1'].position = GridPosition(7, 13)
        options = discover_leave_reach_reactions(
            self.state,
            moving_actor_id='p1',
            from_position=GridPosition(8, 13),
            to_position=GridPosition(10, 13),
        )
        self.assertNotIn('redbrand-barracks-1', {o.actor_id for o in options})

    def test_scoped_encounter_completion_ignores_unengaged_rooms(self):
        from shared_types.encounter_events import DiedEvent
        from shared_types.encounter_models import EncounterPhase, ActorSide

        self.arrive_and_enter('tunnel')
        self.state.actors['p1'].position = GridPosition(8, 13)
        self.act('engage', 'nothic')
        self.state.actors['nothic-1'].current_hit_points = 0
        self.runtime.kernel._apply_event(
            self.state, DiedEvent(actor_id='nothic-1', reason='fixture damage resolution')
        )
        self.assertEqual(self.state.phase, EncounterPhase.COMPLETE)
        self.assertEqual(self.state.winning_side, ActorSide.PLAYER)

    def test_complete_hideout_arc_from_clues_to_rescue_and_return_replays(self):
        import json
        from shared_types.encounter_intents import (
            ExploreMoveIntent,
            MoveActorIntent,
            AttackIntent,
            EndTurnIntent,
        )
        from shared_types.encounter_models import AttackProfile, AttackKind

        fixture = json.loads((ROOT / 'tests/fixtures/phandalin_redbrand_arc.json').read_text())
        actor = self.state.actors['p1']
        actor.armor_class = 40
        actor.initiative_bonus = 50
        actor.max_hit_points = actor.current_hit_points = 200
        actor.ability_modifiers = {ability: 50 for ability in actor.ability_modifiers}
        actor.attacks = {
            'fixture-shot': AttackProfile(
                'fixture-shot', 'Test-only shot', AttackKind.RANGED, 50, None, 120, 120, 1, 4, 100, 'force'
            )
        }
        initial, initial_site = deepcopy(self.state), deepcopy(self.site)
        for command in fixture['commands']:
            try:
                tokens = command.split()
                if tokens[0] == 'move':
                    move_type = (
                        MoveActorIntent if self.site.progress.active_encounter_id else ExploreMoveIntent
                    )
                    result = self.engine.move(
                        self.state,
                        self.site,
                        move_type('p1', int(tokens[1]), int(tokens[2])),
                        party_actor_ids=('p1',),
                    )
                    self.state, self.site = result.encounter_state, result.site_state
                    self.assertEqual(
                        self.state.actors['p1'].position.horizontal(),
                        GridPosition(int(tokens[1]), int(tokens[2])),
                    )
                elif tokens[0] == 'fight':
                    self.assertIsNotNone(self.site.progress.active_encounter_id)
                    encounter = self.engine.definition.encounters[self.site.progress.active_encounter_id]
                    for _ in range(100):
                        living = [
                            m.actor_id
                            for m in encounter.monsters
                            if self.state.actors[m.actor_id].current_hit_points > 0
                        ]
                        if not living:
                            break
                        active = self.state.active_actor_id
                        if active == 'p1' and self.state.actors['p1'].action_available:
                            self.runtime.kernel.dispatch(
                                self.state, AttackIntent('p1', 'fixture-shot', living[0])
                            )
                            if not any(self.state.actors[mid].current_hit_points > 0 for mid in living):
                                break
                        self.runtime.kernel.dispatch(self.state, EndTurnIntent(active))
                    else:
                        self.fail('Fixture combat exceeded its explicit round limit')
                    self.act('resolve-combat')
                else:
                    self.act(tokens[0], tokens[1] if len(tokens) > 1 else None)
            except Exception as exc:
                raise AssertionError(f'Arc command {command!r}: {exc}') from exc
        self.assertFalse(self.site.progress.in_dungeon)
        self.assertTrue(set(fixture['expected_flags']) <= self.site.progress.flags)
        self.assertEqual(set(fixture['expected_encounters']), self.site.progress.resolved_encounters)
        replay = self.engine.replay(initial, initial_site, self.state.event_log)
        self.assertEqual(replay.site_state, self.site)
        self.assertEqual(replay.encounter_state, self.state)

    def test_combat_door_interaction_preserves_action_and_requires_explicit_utilize(self):
        from shared_types.campaign_site import CampaignSiteIntent, SiteAction
        from shared_types.equipment import ObjectInteractionCostMode
        from shared_types.errors import EncounterValidationError

        self.arrive_and_enter()
        self.state.actors['p1'].position = GridPosition(6, 4)
        self.act('engage', 'glasstaff')
        self.state.active_actor_id = 'p1'
        self.act('open', 'quarters-door')
        self.assertTrue(self.state.actors['p1'].action_available)
        self.assertFalse(self.state.actors['p1'].remaining_free_object_interaction)
        before = deepcopy((self.state, self.site))
        with self.assertRaises(EncounterValidationError):
            self.act('close', 'quarters-door')
        self.assertEqual((self.state, self.site), before)
        result = self.engine.resolve(
            self.state,
            self.site,
            CampaignSiteIntent(
                'p1', SiteAction.CLOSE, 'quarters-door', cost_mode=ObjectInteractionCostMode.UTILIZE
            ),
            party_actor_ids=('p1',),
            current_location_id='redbrand-hideout',
        )
        self.assertFalse(result.encounter_state.actors['p1'].action_available)
        self.assertNotIn('quarters-door', result.site_state.progress.opened_doors)
