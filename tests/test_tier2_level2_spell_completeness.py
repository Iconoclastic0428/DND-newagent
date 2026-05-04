from __future__ import annotations

import json
from pathlib import Path
import unittest


MIRROR_ROOT = Path('D:/5etools-mirror-2.github.io')
REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / 'content' / 'manifests' / 'tier2_level2_spells_manifest.json'
SUPPORT_MATRIX_PATH = REPO_ROOT / 'content' / 'manifests' / 'tier2_support_matrix.json'
REQUIRED_IMPLEMENTATION_SECTIONS = (
    '## Source of Truth',
    '## Implementation Family',
    '## Runtime Behavior',
    '## Item-Specific Edge Cases',
    '## Test Matrix',
    '## Dependencies',
)


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


def _expected_level2_spells() -> set[str]:
    spells = _load_json(MIRROR_ROOT / 'data' / 'spells' / 'spells-xphb.json')['spell']
    result: set[str] = set()
    for spell in spells:
        if not isinstance(spell, dict):
            continue
        if spell.get('source') != 'XPHB' or spell.get('level') != 2:
            continue
        result.add(_canonical_name(spell))
    return result


class Tier2Level2SpellCompletenessTests(unittest.TestCase):
    def _manifest(self) -> dict[str, object]:
        return _load_json(MANIFEST_PATH)

    def _support_matrix(self) -> dict[str, object]:
        return _load_json(SUPPORT_MATRIX_PATH)

    def test_manifest_contains_every_xphb_level2_spell(self) -> None:
        manifest = self._manifest()
        actual = {entry['display_name'] for entry in manifest['entries'] if entry['category'] == 'spell' and entry['level'] == 2}
        self.assertSetEqual(actual, _expected_level2_spells())

    def test_support_matrix_matches_manifest_spell_set(self) -> None:
        manifest = self._manifest()
        support = self._support_matrix()
        manifest_names = {entry['display_name'] for entry in manifest['entries']}
        support_names = {entry['display_name'] for entry in support['entries']}
        self.assertSetEqual(manifest_names, support_names)

    def test_implemented_entries_have_required_files(self) -> None:
        manifest = self._manifest()
        for entry in manifest['entries']:
            runtime_status = entry['runtime_status']
            if runtime_status not in {'deterministic-capability', 'story-adjudicated'}:
                continue
            owning_directory = REPO_ROOT / entry['owning_directory']
            self.assertTrue(owning_directory.is_dir(), f"Missing directory for {entry['display_name']}: {owning_directory}")
            for filename in ('definition.json', 'executor.py', 'registry.json', 'README.md', 'IMPLEMENTATION.md'):
                path = owning_directory / filename
                self.assertTrue(path.is_file(), f"Missing {filename} for {entry['display_name']}: {path}")
            test_path = REPO_ROOT / entry['test_path']
            self.assertTrue(test_path.is_file(), f"Missing test file for {entry['display_name']}: {test_path}")

    def test_implementation_docs_have_required_sections(self) -> None:
        manifest = self._manifest()
        for entry in manifest['entries']:
            runtime_status = entry['runtime_status']
            if runtime_status not in {'deterministic-capability', 'story-adjudicated'}:
                continue
            doc_path = REPO_ROOT / entry['owning_directory'] / 'IMPLEMENTATION.md'
            content = doc_path.read_text(encoding='utf-8')
            for section in REQUIRED_IMPLEMENTATION_SECTIONS:
                self.assertIn(section, content, f"{doc_path} is missing section {section!r}")

    def test_implemented_entries_have_executor_wiring(self) -> None:
        manifest = self._manifest()
        for entry in manifest['entries']:
            runtime_status = entry['runtime_status']
            if runtime_status not in {'deterministic-capability', 'story-adjudicated'}:
                continue
            executor_path = REPO_ROOT / entry['owning_directory'] / 'executor.py'
            content = executor_path.read_text(encoding='utf-8')
            self.assertIn('build_capability_definition', content, f"{executor_path} is missing build_capability_definition")


if __name__ == '__main__':
    unittest.main()
