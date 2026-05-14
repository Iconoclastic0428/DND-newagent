from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.training_smoke import TrainingSmokeError, build_training_smoke_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a dry-run training smoke report from ready datasets.')
    parser.add_argument(
        '--input',
        type=Path,
        action='append',
        required=True,
        help='Dataset directory, collection report, benchmark root, or readiness artifact path. Repeat to combine sources.',
    )
    parser.add_argument('--benchmark-history', type=Path, help='Optional explicit benchmark_history.jsonl path.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/training-smoke'), help='Directory for smoke run reports.')
    parser.add_argument('--run-name', default='training-smoke', help='Human-readable run name used in the output id.')
    parser.add_argument('--transition-sample-limit', type=int, default=5, help='Number of transition rows to preview.')
    parser.add_argument('--preference-sample-limit', type=int, default=5, help='Number of preference rows to preview.')
    parser.add_argument(
        '--allow-not-ready',
        action='store_true',
        help='Write a smoke report even when readiness has warnings or blockers.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = build_training_smoke_report(
            args.input,
            output_dir=args.output_dir,
            run_name=args.run_name,
            transition_sample_limit=args.transition_sample_limit,
            preference_sample_limit=args.preference_sample_limit,
            benchmark_history_path=args.benchmark_history,
            allow_not_ready=args.allow_not_ready,
        )
    except TrainingSmokeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
