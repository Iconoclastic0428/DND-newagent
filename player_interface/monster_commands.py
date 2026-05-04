from __future__ import annotations

from monster_runtime import MonsterRuntimeServices
from shared_types.errors import MonsterValidationError, UnknownMonsterCommandError
from shared_types.models import CharacterRecord

from .monster_presenter import present_monster_inspection, present_monster_list, present_runtime_actor


class MonsterSlashCommandInterface:
    def __init__(self, runtime: MonsterRuntimeServices, *, player_record: CharacterRecord | None = None) -> None:
        self.runtime = runtime
        self.player_record = player_record

    def execute(self, command: str) -> str:
        tokens = command.strip().split()
        if not tokens:
            raise UnknownMonsterCommandError("Empty command.")
        if tokens[0] != "/monster":
            raise UnknownMonsterCommandError("Monster commands must start with /monster.")
        if len(tokens) == 2 and tokens[1] == "list":
            return present_monster_list(self.runtime.list_monsters())
        if len(tokens) == 3 and tokens[1] == "inspect":
            return present_monster_inspection(self.runtime.inspect_monster(tokens[2]))
        if len(tokens) == 3 and tokens[1] == "compile":
            actor = self.runtime.compile_monster(monster_id=tokens[2])
            return present_runtime_actor(actor)
        if len(tokens) == 2 and tokens[1] == "compile-player":
            if self.player_record is None:
                raise MonsterValidationError("No player record is available for runtime compilation.")
            actor = self.runtime.compile_player(record=self.player_record)
            return present_runtime_actor(actor)
        raise UnknownMonsterCommandError("Unknown monster command.")

