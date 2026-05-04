from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from shared_types.spellcasting import SpellRuntimeSupportMode, SpellRuntimeSupportProfile
from shared_types.xphb_content import XphbContentEntry, XphbManifest


_CONTENT_ROOT = Path(__file__).resolve().parents[1] / 'content' / 'xphb'
_MANIFEST_ROOT = _CONTENT_ROOT / 'manifests'


def _load_manifest(path: Path) -> XphbManifest:
    payload = json.loads(path.read_text(encoding='utf-8'))
    entries = tuple(XphbContentEntry(**entry) for entry in payload['entries'])
    return XphbManifest(source=str(payload['source']), count=int(payload['count']), entries=entries)


@lru_cache(maxsize=1)
def load_cantrip_manifest() -> XphbManifest:
    return _load_manifest(_MANIFEST_ROOT / 'xphb-cantrips.json')


@lru_cache(maxsize=1)
def load_level1_spell_manifest() -> XphbManifest:
    return _load_manifest(_MANIFEST_ROOT / 'xphb-level1-spells.json')


@lru_cache(maxsize=1)
def load_level1_class_feature_manifest() -> XphbManifest:
    return _load_manifest(_MANIFEST_ROOT / 'xphb-level1-class-features.json')


@lru_cache(maxsize=1)
def load_level1_support_matrix() -> XphbManifest:
    path = _MANIFEST_ROOT / 'xphb-level1-support-matrix.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    entries = tuple(XphbContentEntry(**entry) for entry in payload['entries'])
    return XphbManifest(source=str(payload['source']), count=int(payload['counts']['total']), entries=entries)


@lru_cache(maxsize=1)
def spell_support_lookup() -> dict[str, XphbContentEntry]:
    lookup: dict[str, XphbContentEntry] = {}
    for manifest in (load_cantrip_manifest(), load_level1_spell_manifest()):
        for entry in manifest.entries:
            lookup[entry.display_name.casefold()] = entry
    return lookup


@lru_cache(maxsize=1)
def class_feature_support_lookup() -> dict[tuple[str, str], XphbContentEntry]:
    return {(entry.class_id or '', entry.display_name): entry for entry in load_level1_class_feature_manifest().entries}


def spell_runtime_support_for(name: str, *, source: str) -> SpellRuntimeSupportProfile | None:
    if source.upper() != 'XPHB':
        return None
    entry = spell_support_lookup().get(name.casefold())
    if entry is None:
        return None
    return SpellRuntimeSupportProfile(
        support_mode=SpellRuntimeSupportMode(entry.runtime_status),
        content_id=entry.content_id,
        implementation_path=entry.implementation_path,
        support_summary=f"{entry.category} runtime support: {entry.runtime_status}",
    )
