from __future__ import annotations

from pathlib import Path
import unittest

from character_creation import build_default_kernel
from monster_runtime import build_default_monster_runtime
from player_interface import MonsterSlashCommandInterface, SlashCommandInterface
from shared_types.models import Ability


LOCAL_MIRROR_BASE_URL = Path("D:/5etools-mirror-2.github.io").resolve().as_uri().rstrip("/") + "/"


class MonsterPipelineTests(unittest.TestCase):
    def _build_player_record(self):
        kernel = build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)
        ui = SlashCommandInterface(kernel)
        state = kernel.new_state()
        for command in (
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
        ):
            state, _ = ui.execute(state, command)
        assert state.character_record is not None
        return state.character_record

    def _build_runtime(self):
        return build_default_monster_runtime(base_url=LOCAL_MIRROR_BASE_URL)

    def test_monster_catalog_exposes_local_official_content(self) -> None:
        runtime = self._build_runtime()
        monsters = runtime.list_monsters()
        self.assertTrue(monsters)
        self.assertTrue(any(record.name == "Skeleton" and record.source == "XMM" for record in monsters))
        self.assertTrue(any(record.source not in {"PHB", "XMM"} for record in runtime.monster_catalog.monsters.values()))
        self.assertTrue(all(record.source != "PHB" for record in runtime.monster_catalog.monsters.values()))

    def test_monster_inspection_and_runtime_compilation_work(self) -> None:
        runtime = self._build_runtime()
        mage = next(record for record in runtime.monster_catalog.monsters.values() if record.name == "Mage" and record.source == "XMM")
        inspected = runtime.inspect_monster(mage.record_id)
        self.assertEqual(inspected.record_id, mage.record_id)
        actor = runtime.compile_monster(monster_id=mage.record_id, actor_id="monster-mage-1")
        self.assertEqual(actor.actor_id, "monster-mage-1")
        self.assertEqual(actor.name, "Mage")
        self.assertEqual(actor.ability_modifiers[Ability.DEX], 2)
        self.assertIn("misty-step", actor.spells)

    def test_monster_compilation_keeps_capability_mapped_spells_without_legacy_effect_type(self) -> None:
        runtime = self._build_runtime()
        artificer = next(record for record in runtime.monster_catalog.monsters.values() if record.name == "Cannith Artificer" and record.source == "EFA")
        actor = runtime.compile_monster(monster_id=artificer.record_id, actor_id="monster-artificer-1")
        self.assertIn("cure-wounds", actor.spells)
        self.assertIn("thunderwave", actor.spells)
        self.assertIsNotNone(actor.spells["cure-wounds"].capability)
        self.assertIsNone(actor.spells["cure-wounds"].effect_type)

    def test_user_style_monster_commands_cover_list_inspect_and_compile(self) -> None:
        runtime = self._build_runtime()
        player_record = self._build_player_record()
        ui = MonsterSlashCommandInterface(runtime, player_record=player_record)
        list_output = ui.execute("/monster list")
        self.assertIn("Monsters:", list_output)
        self.assertIn("mage-xmm", list_output)
        inspect_output = ui.execute("/monster inspect mage-xmm")
        self.assertIn("Monster: Mage", inspect_output)
        monster_actor_output = ui.execute("/monster compile mage-xmm")
        self.assertIn("Actor: Mage", monster_actor_output)
        player_actor_output = ui.execute("/monster compile-player")
        self.assertIn("Actor: PC level-1-character", player_actor_output)


if __name__ == "__main__":
    unittest.main()

