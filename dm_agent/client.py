from __future__ import annotations

from dataclasses import dataclass
from http import client as http_client
from typing import Any, Callable, Protocol
from urllib import error, request
from urllib.parse import urljoin
import json

from .config import LLMConfig


class LLMResponseError(RuntimeError):
    pass


_CHAT_JSON_HARDENING_INSTRUCTION = (
    'DeepSeek JSON final-output contract: return one bare, parseable JSON object only. '
    'Think hard internally before answering, but do not reveal reasoning in the final content. '
    'The final content will be parsed by deterministic code and reviewed by a separate GPT verifier; malformed JSON, markdown wrappers, or extra text fails. '
    'Do not emit markdown fences, backticks, prose, headings, labels, XML/HTML tags, <think> blocks, YAML, comments, byte-order marks, zero-width characters, ellipses, Python literals such as None/True/False, NaN, Infinity, single-quoted strings, unescaped control characters, or trailing commas. '
    'Do not wrap the object inside another key such as json, response, data, result, or output unless the caller-provided schema explicitly requires that exact key. '
    'The first non-whitespace character must be { and the last non-whitespace character must be }.'
)


@dataclass(frozen=True)
class ResponsesRequest:
    model: str
    input: tuple[dict[str, Any], ...]
    instructions: str
    temperature: float = 0.0
    max_output_tokens: int = 512
    metadata: dict[str, str] | None = None
    response_format: dict[str, Any] | None = None
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = None

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
        if self.thinking_enabled is not None:
            payload['thinking'] = {'type': 'enabled' if self.thinking_enabled else 'disabled'}
        if self.reasoning_effort is not None:
            payload['reasoning_effort'] = self.reasoning_effort
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
        choice_chunks: list[str] = []
        for choice in self.payload.get('choices', []) or []:
            if not isinstance(choice, dict):
                continue
            message = choice.get('message')
            if not isinstance(message, dict):
                continue
            content = message.get('content')
            if isinstance(content, str) and content:
                choice_chunks.append(content)
        if choice_chunks:
            return ''.join(choice_chunks)
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
    def __init__(self, *, timeout_seconds: float = 300.0, stream_timeout_seconds: float = 300.0, post_read_retries: int = 4) -> None:
        if timeout_seconds <= 0:
            raise ValueError('timeout_seconds must be > 0.')
        if stream_timeout_seconds <= 0:
            raise ValueError('stream_timeout_seconds must be > 0.')
        if post_read_retries < 0:
            raise ValueError('post_read_retries must be >= 0.')
        self.timeout_seconds = timeout_seconds
        self.stream_timeout_seconds = stream_timeout_seconds
        self.post_read_retries = post_read_retries

    def _http_error(self, exc: error.HTTPError) -> LLMResponseError:
        try:
            body = exc.read().decode('utf-8', errors='replace').strip()
        except Exception:
            body = ''
        suffix = f' Response body: {body[:500]}' if body else ''
        return LLMResponseError(f'LLM request failed with HTTP {exc.code}.{suffix}')

    def post(self, *, url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode('utf-8')
        for attempt in range(self.post_read_retries + 1):
            req = request.Request(url, data=body, headers=headers, method='POST')
            try:
                with request.urlopen(req, timeout=self.timeout_seconds) as response:
                    raw = response.read().decode('utf-8')
                break
            except error.HTTPError as exc:
                raise self._http_error(exc) from exc
            except error.URLError as exc:
                if attempt < self.post_read_retries:
                    continue
                raise LLMResponseError(f'LLM request failed: {exc.reason}.') from exc
            except http_client.IncompleteRead as exc:
                if attempt >= self.post_read_retries:
                    raise LLMResponseError('LLM request failed while reading response: incomplete HTTP response.') from exc
        else:
            raise LLMResponseError('LLM request failed while reading response.')
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
            with request.urlopen(req, timeout=self.stream_timeout_seconds) as response:
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
        thinking_enabled: bool | None = None,
        reasoning_effort: str | None = None,
    ) -> ResponsesRequest:
        return ResponsesRequest(
            model=self.config.responses_model,
            input=input_messages,
            instructions=instructions,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            metadata=metadata,
            response_format=response_format,
            thinking_enabled=thinking_enabled,
            reasoning_effort=reasoning_effort,
        )

    def create_response(
        self,
        request_spec: ResponsesRequest,
        *,
        stream_handler: Callable[[LLMStreamEvent], None] | None = None,
    ) -> LLMResponse:
        if self.config.api_format == 'chat_completions':
            return self._create_chat_completion_response(request_spec, stream_handler=stream_handler)
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

    def _create_chat_completion_response(
        self,
        request_spec: ResponsesRequest,
        *,
        stream_handler: Callable[[LLMStreamEvent], None] | None = None,
    ) -> LLMResponse:
        payload = self._chat_completion_payload(request_spec, stream=stream_handler is not None)
        url = urljoin(self.config.base_url.rstrip('/') + '/', 'chat/completions')
        headers = {
            'Authorization': f'Bearer {self.config.api_key}',
            'Content-Type': 'application/json',
        }
        if stream_handler is None:
            raw = self.transport.post(url=url, headers=headers, payload=payload)
            return LLMResponse(request=request_spec, payload=raw)
        raw = self._stream_chat_completion_response(url=url, headers=headers, payload=payload, stream_handler=stream_handler)
        return LLMResponse(request=request_spec, payload=raw)

    def _chat_completion_payload(self, request_spec: ResponsesRequest, *, stream: bool = False) -> dict[str, Any]:
        messages: list[dict[str, str]] = []
        if request_spec.instructions.strip():
            messages.append({'role': 'system', 'content': request_spec.instructions})
        for message in request_spec.input:
            role = str(message.get('role', 'user')).strip() or 'user'
            messages.append({'role': role, 'content': self._chat_message_content(message.get('content'))})
        json_object_request = self._is_json_object_request(request_spec)
        if json_object_request:
            messages = self._with_chat_json_hardening(messages)
        payload: dict[str, Any] = {
            'model': request_spec.model,
            'messages': messages,
            'temperature': request_spec.temperature,
            'max_tokens': request_spec.max_output_tokens,
        }
        if self._is_deepseek_v4_model(request_spec.model) and (
            json_object_request or request_spec.thinking_enabled is not None or request_spec.reasoning_effort is not None
        ):
            thinking_enabled = True if request_spec.thinking_enabled is None else request_spec.thinking_enabled
            payload['thinking'] = {'type': 'enabled' if thinking_enabled else 'disabled'}
            if thinking_enabled:
                if request_spec.reasoning_effort is not None or json_object_request:
                    payload['reasoning_effort'] = request_spec.reasoning_effort or 'high'
            elif request_spec.reasoning_effort is not None:
                payload['reasoning_effort'] = request_spec.reasoning_effort
        if request_spec.response_format is not None:
            payload['response_format'] = dict(request_spec.response_format)
        if stream:
            payload['stream'] = True
        return payload

    def _is_json_object_request(self, request_spec: ResponsesRequest) -> bool:
        if not isinstance(request_spec.response_format, dict):
            return False
        return request_spec.response_format.get('type') == 'json_object'

    def _is_deepseek_v4_model(self, model: str) -> bool:
        return model.strip().lower() in {'deepseek-v4-pro', 'deepseek-v4-flash'}

    def _with_chat_json_hardening(self, messages: list[dict[str, str]]) -> list[dict[str, str]]:
        if not messages or messages[0].get('role') != 'system':
            return [{'role': 'system', 'content': _CHAT_JSON_HARDENING_INSTRUCTION}] + messages
        hardened = list(messages)
        first = dict(hardened[0])
        first['content'] = f"{first.get('content', '').rstrip()} {_CHAT_JSON_HARDENING_INSTRUCTION}".strip()
        hardened[0] = first
        return hardened

    def _chat_message_content(self, content: Any) -> str:
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            chunks: list[str] = []
            for entry in content:
                if not isinstance(entry, dict):
                    continue
                text = entry.get('text')
                if isinstance(text, str):
                    chunks.append(text)
            return '\n'.join(chunks)
        if content is None:
            return ''
        return json.dumps(content, separators=(',', ':'))

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

    def _stream_chat_completion_response(
        self,
        *,
        url: str,
        headers: dict[str, str],
        payload: dict[str, Any],
        stream_handler: Callable[[LLMStreamEvent], None],
    ) -> dict[str, Any]:
        events = self.transport.stream(url=url, headers=headers, payload=payload)
        output_chunks: list[str] = []
        for event in events:
            error = event.get('error')
            if isinstance(error, dict):
                raise LLMResponseError(str(error.get('message', 'LLM streaming response failed.')))
            for choice in event.get('choices', []) or []:
                if not isinstance(choice, dict):
                    continue
                delta = choice.get('delta')
                if not isinstance(delta, dict):
                    continue
                reasoning = delta.get('reasoning_content')
                if isinstance(reasoning, str) and reasoning:
                    stream_handler(LLMStreamEvent(kind='reasoning', text=reasoning))
                content = delta.get('content')
                if isinstance(content, str) and content:
                    output_chunks.append(content)
                    stream_handler(LLMStreamEvent(kind='output', text=content))
        return {
            'choices': [
                {
                    'message': {
                        'role': 'assistant',
                        'content': ''.join(output_chunks),
                    }
                }
            ]
        }

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
