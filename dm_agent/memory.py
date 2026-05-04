from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .markdown import MarkdownDocument, MarkdownDocumentType, MarkdownMetadata, write_markdown_document


@dataclass(frozen=True)
class SessionLogEntry:
    session_id: str
    campaign: str
    title: str
    recap_lines: tuple[str, ...]
    changes_lines: tuple[str, ...] = ()
    clue_lines: tuple[str, ...] = ()
    unresolved_hook_lines: tuple[str, ...] = ()
    next_scene_lines: tuple[str, ...] = ()
    progression_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class CampaignStateSummary:
    campaign: str
    title: str
    current_location: str
    party_goal_lines: tuple[str, ...] = ()
    unresolved_consequence_lines: tuple[str, ...] = ()
    party_belief_lines: tuple[str, ...] = ()
    recent_change_lines: tuple[str, ...] = ()
    progression_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class OpenLoopsSummary:
    campaign: str
    title: str
    loop_lines: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveredSecretsSummary:
    campaign: str
    title: str
    secret_lines: tuple[str, ...]


@dataclass(frozen=True)
class SceneState:
    scene_id: str
    campaign: str
    title: str
    canonical_location: str
    occupant_lines: tuple[str, ...] = ()
    terrain_change_lines: tuple[str, ...] = ()
    discovered_clue_lines: tuple[str, ...] = ()
    triggered_event_lines: tuple[str, ...] = ()
    unresolved_tension_lines: tuple[str, ...] = ()
    exit_lines: tuple[str, ...] = ()
    described_to_players_lines: tuple[str, ...] = ()
    hidden_state_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class NpcPlaybook:
    npc_id: str
    campaign: str
    title: str
    voice_lines: tuple[str, ...] = ()
    current_stance: str = ''
    trust_lines: tuple[str, ...] = ()
    reveal_lines: tuple[str, ...] = ()
    withholding_lines: tuple[str, ...] = ()
    reveal_ladder_lines: tuple[str, ...] = ()
    habit_lines: tuple[str, ...] = ()
    contradiction_lines: tuple[str, ...] = ()
    recent_interaction_lines: tuple[str, ...] = ()
    local_goal_lines: tuple[str, ...] = ()
    warning_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class MemoryWriteResult:
    path: Path
    document: MarkdownDocument


class DmMemoryWriter:
    def __init__(self, root: Path, *, campaign_id: str) -> None:
        self.root = root.resolve()
        self.campaign_id = campaign_id

    @property
    def campaign_root(self) -> Path:
        return self.root / self.campaign_id

    @property
    def dm_root(self) -> Path:
        return self.campaign_root / 'dm'

    @property
    def summaries_root(self) -> Path:
        return self.dm_root / 'summaries'

    @property
    def sessions_root(self) -> Path:
        return self.dm_root / 'sessions'

    @property
    def npc_playbooks_root(self) -> Path:
        return self.dm_root / 'npc-playbooks'

    @property
    def scene_state_root(self) -> Path:
        return self.dm_root / 'scene-state'

    def write_session_log(self, entry: SessionLogEntry) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=entry.session_id,
            type=MarkdownDocumentType.SESSION_LOG,
            title=entry.title,
            campaign=entry.campaign,
            tags=('session',),
            visibility='dm',
            state_scope='session',
        )
        body = self._render_sections(
            (
                ('Session Recap', entry.recap_lines),
                ('World Changes', entry.changes_lines),
                ('Clues Revealed', entry.clue_lines),
                ('Unresolved Hooks', entry.unresolved_hook_lines),
                ('Likely Next Scenes', entry.next_scene_lines),
                ('Progression', entry.progression_lines),
            )
        )
        return self._write(self.sessions_root / f'{entry.session_id}.md', metadata, body)

    def write_campaign_state(self, summary: CampaignStateSummary) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=f'{summary.campaign}-campaign-state',
            type=MarkdownDocumentType.DM_SUMMARY,
            title=summary.title,
            campaign=summary.campaign,
            tags=('campaign-state',),
            visibility='dm',
            state_scope='campaign',
        )
        body = self._render_sections(
            (
                ('Current Location', (summary.current_location,)),
                ('Party Goals', summary.party_goal_lines),
                ('Unresolved Consequences', summary.unresolved_consequence_lines),
                ('What the Party Believes', summary.party_belief_lines),
                ('Recent Changes', summary.recent_change_lines),
                ('Progression', summary.progression_lines),
            )
        )
        return self._write(self.summaries_root / 'campaign-state.md', metadata, body)

    def write_open_loops(self, summary: OpenLoopsSummary) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=f'{summary.campaign}-open-loops',
            type=MarkdownDocumentType.DM_SUMMARY,
            title=summary.title,
            campaign=summary.campaign,
            tags=('open-loops',),
            visibility='dm',
            state_scope='campaign',
        )
        return self._write(self.summaries_root / 'open-loops.md', metadata, self._render_sections((('Open Loops', summary.loop_lines),)))

    def write_discovered_secrets(self, summary: DiscoveredSecretsSummary) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=f'{summary.campaign}-discovered-secrets',
            type=MarkdownDocumentType.DM_SUMMARY,
            title=summary.title,
            campaign=summary.campaign,
            tags=('discovered-secrets',),
            visibility='dm',
            state_scope='campaign',
        )
        return self._write(self.summaries_root / 'discovered-secrets.md', metadata, self._render_sections((('Discovered Secrets', summary.secret_lines),)))

    def write_scene_state(self, state: SceneState) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=f'scene-state-{state.scene_id}',
            type=MarkdownDocumentType.SCENE_STATE,
            title=state.title,
            campaign=state.campaign,
            canonical_location=state.canonical_location,
            tags=('scene-state', state.canonical_location),
            visibility='dm',
            state_scope='scene',
        )
        body = self._render_sections(
            (
                ('Current Occupants', state.occupant_lines),
                ('Changed Terrain or Objects', state.terrain_change_lines),
                ('Discovered Clues', state.discovered_clue_lines),
                ('Triggered Events', state.triggered_event_lines),
                ('Unresolved Tensions', state.unresolved_tension_lines),
                ('Exits and Next Steps', state.exit_lines),
                ('Described to Players', state.described_to_players_lines),
                ('Hidden State', state.hidden_state_lines),
            )
        )
        return self._write(self.scene_state_root / f'{state.scene_id}.md', metadata, body)

    def write_npc_playbook(self, playbook: NpcPlaybook) -> MemoryWriteResult:
        metadata = MarkdownMetadata(
            id=playbook.npc_id,
            type=MarkdownDocumentType.NPC_PLAYBOOK,
            title=playbook.title,
            campaign=playbook.campaign,
            tags=('npc-playbook',),
            visibility='dm',
            state_scope='npc',
        )
        body = self._render_sections(
            (
                ('Voice and Habits', playbook.voice_lines),
                ('Current Stance', (playbook.current_stance,) if playbook.current_stance else ()),
                ('Trust and Leverage', playbook.trust_lines),
                ('What They Will Reveal', playbook.reveal_lines),
                ('What They Are Withholding', playbook.withholding_lines),
                ('Reveal Ladder', playbook.reveal_ladder_lines),
                ('Conversational Habits', playbook.habit_lines),
                ('Contradictions and Motives', playbook.contradiction_lines),
                ('Recent Interactions', playbook.recent_interaction_lines),
                ('Current Local Goals', playbook.local_goal_lines),
                ('Do Not Casually Reveal', playbook.warning_lines),
            )
        )
        return self._write(self.npc_playbooks_root / f'{playbook.npc_id}.md', metadata, body)

    def _write(self, path: Path, metadata: MarkdownMetadata, body: str) -> MemoryWriteResult:
        document = MarkdownDocument(metadata=metadata, body=body)
        write_markdown_document(path, document)
        return MemoryWriteResult(path=path, document=document)

    def _render_sections(self, sections: Sequence[tuple[str, Sequence[str]]]) -> str:
        lines: list[str] = []
        for heading, items in sections:
            lines.append(f'# {heading}')
            normalized = [item.strip() for item in items if item and item.strip()]
            if not normalized:
                lines.append('None.')
                lines.append('')
                continue
            for item in normalized:
                lines.append(f'- {item}')
            lines.append('')
        return '\n'.join(lines).rstrip() + '\n'

