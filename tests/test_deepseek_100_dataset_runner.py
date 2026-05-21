from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import unittest
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_deepseek_100_conversation_dataset import (
    _add_combined_dataset_quality_issues,
    _episode_paths,
    _server_command,
    _write_combined_datasets,
    build_dataset_quality_report,
    build_episode_plan,
    evaluate_pilot_control,
    run_dataset,
)


class DeepSeek100DatasetRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tempdir = REPO_ROOT / '.deepseek-100-tests' / uuid4().hex
        self._tempdir.mkdir(parents=True, exist_ok=False)

    def tearDown(self) -> None:
        shutil.rmtree(self._tempdir, ignore_errors=True)

    def test_build_episode_plan_balances_split_and_pilot_prefix(self) -> None:
        plan = build_episode_plan(
            episodes=10,
            positive_count=5,
            pilot_size=4,
            http_port_base=9100,
            ws_port_base=9200,
            negative_intensity=0.5,
        )

        labels = [spec.label for spec in plan]
        self.assertEqual(labels.count('positive'), 5)
        self.assertEqual(labels.count('negative'), 5)
        self.assertEqual(labels[:4].count('positive'), 2)
        self.assertEqual(labels[:4].count('negative'), 2)
        self.assertEqual(len({spec.http_port for spec in plan}), 10)
        self.assertEqual(len({spec.ws_port for spec in plan}), 10)
        self.assertEqual(plan[0].http_port, 9100)
        self.assertEqual(plan[1].http_port, 9102)

    def test_evaluate_pilot_control_increases_negative_intensity_when_rewards_are_too_high(self) -> None:
        decision = evaluate_pilot_control(
            [
                {'label': 'positive', 'status': 'completed', 'total_reward': 1.0, 'reward_channels': {'penalty': -0.02}},
                {'label': 'positive', 'status': 'completed', 'total_reward': 0.9, 'reward_channels': {'penalty': 0.0}},
                {'label': 'negative', 'status': 'completed', 'total_reward': 1.1, 'reward_channels': {'penalty': -0.01}},
                {'label': 'negative', 'status': 'completed', 'total_reward': 1.0, 'reward_channels': {'penalty': -0.02}},
            ],
            current_negative_intensity=0.4,
        )

        self.assertGreater(decision['negative_intensity'], 0.4)
        self.assertEqual(decision['action'], 'increase_negative_intensity')
        self.assertIn('negative rewards are not lower', decision['reason'])

    def test_quality_report_checks_split_terminals_rewards_and_artifacts(self) -> None:
        transcript = self._write_file('episode-001/transcript.md')
        trajectory = self._write_file('episode-001/trajectory.jsonl')
        raw_io = self._write_file('episode-001/raw-io.jsonl')
        results = [
            {
                'episode_id': 'episode-001',
                'label': 'positive',
                'status': 'completed',
                'terminal_reason': 'demo-complete',
                'total_reward': 1.25,
                'reward_channels': {'progress': 1.0, 'penalty': -0.1},
                'artifact_paths': {
                    'transcript': str(transcript),
                    'trajectory': str(trajectory),
                    'raw_interactions': str(raw_io),
                },
            },
            {
                'episode_id': 'episode-002',
                'label': 'negative',
                'status': 'failed',
                'terminal_reason': 'connector-error',
                'total_reward': -0.5,
                'reward_channels': {'penalty': -0.5},
                'artifact_paths': {},
            },
        ]

        report = build_dataset_quality_report(results, expected_episodes=2, expected_positive_count=1)

        self.assertEqual(report['status'], 'fail')
        self.assertEqual(report['label_counts'], {'negative': 1, 'positive': 1})
        self.assertEqual(report['completed_count'], 1)
        self.assertEqual(report['missing_artifact_count'], 3)
        self.assertEqual(report['reward_channel_totals']['penalty'], -0.6)
        self.assertTrue(any(issue['code'] == 'missing_artifact' for issue in report['issues']))
        self.assertTrue(any(issue['code'] == 'failed_episode_without_trajectory' for issue in report['issues']))

    def test_combined_dataset_failures_are_folded_into_run_quality(self) -> None:
        report = {
            'status': 'pass',
            'issues': [],
            'fail_count': 0,
            'warn_count': 0,
        }

        _add_combined_dataset_quality_issues(
            report,
            {
                'transition_quality': {'status': 'pass'},
                'preference_quality': {'status': 'fail'},
            },
        )

        self.assertEqual(report['status'], 'fail')
        self.assertEqual(report['fail_count'], 1)
        self.assertTrue(any(issue['code'] == 'combined_preference_dataset_quality' for issue in report['issues']))

    def test_combined_datasets_build_scene_level_preferences(self) -> None:
        run_dir = self._tempdir / 'run'
        first_transition = self._transition('episode-001:1', action='I press the attack.', reward=0.25)
        second_transition = self._transition('episode-002:1', action='I wait and do nothing.', reward=-0.05)
        second_transition['observation']['summary_lines'] = ['Runtime mode: storytelling', 'Different scene narration.']
        first_path = self._write_jsonl('episode-001/training_transitions.jsonl', [first_transition])
        second_path = self._write_jsonl('episode-002/training_transitions.jsonl', [second_transition])

        combined = _write_combined_datasets(
            run_dir,
            [
                {'artifact_paths': {'transitions': str(first_path)}},
                {'artifact_paths': {'transitions': str(second_path)}},
            ],
        )

        preference_rows = [
            json.loads(line)
            for line in Path(combined['preference_path']).read_text(encoding='utf-8').splitlines()
            if line.strip()
        ]
        self.assertEqual(combined['transition_quality']['status'], 'pass')
        self.assertEqual(combined['preference_quality']['status'], 'pass')
        self.assertEqual(len(preference_rows), 1)
        self.assertEqual(preference_rows[0]['context_strategy'], 'scene')

    def test_server_command_uses_isolated_episode_campaign_copy(self) -> None:
        source_campaign_root = self._tempdir / 'source-campaigns'
        source_maps = source_campaign_root / 'maps'
        source_maps.mkdir(parents=True)
        (source_maps / 'marker.md').write_text('source campaign\n', encoding='utf-8')
        episode_dir = self._tempdir / 'episode'
        paths = _episode_paths(episode_dir)
        args = SimpleNamespace(
            host='127.0.0.1',
            campaign_root=source_campaign_root,
        )
        spec = build_episode_plan(
            episodes=1,
            positive_count=1,
            pilot_size=1,
            http_port_base=9300,
            ws_port_base=9400,
            negative_intensity=0.5,
        )[0]

        command = _server_command(
            args,
            spec,
            paths,
            self._tempdir / 'dm.env',
            character_load_path=None,
            base_url='file:///mirror/',
        )

        campaign_arg_index = command.index('--campaign-root') + 1
        campaign_arg = Path(command[campaign_arg_index])
        self.assertNotEqual(campaign_arg, source_campaign_root.resolve())
        self.assertTrue(campaign_arg.is_relative_to(episode_dir.resolve()))
        self.assertEqual((campaign_arg / 'maps' / 'marker.md').read_text(encoding='utf-8'), 'source campaign\n')

    def test_connector_command_passes_llm_timeout(self) -> None:
        from run_deepseek_100_conversation_dataset import _connector_command

        paths = _episode_paths(self._tempdir / 'episode')
        args = SimpleNamespace(
            host='127.0.0.1',
            max_actions=90,
            poll_interval_seconds=0.5,
            monster_turn_delay_seconds=0.1,
            request_timeout_seconds=0.0,
            llm_timeout_seconds=180.0,
        )
        spec = build_episode_plan(
            episodes=1,
            positive_count=1,
            pilot_size=1,
            http_port_base=9300,
            ws_port_base=9400,
            negative_intensity=0.5,
        )[0]

        command = _connector_command(args, spec, paths, self._tempdir / 'player.env')

        timeout_index = command.index('--llm-timeout-seconds') + 1
        self.assertEqual(command[timeout_index], '180.0')

    def test_dry_run_writes_plan_and_report_without_episode_execution(self) -> None:
        args = SimpleNamespace(
            output_root=self._tempdir / 'runs',
            run_id='dry-run',
            episodes=4,
            positive_count=2,
            pilot_size=2,
            workers=2,
            http_port_base=9300,
            ws_port_base=9400,
            negative_intensity=0.5,
            dry_run=True,
        )

        report = run_dataset(args)

        self.assertEqual(report['status'], 'dry_run')
        self.assertEqual(report['episode_count'], 4)
        self.assertEqual(report['label_counts'], {'negative': 2, 'positive': 2})
        self.assertTrue(Path(report['plan_path']).exists())
        saved = json.loads(Path(report['report_path']).read_text(encoding='utf-8'))
        self.assertEqual(saved['status'], 'dry_run')

    def _write_file(self, relative_path: str) -> Path:
        path = self._tempdir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test\n', encoding='utf-8')
        return path

    def _write_jsonl(self, relative_path: str, rows: list[dict]) -> Path:
        path = self._tempdir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows), encoding='utf-8')
        return path

    def _transition(self, sample_id: str, *, action: str, reward: float) -> dict:
        return {
            'sample_id': sample_id,
            'scenario_id': 'lmop_full_story_demo',
            'agent_id': 'player-1-controller',
            'source': 'human',
            'runtime_mode': 'storytelling',
            'acting_actor_id': 'player-1',
            'observation': {
                'summary_lines': ['Runtime mode: storytelling', 'Campaign: lmop'],
                'prompt': None,
            },
            'available_actions': [],
            'state_before': {
                'runtime_mode': 'storytelling',
                'scene_id': 'scene-waterdeep-gundren-briefing',
                'location_id': 'waterdeep',
                'round_number': None,
                'encounter_phase': None,
                'active_actor_id': 'player-1',
            },
            'action': action,
            'reward': reward,
            'action_reward': reward,
            'terminal_reward': 0.0,
            'reward_channels': {'progress': reward},
            'error': None,
        }


if __name__ == '__main__':
    unittest.main()
