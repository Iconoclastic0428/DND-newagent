from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from string import Formatter
import time
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request


class LiveWebStoryDemoError(RuntimeError):
    pass


@dataclass(frozen=True)
class LiveWebStoryDemoResult:
    script_id: str
    steps_executed: int
    commands_sent: int
    skipped_steps: int
    final_runtime_mode: str | None
    final_scene_id: str | None


class AutomationHttpClient:
    def __init__(self, base_url: str, *, request_timeout_seconds: float | None = 300.0) -> None:
        normalized = base_url.rstrip('/')
        if not normalized:
            raise LiveWebStoryDemoError('`base_url` must not be empty.')
        self.base_url = normalized
        self.request_timeout_seconds = request_timeout_seconds

    def state(self, controller_id: str) -> dict[str, Any]:
        query = urllib_parse.urlencode({'controller_id': controller_id})
        return self._request_json('GET', f'/automation/state?{query}')

    def submit(self, controller_id: str, text: str) -> dict[str, Any]:
        return self._request_json(
            'POST',
            '/automation/input',
            {'controller_id': controller_id, 'text': text},
        )

    def respond_to_prompt(
        self,
        controller_id: str,
        *,
        option_id: str | None = None,
        option_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if option_id is not None and option_ids is not None:
            raise LiveWebStoryDemoError('Use either `option_id` or `option_ids`, not both.')
        payload: dict[str, Any] = {'controller_id': controller_id}
        if option_ids is not None:
            payload['option_ids'] = option_ids
        else:
            payload['option_id'] = option_id
        return self._request_json('POST', '/automation/prompt-response', payload)

    def _request_json(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        data = None
        headers = {}
        if payload is not None:
            data = json.dumps(payload).encode('utf-8')
            headers['Content-Type'] = 'application/json; charset=utf-8'
        request = urllib_request.Request(
            url=f'{self.base_url}{path}',
            data=data,
            headers=headers,
            method=method,
        )
        try:
            if self.request_timeout_seconds is None:
                response_context = urllib_request.urlopen(request)
            else:
                response_context = urllib_request.urlopen(request, timeout=self.request_timeout_seconds)
            with response_context as response:
                raw = response.read().decode('utf-8')
        except urllib_error.HTTPError as exc:
            body = exc.read().decode('utf-8', errors='replace')
            message = _extract_error_message(body) or body or str(exc)
            raise LiveWebStoryDemoError(f'{method} {path} failed: {message}') from exc
        except urllib_error.URLError as exc:
            raise LiveWebStoryDemoError(f'{method} {path} failed: {exc.reason}') from exc
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise LiveWebStoryDemoError(f'{method} {path} returned invalid JSON: {exc}') from exc
        if not isinstance(decoded, dict):
            raise LiveWebStoryDemoError(f'{method} {path} returned a non-object JSON payload.')
        if decoded.get('ok') is False:
            raise LiveWebStoryDemoError(str(decoded.get('error') or f'{method} {path} failed.'))
        return decoded


def load_live_web_story_script(path: str | Path) -> dict[str, Any]:
    script_path = Path(path)
    return json.loads(script_path.read_text(encoding='utf-8'))


def run_live_web_story_script(
    path: str | Path,
    *,
    base_url: str,
    request_timeout_seconds: float | None = 300.0,
    verbose: bool = False,
) -> LiveWebStoryDemoResult:
    script_path = Path(path)
    script = load_live_web_story_script(script_path)
    client = AutomationHttpClient(base_url, request_timeout_seconds=request_timeout_seconds)
    steps = script.get('steps', [])
    if not isinstance(steps, list):
        raise LiveWebStoryDemoError('Live web story script `steps` must be a list.')
    executed = 0
    commands_sent = 0
    skipped_steps = 0
    snapshots: dict[str, dict[str, Any]] = {}

    for index, step in enumerate(steps, start=1):
        if not isinstance(step, dict):
            raise LiveWebStoryDemoError(f'Step {index} must be a JSON object.')
        step_type = step.get('type')
        if verbose:
            print(f'[{index:03d}] {step_type}: {step.get("label") or step.get("input") or step.get("controller_id") or ""}')
        if step_type == 'comment':
            executed += 1
            continue
        if step_type == 'sleep':
            duration_seconds = _require_float(step.get('seconds'), 'seconds')
            if duration_seconds < 0:
                raise LiveWebStoryDemoError('sleep steps require non-negative `seconds`.')
            time.sleep(duration_seconds)
            executed += 1
            continue
        if step_type == 'command':
            controller_id = _require_non_empty_string(step.get('controller_id'), 'controller_id')
            raw_text = _require_string(step.get('input'), 'input')
            snapshot = _snapshot_for_command_resolution(client, controller_id, raw_text)
            text = _resolve_command_text(raw_text, snapshot)
            snapshots[controller_id] = client.submit(controller_id, text)
            commands_sent += 1
            _apply_post_delay(step)
            executed += 1
            continue
        if step_type == 'command_if_view':
            controller_id = _require_non_empty_string(step.get('controller_id'), 'controller_id')
            raw_text = _require_string(step.get('input'), 'input')
            snapshot = client.state(controller_id)
            snapshots[controller_id] = snapshot
            if _view_matches(snapshot, step):
                text = _resolve_command_text(raw_text, snapshot)
                snapshots[controller_id] = client.submit(controller_id, text)
                commands_sent += 1
                _apply_post_delay(step)
            else:
                skipped_steps += 1
            executed += 1
            continue
        if step_type == 'command_if_prompt':
            controller_id = _require_non_empty_string(step.get('controller_id'), 'controller_id')
            raw_text = _require_string(step.get('input'), 'input')
            snapshot = client.state(controller_id)
            snapshots[controller_id] = snapshot
            if _prompt_matches(snapshot, step):
                text = _resolve_command_text(raw_text, snapshot)
                snapshots[controller_id] = client.submit(controller_id, text)
                commands_sent += 1
                _apply_post_delay(step)
            else:
                skipped_steps += 1
            executed += 1
            continue
        if step_type == 'wait_for_prompt':
            controller_id = _require_non_empty_string(step.get('controller_id'), 'controller_id')
            timeout_seconds = _timeout_seconds(step, default=30.0)
            poll_interval_seconds = _poll_interval_seconds(step)
            snapshots[controller_id] = _wait_for_snapshot(
                fetch_snapshot=lambda: client.state(controller_id),
                matches=lambda snapshot: _prompt_matches(snapshot, step),
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                label=f'prompt for {controller_id}',
            )
            executed += 1
            continue
        if step_type == 'wait_for_view':
            controller_id = _require_non_empty_string(step.get('controller_id'), 'controller_id')
            timeout_seconds = _timeout_seconds(step, default=30.0)
            poll_interval_seconds = _poll_interval_seconds(step)
            snapshots[controller_id] = _wait_for_snapshot(
                fetch_snapshot=lambda: client.state(controller_id),
                matches=lambda snapshot: _view_matches(snapshot, step),
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                label=f'view for {controller_id}',
            )
            executed += 1
            continue
        raise LiveWebStoryDemoError(f'Unknown live web story step type: {step_type!r}.')

    result_controller_id = script.get('result_controller_id')
    if result_controller_id is None:
        if snapshots:
            result_controller_id = next(reversed(snapshots))
        else:
            result_controller_id = 'player-1-controller'
    if not isinstance(result_controller_id, str) or not result_controller_id:
        raise LiveWebStoryDemoError('`result_controller_id` must be a non-empty string when present.')
    final_snapshot = snapshots.get(result_controller_id) or client.state(result_controller_id)
    final_view = _view_from_snapshot(final_snapshot)
    return LiveWebStoryDemoResult(
        script_id=str(script.get('script_id', script_path.stem)),
        steps_executed=executed,
        commands_sent=commands_sent,
        skipped_steps=skipped_steps,
        final_runtime_mode=_string_or_none(final_view.get('runtime_mode')),
        final_scene_id=_string_or_none(final_view.get('current_scene_id')),
    )


def _wait_for_snapshot(
    *,
    fetch_snapshot,
    matches,
    timeout_seconds: float,
    poll_interval_seconds: float,
    label: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_seconds
    last_snapshot: dict[str, Any] | None = None
    while True:
        snapshot = fetch_snapshot()
        last_snapshot = snapshot
        if matches(snapshot):
            return snapshot
        if time.monotonic() >= deadline:
            raise LiveWebStoryDemoError(f'Timed out waiting for {label}.')
        time.sleep(poll_interval_seconds)


def _view_matches(snapshot: dict[str, Any], step: dict[str, Any]) -> bool:
    view = _view_from_snapshot(snapshot)
    expected_runtime_mode = step.get('runtime_mode')
    if expected_runtime_mode is not None and view.get('runtime_mode') != expected_runtime_mode:
        return False
    expected_scene_id = step.get('current_scene_id')
    if expected_scene_id is not None and view.get('current_scene_id') != expected_scene_id:
        return False
    expected_active_actor_id = step.get('active_actor_id')
    if expected_active_actor_id is not None and view.get('active_actor_id') != expected_active_actor_id:
        return False
    expected_active_actor_side = step.get('active_actor_side')
    if expected_active_actor_side is not None and _active_actor_side(view) != expected_active_actor_side:
        return False
    summary_text = '\n'.join(view.get('summary_lines', []))
    for needle in step.get('contains', []):
        if needle not in summary_text:
            return False
    for needle in step.get('not_contains', []):
        if needle in summary_text:
            return False
    return True


def _prompt_matches(snapshot: dict[str, Any], step: dict[str, Any]) -> bool:
    prompt = snapshot.get('prompt')
    if prompt is None:
        return False
    prompt_kind = step.get('prompt_kind')
    if prompt_kind is not None and prompt.get('prompt_kind') != prompt_kind:
        return False
    prompt_text = prompt.get('text')
    if not isinstance(prompt_text, str):
        raise LiveWebStoryDemoError('Automation snapshot prompt is missing string `text`.')
    for needle in step.get('contains', []):
        if needle not in prompt_text:
            return False
    for needle in step.get('not_contains', []):
        if needle in prompt_text:
            return False
    return True


def _view_from_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    view = snapshot.get('view')
    if not isinstance(view, dict):
        raise LiveWebStoryDemoError('Automation snapshot is missing object `view`.')
    return view


def _snapshot_for_command_resolution(client: AutomationHttpClient, controller_id: str, raw_text: str) -> dict[str, Any] | None:
    if '{' not in raw_text or '}' not in raw_text:
        return None
    return client.state(controller_id)


def _resolve_command_text(raw_text: str, snapshot: dict[str, Any] | None) -> str:
    if snapshot is None:
        return raw_text
    view = _view_from_snapshot(snapshot)
    placeholder_names = {field_name for _, field_name, _, _ in Formatter().parse(raw_text) if field_name}
    if not placeholder_names:
        return raw_text
    values: dict[str, Any] = {}
    if 'active_actor_id' in placeholder_names:
        values['active_actor_id'] = _required_view_string(view, 'active_actor_id')
    if 'current_scene_id' in placeholder_names:
        values['current_scene_id'] = _required_view_string(view, 'current_scene_id', allow_none=True)
    if 'first_enemy_actor_id' in placeholder_names:
        values['first_enemy_actor_id'] = _first_enemy_actor_id(view)
    try:
        return raw_text.format(**values)
    except KeyError as exc:
        raise LiveWebStoryDemoError(f'Unknown command template placeholder: {exc.args[0]}') from exc


def _required_view_string(view: dict[str, Any], field_name: str, *, allow_none: bool = False) -> str | None:
    value = view.get(field_name)
    if value is None and allow_none:
        return None
    if not isinstance(value, str) or not value:
        raise LiveWebStoryDemoError(f'View field `{field_name}` is missing a non-empty string value.')
    return value


def _first_enemy_actor_id(view: dict[str, Any]) -> str:
    active_side = _active_actor_side(view)
    if active_side is None:
        raise LiveWebStoryDemoError('Cannot resolve `{first_enemy_actor_id}` without an active actor side.')
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        raise LiveWebStoryDemoError('Cannot resolve `{first_enemy_actor_id}` without an active combat map.')
    tokens = map_view.get('tokens')
    if not isinstance(tokens, list):
        raise LiveWebStoryDemoError('Combat map tokens are missing from the view.')
    for token in tokens:
        if not isinstance(token, dict):
            continue
        actor_id = token.get('actor_id')
        side = token.get('side')
        status = token.get('status')
        if not isinstance(actor_id, str) or not actor_id:
            continue
        if not isinstance(side, str) or side == active_side:
            continue
        if isinstance(status, str) and status.lower() in {'dead', 'defeated', 'removed'}:
            continue
        return actor_id
    raise LiveWebStoryDemoError('No living enemy actor is currently available in the projected view.')


def _active_actor_side(view: dict[str, Any]) -> str | None:
    active_actor_id = view.get('active_actor_id')
    if not isinstance(active_actor_id, str) or not active_actor_id:
        return None
    map_view = view.get('map')
    if not isinstance(map_view, dict):
        return None
    tokens = map_view.get('tokens')
    if not isinstance(tokens, list):
        return None
    for token in tokens:
        if not isinstance(token, dict):
            continue
        if token.get('actor_id') != active_actor_id:
            continue
        side = token.get('side')
        if isinstance(side, str) and side:
            return side
        return None
    return None


def _apply_post_delay(step: dict[str, Any]) -> None:
    delay_seconds = step.get('post_delay_seconds')
    if delay_seconds is None:
        return
    delay = _require_float(delay_seconds, 'post_delay_seconds')
    if delay < 0:
        raise LiveWebStoryDemoError('`post_delay_seconds` must be >= 0.')
    time.sleep(delay)


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise LiveWebStoryDemoError(f'`{field_name}` must be a non-empty string.')
    return value


def _require_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise LiveWebStoryDemoError(f'`{field_name}` must be a string.')
    return value


def _require_float(value: Any, field_name: str) -> float:
    if not isinstance(value, (int, float)):
        raise LiveWebStoryDemoError(f'`{field_name}` must be numeric.')
    return float(value)


def _timeout_seconds(step: dict[str, Any], *, default: float) -> float:
    timeout_seconds = _require_float(step.get('timeout_seconds', default), 'timeout_seconds')
    if timeout_seconds <= 0:
        raise LiveWebStoryDemoError('`timeout_seconds` must be greater than 0.')
    return timeout_seconds


def _poll_interval_seconds(step: dict[str, Any]) -> float:
    poll_interval_seconds = _require_float(step.get('poll_interval_seconds', 0.25), 'poll_interval_seconds')
    if poll_interval_seconds <= 0:
        raise LiveWebStoryDemoError('`poll_interval_seconds` must be greater than 0.')
    return poll_interval_seconds


def _string_or_none(value: Any) -> str | None:
    return value if isinstance(value, str) else None


def _extract_error_message(raw_body: str) -> str | None:
    try:
        decoded = json.loads(raw_body)
    except json.JSONDecodeError:
        return None
    if isinstance(decoded, dict) and isinstance(decoded.get('error'), str):
        return decoded['error']
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Drive a running browser LMOP full-story demo through the local automation API.')
    parser.add_argument('--script', required=True, help='Path to the live web story script JSON file.')
    parser.add_argument('--base-url', default='http://127.0.0.1:8000', help='Base URL of the running web story demo server.')
    parser.add_argument(
        '--request-timeout-seconds',
        type=float,
        default=300.0,
        help='HTTP request timeout for injected controller input. Use 0 to disable the timeout.',
    )
    parser.add_argument('--verbose', action='store_true', help='Print each step as it executes.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.request_timeout_seconds < 0:
        raise SystemExit('ERROR: --request-timeout-seconds must be >= 0.')
    result = run_live_web_story_script(
        args.script,
        base_url=args.base_url,
        request_timeout_seconds=(None if args.request_timeout_seconds == 0 else args.request_timeout_seconds),
        verbose=args.verbose,
    )
    print(
        f'Script {result.script_id} passed: {result.steps_executed} steps, '
        f'{result.commands_sent} commands, {result.skipped_steps} skipped conditional steps, '
        f'final mode {result.final_runtime_mode}, final scene {result.final_scene_id}.'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
