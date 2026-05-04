from __future__ import annotations

from dataclasses import dataclass

from monster_runtime import build_default_monster_runtime
from rules_engine.starter_content import ensure_special_spell_items
from shared_types.battlefield import BattlefieldState
from shared_types.encounter_control import ControllerBinding
from shared_types.encounter_models import CharacterPlacement, EncounterPolicy, GridPosition, MonsterPlacement
from shared_types.models import SourcePolicy

from rules_engine.env import load_env
from rules_engine.fiveetools_loader import DocumentFetcher

from .control import EncounterControlRuntime
from .kernel import EncounterKernel


@dataclass
class EncounterRuntimeServices:
    kernel: EncounterKernel
    monster_runtime: object

    @property
    def character_catalog(self):
        return self.monster_runtime.character_catalog

    @property
    def encounter_catalog(self):
        return self.monster_runtime.monster_catalog

    def _surface_position(self, battlefield: BattlefieldState | None, position: GridPosition) -> GridPosition:
        if battlefield is None or not battlefield.has_authored_map:
            return position
        tile = battlefield.tiles.get(GridPosition(position.x, position.y))
        if tile is None:
            return position
        if position.z != 0:
            return position
        return GridPosition(position.x, position.y, tile.elevation_ft)

    def new_state(
        self,
        *,
        characters: tuple[CharacterPlacement, ...],
        monsters: tuple[MonsterPlacement, ...],
        battlefield: BattlefieldState | None = None,
    ):
        actors = {}
        for placement in characters:
            actors[placement.actor_id] = self.monster_runtime.compile_player(
                record=placement.record,
                actor_id=placement.actor_id,
                position=self._surface_position(battlefield, placement.position),
            )
        for placement in monsters:
            actors[placement.actor_id] = self.monster_runtime.compile_monster(
                monster_id=placement.monster_id,
                actor_id=placement.actor_id,
                position=self._surface_position(battlefield, placement.position),
            )
        return self.kernel.new_state(actors, battlefield=battlefield)

    def build_control_runtime(
        self,
        *,
        controllers: dict[str, ControllerBinding],
        actor_controllers: dict[str, str],
        dm_override_enabled: bool = False,
    ) -> EncounterControlRuntime:
        return EncounterControlRuntime(
            kernel=self.kernel,
            controllers=controllers,
            actor_controllers=actor_controllers,
            dm_override_enabled=dm_override_enabled,
        )


def build_default_encounter_runtime(
    *,
    base_url: str | None = None,
    encounter_policy: EncounterPolicy | None = None,
    character_policy: SourcePolicy | None = None,
    document_fetcher: DocumentFetcher | None = None,
) -> EncounterRuntimeServices:
    env = load_env()
    seed = env.get('DND_DETERMINISTIC_SEED', 'missing-seed')
    monster_runtime = build_default_monster_runtime(
        base_url=base_url,
        monster_policy=encounter_policy,
        character_policy=character_policy,
        document_fetcher=document_fetcher,
    )
    ensure_special_spell_items(monster_runtime.character_catalog.items)
    return EncounterRuntimeServices(
        kernel=EncounterKernel(seed=seed, item_catalog=monster_runtime.character_catalog.items, monster_runtime=monster_runtime),
        monster_runtime=monster_runtime,
    )
