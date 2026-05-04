from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from session_server.bootstrap import build_goblin_ambush_encounter_session
from session_server.orchestrator import EncounterOrchestratorServer
from shared_types.errors import CharacterCreationError, ContentLoadError, EncounterError


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the authoritative D&D encounter orchestrator server.')
    parser.add_argument('--host', default='127.0.0.1', help='Host interface to bind.')
    parser.add_argument('--port', type=int, default=8765, help='TCP port to bind. Use 0 for an ephemeral port.')
    parser.add_argument('--no-auto-start', action='store_true', help='Do not auto-start the encounter on boot.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        server = EncounterOrchestratorServer(
            session=build_goblin_ambush_encounter_session(),
            host=args.host,
            port=args.port,
            auto_start=not args.no_auto_start,
        )
        server.serve_forever()
        return 0
    except (CharacterCreationError, ContentLoadError, EncounterError, RuntimeError) as exc:
        print(f'ERROR: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
