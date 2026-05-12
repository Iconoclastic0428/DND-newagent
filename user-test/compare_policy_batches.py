from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.comparison import compare_policy_batches, load_batch_report, write_policy_comparison_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Compare policy/model performance across batch_report.json files.')
    parser.add_argument(
        '--batch',
        action='append',
        required=True,
        metavar='LABEL=PATH',
        help='Batch report to compare. Use LABEL=path/to/batch_report.json, or just a path to use its batch_id as the label.',
    )
    parser.add_argument('--output', type=Path, help='Optional output JSON comparison report path.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    entries = [_load_batch_arg(raw) for raw in args.batch]
    report = compare_policy_batches(entries)
    if args.output is not None:
        write_policy_comparison_report(report, args.output)
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def _load_batch_arg(raw: str):
    if '=' in raw:
        label, path_text = raw.split('=', 1)
        label = label.strip()
        path_text = path_text.strip()
        if not label:
            raise ValueError(f'Batch label cannot be empty: {raw!r}.')
        if not path_text:
            raise ValueError(f'Batch path cannot be empty: {raw!r}.')
        report = load_batch_report(path_text)
        return label, report
    report = load_batch_report(raw)
    label = str(report.get('batch_id') or Path(raw).parent.name or raw)
    return label, report


if __name__ == '__main__':
    raise SystemExit(main())
