from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / 'content' / 'manifests' / 'tier2_level2_spells_manifest.json'


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _load_test_module(path: Path):
    module_name = f"tier2_spell_test_{path.stem}_{abs(hash(str(path)))}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Could not load test module from {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _NoImplementedTier2Level2SpellTests(unittest.TestCase):
    @unittest.skip('No Tier-2 level-2 spells are marked deterministic-capability yet.')
    def test_no_implemented_tier2_level2_spells_yet(self) -> None:
        pass


def load_tests(loader: unittest.TestLoader, suite: unittest.TestSuite, pattern: str | None):
    manifest = _load_json(MANIFEST_PATH)
    aggregate = unittest.TestSuite()
    implemented_count = 0
    for entry in manifest.get('entries', []):
        if entry.get('runtime_status') != 'deterministic-capability':
            continue
        implemented_count += 1
        test_path = REPO_ROOT / str(entry['test_path'])
        if not test_path.is_file():
            raise AssertionError(f"Implemented spell is missing test file: {test_path}")
        module = _load_test_module(test_path)
        aggregate.addTests(loader.loadTestsFromModule(module))
    if implemented_count == 0:
        aggregate.addTests(loader.loadTestsFromTestCase(_NoImplementedTier2Level2SpellTests))
    return aggregate
