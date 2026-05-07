from __future__ import annotations

from pathlib import Path
import unittest

from rules_engine.fiveetools_loader import _normalise_base_url


class FiveEToolsLoaderPathTests(unittest.TestCase):
    def test_relative_mirror_base_url_normalises_to_file_uri(self) -> None:
        expected = (Path('5etools-mirror-2.github.io').resolve().as_uri().rstrip('/') + '/')
        self.assertEqual(_normalise_base_url('5etools-mirror-2.github.io/'), expected)

    def test_http_mirror_base_url_is_left_as_url(self) -> None:
        self.assertEqual(_normalise_base_url('https://example.test/mirror'), 'https://example.test/mirror/')


if __name__ == '__main__':
    unittest.main()
