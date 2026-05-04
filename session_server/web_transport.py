from __future__ import annotations

from dataclasses import dataclass, field
import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import queue
import threading
import time
from typing import Any
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

from shared_types.errors import EncounterError
from shared_types.web_ui import WebControllerGrant

from .encounter_session import EncounterSession
from .storytelling_session import StorytellingSession
from .web_projection import (
    project_encounter_session_view,
    project_story_session_view,
    to_jsonable,
)


@dataclass(frozen=True)
class WebControllerLease:
    controller_token: str
    controller_id: str
    created_at: float
    last_seen_at: float


@dataclass
class _EventSubscriber:
    subscription_id: str
    controller_id: str
    items: queue.Queue[dict[str, Any]] = field(default_factory=queue.Queue)


class _WebTransportHTTPServer(ThreadingHTTPServer):
    def __init__(self, server_address, app: 'AuthoritativeWebServer') -> None:
        self.app = app
        super().__init__(server_address, _WebTransportRequestHandler)


class _WebTransportRequestHandler(BaseHTTPRequestHandler):
    server: _WebTransportHTTPServer

    def do_OPTIONS(self) -> None:
        self.server.app.handle_options(self)

    def do_GET(self) -> None:
        self.server.app.handle_get(self)

    def do_POST(self) -> None:
        self.server.app.handle_post(self)

    def log_message(self, format: str, *args) -> None:
        return


class AuthoritativeWebServer:
    def __init__(
        self,
        *,
        session: EncounterSession | StorytellingSession,
        host: str = '127.0.0.1',
        port: int = 8800,
        session_id: str = 'default-session',
    ) -> None:
        self.session = session
        self.host = host
        self.port = port
        self.session_id = session_id
        self._http_server: _WebTransportHTTPServer | None = None
        self._serve_thread: threading.Thread | None = None
        self._state_lock = threading.RLock()
        self._leases: dict[str, WebControllerLease] = {}
        self._subscribers: dict[str, dict[str, _EventSubscriber]] = {}
        self._event_counter = 0
        if isinstance(session, StorytellingSession):
            session.llm_feedback_sink = self._emit_feedback_event

    def start(self) -> None:
        if self._http_server is not None:
            raise RuntimeError('Web transport server is already started.')
        http_server = _WebTransportHTTPServer((self.host, self.port), self)
        self._http_server = http_server
        self.port = http_server.server_address[1]
        self._serve_thread = threading.Thread(target=http_server.serve_forever, name='web-transport-server', daemon=True)
        self._serve_thread.start()

    def serve_forever(self) -> None:
        self.start()
        try:
            while self._serve_thread is not None and self._serve_thread.is_alive():
                time.sleep(0.1)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._http_server is None:
            return
        self._http_server.shutdown()
        self._http_server.server_close()
        self._http_server = None
        if self._serve_thread is not None:
            self._serve_thread.join(timeout=1)
            self._serve_thread = None
        with self._state_lock:
            subscribers = self._subscribers
            self._subscribers = {}
        for subscriber_group in subscribers.values():
            for subscriber in subscriber_group.values():
                subscriber.items.put({'close': True})

    def broadcast_updates(self) -> None:
        with self._state_lock:
            tokens = list(self._leases)
        for token in tokens:
            self._publish_view(token)

    def handle_options(self, handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(HTTPStatus.NO_CONTENT)
        self._write_default_headers(handler, content_type='application/json')
        handler.end_headers()

    def handle_get(self, handler: BaseHTTPRequestHandler) -> None:
        try:
            parsed = urlparse(handler.path)
            if parsed.path == '/healthz':
                self._send_json(handler, HTTPStatus.OK, {'ok': True})
                return
            if parsed.path == '/api/session/view':
                token = self._query_token(parsed.query)
                view = self._view_for_token(token)
                self._send_json(handler, HTTPStatus.OK, {'view': to_jsonable(view)})
                return
            if parsed.path == '/api/session/events':
                token = self._query_token(parsed.query)
                self._handle_sse(handler, token)
                return
            self._send_json(handler, HTTPStatus.NOT_FOUND, {'error': 'Not found.'})
        except EncounterError as exc:
            self._send_json(handler, HTTPStatus.BAD_REQUEST, {'error': str(exc)})
        except Exception as exc:
            self._send_json(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {'error': str(exc)})

    def handle_post(self, handler: BaseHTTPRequestHandler) -> None:
        try:
            parsed = urlparse(handler.path)
            payload = self._read_json_body(handler)
            if parsed.path == '/api/session/join':
                grant = self._join(payload)
                view = self._view_for_token(grant.controller_token)
                self._send_json(handler, HTTPStatus.OK, {'grant': to_jsonable(grant), 'view': to_jsonable(view)})
                return
            if parsed.path == '/api/session/reconnect':
                grant = self._reconnect(payload)
                view = self._view_for_token(grant.controller_token)
                self._send_json(handler, HTTPStatus.OK, {'grant': to_jsonable(grant), 'view': to_jsonable(view)})
                return
            if parsed.path == '/api/session/command':
                token = self._payload_token(payload)
                command = payload.get('command')
                if not isinstance(command, str) or not command.strip():
                    raise EncounterError('Command submission requires a non-empty string command.')
                self._submit_command(token, command.strip())
                view = self._view_for_token(token)
                self._send_json(handler, HTTPStatus.OK, {'view': to_jsonable(view)})
                return
            if parsed.path == '/api/session/reaction':
                token = self._payload_token(payload)
                option_ids = payload.get('option_ids', payload.get('option_id'))
                if option_ids is not None and not isinstance(option_ids, (str, list)):
                    raise EncounterError('Reaction submission requires option_id as a string, option_ids as a list of strings, or null.')
                if isinstance(option_ids, list) and not all(isinstance(item, str) for item in option_ids):
                    raise EncounterError('Reaction option_ids entries must all be strings.')
                self._submit_reaction(token, option_ids)
                view = self._view_for_token(token)
                self._send_json(handler, HTTPStatus.OK, {'view': to_jsonable(view)})
                return
            self._send_json(handler, HTTPStatus.NOT_FOUND, {'error': 'Not found.'})
        except EncounterError as exc:
            self._send_json(handler, HTTPStatus.BAD_REQUEST, {'error': str(exc)})
        except Exception as exc:
            self._send_json(handler, HTTPStatus.INTERNAL_SERVER_ERROR, {'error': str(exc)})

    def _join(self, payload: dict[str, Any]) -> WebControllerGrant:
        controller_id = payload.get('controller_id')
        if not isinstance(controller_id, str) or not controller_id.strip():
            raise EncounterError('Join requires controller_id.')
        controller_id = controller_id.strip()
        binding = self._validate_controller(controller_id)
        token = uuid4().hex
        lease = WebControllerLease(
            controller_token=token,
            controller_id=controller_id,
            created_at=time.time(),
            last_seen_at=time.time(),
        )
        with self._state_lock:
            self._leases[token] = lease
            self._subscribers.setdefault(token, {})
        return WebControllerGrant(
            session_id=self.session_id,
            controller_id=controller_id,
            controller_token=token,
            role=binding.role,
            label=binding.label,
        )

    def _reconnect(self, payload: dict[str, Any]) -> WebControllerGrant:
        token = self._payload_token(payload)
        lease = self._lease_for_token(token)
        binding = self._validate_controller(lease.controller_id)
        return WebControllerGrant(
            session_id=self.session_id,
            controller_id=lease.controller_id,
            controller_token=token,
            role=binding.role,
            label=binding.label,
        )

    def _submit_command(self, token: str, command: str) -> None:
        controller_id = self._controller_id_for_token(token)
        with self._state_lock:
            if isinstance(self.session, StorytellingSession):
                self.session.handle_input(controller_id, command)
            else:
                self.session.execute_for_controller(controller_id, command)
            self._touch_lease(token)
        self.broadcast_updates()

    def _submit_reaction(self, token: str, option_ids: list[str] | str | None) -> None:
        controller_id = self._controller_id_for_token(token)
        with self._state_lock:
            if isinstance(self.session, StorytellingSession):
                self.session.encounter_session.respond_to_prompt(controller_id, option_ids)
            else:
                self.session.respond_to_prompt(controller_id, option_ids)
            self._touch_lease(token)
        self.broadcast_updates()

    def _view_for_token(self, token: str):
        controller_id = self._controller_id_for_token(token)
        with self._state_lock:
            self._touch_lease(token)
            return self._project_view(controller_id)

    def _project_view(self, controller_id: str):
        if isinstance(self.session, StorytellingSession):
            return project_story_session_view(self.session, controller_id, session_id=self.session_id)
        return project_encounter_session_view(self.session, controller_id, session_id=self.session_id)

    def _validate_controller(self, controller_id: str):
        if isinstance(self.session, StorytellingSession):
            return self.session.encounter_session.control_runtime.validate_controller(controller_id)
        return self.session.control_runtime.validate_controller(controller_id)

    def _touch_lease(self, token: str) -> None:
        lease = self._leases.get(token)
        if lease is None:
            return
        self._leases[token] = WebControllerLease(
            controller_token=lease.controller_token,
            controller_id=lease.controller_id,
            created_at=lease.created_at,
            last_seen_at=time.time(),
        )

    def _lease_for_token(self, token: str) -> WebControllerLease:
        with self._state_lock:
            lease = self._leases.get(token)
        if lease is None:
            raise EncounterError('Unknown controller token.')
        return lease

    def _controller_id_for_token(self, token: str) -> str:
        return self._lease_for_token(token).controller_id

    def _publish_view(self, token: str) -> None:
        lease = self._lease_for_token(token)
        view = self._view_for_token(token)
        event = {
            'id': self._next_event_id(),
            'event': 'view',
            'data': {'view': to_jsonable(view)},
        }
        for subscriber in list(self._subscribers.get(token, {}).values()):
            subscriber.items.put(event)

    def _emit_feedback_event(self, controller_id: str, kind: str, text: str) -> None:
        if not text.strip():
            return
        with self._state_lock:
            matching_tokens = [token for token, lease in self._leases.items() if lease.controller_id == controller_id]
            event = {
                'id': self._next_event_id(),
                'event': kind,
                'data': {'controller_id': controller_id, 'kind': kind, 'message': text},
            }
            for token in matching_tokens:
                for subscriber in list(self._subscribers.get(token, {}).values()):
                    subscriber.items.put(event)

    def _next_event_id(self) -> int:
        self._event_counter += 1
        return self._event_counter

    def _handle_sse(self, handler: BaseHTTPRequestHandler, token: str) -> None:
        lease = self._lease_for_token(token)
        subscriber = _EventSubscriber(subscription_id=uuid4().hex, controller_id=lease.controller_id)
        with self._state_lock:
            self._subscribers.setdefault(token, {})[subscriber.subscription_id] = subscriber
        subscriber.items.put({
            'id': self._next_event_id(),
            'event': 'view',
            'data': {'view': to_jsonable(self._view_for_token(token))},
        })
        handler.send_response(HTTPStatus.OK)
        self._write_default_headers(handler, content_type='text/event-stream')
        handler.send_header('Cache-Control', 'no-cache')
        handler.send_header('Connection', 'keep-alive')
        handler.end_headers()
        try:
            while True:
                try:
                    item = subscriber.items.get(timeout=15)
                except queue.Empty:
                    handler.wfile.write(b': keepalive\n\n')
                    handler.wfile.flush()
                    continue
                if item.get('close'):
                    return
                payload = self._format_sse(item['event'], item['data'], event_id=item['id'])
                handler.wfile.write(payload)
                handler.wfile.flush()
        except OSError:
            return
        finally:
            with self._state_lock:
                token_subscribers = self._subscribers.get(token)
                if token_subscribers is not None:
                    token_subscribers.pop(subscriber.subscription_id, None)

    def _format_sse(self, event_name: str, data: dict[str, Any], *, event_id: int) -> bytes:
        body = json.dumps(data, separators=(',', ':'), sort_keys=True)
        return f'id: {event_id}\nevent: {event_name}\ndata: {body}\n\n'.encode('utf-8')

    def _send_json(self, handler: BaseHTTPRequestHandler, status: HTTPStatus, payload: dict[str, Any]) -> None:
        data = json.dumps(payload, separators=(',', ':'), sort_keys=True).encode('utf-8')
        handler.send_response(status)
        self._write_default_headers(handler, content_type='application/json')
        handler.send_header('Content-Length', str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    def _write_default_headers(self, handler: BaseHTTPRequestHandler, *, content_type: str) -> None:
        handler.send_header('Content-Type', content_type)
        handler.send_header('Access-Control-Allow-Origin', '*')
        handler.send_header('Access-Control-Allow-Headers', 'Content-Type')
        handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')

    def _read_json_body(self, handler: BaseHTTPRequestHandler) -> dict[str, Any]:
        length = int(handler.headers.get('Content-Length', '0') or '0')
        raw = handler.rfile.read(length) if length else b'{}'
        if not raw:
            return {}
        payload = json.loads(raw.decode('utf-8'))
        if not isinstance(payload, dict):
            raise EncounterError('Request body must be a JSON object.')
        return payload

    def _query_token(self, query: str) -> str:
        params = parse_qs(query, keep_blank_values=False)
        token = params.get('reconnect_token', params.get('controller_token', [None]))[0]
        if token is None or not str(token).strip():
            raise EncounterError('reconnect_token query parameter is required.')
        return str(token).strip()

    def _payload_token(self, payload: dict[str, Any]) -> str:
        token = payload.get('reconnect_token', payload.get('controller_token'))
        if not isinstance(token, str) or not token.strip():
            raise EncounterError('reconnect_token is required.')
        return token.strip()
