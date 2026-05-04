from __future__ import annotations

from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from user_test_controller_wrapper import run_client


if __name__ == '__main__':
    raise SystemExit(run_client('dm'))
