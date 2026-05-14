from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.dataset_quality import validate_preference_dataset, validate_transition_dataset, write_dataset_quality_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Validate training dataset JSONL files before model training.')
    parser.add_argument('--transitions', type=Path, help='Training transitions JSONL file to validate.')
    parser.add_argument('--preferences', type=Path, help='Preference pairs JSONL file to validate.')
    parser.add_argument('--output-dir', type=Path, help='Optional directory for quality reports. Defaults next to each dataset.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.transitions is None and args.preferences is None:
        raise SystemExit('Provide --transitions, --preferences, or both.')
    reports = {}
    if args.transitions is not None:
        report = validate_transition_dataset(args.transitions)
        report_path = _quality_path(args.transitions, output_dir=args.output_dir)
        write_dataset_quality_report(report, report_path)
        reports['transitions'] = {'report_path': str(report_path), **report}
    if args.preferences is not None:
        report = validate_preference_dataset(args.preferences)
        report_path = _quality_path(args.preferences, output_dir=args.output_dir)
        write_dataset_quality_report(report, report_path)
        reports['preferences'] = {'report_path': str(report_path), **report}
    print(json.dumps(reports, ensure_ascii=False, indent=2, sort_keys=True))
    return 1 if any(report['status'] == 'fail' for report in reports.values()) else 0


def _quality_path(dataset_path: Path, *, output_dir: Path | None) -> Path:
    if output_dir is not None:
        return output_dir / f'{dataset_path.name}.quality.json'
    return dataset_path.with_name(dataset_path.name + '.quality.json')


if __name__ == '__main__':
    raise SystemExit(main())
