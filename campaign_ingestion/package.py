from __future__ import annotations

from pathlib import Path

from .manifest import build_campaign_manifest
from .models import CampaignDocument, CampaignPackage
from .parser import parse_campaign_document


def iter_campaign_documents(root: str | Path):
    root_path = Path(root).resolve()
    for path in sorted(root_path.rglob('*.md')):
        if path.name.startswith('.'):
            continue
        yield load_campaign_document(path)


def load_campaign_document(path: str | Path) -> CampaignDocument:
    path = Path(path)
    return parse_campaign_document(path, path.read_text(encoding='utf-8'))


def load_campaign_package(root: str | Path) -> CampaignPackage:
    root_path = Path(root).resolve()
    documents = tuple(iter_campaign_documents(root_path))
    manifest = build_campaign_manifest(root_path, documents)
    return CampaignPackage(root=root_path, documents=documents, manifest=manifest)
