from __future__ import annotations

from dataclasses import asdict
from enum import Enum
from pathlib import Path
import json
from typing import Iterable

from .models import CampaignDocument, CampaignManifest, CampaignManifestEntry


def build_campaign_manifest(root: str | Path, documents: Iterable[CampaignDocument]) -> CampaignManifest:
    root_path = Path(root).resolve()
    docs = tuple(documents)
    campaign = _campaign_id(root_path, docs)
    entries = tuple(_entry(root_path, doc) for doc in docs)
    return CampaignManifest(campaign=campaign, root=root_path, entries=entries)


def manifest_to_json(manifest: CampaignManifest) -> str:
    payload = {
        'campaign': manifest.campaign,
        'root': str(manifest.root),
        'entries': [_serialize_entry(entry) for entry in manifest.entries],
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def write_campaign_manifest(root: str | Path, documents: Iterable[CampaignDocument], output_path: str | Path | None = None) -> Path:
    manifest = build_campaign_manifest(root, documents)
    target = Path(output_path) if output_path is not None else Path(root).resolve() / 'dm' / 'retrieval' / 'manifest.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(manifest_to_json(manifest), encoding='utf-8')
    return target


def _entry(root: Path, document: CampaignDocument) -> CampaignManifestEntry:
    fm = document.front_matter
    return CampaignManifestEntry(
        path=document.path.resolve().relative_to(root).as_posix(),
        id=fm.id,
        type=fm.type,
        title=fm.title,
        campaign=fm.campaign,
        chapter=fm.chapter,
        tags=fm.tags,
        canonical_location=fm.canonical_location,
        involved_npcs=fm.involved_npcs,
        related_files=fm.related_files,
        retrieval_keywords=fm.retrieval_keywords,
        visibility=fm.visibility,
        state_scope=fm.state_scope,
        last_updated=fm.last_updated,
        token_budget_hint=fm.token_budget_hint,
        session_id=fm.session_id,
    )


def _campaign_id(root: Path, documents: tuple[CampaignDocument, ...]) -> str:
    for document in documents:
        if document.front_matter.type.value == 'campaign_index':
            return document.front_matter.campaign
    return root.name


def _serialize_entry(entry: CampaignManifestEntry) -> dict[str, object]:
    return _serialize_value(asdict(entry))  # type: ignore[return-value]


def _serialize_value(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {key: _serialize_value(inner) for key, inner in value.items()}
    if isinstance(value, tuple):
        return [_serialize_value(item) for item in value]
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    return value

