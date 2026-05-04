from __future__ import annotations

import sys

from encounter_controller_client import main as controller_main


def main_for_controller(controller_id: str) -> int:
    argv = ['story-demo-controller', '--controller-id', controller_id, *sys.argv[1:]]
    previous = sys.argv
    try:
        sys.argv = argv
        return controller_main()
    finally:
        sys.argv = previous
