from __future__ import annotations

from pathlib import Path
import re

from .models import (
    CampaignDocument,
    CampaignDocumentType,
    CampaignFrontMatter,
    CampaignStateScope,
    CampaignVisibility,
    TokenBudgetHint,
)


class CampaignMarkdownError(ValueError):
    pass


_LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
_HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
_KEY_VALUE_PATTERN = re.compile(r"^([A-Za-z0-9_]+)\s*:\s*(.*)$")


def parse_campaign_document(path: str | Path, text: str) -> CampaignDocument:
    path = Path(path)
    metadata, body = parse_front_matter(text)
    front_matter = _validate_front_matter(path, metadata)
    headings = extract_headings(body)
    links = extract_links(body)
    return CampaignDocument(path=path, front_matter=front_matter, body=body, headings=headings, links=links)


def parse_front_matter(text: str) -> tuple[dict[str, object], str]:
    text = text.lstrip('\ufeff')
    lines = text.splitlines()
    if not lines or lines[0].strip() != '---':
        raise CampaignMarkdownError('Markdown document is missing a front matter block.')
    end_index = None
    for index in range(1, len(lines)):
        if lines[index].strip() == '---':
            end_index = index
            break
    if end_index is None:
        raise CampaignMarkdownError('Markdown front matter block is not terminated.')
    metadata_lines = lines[1:end_index]
    body = '\n'.join(lines[end_index + 1 :]).lstrip('\n')
    return _parse_metadata_lines(metadata_lines), body


def extract_headings(body: str) -> tuple[str, ...]:
    headings: list[str] = []
    for line in body.splitlines():
        match = _HEADING_PATTERN.match(line)
        if match:
            headings.append(match.group(2).strip())
    return tuple(headings)


def extract_links(body: str) -> tuple[str, ...]:
    links: list[str] = []
    for match in _LINK_PATTERN.finditer(body):
        target = match.group(1).strip()
        if target:
            links.append(target)
    return tuple(dict.fromkeys(links))


def _parse_metadata_lines(lines: list[str]) -> dict[str, object]:
    metadata: dict[str, object] = {}
    index = 0
    while index < len(lines):
        raw_line = lines[index]
        stripped = raw_line.strip()
        index += 1
        if not stripped or stripped.startswith('#'):
            continue
        match = _KEY_VALUE_PATTERN.match(stripped)
        if match is None:
            raise CampaignMarkdownError(f'Invalid front matter line: {raw_line!r}.')
        key = match.group(1)
        value = match.group(2)
        if value == '':
            collected: list[str] = []
            while index < len(lines):
                candidate = lines[index]
                candidate_stripped = candidate.strip()
                if not candidate_stripped:
                    index += 1
                    continue
                if candidate.startswith('  - ') or candidate.startswith('- '):
                    collected.append(candidate_stripped[2:].strip())
                    index += 1
                    continue
                if candidate.startswith('    - '):
                    collected.append(candidate_stripped[2:].strip())
                    index += 1
                    continue
                break
            metadata[key] = tuple(collected)
            continue
        metadata[key] = _parse_scalar_or_list(value)
    return metadata


def _parse_scalar_or_list(value: str) -> object:
    value = value.strip()
    if not value:
        return ''
    if value.startswith('[') and value.endswith(']'):
        inner = value[1:-1].strip()
        if not inner:
            return tuple()
        return tuple(_parse_scalar(item) for item in inner.split(','))
    if value.lower() in {'true', 'false'}:
        return value.lower() == 'true'
    if value.lower() == 'null':
        return None
    return _parse_scalar(value)


def _parse_scalar(value: str) -> object:
    value = value.strip()
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
        return int(value)
    return value


def _validate_front_matter(path: Path, metadata: dict[str, object]) -> CampaignFrontMatter:
    missing = [field for field in ('id', 'type', 'title', 'campaign') if field not in metadata]
    if missing:
        raise CampaignMarkdownError(f'{path}: missing required front matter field(s): {", ".join(missing)}.')
    document_type = _document_type(str(metadata['type']))
    visibility = _visibility(metadata.get('visibility', CampaignVisibility.PUBLIC.value))
    state_scope = _state_scope(metadata.get('state_scope', CampaignStateScope.CANONICAL.value))
    token_budget = _token_budget_hint(metadata.get('token_budget_hint', TokenBudgetHint.SMALL.value))
    return CampaignFrontMatter(
        id=str(metadata['id']),
        type=document_type,
        title=str(metadata['title']),
        campaign=str(metadata['campaign']),
        chapter=_optional_string(metadata.get('chapter')),
        tags=_as_string_tuple(metadata.get('tags')),
        canonical_location=_optional_string(metadata.get('canonical_location')),
        involved_npcs=_as_string_tuple(metadata.get('involved_npcs')),
        related_files=_as_string_tuple(metadata.get('related_files')),
        retrieval_keywords=_as_string_tuple(metadata.get('retrieval_keywords')),
        visibility=visibility,
        state_scope=state_scope,
        last_updated=_optional_string(metadata.get('last_updated')),
        token_budget_hint=token_budget,
        session_id=_optional_string(metadata.get('session_id')),
        custom_fields={key: value for key, value in metadata.items() if key not in {
            'id', 'type', 'title', 'campaign', 'chapter', 'tags', 'canonical_location', 'involved_npcs',
            'related_files', 'retrieval_keywords', 'visibility', 'state_scope', 'last_updated',
            'token_budget_hint', 'session_id',
        }},
    )


def _document_type(value: str) -> CampaignDocumentType:
    try:
        return CampaignDocumentType(value)
    except ValueError as exc:
        raise CampaignMarkdownError(f'Unknown campaign document type: {value!r}.') from exc


def _visibility(value: object) -> CampaignVisibility:
    try:
        return CampaignVisibility(str(value))
    except ValueError as exc:
        raise CampaignMarkdownError(f'Unknown campaign visibility: {value!r}.') from exc


def _state_scope(value: object) -> CampaignStateScope:
    try:
        return CampaignStateScope(str(value))
    except ValueError as exc:
        raise CampaignMarkdownError(f'Unknown campaign state scope: {value!r}.') from exc


def _token_budget_hint(value: object) -> TokenBudgetHint:
    try:
        return TokenBudgetHint(str(value))
    except ValueError as exc:
        raise CampaignMarkdownError(f'Unknown token budget hint: {value!r}.') from exc


def _as_string_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _optional_string(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


