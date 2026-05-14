from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.readiness_report import (
    build_training_readiness_report,
    write_training_readiness_markdown,
    write_training_readiness_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Summarize whether collected benchmark datasets are ready for training.')
    parser.add_argument(
        '--input',
        type=Path,
        action='append',
        required=True,
        help='Dataset directory, collection report, benchmark root, or readiness artifact path. Repeat to combine sources.',
    )
    parser.add_argument('--benchmark-history', type=Path, help='Optional explicit benchmark_history.jsonl path.')
    parser.add_argument('--output-json', type=Path, help='Optional JSON report output path.')
    parser.add_argument('--output-md', type=Path, help='Optional Markdown report output path.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_training_readiness_report(
        args.input,
        benchmark_history_path=args.benchmark_history,
    )
    if args.output_json is not None:
        write_training_readiness_report(report, args.output_json)
    if args.output_md is not None:
        write_training_readiness_markdown(report, args.output_md)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if report['status'] == 'blocked' else 0


if __name__ == '__main__':
    raise SystemExit(main())
