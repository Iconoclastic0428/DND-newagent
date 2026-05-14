from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.evaluation import load_transition_records
from training.dataset_manifest import write_dataset_manifest
from training.preferences import build_preference_pairs, write_preference_pairs_jsonl


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Export DPO-style preference candidates from training transition JSONL files.')
    parser.add_argument('--transitions', type=Path, action='append', required=True, help='Input training transitions JSONL file. Repeat to combine batches.')
    parser.add_argument('--output', type=Path, required=True, help='Output preference pairs JSONL file.')
    parser.add_argument('--manifest-output', type=Path, help='Optional dataset manifest JSON path. Defaults to OUTPUT.manifest.json.')
    parser.add_argument('--min-reward-gap', type=float, default=0.05, help='Minimum reward gap required between chosen and rejected actions.')
    parser.add_argument('--max-pairs-per-context', type=int, default=3, help='Maximum pairs to emit from one matching context.')
    parser.add_argument('--exclude-errors', action='store_true', help='Do not use errored actions as rejected candidates.')
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    transitions = []
    for path in args.transitions:
        transitions.extend(load_transition_records(path))
    pairs = build_preference_pairs(
        transitions,
        min_reward_gap=args.min_reward_gap,
        max_pairs_per_context=args.max_pairs_per_context,
        include_errors=not args.exclude_errors,
    )
    output_path = write_preference_pairs_jsonl(pairs, args.output)
    manifest_path = write_dataset_manifest(
        dataset_type='preference_pairs',
        dataset_path=output_path,
        record_count=len(pairs),
        source_paths=args.transitions,
        manifest_path=args.manifest_output,
        filters={
            'min_reward_gap': args.min_reward_gap,
            'max_pairs_per_context': args.max_pairs_per_context,
            'include_errors': not args.exclude_errors,
        },
        context={'transition_paths': [str(path) for path in args.transitions]},
    )
    print(json.dumps({
        'preference_pair_count': len(pairs),
        'output_path': str(output_path),
        'manifest_path': str(manifest_path),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
