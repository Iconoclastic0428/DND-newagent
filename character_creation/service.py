from __future__ import annotations

from shared_types.models import AbilityGenerationMode, SourcePolicy

from rules_engine.env import load_env
from rules_engine.fiveetools_loader import DocumentFetcher, load_catalog

from .kernel import CharacterCreationKernel


DEFAULT_MIRROR_BASE_URL = "5etools-mirror-2.github.io/"


def build_default_kernel(
    *,
    base_url: str | None = None,
    policy: SourcePolicy | None = None,
    document_fetcher: DocumentFetcher | None = None,
) -> CharacterCreationKernel:
    env = load_env()
    seed = env.get("DND_DETERMINISTIC_SEED", "missing-seed")
    mirror_base_url = base_url or env.get("FIVEETOOLS_MIRROR_BASE_URL", DEFAULT_MIRROR_BASE_URL)
    active_policy = policy or SourcePolicy(
        allowed_sources=frozenset({"XPHB"}),
        ability_generation_mode=AbilityGenerationMode.ROLL_OR_POINT_BUY,
        allow_homebrew=False,
        allow_class_wealth=False,
        allowed_item_sources=frozenset({"XPHB", "XDMG"}),
    )
    catalog = load_catalog(mirror_base_url, active_policy, document_fetcher=document_fetcher)
    return CharacterCreationKernel(catalog=catalog, policy=active_policy, seed=seed)


