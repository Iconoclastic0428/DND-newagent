from __future__ import annotations

from http import client as http_client
import unittest
from unittest.mock import patch
from urllib import error

from dm_agent.client import LLMHttpTransport


class _ResponseContext:
    def __init__(self, *, payload: bytes | None = None, exc: Exception | None = None) -> None:
        self.payload = payload
        self.exc = exc

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        if self.exc is not None:
            raise self.exc
        assert self.payload is not None
        return self.payload


class LLMHttpTransportTests(unittest.TestCase):
    def test_default_timeout_supports_slow_deepseek_json_reasoning_calls(self) -> None:
        transport = LLMHttpTransport()

        self.assertGreaterEqual(transport.timeout_seconds, 300.0)
        self.assertGreaterEqual(transport.stream_timeout_seconds, 300.0)

    def test_rejects_non_positive_timeouts(self) -> None:
        with self.assertRaises(ValueError):
            LLMHttpTransport(timeout_seconds=0)
        with self.assertRaises(ValueError):
            LLMHttpTransport(stream_timeout_seconds=0)

    def test_post_retries_incomplete_chunked_response_read(self) -> None:
        responses = [
            _ResponseContext(exc=http_client.IncompleteRead(b'')),
            _ResponseContext(payload=b'{"ok": true}'),
        ]
        calls: list[float] = []

        def _urlopen(_request, *, timeout):
            calls.append(timeout)
            return responses.pop(0)

        transport = LLMHttpTransport(timeout_seconds=7)

        with patch('dm_agent.client.request.urlopen', side_effect=_urlopen):
            result = transport.post(url='https://example.invalid/v1/chat/completions', headers={}, payload={'model': 'test'})

        self.assertEqual(result, {'ok': True})
        self.assertEqual(calls, [7, 7])

    def test_post_retries_transient_url_error(self) -> None:
        responses = [
            error.URLError(ConnectionResetError(10054, 'forcibly closed by remote host')),
            _ResponseContext(payload=b'{"ok": true}'),
        ]
        calls: list[float] = []

        def _urlopen(_request, *, timeout):
            calls.append(timeout)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        transport = LLMHttpTransport(timeout_seconds=7)

        with patch('dm_agent.client.request.urlopen', side_effect=_urlopen):
            result = transport.post(url='https://example.invalid/v1/chat/completions', headers={}, payload={'model': 'test'})

        self.assertEqual(result, {'ok': True})
        self.assertEqual(calls, [7, 7])

    def test_default_post_retry_budget_covers_several_transient_url_errors(self) -> None:
        responses = [
            error.URLError(TimeoutError(10060, 'connection timed out')),
            error.URLError(TimeoutError(10060, 'connection timed out')),
            error.URLError(ConnectionResetError(10054, 'forcibly closed by remote host')),
            _ResponseContext(payload=b'{"ok": true}'),
        ]
        calls: list[float] = []

        def _urlopen(_request, *, timeout):
            calls.append(timeout)
            response = responses.pop(0)
            if isinstance(response, Exception):
                raise response
            return response

        transport = LLMHttpTransport(timeout_seconds=7)

        with patch('dm_agent.client.request.urlopen', side_effect=_urlopen):
            result = transport.post(url='https://example.invalid/v1/chat/completions', headers={}, payload={'model': 'test'})

        self.assertEqual(result, {'ok': True})
        self.assertEqual(calls, [7, 7, 7, 7])


if __name__ == '__main__':
    unittest.main()
