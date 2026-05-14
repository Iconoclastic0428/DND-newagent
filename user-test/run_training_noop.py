from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.training_noop import TrainingNoOpError, run_noop_training_epoch


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run a no-op trainer accounting pass from a training recipe.')
    parser.add_argument('--recipe', type=Path, required=True, help='Path to training_recipe.json.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/training-runs'), help='Directory for no-op run reports.')
    parser.add_argument('--run-name', default='noop-training', help='Human-readable run name used in the output id.')
    parser.add_argument(
        '--max-records-per-objective',
        type=int,
        help='Optional cap on rows consumed per objective during the accounting pass.',
    )
    parser.add_argument(
        '--allow-record-mismatch',
        action='store_true',
        help='Write a report even when observed dataset counts differ from the recipe.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_noop_training_epoch(
            args.recipe,
            output_dir=args.output_dir,
            run_name=args.run_name,
            max_records_per_objective=args.max_records_per_objective,
            allow_record_mismatch=args.allow_record_mismatch,
        )
    except TrainingNoOpError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
