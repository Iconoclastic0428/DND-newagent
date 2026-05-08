from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from websockets.exceptions import ConnectionClosed
from websockets.sync.server import serve as ws_serve

from session_server.bootstrap import build_lmop_story_demo_session
from shared_types.errors import EncounterPermissionError, EncounterValidationError
from shared_types.travel import HexCoord, TravelPace
from shared_types.web_ui import WebControllerGrant

from .web_projection import inspect_cell, inspect_travel_hex, preview_path, preview_travel_route, project_encounter_session_view, project_manual_demo_wrapper_view, project_story_session_view, to_jsonable


@dataclass
class ConnectedWebController:
    controller_id: str
    websocket: Any
    send_lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, payload: dict) -> None:
        data = json.dumps(to_jsonable(payload))
        with self.send_lock:
            self.websocket.send(data)

    def close(self) -> None:
        try:
            self.websocket.close()
        except Exception:
            pass


class _FrontendHttpHandler(SimpleHTTPRequestHandler):
    server_version = 'DndWebFrontend/0.1'

    def __init__(
        self,
        *args,
        directory: str,
        config_provider,
        automation_enabled: bool,
        automation_state_provider,
        automation_input_handler,
        automation_prompt_response_handler,
        **kwargs,
    ):
        self._config_provider = config_provider
        self._automation_enabled = automation_enabled
        self._automation_state_provider = automation_state_provider
        self._automation_input_handler = automation_input_handler
        self._automation_prompt_response_handler = automation_prompt_response_handler
        super().__init__(*args, directory=directory, **kwargs)

    def end_headers(self) -> None:
        self.send_header('Cache-Control', 'no-store, max-age=0')
        self.send_header('Pragma', 'no-cache')
        self.send_header('Expires', '0')
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path == '/config.json':
            payload = json.dumps(self._config_provider()).encode('utf-8')
            self.send_response(HTTPStatus.OK)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        if parsed.path == '/automation/state':
            if not self._automation_enabled:
                self.send_error(HTTPStatus.NOT_FOUND, 'Automation API is disabled.')
                return
            query = parse_qs(parsed.query, keep_blank_values=False)
            controller_id = query.get('controller_id', [None])[0]
            if not isinstance(controller_id, str) or not controller_id:
                self.send_error(HTTPStatus.BAD_REQUEST, 'Query parameter `controller_id` is required.')
                return
            try:
                payload = self._automation_state_provider(controller_id)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                return
            self._write_json(HTTPStatus.OK, payload)
            return
        if parsed.path in {'', '/'}:
            self.path = '/index.html'
        return super().do_GET()

    def do_POST(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path not in {'/automation/input', '/automation/prompt-response'}:
            self.send_error(HTTPStatus.NOT_FOUND, 'Unknown endpoint.')
            return
        if not self._automation_enabled:
            self.send_error(HTTPStatus.NOT_FOUND, 'Automation API is disabled.')
            return
        try:
            raw_body = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        except ValueError:
            self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': 'Invalid Content-Length header.'})
            return
        try:
            payload = json.loads(raw_body.decode('utf-8'))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': f'Invalid JSON body: {exc}'})
            return
        if not isinstance(payload, dict):
            self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': 'Automation request payload must be a JSON object.'})
            return
        if parsed.path == '/automation/input':
            controller_id = payload.get('controller_id')
            text = payload.get('text')
            if not isinstance(controller_id, str) or not controller_id:
                self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': '`controller_id` must be a non-empty string.'})
                return
            if not isinstance(text, str):
                self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': '`text` must be a string.'})
                return
            try:
                response = self._automation_input_handler(controller_id, text)
            except Exception as exc:
                self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
                return
            self._write_json(HTTPStatus.OK, response)
            return
        controller_id = payload.get('controller_id')
        if not isinstance(controller_id, str) or not controller_id:
            self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': '`controller_id` must be a non-empty string.'})
            return
        option_ids = payload.get('option_ids', payload.get('option_id'))
        try:
            response = self._automation_prompt_response_handler(controller_id, option_ids)
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {'ok': False, 'error': str(exc)})
            return
        self._write_json(HTTPStatus.OK, response)

    def log_message(self, format: str, *args) -> None:
        return

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(to_jsonable(payload)).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class SessionWebServer:
    def __init__(
        self,
        *,
        session,
        session_id: str,
        controller_grants: tuple[WebControllerGrant, ...],
        http_host: str = '127.0.0.1',
        http_port: int = 8000,
        websocket_host: str = '127.0.0.1',
        websocket_port: int = 8767,
        static_root: str | Path | None = None,
        automation_api_enabled: bool = False,
    ) -> None:
        self.session = session
        self.session_id = session_id
        self.http_host = http_host
        self.http_port = http_port
        self.websocket_host = websocket_host
        self.websocket_port = websocket_port
        self.static_root = Path(static_root or Path(__file__).resolve().parents[1] / 'web_frontend').resolve()
        self.controller_grants = {grant.controller_id: grant for grant in controller_grants}
        self.automation_api_enabled = automation_api_enabled
        self._http_server: ThreadingHTTPServer | None = None
        self._http_thread: threading.Thread | None = None
        self._ws_server = None
        self._ws_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._clients: dict[str, ConnectedWebController] = {}
        self.session.llm_feedback_sink = self._emit_llm_feedback

    @classmethod
    def build_story_demo(
        cls,
        *,
        base_url: str | None = None,
        env_path: str | Path = '.env',
        client_transport=None,
        session_id: str = 'lmop-web-demo',
        http_host: str = '127.0.0.1',
        http_port: int = 8000,
        websocket_host: str = '127.0.0.1',
        websocket_port: int = 8767,
        static_root: str | Path | None = None,
        automation_api_enabled: bool = False,
    ) -> 'SessionWebServer':
        session = build_lmop_story_demo_session(
            base_url=base_url,
            env_path=env_path,
            client_transport=client_transport,
        )
        grants = tuple(
            WebControllerGrant(
                session_id=session_id,
                controller_id=controller_id,
                controller_token=f'{controller_id}-token',
                role=binding.role,
                label=binding.label,
            )
            for controller_id, binding in session.encounter_session.control_runtime.controllers.items()
        )
        return cls(
            session=session,
            session_id=session_id,
            controller_grants=grants,
            http_host=http_host,
            http_port=http_port,
            websocket_host=websocket_host,
            websocket_port=websocket_port,
            static_root=static_root,
            automation_api_enabled=automation_api_enabled,
        )

    def start(self) -> None:
        if self._http_server is not None or self._ws_server is not None:
            raise RuntimeError('Web server is already running.')
        if hasattr(self.session, 'system_open_scene'):
            with self._state_lock:
                self.session.system_open_scene()
        self._start_http_server()
        self._start_websocket_server()
        self._log(f'HTTP frontend on http://{self.http_host}:{self.http_port}')
        self._log(f'WebSocket transport on ws://{self.websocket_host}:{self.websocket_port}')
        if self.automation_api_enabled:
            self._log(f'Automation API on http://{self.http_host}:{self.http_port}/automation/input')
        for grant in self.controller_grants.values():
            self._log(f'Join token: {grant.controller_id} -> {grant.controller_token}')

    def serve_forever(self) -> None:
        self.start()
        try:
            while not self._stop_event.is_set():
                time.sleep(0.1)
        finally:
            self.shutdown()

    def shutdown(self) -> None:
        if self._stop_event.is_set():
            return
        self._stop_event.set()
        if self._http_server is not None:
            self._http_server.shutdown()
            self._http_server.server_close()
            self._http_server = None
        if self._ws_server is not None:
            self._ws_server.shutdown()
            self._ws_server = None
        with self._state_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.close()
        if self._http_thread is not None:
            self._http_thread.join(timeout=1)
        if self._ws_thread is not None:
            self._ws_thread.join(timeout=1)

    def _start_http_server(self) -> None:
        handler = partial(
            _FrontendHttpHandler,
            directory=str(self.static_root),
            config_provider=self._frontend_config,
            automation_enabled=self.automation_api_enabled,
            automation_state_provider=self.automation_snapshot,
            automation_input_handler=self.automation_submit_input,
            automation_prompt_response_handler=self.automation_respond_to_prompt,
        )
        self._http_server = ThreadingHTTPServer((self.http_host, self.http_port), handler)
        self.http_port = self._http_server.server_address[1]
        self._http_thread = threading.Thread(target=self._http_server.serve_forever, name='web-frontend-http', daemon=True)
        self._http_thread.start()

    def _start_websocket_server(self) -> None:
        if self.websocket_port == 0:
            self.websocket_port = _allocate_port(self.websocket_host)
        self._ws_server = ws_serve(self._handle_websocket, self.websocket_host, self.websocket_port)
        self._ws_thread = threading.Thread(target=self._ws_server.serve_forever, name='web-frontend-ws', daemon=True)
        self._ws_thread.start()

    def _frontend_config(self) -> dict[str, object]:
        return {
            'sessionId': self.session_id,
            'wsUrl': f'ws://{self.websocket_host}:{self.websocket_port}',
            'availableControllers': [
                {
                    'controllerId': grant.controller_id,
                    'role': grant.role.value,
                    'label': grant.label,
                }
                for grant in self.controller_grants.values()
            ],
            'portalPages': [
                {
                    'controllerId': grant.controller_id,
                    'role': grant.role.value,
                    'label': grant.label,
                    'path': _portal_query_path(grant.controller_id),
                }
                for grant in self.controller_grants.values()
            ],
            'automationApiEnabled': self.automation_api_enabled,
        }

    def automation_snapshot(self, controller_id: str) -> dict[str, object]:
        with self._state_lock:
            self._validate_controller(controller_id)
            prompt = self._project_prompt(controller_id)
            return {
                'ok': True,
                'sessionId': self.session_id,
                'controllerId': controller_id,
                'view': to_jsonable(self._project_view(controller_id)),
                'prompt': to_jsonable(prompt),
            }

    def automation_submit_input(self, controller_id: str, text: str) -> dict[str, object]:
        if not text.strip():
            raise EncounterPermissionError('Automation input requires non-empty `text`.')
        with self._state_lock:
            self._validate_controller(controller_id)
            self._send_command_echo(controller_id, text)
            try:
                self._submit_input(controller_id, text)
            except Exception as exc:
                self._send_to_controller(controller_id, {'type': 'error', 'message': str(exc)})
                raise
            self._broadcast_updates()
            prompt = self._project_prompt(controller_id)
            return {
                'ok': True,
                'sessionId': self.session_id,
                'controllerId': controller_id,
                'text': text,
                'view': to_jsonable(self._project_view(controller_id)),
                'prompt': to_jsonable(prompt),
            }

    def automation_respond_to_prompt(self, controller_id: str, option_ids: object) -> dict[str, object]:
        with self._state_lock:
            self._validate_controller(controller_id)
            prompt = self._prompt_for_response(controller_id)
            normalized = self._normalize_prompt_response(prompt, option_ids)
            if hasattr(self.session, 'encounter_session'):
                self.session.encounter_session.respond_to_prompt(controller_id, normalized)
            else:
                self.session.respond_to_prompt(controller_id, normalized)
            self._broadcast_updates()
            prompt = self._project_prompt(controller_id)
            return {
                'ok': True,
                'sessionId': self.session_id,
                'controllerId': controller_id,
                'option_ids': to_jsonable(normalized),
                'view': to_jsonable(self._project_view(controller_id)),
                'prompt': to_jsonable(prompt),
            }

    def _handle_websocket(self, websocket) -> None:
        controller_id: str | None = None
        try:
            raw_join = websocket.recv()
            if not isinstance(raw_join, str):
                raise EncounterPermissionError('Expected a JSON text join message.')
            join_message = json.loads(raw_join)
            controller_id = self._register_join(websocket, join_message)
            grant = self.controller_grants[controller_id]
            self._send_to_controller(
                controller_id,
                {
                    'type': 'joined',
                    'sessionId': self.session_id,
                    'controllerId': controller_id,
                    'role': grant.role,
                    'label': grant.label,
                },
            )
            self._send_view(controller_id)
            self._send_prompt_if_any(controller_id)
            for raw_message in websocket:
                if self._stop_event.is_set():
                    return
                if not isinstance(raw_message, str):
                    continue
                if not raw_message.strip():
                    continue
                try:
                    message = json.loads(raw_message)
                    self._handle_message(controller_id, message)
                except Exception as exc:
                    self._send_to_controller(controller_id, {'type': 'error', 'message': str(exc)})
        except ConnectionClosed:
            return
        except AssertionError as exc:
            if "connection isn't closed yet" in str(exc):
                return
            raise
        finally:
            if controller_id is not None:
                self._unregister_client(controller_id, websocket=websocket)

    def _register_join(self, websocket, join_message: dict[str, object]) -> str:
        if join_message.get('type') != 'join':
            raise EncounterPermissionError('Expected an initial `join` message.')
        session_id = join_message.get('session_id')
        controller_id = join_message.get('controller_id')
        controller_token = join_message.get('controller_token')
        if session_id != self.session_id:
            raise EncounterPermissionError('Unknown session id.')
        if not isinstance(controller_id, str) or not isinstance(controller_token, str):
            raise EncounterPermissionError('Join requires string `controller_id` and `controller_token`.')
        grant = self.controller_grants.get(controller_id)
        if grant is None:
            raise EncounterPermissionError('Unknown controller id.')
        if controller_token != grant.controller_token:
            raise EncounterPermissionError('Invalid controller token.')
        self._validate_controller(controller_id)
        with self._state_lock:
            existing = self._clients.pop(controller_id, None)
            if existing is not None:
                existing.close()
            self._clients[controller_id] = ConnectedWebController(controller_id=controller_id, websocket=websocket)
        self._log(f'Web client connected: {controller_id}')
        return controller_id

    def _unregister_client(self, controller_id: str, *, websocket=None) -> None:
        with self._state_lock:
            client = self._clients.get(controller_id)
            if client is None:
                return
            if websocket is not None and client.websocket is not websocket:
                return
            self._clients.pop(controller_id, None)
        client.close()
        self._log(f'Web client disconnected: {controller_id}')

    def _handle_message(self, controller_id: str, message: dict[str, object]) -> None:
        message_type = message.get('type')
        if message_type == 'command':
            text = message.get('text')
            if not isinstance(text, str):
                raise EncounterPermissionError('Command messages require string `text`.')
            self._send_command_echo(controller_id, text)
            with self._state_lock:
                self._submit_input(controller_id, text)
                self._broadcast_updates()
            return
        if message_type in {'reaction', 'prompt_response'}:
            raw_option_ids = message.get('option_ids', message.get('option_id'))
            with self._state_lock:
                prompt = self._prompt_for_response(controller_id)
                option_ids = self._normalize_prompt_response(prompt, raw_option_ids)
                if hasattr(self.session, 'encounter_session'):
                    self.session.encounter_session.respond_to_prompt(controller_id, option_ids)
                else:
                    self.session.respond_to_prompt(controller_id, option_ids)
                self._broadcast_updates()
            return
        if message_type == 'inspect_cell':
            x = _require_int(message.get('x'), 'x')
            y = _require_int(message.get('y'), 'y')
            z = message.get('z')
            if z is not None:
                z = _require_int(z, 'z')
            with self._state_lock:
                payload = inspect_cell(self.session, controller_id, x=x, y=y, z=z)
            self._send_to_controller(controller_id, {'type': 'inspection', 'inspection': payload})
            return
        if message_type == 'inspect_travel_hex':
            q = _require_int(message.get('q'), 'q')
            r = _require_int(message.get('r'), 'r')
            with self._state_lock:
                payload = inspect_travel_hex(self.session, controller_id, q=q, r=r)
            self._send_to_controller(controller_id, {'type': 'inspection', 'inspection': payload})
            return
        if message_type == 'preview_move':
            x = _require_int(message.get('x'), 'x')
            y = _require_int(message.get('y'), 'y')
            z = message.get('z')
            mode = message.get('mode', 'walk')
            if z is not None:
                z = _require_int(z, 'z')
            if not isinstance(mode, str):
                raise EncounterPermissionError('Move preview requires string `mode`.')
            with self._state_lock:
                payload = preview_path(self.session, controller_id, x=x, y=y, z=z, mode=mode)
            self._send_to_controller(controller_id, {'type': 'path_preview', 'preview': payload})
            return
        if message_type == 'travel_route_preview':
            q = message.get('q')
            r = message.get('r')
            destination_location_id = message.get('destination_location_id')
            if q is not None:
                q = _require_int(q, 'q')
            if r is not None:
                r = _require_int(r, 'r')
            if destination_location_id is not None and not isinstance(destination_location_id, str):
                raise EncounterPermissionError('Travel route preview requires string `destination_location_id` when present.')
            with self._state_lock:
                payload = preview_travel_route(self.session, controller_id, q=q, r=r, destination_location_id=destination_location_id)
            self._send_to_controller(controller_id, {'type': 'path_preview', 'preview': payload})
            return
        if message_type == 'move_proposal':
            x = _require_int(message.get('x'), 'x')
            y = _require_int(message.get('y'), 'y')
            z = message.get('z')
            mode = message.get('mode', 'walk')
            if z is not None:
                z = _require_int(z, 'z')
            if not isinstance(mode, str):
                raise EncounterPermissionError('Move proposals require string `mode`.')
            with self._state_lock:
                command = self._command_from_move_proposal(controller_id, x=x, y=y, z=z, mode=mode)
                self._submit_input(controller_id, command)
                self._broadcast_updates()
            return
        if message_type == 'action_proposal':
            with self._state_lock:
                command = self._command_from_action_proposal(controller_id, message)
                self._submit_input(controller_id, command)
                self._broadcast_updates()
            return
        if message_type == 'travel_plan_route':
            destination_location_id = message.get('destination_location_id')
            q = message.get('q')
            r = message.get('r')
            if destination_location_id is not None and not isinstance(destination_location_id, str):
                raise EncounterPermissionError('Travel route planning requires string `destination_location_id` when present.')
            destination_coord = None
            if q is not None or r is not None:
                destination_coord = HexCoord(_require_int(q, 'q'), _require_int(r, 'r'))
            with self._state_lock:
                if not hasattr(self.session, 'travel_plan_route'):
                    raise EncounterPermissionError('This session does not support travel route planning.')
                self.session.travel_plan_route(controller_id, destination_coord=destination_coord, destination_location_id=destination_location_id)
                self._broadcast_updates()
            return
        if message_type == 'travel_set_pace':
            raw_pace = message.get('pace')
            if not isinstance(raw_pace, str):
                raise EncounterPermissionError('Travel pace changes require string `pace`.')
            with self._state_lock:
                if not hasattr(self.session, 'travel_set_pace'):
                    raise EncounterPermissionError('This session does not support travel pace changes.')
                self.session.travel_set_pace(controller_id, TravelPace(raw_pace.lower()))
                self._broadcast_updates()
            return
        if message_type == 'travel_advance':
            steps = message.get('steps', 1)
            with self._state_lock:
                if not hasattr(self.session, 'travel_advance'):
                    raise EncounterPermissionError('This session does not support travel advancement.')
                self.session.travel_advance(controller_id, steps=_require_int(steps, 'steps'))
                self._broadcast_updates()
            return
        if message_type == 'travel_resume':
            with self._state_lock:
                if not hasattr(self.session, 'travel_resume'):
                    raise EncounterPermissionError('This session does not support travel resumption.')
                self.session.travel_resume(controller_id)
                self._broadcast_updates()
            return
        if message_type == 'travel_engage':
            with self._state_lock:
                if not hasattr(self.session, 'travel_engage_pending_hook'):
                    raise EncounterPermissionError('This session does not support travel hook engagement.')
                self.session.travel_engage_pending_hook(controller_id)
                self._broadcast_updates()
            return
        raise EncounterPermissionError(f'Unknown web message type: {message_type!r}.')

    def _command_from_action_proposal(self, controller_id: str, message: dict[str, object]) -> str:
        active_actor_id = self.session.state.active_actor_id
        if active_actor_id is None:
            raise EncounterPermissionError('There is no active actor to act with.')
        owner = self._control_runtime().controller_for_actor(active_actor_id)
        if owner != controller_id:
            raise EncounterPermissionError('Only the owner of the active actor may submit an action proposal.')
        group_id = message.get('group_id')
        option_id = message.get('option_id')
        target_actor_id = message.get('target_actor_id')
        x = message.get('x')
        y = message.get('y')
        z = message.get('z')
        if not isinstance(group_id, str) or not isinstance(option_id, str):
            raise EncounterPermissionError('Action proposals require string `group_id` and `option_id`.')
        if target_actor_id is not None and not isinstance(target_actor_id, str):
            raise EncounterPermissionError('`target_actor_id` must be a string when present.')
        if x is not None:
            x = _require_int(x, 'x')
        if y is not None:
            y = _require_int(y, 'y')
        if z is not None:
            z = _require_int(z, 'z')
        actor = self.session.state.actors[active_actor_id]
        if group_id == 'attacks':
            if target_actor_id is None:
                raise EncounterPermissionError('Attack proposals require `target_actor_id`.')
            return f'/attack {active_actor_id} {option_id} {target_actor_id}'
        if group_id == 'actions':
            if option_id in {'dash', 'disengage', 'dodge', 'hide', 'search', 'study', 'utilize'}:
                return f'/{option_id} {active_actor_id}'
            if option_id == 'endturn':
                return f'/endturn {active_actor_id}'
            if option_id == 'help':
                if target_actor_id is None:
                    raise EncounterPermissionError('Help proposals require `target_actor_id`.')
                return f'/help {active_actor_id} {target_actor_id}'
            if option_id == 'grapple':
                if target_actor_id is None:
                    raise EncounterPermissionError('Grapple proposals require `target_actor_id`.')
                return f'/grapple {active_actor_id} {target_actor_id}'
            if option_id == 'shove':
                outcome = message.get('shove_outcome')
                if target_actor_id is None or not isinstance(outcome, str):
                    raise EncounterPermissionError('Shove proposals require `target_actor_id` and string `shove_outcome`.')
                return f'/shove {active_actor_id} {target_actor_id} {outcome}'
            raise EncounterPermissionError(f'Unsupported action proposal option: {option_id}.')
        if group_id == 'movement':
            if option_id != 'stand':
                raise EncounterPermissionError(f'Unsupported movement proposal option: {option_id}.')
            return f'/stand {active_actor_id}'
        if option_id in actor.spells:
            if target_actor_id is not None:
                return f'/cast {active_actor_id} {option_id} {target_actor_id}'
            if x is not None and y is not None:
                return f'/cast {active_actor_id} {option_id} {x} {y}' + (f' {z}' if z is not None else '')
            return f'/cast {active_actor_id} {option_id}'
        if option_id in actor.capabilities:
            slash = '/use' if actor.capabilities[option_id].kind.value == 'item' else '/feature'
            if target_actor_id is not None:
                return f'{slash} {active_actor_id} {option_id} {target_actor_id}'
            if x is not None and y is not None:
                return f'{slash} {active_actor_id} {option_id} {x} {y}' + (f' {z}' if z is not None else '')
            return f'{slash} {active_actor_id} {option_id}'
        raise EncounterPermissionError(f'Unsupported action proposal group: {group_id}.')

    def _command_from_move_proposal(self, controller_id: str, *, x: int, y: int, z: int | None, mode: str) -> str:
        active_actor_id = self.session.state.active_actor_id
        if active_actor_id is None:
            raise EncounterPermissionError('There is no active actor to move.')
        owner = self._control_runtime().controller_for_actor(active_actor_id)
        if owner != controller_id:
            raise EncounterPermissionError('Only the owner of the active actor may submit a move proposal.')
        if mode == 'walk':
            command = f'/move {active_actor_id} {x} {y}'
            if z is not None:
                command += f' {z}'
            return command
        if mode == 'elevation':
            command = f'/move {active_actor_id} {x} {y}'
            if z is not None:
                command += f' {z}'
            command += ' --allow-elevation'
            return command
        if mode == 'climb':
            command = f'/climb {active_actor_id} {x} {y}'
            if z is not None:
                command += f' {z}'
            return command
        if mode == 'fly':
            if z is None:
                raise EncounterPermissionError('Fly proposals require an explicit `z` destination.')
            return f'/fly {active_actor_id} {x} {y} {z}'
        raise EncounterPermissionError(f'Unknown move proposal mode: {mode}.')

    def _broadcast_updates(self) -> None:
        for controller_id in list(self._clients):
            self._send_view(controller_id)
        for controller_id in list(self._clients):
            self._send_prompt_if_any(controller_id)

    def _control_runtime(self):
        if hasattr(self.session, 'encounter_session'):
            return self.session.encounter_session.control_runtime
        return self.session.control_runtime

    def _prompt_for_response(self, controller_id: str):
        if hasattr(self.session, 'encounter_session'):
            return self.session.encounter_session.prompt_for_controller(controller_id)
        return self.session.prompt_for_controller(controller_id)

    def _normalize_prompt_response(self, prompt, option_ids: object):
        if prompt is None:
            raise EncounterPermissionError('There is no prompt available for this controller.')
        prompt_kind = getattr(prompt, 'prompt_kind', None)
        if not isinstance(prompt_kind, str) or not prompt_kind:
            raise EncounterPermissionError('The active prompt is missing a prompt kind.')
        if prompt_kind == 'reaction':
            if option_ids is not None and not isinstance(option_ids, (str, list)):
                raise EncounterPermissionError('Reaction prompt responses require `option_id` to be a string, `option_ids` to be a list of strings, or null.')
            if isinstance(option_ids, list) and not all(isinstance(item, str) for item in option_ids):
                raise EncounterPermissionError('Reaction prompt option ids must be strings.')
            return option_ids
        if prompt_kind == 'timing-order':
            if option_ids is None:
                return None
            if isinstance(option_ids, str):
                return option_ids
            if not isinstance(option_ids, list):
                raise EncounterPermissionError('Timing-order prompt responses require a string `option_id`, a single-entry `option_ids` list, or null.')
            if not all(isinstance(item, str) for item in option_ids):
                raise EncounterPermissionError('Timing-order prompt option ids must be strings.')
            if len(option_ids) > 1:
                raise EncounterPermissionError('Timing-order prompt responses may choose only one option.')
            return option_ids[0] if option_ids else None
        if option_ids is not None and not isinstance(option_ids, (str, list)):
            raise EncounterPermissionError('Prompt responses require `option_id` to be a string, `option_ids` to be a list of strings, or null.')
        if isinstance(option_ids, list) and not all(isinstance(item, str) for item in option_ids):
            raise EncounterPermissionError('Prompt option ids must be strings.')
        return option_ids

    def _submit_input(self, controller_id: str, text: str):
        if hasattr(self.session, 'handle_input'):
            result = self.session.handle_input(controller_id, text)
        else:
            result = self.session.execute_for_controller(controller_id, text)
        if hasattr(self.session, 'pump_llm_players'):
            self.session.pump_llm_players()
        return result

    def _validate_controller(self, controller_id: str):
        if hasattr(self.session, 'validate_controller'):
            return self.session.validate_controller(controller_id)
        return self.session.control_runtime.validate_controller(controller_id)

    def _project_view(self, controller_id: str):
        if hasattr(self.session, 'story_state') and hasattr(self.session, 'encounter_session'):
            return project_story_session_view(self.session, controller_id, session_id=self.session_id)
        if hasattr(self.session, 'control_runtime') and hasattr(self.session, 'state'):
            return project_encounter_session_view(self.session, controller_id, session_id=self.session_id)
        story_session = getattr(self.session, 'story_session', None)
        if hasattr(self.session, 'view_for_controller') and hasattr(self.session, 'validate_controller') and not hasattr(self.session, 'state'):
            if story_session is None or getattr(self.session, '_completion_state', None) is not None:
                return project_manual_demo_wrapper_view(self.session, controller_id, session_id=self.session_id)
        if story_session is not None:
            return project_story_session_view(story_session, controller_id, session_id=self.session_id)
        raise EncounterPermissionError(f'Unsupported web session type: {type(self.session).__name__}.')

    def _send_view(self, controller_id: str) -> None:
        payload = self._project_view(controller_id)
        self._send_to_controller(controller_id, {'type': 'view', 'view': payload})

    def _send_prompt_if_any(self, controller_id: str) -> None:
        prompt = self._project_prompt(controller_id)
        if prompt is None:
            return
        self._send_to_controller(controller_id, {'type': 'prompt', 'prompt': to_jsonable(prompt)})

    def _send_command_echo(self, controller_id: str, text: str) -> None:
        entry = self._command_echo_entry(controller_id, text)
        if entry is None:
            return
        self._send_to_controller(controller_id, {'type': 'echo', 'entry': entry})

    def _command_echo_entry(self, controller_id: str, text: str) -> dict[str, object] | None:
        stripped = text.strip()
        if not stripped:
            return None
        grant = self.controller_grants.get(controller_id)
        speaker = grant.label if grant is not None else controller_id
        lowered = stripped.lower()
        category = 'player-command'
        echoed = stripped
        if lowered == '/check':
            category = 'check'
            echoed = 'Resolving the pending check through the rules engine.'
        elif lowered.startswith('/say ') or lowered.startswith('/story ') or lowered.startswith('/do ') or lowered.startswith('/improvise '):
            category = 'player'
            echoed = stripped.split(maxsplit=1)[1].strip()
        elif not lowered.startswith('/'):
            category = 'player'
            echoed = stripped
        return {
            'entry_id': f'echo:{time.time_ns()}:{controller_id}',
            'speaker': speaker,
            'text': echoed,
            'category': category,
            'visibility': 'public',
        }

    def _project_prompt(self, controller_id: str):
        projected_view = self._project_view(controller_id)
        return projected_view.prompt

    def _emit_llm_feedback(self, controller_id: str, kind: str, text: str) -> None:
        if not text.strip():
            return
        payload = {
            'type': 'thinking' if kind == 'thinking' else 'info',
            'kind': kind,
            'controller_id': controller_id,
            'message': text,
        }
        self._send_to_controller(controller_id, payload)

    def _send_to_controller(self, controller_id: str, payload: dict[str, object]) -> None:
        client = self._clients.get(controller_id)
        if client is None:
            return
        try:
            client.send(payload)
        except Exception:
            self._unregister_client(controller_id)

    def _log(self, message: str) -> None:
        print(f'[web] {message}', flush=True)


def _require_int(value: object, field_name: str) -> int:
    if not isinstance(value, int):
        raise EncounterPermissionError(f'`{field_name}` must be an integer.')
    return value


def _allocate_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.bind((host, 0))
        return int(probe.getsockname()[1])



def _portal_query_path(controller_id: str) -> str:
    return f'/?portal={controller_id}&autoconnect=1'






