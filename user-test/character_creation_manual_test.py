from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from shared_types.errors import CharacterCreationError, ContentLoadError


EXAMPLE_COMMANDS: tuple[str, ...] = (
    "/create policy show",
    "/create begin",
    "/create summary",
    "/create inspect species dwarf",
    "/create choose species dwarf",
    "/create inspect class wizard",
    "/create choose class wizard",
    "/create choose class-skills Arcana History",
    "/create inspect background acolyte",
    "/create choose background acolyte",
    "/create choose choice class:wizard:cantrips fire-bolt mage-hand light",
    "/create choose choice class:wizard:spells magic-missile shield detect-magic charm-person",
    "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:ability WIS",
    "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:cantrips guidance resistance",
    "/create choose choice background:acolyte:origin-feat:magic-initiate-spellcasting:spell cure-wounds",
    "/create ability generate point-buy 15 14 13 12 10 8",
    "/create ability assign 8 14 13 15 12 10",
    "/create background-asi choose acolyte-int2-wis1",
    "/create equipment background gold",
    "/create equipment class package wizard-package-1",
    "/create equipment buy spear 1",
    "/create summary",
    "/create confirm",
)


def build_kernel():
    return build_default_kernel()


def execute_commands(ui: SlashCommandInterface, state, commands: Iterable[str]):
    for raw_command in commands:
        command = raw_command.strip()
        if not command:
            continue
        print(f"> {command}")
        state, output = ui.execute(state, command)
        print(output)
        if state.character_record is not None:
            print()
            print("Final CharacterRecord:")
            print(state.character_record)
        print()
    return state


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Manual slash-command harness for the deterministic D&D 2024 character creation kernel."
    )
    parser.add_argument(
        "--command",
        action="append",
        default=[],
        help="Execute a slash command non-interactively. Repeat for multiple commands.",
    )
    parser.add_argument(
        "--commands-file",
        type=Path,
        help="Read slash commands from a text file, one per line.",
    )
    parser.add_argument(
        "--print-example",
        action="store_true",
        help="Print an example command sequence and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.print_example:
        print("Example commands:")
        for command in EXAMPLE_COMMANDS:
            print(command)
        return 0

    command_batch: list[str] = list(args.command)
    if args.commands_file is not None:
        command_batch.extend(args.commands_file.read_text(encoding="utf-8").splitlines())

    try:
        kernel = build_kernel()
    except ContentLoadError as exc:
        print(f"ERROR: {exc}")
        print("The manual harness only uses the configured production mirror from FIVEETOOLS_MIRROR_BASE_URL.")
        return 1

    ui = SlashCommandInterface(kernel)
    state = kernel.new_state()

    print("Character creation manual test harness")
    print("Mode: configured mirror")
    print("Data source: FIVEETOOLS_MIRROR_BASE_URL from .env through the real loader.")
    print("Type /create ... commands, 'example' to print a working flow, or 'exit' to quit.")
    print()

    if command_batch:
        try:
            execute_commands(ui, state, command_batch)
            return 0
        except CharacterCreationError as exc:
            print(f"ERROR: {exc}")
            return 1

    while True:
        try:
            command = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0

        if not command:
            continue
        if command.lower() in {"exit", "quit"}:
            return 0
        if command.lower() == "example":
            print()
            for example_command in EXAMPLE_COMMANDS:
                print(example_command)
            print()
            continue

        try:
            state, output = ui.execute(state, command)
            print(output)
            if state.character_record is not None:
                print()
                print("Final CharacterRecord:")
                print(state.character_record)
            print()
        except CharacterCreationError as exc:
            print(f"ERROR: {exc}")
            print()


if __name__ == "__main__":
    raise SystemExit(main())


