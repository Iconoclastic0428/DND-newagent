from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.transitions import build_training_transitions, write_training_transitions_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Export RL-style per-player transitions from a trajectory JSONL file.')
    parser.add_argument('--trajectory', type=Path, required=True, help='Input trajectory.jsonl file.')
    parser.add_argument('--output', type=Path, required=True, help='Output training transitions JSONL file.')
    parser.add_argument('--include-dm', action='store_true', help='Also export DM turns. Defaults to player turns only.')
    parser.add_argument('--exclude-errors', action='store_true', help='Skip transitions whose action raised an error.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    roles = ('player', 'dm') if args.include_dm else ('player',)
    transitions = build_training_transitions(
        args.trajectory,
        include_roles=roles,
        include_errors=not args.exclude_errors,
    )
    path = write_training_transitions_jsonl(transitions, args.output)
    print(json.dumps({'transition_count': len(transitions), 'output_path': str(path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
