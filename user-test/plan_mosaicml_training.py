from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.mosaicml_plan import MosaicMLPlanError, build_mosaicml_training_plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Create a MosaicML GPU training handoff plan from a recipe and baseline report.')
    parser.add_argument('--recipe', type=Path, required=True, help='Path to training_recipe.json.')
    parser.add_argument('--baseline-report', type=Path, required=True, help='Path to supervised_baseline_report.json.')
    parser.add_argument('--output-dir', type=Path, default=Path('runs/mosaicml-plans'), help='Directory for MosaicML plan outputs.')
    parser.add_argument('--plan-name', default='mosaicml-training-plan', help='Human-readable plan name used in the output id.')
    parser.add_argument('--accelerator', default='gpu', help='Remote accelerator family expected for training.')
    parser.add_argument('--gpu-type', default='configured-by-mosaicml-workspace', help='MosaicML GPU type or workspace preset.')
    parser.add_argument('--container-image', default='configured-by-mosaicml-workspace', help='MosaicML container image or workspace preset.')
    parser.add_argument('--target-delta', type=float, default=0.05, help='Accuracy delta target above aggregate baseline eval accuracy.')
    parser.add_argument('--weak-slice-target-delta', type=float, default=0.10, help='Accuracy delta target above weak slice baseline accuracy.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        plan = build_mosaicml_training_plan(
            args.recipe,
            baseline_report_path=args.baseline_report,
            output_dir=args.output_dir,
            plan_name=args.plan_name,
            accelerator=args.accelerator,
            gpu_type=args.gpu_type,
            container_image=args.container_image,
            target_delta=args.target_delta,
            weak_slice_target_delta=args.weak_slice_target_delta,
        )
    except MosaicMLPlanError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
