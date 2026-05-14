from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.training_recipe import TrainingRecipeError, build_training_recipe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a dry-run trainer recipe from a training smoke report.')
    parser.add_argument('--smoke-report', type=Path, required=True, help='Path to training_smoke_report.json.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/training-recipes'), help='Directory for recipe outputs.')
    parser.add_argument('--recipe-name', default='training-recipe', help='Human-readable recipe name used in the output id.')
    parser.add_argument(
        '--supervised-weight',
        type=float,
        default=0.6,
        help='Relative weight for supervised action prediction.',
    )
    parser.add_argument(
        '--preference-weight',
        type=float,
        default=0.4,
        help='Relative weight for preference ranking.',
    )
    parser.add_argument(
        '--allow-failed-smoke',
        action='store_true',
        help='Write a recipe even when the smoke report has failed checks or non-ready readiness.',
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        recipe = build_training_recipe(
            args.smoke_report,
            output_dir=args.output_dir,
            recipe_name=args.recipe_name,
            objective_mix={
                'supervised_action_prediction': args.supervised_weight,
                'preference_ranking': args.preference_weight,
            },
            allow_failed_smoke=args.allow_failed_smoke,
        )
    except TrainingRecipeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(recipe, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
