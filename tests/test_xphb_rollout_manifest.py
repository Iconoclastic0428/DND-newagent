from __future__ import annotations

import json
from pathlib import Path
import unittest

from shared_types.models import slugify


MIRROR_ROOT = Path('D:/5etools-mirror-2.github.io')
MANIFEST_PATH = Path(__file__).resolve().parents[1] / 'docs' / 'xphb-rollout-manifest.json'



def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _canonical_name(record: dict[str, object]) -> str:
    english_name = record.get('ENG_name')
    if isinstance(english_name, str) and english_name.strip():
        return english_name.strip()
    raw_name = record.get('name')
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    raise AssertionError(f'Record missing canonical name: {record!r}')


def _expected_weapons() -> set[tuple[str, str]]:
    items = _load_json(MIRROR_ROOT / 'data' / 'items-base.json')['baseitem']
    result: set[tuple[str, str]] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get('source') != 'XPHB' or not item.get('weapon'):
            continue
        raw_type = item.get('type')
        raw_category = item.get('weaponCategory')
        if not isinstance(raw_type, str) or not isinstance(raw_category, str):
            continue
        item_type = raw_type.split('|', 1)[0]
        category = raw_category.split('|', 1)[0]
        if item_type == 'M' and category == 'simple':
            subtype = 'simple-melee'
        elif item_type == 'R' and category == 'simple':
            subtype = 'simple-ranged'
        elif item_type == 'M' and category == 'martial':
            subtype = 'martial-melee'
        elif item_type == 'R' and category == 'martial':
            subtype = 'martial-ranged'
        else:
            continue
        result.add((_canonical_name(item), subtype))
    return result


def _expected_ammunition_refs() -> set[str]:
    items = _load_json(MIRROR_ROOT / 'data' / 'items-base.json')['baseitem']
    result: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        if item.get('source') != 'XPHB' or not item.get('weapon'):
            continue
        ammo_type = item.get('ammoType')
        if not isinstance(ammo_type, str) or not ammo_type.strip():
            continue
        result.add(ammo_type.split('|', 1)[0].strip())
    return result


def _expected_spells() -> set[tuple[str, str]]:
    spells = _load_json(MIRROR_ROOT / 'data' / 'spells' / 'spells-xphb.json')['spell']
    result: set[tuple[str, str]] = set()
    for spell in spells:
        if not isinstance(spell, dict):
            continue
        if spell.get('source') != 'XPHB':
            continue
        level = spell.get('level')
        if level not in {0, 1}:
            continue
        subtype = 'cantrip' if level == 0 else 'spell-level-1'
        result.add((_canonical_name(spell), subtype))
    return result


def _expected_level_one_class_features() -> set[tuple[str, str]]:
    class_root = MIRROR_ROOT / 'data' / 'class'
    class_name_map: dict[str, str] = {}
    result: set[tuple[str, str]] = set()
    for path in sorted(class_root.glob('class-*.json')):
        payload = _load_json(path)
        for cls in payload.get('class', []):
            if not isinstance(cls, dict):
                continue
            if cls.get('source') != 'XPHB':
                continue
            raw_name = cls.get('name')
            if isinstance(raw_name, str) and raw_name.strip():
                class_name_map[raw_name.strip()] = _canonical_name(cls)
        for feature in payload.get('classFeature', []):
            if not isinstance(feature, dict):
                continue
            if feature.get('source') != 'XPHB' or feature.get('classSource') != 'XPHB' or feature.get('level') != 1:
                continue
            raw_class_name = str(feature.get('className', '')).strip()
            class_name = class_name_map.get(raw_class_name, raw_class_name)
            result.add((slugify(class_name), _canonical_name(feature)))
    return result


class XphbRolloutManifestTests(unittest.TestCase):
    def _manifest(self) -> dict[str, object]:
        return _load_json(MANIFEST_PATH)

    def test_manifest_summary_matches_local_mirror_counts(self) -> None:
        manifest = self._manifest()
        summary = manifest['summary']
        self.assertEqual(summary['weapon_count'], len(_expected_weapons()))
        self.assertEqual(summary['ammunition_count'], len(_expected_ammunition_refs()))
        expected_spells = _expected_spells()
        self.assertEqual(summary['cantrip_count'], sum(1 for _, subtype in expected_spells if subtype == 'cantrip'))
        self.assertEqual(summary['spell_level_1_count'], sum(1 for _, subtype in expected_spells if subtype == 'spell-level-1'))
        self.assertEqual(summary['class_feature_count'], len(_expected_level_one_class_features()))

    def test_manifest_contains_every_xphb_weapon_target(self) -> None:
        manifest = self._manifest()
        actual = {
            (entry['entry_name'], entry['subtype'])
            for entry in manifest['entries']
            if entry['content_type'] == 'weapon'
        }
        self.assertSetEqual(actual, _expected_weapons())

    def test_manifest_contains_every_required_ammunition_target(self) -> None:
        manifest = self._manifest()
        actual = {
            entry['entry_name']
            for entry in manifest['entries']
            if entry['content_type'] == 'ammunition'
        }
        self.assertSetEqual(actual, _expected_ammunition_refs())

    def test_manifest_contains_every_xphb_cantrip_and_first_level_spell(self) -> None:
        manifest = self._manifest()
        actual = {
            (entry['entry_name'], entry['subtype'])
            for entry in manifest['entries']
            if entry['content_type'] == 'spell'
        }
        self.assertSetEqual(actual, _expected_spells())

    def test_manifest_contains_every_xphb_level_one_class_feature_record(self) -> None:
        manifest = self._manifest()
        actual = {
            (entry['class_id'], entry['entry_name'])
            for entry in manifest['entries']
            if entry['content_type'] == 'class-feature'
        }
        self.assertSetEqual(actual, _expected_level_one_class_features())

    def test_manifest_entry_ids_are_unique(self) -> None:
        manifest = self._manifest()
        entry_ids = [entry['entry_id'] for entry in manifest['entries']]
        self.assertEqual(len(entry_ids), len(set(entry_ids)))


if __name__ == '__main__':
    unittest.main()
