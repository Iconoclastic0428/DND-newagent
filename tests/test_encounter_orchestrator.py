from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import socket
import time
import unittest

from session_server import EncounterOrchestratorServer


CLIENT_PATH = Path('user-test/encounter_controller_client.py').resolve()
CLIENT_SPEC = importlib.util.spec_from_file_location('encounter_controller_client', CLIENT_PATH)
assert CLIENT_SPEC is not None and CLIENT_SPEC.loader is not None
CLIENT_MODULE = importlib.util.module_from_spec(CLIENT_SPEC)
CLIENT_SPEC.loader.exec_module(CLIENT_MODULE)
ControllerClient = CLIENT_MODULE.ControllerClient


class JsonLineClient:
    def __init__(self, *, host: str, port: int, controller_id: str) -> None:
        self.socket = socket.create_connection((host, port), timeout=5)
        self.socket.settimeout(5)
        self.reader = self.socket.makefile('r', encoding='utf-8')
        self.send({'type': 'hello', 'controller_id': controller_id})

    def send(self, payload: dict) -> None:
        self.socket.sendall((json.dumps(payload) + '\n').encode('utf-8'))

    def send_command(self, command: str) -> None:
        self.send({'type': 'command', 'command': command})

    def read_until(self, message_type: str, *, timeout: float = 5.0) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            line = self.reader.readline()
            if not line:
                raise AssertionError('Connection closed before expected message arrived.')
            message = json.loads(line)
            if message.get('type') == message_type:
                return message
        raise AssertionError(f'Timed out waiting for message type {message_type!r}.')

    def close(self) -> None:
        try:
            self.reader.close()
        finally:
            self.socket.close()


class EncounterOrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.server = EncounterOrchestratorServer.build_default(host='127.0.0.1', port=0, auto_start=True)
        self.server.start()

    def tearDown(self) -> None:
        self.server.shutdown()

    def _connect(self, controller_id: str) -> JsonLineClient:
        client = JsonLineClient(host='127.0.0.1', port=self.server.port, controller_id=controller_id)
        client.read_until('info')
        client.read_until('view')
        return client

    def test_player_command_for_monster_is_rejected_over_socket(self) -> None:
        player = self._connect('player-1-controller')
        try:
            player.send_command('/dash monster-skeleton-1')
            error = player.read_until('error')
            self.assertIn('does not own actor', error['message'])
        finally:
            player.close()

    def test_dm_move_broadcasts_filtered_updates(self) -> None:
        dm = self._connect('dm')
        player = self._connect('player-1-controller')
        try:
            dm.send_command('/move monster-skeleton-1 1 0')
            dm_view = dm.read_until('view')
            player_view = player.read_until('view')
            self.assertIn('monster-skeleton-1: Skeleton [monster] HP 13/13', dm_view['text'])
            self.assertIn('monster-skeleton-1: Skeleton [monster] Pos (1,0,0); Status active; Turn active', player_view['text'])
            self.assertNotIn('monster-skeleton-1: Skeleton [monster] HP 13/13', player_view['text'])
        finally:
            dm.close()
            player.close()

    def test_view_payload_contains_structured_projection_with_view_separation(self) -> None:
        dm = self._connect('dm')
        player = self._connect('player-1-controller')
        try:
            dm.send_command('/move monster-skeleton-1 1 0')
            dm_view = dm.read_until('view')
            player_view = player.read_until('view')
            self.assertIn('projection', dm_view)
            self.assertIn('projection', player_view)
            monster_dm = next(actor for actor in dm_view['projection']['actors'] if actor['public']['actor_id'] == 'monster-skeleton-1')
            monster_player = next(actor for actor in player_view['projection']['actors'] if actor['public']['actor_id'] == 'monster-skeleton-1')
            self.assertIsNotNone(monster_dm['private_state'])
            self.assertIsNone(monster_player['private_state'])
            self.assertEqual(monster_player['public']['position'], {'x': 1, 'y': 0, 'z': 0})
        finally:
            dm.close()
            player.close()

    def test_reconnect_replaces_existing_controller_connection(self) -> None:
        first_dm = self._connect('dm')
        replacement_dm = None
        try:
            replacement_dm = self._connect('dm')
            replacement_dm.send_command('/move monster-skeleton-1 1 0')
            replacement_view = replacement_dm.read_until('view')
            self.assertIn('monster-skeleton-1: Skeleton [monster] HP 13/13; Temp 0; AC 14; Pos (1,0,0)', replacement_view['text'])
        finally:
            if replacement_dm is not None:
                replacement_dm.close()
            first_dm.close()

    def test_reconnect_replays_pending_prompt_to_replacement_controller(self) -> None:
        dm = self._connect('dm')
        player = self._connect('player-1-controller')
        replacement_dm = None
        try:
            dm.send_command('/move monster-skeleton-1 1 0')
            dm.read_until('view')
            player.read_until('view')
            dm.send_command('/endturn monster-skeleton-1')
            dm.read_until('view')
            player.read_until('view')
            dm.send_command('/endturn monster-mage-1')
            dm.read_until('view')
            player.read_until('view')
            player.send_command('/move player-1 3 0')
            dm.read_until('view')
            player.read_until('view')
            prompt = dm.read_until('prompt')
            self.assertEqual(prompt['controller_id'], 'dm')
            replacement_dm = JsonLineClient(host='127.0.0.1', port=self.server.port, controller_id='dm')
            replacement_dm.read_until('info')
            replacement_dm.read_until('view')
            replayed_prompt = replacement_dm.read_until('prompt')
            self.assertEqual(replayed_prompt['trigger_type'], 'leave-reach')
            self.assertEqual([recipient['controller_id'] for recipient in replayed_prompt['recipients']], ['dm'])
            self.assertTrue(all(option['actor_id'].startswith('monster-') for option in replayed_prompt['options']))
        finally:
            if replacement_dm is not None:
                replacement_dm.close()
            dm.close()
            player.close()


class EncounterControllerClientTests(unittest.TestCase):
    def test_numeric_reaction_input_maps_to_prompt_option_id(self) -> None:
        client = ControllerClient.__new__(ControllerClient)
        client._prompt_options = ['opportunity:monster-skeleton-1:shortsword', 'opportunity:monster-mage-1:dagger']
        self.assertEqual(client.resolve_reaction_input('1'), ['opportunity:monster-skeleton-1:shortsword'])
        self.assertEqual(client.resolve_reaction_input('1,2'), ['opportunity:monster-skeleton-1:shortsword', 'opportunity:monster-mage-1:dagger'])
        self.assertIsNone(client.resolve_reaction_input('0'))
        self.assertIsNone(client.resolve_reaction_input('decline'))
        self.assertEqual(client.resolve_reaction_input('opportunity:monster-skeleton-1:shortsword'), ['opportunity:monster-skeleton-1:shortsword'])


if __name__ == '__main__':
    unittest.main()
