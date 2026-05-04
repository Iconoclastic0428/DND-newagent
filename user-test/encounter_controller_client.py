from __future__ import annotations

import argparse
import json
from pathlib import Path
import socket
import sys
import threading
import time

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


class ControllerClient:
    def __init__(self, *, controller_id: str, host: str, port: int) -> None:
        self.controller_id = controller_id
        self.host = host
        self.port = port
        self.socket = socket.create_connection((host, port))
        self.reader = self.socket.makefile('r', encoding='utf-8')
        self._send_lock = threading.Lock()
        self._stop_event = threading.Event()
        self._pending_prompt = threading.Event()
        self._prompt_kind: str | None = None
        self._prompt_options: list[str] = []
        self._receiver_thread = threading.Thread(target=self._receive_loop, daemon=True)
        self._thinking_open = False

    def start(self) -> None:
        self._send({'type': 'hello', 'controller_id': self.controller_id})
        self._receiver_thread.start()

    def close(self) -> None:
        self._stop_event.set()
        try:
            self.socket.close()
        except OSError:
            pass
        try:
            self.reader.close()
        except OSError:
            pass

    def send_command(self, command: str) -> None:
        self._send({'type': 'command', 'command': command})

    def send_reaction(self, option_ids: list[str] | None) -> None:
        self._send({'type': 'reaction', 'option_ids': option_ids})

    def has_pending_prompt(self) -> bool:
        return self._pending_prompt.is_set()

    def is_reaction_prompt(self) -> bool:
        return self._prompt_kind == 'reaction'

    def resolve_reaction_input(self, raw_input: str) -> list[str] | None:
        token = raw_input.strip()
        if token in {'', '0'} or token.lower() == 'decline':
            return None
        parts = [part.strip() for part in token.split(',') if part.strip()]
        resolved: list[str] = []
        for part in parts:
            if part.isdigit():
                offset = int(part) - 1
                if 0 <= offset < len(self._prompt_options):
                    resolved.append(self._prompt_options[offset])
                    continue
            resolved.append(part)
        return resolved or None

    def _send(self, payload: dict) -> None:
        data = (json.dumps(payload) + '\n').encode('utf-8')
        with self._send_lock:
            self.socket.sendall(data)

    def _receive_loop(self) -> None:
        try:
            for line in self.reader:
                if self._stop_event.is_set():
                    return
                if not line.strip():
                    continue
                message = json.loads(line)
                self._handle_message(message)
        except OSError:
            return

    def _handle_message(self, message: dict) -> None:
        message_type = message.get('type')
        if message_type != 'thinking' and self._thinking_open:
            print()
            self._thinking_open = False
        if message_type == 'view':
            text = message['text']
            if 'Reaction prompt:' not in text and 'Pending check:' not in text:
                self._pending_prompt.clear()
                self._prompt_options = []
                self._prompt_kind = None
            print(f'[{self.controller_id} update]')
            print(text)
            print()
            return
        if message_type == 'prompt':
            self._pending_prompt.set()
            self._prompt_kind = message.get('prompt_kind', 'reaction')
            self._prompt_options = [option['option_id'] for option in message.get('options', [])]
            prompt_kind = self._prompt_kind or 'prompt'
            print(f'[{self.controller_id} prompt:{prompt_kind}] {message["text"]}')
            if self._prompt_kind == 'story-check':
                print('Type `/check` to resolve the requested check through the rules engine.')
                print()
                return
            for index, option in enumerate(message.get('options', []), start=1):
                print(f'  {index}. {option["label"]} [{option["option_id"]}] - {option["detail"]}')
            print('  0. Decline all shown options')
            print('Type a number, a comma-separated list like `1,2`, an option id, or `decline`.')
            print()
            return
        if message_type == 'info':
            print(f'[info] {message["message"]}')
            return
        if message_type == 'thinking':
            if not self._thinking_open:
                print('[thinking] ', end='', flush=True)
                self._thinking_open = True
            print(message['message'], end='', flush=True)
            return
        if message_type == 'error':
            print(f'[error] {message["message"]}')
            return
        print(f'[message] {message}')


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Interactive encounter/story controller client.')
    parser.add_argument('--controller-id', required=True, help='Controller id to connect as.')
    parser.add_argument('--host', default='127.0.0.1', help='Orchestrator host.')
    parser.add_argument('--port', type=int, default=8765, help='Orchestrator port.')
    parser.add_argument('--command', action='append', default=[], help='Execute a command or prompt response non-interactively.')
    parser.add_argument('--commands-file', type=Path, help='Read commands from a file, one per line.')
    return parser.parse_args()


def _handle_input(client: ControllerClient, line: str) -> None:
    if line.lower().startswith('reply '):
        choice = line.split(None, 1)[1].strip()
        option_ids = client.resolve_reaction_input(choice)
        client.send_reaction(option_ids)
        return
    if client.has_pending_prompt() and client.is_reaction_prompt() and not line.startswith('/'):
        option_ids = client.resolve_reaction_input(line)
        client.send_reaction(option_ids)
        return
    client.send_command(line)


def main() -> int:
    args = parse_args()
    client = ControllerClient(controller_id=args.controller_id, host=args.host, port=args.port)
    client.start()
    commands = list(args.command)
    if args.commands_file is not None:
        commands.extend(args.commands_file.read_text(encoding='utf-8').splitlines())
    print(
        f'Connected as {args.controller_id}. The full story demo starts in character creation. Use `/create ...` during setup, then natural-language story input or slash commands after the campaign begins. '
        'If a reaction prompt appears, type a number, comma-separated numbers, option ids, or `decline`. '
        'If a story-check prompt appears, type `/check`.'
    )
    try:
        if commands:
            for line in commands:
                line = line.strip()
                if not line:
                    continue
                _handle_input(client, line)
                time.sleep(0.4)
            time.sleep(1.0)
            return 0
        while True:
            try:
                line = input('> ').strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return 0
            if not line:
                continue
            if line.lower() in {'exit', 'quit'}:
                return 0
            _handle_input(client, line)
    finally:
        client.close()


if __name__ == '__main__':
    raise SystemExit(main())
