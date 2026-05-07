from __future__ import annotations

from dataclasses import dataclass

from character_creation import build_default_kernel
from shared_types.encounter_models import CharacterPlacement, EncounterContentCatalog, EncounterPolicy, GridPosition, MonsterPlacement, MonsterRecord, RuntimeActorState
from shared_types.errors import MonsterValidationError
from shared_types.models import CharacterRecord, SourcePolicy

from rules_engine.env import load_env
from rules_engine.fiveetools_loader import DocumentFetcher
from rules_engine.monster_loader import load_monster_catalog

from .compiler import compile_monster_actor, compile_player_actor


DEFAULT_MIRROR_BASE_URL = "5etools-mirror-2.github.io/"


@dataclass
class MonsterRuntimeServices:
    character_catalog: object
    monster_catalog: EncounterContentCatalog

    def list_monsters(self, *, limit: int | None = None) -> tuple[MonsterRecord, ...]:
        records = tuple(sorted(self.monster_catalog.monsters.values(), key=lambda record: (record.name, record.source, record.record_id)))
        if limit is not None:
            return records[:limit]
        return records

    def inspect_monster(self, monster_id: str) -> MonsterRecord:
        monster = self.monster_catalog.monsters.get(monster_id)
        if monster is None:
            raise MonsterValidationError(f"Monster {monster_id!r} is not available under the active monster policy.")
        return monster

    def compile_monster(self, *, monster_id: str, actor_id: str = "monster-1", position: GridPosition | None = None) -> RuntimeActorState:
        return compile_monster_actor(
            MonsterPlacement(actor_id=actor_id, monster_id=monster_id, position=position or GridPosition(0, 0)),
            monster_catalog=self.monster_catalog,
        )

    def compile_player(self, *, record: CharacterRecord, actor_id: str = "player-1", position: GridPosition | None = None) -> RuntimeActorState:
        return compile_player_actor(
            CharacterPlacement(actor_id=actor_id, record=record, position=position or GridPosition(0, 0)),
            character_catalog=self.character_catalog,
            encounter_catalog=self.monster_catalog,
        )


def build_default_monster_runtime(
    *,
    base_url: str | None = None,
    monster_policy: EncounterPolicy | None = None,
    character_policy: SourcePolicy | None = None,
    document_fetcher: DocumentFetcher | None = None,
) -> MonsterRuntimeServices:
    env = load_env()
    mirror_base_url = base_url or env.get("FIVEETOOLS_MIRROR_BASE_URL", DEFAULT_MIRROR_BASE_URL)
    character_kernel = build_default_kernel(base_url=mirror_base_url, policy=character_policy, document_fetcher=document_fetcher)
    active_policy = monster_policy or EncounterPolicy()
    monster_catalog = load_monster_catalog(mirror_base_url, active_policy, document_fetcher=document_fetcher)
    return MonsterRuntimeServices(
        character_catalog=character_kernel.catalog,
        monster_catalog=monster_catalog,
    )
