from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from character_creation import build_default_kernel
from encounter_runtime import build_default_encounter_runtime
from player_interface import EncounterSlashCommandInterface, SlashCommandInterface, present_encounter_snapshot
from session_server import EncounterSession
from shared_types.encounter_control import ControllerBinding, ControllerRole, ReactionPrompt
from shared_types.encounter_models import CharacterPlacement, GridPosition, MonsterPlacement
from shared_types.errors import CharacterCreationError, ContentLoadError, EncounterError


EXAMPLE_COMMANDS: tuple[str, ...] = (
    'system: /encounter start',
    'dm: /move monster-skeleton-1 1 0',
    'dm: /endturn monster-skeleton-1',
    'dm: /endturn monster-mage-1',
    'player-1-controller: /move player-1 3 0',
    'view dm',
    'view player-1-controller',
)

CONTROLLERS: tuple[str, ...] = ('system', 'dm', 'player-1-controller')


def build_character_record():
    kernel = build_default_kernel()
    ui = SlashCommandInterface(kernel)
    state = kernel.new_state()
    commands = (
        '/create begin',
        '/create choose species aasimar',
        '/create choose class wizard',
        '/create choose class-skills Arcana History',
        '/create choose background acolyte',
        '/create choose choice class:wizard:cantrips fire-bolt mage-hand light',
        '/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance',
        '/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds',
        '/create ability generate point-buy 15 14 13 12 10 8',
        '/create ability assign 8 14 13 15 12 10',
        '/create background-asi choose acolyte-int2-wis1',
        '/create equipment background gold',
        '/create equipment class package wizard-package-1',
        '/create confirm',
    )
    for command in commands:
        state, _ = ui.execute(state, command)
    if state.character_record is None:
        raise RuntimeError('Character creation did not produce a CharacterRecord.')
    return state.character_record


def _monster_id(runtime, *, name: str, source: str) -> str:
    for record_id, record in runtime.encounter_catalog.monsters.items():
        if record.name == name and record.source == source:
            return record_id
    raise RuntimeError(f'Monster not found: {name} [{source}]')


def build_session() -> EncounterSession:
    runtime = build_default_encounter_runtime()
    record = build_character_record()
    skeleton_id = _monster_id(runtime, name='Skeleton', source='XMM')
    mage_id = _monster_id(runtime, name='Mage', source='XMM')
    state = runtime.new_state(
        characters=(CharacterPlacement(actor_id='player-1', record=record, position=GridPosition(0, 0)),),
        monsters=(
            MonsterPlacement(actor_id='monster-skeleton-1', monster_id=skeleton_id, position=GridPosition(6, 0)),
            MonsterPlacement(actor_id='monster-mage-1', monster_id=mage_id, position=GridPosition(8, 2)),
        ),
    )
    controllers = {
        'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
        'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
    }
    actor_controllers = {
        'player-1': 'player-1-controller',
        'monster-skeleton-1': 'dm',
        'monster-mage-1': 'dm',
    }
    control_runtime = runtime.build_control_runtime(controllers=controllers, actor_controllers=actor_controllers)
    return EncounterSession(
        state=state,
        control_runtime=control_runtime,
        command_interface=EncounterSlashCommandInterface(runtime.kernel),
    )


def _prompt_reaction(prompt: ReactionPrompt, state) -> str | None:
    recipients = ', '.join(f"{recipient.label} ({', '.join(recipient.actor_ids)})" for recipient in prompt.recipients)
    print(f'System prompt for {recipients}: {prompt.prompt}')
    for index, option in enumerate(prompt.options, start=1):
        print(f'  {index}. {option.label} [{option.actor_id}] - {option.detail}')
    print('  0. Decline')
    while True:
        choice = input('Reaction choice> ').strip()
        if choice in {'', '0', 'decline'}:
            return None
        if choice.isdigit():
            offset = int(choice) - 1
            if 0 <= offset < len(prompt.options):
                return prompt.options[offset].option_id
        if any(option.option_id == choice for option in prompt.options):
            return choice
        print('Enter a listed number, an option id, or 0 to decline.')


def _render_controller_view(session: EncounterSession, controller_id: str) -> None:
    view = session.view_for_controller(controller_id)
    print(f'[{controller_id}]')
    print(present_encounter_snapshot(view))
    print()


def execute_commands(session: EncounterSession, commands: Iterable[str]):
    current_sender = 'system'
    for raw_command in commands:
        command = raw_command.strip()
        if not command:
            continue
        if command.lower() == 'controllers':
            print('Controllers: system, dm, player-1-controller')
            print()
            continue
        if command.lower().startswith('use '):
            chosen = command.split(None, 1)[1].strip()
            if chosen not in CONTROLLERS:
                raise EncounterError(f'Unknown controller context: {chosen!r}.')
            current_sender = chosen
            print(f'Active controller: {current_sender}')
            print()
            continue
        if command.lower().startswith('view '):
            chosen = command.split(None, 1)[1].strip()
            if chosen == 'system':
                raise EncounterError('System does not have a private controller view.')
            _render_controller_view(session, chosen)
            continue
        sender = current_sender
        payload = command
        if ':' in command:
            prefix, remainder = command.split(':', 1)
            if prefix.strip() in CONTROLLERS:
                sender = prefix.strip()
                payload = remainder.strip()
        print(f'[{sender}]> {payload}')
        if sender == 'system':
            session.system_execute(payload, reaction_decider=_prompt_reaction)
            print('System command executed.')
            print()
            continue
        result = session.execute_for_controller(sender, payload, reaction_decider=_prompt_reaction)
        print(present_encounter_snapshot(result.view))
        print()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Manual encounter harness for the deterministic D&D 2024 encounter slice.')
    parser.add_argument('--command', action='append', default=[], help='Execute a command non-interactively. Prefix with `system:`, `dm:`, or `player-1-controller:` when needed.')
    parser.add_argument('--commands-file', type=Path, help='Read commands from a text file, one per line.')
    parser.add_argument('--print-example', action='store_true', help='Print example commands and exit.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_example:
        print('Example commands:')
        for command in EXAMPLE_COMMANDS:
            print(command)
        return 0

    commands = list(args.command)
    if args.commands_file is not None:
        commands.extend(args.commands_file.read_text(encoding='utf-8').splitlines())

    try:
        session = build_session()
    except (ContentLoadError, CharacterCreationError, EncounterError) as exc:
        print(f'ERROR: {exc}')
        print('The encounter harness only uses the configured mirror and a real CharacterRecord built through the character-creation subsystem.')
        return 1

    print('Encounter manual test harness')
    print('Mode: configured mirror')
    print('Data source: FIVEETOOLS_MIRROR_BASE_URL from .env through the real loaders.')
    print('Controllers: system, dm, player-1-controller')
    print('Ownership: DM owns all monsters; Player 1 owns player-1; system starts the encounter and routes prompts.')
    print("Use `use <controller>` to switch context, `view <controller>` to inspect a filtered view, or `controllers` to list contexts.")
    print()

    if commands:
        try:
            execute_commands(session, commands)
            return 0
        except EncounterError as exc:
            print(f'ERROR: {exc}')
            return 1

    while True:
        try:
            command = input('> ').strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not command:
            continue
        if command.lower() in {'exit', 'quit'}:
            return 0
        if command.lower() == 'example':
            print()
            for example_command in EXAMPLE_COMMANDS:
                print(example_command)
            print()
            continue
        try:
            execute_commands(session, (command,))
        except EncounterError as exc:
            print(f'ERROR: {exc}')
            print()


if __name__ == '__main__':
    raise SystemExit(main())
