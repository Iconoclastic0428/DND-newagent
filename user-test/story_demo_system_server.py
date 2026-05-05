from __future__ import annotations

import argparse
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from character_creation import build_default_kernel
from player_interface import SlashCommandInterface
from session_server import StoryOrchestratorServer
from session_server.bootstrap import build_default_character_record, build_lmop_story_demo_session_from_records
from shared_types.encounter_control import ControllerBinding, ControllerRole
from shared_types.encounter_models import ActorSide, EncounterPhase
from shared_types.errors import CharacterCreationError, ContentLoadError, EncounterError, EncounterPermissionError, EncounterValidationError
from shared_types.models import CharacterRecord, ChoiceView, CreationState
from shared_types.storytelling import RuntimeMode


@dataclass(frozen=True)
class _CompletionState:
    result_summary: str
    detail_summary: str


class FullStoryDemoManualSession:
    _PLAYER_CONTROLLER_IDS = (
        'player-1-controller',
        'player-2-controller',
        'player-3-controller',
        'player-4-controller',
    )

    def __init__(
        self,
        *,
        base_url: str | None = None,
        campaign_root: str | Path | None = None,
        env_path: str | Path = '.env',
        client_transport=None,
        precreate_characters: bool = False,
    ) -> None:
        self.base_url = base_url
        self.campaign_root = campaign_root
        self.env_path = env_path
        self.client_transport = client_transport
        self.creation_kernel = build_default_kernel(base_url=base_url)
        self.creation_ui = SlashCommandInterface(self.creation_kernel)
        self.creation_states: dict[str, CreationState] = {
            controller_id: self.creation_kernel.new_state()
            for controller_id in self._PLAYER_CONTROLLER_IDS
        }
        self.confirmed_records: dict[str, CharacterRecord] = {}
        self.story_session = None
        self._llm_feedback_sink = None
        self._completion_state: _CompletionState | None = None
        self._controllers = {
            'dm': ControllerBinding(controller_id='dm', role=ControllerRole.DM, label='DM'),
            'player-1-controller': ControllerBinding(controller_id='player-1-controller', role=ControllerRole.PLAYER, label='Player 1'),
            'player-2-controller': ControllerBinding(controller_id='player-2-controller', role=ControllerRole.PLAYER, label='Player 2'),
            'player-3-controller': ControllerBinding(controller_id='player-3-controller', role=ControllerRole.PLAYER, label='Player 3'),
            'player-4-controller': ControllerBinding(controller_id='player-4-controller', role=ControllerRole.PLAYER, label='Player 4'),
        }
        if precreate_characters:
            self._precreate_default_party()

    @property
    def llm_feedback_sink(self):
        return self._llm_feedback_sink

    @llm_feedback_sink.setter
    def llm_feedback_sink(self, sink) -> None:
        self._llm_feedback_sink = sink
        if self.story_session is not None:
            self.story_session.llm_feedback_sink = sink

    @property
    def encounter_session(self):
        if self.story_session is None:
            raise EncounterPermissionError('The encounter session is not active until all four players confirm characters.')
        return self.story_session.encounter_session

    def validate_controller(self, controller_id: str) -> ControllerBinding:
        if self.story_session is not None:
            return self.story_session.validate_controller(controller_id)
        binding = self._controllers.get(controller_id)
        if binding is None:
            raise EncounterPermissionError(f'Unknown controller {controller_id!r}.')
        return binding

    def system_open_scene(self) -> None:
        if self.story_session is not None and self._completion_state is None:
            self.story_session.system_open_scene()

    def view_for_controller(self, controller_id: str):
        binding = self.validate_controller(controller_id)
        self._refresh_demo_completion()
        if self._completion_state is not None:
            return self._build_completion_view(controller_id)
        if self.story_session is not None:
            return self.story_session.view_for_controller(controller_id)
        if binding.role == ControllerRole.DM:
            return self._build_creation_overview_for_dm()
        return self._build_creation_view_for_player(controller_id)

    def prompt_for_controller(self, controller_id: str):
        self.validate_controller(controller_id)
        self._refresh_demo_completion()
        if self._completion_state is not None or self.story_session is None:
            return None
        return self.story_session.prompt_for_controller(controller_id)

    def handle_input(self, controller_id: str, raw_input: str):
        self.validate_controller(controller_id)
        raw_input = raw_input.strip()
        if not raw_input:
            return self.view_for_controller(controller_id)
        self._refresh_demo_completion()
        if self._completion_state is not None:
            if raw_input.lower() in {'/view', '/status'}:
                return self.view_for_controller(controller_id)
            raise EncounterPermissionError('The demo is complete. Restart the full story demo to play again.')
        if self.story_session is not None:
            result = self.story_session.handle_input(controller_id, raw_input)
            self._refresh_demo_completion()
            if self._completion_state is not None:
                return self.view_for_controller(controller_id)
            return result
        return self._handle_creation_input(controller_id, raw_input)

    def _handle_creation_input(self, controller_id: str, raw_input: str):
        binding = self._controllers[controller_id]
        if raw_input.lower() in {'/view', '/status'}:
            return self.view_for_controller(controller_id)
        if binding.role == ControllerRole.DM:
            raise EncounterPermissionError('The DM observes character creation in this demo. Players must complete `/create` before the campaign begins.')
        if not raw_input.startswith('/create'):
            raise EncounterPermissionError('The full story demo starts in deterministic character creation. Use `/create ...` commands until your character is confirmed.')
        state = self.creation_states[controller_id]
        updated_state, _rendered = self.creation_ui.execute(state, raw_input)
        self.creation_states[controller_id] = updated_state
        if updated_state.character_record is not None:
            self.confirmed_records[controller_id] = self._confirmed_record_copy(controller_id, updated_state.character_record)
        self._start_story_if_ready()
        return self.view_for_controller(controller_id)

    def _build_creation_view_for_player(self, controller_id: str):
        binding = self._controllers[controller_id]
        state = self.creation_states[controller_id]
        snapshot = self.creation_kernel.snapshot(state)
        summary_lines = [
            'Runtime mode: character-creation',
            'Campaign: lmop',
            'Demo phase: create your character',
            'The campaign will begin automatically after all four players confirm characters.',
            'Controller status:',
        ]
        summary_lines.extend(self._creation_status_lines())
        summary_lines.append(f'You are: {binding.label}')
        summary_lines.extend(snapshot.summary_lines)
        if state.character_record is None:
            summary_lines.append('Use `/create ...` commands to progress your character. Use `/view` to refresh this summary.')
            available_choices = snapshot.available_choices or {'create-flow': (ChoiceView(option_id='begin', label='Begin character creation', detail='Insert /create begin into the command box.'),)}
        else:
            summary_lines.append('Your character is confirmed. Wait for the other players to finish character creation.')
            available_choices = {}
        return self._story_view(summary_lines, available_choices)

    def _build_creation_overview_for_dm(self):
        summary_lines = [
            'Runtime mode: character-creation',
            'Campaign: lmop',
            'Demo phase: waiting for four player characters',
            'The DM observes creation. The campaign begins automatically after all four players confirm.',
            'Controller status:',
        ]
        summary_lines.extend(self._creation_status_lines())
        return self._story_view(summary_lines, {})

    def _creation_status_lines(self) -> tuple[str, ...]:
        lines: list[str] = []
        for controller_id in self._PLAYER_CONTROLLER_IDS:
            binding = self._controllers[controller_id]
            state = self.creation_states[controller_id]
            if state.character_record is None:
                lines.append(f'  - {binding.label}: {self.creation_kernel.phase(state).value}')
                continue
            record = state.character_record
            lines.append(
                f'  - {binding.label}: confirmed; species {record.species_id}; class {record.class_id}; background {record.background_id}'
            )
        return tuple(lines)

    def _confirmed_record_copy(self, controller_id: str, record: CharacterRecord) -> CharacterRecord:
        cloned = deepcopy(record)
        slot = self._PLAYER_CONTROLLER_IDS.index(controller_id) + 1
        cloned.record_id = f'level-1-character-p{slot}'
        return cloned

    def _precreate_default_party(self) -> None:
        if self.story_session is not None:
            raise EncounterValidationError('The story session is already active.')
        if self.confirmed_records:
            raise EncounterValidationError('Cannot precreate characters after character creation has started.')
        base_record = build_default_character_record(base_url=self.base_url)
        for controller_id in self._PLAYER_CONTROLLER_IDS:
            self.confirmed_records[controller_id] = self._confirmed_record_copy(controller_id, base_record)
        self._start_story_if_ready()

    def _start_story_if_ready(self) -> None:
        if self.story_session is not None:
            return
        if len(self.confirmed_records) != len(self._PLAYER_CONTROLLER_IDS):
            return
        ordered_records = tuple(self.confirmed_records[controller_id] for controller_id in self._PLAYER_CONTROLLER_IDS)
        self.story_session = build_lmop_story_demo_session_from_records(
            player_records=ordered_records,
            base_url=self.base_url,
            campaign_root=self.campaign_root,
            env_path=self.env_path,
            client_transport=self.client_transport,
        )
        self.story_session.llm_feedback_sink = self.llm_feedback_sink
        self.story_session.system_open_scene()
        self._refresh_demo_completion()

    def _refresh_demo_completion(self) -> None:
        if self.story_session is None or self._completion_state is not None:
            return
        state = self.story_session.state
        if self.story_session.story_state.runtime_mode != RuntimeMode.COMBAT:
            return
        if state.phase != EncounterPhase.COMPLETE:
            return
        if state.winning_side == ActorSide.PLAYER:
            self._completion_state = _CompletionState(
                result_summary='The party survived the goblin ambush.',
                detail_summary='Demo result: success. The party defeated or drove off the ambushers and secured the road.',
            )
            return
        if state.winning_side == ActorSide.MONSTER:
            self._completion_state = _CompletionState(
                result_summary='The goblin ambush defeated the party.',
                detail_summary='Demo result: defeat. All player characters were brought down before they could secure the trail.',
            )
            return
        raise EncounterValidationError('The ambush combat completed without a winning side.')

    def _build_completion_view(self, controller_id: str):
        assert self.story_session is not None
        assert self._completion_state is not None
        inner_view = self.story_session.view_for_controller(controller_id)
        filtered_inner_lines = [
            line for line in inner_view.summary_lines
            if not line.startswith('Runtime mode: ')
        ]
        summary_lines = [
            'Runtime mode: demo-complete',
            'Campaign: lmop',
            self._completion_state.result_summary,
            self._completion_state.detail_summary,
            'Final authoritative state:',
        ]
        summary_lines.extend(filtered_inner_lines)
        summary_lines.append('The demo is complete. Restart the full story demo to begin a new run.')
        return self._story_view(summary_lines, {})

    def _story_view(self, summary_lines, available_choices):
        from session_server.storytelling_session import StoryControllerView
        return StoryControllerView(summary_lines=tuple(summary_lines), available_choices=available_choices)


def build_full_story_demo_manual_session(
    *,
    base_url: str | None = None,
    campaign_root: str | Path | None = None,
    env_path: str | Path = '.env',
    client_transport=None,
    precreate_characters: bool = False,
) -> FullStoryDemoManualSession:
    return FullStoryDemoManualSession(
        base_url=base_url,
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=client_transport,
        precreate_characters=precreate_characters,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the authoritative LMoP storytelling/combat demo server.')
    parser.add_argument('--host', default='127.0.0.1', help='Host interface to bind.')
    parser.add_argument('--port', type=int, default=8766, help='TCP port to bind. Use 0 for an ephemeral port.')
    parser.add_argument('--campaign-root', type=Path, help='Override the campaign markdown root.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='Path to the local .env file.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        session = build_full_story_demo_manual_session(campaign_root=args.campaign_root, env_path=args.env_path)
        server = StoryOrchestratorServer(session=session, host=args.host, port=args.port)
        server.serve_forever()
        return 0
    except (CharacterCreationError, ContentLoadError, EncounterError, RuntimeError) as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
