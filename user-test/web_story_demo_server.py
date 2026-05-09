from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

USER_TEST_ROOT = Path(__file__).resolve().parent
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from dm_agent.client import LLMClient
from dm_agent.config import load_llm_config
from session_server.llm_player import LLMPlayerAgent
from session_server.web_server import SessionWebServer
from shared_types.errors import ContentLoadError, EncounterError
from shared_types.web_ui import WebControllerGrant
from story_demo_system_server import build_full_story_demo_manual_session
from training.trajectory import TrajectoryRecorder


_CONTROLLER_IDS = (
    'dm',
    'player-1-controller',
    'player-2-controller',
    'player-3-controller',
    'player-4-controller',
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the browser-based LMOP full-story demo server.')
    parser.add_argument('--host', default='127.0.0.1', help='Host interface for HTTP and WebSocket listeners.')
    parser.add_argument('--http-port', type=int, default=8000, help='HTTP port for the static frontend. Use 0 for ephemeral.')
    parser.add_argument('--ws-port', type=int, default=8767, help='WebSocket port for realtime updates. Use 0 for ephemeral.')
    parser.add_argument('--env-path', type=Path, default=Path('.env'), help='Path to the local .env file for DM runtime config.')
    parser.add_argument('--campaign-root', type=Path, help='Optional override for the campaign markdown root.')
    parser.add_argument('--base-url', help='Optional override for the 5etools mirror base URL.')
    parser.add_argument('--local-llm', action='store_true', help='Use a deterministic in-process LLM transport for local demo verification.')
    parser.add_argument(
        '--start-in-character-creation',
        action='store_true',
        help='Start in character creation instead of precreating the four default player characters.',
    )
    parser.add_argument('--save-characters', type=Path, help='Write confirmed character records to this JSON party file.')
    parser.add_argument('--load-characters', type=Path, help='Load confirmed character records from this JSON party file and start the story immediately.')
    parser.add_argument(
        '--llm-player',
        action='append',
        default=[],
        metavar='CONTROLLER_ID=ENV_PATH',
        help='Assign an LLM to a player controller using a separate env file. Repeat for multiple LLM players.',
    )
    parser.add_argument(
        '--llm-player-max-actions-per-pump',
        type=int,
        default=1,
        help='Maximum LLM player actions to submit after each web input.',
    )
    parser.add_argument(
        '--disable-llm-player-autopump',
        action='store_true',
        help='Configure LLM players but do not automatically submit their actions after web inputs.',
    )
    parser.add_argument(
        '--trajectory-dir',
        type=Path,
        default=Path('runs/episodes'),
        help='Directory where per-episode trajectory JSONL logs are written.',
    )
    parser.add_argument(
        '--disable-trajectory-logging',
        action='store_true',
        help='Disable JSONL trajectory logging for this run.',
    )
    return parser.parse_args()


class LocalDemoLLMTransport:
    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        del url, headers
        return {'output_text': json.dumps(self._response_payload(payload), ensure_ascii=False)}

    def stream(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        response = self.post(url=url, headers=headers, payload=payload)
        if 'messages' in payload:
            content = str(response.get('output_text', ''))
            return [{'choices': [{'delta': {'content': content}, 'finish_reason': 'stop'}]}]
        return [{'type': 'response.completed', 'response': response}]

    def _response_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        metadata = payload.get('metadata')
        request_type = metadata.get('request_type') if isinstance(metadata, dict) else None
        if request_type == 'mode_switch':
            return {
                'decision_type': 'stay_in_storytelling',
                'reason': 'Local demo transport keeps the scene in storytelling mode.',
                'enter_combat_plan': None,
                'exit_combat_plan': None,
                'confidence': 1.0,
            }
        if request_type == 'story_spellcasting_reaction':
            return {
                'public_narration': 'The local demo DM treats the harmless magic as routine and keeps the scene moving.',
                'witness_reactions': [],
                'scene_note': 'Local deterministic verification response.',
                'dm_note': 'No escalation in local demo mode.',
                'escalation': {'recommended': False, 'reason': '', 'mode_switch_decision': None},
            }
        return {
            'public_narration': 'The local demo DM acknowledges the declaration and keeps the party moving toward Phandalin.',
            'transcript_entries': [
                {
                    'speaker': 'DM',
                    'text': 'The conversation stays friendly, practical details are shared, and the road remains the next priority.',
                    'visibility': 'public',
                }
            ],
            'check_request': None,
            'scene_update': {
                'summary': 'The party keeps Gundren and Sildar cooperative before setting out for Phandalin.',
                'open_loops': ['Reach Phandalin safely.', 'Learn why Gundren is protecting his discovery.'],
                'party_goals': ['Escort the wagon north.', 'Watch the road for trouble.'],
                'party_beliefs': ['Gundren is cautious but friendly.'],
            },
            'mode_switch_decision': None,
            'memory_note': 'Local deterministic demo response used for web-runner verification.',
        }

def _controller_grants(session, *, session_id: str) -> tuple[WebControllerGrant, ...]:
    grants: list[WebControllerGrant] = []
    for controller_id in _CONTROLLER_IDS:
        binding = session.validate_controller(controller_id)
        grants.append(
            WebControllerGrant(
                session_id=session_id,
                controller_id=controller_id,
                controller_token=f'{controller_id}-token',
                role=binding.role,
                label=binding.label,
            )
        )
    return tuple(grants)


def _build_llm_player_agents(specs: tuple[str, ...] | list[str]) -> tuple[LLMPlayerAgent, ...]:
    agents: list[LLMPlayerAgent] = []
    for spec in specs:
        if '=' not in spec:
            raise ValueError(f'LLM player spec must be CONTROLLER_ID=ENV_PATH: {spec!r}')
        controller_id, raw_env_path = spec.split('=', 1)
        controller_id = controller_id.strip()
        env_path = Path(raw_env_path.strip())
        if not controller_id or not raw_env_path.strip():
            raise ValueError(f'LLM player spec must include both controller and env path: {spec!r}')
        config = load_llm_config(env_path=env_path)
        agents.append(
            LLMPlayerAgent(
                controller_id=controller_id,
                client=LLMClient(config),
                label=f'{controller_id}:{config.responses_model}',
            )
        )
    return tuple(agents)



def main() -> int:
    args = parse_args()
    try:
        session_id = 'lmop-web-demo'
        llm_player_agents = _build_llm_player_agents(tuple(args.llm_player))
        trajectory_recorder = None
        if not args.disable_trajectory_logging:
            trajectory_recorder = TrajectoryRecorder(
                output_dir=args.trajectory_dir,
                scenario_id='lmop_full_story_demo',
            )
            print(f'[web] Trajectory log: {trajectory_recorder.path}', flush=True)
        session = build_full_story_demo_manual_session(
            base_url=args.base_url,
            campaign_root=args.campaign_root,
            env_path=args.env_path,
            client_transport=LocalDemoLLMTransport() if args.local_llm else None,
            precreate_characters=not args.start_in_character_creation and args.load_characters is None,
            character_load_path=args.load_characters,
            character_save_path=args.save_characters,
            llm_player_agents=llm_player_agents,
            llm_player_autopump=bool(llm_player_agents) and not args.disable_llm_player_autopump,
            llm_player_max_actions_per_pump=args.llm_player_max_actions_per_pump,
            trajectory_recorder=trajectory_recorder,
        )
        server = SessionWebServer(
            session=session,
            session_id=session_id,
            controller_grants=_controller_grants(session, session_id=session_id),
            http_host=args.host,
            http_port=args.http_port,
            websocket_host=args.host,
            websocket_port=args.ws_port,
            automation_api_enabled=True,
        )
        server.serve_forever()
        return 0
    except (ContentLoadError, EncounterError, RuntimeError) as exc:
        print(f'ERROR: {exc}')
        return 1
    except ValueError as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
