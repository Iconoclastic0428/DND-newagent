from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.evaluation import summarize_policy_evaluation, write_policy_evaluation_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Summarize policy performance from a training_transitions.jsonl file.')
    parser.add_argument('--transitions', type=Path, required=True, help='Input training transitions JSONL file.')
    parser.add_argument('--output', type=Path, help='Optional output JSON report path.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = summarize_policy_evaluation(args.transitions)
    if args.output is not None:
        write_policy_evaluation_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
