from __future__ import annotations

import json
from pathlib import Path
import unittest

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from encounter_runtime import build_default_encounter_runtime
from shared_types.encounter_models import GridPosition
from shared_types.models import CreationPhase
from rules_engine.xphb_level1_registry import (
    load_cantrip_manifest,
    load_level1_class_feature_manifest,
    load_level1_spell_manifest,
    load_level1_support_matrix,
)


LOCAL_MIRROR_BASE_URL = Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'
REPO_ROOT = Path(__file__).resolve().parents[1]
CONTENT_ROOT = REPO_ROOT / 'content' / 'xphb'
MANIFEST_ROOT = CONTENT_ROOT / 'manifests'

EXPECTED_CANTRIPS = {
    'Acid Splash',
    'Blade Ward',
    'Chill Touch',
    'Dancing Lights',
    'Druidcraft',
    'Eldritch Blast',
    'Elementalism',
    'Fire Bolt',
    'Friends',
    'Guidance',
    'Light',
    'Mage Hand',
    'Mending',
    'Message',
    'Mind Sliver',
    'Minor Illusion',
    'Poison Spray',
    'Prestidigitation',
    'Produce Flame',
    'Ray of Frost',
    'Resistance',
    'Sacred Flame',
    'Shillelagh',
    'Shocking Grasp',
    'Sorcerous Burst',
    'Spare the Dying',
    'Starry Wisp',
    'Thaumaturgy',
    'Thorn Whip',
    'Thunderclap',
    'Toll the Dead',
    'True Strike',
    'Vicious Mockery',
    'Word of Radiance',
}

EXPECTED_LEVEL1_SPELLS = {
    'Alarm',
    'Animal Friendship',
    'Armor of Agathys',
    'Arms of Hadar',
    'Bane',
    'Bless',
    'Burning Hands',
    'Charm Person',
    'Chromatic Orb',
    'Color Spray',
    'Command',
    'Compelled Duel',
    'Comprehend Languages',
    'Create or Destroy Water',
    'Cure Wounds',
    'Detect Evil and Good',
    'Detect Magic',
    'Detect Poison and Disease',
    'Disguise Self',
    'Dissonant Whispers',
    'Divine Favor',
    'Divine Smite',
    'Ensnaring Strike',
    'Entangle',
    'Expeditious Retreat',
    'Faerie Fire',
    'False Life',
    'Feather Fall',
    'Find Familiar',
    'Fog Cloud',
    'Goodberry',
    'Grease',
    'Guiding Bolt',
    'Hail of Thorns',
    'Healing Word',
    'Hellish Rebuke',
    'Heroism',
    'Hex',
    "Hunter's Mark",
    'Ice Knife',
    'Identify',
    'Illusory Script',
    'Inflict Wounds',
    'Jump',
    'Longstrider',
    'Mage Armor',
    'Magic Missile',
    'Protection from Evil and Good',
    'Purify Food and Drink',
    'Ray of Sickness',
    'Sanctuary',
    'Searing Smite',
    'Shield',
    'Shield of Faith',
    'Silent Image',
    'Sleep',
    'Speak with Animals',
    "Tasha's Hideous Laughter",
    "Tenser's Floating Disk",
    'Thunderous Smite',
    'Thunderwave',
    'Unseen Servant',
    'Witch Bolt',
    'Wrathful Smite',
}

EXPECTED_CLASS_FEATURES = {
    ('barbarian', 'Rage'),
    ('barbarian', 'Unarmored Defense'),
    ('barbarian', 'Weapon Mastery'),
    ('bard', 'Bardic Inspiration'),
    ('bard', 'Spellcasting'),
    ('cleric', 'Spellcasting'),
    ('cleric', 'Divine Order'),
    ('druid', 'Druidic'),
    ('druid', 'Primal Order'),
    ('druid', 'Spellcasting'),
    ('fighter', 'Fighting Style'),
    ('fighter', 'Second Wind'),
    ('fighter', 'Weapon Mastery'),
    ('monk', 'Martial Arts'),
    ('monk', 'Unarmored Defense'),
    ('paladin', 'Lay on Hands'),
    ('paladin', 'Spellcasting'),
    ('paladin', 'Weapon Mastery'),
    ('ranger', 'Spellcasting'),
    ('ranger', 'Favored Enemy'),
    ('ranger', 'Weapon Mastery'),
    ('rogue', 'Expertise'),
    ('rogue', 'Sneak Attack'),
    ('rogue', "Thieves' Cant"),
    ('rogue', 'Weapon Mastery'),
    ('sorcerer', 'Spellcasting'),
    ('sorcerer', 'Innate Sorcery'),
    ('warlock', 'Eldritch Invocations'),
    ('warlock', 'Pact Magic'),
    ('warlock', 'Eldritch Invocation Options'),
    ('wizard', 'Spellcasting'),
    ('wizard', 'Ritual Adept'),
    ('wizard', 'Arcane Recovery'),
}


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8'))


def _manifest_path(filename: str) -> Path:
    return MANIFEST_ROOT / filename


def _assert_folder_has_required_files(testcase: unittest.TestCase, folder: Path, *, require_options: bool = False) -> None:
    testcase.assertTrue(folder.is_dir(), f'Missing content folder: {folder}')
    for filename in ('metadata.json', 'implementation.json', 'README.md'):
        testcase.assertTrue((folder / filename).is_file(), f'Missing required file {filename!r} in {folder}')
    if require_options:
        options_path = folder / 'options.json'
        testcase.assertTrue(options_path.is_file(), f'Covered option folder is missing options.json: {folder}')
        payload = _load_json(options_path)
        testcase.assertIn('options', payload)
        testcase.assertTrue(payload['options'], f'Covered option folder has an empty options list: {folder}')


def _assert_cantrip_folder_metadata_matches_manifest(testcase: unittest.TestCase, entry: dict[str, object]) -> None:
    folder = CONTENT_ROOT / str(entry['implementation_path'])
    _assert_folder_has_required_files(testcase, folder)
    metadata = _load_json(folder / 'metadata.json')
    implementation = _load_json(folder / 'implementation.json')
    testcase.assertEqual(metadata['content_id'], entry['content_id'])
    testcase.assertEqual(metadata['display_name'], entry['display_name'])
    testcase.assertEqual(metadata['runtime_status'], entry['runtime_status'])
    testcase.assertEqual(implementation['runtime_support_mode'], entry['runtime_status'])
    testcase.assertIn('tests.test_xphb_level1_content_pack', implementation['test_refs'])


class XphbLevel1ContentPackTests(unittest.TestCase):
    def _build_kernel(self):
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

    def _complete_record(self, class_id: str, *, assign_command: str = '/create ability assign 15 14 13 12 10 8', overrides: dict[str, tuple[str, ...]] | None = None):
        kernel = self._build_kernel()
        ui = SlashCommandInterface(kernel)
        state = kernel.new_state()
        background_id = next(record_id for record_id, record in kernel.catalog.backgrounds.items() if record.name == 'Acolyte' and record.source == 'XPHB')
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

    def test_manifest_loaders_read_all_content_manifests(self) -> None:
        cantrips = load_cantrip_manifest()
        spells = load_level1_spell_manifest()
        class_features = load_level1_class_feature_manifest()
        support_matrix = load_level1_support_matrix()

        self.assertEqual(cantrips.count, 34)
        self.assertEqual(spells.count, 64)
        self.assertEqual(class_features.count, 33)
        self.assertEqual(support_matrix.count, 131)

    def test_manifest_and_support_matrix_target_sets_match_the_required_xphb_lists(self) -> None:
        support_matrix = load_level1_support_matrix()
        cantrip_names = {entry.display_name for entry in support_matrix.entries if entry.category == 'cantrip'}
        spell_names = {entry.display_name for entry in support_matrix.entries if entry.category == 'spell'}
        class_feature_names = {(entry.class_id or '', entry.display_name) for entry in support_matrix.entries if entry.category == 'class-feature'}

        self.assertSetEqual(cantrip_names, EXPECTED_CANTRIPS)
        self.assertSetEqual(spell_names, EXPECTED_LEVEL1_SPELLS)
        self.assertSetEqual(class_feature_names, EXPECTED_CLASS_FEATURES)

    def test_support_matrix_entries_point_to_real_folders_and_required_files(self) -> None:
        support_matrix = load_level1_support_matrix()
        for entry in support_matrix.entries:
            with self.subTest(content_id=entry.content_id):
                folder = Path(entry.implementation_path)
                self.assertTrue(folder.exists(), f'Implementation folder missing: {folder}')
                self.assertTrue(folder.is_dir(), f'Implementation path is not a folder: {folder}')
                self.assertEqual(entry.blocker_status, 'none')
                _assert_folder_has_required_files(self, folder, require_options=(entry.option_coverage_status == 'covered'))

    def test_registry_loaders_are_able_to_read_the_manifest_files(self) -> None:
        cantrip_manifest = _load_json(_manifest_path('xphb-cantrips.json'))
        spell_manifest = _load_json(_manifest_path('xphb-level1-spells.json'))
        class_feature_manifest = _load_json(_manifest_path('xphb-level1-class-features.json'))
        support_matrix_manifest = _load_json(_manifest_path('xphb-level1-support-matrix.json'))

        self.assertEqual(cantrip_manifest['source'], 'XPHB')
        self.assertEqual(spell_manifest['source'], 'XPHB')
        self.assertEqual(class_feature_manifest['source'], 'XPHB')
        self.assertEqual(support_matrix_manifest['source'], 'XPHB')
        self.assertEqual(len(cantrip_manifest['entries']), 34)
        self.assertEqual(len(spell_manifest['entries']), 64)
        self.assertEqual(len(class_feature_manifest['entries']), 33)
        self.assertEqual(len(support_matrix_manifest['entries']), 131)

    def test_every_cantrip_folder_matches_the_manifest_and_has_required_files(self) -> None:
        manifest = _load_json(_manifest_path('xphb-cantrips.json'))
        self.assertEqual(len(manifest['entries']), 34)
        for entry in manifest['entries']:
            self.assertEqual(entry['source_id'], 'XPHB')
            self.assertEqual(entry['category'], 'cantrip')
            _assert_cantrip_folder_metadata_matches_manifest(self, entry)

    def test_runtime_compilation_exposes_representative_level_one_feature_support(self) -> None:
        runtime = build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)

        bard_record = self._complete_record('bard')
        bard_actor = runtime.monster_runtime.compile_player(record=bard_record, actor_id='bard-pc', position=GridPosition(0, 0, 0))
        self.assertIn('bardic-inspiration', bard_actor.capabilities)

        monk_record = self._complete_record('monk', assign_command='/create ability assign 8 15 13 10 14 12')
        monk_actor = runtime.monster_runtime.compile_player(record=monk_record, actor_id='monk-pc', position=GridPosition(0, 0, 0))
        self.assertEqual(monk_actor.effective_armor_class, 14)
        self.assertEqual(monk_actor.attacks['unarmed-strike'].damage_die_faces, 6)

        paladin_record = self._complete_record('paladin')
        paladin_actor = runtime.monster_runtime.compile_player(record=paladin_record, actor_id='paladin-pc', position=GridPosition(0, 0, 0))
        self.assertIn('lay-on-hands', paladin_actor.resource_pools)
        self.assertEqual(paladin_actor.resource_pools['lay-on-hands'].current, 5)

        ranger_record = self._complete_record('ranger')
        ranger_actor = runtime.monster_runtime.compile_player(record=ranger_record, actor_id='ranger-pc', position=GridPosition(0, 0, 0))
        self.assertIn('hunter-s-mark', ranger_actor.spells)
        self.assertIn('favored-enemy-hunters-mark', ranger_actor.resource_pools)

        rogue_record = self._complete_record('rogue', overrides={
            'class:rogue:expertise': ('acrobatics', 'thieves-tools'),
            'class:rogue:weapon-mastery': ('dagger', 'shortbow'),
        })
        rogue_actor = runtime.monster_runtime.compile_player(record=rogue_record, actor_id='rogue-pc', position=GridPosition(0, 0, 0))
        self.assertEqual(rogue_actor.skill_bonuses['Acrobatics'], 6)

        sorcerer_record = self._complete_record('sorcerer')
        sorcerer_actor = runtime.monster_runtime.compile_player(record=sorcerer_record, actor_id='sorcerer-pc', position=GridPosition(0, 0, 0))
        self.assertIn('innate-sorcery', sorcerer_actor.capabilities)

        wizard_record = self._complete_record('wizard')
        wizard_actor = runtime.monster_runtime.compile_player(record=wizard_record, actor_id='wizard-pc', position=GridPosition(0, 0, 0))
        self.assertIn('arcane-recovery', wizard_actor.resource_pools)

    def test_every_xphb_level0_and_level1_spell_has_runtime_support_in_the_encounter_catalog(self) -> None:
        runtime = build_default_encounter_runtime(base_url=LOCAL_MIRROR_BASE_URL)
        xphb_spells = [
            spell
            for spell in runtime.encounter_catalog.spells.values()
            if spell.source == 'XPHB' and spell.level in {0, 1}
        ]
        self.assertEqual(len(xphb_spells), 98)
        for spell in xphb_spells:
            with self.subTest(spell=spell.name):
                self.assertIsNotNone(spell.runtime_support)



if __name__ == '__main__':
    unittest.main()
