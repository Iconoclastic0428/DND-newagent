from __future__ import annotations

import json
from pathlib import Path
import shutil
import unittest
from uuid import uuid4

from training.dataset_manifest import DATASET_MANIFEST_SCHEMA_VERSION, write_dataset_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]


class DatasetManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.dataset-manifest-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_write_dataset_manifest_records_provenance_and_reward_schema(self) -> None:
        dataset_path = self._tempdir / 'training_transitions.jsonl'
        dataset_path.write_text('{"sample_id": "one"}\n', encoding='utf-8')
        source_path = self._tempdir / 'trajectory.jsonl'
        source_path.write_text('{"record_type": "turn"}\n', encoding='utf-8')

        manifest_path = write_dataset_manifest(
            dataset_type='training_transitions',
            dataset_path=dataset_path,
            record_count=1,
            source_paths=[source_path],
            filters={'include_roles': ['player']},
            context={'scenario_id': 'lmop_first_combat', 'policy': 'scripted'},
        )

        self.assertEqual(manifest_path, dataset_path.with_name(dataset_path.name + '.manifest.json'))
        manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        self.assertEqual(manifest['schema_version'], DATASET_MANIFEST_SCHEMA_VERSION)
        self.assertEqual(manifest['dataset_type'], 'training_transitions')
        self.assertEqual(manifest['record_count'], 1)
        self.assertEqual(manifest['source_paths'], [str(source_path)])
        self.assertEqual(manifest['filters']['include_roles'], ['player'])
        self.assertEqual(manifest['context']['policy'], 'scripted')
        self.assertIn('enemy_damage', manifest['reward_schema']['component_to_channel'])
        self.assertEqual(manifest['reward_schema']['terminal_reward_channel'], 'terminal')
        self.assertIsInstance(manifest['dataset_sha256'], str)


if __name__ == '__main__':
    unittest.main()
