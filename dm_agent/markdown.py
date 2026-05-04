from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import re
from typing import Iterable, Mapping


class MarkdownDocumentType(str, Enum):
    CAMPAIGN_INDEX = 'campaign_index'
    CHAPTER_INDEX = 'chapter_index'
    SCENE = 'scene'
    NPC = 'npc'
    LOCATION = 'location'
    DM_SUMMARY = 'dm_summary'
    NPC_PLAYBOOK = 'npc_playbook'
    SESSION_LOG = 'session_log'
    SCENE_STATE = 'scene_state'


CampaignDocumentType = MarkdownDocumentType


@dataclass(frozen=True)
class MarkdownMetadata:
    id: str
    type: MarkdownDocumentType
    title: str
    campaign: str
    chapter: str | None = None
    tags: tuple[str, ...] = ()
    canonical_location: str | None = None
    involved_npcs: tuple[str, ...] = ()
    related_files: tuple[str, ...] = ()
    retrieval_keywords: tuple[str, ...] = ()
    visibility: str = 'public'
    state_scope: str = 'canonical'
    last_updated: str | None = None
    token_budget_hint: str = 'small'
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class MarkdownDocument:
    metadata: MarkdownMetadata
    body: str

    def render(self) -> str:
        return render_markdown_document(self.metadata, self.body)


@dataclass(frozen=True)
class CampaignManifestEntry:
    metadata: MarkdownMetadata
    path: Path
    relative_path: str


@dataclass(frozen=True)
class RetrievalRequest:
    campaign: str
    current_scene_id: str | None = None
    current_location: str | None = None
    current_chapter: str | None = None
    npc_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    recent_terms: tuple[str, ...] = ()
    linked_from_ids: tuple[str, ...] = ()
    max_results: int = 8


@dataclass
class CampaignManifest:
    root: Path
    entries: tuple[CampaignManifestEntry, ...]
    _by_id: dict[str, CampaignManifestEntry] = field(default_factory=dict, repr=False)
    _by_path: dict[str, CampaignManifestEntry] = field(default_factory=dict, repr=False)

    @classmethod
    def from_root(cls, root: Path) -> 'CampaignManifest':
        root = root.resolve()
        entries: list[CampaignManifestEntry] = []
        for path in sorted(root.rglob('*.md')):
            document = load_markdown_document(path)
            relative_path = path.resolve().relative_to(root).as_posix()
            entries.append(CampaignManifestEntry(metadata=document.metadata, path=path, relative_path=relative_path))
        return cls(root=root, entries=tuple(entries), _by_id={entry.metadata.id: entry for entry in entries}, _by_path={entry.relative_path: entry for entry in entries})

    def select(self, request: RetrievalRequest) -> tuple[CampaignManifestEntry, ...]:
        if request.max_results <= 0:
            return ()
        linked: set[str] = set()
        for ref_id in request.linked_from_ids:
            entry = self._by_id.get(ref_id)
            if entry is None:
                continue
            linked.add(entry.metadata.id)
            linked.add(entry.relative_path)
            linked.update(entry.metadata.related_files)
        scored: list[tuple[int, str, CampaignManifestEntry]] = []
        for entry in self.entries:
            if entry.metadata.campaign != request.campaign:
                continue
            score = _score_entry(entry, request)
            if entry.metadata.id in linked or entry.relative_path in linked:
                score += 120
            if score > 0:
                scored.append((score, entry.relative_path, entry))
        scored.sort(key=lambda item: (-item[0], item[1], item[2].metadata.id))
        out: list[CampaignManifestEntry] = []
        seen: set[str] = set()
        for _, _, entry in scored:
            if entry.metadata.id in seen:
                continue
            out.append(entry)
            seen.add(entry.metadata.id)
            if len(out) >= request.max_results:
                break
        return tuple(out)

    def get(self, entry_id: str) -> CampaignManifestEntry | None:
        return self._by_id.get(entry_id)

    def get_by_path(self, relative_path: str) -> CampaignManifestEntry | None:
        return self._by_path.get(relative_path)


def load_campaign_manifest(root: Path) -> CampaignManifest:
    return CampaignManifest.from_root(root)


def load_markdown_document(path: Path) -> MarkdownDocument:
    metadata, body = parse_markdown_document(path.read_text(encoding='utf-8'))
    return MarkdownDocument(metadata=metadata, body=body)


def write_markdown_document(path: Path, document: MarkdownDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(document.render(), encoding='utf-8')


def render_markdown_document(metadata: MarkdownMetadata, body: str) -> str:
    text = body.rstrip()
    front_matter = _render_front_matter(metadata)
    if text:
        return f'---\n{front_matter}---\n\n{text}\n'
    return f'---\n{front_matter}---\n'


def parse_markdown_document(text: str) -> tuple[MarkdownMetadata, str]:
    normalized = text.lstrip('\ufeff')
    if not normalized.startswith('---\n'):
        raise ValueError('Markdown document is missing front matter.')
    parts = normalized.split('---\n', 2)
    if len(parts) < 3:
        raise ValueError('Markdown document is missing a closing front matter delimiter.')
    _, front_matter, remainder = parts
    return _metadata_from_raw(_parse_front_matter(front_matter)), remainder.lstrip('\n').rstrip()


def _parse_front_matter(block: str) -> dict[str, object]:
    raw: dict[str, object] = {}
    current_list_key: str | None = None
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith('- '):
            if current_list_key is None:
                raise ValueError(f'Unexpected list item in front matter: {line!r}')
            raw.setdefault(current_list_key, [])
            assert isinstance(raw[current_list_key], list)
            raw[current_list_key].append(_parse_scalar(stripped[2:].strip()))
            continue
        if ':' not in stripped:
            raise ValueError(f'Invalid front matter line: {line!r}')
        key, value = stripped.split(':', 1)
        key = key.strip()
        value = value.strip()
        if not key:
            raise ValueError(f'Invalid front matter key in line: {line!r}')
        if value == '':
            raw[key] = []
            current_list_key = key
            continue
        current_list_key = None
        raw[key] = _parse_scalar(value)
    return raw


def _metadata_from_raw(raw: Mapping[str, object]) -> MarkdownMetadata:
    for field_name in ('id', 'type', 'title', 'campaign'):
        value = raw.get(field_name)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f'Markdown front matter is missing required field {field_name!r}.')
    metadata_type = MarkdownDocumentType(str(raw['type']))

    def as_tuple(key: str) -> tuple[str, ...]:
        value = raw.get(key)
        if value is None:
            return ()
        if isinstance(value, str):
            return (value,)
        if isinstance(value, list):
            return tuple(str(item) for item in value)
        raise ValueError(f'Front matter field {key!r} must be a string or list of strings.')

    def maybe_str(key: str) -> str | None:
        value = raw.get(key)
        if value is None:
            return None
        if not isinstance(value, str):
            raise ValueError(f'Front matter field {key!r} must be a string.')
        return value.strip() or None

    extra = tuple((key, str(value)) for key, value in sorted(raw.items()) if key not in {
        'id', 'type', 'title', 'campaign', 'chapter', 'tags', 'canonical_location', 'involved_npcs', 'related_files', 'retrieval_keywords', 'visibility', 'state_scope', 'last_updated', 'token_budget_hint',
    })
    visibility = raw.get('visibility', 'public')
    state_scope = raw.get('state_scope', 'canonical')
    token_budget_hint = raw.get('token_budget_hint', 'small')
    if not isinstance(visibility, str) or not isinstance(state_scope, str) or not isinstance(token_budget_hint, str):
        raise ValueError('Front matter visibility/state_scope/token_budget_hint must be strings.')
    return MarkdownMetadata(
        id=str(raw['id']).strip(),
        type=metadata_type,
        title=str(raw['title']).strip(),
        campaign=str(raw['campaign']).strip(),
        chapter=maybe_str('chapter'),
        tags=as_tuple('tags'),
        canonical_location=maybe_str('canonical_location'),
        involved_npcs=as_tuple('involved_npcs'),
        related_files=as_tuple('related_files'),
        retrieval_keywords=as_tuple('retrieval_keywords'),
        visibility=visibility,
        state_scope=state_scope,
        last_updated=maybe_str('last_updated'),
        token_budget_hint=token_budget_hint,
        extra=extra,
    )


def _parse_scalar(value: str) -> object:
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        return [] if not inner else [_parse_scalar(part.strip()) for part in _split_csv(inner)]
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1].replace('\\"', '"')
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("\\'", "'")
    if value.lower() in {'true', 'false'}:
        return value.lower() == 'true'
    if re.fullmatch(r'-?\d+', value):
        return int(value)
    return value


def _split_csv(text: str) -> list[str]:
    out: list[str] = []
    current: list[str] = []
    quote: str | None = None
    for ch in text:
        if quote:
            if ch == quote:
                quote = None
            else:
                current.append(ch)
            continue
        if ch in {'"', "'"}:
            quote = ch
        elif ch == ',':
            out.append(''.join(current).strip())
            current = []
        else:
            current.append(ch)
    if current or text.endswith(','):
        out.append(''.join(current).strip())
    return out


def _render_front_matter(metadata: MarkdownMetadata) -> str:
    lines = [
        f'id: {_format_scalar(metadata.id)}',
        f'type: {_format_scalar(metadata.type.value)}',
        f'title: {_format_scalar(metadata.title)}',
        f'campaign: {_format_scalar(metadata.campaign)}',
    ]
    if metadata.chapter:
        lines.append(f'chapter: {_format_scalar(metadata.chapter)}')
    lines.extend(_render_list('tags', metadata.tags))
    if metadata.canonical_location:
        lines.append(f'canonical_location: {_format_scalar(metadata.canonical_location)}')
    lines.extend(_render_list('involved_npcs', metadata.involved_npcs))
    lines.extend(_render_list('related_files', metadata.related_files))
    lines.extend(_render_list('retrieval_keywords', metadata.retrieval_keywords))
    lines.extend([
        f'visibility: {_format_scalar(metadata.visibility)}',
        f'state_scope: {_format_scalar(metadata.state_scope)}',
    ])
    if metadata.last_updated:
        lines.append(f'last_updated: {_format_scalar(metadata.last_updated)}')
    lines.append(f'token_budget_hint: {_format_scalar(metadata.token_budget_hint)}')
    for key, value in metadata.extra:
        lines.append(f'{key}: {_format_scalar(value)}')
    return '\n'.join(lines) + '\n'


def _render_list(key: str, values: Iterable[str]) -> list[str]:
    items = tuple(values)
    if not items:
        return []
    return [key + ':', *[f'  - {_format_scalar(item)}' for item in items]]


def _format_scalar(value: object) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, int):
        return str(value)
    text = str(value)
    if not text:
        return '""'
    if re.fullmatch(r'[A-Za-z0-9_./:-]+', text):
        return text
    return '"' + text.replace('"', '\\"') + '"'


def _score_entry(entry: CampaignManifestEntry, request: RetrievalRequest) -> int:
    metadata = entry.metadata
    score = 0
    if metadata.id == request.current_scene_id:
        score += 1000
    if request.current_location and (metadata.canonical_location == request.current_location or metadata.id == request.current_location):
        score += 700
    if request.current_chapter and metadata.chapter == request.current_chapter:
        score += 250
    if metadata.id in request.npc_ids:
        score += 350
    score += len(set(metadata.tags) & set(request.tags)) * 40
    score += _overlap(metadata.retrieval_keywords, request.recent_terms) * 15
    score += _overlap((metadata.title,), request.recent_terms) * 10
    return score + len(metadata.related_files)


def _overlap(values: Iterable[str], terms: Iterable[str]) -> int:
    value_set = {value.lower() for value in values}
    return sum(1 for term in terms if term.lower() in value_set)
