from __future__ import annotations

from collections.abc import Mapping, Sequence
import re
from urllib.parse import urljoin

from shared_types.encounter_models import (
    AttackKind,
    AttackProfile,
    EncounterContentCatalog,
    EncounterPolicy,
    MonsterRecord,
    SpellEffectType,
    SpellOption,
    SpellRecord,
)
from shared_types.errors import ContentLoadError
from shared_types.spellcasting import SpellPerceptibilityProfile
from shared_types.models import ABILITY_ORDER, Ability, slugify

from .capability_loader import build_spell_capability_definition
from .xphb_level1_registry import spell_runtime_support_for as level1_spell_runtime_support_for
from .tier2_spell_registry import spell_runtime_support_for as tier2_spell_runtime_support_for
from .fiveetools_loader import (
    DocumentFetcher,
    _SourceMetadata,
    _canonical_name,
    _fetch_json_from_url,
    _is_homebrew,
    _is_official,
    _load_source_metadata,
    _name_aliases,
    _normalise_base_url,
)


def _runtime_support_for_spell(name: str, *, source: str):
    return level1_spell_runtime_support_for(name, source=source) or tier2_spell_runtime_support_for(name, source=source)


_ATTACK_KIND_MAP = {
    "m": AttackKind.MELEE,
    "r": AttackKind.RANGED,
    "m,r": AttackKind.MELEE_OR_RANGED,
    "r,m": AttackKind.MELEE_OR_RANGED,
}

_SPELL_MATERIAL_PROFILE_OVERRIDES = {
    ('Bless', 'XPHB'): {
        'cost_cp': 500,
        'focus_tags': ('focus-holy',),
    },
    ('Chromatic Orb', 'XPHB'): {
        'cost_cp': 5000,
        'item_keywords': ('diamond',),
    },
    ('Find Familiar', 'XPHB'): {
        'cost_cp': 1000,
        'consumed': True,
        'item_keywords': ('incense',),
    },
    ('Protection from Evil and Good', 'XPHB'): {
        'cost_cp': 2500,
        'consumed': True,
        'item_keywords': ('holy-water', 'holy water'),
    },
    ('True Strike', 'XPHB'): {
        # The material component is the same weapon selected by the spell's
        # executable capability, which validates held state, cost, and proficiency.
        'handled_by_capability': True,
    },
}


def _spell_material_profile(record: Mapping[str, object]) -> tuple[int | None, bool, tuple[str, ...], tuple[str, ...]]:
    name = _canonical_name(record)
    source = str(record.get('source', '')).upper()
    override = _SPELL_MATERIAL_PROFILE_OVERRIDES.get((name, source), {})
    if override.get('handled_by_capability'):
        return None, False, (), ()
    cost_cp = None
    consumed = False
    raw_components = record.get('components')
    if isinstance(raw_components, Mapping):
        raw_material = raw_components.get('m')
        if isinstance(raw_material, Mapping):
            raw_cost = raw_material.get('cost')
            if isinstance(raw_cost, int) and raw_cost > 0:
                cost_cp = raw_cost
            consumed = bool(raw_material.get('consume'))
    if override.get('cost_cp') is not None:
        cost_cp = int(override['cost_cp'])
    if override.get('consumed') is not None:
        consumed = bool(override['consumed'])
    item_keywords = tuple(str(value) for value in override.get('item_keywords', ()))
    focus_tags = tuple(str(value) for value in override.get('focus_tags', ()))
    return cost_cp, consumed, item_keywords, focus_tags


_DAMAGE_TYPE_PATTERN = re.compile(r"([A-Za-z\u4e00-\u9fff]+)\u4f24\u5bb3")
_SPELL_TAG_PATTERN = re.compile(r"\{@spell\s+([^|}]+)\|([^}|]+)[^}]*\}")
_DAMAGE_PATTERN = re.compile(r"\{@damage\s+(\d+)d(\d+)(?:\s*([+-])\s*(\d+))?\}")
_HIT_PATTERN = re.compile(r"\{@hit\s+([+-]?\d+)\}")
_REACH_PATTERN = re.compile(r"\u89e6\u53ca\s*(\d+)\s*\u5c3a")
_RANGE_PATTERN = re.compile(r"\u5c04\u7a0b\s*(\d+)(?:\s*/\s*(\d+))?\s*\u5c3a")
_DAILY_USE_PATTERN = re.compile(r"(\d+)")
_SPELL_DC_PATTERN = re.compile(r"\{@dc\s+(\d+)\}")


def _record_id_for_name_source(name: str, source: str, existing_ids: set[str]) -> str:
    base = slugify(name)
    if base not in existing_ids:
        return base
    candidate = f"{base}-{source.lower()}"
    if candidate not in existing_ids:
        return candidate
    suffix = 2
    while True:
        candidate = f"{base}-{source.lower()}-{suffix}"
        if candidate not in existing_ids:
            return candidate
        suffix += 1


def _monster_token_image_path(record: Mapping[str, object], *, name: str, source: str) -> str | None:
    if record.get("hasToken") is not True:
        return None
    return f"img/bestiary/tokens/{source}/{name}.webp"


def _source_metadata_for(source: str, source_metadata: Mapping[str, _SourceMetadata]) -> _SourceMetadata:
    return source_metadata.get(source, _SourceMetadata(source=source, author="", group=""))


def _ability_scores(record: Mapping[str, object]) -> dict[Ability, int]:
    result: dict[Ability, int] = {}
    for ability in ABILITY_ORDER:
        value = record.get(ability.value.lower())
        if not isinstance(value, int):
            raise ContentLoadError(f"Monster {_canonical_name(record)} is missing ability score {ability.value}.")
        result[ability] = value
    return result


def _parse_bonus_map(raw_map: object, *, ability_keys: bool) -> dict[Ability, int] | dict[str, int]:
    result: dict[object, int] = {}
    if not isinstance(raw_map, Mapping):
        return result
    for raw_key, raw_value in raw_map.items():
        if not isinstance(raw_value, str):
            continue
        try:
            bonus = int(raw_value.replace("+", "").strip())
        except ValueError:
            continue
        if ability_keys:
            key = str(raw_key).strip().lower()
            if key not in {ability.value.lower() for ability in ABILITY_ORDER}:
                continue
            result[Ability(key.upper())] = bonus
        else:
            result[str(raw_key).strip().title()] = bonus
    return result


def _first_string(entries: object) -> str | None:
    if isinstance(entries, str) and entries.strip():
        return entries.strip()
    if isinstance(entries, Sequence) and not isinstance(entries, (str, bytes)):
        for entry in entries:
            value = _first_string(entry)
            if value:
                return value
    return None


def _parse_attack_profile(action_entry: Mapping[str, object], *, existing_ids: set[str]) -> AttackProfile | None:
    text = _first_string(action_entry.get("entries"))
    if not text or "{@hit" not in text or "{@damage" not in text:
        return None
    raw_kind_match = re.search(r"\{@atkr\s+([^}]+)\}", text)
    if raw_kind_match is None:
        return None
    raw_kind = raw_kind_match.group(1).replace(" ", "")
    attack_kind = _ATTACK_KIND_MAP.get(raw_kind)
    if attack_kind is None:
        return None
    hit_match = _HIT_PATTERN.search(text)
    damage_match = _DAMAGE_PATTERN.search(text)
    if hit_match is None or damage_match is None:
        return None
    to_hit_bonus = int(hit_match.group(1))
    damage_bonus = int(damage_match.group(4) or 0)
    if damage_match.group(3) == "-":
        damage_bonus *= -1
    reach_match = _REACH_PATTERN.search(text)
    range_match = _RANGE_PATTERN.search(text)
    damage_type_match = _DAMAGE_TYPE_PATTERN.search(text)
    name = _canonical_name(action_entry)
    attack_id = _record_id_for_name_source(name, "attack", existing_ids)
    existing_ids.add(attack_id)
    return AttackProfile(
        attack_id=attack_id,
        name=name,
        attack_kind=attack_kind,
        to_hit_bonus=to_hit_bonus,
        reach_ft=int(reach_match.group(1)) if reach_match else None,
        range_ft=int(range_match.group(1)) if range_match else None,
        long_range_ft=int(range_match.group(2)) if range_match and range_match.group(2) else None,
        damage_dice_count=int(damage_match.group(1)),
        damage_die_faces=int(damage_match.group(2)),
        damage_bonus=damage_bonus,
        damage_type=damage_type_match.group(1) if damage_type_match else "unknown",
    )


def _spell_effect_type(record: Mapping[str, object]) -> SpellEffectType | None:
    name = _canonical_name(record)
    if name == "Misty Step":
        return SpellEffectType.MISTY_STEP
    if name == "Shield":
        return SpellEffectType.SHIELD
    if name == "Magic Missile":
        return SpellEffectType.MAGIC_MISSILE
    return None


def _spell_time_unit(record: Mapping[str, object]) -> str:
    raw_time = record.get("time")
    if isinstance(raw_time, Sequence) and raw_time and isinstance(raw_time[0], Mapping):
        return str(raw_time[0].get("unit", "action")).strip().lower()
    return 'action'


def _spell_action_cost(record: Mapping[str, object]) -> str:
    unit = _spell_time_unit(record)
    if unit in {'bonus', 'bonus action', '\u9644\u8d60\u52a8\u4f5c'}:
        return 'bonus'
    if unit in {'reaction', '\u53cd\u5e94'}:
        return 'reaction'
    return 'action'


def _spell_casting_time_seconds(record: Mapping[str, object]) -> int:
    raw_time = record.get('time')
    if not (isinstance(raw_time, Sequence) and raw_time and isinstance(raw_time[0], Mapping)):
        return 6
    first = raw_time[0]
    number = first.get('number', 1)
    if not isinstance(number, int) or number <= 0:
        number = 1
    unit = _spell_time_unit(record)
    if unit in {'reaction', '\u53cd\u5e94'}:
        return 0
    if unit in {'bonus', 'bonus action', '\u9644\u8d60\u52a8\u4f5c', 'action', '\u52a8\u4f5c'}:
        return number * 6
    if unit in {'minute', 'minutes', '\u5206\u949f'}:
        return number * 60
    if unit in {'hour', 'hours', '\u5c0f\u65f6'}:
        return number * 60 * 60
    if unit in {'round', 'rounds', '\u8f6e'}:
        return number * 6
    return number * 6


def _spell_can_cast_as_ritual(record: Mapping[str, object]) -> bool:
    raw_meta = record.get('meta')
    if not isinstance(raw_meta, Mapping):
        return False
    return bool(raw_meta.get('ritual'))


def _spell_perceptibility(record: Mapping[str, object]) -> SpellPerceptibilityProfile:
    raw_components = record.get('components')
    has_verbal = False
    has_somatic = False
    has_material = False
    material_costly_or_consumed = False
    material_description = None
    if isinstance(raw_components, Mapping):
        has_verbal = bool(raw_components.get('v'))
        has_somatic = bool(raw_components.get('s'))
        raw_material = raw_components.get('m')
        has_material = bool(raw_material)
        if isinstance(raw_material, Mapping):
            material_costly_or_consumed = bool(raw_material.get('cost')) or bool(raw_material.get('consume'))
            text_value = raw_material.get('text')
            if isinstance(text_value, str) and text_value.strip():
                material_description = text_value.strip()
        elif isinstance(raw_material, str) and raw_material.strip():
            material_description = raw_material.strip()
    effect_visible = bool(record.get('damageInflict') or record.get('conditionInflict') or record.get('areaTags') or build_spell_capability_definition(record) is not None or _spell_effect_type(record) is not None)
    effect_audible = any(str(value).lower() == 'thunder' for value in record.get('damageInflict', []) if isinstance(record.get('damageInflict'), Sequence))
    return SpellPerceptibilityProfile(
        has_verbal_component=has_verbal,
        has_somatic_component=has_somatic,
        has_material_component=has_material,
        material_is_costly_or_consumed=material_costly_or_consumed,
        material_description=material_description,
        casting_visual_manifestation=has_somatic or has_material,
        casting_auditory_manifestation=has_verbal,
        effect_visible=effect_visible,
        effect_audible=effect_audible,
    )


def _spell_range_ft(record: Mapping[str, object]) -> int | None:
    if _canonical_name(record) == "Misty Step":
        return 30
    return None


def _spell_lookup_key(name: str, source: str) -> str:
    return f"{name.strip().casefold()}|{source.lower()}"


def _register_spell_aliases(raw_spell: Mapping[str, object], record: SpellRecord, spell_lookup: dict[str, str]) -> None:
    for alias in _name_aliases(raw_spell):
        spell_lookup[_spell_lookup_key(alias, record.source)] = record.record_id


def _resolve_spell_id(reference_name: str, source: str, spell_lookup: Mapping[str, str], spells: Mapping[str, SpellRecord]) -> str | None:
    key = _spell_lookup_key(reference_name, source)
    if key in spell_lookup:
        return spell_lookup[key]
    matches = [record_id for record_id, spell in spells.items() if slugify(spell.name) == slugify(reference_name)]
    if len(matches) == 1:
        return matches[0]
    return None


def _extract_spell_options(
    raw_monster: Mapping[str, object],
    *,
    spells: Mapping[str, SpellRecord],
    spell_lookup: Mapping[str, str],
) -> tuple[SpellOption, ...]:
    options: dict[str, SpellOption] = {}
    spellcasting_blocks = raw_monster.get("spellcasting") or []
    if not isinstance(spellcasting_blocks, Sequence) or isinstance(spellcasting_blocks, (str, bytes)):
        return ()

    def register_entries(raw_spells: object, *, uses: int | None, action_cost_override: str | None) -> None:
        if not isinstance(raw_spells, Sequence) or isinstance(raw_spells, (str, bytes)):
            return
        for entry in raw_spells:
            if not isinstance(entry, str):
                continue
            spell_match = _SPELL_TAG_PATTERN.search(entry)
            if spell_match is None:
                continue
            spell_id = _resolve_spell_id(spell_match.group(1), spell_match.group(2).upper(), spell_lookup, spells)
            if spell_id is None:
                continue
            spell = spells[spell_id]
            if spell.capability is None and spell.effect_type is None:
                continue
            option_id = slugify(spell.name)
            options[option_id] = SpellOption(
                option_id=option_id,
                spell_record_id=spell_id,
                uses_per_day=uses,
                action_cost_override=action_cost_override,
            )

    for block in spellcasting_blocks:
        if not isinstance(block, Mapping):
            continue
        display_as = str(block.get("displayAs", "")).strip().lower() or None
        register_entries(block.get("will"), uses=None, action_cost_override=display_as)
        use_map = block.get("daily")
        if isinstance(use_map, Mapping):
            for raw_uses, raw_spells in use_map.items():
                match = _DAILY_USE_PATTERN.search(str(raw_uses))
                uses = int(match.group(1)) if match else None
                register_entries(raw_spells, uses=uses, action_cost_override=display_as)
    return tuple(options.values())


def _parse_concentration(raw_duration: object) -> bool:
    if not isinstance(raw_duration, Sequence) or isinstance(raw_duration, (str, bytes)):
        return False
    return any(isinstance(entry, Mapping) and entry.get("concentration") for entry in raw_duration)


def _monster_speed_ft(raw_speed: object) -> int:
    if isinstance(raw_speed, Mapping):
        walk_speed = raw_speed.get("walk")
        if isinstance(walk_speed, int):
            return walk_speed
    if isinstance(raw_speed, int):
        return raw_speed
    return 30

def _monster_climb_speed_ft(raw_speed: object) -> int:
    if isinstance(raw_speed, Mapping):
        climb_speed = raw_speed.get("climb")
        if isinstance(climb_speed, int):
            return climb_speed
    return 0


def _monster_proficiency_bonus(raw_monster: Mapping[str, object]) -> int:
    raw_cr = raw_monster.get('cr')
    if isinstance(raw_cr, Mapping):
        raw_cr = raw_cr.get('cr')
    try:
        if isinstance(raw_cr, str) and '/' in raw_cr:
            numerator, denominator = raw_cr.split('/', 1)
            cr_value = float(numerator) / float(denominator)
        else:
            cr_value = float(raw_cr)
    except (TypeError, ValueError, ZeroDivisionError):
        return 2
    if cr_value <= 4:
        return 2
    return 2 + int((cr_value - 1) // 4)


def _monster_spellcasting(raw_monster: Mapping[str, object]) -> tuple[Ability | None, int | None, int | None]:
    spellcasting_blocks = raw_monster.get('spellcasting') or []
    if not isinstance(spellcasting_blocks, Sequence) or isinstance(spellcasting_blocks, (str, bytes)):
        return None, None, None
    ability = None
    dc = None
    for block in spellcasting_blocks:
        if not isinstance(block, Mapping):
            continue
        raw_ability = block.get('ability')
        if ability is None and isinstance(raw_ability, str):
            key = raw_ability.strip().upper()
            if key in Ability.__members__:
                ability = Ability[key]
        header_entries = block.get('headerEntries') or []
        if dc is None and isinstance(header_entries, Sequence) and not isinstance(header_entries, (str, bytes)):
            for entry in header_entries:
                match = _SPELL_DC_PATTERN.search(str(entry))
                if match is not None:
                    dc = int(match.group(1))
                    break
        if ability is not None and dc is not None:
            break
    attack_bonus = None if dc is None else dc - 8
    return ability, dc, attack_bonus


def _monster_armor_class(raw_ac: object, *, name: str) -> int:
    if isinstance(raw_ac, Sequence) and not isinstance(raw_ac, (str, bytes)) and raw_ac:
        first_entry = raw_ac[0]
        if isinstance(first_entry, int):
            return int(first_entry)
        if isinstance(first_entry, Mapping) and isinstance(first_entry.get("ac"), int):
            return int(first_entry["ac"])
    if isinstance(raw_ac, int):
        return raw_ac
    raise ContentLoadError(f"Monster {name} is missing AC data in the local mirror.")


def _monster_size(raw_size: object) -> str:
    if isinstance(raw_size, Sequence) and not isinstance(raw_size, (str, bytes)) and raw_size:
        return str(raw_size[0])
    return str(raw_size or "M")


def _monster_alignment(raw_alignment: object) -> str | None:
    if isinstance(raw_alignment, str) and raw_alignment.strip():
        return raw_alignment.strip()
    if isinstance(raw_alignment, Sequence) and not isinstance(raw_alignment, (str, bytes)):
        parts = [str(value).strip() for value in raw_alignment if str(value).strip()]
        if parts:
            return '/'.join(parts)
    return None


def _monster_creature_type(raw_type: object) -> str:
    if isinstance(raw_type, Mapping):
        return str(raw_type.get("type", "unknown"))
    return str(raw_type or "unknown")


def load_monster_catalog(
    base_url: str,
    policy: EncounterPolicy,
    document_fetcher: DocumentFetcher | None = None,
) -> EncounterContentCatalog:
    fetch_json = document_fetcher or _fetch_json_from_url
    mirror_base_url = _normalise_base_url(base_url)
    source_metadata = _load_source_metadata(mirror_base_url, fetch_json)

    spells: dict[str, SpellRecord] = {}
    spell_lookup: dict[str, str] = {}
    existing_spell_ids: set[str] = set()
    spell_index_doc = fetch_json(urljoin(mirror_base_url, "data/spells/index.json"))
    if not isinstance(spell_index_doc, Mapping):
        raise ContentLoadError("Mirror spell index is not a JSON object.")
    for source_key, filename in spell_index_doc.items():
        if not isinstance(filename, str):
            continue
        source = str(source_key).upper()
        metadata = _source_metadata_for(source, source_metadata)
        if not policy.allows_spell_source(source, homebrew=False, official=True, first_party=metadata.first_party):
            continue
        spell_doc = fetch_json(urljoin(mirror_base_url, f"data/spells/{filename}"))
        for raw_spell in spell_doc.get("spell", []):
            if not isinstance(raw_spell, Mapping):
                continue
            record_source = str(raw_spell.get("source", source)).upper()
            homebrew = _is_homebrew(record_source, raw_spell)
            official = _is_official(record_source, raw_spell)
            metadata = _source_metadata_for(record_source, source_metadata)
            if not policy.allows_spell_source(record_source, homebrew=homebrew, official=official, first_party=metadata.first_party):
                continue
            name = _canonical_name(raw_spell)
            record_id = _record_id_for_name_source(name, record_source, existing_spell_ids)
            existing_spell_ids.add(record_id)
            material_cost_cp, material_consumed, material_item_keywords, material_focus_tags = _spell_material_profile(raw_spell)
            record = SpellRecord(
                record_id=record_id,
                name=name,
                source=record_source,
                official=official,
                homebrew=homebrew,
                level=(int(raw_spell.get('level', 0)) if isinstance(raw_spell.get('level', 0), int) else 0),
                casting_time_seconds=_spell_casting_time_seconds(raw_spell),
                perceptibility=_spell_perceptibility(raw_spell),
                material_component_cost_cp=material_cost_cp,
                material_component_consumed=material_consumed,
                material_component_item_keywords=material_item_keywords,
                material_component_focus_tags=material_focus_tags,
                can_cast_as_ritual=_spell_can_cast_as_ritual(raw_spell),
                ritual_additional_cast_seconds=600,
                effect_type=_spell_effect_type(raw_spell),
                action_cost=_spell_action_cost(raw_spell),
                range_ft=_spell_range_ft(raw_spell),
                concentration=_parse_concentration(raw_spell.get("duration")),
                capability=build_spell_capability_definition(raw_spell),
                runtime_support=_runtime_support_for_spell(name, source=record_source),
            )
            spells[record.record_id] = record
            _register_spell_aliases(raw_spell, record, spell_lookup)

    monsters: dict[str, MonsterRecord] = {}
    existing_monster_ids: set[str] = set()
    bestiary_index_doc = fetch_json(urljoin(mirror_base_url, "data/bestiary/index.json"))
    if not isinstance(bestiary_index_doc, Mapping):
        raise ContentLoadError("Mirror bestiary index is not a JSON object.")
    for source_key, filename in bestiary_index_doc.items():
        if not isinstance(filename, str):
            continue
        source = str(source_key).upper()
        metadata = _source_metadata_for(source, source_metadata)
        if not policy.allows_monster_source(source, homebrew=False, official=True, first_party=metadata.first_party):
            continue
        bestiary_doc = fetch_json(urljoin(mirror_base_url, f"data/bestiary/{filename}"))
        for raw_monster in bestiary_doc.get("monster", []):
            if not isinstance(raw_monster, Mapping):
                continue
            record_source = str(raw_monster.get("source", source)).upper()
            homebrew = _is_homebrew(record_source, raw_monster)
            official = _is_official(record_source, raw_monster)
            metadata = _source_metadata_for(record_source, source_metadata)
            if not policy.allows_monster_source(record_source, homebrew=homebrew, official=official, first_party=metadata.first_party):
                continue
            name = _canonical_name(raw_monster)
            record_id = _record_id_for_name_source(name, record_source, existing_monster_ids)
            existing_monster_ids.add(record_id)
            attack_ids: set[str] = set()
            raw_actions = raw_monster.get("action", [])
            attacks = ()
            if isinstance(raw_actions, Sequence) and not isinstance(raw_actions, (str, bytes)):
                attacks = tuple(
                    attack
                    for attack in (
                        _parse_attack_profile(action_entry, existing_ids=attack_ids)
                        for action_entry in raw_actions
                        if isinstance(action_entry, Mapping)
                    )
                    if attack is not None
                )
            hp_data = raw_monster.get("hp")
            spellcasting_ability, spell_save_dc, spell_attack_bonus = _monster_spellcasting(raw_monster)
            traits: list[str] = []
            raw_traits = raw_monster.get("trait", [])
            if isinstance(raw_traits, Sequence) and not isinstance(raw_traits, (str, bytes)):
                for trait_entry in raw_traits:
                    if not isinstance(trait_entry, Mapping):
                        continue
                    english_name = trait_entry.get("ENG_name")
                    local_name = trait_entry.get("name")
                    if isinstance(english_name, str) and english_name.strip():
                        traits.append(english_name.strip())
                    elif isinstance(local_name, str) and local_name.strip():
                        traits.append(local_name.strip())
            try:
                monsters[record_id] = MonsterRecord(
                    record_id=record_id,
                    name=name,
                    source=record_source,
                    official=official,
                    homebrew=homebrew,
                    size=_monster_size(raw_monster.get("size")),
                    alignment=_monster_alignment(raw_monster.get("alignment")),
                    creature_type=_monster_creature_type(raw_monster.get("type")),
                    armor_class=_monster_armor_class(raw_monster.get("ac"), name=name),
                    max_hit_points=int(hp_data["average"]) if isinstance(hp_data, Mapping) and isinstance(hp_data.get("average"), int) else (_ for _ in ()).throw(ContentLoadError(f"Monster {name} is missing HP data in the local mirror.")),
                    hit_point_formula=str(hp_data.get("formula", "")),
                    speed_ft=_monster_speed_ft(raw_monster.get("speed")),
                    climb_speed_ft=_monster_climb_speed_ft(raw_monster.get("speed")),
                    proficiency_bonus=_monster_proficiency_bonus(raw_monster),
                    ability_scores=_ability_scores(raw_monster),
                    save_bonuses=_parse_bonus_map(raw_monster.get("save"), ability_keys=True),
                    skill_bonuses=_parse_bonus_map(raw_monster.get("skill"), ability_keys=False),
                    passive_perception=int(raw_monster.get("passive", 10)),
                    damage_immunities=tuple(str(value) for value in raw_monster.get("immune", []) if isinstance(value, str)),
                    damage_resistances=tuple(str(value) for value in raw_monster.get("resist", []) if isinstance(value, str)),
                    condition_immunities=tuple(str(value) for value in raw_monster.get("conditionImmune", []) if isinstance(value, str)),
                    traits=tuple(traits),
                    attacks=attacks,
                    spell_options=_extract_spell_options(raw_monster, spells=spells, spell_lookup=spell_lookup),
                    spellcasting_ability=spellcasting_ability,
                    spell_save_dc=spell_save_dc,
                    spell_attack_bonus=spell_attack_bonus,
                    token_image_path=_monster_token_image_path(raw_monster, name=name, source=record_source),
                )
            except ContentLoadError:
                continue

    if not monsters:
        raise ContentLoadError("The configured local mirror did not return any official monsters for the active monster policy.")
    return EncounterContentCatalog(monsters=monsters, spells=spells)




