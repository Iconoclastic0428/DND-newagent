from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from shared_types.character_record_io import character_record_from_dict, character_record_to_dict, load_character_party, save_character_party
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class CharacterRecordIOTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = Path(__file__).resolve().parents[1] / '.character-record-io-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def _build_record(self):
        kernel = build_default_kernel(base_url=LOCAL_MIRROR_BASE_URL)
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
            '/create background-asi choose acolyte-wis2-cha1',
            '/create equipment background gold',
            '/create equipment class package wizard-package-1',
            '/create confirm',
        )
        for command in commands:
            state, _ = ui.execute(state, command)
        assert state.character_record is not None
        return state.character_record

    def test_character_record_round_trips_through_json_dict(self) -> None:
        record = self._build_record()
        reloaded = character_record_from_dict(character_record_to_dict(record))
        self.assertEqual(reloaded.record_id, record.record_id)
        self.assertEqual(reloaded.ability_scores, record.ability_scores)
        self.assertEqual(reloaded.spell_selections, record.spell_selections)
        self.assertEqual(reloaded.feat_grants, record.feat_grants)
        self.assertEqual(reloaded.resolved_creation_choices, record.resolved_creation_choices)

    def test_character_party_save_and_load_preserves_controller_records(self) -> None:
        record = self._build_record()
        path = self._tempdir / 'party.json'
        save_character_party(
            path,
            {
                'player-1-controller': record,
                'player-2-controller': record,
            },
        )
        loaded = load_character_party(path)
        self.assertEqual(set(loaded), {'player-1-controller', 'player-2-controller'})
        self.assertEqual(loaded['player-1-controller'].ability_scores, record.ability_scores)


if __name__ == '__main__':
    unittest.main()
