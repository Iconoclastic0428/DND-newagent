from __future__ import annotations

import argparse
from dataclasses import dataclass
from enum import Enum
import json
from pathlib import Path
import sys
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from story_demo_system_server import build_full_story_demo_manual_session


class StoryDemoReplayError(RuntimeError):
    pass


class QueueTransport:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self.payloads = list(payloads)
        self.requests: list[dict[str, Any]] = []

    def _next_payload(self) -> dict[str, Any]:
        if not self.payloads:
            raise StoryDemoReplayError('No queued LLM payloads remain for this replay script.')
        return self.payloads.pop(0)

    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return self._next_payload()

    def stream(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        self.requests.append({'url': url, 'headers': headers, 'payload': payload})
        return [{'type': 'response.completed', 'response': self._next_payload()}]


@dataclass(frozen=True)
class ReplayResult:
    script_id: str
    steps_executed: int
    llm_requests: int
    remaining_llm_payloads: int
    final_runtime_mode: str
    final_scene_id: str | None


def _default_base_url() -> str:
    return Path('D:/5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/'


def _normalize_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StoryDemoReplayError('Replay script llm_payloads entries must be objects.')
    if 'output_text' in payload:
        output = payload['output_text']
        if isinstance(output, str):
            return {'output_text': output}
        return {'output_text': json.dumps(output, ensure_ascii=False)}
    return {'output_text': json.dumps(payload, ensure_ascii=False)}


def _normalize_scalar(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    return value


def _resolve_path(root: Any, path: list[str]) -> Any:
    current = root
    for segment in path:
        if isinstance(current, dict):
            if segment not in current:
                raise StoryDemoReplayError(f'Path segment {segment!r} was not found in dict during replay assertion.')
            current = current[segment]
            continue
        if not hasattr(current, segment):
            raise StoryDemoReplayError(f'Path segment {segment!r} was not found on {type(current).__name__} during replay assertion.')
        current = getattr(current, segment)
    return current


def _assert_contains(label: str, haystack: str, needles: list[str]) -> None:
    for needle in needles:
        if needle not in haystack:
            raise StoryDemoReplayError(f'{label} is missing expected text: {needle!r}.')


def _assert_not_contains(label: str, haystack: str, needles: list[str]) -> None:
    for needle in needles:
        if needle in haystack:
            raise StoryDemoReplayError(f'{label} unexpectedly contains text: {needle!r}.')


def _assert_value(root: dict[str, Any], step: dict[str, Any]) -> None:
    if 'path' not in step or not isinstance(step['path'], list):
        raise StoryDemoReplayError('assert_value steps require a list-valued `path`.')
    value = _resolve_path(root, step['path'])
    normalized = _normalize_scalar(value)
    if 'equals' in step and normalized != step['equals']:
        raise StoryDemoReplayError(f'Value assertion failed for {step["path"]}: expected {step["equals"]!r}, got {normalized!r}.')
    if 'not_equals' in step and normalized == step['not_equals']:
        raise StoryDemoReplayError(f'Value assertion failed for {step["path"]}: value unexpectedly equaled {step["not_equals"]!r}.')
    if 'gte' in step and normalized < step['gte']:
        raise StoryDemoReplayError(f'Value assertion failed for {step["path"]}: expected >= {step["gte"]!r}, got {normalized!r}.')
    if 'lte' in step and normalized > step['lte']:
        raise StoryDemoReplayError(f'Value assertion failed for {step["path"]}: expected <= {step["lte"]!r}, got {normalized!r}.')
    if 'truthy' in step and bool(normalized) is not bool(step['truthy']):
        raise StoryDemoReplayError(f'Value assertion failed for {step["path"]}: truthiness was {bool(normalized)!r}.')
    if 'len_equals' in step and len(value) != step['len_equals']:
        raise StoryDemoReplayError(f'Length assertion failed for {step["path"]}: expected {step["len_equals"]}, got {len(value)}.')
    if 'len_gte' in step and len(value) < step['len_gte']:
        raise StoryDemoReplayError(f'Length assertion failed for {step["path"]}: expected >= {step["len_gte"]}, got {len(value)}.')
    if 'len_lte' in step and len(value) > step['len_lte']:
        raise StoryDemoReplayError(f'Length assertion failed for {step["path"]}: expected <= {step["len_lte"]}, got {len(value)}.')
    if 'contains' in step:
        container = normalized
        needle = step['contains']
        if isinstance(container, str):
            if needle not in container:
                raise StoryDemoReplayError(f'Containment assertion failed for {step["path"]}: missing {needle!r}.')
        elif needle not in container:
            raise StoryDemoReplayError(f'Containment assertion failed for {step["path"]}: missing {needle!r}.')
    if 'not_contains' in step:
        container = normalized
        needle = step['not_contains']
        if isinstance(container, str):
            if needle in container:
                raise StoryDemoReplayError(f'Containment assertion failed for {step["path"]}: unexpectedly found {needle!r}.')
        elif needle in container:
            raise StoryDemoReplayError(f'Containment assertion failed for {step["path"]}: unexpectedly found {needle!r}.')


def _assert_view(session, controller_id: str, *, contains: list[str] | None = None, not_contains: list[str] | None = None) -> None:
    view = session.view_for_controller(controller_id)
    text = '\n'.join(view.summary_lines)
    if contains:
        _assert_contains(f'View for {controller_id}', text, contains)
    if not_contains:
        _assert_not_contains(f'View for {controller_id}', text, not_contains)


def _assert_prompt(session, controller_id: str, step: dict[str, Any]) -> None:
    prompt = session.prompt_for_controller(controller_id)
    require_present = step.get('present', True)
    if not require_present:
        if prompt is not None:
            raise StoryDemoReplayError(f'Expected no prompt for {controller_id}, but one was present.')
        return
    if prompt is None:
        raise StoryDemoReplayError(f'Expected a prompt for {controller_id}, but none was present.')
    if 'prompt_kind' in step and prompt.prompt_kind != step['prompt_kind']:
        raise StoryDemoReplayError(f'Prompt kind mismatch for {controller_id}: expected {step["prompt_kind"]!r}, got {prompt.prompt_kind!r}.')
    if 'contains' in step:
        _assert_contains(f'Prompt for {controller_id}', prompt.prompt, step['contains'])
    if 'not_contains' in step:
        _assert_not_contains(f'Prompt for {controller_id}', prompt.prompt, step['not_contains'])


def load_story_demo_script(path: str | Path) -> dict[str, Any]:
    script_path = Path(path)
    return json.loads(script_path.read_text(encoding='utf-8'))


def run_story_demo_script(
    path: str | Path,
    *,
    env_path: str | Path = '.env',
    base_url: str | None = None,
    campaign_root: str | Path | None = None,
    verbose: bool = False,
) -> ReplayResult:
    script_path = Path(path)
    script = load_story_demo_script(script_path)
    llm_payloads = [_normalize_payload(payload) for payload in script.get('llm_payloads', [])]
    transport = QueueTransport(llm_payloads)
    session = build_full_story_demo_manual_session(
        base_url=(base_url or _default_base_url()),
        campaign_root=campaign_root,
        env_path=env_path,
        client_transport=transport,
    )
    root = {'session': session, 'transport': transport}
    steps = script.get('steps', [])
    executed = 0
    for index, step in enumerate(steps, start=1):
        step_type = step.get('type')
        if verbose:
            print(f'[{index:03d}] {step_type}: {step.get("label") or step.get("input") or step.get("controller_id") or ""}')
        if step_type == 'comment':
            executed += 1
            continue
        if step_type == 'command':
            controller_id = step['controller_id']
            view = session.handle_input(controller_id, step['input'])
            text = '\n'.join(view.summary_lines)
            if 'view_contains' in step:
                _assert_contains(f'View after command {step["input"]!r}', text, step['view_contains'])
            if 'view_not_contains' in step:
                _assert_not_contains(f'View after command {step["input"]!r}', text, step['view_not_contains'])
            executed += 1
            continue
        if step_type == 'assert_view':
            _assert_view(session, step['controller_id'], contains=step.get('contains'), not_contains=step.get('not_contains'))
            executed += 1
            continue
        if step_type == 'assert_prompt':
            _assert_prompt(session, step['controller_id'], step)
            executed += 1
            continue
        if step_type == 'assert_value':
            _assert_value(root, step)
            executed += 1
            continue
        raise StoryDemoReplayError(f'Unknown replay step type: {step_type!r}.')
    if script.get('consume_all_llm_payloads', True) and transport.payloads:
        raise StoryDemoReplayError(f'Replay finished with {len(transport.payloads)} unused queued LLM payload(s).')
    story_session = session.story_session
    final_runtime_mode = 'character-creation' if story_session is None else story_session.story_state.runtime_mode.value
    final_scene_id = None if story_session is None else story_session.story_state.current_scene_id
    return ReplayResult(
        script_id=str(script.get('script_id', script_path.stem)),
        steps_executed=executed,
        llm_requests=len(transport.requests),
        remaining_llm_payloads=len(transport.payloads),
        final_runtime_mode=final_runtime_mode,
        final_scene_id=final_scene_id,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Run an authored LMOP full-story demo replay script.')
    parser.add_argument('--script', required=True, help='Path to the replay script JSON file.')
    parser.add_argument('--env-path', default='.env', help='Env file path used to configure the DM runtime shell.')
    parser.add_argument('--base-url', default=None, help='Optional explicit 5etools mirror base URL.')
    parser.add_argument('--campaign-root', default=None, help='Optional campaign root override.')
    parser.add_argument('--verbose', action='store_true', help='Print each step as it executes.')
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    result = run_story_demo_script(
        args.script,
        env_path=args.env_path,
        base_url=args.base_url,
        campaign_root=args.campaign_root,
        verbose=args.verbose,
    )
    print(f'Script {result.script_id} passed: {result.steps_executed} steps, {result.llm_requests} queued LLM requests, final mode {result.final_runtime_mode}, final scene {result.final_scene_id}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
