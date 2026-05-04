from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from shared_types.encounter_models import RuntimeSpellState
from shared_types.spellcasting import SpellRuntimeSupportMode, SpellRuntimeSupportProfile
from shared_types.models import slugify
from tests.xphb_level1_spells.support import EncounterLevel1SpellTestCase


REPO_ROOT = Path(__file__).resolve().parents[2]
LEVEL2_ROOT = REPO_ROOT / 'content' / 'xphb' / 'spells' / 'level-2'
MIRROR_PATH = Path(r'D:/5etools-mirror-2.github.io/data/spells/spells-xphb.json')


def load_local_spell_executor(slug: str):
    executor_path = LEVEL2_ROOT / slug / 'executor.py'
    spec = importlib.util.spec_from_file_location(f'xphb_level2_{slug.replace("-", "_")}', executor_path)
    if spec is None or spec.loader is None:
        raise FileNotFoundError(executor_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_local_spell_record(name: str, *, source: str = 'XPHB') -> dict[str, object]:
    for spell in json.loads(MIRROR_PATH.read_text(encoding='utf-8'))['spell']:
        if not isinstance(spell, dict):
            continue
        if spell.get('source') != source:
            continue
        if spell.get('ENG_name') == name or spell.get('name') == name:
            return spell
    raise AssertionError(f'Could not locate local level-2 spell record for {name!r}.')


def build_local_spell_capability(slug: str, *, name: str, source: str = 'XPHB'):
    module = load_local_spell_executor(slug)
    builder = getattr(module, 'build_capability_definition')
    raw_spell = load_local_spell_record(name, source=source)
    return builder(raw_spell)


def inject_local_spell(session, *, actor_id: str, slug: str, name: str, remaining_uses: int | None = None) -> None:
    capability = build_local_spell_capability(slug, name=name)
    if capability is None:
        raise AssertionError(f'Local spell {name!r} is blocked and cannot be injected.')
    spell_id = slugify(name)
    effect = capability.effect
    concentration = bool(getattr(effect, 'concentration', False) or getattr(getattr(effect, 'active_effect', None), 'concentration', False))
    session.state.actors[actor_id].spells[spell_id] = RuntimeSpellState(
        option_id=spell_id,
        name=name,
        source='XPHB',
        action_cost=capability.action_cost,
        range_ft=capability.targeting.range_ft,
        remaining_uses=remaining_uses,
        concentration=concentration,
        level=2,
        capability=capability,
        runtime_support=SpellRuntimeSupportProfile(support_mode=SpellRuntimeSupportMode.DETERMINISTIC_CAPABILITY, content_id=f'XPHB:spell:{spell_id}', implementation_path=f'content/xphb/spells/level-2/{slug}'),
    )
    return spell_id


class EncounterLevel2SpellTestCase(EncounterLevel1SpellTestCase):
    """Shared harness for Tier-2 level-2 XPHB spell tests."""
    pass
