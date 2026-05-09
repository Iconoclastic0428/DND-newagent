from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
import threading
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class TrajectoryRecord:
    episode_id: str
    scenario_id: str
    turn_index: int
    record_type: str
    agent_id: str | None
    role: str | None
    runtime_mode: str | None
    timestamp: str
    source: str
    raw_text: str | None = None
    parsed_action: dict[str, Any] | None = None
    observation: dict[str, Any] | None = None
    post_observation: dict[str, Any] | None = None
    state_before: dict[str, Any] | None = None
    state_after: dict[str, Any] | None = None
    reward_components: dict[str, float] | None = None
    error: str | None = None
    metadata: dict[str, Any] | None = None


class TrajectoryRecorder:
    def __init__(
        self,
        *,
        output_dir: str | Path,
        scenario_id: str,
        episode_id: str | None = None,
        file_name: str = 'trajectory.jsonl',
    ) -> None:
        self.output_dir = Path(output_dir)
        self.scenario_id = scenario_id
        self.episode_id = episode_id or f'{scenario_id}-{datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")}-{uuid4().hex[:8]}'
        self.episode_dir = self.output_dir / self.episode_id
        self.path = self.episode_dir / file_name
        self._lock = threading.Lock()
        self._turn_index = 0
        self.episode_dir.mkdir(parents=True, exist_ok=True)

    def record_turn(
        self,
        *,
        agent_id: str | None,
        role: str | None,
        runtime_mode: str | None,
        source: str,
        raw_text: str | None,
        parsed_action: dict[str, Any] | None = None,
        observation: dict[str, Any] | None = None,
        post_observation: dict[str, Any] | None = None,
        state_before: dict[str, Any] | None = None,
        state_after: dict[str, Any] | None = None,
        reward_components: dict[str, float] | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrajectoryRecord:
        return self._write_record(
            record_type='turn',
            agent_id=agent_id,
            role=role,
            runtime_mode=runtime_mode,
            source=source,
            raw_text=raw_text,
            parsed_action=parsed_action,
            observation=observation,
            post_observation=post_observation,
            state_before=state_before,
            state_after=state_after,
            reward_components=reward_components,
            error=error,
            metadata=metadata,
        )

    def record_event(
        self,
        *,
        record_type: str,
        source: str,
        agent_id: str | None = None,
        role: str | None = None,
        runtime_mode: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrajectoryRecord:
        return self._write_record(
            record_type=record_type,
            agent_id=agent_id,
            role=role,
            runtime_mode=runtime_mode,
            source=source,
            raw_text=None,
            metadata=metadata,
        )

    def _write_record(
        self,
        *,
        record_type: str,
        agent_id: str | None,
        role: str | None,
        runtime_mode: str | None,
        source: str,
        raw_text: str | None,
        parsed_action: dict[str, Any] | None = None,
        observation: dict[str, Any] | None = None,
        post_observation: dict[str, Any] | None = None,
        state_before: dict[str, Any] | None = None,
        state_after: dict[str, Any] | None = None,
        reward_components: dict[str, float] | None = None,
        error: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TrajectoryRecord:
        with self._lock:
            turn_index = self._turn_index
            self._turn_index += 1
            record = TrajectoryRecord(
                episode_id=self.episode_id,
                scenario_id=self.scenario_id,
                turn_index=turn_index,
                record_type=record_type,
                agent_id=agent_id,
                role=role,
                runtime_mode=runtime_mode,
                timestamp=datetime.now(timezone.utc).isoformat(),
                source=source,
                raw_text=raw_text,
                parsed_action=_jsonable(parsed_action),
                observation=_jsonable(observation),
                post_observation=_jsonable(post_observation),
                state_before=_jsonable(state_before),
                state_after=_jsonable(state_after),
                reward_components=_jsonable(reward_components),
                error=error,
                metadata=_jsonable(metadata),
            )
            with self.path.open('a', encoding='utf-8') as handle:
                handle.write(json.dumps(_jsonable(record), ensure_ascii=False, sort_keys=True) + '\n')
            return record


def classify_raw_action(raw_text: str) -> dict[str, Any]:
    stripped = raw_text.strip()
    lowered = stripped.lower()
    if not stripped:
        return {'kind': 'empty'}
    if lowered.startswith('/create'):
        return {'kind': 'character_creation', 'command': stripped}
    if lowered == '/check':
        return {'kind': 'story_check', 'command': stripped}
    if lowered.startswith('/'):
        return {'kind': 'command', 'command': stripped.split(maxsplit=1)[0], 'raw_command': stripped}
    return {'kind': 'natural_language', 'utterance': stripped}


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(item) for item in value]
    return value

