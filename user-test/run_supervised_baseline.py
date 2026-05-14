from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.supervised_baseline import SupervisedBaselineError, run_supervised_action_baseline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run a lightweight supervised action-prediction baseline from a training recipe.')
    parser.add_argument('--recipe', type=Path, required=True, help='Path to training_recipe.json.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/training-runs'), help='Directory for baseline run reports.')
    parser.add_argument('--run-name', default='supervised-baseline', help='Human-readable run name used in the output id.')
    parser.add_argument('--holdout-fraction', type=float, default=0.2, help='Fraction of rows held out for evaluation.')
    parser.add_argument('--smoothing-alpha', type=float, default=1.0, help='Additive smoothing for negative log loss.')
    parser.add_argument('--max-records', type=int, help='Optional cap on transition rows used by the baseline.')
    parser.add_argument(
        '--split-strategy',
        choices=('hash', 'tail'),
        default='hash',
        help='Deterministic train/eval split strategy.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_supervised_action_baseline(
            args.recipe,
            output_dir=args.output_dir,
            run_name=args.run_name,
            holdout_fraction=args.holdout_fraction,
            smoothing_alpha=args.smoothing_alpha,
            max_records=args.max_records,
            split_strategy=args.split_strategy,
        )
    except SupervisedBaselineError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
