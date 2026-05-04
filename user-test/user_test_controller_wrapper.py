from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent


def run_client(default_controller_id: str) -> int:
    parser = argparse.ArgumentParser(description='Wrapper for the generic encounter controller client.')
    parser.add_argument('--controller-id', default=default_controller_id)
    args, passthrough = parser.parse_known_args()
    command = [
        sys.executable,
        str(REPO_ROOT / 'encounter_controller_client.py'),
        '--controller-id',
        args.controller_id,
        *passthrough,
    ]
    return subprocess.call(command)
