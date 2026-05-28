from __future__ import annotations

import unittest
from unittest.mock import Mock, patch

from character_creation import service as character_service
from monster_runtime import service as monster_service


class ServiceDefaultMirrorTests(unittest.TestCase):
    def test_character_creation_default_mirror_uses_kiwee(self) -> None:
        fake_catalog = object()
        fake_fetcher = object()
        fake_policy = object()

        with (
            patch.object(character_service, "load_env", return_value={}),
            patch.object(character_service, "load_catalog", return_value=fake_catalog) as load_catalog,
        ):
            kernel = character_service.build_default_kernel(
                policy=fake_policy,
                document_fetcher=fake_fetcher,
            )

        self.assertIs(kernel.catalog, fake_catalog)
        load_catalog.assert_called_once_with(
            "https://5e.kiwee.top/",
            fake_policy,
            document_fetcher=fake_fetcher,
        )

    def test_monster_runtime_default_mirror_uses_kiwee(self) -> None:
        fake_character_kernel = Mock()
        fake_character_kernel.catalog = object()
        fake_monster_catalog = object()
        fake_fetcher = object()
        fake_monster_policy = object()
        fake_character_policy = object()

        with (
            patch.object(monster_service, "load_env", return_value={}),
            patch.object(monster_service, "build_default_kernel", return_value=fake_character_kernel) as build_kernel,
            patch.object(monster_service, "load_monster_catalog", return_value=fake_monster_catalog) as load_monsters,
        ):
            runtime = monster_service.build_default_monster_runtime(
                monster_policy=fake_monster_policy,
                character_policy=fake_character_policy,
                document_fetcher=fake_fetcher,
            )

        self.assertIs(runtime.character_catalog, fake_character_kernel.catalog)
        self.assertIs(runtime.monster_catalog, fake_monster_catalog)
        build_kernel.assert_called_once_with(
            base_url="https://5e.kiwee.top/",
            policy=fake_character_policy,
            document_fetcher=fake_fetcher,
        )
        load_monsters.assert_called_once_with(
            "https://5e.kiwee.top/",
            fake_monster_policy,
            document_fetcher=fake_fetcher,
        )


if __name__ == "__main__":
    unittest.main()
