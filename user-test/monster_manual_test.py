from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

from character_creation import build_default_kernel
from monster_runtime import build_default_monster_runtime
from player_interface import MonsterSlashCommandInterface, SlashCommandInterface
from shared_types.errors import CharacterCreationError, ContentLoadError, MonsterRuntimeError


EXAMPLE_COMMANDS: tuple[str, ...] = (
    "/monster list",
    "/monster inspect mage-xmm",
    "/monster compile mage-xmm",
    "/monster compile-player",
)


def build_character_record():
    kernel = build_default_kernel()
    ui = SlashCommandInterface(kernel)
    state = kernel.new_state()
    commands = (
        "/create begin",
        "/create choose species aasimar",
        "/create choose class wizard",
        "/create choose class-skills Arcana History",
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
        "/create confirm",
    )
    for command in commands:
        state, _ = ui.execute(state, command)
    if state.character_record is None:
        raise RuntimeError("Character creation did not produce a CharacterRecord.")
    return state.character_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Manual monster-pipeline harness for the deterministic D&D 2024 runtime.")
    parser.add_argument("--command", action="append", default=[], help="Execute a monster command non-interactively.")
    parser.add_argument("--print-example", action="store_true", help="Print example monster commands and exit.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.print_example:
        print("Example commands:")
        for command in EXAMPLE_COMMANDS:
            print(command)
        return 0

    try:
        runtime = build_default_monster_runtime()
        player_record = build_character_record()
    except (ContentLoadError, CharacterCreationError, MonsterRuntimeError) as exc:
        print(f"ERROR: {exc}")
        print("The monster harness only uses the configured local mirror and a real CharacterRecord built through the character-creation subsystem.")
        return 1

    ui = MonsterSlashCommandInterface(runtime, player_record=player_record)

    print("Monster manual test harness")
    print("Mode: configured local mirror")
    print("Data source: FIVEETOOLS_MIRROR_BASE_URL from .env through the real loaders.")
    print("Type monster commands, 'example' to print a flow, or 'exit' to quit.")
    print()

    if args.command:
        try:
            for command in args.command:
                print(f"> {command}")
                print(ui.execute(command))
                print()
            return 0
        except MonsterRuntimeError as exc:
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
            print(ui.execute(command))
            print()
        except MonsterRuntimeError as exc:
            print(f"ERROR: {exc}")
            print()


if __name__ == "__main__":
    raise SystemExit(main())

