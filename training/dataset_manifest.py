from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from typing import Any, Iterable

from training.transitions import REWARD_CHANNELS, TERMINAL_REWARD_CHANNEL


DATASET_MANIFEST_SCHEMA_VERSION = 'dnd-agents-dataset-manifest-v1'


def write_dataset_manifest(
    *,
    dataset_type: str,
    dataset_path: str | Path,
    record_count: int,
    source_paths: Iterable[str | Path],
    manifest_path: str | Path | None = None,
    filters: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> Path:
    path = Path(dataset_path)
    output_path = Path(manifest_path) if manifest_path is not None else path.with_name(path.name + '.manifest.json')
    manifest = build_dataset_manifest(
        dataset_type=dataset_type,
        dataset_path=path,
        record_count=record_count,
        source_paths=source_paths,
        filters=filters,
        context=context,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return output_path


def build_dataset_manifest(
    *,
    dataset_type: str,
    dataset_path: str | Path,
    record_count: int,
    source_paths: Iterable[str | Path],
    filters: dict[str, Any] | None = None,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    path = Path(dataset_path)
    return {
        'schema_version': DATASET_MANIFEST_SCHEMA_VERSION,
        'created_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'dataset_type': dataset_type,
        'dataset_path': str(path),
        'dataset_sha256': _file_sha256(path),
        'record_count': record_count,
        'source_paths': [str(Path(source_path)) for source_path in source_paths],
        'filters': filters or {},
        'context': context or {},
        'reward_schema': {
            'component_to_channel': dict(sorted(REWARD_CHANNELS.items())),
            'terminal_reward_channel': TERMINAL_REWARD_CHANNEL,
        },
    }


def _file_sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
