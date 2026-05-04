
from __future__ import annotations

from pathlib import Path
import json
import shutil
import textwrap
import unittest

from campaign_ingestion import (
    CampaignDocumentType,
    CampaignRetrievalIndex,
    CampaignRetrievalQuery,
    build_campaign_manifest,
    load_campaign_document,
    load_campaign_package,
    manifest_to_json,
    parse_campaign_document,
    select_campaign_documents,
    write_campaign_manifest,
)
from campaign_ingestion.parser import CampaignMarkdownError


REPO_ROOT = Path(__file__).resolve().parents[1]
CAMPAIGN_ROOT = REPO_ROOT / 'campaigns' / 'lmop'


def _write_markdown(root: Path, relative_path: str, content: str) -> Path:
    path = root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(content).lstrip('\n'), encoding='utf-8')
    return path


class CampaignMarkdownTests(unittest.TestCase):
    def test_parse_front_matter_and_extract_links(self) -> None:
        text = """
        ---
        id: scene-sample
        type: scene
        title: Sample Scene
        campaign: sample
        chapter: chapter-01
        tags: [alpha, beta]
        canonical_location: sample-location
        involved_npcs:
          - npc-a
          - npc-b
        related_files:
          - ../locations/sample-location.md
        retrieval_keywords: [clue, trap]
        visibility: mixed
        state_scope: scene
        last_updated: 2026-04-03
        token_budget_hint: small
        ---
        # Public Summary
        This is a [linked file](../locations/sample-location.md).
        """
        document = parse_campaign_document(Path('scene-sample.md'), textwrap.dedent(text).lstrip('\n'))
        self.assertEqual(document.front_matter.id, 'scene-sample')
        self.assertEqual(document.front_matter.type, CampaignDocumentType.SCENE)
        self.assertEqual(document.front_matter.tags, ('alpha', 'beta'))
        self.assertEqual(document.front_matter.involved_npcs, ('npc-a', 'npc-b'))
        self.assertEqual(document.front_matter.related_files, ('../locations/sample-location.md',))
        self.assertIn('Public Summary', document.headings)
        self.assertEqual(document.links, ('../locations/sample-location.md',))

    def test_missing_front_matter_field_is_rejected(self) -> None:
        text = """
        ---
        id: broken
        type: scene
        title: Broken Scene
        ---
        # Public Summary
        """
        with self.assertRaises(CampaignMarkdownError):
            parse_campaign_document(Path('broken.md'), text)

    def test_example_campaign_package_loads_and_writes_manifest(self) -> None:
        package = load_campaign_package(CAMPAIGN_ROOT)
        self.assertEqual(package.manifest.campaign, 'lmop')
        self.assertGreaterEqual(len(package.documents), 10)
        self.assertTrue(any(doc.front_matter.type == CampaignDocumentType.CAMPAIGN_INDEX for doc in package.documents))
        self.assertTrue(any(doc.front_matter.type == CampaignDocumentType.SCENE for doc in package.documents))

        manifest_text = manifest_to_json(package.manifest)
        payload = json.loads(manifest_text)
        self.assertEqual(payload['campaign'], 'lmop')
        self.assertEqual(len(payload['entries']), len(package.documents))

        scratch = REPO_ROOT / 'tmp_campaign_markdown_manifest'
        if scratch.exists():
            shutil.rmtree(scratch)
        scratch.mkdir(parents=True, exist_ok=True)
        try:
            output = write_campaign_manifest(CAMPAIGN_ROOT, package.documents, output_path=scratch / 'manifest.json')
            written = json.loads(output.read_text(encoding='utf-8'))
            self.assertEqual(written['campaign'], 'lmop')
            self.assertEqual(len(written['entries']), len(package.documents))
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_scene_retrieval_orders_anchors_then_linked_files(self) -> None:
        index = CampaignRetrievalIndex.from_root(CAMPAIGN_ROOT)
        result = index.select_documents(
            CampaignRetrievalQuery(
                campaign='lmop',
                chapter='chapter-01',
                scene_id='scene-triboar-goblin-ambush',
                max_results=10,
            )
        )
        self.assertEqual(
            result.selected_paths[:3],
            (
                'index.md',
                'chapters/chapter-01/index.md',
                'chapters/chapter-01/scene-01-goblin-ambush.md',
            ),
        )
        self.assertIn('locations/triboar-trail.md', result.selected_paths)
        self.assertIn('npcs/gundren-rockseeker.md', result.selected_paths)
        self.assertIn('dm/scene-state/scene-triboar-goblin-ambush.md', result.selected_paths)
        self.assertIn('dm/summaries/campaign-state.md', result.selected_paths)

    def test_retrieval_prefers_relevant_small_bundle_over_many_irrelevant_docs(self) -> None:
        root = REPO_ROOT / 'tmp_campaign_markdown_selective'
        if root.exists():
            shutil.rmtree(root)
        root.mkdir(parents=True, exist_ok=True)
        try:
            _write_markdown(
                root,
                'index.md',
                """
                ---
                id: temp-index
                type: campaign_index
                title: Temp Campaign
                campaign: temp
                related_files: [chapters/chapter-01/index.md]
                visibility: public
                state_scope: canonical
                token_budget_hint: small
                ---
                # Campaign Summary
                """,
            )
            _write_markdown(
                root,
                'chapters/chapter-01/index.md',
                """
                ---
                id: temp-chapter-01
                type: chapter_index
                title: Chapter 1
                campaign: temp
                chapter: chapter-01
                related_files: [scene-01.md]
                visibility: public
                state_scope: chapter
                token_budget_hint: small
                ---
                # Chapter Summary
                """,
            )
            _write_markdown(
                root,
                'chapters/chapter-01/scene-01.md',
                """
                ---
                id: temp-scene-01
                type: scene
                title: Relevant Scene
                campaign: temp
                chapter: chapter-01
                canonical_location: temp-location
                related_files: [../../locations/temp-location.md, ../../npcs/temp-npc.md]
                retrieval_keywords: [relevant, clue]
                visibility: mixed
                state_scope: scene
                token_budget_hint: small
                ---
                # Public Summary
                """,
            )
            _write_markdown(
                root,
                'locations/temp-location.md',
                """
                ---
                id: temp-location
                type: location
                title: Temp Location
                campaign: temp
                visibility: public
                state_scope: location
                token_budget_hint: small
                ---
                # Public Identity
                """,
            )
            _write_markdown(
                root,
                'npcs/temp-npc.md',
                """
                ---
                id: temp-npc
                type: npc
                title: Temp NPC
                campaign: temp
                visibility: mixed
                state_scope: npc
                token_budget_hint: small
                ---
                # Public Identity
                """,
            )
            for index in range(20):
                _write_markdown(
                    root,
                    f'notes/irrelevant-{index:02d}.md',
                    f"""
                    ---
                    id: irrelevant-{index:02d}
                    type: dm_summary
                    title: Irrelevant Note {index:02d}
                    campaign: temp
                    visibility: dm
                    state_scope: summary
                    token_budget_hint: small
                    ---
                    # Summary
                    Nothing useful here.
                    """,
                )

            result = select_campaign_documents(
                root,
                CampaignRetrievalQuery(
                    campaign='temp',
                    chapter='chapter-01',
                    scene_id='temp-scene-01',
                    max_results=5,
                ),
            )
            self.assertEqual(result.selected_paths[:5], ('index.md', 'chapters/chapter-01/index.md', 'chapters/chapter-01/scene-01.md', 'locations/temp-location.md', 'npcs/temp-npc.md'))
            self.assertNotIn('notes/irrelevant-00.md', result.selected_paths)
            self.assertNotIn('notes/irrelevant-19.md', result.selected_paths)
        finally:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()


