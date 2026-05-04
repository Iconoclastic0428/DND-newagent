from __future__ import annotations

from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from dm_agent import (
    CampaignDocumentType,
    CampaignManifest,
    CampaignStateSummary,
    DiscoveredSecretsSummary,
    DmMemoryWriter,
    MarkdownDocument,
    MarkdownMetadata,
    NpcPlaybook,
    OpenLoopsSummary,
    RetrievalRequest,
    SceneState,
    SessionLogEntry,
    load_markdown_document,
)


class DmMemoryTests(unittest.TestCase):
    def test_markdown_round_trip_and_validation(self) -> None:
        metadata = MarkdownMetadata(
            id='scene-triboar-goblin-ambush',
            type=CampaignDocumentType.SCENE,
            title='Goblin Ambush on Triboar Trail',
            campaign='lmop',
            chapter='chapter-01',
            tags=('ambush', 'trail'),
            canonical_location='triboar-trail',
            involved_npcs=('goblin-band', 'sildar-hallwinter'),
            related_files=('locations/triboar-trail.md',),
            retrieval_keywords=('goblins', 'horses'),
            visibility='mixed',
            state_scope='scene',
            last_updated='2026-04-03',
            token_budget_hint='small',
        )
        document = MarkdownDocument(metadata=metadata, body='# Public Summary\nA fight on the trail.\n')
        with self._tempdir() as tmpdir:
            path = Path(tmpdir) / 'scene.md'
            path.write_text(document.render(), encoding='utf-8')
            loaded = load_markdown_document(path)
        self.assertEqual(loaded.metadata, metadata)
        self.assertIn('Public Summary', loaded.body)

    def test_missing_front_matter_is_rejected(self) -> None:
        with self._tempdir() as tmpdir:
            path = Path(tmpdir) / 'broken.md'
            path.write_text('# No front matter\n', encoding='utf-8')
            with self.assertRaises(ValueError):
                load_markdown_document(path)

    def test_manifest_selects_relevant_files_and_follows_links(self) -> None:
        with self._tempdir() as tmpdir:
            root = Path(tmpdir) / 'campaigns' / 'lmop'
            self._write(root / 'index.md', CampaignDocumentType.CAMPAIGN_INDEX, 'Campaign Index', 'lmop', ('campaign',), '# Index\n')
            self._write(root / 'chapters' / 'chapter-01' / 'index.md', CampaignDocumentType.CHAPTER_INDEX, 'Chapter 01', 'lmop', ('chapter',), '# Chapter\n', chapter='chapter-01')
            self._write(
                root / 'chapters' / 'chapter-01' / 'scene-01-goblin-ambush.md',
                CampaignDocumentType.SCENE,
                'Goblin Ambush',
                'lmop',
                ('ambush', 'trail'),
                '# Scene\n',
                chapter='chapter-01',
                canonical_location='triboar-trail',
                involved_npcs=('goblin-band',),
                related_files=('npcs/goblin-band.md', 'locations/triboar-trail.md'),
                retrieval_keywords=('goblins', 'ambush'),
            )
            self._write(root / 'npcs' / 'goblin-band.md', CampaignDocumentType.NPC, 'Goblin Band', 'lmop', ('npc',), '# NPC\n')
            self._write(root / 'locations' / 'triboar-trail.md', CampaignDocumentType.LOCATION, 'Triboar Trail', 'lmop', ('location',), '# Location\n')
            manifest = CampaignManifest.from_root(root)
            selected = manifest.select(
                RetrievalRequest(
                    campaign='lmop',
                    current_scene_id='scene-01-goblin-ambush',
                    current_location='triboar-trail',
                    current_chapter='chapter-01',
                    npc_ids=('goblin-band',),
                    tags=('ambush',),
                    recent_terms=('goblins',),
                    linked_from_ids=('scene-01-goblin-ambush',),
                    max_results=4,
                )
            )
            selected_ids = [entry.metadata.id for entry in selected]
            self.assertEqual(selected_ids[0], 'scene-01-goblin-ambush')
            self.assertIn('goblin-band', selected_ids)
            self.assertIn('triboar-trail', selected_ids)

    def test_memory_writer_outputs_compact_files(self) -> None:
        with self._tempdir() as tmpdir:
            writer = DmMemoryWriter(Path(tmpdir), campaign_id='lmop')
            session = writer.write_session_log(
                SessionLogEntry(
                    session_id='session-0001',
                    campaign='lmop',
                    title='Session 0001',
                    recap_lines=('The party reached Triboar Trail.', 'The goblin ambush was sprung.'),
                    changes_lines=('A horse was lost.',),
                    clue_lines=('The trail is not safe.',),
                    unresolved_hook_lines=('Who set the ambush?',),
                    next_scene_lines=('Track the goblins.',),
                )
            )
            state = writer.write_campaign_state(
                CampaignStateSummary(
                    campaign='lmop',
                    title='Campaign State',
                    current_location='Triboar Trail',
                    party_goal_lines=('Reach Phandalin.',),
                    unresolved_consequence_lines=('The road remains dangerous.',),
                    party_belief_lines=('The goblins are linked to Cragmaw.',),
                    recent_change_lines=('The ambush depleted supplies.',),
                )
            )
            open_loops = writer.write_open_loops(OpenLoopsSummary(campaign='lmop', title='Open Loops', loop_lines=('Investigate Cragmaw Hideout.',)))
            secrets = writer.write_discovered_secrets(DiscoveredSecretsSummary(campaign='lmop', title='Discovered Secrets', secret_lines=('Sildar knows Gundren.',)))
            scene = writer.write_scene_state(
                SceneState(
                    scene_id='scene-01-goblin-ambush',
                    campaign='lmop',
                    title='Goblin Ambush',
                    canonical_location='triboar-trail',
                    occupant_lines=('3 goblins remain.',),
                    terrain_change_lines=('A wagon blocks the road.',),
                    discovered_clue_lines=('Arrow shafts point north.',),
                    triggered_event_lines=('The attack began at dusk.',),
                    unresolved_tension_lines=('No one saw the ambush leader.',),
                    exit_lines=('North trail is open.',),
                    described_to_players_lines=('Smoke and hoofprints are visible.',),
                    hidden_state_lines=('A goblin scout fled east.',),
                )
            )
            playbook = writer.write_npc_playbook(
                NpcPlaybook(
                    npc_id='sildar-hallwinter',
                    campaign='lmop',
                    title='Sildar Hallwinter',
                    voice_lines=('Measured, clipped, professional.',),
                    current_stance='Wary but cooperative.',
                    trust_lines=('Trusts the party enough to accept help.',),
                    reveal_lines=('Will explain the local road danger.',),
                    withholding_lines=('Will not discuss hidden faction ties yet.',),
                    reveal_ladder_lines=('First: road danger', 'Later: Gundren', 'Last: faction details'),
                    habit_lines=('Answers directly when pressed.',),
                    contradiction_lines=('He wants order but hides panic.',),
                    recent_interaction_lines=('Thanked the party after the ambush.',),
                    local_goal_lines=('Reach Phandalin safely.',),
                    warning_lines=('Do not casually reveal the Zhentarim lead.',),
                )
            )
            self.assertTrue(session.path.exists())
            self.assertTrue(state.path.exists())
            self.assertTrue(open_loops.path.exists())
            self.assertTrue(secrets.path.exists())
            self.assertTrue(scene.path.exists())
            self.assertTrue(playbook.path.exists())
            self.assertIn('Session Recap', session.document.body)
            self.assertIn('Current Location', state.document.body)
            self.assertIn('Open Loops', open_loops.document.body)
            self.assertIn('Discovered Secrets', secrets.document.body)
            self.assertIn('Current Occupants', scene.document.body)
            self.assertIn('Reveal Ladder', playbook.document.body)

    def test_scene_state_rewrites_deterministically(self) -> None:
        with self._tempdir() as tmpdir:
            writer = DmMemoryWriter(Path(tmpdir), campaign_id='lmop')
            first = writer.write_scene_state(SceneState(scene_id='scene-01-goblin-ambush', campaign='lmop', title='Goblin Ambush', canonical_location='triboar-trail', occupant_lines=('3 goblins remain.',), hidden_state_lines=('A scout fled east.',)))
            second = writer.write_scene_state(SceneState(scene_id='scene-01-goblin-ambush', campaign='lmop', title='Goblin Ambush', canonical_location='triboar-trail', occupant_lines=('2 goblins remain.',), hidden_state_lines=('A scout fled east.',)))
            self.assertEqual(first.path, second.path)
            self.assertIn('2 goblins remain.', second.document.body)
            self.assertNotIn('3 goblins remain.', second.document.body)

    def test_large_campaign_selective_retrieval_limits_results(self) -> None:
        with self._tempdir() as tmpdir:
            root = Path(tmpdir) / 'campaigns' / 'lmop'
            self._write(root / 'index.md', CampaignDocumentType.CAMPAIGN_INDEX, 'Campaign Index', 'lmop', ('campaign',), '# Index\n')
            for index in range(40):
                self._write(root / 'npcs' / f'npc-{index:02d}.md', CampaignDocumentType.NPC, f'NPC {index:02d}', 'lmop', ('npc',), '# NPC\n', retrieval_keywords=(f'keyword-{index:02d}',))
            self._write(root / 'scenes' / 'scene-target.md', CampaignDocumentType.SCENE, 'Target Scene', 'lmop', ('target', 'trail'), '# Scene\n', canonical_location='triboar-trail', retrieval_keywords=('ambush', 'goblins'), related_files=('npcs/npc-07.md',))
            manifest = CampaignManifest.from_root(root)
            selected = manifest.select(RetrievalRequest(campaign='lmop', current_scene_id='scene-target', current_location='triboar-trail', current_chapter='chapter-01', tags=('target',), recent_terms=('ambush',), linked_from_ids=('scene-target',), max_results=5))
            self.assertLessEqual(len(selected), 5)
            self.assertEqual(selected[0].metadata.id, 'scene-target')
            self.assertTrue(any(entry.metadata.id == 'npc-07' for entry in selected))

    def _tempdir(self):
        base = Path(__file__).resolve().parents[1] / '.dm-memory-tests' / uuid4().hex
        base.mkdir(parents=True, exist_ok=False)
        return _ScratchDir(base)

    def _write(self, path: Path, doc_type: CampaignDocumentType, title: str, campaign: str, tags: tuple[str, ...], body: str, **extra) -> None:
        metadata = MarkdownMetadata(id=path.stem, type=doc_type, title=title, campaign=campaign, tags=tags, **extra)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(MarkdownDocument(metadata=metadata, body=body).render(), encoding='utf-8')


class _ScratchDir:
    def __init__(self, path: Path) -> None:
        self.name = str(path)

    def __enter__(self) -> str:
        return self.name

    def __exit__(self, exc_type, exc, tb) -> bool:
        shutil.rmtree(self.name, ignore_errors=True)
        return False


if __name__ == '__main__':
    unittest.main()
