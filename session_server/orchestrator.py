from __future__ import annotations

import json
import socket
import threading
import time
from dataclasses import dataclass, field

from player_interface import present_encounter_snapshot
from session_server.bootstrap import build_default_encounter_session
from session_server.encounter_projection import projection_to_payload
from session_server.encounter_session import EncounterSession
from shared_types.errors import EncounterPermissionError


@dataclass
class ConnectedController:
    controller_id: str
    socket: socket.socket
    send_lock: threading.Lock = field(default_factory=threading.Lock)

    def send(self, payload: dict) -> None:
        data = (json.dumps(payload) + '\n').encode('utf-8')
        with self.send_lock:
            self.socket.sendall(data)

    def close(self) -> None:
        try:
            self.socket.close()
        except OSError:
            pass


class EncounterOrchestratorServer:
    def __init__(
        self,
        *,
        session: EncounterSession,
        host: str = '127.0.0.1',
        port: int = 8765,
        auto_start: bool = True,
    ) -> None:
        self.session = session
        self.host = host
        self.port = port
        self.auto_start = auto_start
        self._server_socket: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._client_threads: set[threading.Thread] = set()
        self._stop_event = threading.Event()
        self._state_lock = threading.RLock()
        self._clients: dict[str, ConnectedController] = {}

    @classmethod
    def build_default(cls, *, host: str = '127.0.0.1', port: int = 8765, auto_start: bool = True):
        return cls(session=build_default_encounter_session(), host=host, port=port, auto_start=auto_start)

    def start(self) -> None:
        if self._server_socket is not None:
            raise RuntimeError('Server is already started.')
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((self.host, self.port))
        server_socket.listen()
        server_socket.settimeout(0.5)
        self._server_socket = server_socket
        self.port = server_socket.getsockname()[1]
        if self.auto_start:
            with self._state_lock:
                self.session.system_execute('/encounter start')
        self._accept_thread = threading.Thread(target=self._accept_loop, name='encounter-orchestrator-accept', daemon=True)
        self._accept_thread.start()
        self._log(f'Server listening on {self.host}:{self.port}')
        self._broadcast_updates()

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
        if self._server_socket is not None:
            try:
                self._server_socket.close()
            except OSError:
                pass
            self._server_socket = None
        with self._state_lock:
            clients = list(self._clients.values())
            self._clients.clear()
        for client in clients:
            client.close()
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=1)
        for thread in list(self._client_threads):
            thread.join(timeout=1)

    def _accept_loop(self) -> None:
        assert self._server_socket is not None
        while not self._stop_event.is_set():
            try:
                client_socket, _ = self._server_socket.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            thread = threading.Thread(target=self._handle_client, args=(client_socket,), daemon=True)
            self._client_threads.add(thread)
            thread.start()

    def _handle_client(self, client_socket: socket.socket) -> None:
        controller_id: str | None = None
        registered_client: ConnectedController | None = None
        reader = client_socket.makefile('r', encoding='utf-8')
        try:
            hello_line = reader.readline()
            if not hello_line:
                return
            hello = json.loads(hello_line)
            if hello.get('type') != 'hello' or not isinstance(hello.get('controller_id'), str):
                self._send_raw(client_socket, {'type': 'error', 'message': 'Expected hello message with controller_id.'})
                return
            controller_id = hello['controller_id']
            registered_client = self._register_client(controller_id, client_socket)
            self._send_to_controller(controller_id, {'type': 'info', 'message': f'Connected as {controller_id}.'})
            self._send_view(controller_id)
            self._send_prompt_if_any(controller_id)
            for line in reader:
                if self._stop_event.is_set():
                    return
                if not line.strip():
                    continue
                try:
                    message = json.loads(line)
                    self._handle_message(controller_id, message)
                except Exception as exc:
                    self._send_to_controller(controller_id, {'type': 'error', 'message': str(exc)})
        except (ConnectionResetError, OSError):
            return
        finally:
            reader.close()
            if controller_id is not None:
                self._unregister_client(controller_id, expected_client=registered_client)
            try:
                client_socket.close()
            except OSError:
                pass

    def _handle_message(self, controller_id: str, message: dict) -> None:
        message_type = message.get('type')
        if message_type == 'command':
            command = message.get('command')
            if not isinstance(command, str):
                raise EncounterPermissionError('Command messages require a string `command`.')
            with self._state_lock:
                self.session.execute_for_controller(controller_id, command)
                self._log(f'{controller_id}> {command}')
                self._broadcast_updates()
            return
        if message_type == 'reaction':
            option_ids = message.get('option_ids', message.get('option_id'))
            if option_ids is not None and not isinstance(option_ids, (str, list)):
                raise EncounterPermissionError('Reaction messages require `option_id` to be a string, `option_ids` to be a list of strings, or null.')
            if isinstance(option_ids, list) and not all(isinstance(item, str) for item in option_ids):
                raise EncounterPermissionError('Reaction `option_ids` entries must all be strings.')
            with self._state_lock:
                self.session.respond_to_prompt(controller_id, option_ids)
                if isinstance(option_ids, list):
                    choice_text = ','.join(option_ids) if option_ids else 'decline'
                else:
                    choice_text = option_ids or 'decline'
                self._log(f'{controller_id} reacted with {choice_text}')
                self._broadcast_updates()
            return
        raise EncounterPermissionError(f'Unknown client message type: {message_type!r}.')

    def _register_client(self, controller_id: str, client_socket: socket.socket) -> ConnectedController:
        existing: ConnectedController | None = None
        with self._state_lock:
            self.session.control_runtime.validate_controller(controller_id)
            existing = self._clients.get(controller_id)
            if existing is not None:
                existing.close()
            client = ConnectedController(controller_id=controller_id, socket=client_socket)
            self._clients[controller_id] = client
        self._log(f'Reconnected: {controller_id}' if existing is not None else f'Connected: {controller_id}')
        return client

    def _unregister_client(self, controller_id: str, *, expected_client: ConnectedController | None = None) -> None:
        with self._state_lock:
            client = self._clients.get(controller_id)
            if client is None:
                return
            if expected_client is not None and client is not expected_client:
                return
            self._clients.pop(controller_id, None)
        client.close()
        self._log(f'Disconnected: {controller_id}')

    def _broadcast_updates(self) -> None:
        for controller_id in list(self._clients):
            self._send_view(controller_id)
        for controller_id in list(self._clients):
            self._send_prompt_if_any(controller_id)

    def _send_view(self, controller_id: str) -> None:
        view = self.session.view_for_controller(controller_id)
        payload = {
            'type': 'view',
            'controller_id': controller_id,
            'text': present_encounter_snapshot(view),
            'projection': projection_to_payload(view.projection),
        }
        self._send_to_controller(controller_id, payload)

    def _send_prompt_if_any(self, controller_id: str) -> None:
        prompt = self.session.prompt_for_controller(controller_id)
        if prompt is None:
            return
        payload = {
            'type': 'prompt',
            'prompt_id': prompt.prompt_id,
            'controller_id': controller_id,
            'trigger_type': getattr(prompt.trigger_type, 'value', prompt.trigger_type),
            'text': prompt.prompt,
            'options': [
                {
                    'option_id': option.option_id,
                    'label': option.label,
                    'detail': option.detail,
                    'actor_id': option.actor_id,
                }
                for option in prompt.options
            ],
            'recipients': [
                {
                    'controller_id': recipient.controller_id,
                    'role': recipient.role.value,
                    'label': recipient.label,
                    'actor_ids': list(recipient.actor_ids),
                }
                for recipient in prompt.recipients
            ],
        }
        self._send_to_controller(controller_id, payload)

    def _send_to_controller(self, controller_id: str, payload: dict) -> None:
        client = self._clients.get(controller_id)
        if client is None:
            return
        try:
            client.send(payload)
        except OSError:
            self._unregister_client(controller_id, expected_client=client)

    def _send_raw(self, client_socket: socket.socket, payload: dict) -> None:
        client_socket.sendall((json.dumps(payload) + '\n').encode('utf-8'))

    def _log(self, message: str) -> None:
        print(f'[system] {message}', flush=True)
