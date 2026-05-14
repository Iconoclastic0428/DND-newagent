from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_collection import collect_training_datasets


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Collect benchmark transition/preference JSONL files into combined training datasets.')
    parser.add_argument(
        '--input',
        type=Path,
        action='append',
        required=True,
        help='Benchmark root, benchmark_report.json, or batch_report.json. Repeat to combine sources.',
    )
    parser.add_argument('--output-dir', type=Path, required=True, help='Directory for combined datasets and collection report.')
    parser.add_argument('--transitions-only', action='store_true', help='Only write combined_training_transitions.jsonl.')
    parser.add_argument('--preferences-only', action='store_true', help='Only write combined_preference_pairs.jsonl.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.transitions_only and args.preferences_only:
        raise SystemExit('--transitions-only and --preferences-only cannot be used together.')
    report = collect_training_datasets(
        args.input,
        output_dir=args.output_dir,
        include_transitions=not args.preferences_only,
        include_preferences=not args.transitions_only,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
