from __future__ import annotations

import json
from pathlib import Path
import shutil
import socket
import sys
import unittest
from types import SimpleNamespace
from uuid import uuid4

REPO_ROOT = Path(__file__).resolve().parents[1]
USER_TEST_ROOT = REPO_ROOT / 'user-test'
if str(USER_TEST_ROOT) not in sys.path:
    sys.path.insert(0, str(USER_TEST_ROOT))

from run_deepseek_100_conversation_dataset import (
    DeepSeekDatasetRunnerError,
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

    def test_server_command_uses_short_trajectory_episode_id(self) -> None:
        paths = _episode_paths(self._tempdir / 'episode')
        args = SimpleNamespace(
            host='127.0.0.1',
            campaign_root=None,
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

        self.assertIn('--trajectory-episode-id', command)
        self.assertEqual(command[command.index('--trajectory-episode-id') + 1], 'web')

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

    def test_port_preflight_rejects_occupied_websocket_port(self) -> None:
        from run_deepseek_100_conversation_dataset import _assert_episode_ports_available

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as occupied_socket:
            occupied_socket.bind(('127.0.0.1', 0))
            occupied_socket.listen(1)
            occupied_port = occupied_socket.getsockname()[1]
            free_http_port = self._free_tcp_port(excluding={occupied_port})
            spec = build_episode_plan(
                episodes=1,
                positive_count=1,
                pilot_size=1,
                http_port_base=free_http_port,
                ws_port_base=occupied_port,
                negative_intensity=0.5,
            )[0]

            with self.assertRaisesRegex(RuntimeError, f'ws port {occupied_port} is already in use'):
                _assert_episode_ports_available((spec,), host='127.0.0.1')

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

    def test_run_dataset_stops_after_failed_pilot_before_main_expansion(self) -> None:
        env_path = self._write_file('dm.env')
        executed_indexes: list[int] = []

        def fake_episode_runner(spec, **_kwargs):
            executed_indexes.append(spec.index)
            transcript = self._write_file(f'{spec.episode_id}/transcript.md')
            trajectory = self._write_file(f'{spec.episode_id}/trajectory.jsonl')
            raw_io = self._write_file(f'{spec.episode_id}/raw-io.jsonl')
            result = {
                'episode_id': spec.episode_id,
                'index': spec.index,
                'label': spec.label,
                'phase': spec.phase,
                'artifact_paths': {
                    'transcript': str(transcript),
                    'trajectory': str(trajectory),
                    'raw_interactions': str(raw_io),
                },
            }
            if spec.index == 1:
                result.update(
                    {
                        'status': 'completed',
                        'terminal_reason': 'demo-complete',
                        'total_reward': 1.0,
                        'reward_channels': {'progress': 1.0},
                    }
                )
            else:
                result.update(
                    {
                        'status': 'failed',
                        'terminal_reason': 'episode-error',
                        'error': 'LLM request failed with HTTP 402. Response body: Insufficient Balance',
                    }
                )
            return result

        args = SimpleNamespace(
            output_root=self._tempdir / 'runs',
            run_id='pilot-stop',
            episodes=4,
            positive_count=2,
            pilot_size=2,
            workers=2,
            http_port_base=38000,
            ws_port_base=39000,
            env_path=env_path,
            player_env_path=None,
            character_load_path=None,
            base_url='file:///mirror/',
            mirror_root=self._tempdir / 'missing-mirror',
            campaign_root=None,
            host='127.0.0.1',
            max_actions=90,
            poll_interval_seconds=0.5,
            monster_turn_delay_seconds=0.1,
            request_timeout_seconds=0.0,
            llm_timeout_seconds=180.0,
            server_start_timeout_seconds=120.0,
            pre_connector_delay_seconds=0.5,
            connector_timeout_seconds=43200.0,
            negative_intensity=0.5,
            min_transitions=1,
            dry_run=False,
        )

        report = run_dataset(args, episode_runner=fake_episode_runner, provider_probe=lambda _env_path: {'status': 'ok'})

        self.assertEqual(set(executed_indexes), {1, 2})
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['episode_count'], 2)
        quality = json.loads(Path(report['quality_report_path']).read_text(encoding='utf-8'))
        self.assertTrue(any(issue['code'] == 'pilot_failed_before_expansion' for issue in quality['issues']))

    def test_run_dataset_preflights_provider_before_episode_execution(self) -> None:
        env_path = self._write_file('dm.env')
        executed_indexes: list[int] = []

        def fake_episode_runner(spec, **_kwargs):
            executed_indexes.append(spec.index)
            raise AssertionError('episode runner should not start when provider preflight fails')

        def failing_provider_probe(_env_path):
            raise RuntimeError('LLM request failed with HTTP 402. Response body: Insufficient Balance')

        args = SimpleNamespace(
            output_root=self._tempdir / 'runs',
            run_id='provider-preflight-fail',
            episodes=4,
            positive_count=2,
            pilot_size=2,
            workers=2,
            http_port_base=38000,
            ws_port_base=39000,
            env_path=env_path,
            player_env_path=None,
            character_load_path=None,
            base_url='file:///mirror/',
            mirror_root=self._tempdir / 'missing-mirror',
            campaign_root=None,
            host='127.0.0.1',
            max_actions=90,
            poll_interval_seconds=0.5,
            monster_turn_delay_seconds=0.1,
            request_timeout_seconds=0.0,
            llm_timeout_seconds=180.0,
            server_start_timeout_seconds=120.0,
            pre_connector_delay_seconds=0.5,
            connector_timeout_seconds=43200.0,
            negative_intensity=0.5,
            min_transitions=1,
            dry_run=False,
        )

        report = run_dataset(args, episode_runner=fake_episode_runner, provider_probe=failing_provider_probe)

        self.assertEqual(executed_indexes, [])
        self.assertEqual(report['status'], 'failed')
        self.assertEqual(report['episode_count'], 0)
        self.assertFalse((self._tempdir / 'runs' / 'provider-preflight-fail' / 'episodes').exists())
        preflight = json.loads(Path(report['provider_preflight_path']).read_text(encoding='utf-8'))
        self.assertEqual(preflight['status'], 'fail')
        self.assertIn('Insufficient Balance', preflight['error'])
        quality = json.loads(Path(report['quality_report_path']).read_text(encoding='utf-8'))
        self.assertTrue(any(issue['code'] == 'llm_provider_preflight_failed' for issue in quality['issues']))

    def test_run_dataset_reduces_remaining_plan_from_accepted_pool(self) -> None:
        env_path = self._write_file('dm.env')
        accepted_pool_path = self._tempdir / 'accepted-conversations.jsonl'
        prior_rows = [
            self._good_conversation_result('accepted-positive', label='positive', index=1),
            self._good_conversation_result('accepted-negative', label='negative', index=2),
        ]
        accepted_pool_path.write_text(
            ''.join(json.dumps(row, sort_keys=True) + '\n' for row in prior_rows),
            encoding='utf-8',
        )
        executed_labels: list[str] = []

        def fake_episode_runner(spec, **_kwargs):
            executed_labels.append(spec.label)
            return self._good_conversation_result(spec.episode_id, label=spec.label, index=spec.index)

        args = self._dataset_args(
            env_path=env_path,
            accepted_pool_path=accepted_pool_path,
            run_id='accepted-pool-reduced-plan',
            episodes=4,
            positive_count=2,
            pilot_size=2,
        )

        report = run_dataset(args, episode_runner=fake_episode_runner, provider_probe=lambda _env_path: {'status': 'ok'})

        self.assertEqual(executed_labels, ['positive', 'negative'])
        self.assertEqual(report['accepted_pool']['target_episode_count'], 4)
        self.assertEqual(report['accepted_pool']['accepted_for_target_count'], 4)
        self.assertEqual(report['accepted_pool']['remaining_episode_count'], 0)
        accepted_rows = [json.loads(line) for line in accepted_pool_path.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual(len(accepted_rows), 4)

    def test_run_dataset_persists_good_pilot_before_failed_pilot_halt(self) -> None:
        env_path = self._write_file('dm.env')
        accepted_pool_path = self._tempdir / 'accepted-conversations.jsonl'

        def fake_episode_runner(spec, **_kwargs):
            if spec.index == 1:
                return self._good_conversation_result(spec.episode_id, label=spec.label, index=spec.index)
            return {
                'episode_id': spec.episode_id,
                'index': spec.index,
                'label': spec.label,
                'phase': spec.phase,
                'status': 'failed',
                'terminal_reason': 'episode-error',
                'error': 'provider failed after one good pilot',
                'artifact_paths': {},
            }

        args = self._dataset_args(
            env_path=env_path,
            accepted_pool_path=accepted_pool_path,
            run_id='accepted-pool-pilot-halt',
            episodes=4,
            positive_count=2,
            pilot_size=2,
        )

        report = run_dataset(args, episode_runner=fake_episode_runner, provider_probe=lambda _env_path: {'status': 'ok'})

        self.assertEqual(report['status'], 'failed')
        self.assertTrue(accepted_pool_path.exists())
        accepted_rows = [json.loads(line) for line in accepted_pool_path.read_text(encoding='utf-8').splitlines() if line.strip()]
        self.assertEqual([row['episode_id'] for row in accepted_rows], ['conversation-001-positive'])
        self.assertEqual(report['accepted_pool']['accepted_new_count'], 1)

    def test_run_dataset_does_not_accept_completed_conversation_with_invalid_actions(self) -> None:
        env_path = self._write_file('dm.env')
        accepted_pool_path = self._tempdir / 'accepted-conversations.jsonl'

        def fake_episode_runner(spec, **_kwargs):
            return self._good_conversation_result(
                spec.episode_id,
                label=spec.label,
                index=spec.index,
                invalid_action_count=1,
            )

        args = self._dataset_args(
            env_path=env_path,
            accepted_pool_path=accepted_pool_path,
            run_id='accepted-pool-invalid-actions',
            episodes=1,
            positive_count=1,
            pilot_size=1,
        )

        report = run_dataset(args, episode_runner=fake_episode_runner, provider_probe=lambda _env_path: {'status': 'ok'})

        self.assertFalse(accepted_pool_path.exists())
        self.assertEqual(report['accepted_pool']['accepted_new_count'], 0)
        self.assertEqual(report['accepted_pool']['remaining_episode_count'], 1)

    def test_accepted_pool_rejects_tampered_acceptance_key(self) -> None:
        env_path = self._write_file('dm.env')
        accepted_pool_path = self._tempdir / 'accepted-conversations.jsonl'
        row = {
            **self._good_conversation_result('accepted-positive', label='positive', index=1),
            'acceptance_key': 'tampered:key',
        }
        accepted_pool_path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')
        args = self._dataset_args(
            env_path=env_path,
            accepted_pool_path=accepted_pool_path,
            run_id='accepted-pool-tampered-key',
            episodes=1,
            positive_count=1,
            pilot_size=1,
        )

        with self.assertRaisesRegex(DeepSeekDatasetRunnerError, 'acceptance key'):
            run_dataset(args, episode_runner=None, provider_probe=lambda _env_path: {'status': 'ok'})

    def test_accepted_pool_rejects_transition_count_mismatching_artifact(self) -> None:
        env_path = self._write_file('dm.env')
        accepted_pool_path = self._tempdir / 'accepted-conversations.jsonl'
        row = {
            **self._good_conversation_result('accepted-positive', label='positive', index=1),
            'transition_count': 2,
        }
        accepted_pool_path.write_text(json.dumps(row, sort_keys=True) + '\n', encoding='utf-8')
        args = self._dataset_args(
            env_path=env_path,
            accepted_pool_path=accepted_pool_path,
            run_id='accepted-pool-transition-mismatch',
            episodes=1,
            positive_count=1,
            pilot_size=1,
        )

        with self.assertRaisesRegex(DeepSeekDatasetRunnerError, 'transition count'):
            run_dataset(args, episode_runner=None, provider_probe=lambda _env_path: {'status': 'ok'})

    def _write_file(self, relative_path: str) -> Path:
        path = self._tempdir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('test\n', encoding='utf-8')
        return path

    def _dataset_args(
        self,
        *,
        env_path: Path,
        accepted_pool_path: Path,
        run_id: str,
        episodes: int,
        positive_count: int,
        pilot_size: int,
    ) -> SimpleNamespace:
        return SimpleNamespace(
            output_root=self._tempdir / 'runs',
            run_id=run_id,
            episodes=episodes,
            positive_count=positive_count,
            pilot_size=pilot_size,
            workers=2,
            http_port_base=38000,
            ws_port_base=39000,
            env_path=env_path,
            player_env_path=None,
            character_load_path=None,
            base_url='file:///mirror/',
            mirror_root=self._tempdir / 'missing-mirror',
            campaign_root=None,
            host='127.0.0.1',
            max_actions=90,
            poll_interval_seconds=0.5,
            monster_turn_delay_seconds=0.1,
            request_timeout_seconds=0.0,
            llm_timeout_seconds=180.0,
            server_start_timeout_seconds=120.0,
            pre_connector_delay_seconds=0.5,
            connector_timeout_seconds=43200.0,
            negative_intensity=0.5,
            min_transitions=1,
            dry_run=False,
            accepted_pool_path=accepted_pool_path,
        )

    def _good_conversation_result(
        self,
        episode_id: str,
        *,
        label: str,
        index: int,
        invalid_action_count: int = 0,
    ) -> dict:
        transcript = self._write_file(f'{episode_id}/transcript.md')
        raw_io = self._write_jsonl(f'{episode_id}/raw-io.jsonl', [{'request_payload': {}, 'response_payload': {'ok': True}}])
        trajectory = self._write_jsonl(
            f'{episode_id}/trajectory.jsonl',
            [
                {
                    'record_type': 'turn',
                    'scenario_id': 'lmop_full_story_demo',
                    'episode_id': episode_id,
                    'reward': 1.0 if label == 'positive' else -0.25,
                }
            ],
        )
        transitions = self._write_jsonl(
            f'{episode_id}/training-transitions.jsonl',
            [self._transition(f'{episode_id}:0', action='advance the scene', reward=(1.0 if label == 'positive' else -0.25))],
        )
        preferences = self._write_jsonl(f'{episode_id}/preference-pairs.jsonl', [])
        result_path = self._write_file(f'{episode_id}/episode_result.json')
        return {
            'episode_id': episode_id,
            'index': index,
            'label': label,
            'phase': 'pilot',
            'status': 'completed',
            'terminal_reason': 'demo-complete',
            'total_reward': 1.0 if label == 'positive' else -0.25,
            'reward_channels': {'progress': 1.0 if label == 'positive' else -0.25},
            'trajectory_summary': {
                'success': True,
                'final_runtime_mode': 'demo-complete',
                'invalid_action_count': invalid_action_count,
            },
            'invalid_action_count': invalid_action_count,
            'transition_count': 1,
            'preference_pair_count': 0,
            'artifact_paths': {
                'transcript': str(transcript),
                'trajectory': str(trajectory),
                'raw_interactions': str(raw_io),
                'transitions': str(transitions),
                'preferences': str(preferences),
            },
            'result_path': str(result_path),
        }

    def _free_tcp_port(self, *, excluding: set[int] | None = None) -> int:
        excluding = excluding or set()
        while True:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as free_socket:
                free_socket.bind(('127.0.0.1', 0))
                port = free_socket.getsockname()[1]
            if port not in excluding:
                return port

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
