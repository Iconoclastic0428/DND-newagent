from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class CampaignDocumentType(str, Enum):
    CAMPAIGN_INDEX = 'campaign_index'
    CHAPTER_INDEX = 'chapter_index'
    SCENE = 'scene'
    NPC = 'npc'
    LOCATION = 'location'
    ITEM = 'item'
    FACTION = 'faction'
    DM_SUMMARY = 'dm_summary'
    NPC_PLAYBOOK = 'npc_playbook'
    SESSION_LOG = 'session_log'
    SCENE_STATE = 'scene_state'
    RETRIEVAL_INDEX = 'retrieval_index'


class CampaignVisibility(str, Enum):
    PUBLIC = 'public'
    MIXED = 'mixed'
    DM = 'dm'


class CampaignStateScope(str, Enum):
    CANONICAL = 'canonical'
    CAMPAIGN = 'campaign'
    CHAPTER = 'chapter'
    SCENE = 'scene'
    NPC = 'npc'
    LOCATION = 'location'
    SESSION = 'session'
    SUMMARY = 'summary'
    PLAYBOOK = 'playbook'
    RETRIEVAL = 'retrieval'


class TokenBudgetHint(str, Enum):
    SMALL = 'small'
    MEDIUM = 'medium'
    LARGE = 'large'


@dataclass(frozen=True)
class CampaignFrontMatter:
    id: str
    type: CampaignDocumentType
    title: str
    campaign: str
    chapter: str | None = None
    tags: tuple[str, ...] = ()
    canonical_location: str | None = None
    involved_npcs: tuple[str, ...] = ()
    related_files: tuple[str, ...] = ()
    retrieval_keywords: tuple[str, ...] = ()
    visibility: CampaignVisibility = CampaignVisibility.PUBLIC
    state_scope: CampaignStateScope = CampaignStateScope.CANONICAL
    last_updated: str | None = None
    token_budget_hint: TokenBudgetHint = TokenBudgetHint.SMALL
    session_id: str | None = None
    custom_fields: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CampaignDocument:
    path: Path
    front_matter: CampaignFrontMatter
    body: str
    headings: tuple[str, ...] = ()
    links: tuple[str, ...] = ()


@dataclass(frozen=True)
class CampaignManifestEntry:
    path: str
    id: str
    type: CampaignDocumentType
    title: str
    campaign: str
    chapter: str | None
    tags: tuple[str, ...]
    canonical_location: str | None
    involved_npcs: tuple[str, ...]
    related_files: tuple[str, ...]
    retrieval_keywords: tuple[str, ...]
    visibility: CampaignVisibility
    state_scope: CampaignStateScope
    last_updated: str | None
    token_budget_hint: TokenBudgetHint
    session_id: str | None


@dataclass(frozen=True)
class CampaignManifest:
    campaign: str
    root: Path
    entries: tuple[CampaignManifestEntry, ...]


@dataclass(frozen=True)
class CampaignPackage:
    root: Path
    documents: tuple[CampaignDocument, ...]
    manifest: CampaignManifest


@dataclass(frozen=True)
class CampaignRetrievalQuery:
    campaign: str | None = None
    chapter: str | None = None
    scene_id: str | None = None
    location: str | None = None
    npc_ids: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()
    recent_paths: tuple[str, ...] = ()
    include_types: tuple[CampaignDocumentType, ...] = ()
    max_results: int = 8
    include_dm_memory: bool = True


@dataclass(frozen=True)
class CampaignRetrievalResult:
    query: CampaignRetrievalQuery
    selected_paths: tuple[str, ...]
    documents: tuple[CampaignDocument, ...]
    score_by_path: dict[str, int]
    rationale_by_path: dict[str, tuple[str, ...]]


