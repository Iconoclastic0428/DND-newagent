from __future__ import annotations

import importlib.util
import json
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import ModuleType

from shared_types.capabilities import CapabilityDefinition
from shared_types.spellcasting import SpellRuntimeSupportMode, SpellRuntimeSupportProfile

from .fiveetools_loader import _canonical_name


_REPO_ROOT = Path(__file__).resolve().parents[1]
_MANIFEST_ROOT = _REPO_ROOT / 'content' / 'manifests'
_LEVEL2_MANIFEST_PATH = _MANIFEST_ROOT / 'tier2_level2_spells_manifest.json'
_SUPPORT_MATRIX_PATH = _MANIFEST_ROOT / 'tier2_support_matrix.json'


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding='utf-8-sig'))


@lru_cache(maxsize=1)
def load_level2_spell_manifest() -> dict[str, object]:
    return _load_json(_LEVEL2_MANIFEST_PATH)


@lru_cache(maxsize=1)
def load_tier2_support_matrix() -> dict[str, object]:
    return _load_json(_SUPPORT_MATRIX_PATH)


@lru_cache(maxsize=1)
def level2_spell_lookup() -> dict[str, dict[str, object]]:
    manifest = load_level2_spell_manifest()
    lookup: dict[str, dict[str, object]] = {}
    for entry in manifest.get('entries', []):
        if not isinstance(entry, dict):
            continue
        display_name = str(entry.get('display_name', '')).strip()
        if not display_name:
            continue
        lookup[display_name.casefold()] = entry
    return lookup


def spell_runtime_support_for(name: str, *, source: str) -> SpellRuntimeSupportProfile | None:
    if source.upper() != 'XPHB':
        return None
    entry = level2_spell_lookup().get(name.casefold())
    if entry is None:
        return None
    runtime_status = str(entry.get('runtime_status', ''))
    if runtime_status not in {SpellRuntimeSupportMode.DETERMINISTIC_CAPABILITY.value, SpellRuntimeSupportMode.STORY_ADJUDICATED.value}:
        return None
    return SpellRuntimeSupportProfile(
        support_mode=SpellRuntimeSupportMode(runtime_status),
        content_id=str(entry.get('source_id', f"XPHB:spell:{name.casefold()}")),
        implementation_path=str(entry.get('owning_directory', '')),
        support_summary=f"level-2 spell runtime support: {runtime_status}",
    )


def _executor_path(entry: Mapping[str, object]) -> Path:
    owning_directory = str(entry.get('owning_directory', '')).strip()
    if not owning_directory:
        raise FileNotFoundError('Tier-2 spell entry is missing owning_directory.')
    return _REPO_ROOT / owning_directory / 'executor.py'


@lru_cache(maxsize=None)
def _load_executor_module(executor_path: str) -> ModuleType:
    path = Path(executor_path)
    if not path.exists():
        raise FileNotFoundError(f'Tier-2 spell executor not found: {path}')
    module_name = f"tier2_spell_{path.parent.name.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f'Could not load Tier-2 spell executor module from {path}')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_tier2_spell_capability_definition(raw_spell: Mapping[str, object]) -> CapabilityDefinition | None:
    source = str(raw_spell.get('source', '')).upper()
    level = raw_spell.get('level')
    if source != 'XPHB' or level != 2:
        return None
    name = _canonical_name(raw_spell)
    entry = level2_spell_lookup().get(name.casefold())
    if entry is None:
        return None
    if str(entry.get('runtime_status', '')) != SpellRuntimeSupportMode.DETERMINISTIC_CAPABILITY.value:
        return None
    module = _load_executor_module(str(_executor_path(entry)))
    builder = getattr(module, 'build_capability_definition', None)
    if builder is None:
        raise AttributeError(f'Tier-2 spell executor {module.__file__} is missing build_capability_definition(raw_spell).')
    capability = builder(raw_spell)
    if capability is not None and not isinstance(capability, CapabilityDefinition):
        raise TypeError(f'Tier-2 spell executor {module.__file__} returned {type(capability)!r} instead of CapabilityDefinition | None.')
    return capability

