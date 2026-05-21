from __future__ import annotations

import unittest

from dm_agent.client import LLMHttpTransport


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


if __name__ == '__main__':
    unittest.main()
