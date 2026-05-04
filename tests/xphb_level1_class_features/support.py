from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import unittest

from character_creation import build_default_kernel
from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface, SlashCommandInterface
from shared_types.encounter_intents import ContinueTimingIntent
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.models import CreationPhase

LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


class Level1ClassFeatureTestCase(unittest.TestCase):
    def build_runtime(self):
        return build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def _monster_id(self, runtime, *, name: str = 'Skeleton', source: str = 'XMM') -> str:
        for record_id, record in runtime.encounter_catalog.monsters.items():
            if record.name == name and record.source == source:
                return record_id
        raise AssertionError(f'Monster not found: {name} [{source}]')

    def _build_creation_kernel(self):
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

    def complete_record(
        self,
        class_id: str,
        *,
        assign_command: str = '/create ability assign 15 14 13 12 10 8',
        overrides: dict[str, tuple[str, ...]] | None = None,
        background_name: str = 'Acolyte',
    ):
        kernel = self._build_creation_kernel()
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
        assert state.character_record is not None
        return state.character_record

    def compile_actor(self, record, *, actor_id: str = 'player-1', position: GridPosition = GridPosition(0, 0, 0)):
        runtime = self.build_runtime()
        return runtime.monster_runtime.compile_player(record=record, actor_id=actor_id, position=position)

    def build_session(
        self,
        record,
        *,
        player_position: GridPosition = GridPosition(0, 0, 0),
        monster_name: str = 'Skeleton',
        monster_source: str = 'XMM',
        monster_position: GridPosition = GridPosition(1, 0, 0),
    ):
        runtime = self.build_runtime()
        monster_id = self._monster_id(runtime, name=monster_name, source=monster_source)
        state = runtime.new_state(
            characters=(CharacterPlacement(actor_id='player-1', record=record, position=player_position),),
            monsters=(MonsterPlacement(actor_id='monster-1', monster_id=monster_id, position=monster_position),),
        )
        return SimpleNamespace(
            runtime_services=runtime,
            command_interface=EncounterSlashCommandInterface(runtime.kernel),
            state=state,
        )

    def advance_to_actor(self, session, actor_id: str) -> None:
        session.state, _ = session.command_interface.execute(session.state, '/encounter start')
        self.advance_existing_turn(session, actor_id)

    def advance_existing_turn(self, session, actor_id: str) -> None:
        guard = 0
        while session.state.active_actor_id != actor_id:
            guard += 1
            if guard > 40:
                raise AssertionError(f'Could not advance to actor {actor_id}.')
            current_actor_id = session.state.active_actor_id
            session.state, _ = session.command_interface.execute(session.state, f'/endturn {current_actor_id}')
            if current_actor_id is not None:
                self.resolve_pending_timing(session, actor_id=current_actor_id)

    def resolve_pending_timing(self, session, *, actor_id: str) -> None:
        guard = 0
        while session.state.pending_timing_queue is not None:
            guard += 1
            if guard > 20:
                raise AssertionError('Could not resolve the pending timing queue.')
            session.state = session.command_interface.kernel.dispatch(
                session.state,
                ContinueTimingIntent(actor_id=actor_id),
            )

    def end_turn_and_resolve(self, session, actor_id: str) -> None:
        session.state, _ = session.command_interface.execute(session.state, f'/endturn {actor_id}')
        self.resolve_pending_timing(session, actor_id=actor_id)

    def choice_ids(self, record, choice_id: str) -> tuple[str, ...]:
        for choice in record.resolved_creation_choices:
            if choice.choice_id == choice_id:
                return choice.selected_option_ids
        return ()

    def choice_labels(self, record, choice_id: str) -> tuple[str, ...]:
        for choice in record.resolved_creation_choices:
            if choice.choice_id == choice_id:
                return choice.selected_option_labels
        return ()

    def events_since(self, session, start_index: int, event_type):
        return [event for event in session.state.event_log[start_index:] if isinstance(event, event_type)]

