from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from rules_engine.advancement import CharacterAdvancementEngine
from session_server import build_default_character_record
from session_server.bootstrap import build_lmop_story_demo_session_from_records
from session_server.web_projection import project_story_session_view
from shared_types.advancement import AdvancementHitPointMode, AdvancementPolicy, AdvancementRuntimeState
from shared_types.errors import EncounterValidationError
from shared_types.models import Ability, ContentCatalog, CreationPhase, MulticlassRequirementSet
from shared_types.progression import PendingLevelUpRecord, ProgressionMode
from shared_types.storytelling import RuntimeMode

LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class QueueTransport:
    def __init__(self, payloads: list[dict] | None = None) -> None:
        self.payloads = list(payloads or [])

    def _next_payload(self) -> dict:
        if not self.payloads:
            raise AssertionError('No queued LLM payloads remain for this test.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict) -> dict:
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict) -> list[dict]:
        return [{'type': 'response.completed', 'response': self._next_payload()}]


class AdvancementEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.advancement-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)
        self.env_path = self._tempdir / '.env'
        self.env_path.write_text(
            'OPENAI_API_KEY=test-key\n'
            'OPENAI_BASE_URL=https://example.invalid/v1\n'
            'OPENAI_RESPONSES_MODEL=test-model\n',
            encoding='utf-8',
        )

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _creation_kernel(self):
        return build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)

    def _class_skill_tokens_for(self, kernel, class_id: str) -> tuple[str, ...]:
        class_record = kernel.catalog.classes[class_id]
        return tuple(class_record.class_skill_option_ids[: class_record.skill_choice_count])

    def _resolve_all_pending_choices(self, kernel, ui, state, *, overrides: dict[str, tuple[str, ...]] | None = None):
        overrides = overrides or {}
        while kernel.phase(state) == CreationPhase.CHOOSE_CREATION_CHOICES:
            pending = kernel._next_pending_creation_choice(state)
            if pending is None:
                break
            option_ids = overrides.get(pending.group.choice_id)
            if option_ids is None:
                required = pending.group.constraint.required_count
                option_ids = tuple(option.option_id for option in pending.group.options[:required])
            state, _ = ui.execute(state, f"/create choose choice {pending.group.choice_id} {' '.join(option_ids)}")
        return state

    def _build_record(
        self,
        class_id: str,
        *,
        assign_command: str = '/create ability assign 15 14 13 12 10 8',
        overrides: dict[str, tuple[str, ...]] | None = None,
        background_name: str = 'Acolyte',
    ):
        kernel = self._creation_kernel()
        ui = SlashCommandInterface(kernel)
        state = kernel.new_state()
        background_id = next(
            record_id
            for record_id, record in kernel.catalog.backgrounds.items()
            if record.name == background_name and record.source == 'XPHB'
        )
        commands = [
            '/create begin',
            '/create choose species human',
            f'/create choose class {class_id}',
            '/create choose class-skills ' + ' '.join(self._class_skill_tokens_for(kernel, class_id)),
            f'/create choose background {background_id}',
        ]
        for command in commands:
            state, _ = ui.execute(state, command)
        state = self._resolve_all_pending_choices(kernel, ui, state, overrides=overrides)
        background = kernel.catalog.backgrounds[background_id]
        class_record = kernel.catalog.classes[class_id]
        followup = [
            '/create ability generate point-buy 15 14 13 12 10 8',
            assign_command,
            f'/create background-asi choose {background.ability_increase_options()[0].option_id}',
            f'/create equipment background package {background.package_options[0].package_id}',
        ]
        if class_record.package_options:
            followup.append(f'/create equipment class package {class_record.package_options[0].package_id}')
        else:
            followup.append('/create equipment class wealth')
        followup.append('/create confirm')
        for command in followup:
            state, _ = ui.execute(state, command)
        self.assertEqual(kernel.phase(state), CreationPhase.COMPLETE)
        self.assertIsNotNone(state.character_record)
        return state.character_record

    def _clone_record(self, record, *, record_id: str):
        cloned = deepcopy(record)
        cloned.record_id = record_id
        return cloned

    def _build_story_session(self, record):
        player_records = tuple(
            self._clone_record(record, record_id=f'{record.record_id}-p{index}')
            for index in range(1, 5)
        )
        return build_lmop_story_demo_session_from_records(
            player_records=player_records,
            base_url=LOCAL_MIRROR_BASE_URL,
            env_path=self.env_path,
            client_transport=QueueTransport(),
        )

    def test_xp_pending_level_up_can_be_started_and_applied(self) -> None:
        session = self._build_story_session(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL))
        actor_before = session.state.actors['player-1']
        old_max_hp = actor_before.max_hit_points
        old_slot_max = actor_before.resource_pools['spell-slot-1'].maximum

        session.execute_for_controller('dm', '/progression xp award actor:player-1 300 dm_manual advancement-xp threshold reached')
        start_view = session.execute_for_controller('player-1-controller', '/levelup start')
        self.assertTrue(any('Pending advancement transaction' in line for line in start_view.summary_lines))

        session.execute_for_controller('player-1-controller', '/levelup apply')
        actor_after = session.state.actors['player-1']
        self.assertEqual(actor_after.level, 2)
        self.assertEqual(actor_after.character_record.level, 2)
        self.assertGreater(actor_after.max_hit_points, old_max_hp)
        self.assertEqual(actor_after.total_hit_dice, 2)
        self.assertEqual(actor_after.remaining_hit_dice, 2)
        self.assertGreater(actor_after.resource_pools['spell-slot-1'].maximum, old_slot_max)
        self.assertTrue(session.story_state.progression_state.pending_level_ups['level-up:xp:player-1:2'].applied)
        self.assertTrue(any('advances to level 2' in entry.text for entry in session.story_state.transcript_entries))

    def test_milestone_pending_level_up_can_be_consumed(self) -> None:
        session = self._build_story_session(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL))
        session.execute_for_controller('dm', '/progression mode milestone')
        session.execute_for_controller('dm', '/progression milestone complete party chapter_beat_reached chapter-01 complete')
        session.execute_for_controller('player-1-controller', '/levelup start')
        session.execute_for_controller('player-1-controller', '/levelup apply')
        self.assertEqual(session.state.actors['player-1'].level, 2)
        self.assertTrue(session.story_state.progression_state.pending_level_ups['level-up:milestone:player-1:2'].applied)

    def test_sorcerer_level_up_blocks_until_pending_choices_are_resolved(self) -> None:
        record = self._build_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        session = self._build_story_session(record)
        session.execute_for_controller('dm', '/progression xp award actor:player-1 300 dm_manual sorcerer-threshold reached')
        view = session.execute_for_controller('player-1-controller', '/levelup start')
        choice_group_id = next(group_id for group_id in view.available_choices if group_id.startswith('levelup:player-1:'))
        self.assertIn('metamagic', choice_group_id)
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/levelup apply')
        self.assertEqual(session.state.actors['player-1'].level, 1)
        choice_id = choice_group_id.split(':', 2)[2]
        selected = view.available_choices[choice_group_id][:2]
        session.execute_for_controller(
            'player-1-controller',
            f"/levelup choose {choice_id} {' '.join(option.option_id for option in selected)}",
        )
        session.execute_for_controller('player-1-controller', '/levelup apply')
        updated_record = session.state.actors['player-1'].character_record
        self.assertEqual(updated_record.level, 2)
        self.assertIn('Metamagic', updated_record.class_feature_names)
        for option in selected:
            self.assertIn(option.label, updated_record.class_feature_names)

    def test_level_up_apply_is_blocked_in_combat_unless_policy_allows_it(self) -> None:
        session = self._build_story_session(build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL))
        session.execute_for_controller('dm', '/progression xp award actor:player-1 300 dm_manual combat-threshold reached')
        session.execute_for_controller('player-1-controller', '/levelup start')
        session.story_state.runtime_mode = RuntimeMode.COMBAT
        with self.assertRaises(EncounterValidationError):
            session.execute_for_controller('player-1-controller', '/levelup apply')
        session.story_state.advancement_state.policy = replace(session.story_state.advancement_state.policy, allow_apply_in_combat=True)
        session.execute_for_controller('player-1-controller', '/levelup apply')
        self.assertEqual(session.state.actors['player-1'].level, 2)

    def test_multiclass_validation_checks_requirement_sets_when_enabled(self) -> None:
        engine = CharacterAdvancementEngine()
        kernel = self._creation_kernel()
        catalog = kernel.catalog
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        pending = PendingLevelUpRecord(
            pending_id='pending-xp-player-1-2',
            actor_id='player-1',
            actor_label='Player 1',
            target_new_total_level=2,
            source_mode=ProgressionMode.XP,
        )
        valid_fighter = replace(
            catalog.classes['fighter'],
            multiclass_requirement_sets=(MulticlassRequirementSet(minimum_scores={Ability.DEX: 13}),),
        )
        invalid_fighter = replace(
            catalog.classes['fighter'],
            multiclass_requirement_sets=(MulticlassRequirementSet(minimum_scores={Ability.STR: 20}),),
        )
        valid_catalog = ContentCatalog(
            species=catalog.species,
            classes={**catalog.classes, 'fighter': valid_fighter},
            backgrounds=catalog.backgrounds,
            feats=catalog.feats,
            items=catalog.items,
            skills=catalog.skills,
            tools=catalog.tools,
            spells=catalog.spells,
        )
        invalid_catalog = ContentCatalog(
            species=catalog.species,
            classes={**catalog.classes, 'fighter': invalid_fighter},
            backgrounds=catalog.backgrounds,
            feats=catalog.feats,
            items=catalog.items,
            skills=catalog.skills,
            tools=catalog.tools,
            spells=catalog.spells,
        )
        valid_state = AdvancementRuntimeState(policy=AdvancementPolicy(allow_multiclass=True))
        valid_state, _transaction, _events = engine.start_transaction(
            valid_state,
            actor_id='player-1',
            actor_label='Player 1',
            record=record,
            pending_record=pending,
            timestamp_seconds=0,
            catalog=valid_catalog,
        )
        valid_state, transaction, _events = engine.choose_class(
            valid_state,
            transaction_id=valid_state.actor_transaction_ids['player-1'],
            chosen_class_id='fighter',
            record=record,
            catalog=valid_catalog,
        )
        self.assertEqual(transaction.chosen_class_id, 'fighter')
        invalid_state = AdvancementRuntimeState(policy=AdvancementPolicy(allow_multiclass=True))
        invalid_state, _transaction, _events = engine.start_transaction(
            invalid_state,
            actor_id='player-1',
            actor_label='Player 1',
            record=record,
            pending_record=pending,
            timestamp_seconds=0,
            catalog=invalid_catalog,
        )
        with self.assertRaises(EncounterValidationError):
            engine.choose_class(
                invalid_state,
                transaction_id=invalid_state.actor_transaction_ids['player-1'],
                chosen_class_id='fighter',
                record=record,
                catalog=invalid_catalog,
            )

    def test_rolled_hit_point_gain_is_deterministic(self) -> None:
        engine = CharacterAdvancementEngine()
        kernel = self._creation_kernel()
        catalog = kernel.catalog
        record = build_default_character_record(base_url=LOCAL_MIRROR_BASE_URL)
        pending = PendingLevelUpRecord(
            pending_id='pending-xp-player-1-2',
            actor_id='player-1',
            actor_label='Player 1',
            target_new_total_level=2,
            source_mode=ProgressionMode.XP,
        )
        policy = AdvancementPolicy(hit_point_mode=AdvancementHitPointMode.ROLLED)
        species_bonus = catalog.species[record.species_id].hit_point_bonus_per_level

        first_state = AdvancementRuntimeState(policy=policy)
        first_state, _transaction, _events = engine.start_transaction(
            first_state,
            actor_id='player-1',
            actor_label='Player 1',
            record=record,
            pending_record=pending,
            timestamp_seconds=0,
            catalog=catalog,
        )
        first_state, first_record, first_transaction, _events, first_counter = engine.commit_transaction(
            first_state,
            actor_id='player-1',
            record=record,
            species_hit_point_bonus_per_level=species_bonus,
            catalog=catalog,
            random_counter=7,
            seed='advancement-seed',
        )

        second_state = AdvancementRuntimeState(policy=policy)
        second_state, _transaction, _events = engine.start_transaction(
            second_state,
            actor_id='player-1',
            actor_label='Player 1',
            record=record,
            pending_record=pending,
            timestamp_seconds=0,
            catalog=catalog,
        )
        second_state, second_record, second_transaction, _events, second_counter = engine.commit_transaction(
            second_state,
            actor_id='player-1',
            record=record,
            species_hit_point_bonus_per_level=species_bonus,
            catalog=catalog,
            random_counter=7,
            seed='advancement-seed',
        )

        self.assertEqual(first_transaction.hp_gain.total_gained, second_transaction.hp_gain.total_gained)
        self.assertEqual(first_record.max_hit_points, second_record.max_hit_points)
        self.assertEqual(first_counter, second_counter)

    def test_web_projection_exposes_advancement_choice_command_insert(self) -> None:
        record = self._build_record('sorcerer', assign_command='/create ability assign 10 14 13 12 8 15')
        session = self._build_story_session(record)
        session.execute_for_controller('dm', '/progression xp award actor:player-1 300 dm_manual web-threshold reached')
        session.execute_for_controller('player-1-controller', '/levelup start')
        view = project_story_session_view(session, 'player-1-controller', session_id='advancement-web')
        levelup_groups = tuple(group for group in view.action_groups if group.group_id.startswith('levelup:player-1:'))
        self.assertTrue(levelup_groups)
        first_choice = levelup_groups[0].choices[0]
        self.assertIsNotNone(first_choice.command_insert_text)
        self.assertTrue(first_choice.command_insert_text.startswith('/levelup choose player-1 '))
        self.assertIn(first_choice.option_id, first_choice.command_insert_text)


if __name__ == '__main__':
    unittest.main()
