from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

USER_TEST_ROOT = Path(__file__).resolve().parent
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from session_server.web_server import SessionWebServer
from shared_types.errors import ContentLoadError, EncounterError
from shared_types.web_ui import WebControllerGrant
from story_demo_system_server import build_full_story_demo_manual_session


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
    parser.add_argument(
        '--start-in-character-creation',
        action='store_true',
        help='Start in the old character-creation phase instead of precreating the four default player characters.',
    )
    return parser.parse_args()



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



def main() -> int:
    args = parse_args()
    try:
        session_id = 'lmop-web-demo'
        session = build_full_story_demo_manual_session(
            base_url=args.base_url,
            campaign_root=args.campaign_root,
            env_path=args.env_path,
            precreate_characters=not args.start_in_character_creation,
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


if __name__ == '__main__':
    raise SystemExit(main())
