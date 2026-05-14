from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.trainable_policy import TrainablePolicyError, run_trainable_policy_preflight


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run the first trainable policy preflight using the MosaicML entrypoint shape.')
    parser.add_argument('--recipe', type=Path, required=True, help='Path to training_recipe.json.')
    parser.add_argument('--baseline-report', type=Path, required=True, help='Path to supervised_baseline_report.json.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/training-runs'), help='Directory for training run outputs.')
    parser.add_argument('--run-name', default='mosaicml-trainable-policy', help='Human-readable run name used in the output id.')
    parser.add_argument('--epochs', type=int, default=8, help='Number of local preflight training epochs.')
    parser.add_argument('--learning-rate', type=float, default=1.0, help='Sparse perceptron learning rate.')
    parser.add_argument('--holdout-fraction', type=float, default=0.2, help='Fraction of rows held out for evaluation.')
    parser.add_argument(
        '--split-strategy',
        choices=('hash', 'tail'),
        default='hash',
        help='Deterministic train/eval split strategy.',
    )
    parser.add_argument('--max-records', type=int, help='Optional cap on transition rows used by the preflight.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = run_trainable_policy_preflight(
            args.recipe,
            baseline_report_path=args.baseline_report,
            output_dir=args.output_dir,
            run_name=args.run_name,
            epochs=args.epochs,
            learning_rate=args.learning_rate,
            holdout_fraction=args.holdout_fraction,
            split_strategy=args.split_strategy,
            max_records=args.max_records,
        )
    except TrainablePolicyError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
