from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from user_test_story_demo_helper import main_for_controller


if __name__ == '__main__':
    raise SystemExit(main_for_controller('player-2-controller'))
