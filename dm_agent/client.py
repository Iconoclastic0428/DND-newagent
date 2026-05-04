from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Protocol
from urllib import error, request
from urllib.parse import urljoin
import json

from .config import LLMConfig


class LLMResponseError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResponsesRequest:
    model: str
    input: tuple[dict[str, Any], ...]
    instructions: str
    temperature: float = 0.0
    max_output_tokens: int = 512
    metadata: dict[str, str] | None = None
    response_format: dict[str, Any] | None = None

    def to_payload(self, *, stream: bool = False) -> dict[str, Any]:
        payload: dict[str, Any] = {
            'model': self.model,
            'input': list(self.input),
            'instructions': self.instructions,
            'temperature': self.temperature,
            'max_output_tokens': self.max_output_tokens,
        }
        if self.metadata is not None:
            payload['metadata'] = dict(self.metadata)
        if self.response_format is not None:
            payload['response_format'] = dict(self.response_format)
        if stream:
            payload['stream'] = True
        return payload


@dataclass(frozen=True)
class LLMStreamEvent:
    kind: str
    text: str


@dataclass(frozen=True)
class LLMResponse:
    request: ResponsesRequest
    payload: dict[str, Any]

    @property
    def output_text(self) -> str:
        direct = self.payload.get('output_text')
        if isinstance(direct, str) and direct.strip():
            return direct
        assistant_chunks: list[str] = []
        fallback_chunks: list[str] = []
        for item in self.payload.get('output', []) or []:
            if not isinstance(item, dict):
                continue
            content = item.get('content', []) or []
            for entry in content:
                if not isinstance(entry, dict):
                    continue
                text = entry.get('text')
                if not isinstance(text, str) or not text:
                    continue
                entry_type = str(entry.get('type', ''))
                if item.get('type') == 'message' or item.get('role') == 'assistant':
                    if entry_type in {'output_text', 'text'}:
                        assistant_chunks.append(text)
                elif entry_type not in {'reasoning_text'}:
                    fallback_chunks.append(text)
        if assistant_chunks:
            return ''.join(assistant_chunks)
        return ''.join(fallback_chunks)


class LLMTransport(Protocol):
    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def stream(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        ...


class LLMHttpTransport:
    def _http_error(self, exc: error.HTTPError) -> LLMResponseError:
        try:
            body = exc.read().decode('utf-8', errors='replace').strip()
        except Exception:
            body = ''
        suffix = f' Response body: {body[:500]}' if body else ''
        return LLMResponseError(f'LLM request failed with HTTP {exc.code}.{suffix}')

    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        req = request.Request(url, data=body, headers=headers, method='POST')
        try:
            with request.urlopen(req, timeout=60) as response:
                raw = response.read().decode('utf-8')
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise LLMResponseError(f'LLM request failed: {exc.reason}.') from exc
        data = json.loads(raw)
        if not isinstance(data, dict):
            raise LLMResponseError('LLM response payload must be a JSON object.')
        return data

    def stream(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> list[dict[str, Any]]:
        body = json.dumps(payload).encode('utf-8')
        request_headers = dict(headers)
        request_headers['Accept'] = 'text/event-stream'
        req = request.Request(url, data=body, headers=request_headers, method='POST')
        events: list[dict[str, Any]] = []
        try:
            with request.urlopen(req, timeout=120) as response:
                for raw_line in response:
                    line = raw_line.decode('utf-8', errors='replace').strip()
                    if not line or line.startswith(':'):
                        continue
                    if not line.startswith('data:'):
                        continue
                    data_text = line[5:].strip()
                    if data_text == '[DONE]':
                        break
                    event = json.loads(data_text)
                    if isinstance(event, dict):
                        events.append(event)
        except error.HTTPError as exc:
            raise self._http_error(exc) from exc
        except error.URLError as exc:
            raise LLMResponseError(f'LLM request failed: {exc.reason}.') from exc
        return events


class LLMClient:
    def __init__(self, config: LLMConfig, *, transport: LLMTransport | None = None) -> None:
        self.config = config
        self.transport = transport or LLMHttpTransport()

    def build_request(
        self,
        *,
        instructions: str,
        input_messages: tuple[dict[str, Any], ...],
        metadata: dict[str, str] | None = None,
        temperature: float = 0.0,
        max_output_tokens: int = 512,
        response_format: dict[str, Any] | None = None,
    ) -> ResponsesRequest:
        return ResponsesRequest(
            model=self.config.responses_model,
            input=input_messages,
            instructions=instructions,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
            response_format=response_format,
        )

    def create_response(
        self,
        request_spec: ResponsesRequest,
        *,
        stream_handler: Callable[[LLMStreamEvent], None] | None = None,
    ) -> LLMResponse:
        payload = request_spec.to_payload(stream=stream_handler is not None)
        url = urljoin(self.config.base_url.rstrip('/') + '/', 'responses')
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
        }
        if stream_handler is None:
            raw = self.transport.post(url=url, headers=headers, payload=payload)
            return LLMResponse(request=request_spec, payload=raw)
        raw = self._stream_response(url=url, headers=headers, payload=payload, stream_handler=stream_handler)
        return LLMResponse(request=request_spec, payload=raw)

    def _stream_response(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        stream_handler: Callable[[LLMStreamEvent], None],
    ) -> dict[str, Any]:
        events = self.transport.stream(url=url, headers=headers, payload=payload)
        final_payload: dict[str, Any] | None = None
        for event in events:
            event_type = str(event.get('type', ''))
            delta = self._extract_stream_delta(event)
            if delta is not None:
                stream_handler(delta)
            if event_type == 'response.failed':
                failure = event.get('response', event)
                message = 'LLM streaming response failed.'
                if isinstance(failure, dict):
                    message = str(failure.get('error', failure.get('message', message)))
                raise LLMResponseError(message)
            if event_type == 'response.completed' and isinstance(event.get('response'), dict):
                final_payload = event['response']
        if final_payload is None:
            raise LLMResponseError('LLM streaming response completed without a final payload.')
        return final_payload

    def _extract_stream_delta(self, event: dict[str, Any]) -> LLMStreamEvent | None:
        event_type = str(event.get('type', ''))
        if 'reasoning' in event_type:
            text = self._extract_text(event.get('delta')) or self._extract_nested_text(event)
            if text:
                return LLMStreamEvent(kind='reasoning', text=text)
        if 'output_text' in event_type or 'text' in event_type:
            text = self._extract_text(event.get('delta')) or self._extract_nested_text(event)
            if text:
                return LLMStreamEvent(kind='output', text=text)
        return None

    def _extract_text(self, value: Any) -> str | None:
        if isinstance(value, str) and value:
            return value
        return None

    def _extract_nested_text(self, value: Any) -> str | None:
        if isinstance(value, dict):
            text = value.get('text')
            if isinstance(text, str) and text:
                return text
            for nested in ('part', 'item', 'content', 'response'):
                if nested in value:
                    found = self._extract_nested_text(value[nested])
                    if found:
                        return found
        if isinstance(value, list):
            for item in value:
                found = self._extract_nested_text(item)
                if found:
                    return found
        return None
