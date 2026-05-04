from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from .models import (
    CampaignDocument,
    CampaignDocumentType,
    CampaignPackage,
    CampaignRetrievalQuery,
    CampaignRetrievalResult,
)
from .package import load_campaign_package


@dataclass(frozen=True)
class _ScoredDocument:
    score: int
    priority: int
    path: str
    rationale: tuple[str, ...]
    document: CampaignDocument


_PRIORITY = {
    CampaignDocumentType.CAMPAIGN_INDEX: 0,
    CampaignDocumentType.CHAPTER_INDEX: 1,
    CampaignDocumentType.NPC: 2,
    CampaignDocumentType.LOCATION: 3,
    CampaignDocumentType.SCENE: 4,
    CampaignDocumentType.SCENE_STATE: 5,
    CampaignDocumentType.DM_SUMMARY: 6,
    CampaignDocumentType.NPC_PLAYBOOK: 7,
    CampaignDocumentType.SESSION_LOG: 8,
    CampaignDocumentType.ITEM: 9,
    CampaignDocumentType.FACTION: 10,
    CampaignDocumentType.RETRIEVAL_INDEX: 11,
}


_ANCHOR_ORDER = {
    CampaignDocumentType.CAMPAIGN_INDEX: 0,
    CampaignDocumentType.CHAPTER_INDEX: 1,
    CampaignDocumentType.SCENE: 2,
    CampaignDocumentType.LOCATION: 3,
    CampaignDocumentType.NPC: 4,
    CampaignDocumentType.SCENE_STATE: 5,
    CampaignDocumentType.DM_SUMMARY: 6,
    CampaignDocumentType.NPC_PLAYBOOK: 7,
    CampaignDocumentType.SESSION_LOG: 8,
}


class CampaignRetrievalIndex:
    def __init__(self, package: CampaignPackage) -> None:
        self.package = package
        self.by_path = {doc.path.resolve().relative_to(package.root).as_posix(): doc for doc in package.documents}
        self.by_id = {doc.front_matter.id: doc for doc in package.documents}
        self.by_type: dict[CampaignDocumentType, tuple[CampaignDocument, ...]] = defaultdict(tuple)
        for doc in package.documents:
            self.by_type[doc.front_matter.type] = (*self.by_type[doc.front_matter.type], doc)

    @classmethod
    def from_root(cls, root: str | Path) -> 'CampaignRetrievalIndex':
        return cls(load_campaign_package(root))

    def select_documents(self, query: CampaignRetrievalQuery) -> CampaignRetrievalResult:
        anchor_docs: list[CampaignDocument] = []
        linked_docs: list[CampaignDocument] = []
        scored: list[_ScoredDocument] = []
        anchor_paths: set[str] = set()
        minimum_score = 25

        for doc in self.package.documents:
            rel_path = doc.path.resolve().relative_to(self.package.root).as_posix()
            if self._is_mandatory(doc, query):
                anchor_docs.append(doc)
                anchor_paths.add(rel_path)

        linked_paths = self._linked_paths(anchor_paths)
        for doc in self.package.documents:
            rel_path = doc.path.resolve().relative_to(self.package.root).as_posix()
            if rel_path in linked_paths and rel_path not in anchor_paths:
                linked_docs.append(doc)

        selected: list[_ScoredDocument] = []
        seen: set[str] = set()

        for doc in sorted(anchor_docs, key=lambda item: (_ANCHOR_ORDER.get(item.front_matter.type, 99), str(item.path))):
            rel_path = doc.path.resolve().relative_to(self.package.root).as_posix()
            selected.append(
                _ScoredDocument(
                    score=1000,
                    priority=_PRIORITY.get(doc.front_matter.type, 99),
                    path=rel_path,
                    rationale=('mandatory',),
                    document=doc,
                )
            )
            seen.add(rel_path)

        for doc in sorted(linked_docs, key=lambda item: (_PRIORITY.get(item.front_matter.type, 99), str(item.path))):
            rel_path = doc.path.resolve().relative_to(self.package.root).as_posix()
            if rel_path in seen:
                continue
            selected.append(
                _ScoredDocument(
                    score=300,
                    priority=_PRIORITY.get(doc.front_matter.type, 99),
                    path=rel_path,
                    rationale=('linked',),
                    document=doc,
                )
            )
            seen.add(rel_path)

        for doc in self.package.documents:
            rel_path = doc.path.resolve().relative_to(self.package.root).as_posix()
            if rel_path in seen:
                continue
            score, rationale = self._score_document(doc, query)
            if query.include_types and doc.front_matter.type not in query.include_types:
                score -= 500
            if score < minimum_score:
                continue
            selected.append(
                _ScoredDocument(
                    score=score,
                    priority=_PRIORITY.get(doc.front_matter.type, 99),
                    path=rel_path,
                    rationale=tuple(rationale),
                    document=doc,
                )
            )

        ordered = selected[: max(1, query.max_results)]
        return CampaignRetrievalResult(
            query=query,
            selected_paths=tuple(item.path for item in ordered),
            documents=tuple(item.document for item in ordered),
            score_by_path={item.path: item.score for item in ordered},
            rationale_by_path={item.path: item.rationale for item in ordered},
        )

    def _linked_paths(self, anchor_paths: set[str]) -> set[str]:
        linked: set[str] = set()
        for rel_path in anchor_paths:
            doc = self.by_path.get(rel_path)
            if doc is None:
                continue
            for related in doc.front_matter.related_files:
                resolved = self._resolve_related_path(doc.path, related)
                if resolved is not None:
                    linked.add(resolved)
            for link in doc.links:
                resolved = self._resolve_related_path(doc.path, link)
                if resolved is not None:
                    linked.add(resolved)
        return linked

    def _resolve_related_path(self, source_path: Path, related: str) -> str | None:
        candidate = (source_path.parent / related).resolve()
        try:
            return candidate.relative_to(self.package.root).as_posix()
        except ValueError:
            return None

    def _is_mandatory(self, doc: CampaignDocument, query: CampaignRetrievalQuery) -> bool:
        fm = doc.front_matter
        if fm.type == CampaignDocumentType.CAMPAIGN_INDEX:
            return query.campaign is None or fm.campaign == query.campaign
        if fm.type == CampaignDocumentType.CHAPTER_INDEX:
            return query.chapter is not None and fm.chapter == query.chapter
        if fm.type == CampaignDocumentType.SCENE:
            return query.scene_id is not None and fm.id == query.scene_id
        if fm.type == CampaignDocumentType.LOCATION:
            if query.location is not None and fm.id == query.location:
                return True
            if query.scene_id is not None:
                scene_doc = self.by_id.get(query.scene_id)
                if scene_doc is not None and scene_doc.front_matter.canonical_location == fm.id:
                    return True
            return False
        if fm.type == CampaignDocumentType.NPC:
            return fm.id in set(query.npc_ids)
        if fm.type == CampaignDocumentType.DM_SUMMARY:
            if not query.include_dm_memory:
                return False
            if fm.state_scope.value == 'campaign':
                return True
            return self._matches_memory_context(doc, query)
        if fm.type in {CampaignDocumentType.SCENE_STATE, CampaignDocumentType.NPC_PLAYBOOK, CampaignDocumentType.SESSION_LOG}:
            if not query.include_dm_memory:
                return False
            return self._matches_memory_context(doc, query)
        return False

    def _matches_memory_context(self, doc: CampaignDocument, query: CampaignRetrievalQuery) -> bool:
        fm = doc.front_matter
        if query.scene_id and fm.canonical_location and query.scene_id in fm.id:
            return True
        if query.location and fm.canonical_location == query.location:
            return True
        if query.npc_ids and any(npc in fm.involved_npcs for npc in query.npc_ids):
            return True
        return False

    def _score_document(self, doc: CampaignDocument, query: CampaignRetrievalQuery) -> tuple[int, list[str]]:
        fm = doc.front_matter
        score = 0
        rationale: list[str] = []
        if query.campaign and fm.campaign == query.campaign and fm.type == CampaignDocumentType.CAMPAIGN_INDEX:
            score += 60
            rationale.append('campaign-index')
        if query.chapter and fm.chapter == query.chapter:
            score += 80
            rationale.append('chapter')
        if query.scene_id and fm.id == query.scene_id:
            score += 1000
            rationale.append('scene-id')
        if query.location and (fm.id == query.location or fm.canonical_location == query.location):
            score += 800
            rationale.append('location')
        if query.npc_ids:
            overlap = set(query.npc_ids).intersection(fm.involved_npcs)
            if overlap:
                bonus = 150 + (25 * len(overlap))
                score += bonus
                rationale.append(f'npcs:{",".join(sorted(overlap))}')
        if query.tags:
            overlap = set(query.tags).intersection(fm.tags)
            if overlap:
                bonus = 40 * len(overlap)
                score += bonus
                rationale.append(f'tags:{",".join(sorted(overlap))}')
        if query.keywords:
            haystack = ' '.join((fm.id, fm.title, doc.body, ' '.join(fm.retrieval_keywords), ' '.join(fm.tags))).lower()
            overlap = [keyword for keyword in query.keywords if keyword.lower() in haystack]
            if overlap:
                bonus = 20 * len(overlap)
                score += bonus
                rationale.append(f'keywords:{",".join(overlap)}')
        if doc.path.resolve().relative_to(self.package.root).as_posix() in query.recent_paths:
            score += 400
            rationale.append('recent')
        if doc.front_matter.type in query.include_types:
            score += 50
            rationale.append('allowed-type')
        if doc.front_matter.id in query.recent_paths:
            score += 250
            rationale.append('recent-id')
        return score, rationale


def select_campaign_documents(root: str | Path, query: CampaignRetrievalQuery) -> CampaignRetrievalResult:
    return CampaignRetrievalIndex.from_root(root).select_documents(query)




