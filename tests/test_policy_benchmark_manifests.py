from __future__ import annotations

import json
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_DIR = REPO_ROOT / 'user-test' / 'full-story-demo' / 'scripts'


class PolicyBenchmarkManifestTests(unittest.TestCase):
    def test_committed_policy_benchmark_manifests_are_valid_json_without_secrets(self) -> None:
        manifest_paths = sorted(MANIFEST_DIR.glob('policy-benchmark*.json'))
        self.assertGreaterEqual(len(manifest_paths), 4)
        for manifest_path in manifest_paths:
            with self.subTest(manifest=manifest_path.name):
                raw_text = manifest_path.read_text(encoding='utf-8')
                self.assertNotIn('sk-', raw_text)
                manifest = json.loads(raw_text)
                self.assertIsInstance(manifest.get('policies'), list)
                self.assertGreater(len(manifest['policies']), 0)
                self.assertEqual(manifest.get('scenario_id', 'lmop_first_combat'), 'lmop_first_combat')
                self.assertIsInstance(manifest.get('seeds', [0]), list)
                self.assertGreater(len(manifest.get('seeds', [0])), 0)
                for policy_entry in manifest['policies']:
                    if isinstance(policy_entry, str):
                        continue
                    self.assertIsInstance(policy_entry, dict)
                    self.assertIn(policy_entry.get('policy'), {'scripted', 'random-legal', 'llm-party'})
                    llm_players = policy_entry.get('llm_players')
                    if llm_players is not None:
                        self.assertIsInstance(llm_players, dict)
                        for controller_id, env_path in llm_players.items():
                            self.assertRegex(controller_id, r'^player-[1-4]-controller$')
                            self.assertTrue(str(env_path).endswith('.env'))


if __name__ == '__main__':
    unittest.main()
