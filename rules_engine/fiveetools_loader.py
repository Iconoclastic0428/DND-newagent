from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
import json
from itertools import product
from pathlib import Path
import re
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urljoin, urlparse
from urllib.request import Request, urlopen

from shared_types.equipment import ArmorCategory
from shared_types.errors import ContentLoadError
from shared_types.models import (
    ABILITY_ORDER,
    Ability,
    BackgroundRecord,
    ChoiceGroup,
    ChoiceOption,
    ClassFeatureChoiceGroup,
    ClassFeatureChoiceOption,
    ClassFeatureGrantedSpell,
    ClassFeatureSpellChoiceBundle,
    ClassLevelFeatureGrant,
    ClassRecord,
    ClassSpellcastingRecord,
    MulticlassProficiencyGrant,
    MulticlassRequirementSet,
    SubclassRecord,
    ContentCatalog,
    CreationChoiceCategory,
    CreationSpellRecord,
    CurrencyRoll,
    EquipmentPackage,
    FeatGrantOption,
    FeatRecord,
    FeatSpellChoiceBundle,
    ItemGrant,
    ItemRecord,
    ProficiencyCategory,
    ProficiencyChoiceGroup,
    SelectionConstraint,
    SkillRecord,
    SourcePolicy,
    SpeciesRecord,
    SpellSelectionKind,
    ToolRecord,
    slugify,
)


DocumentFetcher = Callable[[str], Mapping[str, object]]

_SIZE_MAP = {
    "S": "Small",
    "M": "Medium",
    "L": "Large",
    "T": "Tiny",
}

_SKILL_NAME_MAP = {
    "acrobatics": "Acrobatics",
    "animal handling": "Animal Handling",
    "animalhandling": "Animal Handling",
    "arcana": "Arcana",
    "athletics": "Athletics",
    "deception": "Deception",
    "history": "History",
    "insight": "Insight",
    "intimidation": "Intimidation",
    "investigation": "Investigation",
    "medicine": "Medicine",
    "nature": "Nature",
    "perception": "Perception",
    "performance": "Performance",
    "persuasion": "Persuasion",
    "religion": "Religion",
    "sleight of hand": "Sleight of Hand",
    "sleightofhand": "Sleight of Hand",
    "stealth": "Stealth",
    "survival": "Survival",
    "鐢熷瓨": "Survival",
}


_ABILITY_MAP = {
    "str": Ability.STR,
    "strength": Ability.STR,
    "dex": Ability.DEX,
    "dexterity": Ability.DEX,
    "con": Ability.CON,
    "constitution": Ability.CON,
    "int": Ability.INT,
    "intelligence": Ability.INT,
    "wis": Ability.WIS,
    "wisdom": Ability.WIS,
    "cha": Ability.CHA,
    "charisma": Ability.CHA,
}

_ARCANE_FOCUS_TAG = "focus-arcane"
_HOLY_FOCUS_TAG = "focus-holy"
_DRUID_FOCUS_TAG = "focus-druid"

_DAMAGE_TYPE_MAP = {
    "B": "bludgeoning",
    "P": "piercing",
    "S": "slashing",
}

_WEAPON_PROPERTY_MAP = {
    "2H": "two-handed",
    "A": "ammunition",
    "F": "finesse",
    "H": "heavy",
    "L": "light",
    "LD": "loading",
    "R": "reach",
    "T": "thrown",
    "V": "versatile",
}

_WEAPON_MASTERY_MAP = {
    "渚垫壈": "vex",
    "鍓婂急": "sap",
    "澶辫　": "topple",
    "鎺ㄧ": "push",
    "鎿︽帬": "graze",
    "妯壂": "cleave",
    "slow-cn": "slow",
    "杩呭嚮": "nick",
}


@dataclass(frozen=True)
class _SourceMetadata:
    source: str
    author: str
    group: str

    @property
    def first_party(self) -> bool:
        lowered_author = self.author.lower()
        lowered_group = self.group.lower()
        return (
            "wizard" in lowered_author
            or self.author == "???RPG??"
            or lowered_group in {"core", "supplement", "supplement-alt", "setting", "setting-alt"}
        )


def _local_path_from_file_url(url: str) -> Path:
    parsed = urlparse(url)
    return Path(unquote(parsed.path.lstrip("/")))


def _fetch_json_from_url(url: str) -> Mapping[str, object]:
    if url.startswith("file://"):
        path = _local_path_from_file_url(url)
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except OSError as exc:
            raise ContentLoadError(f"Failed to read local mirror file {path}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise ContentLoadError(f"Local mirror file {path} returned invalid JSON: {exc}") from exc

    request = Request(url, headers={"User-Agent": "DND-agent-character-kernel/1.0"})
    try:
        with urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8-sig"))
    except HTTPError as exc:
        raise ContentLoadError(f"Failed to fetch mirror URL {url}: HTTP {exc.code} {exc.reason}") from exc
    except URLError as exc:
        raise ContentLoadError(f"Failed to fetch mirror URL {url}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise ContentLoadError(f"Mirror URL {url} returned invalid JSON: {exc}") from exc


def _normalise_base_url(base_url: str) -> str:
    stripped = base_url.strip()
    if re.match(r"^[a-zA-Z]:[\\/]", stripped):
        return Path(stripped).resolve().as_uri().rstrip("/") + "/"
    if stripped.startswith("file://"):
        return stripped.rstrip("/") + "/"
    return stripped.rstrip("/") + "/"


def _canonical_name(record: Mapping[str, object]) -> str:
    english_name = record.get("ENG_name")
    if isinstance(english_name, str) and english_name.strip():
        return english_name.strip()
    raw_name = record.get("name")
    if isinstance(raw_name, str) and raw_name.strip():
        return raw_name.strip()
    raise ContentLoadError(f"Mirror record is missing a usable name: {record!r}")


def _name_aliases(record: Mapping[str, object]) -> tuple[str, ...]:
    aliases: list[str] = []
    for key in ("ENG_name", "name"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            aliases.append(value.strip())
    if not aliases:
        aliases.append(_canonical_name(record))
    return tuple(dict.fromkeys(aliases))


def _item_type_abbreviation(raw_item: Mapping[str, object]) -> str | None:
    item_type = raw_item.get("type")
    if not isinstance(item_type, str):
        return None
    return item_type.split("|", 1)[0]


def _ability(value: str) -> Ability:
    normalised = value.strip().lower()
    if normalised not in _ABILITY_MAP:
        raise ContentLoadError(f"Unsupported ability token in mirror data: {value}")
    return _ABILITY_MAP[normalised]


def _display_skill(value: str) -> str:
    normalised = value.strip().lower()
    return _SKILL_NAME_MAP.get(normalised, value.replace("_", " ").title())


def _display_text(value: str) -> str:
    return value.replace("_", " ").title()


def _is_homebrew(source: str, record: Mapping[str, object]) -> bool:
    source_upper = source.upper()
    if source_upper.startswith("HB") or source_upper.startswith("BREW"):
        return True
    return bool(record.get("homebrew", False))


def _is_official(source: str, record: Mapping[str, object]) -> bool:
    if _is_homebrew(source, record):
        return False
    return bool(source.strip())


def _edition_for_source(source: str) -> str:
    return "2024" if source.upper().startswith("X") else "2014"


def _ref_key(name: str, source: str) -> str:
    return f"{slugify(name)}|{source.lower()}"


def _parse_item_ref(reference: str) -> tuple[str, str]:
    if "|" in reference:
        name, source = reference.split("|", 1)
        return name.strip(), source.strip().upper()
    return reference.strip(), ""


def _parse_speed(raw_speed: object) -> int:
    if isinstance(raw_speed, int):
        return raw_speed
    if isinstance(raw_speed, Mapping):
        walk_speed = raw_speed.get("walk")
        if isinstance(walk_speed, int):
            return walk_speed
    raise ContentLoadError(f"Unsupported speed value in mirror data: {raw_speed!r}")


def _parse_size_options(raw_size: object) -> tuple[str, ...]:
    if isinstance(raw_size, str):
        return (_SIZE_MAP.get(raw_size, raw_size),)
    if isinstance(raw_size, Sequence):
        size_options = tuple(_SIZE_MAP.get(str(value), str(value)) for value in raw_size)
        if size_options:
            return size_options
    raise ContentLoadError(f"Unsupported size value in mirror data: {raw_size!r}")


def _extract_trait_names(record: Mapping[str, object]) -> tuple[str, ...]:
    trait_names: list[str] = []
    entries = record.get("entries")
    if isinstance(entries, Sequence):
        for entry in entries:
            if isinstance(entry, Mapping) and isinstance(entry.get("ENG_name"), str):
                trait_names.append(str(entry["ENG_name"]))
            elif isinstance(entry, Mapping) and isinstance(entry.get("name"), str):
                trait_names.append(str(entry["name"]))
    if trait_names:
        return tuple(dict.fromkeys(trait_names))
    raw_tags = record.get("traitTags")
    if isinstance(raw_tags, Sequence):
        return tuple(str(tag) for tag in raw_tags)
    return ()


def _extract_skill_list(raw_entries: object) -> tuple[str, ...]:
    skills: list[str] = []
    if not isinstance(raw_entries, Sequence):
        return ()
    for entry in raw_entries:
        if isinstance(entry, str):
            skills.append(_display_skill(entry))
            continue
        if not isinstance(entry, Mapping):
            continue
        for key, value in entry.items():
            if key == "choose" and isinstance(value, Mapping):
                from_values = value.get("from")
                if isinstance(from_values, Sequence):
                    skills.extend(_display_skill(str(skill)) for skill in from_values)
            elif isinstance(value, bool) and value:
                skills.append(_display_skill(str(key)))
    return tuple(dict.fromkeys(skills))


def _extract_tool_list(raw_entries: object) -> tuple[str, ...]:
    tools: list[str] = []
    if not isinstance(raw_entries, Sequence):
        return ()
    for entry in raw_entries:
        if isinstance(entry, str):
            tools.append(_display_text(entry))
            continue
        if not isinstance(entry, Mapping):
            continue
        for key, value in entry.items():
            if key == "choose" and isinstance(value, Mapping):
                from_values = value.get("from")
                if isinstance(from_values, Sequence):
                    tools.extend(_display_text(str(tool)) for tool in from_values)
            elif isinstance(value, bool) and value:
                tools.append(_display_text(str(key)))
    return tuple(dict.fromkeys(tools))


def _extract_skill_choice(record: Mapping[str, object]) -> tuple[tuple[str, ...], int]:
    starting = record.get("startingProficiencies")
    if not isinstance(starting, Mapping):
        raise ContentLoadError(f"Class {_canonical_name(record)} is missing starting proficiencies.")
    skills = starting.get("skills")
    if not isinstance(skills, Sequence):
        return (), 0
    for entry in skills:
        if not isinstance(entry, Mapping):
            continue
        choose = entry.get("choose")
        if not isinstance(choose, Mapping):
            continue
        raw_from = choose.get("from")
        count = choose.get("count")
        if isinstance(raw_from, Sequence) and isinstance(count, int):
            options = tuple(_display_skill(str(skill)) for skill in raw_from)
            return tuple(dict.fromkeys(options)), count
    return (), 0


def _parse_primary_abilities(record: Mapping[str, object]) -> tuple[Ability, ...]:
    values: list[Ability] = []
    primary = record.get("primaryAbility")
    if isinstance(primary, Sequence) and not isinstance(primary, (str, bytes)):
        for entry in primary:
            if isinstance(entry, str):
                values.append(_ability(entry))
                continue
            if not isinstance(entry, Mapping):
                continue
            for key, enabled in entry.items():
                if isinstance(enabled, bool) and enabled and str(key).lower() in _ABILITY_MAP:
                    values.append(_ability(str(key)))
        if values:
            return tuple(dict.fromkeys(values))
    spellcasting = record.get("spellcastingAbility")
    if isinstance(spellcasting, str):
        return (_ability(spellcasting),)
    return ()


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


def _extract_first_string(raw_entries: object) -> str | None:
    if isinstance(raw_entries, str) and raw_entries.strip():
        return raw_entries.strip()
    if isinstance(raw_entries, Sequence) and not isinstance(raw_entries, (str, bytes)):
        for entry in raw_entries:
            value = _extract_first_string(entry)
            if value:
                return value
    if isinstance(raw_entries, Mapping):
        value = _extract_first_string(raw_entries.get("entries"))
        if value:
            return value
    return None


def _load_source_metadata(mirror_base_url: str, fetch_json: DocumentFetcher) -> dict[str, _SourceMetadata]:
    metadata: dict[str, _SourceMetadata] = {}
    for relative_path, key in (("data/books.json", "book"), ("data/adventures.json", "adventure")):
        try:
            doc = fetch_json(urljoin(mirror_base_url, relative_path))
        except ContentLoadError:
            continue
        raw_entries = doc.get(key, []) if isinstance(doc, Mapping) else []
        if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
            continue
        for entry in raw_entries:
            if not isinstance(entry, Mapping):
                continue
            source = str(entry.get("source", "")).upper()
            if not source:
                continue
            metadata[source] = _SourceMetadata(
                source=source,
                author=str(entry.get("author", "")),
                group=str(entry.get("group", "")),
            )
    return metadata


def _build_feat_record(raw_feat: Mapping[str, object], *, policy: SourcePolicy, source_metadata: Mapping[str, _SourceMetadata], existing_ids: set[str]) -> FeatRecord | None:
    source = str(raw_feat.get("source", "")).upper()
    homebrew = _is_homebrew(source, raw_feat)
    official = _is_official(source, raw_feat)
    if homebrew and not policy.allow_homebrew:
        return None
    if not official:
        return None
    category = str(raw_feat.get("category", "")).upper()
    name = _canonical_name(raw_feat)
    record_id = _record_id_for_name_source(name, source, existing_ids)
    metadata = source_metadata.get(source, _SourceMetadata(source=source, author="", group=""))
    return FeatRecord(
        record_id=record_id,
        name=name,
        source=source,
        official=official,
        homebrew=homebrew,
        category=category,
        prerequisite=_extract_first_string(raw_feat.get("prerequisite")),
        selectable_for_custom_origin=(
            category == "O"
            and policy.allows_origin_feat_source(
                source,
                homebrew=homebrew,
                official=official,
                first_party=metadata.first_party,
            )
        ),
    )


def _register_feat_aliases(raw_feat: Mapping[str, object], record: FeatRecord, feat_lookup: dict[str, str]) -> None:
    for alias in _name_aliases(raw_feat):
        feat_lookup[_ref_key(alias, record.source)] = record.record_id


def _resolve_feat_id(reference: str, feat_lookup: Mapping[str, str], feats: Mapping[str, FeatRecord]) -> str:
    name, source = _parse_item_ref(reference)
    key = _ref_key(name, source)
    if key in feat_lookup:
        return feat_lookup[key]
    fallback_matches = [feat.record_id for feat in feats.values() if slugify(feat.name) == slugify(name)]
    if len(fallback_matches) == 1:
        return fallback_matches[0]
    raise ContentLoadError(f"Mirror feat reference {reference!r} could not be resolved.")


def _parse_species_bonus_origin_feat_count(record: Mapping[str, object]) -> int:
    raw_feats = record.get("feats")
    if not isinstance(raw_feats, Sequence) or isinstance(raw_feats, (str, bytes)):
        return 0
    count = 0
    for feat_entry in raw_feats:
        if not isinstance(feat_entry, Mapping):
            continue
        any_from_category = feat_entry.get("anyFromCategory")
        if not isinstance(any_from_category, Mapping):
            continue
        categories = any_from_category.get("category")
        category_values = [str(categories)] if isinstance(categories, str) else [str(value) for value in categories] if isinstance(categories, Sequence) and not isinstance(categories, (str, bytes)) else []
        if "O" in {value.upper() for value in category_values}:
            count += int(any_from_category.get("count", 1) or 1)
    return count


def _parse_background_ability_config(record: Mapping[str, object]) -> tuple[tuple[Ability, ...], bool]:
    direct_choices = record.get("abilityScoreChoices")
    if isinstance(direct_choices, Sequence) and not isinstance(direct_choices, (str, bytes)) and len(direct_choices) == 3:
        return tuple(_ability(str(value)) for value in direct_choices), False

    ability_entries = record.get("ability")
    if isinstance(ability_entries, Sequence) and not isinstance(ability_entries, (str, bytes)):
        for ability_entry in ability_entries:
            if not isinstance(ability_entry, Mapping):
                continue
            choose = ability_entry.get("choose")
            if isinstance(choose, Mapping):
                from_values = choose.get("from")
                if isinstance(from_values, Sequence) and not isinstance(from_values, (str, bytes)) and len(from_values) == 3:
                    return tuple(_ability(str(value)) for value in from_values), False
                weighted = choose.get("weighted")
                if isinstance(weighted, Mapping):
                    weighted_from = weighted.get("from")
                    if isinstance(weighted_from, Sequence) and not isinstance(weighted_from, (str, bytes)) and len(weighted_from) == 3:
                        return tuple(_ability(str(value)) for value in weighted_from), False
            enabled = [_ability(str(key)) for key, value in ability_entry.items() if isinstance(value, bool) and value and str(key).lower() in _ABILITY_MAP]
            if len(enabled) == 3:
                return tuple(enabled), False

    return ABILITY_ORDER, True


def _parse_origin_feat_option_ids(record: Mapping[str, object], *, feats: Mapping[str, FeatRecord], feat_lookup: Mapping[str, str]) -> tuple[str, ...]:
    raw_feats = record.get("feats")
    option_ids: list[str] = []
    if isinstance(raw_feats, Sequence) and not isinstance(raw_feats, (str, bytes)):
        for feat_entry in raw_feats:
            if isinstance(feat_entry, str):
                option_ids.append(_resolve_feat_id(feat_entry, feat_lookup, feats))
                continue
            if not isinstance(feat_entry, Mapping):
                continue
            any_from_category = feat_entry.get("anyFromCategory")
            if isinstance(any_from_category, Mapping):
                categories = any_from_category.get("category")
                category_values = [str(categories)] if isinstance(categories, str) else [str(value) for value in categories] if isinstance(categories, Sequence) and not isinstance(categories, (str, bytes)) else []
                if "O" in {value.upper() for value in category_values}:
                    return ()
            for key, value in feat_entry.items():
                if isinstance(value, bool) and value:
                    option_ids.append(_resolve_feat_id(str(key), feat_lookup, feats))
    origin_feat = record.get("originFeat")
    if isinstance(origin_feat, str):
        option_ids.append(_resolve_feat_id(origin_feat, feat_lookup, feats))
    return tuple(dict.fromkeys(option_ids))


def _parse_weapon_damage(raw_value: object) -> tuple[int | None, int | None]:
    if not isinstance(raw_value, str) or 'd' not in raw_value:
        return None, None
    count_text, faces_text = raw_value.lower().split('d', 1)
    try:
        return int(count_text), int(faces_text)
    except ValueError:
        return None, None


def _parse_weapon_range(raw_value: object) -> tuple[int | None, int | None]:
    if not isinstance(raw_value, str) or not raw_value.strip():
        return None, None
    parts = [part.strip() for part in raw_value.split('/', 1)]
    try:
        short_range = int(parts[0])
    except ValueError:
        return None, None
    if len(parts) == 1:
        return short_range, None
    try:
        return short_range, int(parts[1])
    except ValueError:
        return short_range, None


def _parse_weapon_properties(raw_item: Mapping[str, object]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    properties: list[str] = []
    notes: list[str] = []
    raw_properties = raw_item.get('property')
    if not isinstance(raw_properties, Sequence) or isinstance(raw_properties, (str, bytes)):
        return (), ()
    for raw_property in raw_properties:
        note: str | None = None
        uid: str | None = None
        if isinstance(raw_property, str):
            uid = raw_property
        elif isinstance(raw_property, Mapping):
            raw_uid = raw_property.get('uid')
            if isinstance(raw_uid, str):
                uid = raw_uid
            raw_note = raw_property.get('note')
            if isinstance(raw_note, str) and raw_note.strip():
                note = raw_note.strip()
        if not isinstance(uid, str):
            continue
        token = uid.split('|', 1)[0]
        property_name = _WEAPON_PROPERTY_MAP.get(token)
        if property_name is None:
            continue
        properties.append(property_name)
        if note is not None:
            notes.append(f'{property_name} {note}')
    return tuple(dict.fromkeys(properties)), tuple(dict.fromkeys(notes))


def _parse_weapon_mastery(raw_item: Mapping[str, object]) -> str | None:
    raw_masteries = raw_item.get('mastery')
    if not isinstance(raw_masteries, Sequence) or isinstance(raw_masteries, (str, bytes)) or not raw_masteries:
        return None
    raw_mastery = raw_masteries[0]
    if not isinstance(raw_mastery, str):
        return None
    token = raw_mastery.split('|', 1)[0]
    return _WEAPON_MASTERY_MAP.get(token)


def _parse_weapon_ammunition_type(raw_item: Mapping[str, object]) -> str | None:
    ammo_type = raw_item.get('ammoType')
    if not isinstance(ammo_type, str) or not ammo_type.strip():
        return None
    return ammo_type.split('|', 1)[0].strip()


def _armor_metadata(raw_item: Mapping[str, object]) -> dict[str, object]:
    raw_type = raw_item.get('type')
    if not isinstance(raw_type, str):
        return {}
    item_type = raw_type.split('|', 1)[0]
    if not raw_item.get('armor') and item_type != 'S':
        return {}
    ac_value = raw_item.get('ac')
    armor_class = ac_value if isinstance(ac_value, int) else None
    strength_requirement = raw_item.get('strength') if isinstance(raw_item.get('strength'), int) else None
    stealth_disadvantage = bool(raw_item.get('stealth'))
    if item_type == 'LA':
        return {
            'armor_category': ArmorCategory.LIGHT,
            'armor_base_ac': armor_class,
            'armor_dex_cap': None,
            'armor_strength_requirement': strength_requirement,
            'armor_stealth_disadvantage': stealth_disadvantage,
            'armor_don_time_seconds': 10 * 60,
        }
    if item_type == 'MA':
        return {
            'armor_category': ArmorCategory.MEDIUM,
            'armor_base_ac': armor_class,
            'armor_dex_cap': 2,
            'armor_strength_requirement': strength_requirement,
            'armor_stealth_disadvantage': stealth_disadvantage,
            'armor_don_time_seconds': 10 * 60,
        }
    if item_type == 'HA':
        return {
            'armor_category': ArmorCategory.HEAVY,
            'armor_base_ac': armor_class,
            'armor_dex_cap': 0,
            'armor_strength_requirement': strength_requirement,
            'armor_stealth_disadvantage': stealth_disadvantage,
            'armor_don_time_seconds': 10 * 60,
        }
    if item_type == 'S':
        return {
            'armor_category': ArmorCategory.SHIELD,
            'shield_ac_bonus': armor_class,
        }
    return {}


def _weapon_metadata(raw_item: Mapping[str, object]) -> dict[str, object]:
    if not raw_item.get('weapon'):
        return {}
    raw_type = raw_item.get('type')
    raw_category = raw_item.get('weaponCategory')
    if not isinstance(raw_type, str) or not isinstance(raw_category, str):
        return {}
    item_type = raw_type.split('|', 1)[0]
    if item_type == 'M':
        weapon_kind = 'melee'
    elif item_type == 'R':
        weapon_kind = 'ranged'
    else:
        return {}
    damage_count, damage_faces = _parse_weapon_damage(raw_item.get('dmg1'))
    versatile_count, versatile_faces = _parse_weapon_damage(raw_item.get('dmg2'))
    range_ft, long_range_ft = _parse_weapon_range(raw_item.get('range'))
    properties, notes = _parse_weapon_properties(raw_item)
    damage_type = _DAMAGE_TYPE_MAP.get(str(raw_item.get('dmgType', '')).strip())
    return {
        'weapon_category': raw_category.split('|', 1)[0],
        'weapon_kind': weapon_kind,
        'weapon_damage_dice_count': damage_count,
        'weapon_damage_die_faces': damage_faces,
        'weapon_versatile_damage_dice_count': versatile_count,
        'weapon_versatile_damage_die_faces': versatile_faces,
        'weapon_damage_type': damage_type,
        'weapon_range_ft': range_ft,
        'weapon_long_range_ft': long_range_ft,
        'weapon_properties': properties,
        'weapon_mastery': _parse_weapon_mastery(raw_item),
        'weapon_ammunition_type': _parse_weapon_ammunition_type(raw_item),
        'weapon_notes': notes,
    }


def _build_item_record(raw_item: Mapping[str, object], policy: SourcePolicy) -> ItemRecord | None:
    source = str(raw_item.get("source", "")).upper()
    edition = _edition_for_source(source)
    homebrew = _is_homebrew(source, raw_item)
    official = _is_official(source, raw_item)
    if not policy.allows_item_source(source, homebrew=homebrew, edition=edition, official=official):
        return None
    name = _canonical_name(raw_item)
    record_id = str(raw_item.get("id") or slugify(name))
    tags: list[str] = []
    item_type = _item_type_abbreviation(raw_item)
    if item_type is not None:
        tags.append(item_type.lower())
    if raw_item.get("weapon"):
        tags.append("weapon")
    if raw_item.get("armor"):
        tags.append("armor")
    if item_type == 'S':
        tags.append('shield')
    if item_type == "SCF":
        scf_type = str(raw_item.get("scfType", "")).lower()
        if scf_type == "arcane":
            tags.append(_ARCANE_FOCUS_TAG)
        elif scf_type == "holy":
            tags.append(_HOLY_FOCUS_TAG)
        elif scf_type == "druid":
            tags.append(_DRUID_FOCUS_TAG)
    weight_raw = raw_item.get("weight", 0)
    try:
        weight_lb = float(weight_raw) if weight_raw is not None else 0.0
    except (TypeError, ValueError):
        weight_lb = 0.0
    return ItemRecord(
        record_id=record_id,
        name=name,
        source=source,
        edition=edition,
        official=official,
        homebrew=homebrew,
        cost_cp=int(raw_item.get("value", 0) or 0),
        weight_lb=weight_lb,
        is_magical=(str(raw_item.get("rarity", "")).strip().casefold() not in {"", "none", "unknown"} or bool(raw_item.get("wondrous") or raw_item.get("staff") or raw_item.get("wand") or raw_item.get("rod") or raw_item.get("reqAttune") or raw_item.get("charges") or raw_item.get("bonusWeapon") or raw_item.get("bonusAc") or raw_item.get("bonusSavingThrow"))),
        tags=tuple(dict.fromkeys(tags)),
        **_weapon_metadata(raw_item),
        **_armor_metadata(raw_item),
    )


def _register_item_aliases(raw_item: Mapping[str, object], record: ItemRecord, item_lookup: dict[str, str]) -> None:
    for alias in _name_aliases(raw_item):
        item_lookup[_ref_key(alias, record.source)] = record.record_id


def _iter_item_records(items_doc: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw_items: list[Mapping[str, object]] = []
    for key in ("baseitem", "item"):
        entries = items_doc.get(key)
        if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
            continue
        raw_items.extend(entry for entry in entries if isinstance(entry, Mapping))
    return tuple(raw_items)


def _register_item_reprint_aliases(
    raw_item: Mapping[str, object],
    *,
    item_lookup: dict[str, str],
    items: Mapping[str, ItemRecord],
) -> None:
    source = str(raw_item.get("source", "")).upper()
    if not source:
        return
    raw_reprinted_as = raw_item.get("reprintedAs")
    if not isinstance(raw_reprinted_as, Sequence) or isinstance(raw_reprinted_as, (str, bytes)):
        return

    target_id: str | None = None
    for reference in raw_reprinted_as:
        if not isinstance(reference, str):
            continue
        try:
            target_id = _resolve_item_id(reference, item_lookup, items)
            break
        except ContentLoadError:
            continue
    if target_id is None:
        return

    for alias in _name_aliases(raw_item):
        item_lookup[_ref_key(alias, source)] = target_id

def _ensure_special_item(
    *,
    name: str,
    source: str,
    items: dict[str, ItemRecord],
    item_lookup: dict[str, str],
) -> str:
    key = _ref_key(name, source)
    existing = item_lookup.get(key)
    if existing is not None:
        return existing
    record_id = slugify(name)
    suffix = 2
    while record_id in items:
        record_id = f"{slugify(name)}-{suffix}"
        suffix += 1
    items[record_id] = ItemRecord(
        record_id=record_id,
        name=name,
        source=source,
        edition=_edition_for_source(source),
        official=_is_official(source, {}),
        homebrew=_is_homebrew(source, {}),
        cost_cp=0,
        is_magical=False,
        tags=("special", "package-only"),
    )
    item_lookup[key] = record_id
    return record_id


def _resolve_item_id(reference: str, item_lookup: Mapping[str, str], items: Mapping[str, ItemRecord]) -> str:
    name, source = _parse_item_ref(reference)
    key = _ref_key(name, source)
    if key in item_lookup:
        return item_lookup[key]
    alias_matches = {
        record_id
        for alias_key, record_id in item_lookup.items()
        if alias_key.split("|", 1)[0] == slugify(name)
    }
    if len(alias_matches) == 1:
        return next(iter(alias_matches))
    fallback_matches = [item.record_id for item in items.values() if slugify(item.name) == slugify(name)]
    if len(fallback_matches) == 1:
        return fallback_matches[0]
    raise ContentLoadError(f"Mirror equipment reference {reference!r} is not available under the active item policy.")


def _expand_atom(
    atom: object,
    *,
    source: str,
    items: dict[str, ItemRecord],
    item_lookup: dict[str, str],
) -> list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]]:
    if isinstance(atom, str):
        try:
            item_id = _resolve_item_id(atom, item_lookup, items)
            item = items[item_id]
            return [((ItemGrant(item_id=item_id, quantity=1),), 0, (item.name,))]
        except ContentLoadError:
            item_name, item_source = _parse_item_ref(atom)
            item_id = _ensure_special_item(name=item_name, source=source, items=items, item_lookup=item_lookup)
            return [((ItemGrant(item_id=item_id, quantity=1),), 0, (item_name,))]

    if not isinstance(atom, Mapping):
        raise ContentLoadError(f"Unsupported equipment atom in mirror data: {atom!r}")

    if isinstance(atom.get("value"), int):
        return [((), int(atom.get("value", 0) or 0), ())]

    if isinstance(atom.get("item"), str):
        quantity = int(atom.get("quantity", 1) or 1)
        currency = int(atom.get("containsValue", 0) or 0)
        try:
            item_id = _resolve_item_id(str(atom["item"]), item_lookup, items)
            item = items[item_id]
            return [((ItemGrant(item_id=item_id, quantity=quantity),), currency, (item.name,))]
        except ContentLoadError:
            display_name = atom.get("displayName")
            item_name, item_source = _parse_item_ref(str(atom["item"]))
            if isinstance(display_name, str) and display_name.strip():
                item_id = _ensure_special_item(name=display_name.strip(), source=source, items=items, item_lookup=item_lookup)
                return [((ItemGrant(item_id=item_id, quantity=quantity),), currency, (display_name.strip(),))]
            item_id = _ensure_special_item(name=item_name, source=source, items=items, item_lookup=item_lookup)
            return [((ItemGrant(item_id=item_id, quantity=quantity),), currency, (item_name,))]

    if isinstance(atom.get("special"), str):
        special_name = str(atom["special"])
        item_id = _ensure_special_item(name=special_name, source=source, items=items, item_lookup=item_lookup)
        quantity = int(atom.get("quantity", 1) or 1)
        return [((ItemGrant(item_id=item_id, quantity=quantity),), 0, (special_name,))]

    raw_equipment_types = atom.get("equipmentTypes")
    if isinstance(raw_equipment_types, Sequence) and not isinstance(raw_equipment_types, (str, bytes)):
        item_id = _ensure_special_item(name="Equipment Choice", source=source, items=items, item_lookup=item_lookup)
        return [((ItemGrant(item_id=item_id, quantity=1),), 0, (items[item_id].name,))]

    equipment_type = atom.get("equipmentType")
    if equipment_type in {"focusSpellcastingArcane", "focusSpellcastingHoly", "focusSpellcastingDruidic"}:
        target_tag = {
            "focusSpellcastingArcane": _ARCANE_FOCUS_TAG,
            "focusSpellcastingHoly": _HOLY_FOCUS_TAG,
            "focusSpellcastingDruidic": _DRUID_FOCUS_TAG,
        }[str(equipment_type)]
        variants: list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]] = []
        for item in items.values():
            if target_tag in item.tags:
                variants.append(((ItemGrant(item_id=item.record_id, quantity=1),), 0, (item.name,)))
        if not variants:
            raise ContentLoadError(f"Mirror data requested {equipment_type!r}, but no allowed focus items were loaded.")
        return variants

    equipment_type_tags = {
        "toolArtisan": "at",
        "setGaming": "gs",
        "instrumentMusical": "ins",
    }
    if equipment_type in equipment_type_tags:
        target_tag = equipment_type_tags[str(equipment_type)]
        variants = []
        for item in items.values():
            if target_tag in item.tags:
                variants.append(((ItemGrant(item_id=item.record_id, quantity=1),), 0, (item.name,)))
        if variants:
            return variants
        if equipment_type == "setGaming":
            item_id = _ensure_special_item(name="Gaming Set", source=source, items=items, item_lookup=item_lookup)
            return [((ItemGrant(item_id=item_id, quantity=1),), 0, (items[item_id].name,))]
        raise ContentLoadError(f"Mirror data requested equipmentType {equipment_type!r}, but no allowed items were loaded.")

    raise ContentLoadError(f"Unsupported equipment atom in mirror data: {atom!r}")


def _combine_atom_list(
    atoms: Sequence[object],
    *,
    source: str,
    items: dict[str, ItemRecord],
    item_lookup: dict[str, str],
) -> list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]]:
    variants: list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]] = [((), 0, ())]
    for atom in atoms:
        atom_variants = _expand_atom(atom, source=source, items=items, item_lookup=item_lookup)
        next_variants: list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]] = []
        for grants, currency, labels in variants:
            for atom_grants, atom_currency, atom_labels in atom_variants:
                next_variants.append((grants + atom_grants, currency + atom_currency, labels + atom_labels))
        variants = next_variants
    return variants


def _is_currency_only_option(option_entries: object) -> bool:
    if not isinstance(option_entries, Sequence):
        return False
    saw_currency = False
    for atom in option_entries:
        if not isinstance(atom, Mapping) or not isinstance(atom.get("value"), int):
            return False
        saw_currency = True
    return saw_currency


def _extract_default_data(starting_equipment: object) -> Sequence[object]:
    if starting_equipment is None:
        return ()
    if isinstance(starting_equipment, Mapping):
        default_data = starting_equipment.get("defaultData")
        if not isinstance(default_data, Sequence):
            raise ContentLoadError("Mirror starting equipment is missing defaultData.")
        return default_data
    if isinstance(starting_equipment, Sequence):
        return starting_equipment
    raise ContentLoadError(f"Unsupported structured starting equipment data: {starting_equipment!r}")


def _build_packages(
    *,
    owner_id: str,
    owner_name: str,
    source: str,
    starting_equipment: object,
    items: dict[str, ItemRecord],
    item_lookup: dict[str, str],
) -> tuple[EquipmentPackage, ...]:
    default_data = _extract_default_data(starting_equipment)

    group_variants: list[list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]]] = []
    for group in default_data:
        if not isinstance(group, Mapping):
            raise ContentLoadError(f"Unsupported equipment group in mirror data for {owner_name}.")
        if "_" in group:
            fixed_entries = group["_"]
            if not isinstance(fixed_entries, Sequence):
                raise ContentLoadError(f"Unsupported fixed equipment group in mirror data for {owner_name}.")
            group_variants.append(_combine_atom_list(fixed_entries, source=source, items=items, item_lookup=item_lookup))
            continue

        option_variants: list[tuple[tuple[ItemGrant, ...], int, tuple[str, ...]]] = []
        for option_key in sorted(group):
            option_entries = group[option_key]
            if _is_currency_only_option(option_entries):
                continue
            if not isinstance(option_entries, Sequence):
                raise ContentLoadError(f"Unsupported equipment option in mirror data for {owner_name}.")
            option_variants.extend(
                _combine_atom_list(option_entries, source=source, items=items, item_lookup=item_lookup)
            )
        if not option_variants:
            continue
        group_variants.append(option_variants)

    if not group_variants:
        return ()

    packages: list[EquipmentPackage] = []
    for index, selection in enumerate(product(*group_variants), start=1):
        grants: list[ItemGrant] = []
        currency_cp = 0
        labels: list[str] = []
        for group_grants, group_currency, group_labels in selection:
            grants.extend(group_grants)
            currency_cp += group_currency
            labels.extend(group_labels)
        package_id = f"{owner_id}-package-{index}"
        label = f"{owner_name} package {index}: {', '.join(labels)}"
        packages.append(
            EquipmentPackage(
                package_id=package_id,
                label=label,
                item_grants=tuple(grants),
                currency_cp=currency_cp,
            )
        )
    return tuple(packages)


def _parse_background_ability_choices(record: Mapping[str, object]) -> tuple[Ability, Ability, Ability]:
    direct_choices = record.get("abilityScoreChoices")
    if isinstance(direct_choices, Sequence) and len(direct_choices) == 3:
        return tuple(_ability(str(value)) for value in direct_choices)  # type: ignore[return-value]

    ability_entries = record.get("ability")
    if isinstance(ability_entries, Sequence):
        for ability_entry in ability_entries:
            if not isinstance(ability_entry, Mapping):
                continue
            choose = ability_entry.get("choose")
            if isinstance(choose, Mapping):
                from_values = choose.get("from")
                if isinstance(from_values, Sequence) and len(from_values) == 3:
                    return tuple(_ability(str(value)) for value in from_values)  # type: ignore[return-value]
                weighted = choose.get("weighted")
                if isinstance(weighted, Mapping):
                    weighted_from = weighted.get("from")
                    if isinstance(weighted_from, Sequence) and len(weighted_from) == 3:
                        return tuple(_ability(str(value)) for value in weighted_from)  # type: ignore[return-value]
            enabled = [
                _ability(str(key))
                for key, value in ability_entry.items()
                if isinstance(value, bool) and value and str(key).lower() in _ABILITY_MAP
            ]
            if len(enabled) == 3:
                return tuple(enabled)  # type: ignore[return-value]

    raise ContentLoadError(
        f"Background {_canonical_name(record)} is missing 2024 background ability choices in mirror data."
    )


def _parse_origin_feat(record: Mapping[str, object]) -> str:
    raw_feats = record.get("feats")
    if isinstance(raw_feats, Sequence):
        for feat_entry in raw_feats:
            if isinstance(feat_entry, str):
                return _parse_item_ref(feat_entry)[0].title()
            if not isinstance(feat_entry, Mapping):
                continue
            for key, value in feat_entry.items():
                if isinstance(value, bool) and value:
                    return _parse_item_ref(str(key))[0].title()
    origin_feat = record.get("originFeat")
    if isinstance(origin_feat, str):
        return origin_feat
    raise ContentLoadError(f"Background {_canonical_name(record)} is missing an origin feat in mirror data.")


def _parse_gold_option_cp(record: Mapping[str, object]) -> int | None:
    for key in ("goldOptionCp", "startingGold", "goldOption", "gold", "wealth"):
        value = record.get(key)
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            match = re.search(r"(\d+)\s*gp", value, flags=re.IGNORECASE)
            if match:
                return int(match.group(1)) * 100

    starting_equipment = record.get("startingEquipment")
    if isinstance(starting_equipment, Sequence):
        for group in starting_equipment:
            if not isinstance(group, Mapping):
                continue
            for option_entries in group.values():
                if not _is_currency_only_option(option_entries):
                    continue
                return sum(int(atom.get("value", 0) or 0) for atom in option_entries if isinstance(atom, Mapping))

    return None


def _parse_currency_roll(raw_value: object) -> CurrencyRoll | None:
    if raw_value is None:
        return None
    if isinstance(raw_value, Mapping):
        die_count = raw_value.get("dieCount")
        die_faces = raw_value.get("dieFaces")
        multiplier_cp = raw_value.get("multiplierCp")
        label = raw_value.get("label")
        if isinstance(die_count, int) and isinstance(die_faces, int) and isinstance(multiplier_cp, int):
            return CurrencyRoll(
                die_count=die_count,
                die_faces=die_faces,
                multiplier_cp=multiplier_cp,
                label=str(label or f"{die_count}d{die_faces}"),
            )
    if isinstance(raw_value, str):
        cleaned = raw_value.replace("\u00d7", "x")
        match = re.search(r"(\d+)d(\d+)\s*x\s*(\d+)", cleaned, flags=re.IGNORECASE)
        if not match:
            raise ContentLoadError(f"Unsupported class wealth expression in mirror data: {raw_value}")
        die_count = int(match.group(1))
        die_faces = int(match.group(2))
        multiplier_gp = int(match.group(3))
        label = f"{die_count}d{die_faces} x {multiplier_gp} gp"
        return CurrencyRoll(
            die_count=die_count,
            die_faces=die_faces,
            multiplier_cp=multiplier_gp * 100,
            label=label,
        )
    raise ContentLoadError(f"Unsupported class wealth expression in mirror data: {raw_value!r}")



def _register_lookup_aliases(raw_record: Mapping[str, object], *, record_id: str, source: str, lookup: dict[str, str]) -> None:
    for alias in _name_aliases(raw_record):
        lookup[_ref_key(alias, source)] = record_id


def _resolve_record_id(
    reference: str,
    *,
    lookup: Mapping[str, str],
    records: Mapping[str, object],
    record_kind: str,
) -> str:
    name, source = _parse_item_ref(reference)
    key = _ref_key(name, source)
    if key in lookup:
        return lookup[key]
    alias_matches = {
        record_id
        for alias_key, record_id in lookup.items()
        if alias_key.split('|', 1)[0] == slugify(name)
    }
    if len(alias_matches) == 1:
        return next(iter(alias_matches))
    fallback_matches = [
        record_id
        for record_id, record in records.items()
        if hasattr(record, 'name') and slugify(str(getattr(record, 'name'))) == slugify(name)
    ]
    if len(fallback_matches) == 1:
        return fallback_matches[0]
    raise ContentLoadError(f"Mirror {record_kind} reference {reference!r} could not be resolved.")


def _build_skill_catalog(
    skills_doc: Mapping[str, object],
    policy: SourcePolicy,
) -> tuple[dict[str, SkillRecord], dict[str, str]]:
    skills: dict[str, SkillRecord] = {}
    skill_lookup: dict[str, str] = {}
    existing_ids: set[str] = set()
    for raw_skill in skills_doc.get('skill', []):
        if not isinstance(raw_skill, Mapping):
            continue
        source = str(raw_skill.get('source', '')).upper()
        edition = _edition_for_source(source)
        homebrew = _is_homebrew(source, raw_skill)
        official = _is_official(source, raw_skill)
        if not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
            continue
        raw_ability = raw_skill.get('ability')
        if not isinstance(raw_ability, str):
            raise ContentLoadError(f"Skill {_canonical_name(raw_skill)} is missing an ability in mirror data.")
        name = _canonical_name(raw_skill)
        record_id = _record_id_for_name_source(name, source, existing_ids)
        existing_ids.add(record_id)
        record = SkillRecord(
            record_id=record_id,
            name=name,
            source=source,
            edition=edition,
            official=official,
            homebrew=homebrew,
            ability=_ability(raw_ability),
        )
        skills[record.record_id] = record
        _register_lookup_aliases(raw_skill, record_id=record.record_id, source=source, lookup=skill_lookup)
    return skills, skill_lookup


def _build_tool_catalog(items: Mapping[str, ItemRecord]) -> dict[str, ToolRecord]:
    tools: dict[str, ToolRecord] = {}
    for item in items.values():
        if item.is_magical:
            continue
        lowered_tags = {tag.lower() for tag in item.tags}
        category: str | None = None
        if 'ins' in lowered_tags:
            category = 'instrument'
        elif 'at' in lowered_tags:
            category = 'artisan-tool'
        elif 'gs' in lowered_tags:
            category = 'gaming-set'
        elif 't' in lowered_tags:
            category = 'tool'
        if category is None:
            continue
        tools[item.record_id] = ToolRecord(
            record_id=item.record_id,
            name=item.name,
            source=item.source,
            edition=item.edition,
            official=item.official,
            homebrew=item.homebrew,
            category=category,
        )
    return tools


def _resolve_skill_id(reference: str, *, skill_lookup: Mapping[str, str], skills: Mapping[str, SkillRecord]) -> str:
    try:
        return _resolve_record_id(reference, lookup=skill_lookup, records=skills, record_kind='skill')
    except ContentLoadError:
        canonical_reference = _display_skill(reference)
        if canonical_reference == reference:
            raise
        return _resolve_record_id(canonical_reference, lookup=skill_lookup, records=skills, record_kind='skill')


def _resolve_tool_id(reference: str, *, item_lookup: Mapping[str, str], tools: Mapping[str, ToolRecord]) -> str:
    return _resolve_record_id(reference, lookup=item_lookup, records=tools, record_kind='tool')


def _parse_skill_proficiency_data(
    raw_entries: object,
    *,
    skill_lookup: Mapping[str, str],
    skills: Mapping[str, SkillRecord],
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    fixed_ids: list[str] = []
    choice_option_ids: tuple[str, ...] = ()
    choice_count = 0
    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        return (), (), 0
    for entry in raw_entries:
        if isinstance(entry, str):
            fixed_ids.append(_resolve_skill_id(entry, skill_lookup=skill_lookup, skills=skills))
            continue
        if not isinstance(entry, Mapping):
            continue
        for key, value in entry.items():
            if key == 'choose' and isinstance(value, Mapping):
                raw_from = value.get('from')
                if not isinstance(raw_from, Sequence) or isinstance(raw_from, (str, bytes)):
                    raise ContentLoadError(f"Unsupported skill choice data: {value!r}")
                option_ids = tuple(
                    _resolve_skill_id(str(skill_ref), skill_lookup=skill_lookup, skills=skills)
                    for skill_ref in raw_from
                )
                requested_count = int(value.get('count', 1) or 1)
                if choice_option_ids and (choice_option_ids != option_ids or choice_count != requested_count):
                    raise ContentLoadError('Background skill data contains multiple distinct choice groups; normalize this case first.')
                choice_option_ids = tuple(dict.fromkeys(option_ids))
                choice_count = requested_count
            elif isinstance(value, bool) and value:
                fixed_ids.append(_resolve_skill_id(str(key), skill_lookup=skill_lookup, skills=skills))
    return tuple(dict.fromkeys(fixed_ids)), choice_option_ids, choice_count


def _extract_item_refs_from_text(raw_text: str) -> tuple[tuple[str, str], ...]:
    refs = re.findall(r'\{@item ([^|}]+)\|([^|}]+)(?:\|[^}]+)?\}', raw_text)
    return tuple((name.strip(), source.strip().upper()) for name, source in refs)


def _tool_option_ids_by_category(tools: Mapping[str, ToolRecord], *categories: str) -> tuple[str, ...]:
    wanted = set(categories)
    selected = [record for record in tools.values() if record.category in wanted]
    selected.sort(key=lambda record: (record.category, record.name.casefold(), record.record_id))
    return tuple(record.record_id for record in selected)


def _parse_tool_proficiency_data(
    raw_entries: object,
    *,
    item_lookup: Mapping[str, str],
    tools: Mapping[str, ToolRecord],
) -> tuple[tuple[str, ...], tuple[str, ...], int]:
    fixed_ids: list[str] = []
    choice_option_ids: tuple[str, ...] = ()
    choice_count = 0

    def _merge_choice_options(option_ids: tuple[str, ...], requested_count: int) -> None:
        nonlocal choice_option_ids, choice_count
        normalized_option_ids = tuple(dict.fromkeys(option_ids))
        if not normalized_option_ids:
            return
        if choice_option_ids:
            if choice_count != requested_count:
                raise ContentLoadError('Tool proficiency data contains incompatible choice groups; normalize this case first.')
            choice_option_ids = tuple(dict.fromkeys(choice_option_ids + normalized_option_ids))
            return
        choice_option_ids = normalized_option_ids
        choice_count = requested_count

    if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
        return (), (), 0
    for entry in raw_entries:
        if isinstance(entry, str):
            refs = _extract_item_refs_from_text(entry)
            if refs and '\u9009\u62e9' not in entry and '\u4efb\u9009' not in entry:
                for name, source in refs:
                    fixed_ids.append(_resolve_tool_id(f'{name}|{source}', item_lookup=item_lookup, tools=tools))
                continue
            if '\u4e50\u5668' in entry and any(token in entry for token in ('\u4efb\u9009', '\u9009\u62e9', 'choose')):
                option_ids = _tool_option_ids_by_category(tools, 'instrument')
                if not option_ids:
                    raise ContentLoadError('Mirror data requested musical instrument choices, but none were loaded.')
                _merge_choice_options(option_ids, 3 if '3' in entry else 1)
                continue
            if '\u5de5\u5320\u5de5\u5177' in entry and '\u4e50\u5668' in entry and '\u9009\u62e9' in entry:
                option_ids = _tool_option_ids_by_category(tools, 'artisan-tool', 'instrument')
                if not option_ids:
                    raise ContentLoadError('Mirror data requested artisan-tool-or-instrument choices, but none were loaded.')
                _merge_choice_options(option_ids, 1)
                continue
            raise ContentLoadError(f'Unsupported tool proficiency text in mirror data: {entry!r}')
        if not isinstance(entry, Mapping):
            continue
        any_musical_instrument = entry.get('anyMusicalInstrument')
        if isinstance(any_musical_instrument, int):
            option_ids = _tool_option_ids_by_category(tools, 'instrument')
            if not option_ids:
                raise ContentLoadError('Mirror feat/background data requested musical instrument choices, but none were loaded.')
            _merge_choice_options(option_ids, any_musical_instrument)
            continue
        any_artisans_tool = entry.get('anyArtisansTool')
        if isinstance(any_artisans_tool, int):
            option_ids = _tool_option_ids_by_category(tools, 'artisan-tool')
            if not option_ids:
                raise ContentLoadError('Mirror feat/background data requested artisan-tool choices, but none were loaded.')
            _merge_choice_options(option_ids, any_artisans_tool)
            continue
        any_gaming_set = entry.get('anyGamingSet')
        if isinstance(any_gaming_set, int):
            option_ids = _tool_option_ids_by_category(tools, 'gaming-set')
            if not option_ids:
                raise ContentLoadError('Mirror feat/background data requested gaming-set choices, but none were loaded.')
            _merge_choice_options(option_ids, any_gaming_set)
            continue
        for key, value in entry.items():
            if key == 'choose' and isinstance(value, Mapping):
                raw_from = value.get('from')
                if not isinstance(raw_from, Sequence) or isinstance(raw_from, (str, bytes)):
                    raise ContentLoadError(f'Unsupported tool choice data: {value!r}')
                option_ids = tuple(
                    _resolve_tool_id(str(tool_ref), item_lookup=item_lookup, tools=tools)
                    for tool_ref in raw_from
                )
                requested_count = int(value.get('count', 1) or 1)
                _merge_choice_options(tuple(option_ids), requested_count)
            elif isinstance(value, bool) and value:
                fixed_ids.append(_resolve_tool_id(str(key), item_lookup=item_lookup, tools=tools))
    return tuple(dict.fromkeys(fixed_ids)), choice_option_ids, choice_count


def _parse_class_skill_choice_ids(
    record: Mapping[str, object],
    *,
    skill_lookup: Mapping[str, str],
    skills: Mapping[str, SkillRecord],
) -> tuple[tuple[str, ...], int]:
    starting = record.get('startingProficiencies')
    if not isinstance(starting, Mapping):
        raise ContentLoadError(f"Class {_canonical_name(record)} is missing starting proficiencies.")
    raw_skills = starting.get('skills')
    if not isinstance(raw_skills, Sequence) or isinstance(raw_skills, (str, bytes)):
        return (), 0
    all_skill_option_ids = tuple(sorted(skills, key=lambda skill_id: skills[skill_id].name))
    for entry in raw_skills:
        if not isinstance(entry, Mapping):
            continue
        raw_any = entry.get('any')
        if isinstance(raw_any, int) and raw_any > 0:
            return all_skill_option_ids, raw_any
        choose = entry.get('choose')
        if not isinstance(choose, Mapping):
            continue
        raw_from = choose.get('from')
        count = choose.get('count')
        if not isinstance(raw_from, Sequence) or isinstance(raw_from, (str, bytes)) or not isinstance(count, int):
            continue
        option_ids = tuple(
            _resolve_skill_id(str(skill_ref), skill_lookup=skill_lookup, skills=skills)
            for skill_ref in raw_from
        )
        return tuple(dict.fromkeys(option_ids)), count
    return (), 0


def _parse_level_one_progression_value(raw_value: object) -> int:
    if isinstance(raw_value, Sequence) and not isinstance(raw_value, (str, bytes)) and raw_value:
        first = raw_value[0]
        if isinstance(first, int):
            return first
    if isinstance(raw_value, int):
        return raw_value
    return 0


def _parse_progression_values(raw_value: object) -> tuple[int, ...]:
    if isinstance(raw_value, int):
        return (raw_value,)
    if not isinstance(raw_value, Sequence) or isinstance(raw_value, (str, bytes)):
        return ()
    values: list[int] = []
    for entry in raw_value:
        if not isinstance(entry, int):
            return ()
        values.append(int(entry))
    return tuple(values)


def _cumulative_progression(raw_value: object) -> tuple[int, ...]:
    running_total = 0
    totals: list[int] = []
    for value in _parse_progression_values(raw_value):
        running_total += value
        totals.append(running_total)
    return tuple(totals)


def _parse_spell_slot_progression(record: Mapping[str, object]) -> tuple[tuple[int, ...], ...]:
    groups = record.get('classTableGroups')
    if not isinstance(groups, Sequence) or isinstance(groups, (str, bytes)):
        return ()
    for group in groups:
        if not isinstance(group, Mapping):
            continue
        rows = group.get('rowsSpellProgression')
        if isinstance(rows, Sequence) and not isinstance(rows, (str, bytes)):
            progression: list[tuple[int, ...]] = []
            for row in rows:
                if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                    return ()
                slot_counts = tuple(int(value) for value in row if isinstance(value, int))
                progression.append(slot_counts)
            if progression:
                return tuple(progression)
        col_labels = group.get('colLabels')
        rows = group.get('rows')
        if not isinstance(col_labels, Sequence) or isinstance(col_labels, (str, bytes)):
            continue
        if len(col_labels) < 4:
            continue
        if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
            continue
        progression = []
        for row in rows:
            if not isinstance(row, Sequence) or isinstance(row, (str, bytes)):
                return ()
            slot_count: int | None = None
            slot_level: int | None = None
            if len(row) >= 2 and isinstance(row[-1], int) and isinstance(row[-2], int):
                slot_count = row[-2]
                slot_level = row[-1]
            elif len(row) >= 3 and isinstance(row[-2], str) and isinstance(row[-3], int):
                match = re.search(r'(\d+)(?:st|nd|rd|th)', row[-2])
                if match is not None:
                    slot_count = row[-3]
                    slot_level = int(match.group(1))
            if slot_count is None or slot_level is None:
                progression = []
                break
            slot_counts = [0] * slot_level
            slot_counts[slot_level - 1] = slot_count
            progression.append(tuple(slot_counts))
        if progression:
            return tuple(progression)
    return ()


def _parse_class_spellcasting(record: Mapping[str, object]) -> ClassSpellcastingRecord | None:
    raw_ability = record.get('spellcastingAbility')
    if not isinstance(raw_ability, str):
        return None
    cantrip_count = _parse_level_one_progression_value(record.get('cantripProgression'))
    prepared_count = _parse_level_one_progression_value(record.get('preparedSpellsProgression'))
    known_count = _parse_level_one_progression_value(record.get('spellsKnownProgression'))
    cantrip_progression = _parse_progression_values(record.get('cantripProgression'))
    known_progression = _parse_progression_values(record.get('spellsKnownProgression'))
    fixed_known_progression = _cumulative_progression(record.get('spellsKnownProgressionFixed'))
    prepared_progression = _parse_progression_values(record.get('preparedSpellsProgression'))
    slot_progression = _parse_spell_slot_progression(record)
    if prepared_count > 0 or prepared_progression:
        return ClassSpellcastingRecord(
            spellcasting_ability=_ability(raw_ability),
            cantrip_choice_count=cantrip_count,
            spell_choice_count=prepared_count,
            spell_selection_kind=SpellSelectionKind.PREPARED,
            spell_slot_progression=slot_progression,
            cantrip_choice_progression=cantrip_progression,
            spell_choice_progression=prepared_progression,
        )
    spell_choice_progression = known_progression or fixed_known_progression
    if known_count > 0 or cantrip_count > 0 or slot_progression or spell_choice_progression:
        return ClassSpellcastingRecord(
            spellcasting_ability=_ability(raw_ability),
            cantrip_choice_count=cantrip_count,
            spell_choice_count=known_count,
            spell_selection_kind=SpellSelectionKind.KNOWN,
            spell_slot_progression=slot_progression,
            cantrip_choice_progression=cantrip_progression,
            spell_choice_progression=spell_choice_progression,
        )
    return None


def _iter_structured_entries(raw_value: object) -> Sequence[object]:
    if isinstance(raw_value, Sequence) and not isinstance(raw_value, (str, bytes)):
        return raw_value
    return ()



def _iter_options_blocks(raw_value: object):
    if isinstance(raw_value, Mapping):
        if raw_value.get('type') == 'options':
            yield raw_value
        for nested in raw_value.values():
            yield from _iter_options_blocks(nested)
        return
    if isinstance(raw_value, Sequence) and not isinstance(raw_value, (str, bytes)):
        for nested in raw_value:
            yield from _iter_options_blocks(nested)



def _build_optionalfeature_lookup(
    optionalfeatures_doc: Mapping[str, object],
    *,
    policy: SourcePolicy,
) -> dict[tuple[str, str], Mapping[str, object]]:
    lookup: dict[tuple[str, str], Mapping[str, object]] = {}
    for raw_feature in optionalfeatures_doc.get('optionalfeature', []):
        if not isinstance(raw_feature, Mapping):
            continue
        source = str(raw_feature.get('source', '')).upper()
        edition = _edition_for_source(source)
        homebrew = _is_homebrew(source, raw_feature)
        official = _is_official(source, raw_feature)
        if not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
            continue
        for candidate in {str(raw_feature.get('name', '')).strip(), str(raw_feature.get('ENG_name', '')).strip(), _canonical_name(raw_feature)}:
            if candidate:
                lookup[(candidate, source)] = raw_feature
    return lookup



def _class_feature_ref_parts(raw_value: object) -> tuple[str, str, str, int]:
    if not isinstance(raw_value, str):
        raise ContentLoadError(f'Unsupported class feature reference {raw_value!r}.')
    parts = [part.strip() for part in raw_value.split('|')]
    if len(parts) < 4:
        raise ContentLoadError(f'Unsupported class feature reference {raw_value!r}.')
    try:
        level = int(parts[3])
    except ValueError as exc:
        raise ContentLoadError(f'Unsupported class feature reference {raw_value!r}.') from exc
    return parts[0], parts[1], parts[2].upper(), level



def _class_feature_matches_ref(
    raw_feature: Mapping[str, object],
    *,
    feature_name: str,
    class_name: str,
    source: str,
    level: int,
) -> bool:
    if str(raw_feature.get('source', '')).upper() != source:
        return False
    if int(raw_feature.get('level', 0) or 0) != level:
        return False
    class_candidates = {str(raw_feature.get('className', '')).strip(), str(raw_feature.get('className', '')).strip(), str(raw_feature.get('ENG_className', '')).strip()}
    class_candidates.discard('')
    if class_name not in class_candidates:
        return False
    feature_candidates = {str(raw_feature.get('name', '')).strip(), str(raw_feature.get('ENG_name', '')).strip(), _canonical_name(raw_feature)}
    feature_candidates.discard('')
    return feature_name in feature_candidates



def _resolve_class_feature_record(
    raw_reference: object,
    *,
    class_features: Sequence[Mapping[str, object]],
) -> Mapping[str, object]:
    feature_name, class_name, source, level = _class_feature_ref_parts(raw_reference)
    for raw_feature in class_features:
        if _class_feature_matches_ref(raw_feature, feature_name=feature_name, class_name=class_name, source=source, level=level):
            return raw_feature
    raise ContentLoadError(f'Class feature reference {raw_reference!r} could not be resolved in mirror data.')



def _optionalfeature_ref_parts(raw_value: object) -> tuple[str, str]:
    if not isinstance(raw_value, str):
        raise ContentLoadError(f'Unsupported optionalfeature reference {raw_value!r}.')
    parts = [part.strip() for part in raw_value.split('|') if part.strip()]
    if len(parts) == 1:
        return parts[0], 'XPHB'
    if len(parts) < 2:
        raise ContentLoadError(f'Unsupported optionalfeature reference {raw_value!r}.')
    return parts[0], parts[1].upper()



def _optionalfeature_prerequisite_satisfied(
    prerequisite: Mapping[str, object],
    *,
    class_names: frozenset[str],
    level: int,
) -> bool:
    if not isinstance(prerequisite, Mapping):
        return False
    for key, value in prerequisite.items():
        if key == 'level':
            if not isinstance(value, Mapping):
                return False
            raw_level = value.get('level')
            if not isinstance(raw_level, int) or raw_level > level:
                return False
            raw_class = value.get('class')
            if isinstance(raw_class, Mapping):
                candidate_names = {str(raw_class.get('name', '')).strip(), str(raw_class.get('ENG_name', '')).strip()}
                candidate_names.discard('')
                if candidate_names and class_names.isdisjoint(candidate_names):
                    return False
            continue
        return False
    return True



def _optionalfeature_available_at_creation(
    raw_feature: Mapping[str, object],
    *,
    class_names: frozenset[str],
    level: int,
) -> bool:
    prerequisites = raw_feature.get('prerequisite')
    if not isinstance(prerequisites, Sequence) or isinstance(prerequisites, (str, bytes)) or not prerequisites:
        return True
    return any(_optionalfeature_prerequisite_satisfied(block, class_names=class_names, level=level) for block in prerequisites if isinstance(block, Mapping))



def _class_feature_choice_option_metadata(
    *,
    class_id: str,
    feature_name: str,
    option_name: str,
    all_class_ids: tuple[str, ...],
) -> dict[str, object]:
    if (class_id, feature_name, option_name) == ('cleric', 'Divine Order', 'Protector'):
        return {
            'armor_training_grants': ('heavy',),
            'weapon_proficiency_grants': ('martial',),
        }
    if (class_id, feature_name, option_name) == ('cleric', 'Divine Order', 'Thaumaturge'):
        return {
            'spell_choice_bundles': (
                ClassFeatureSpellChoiceBundle(
                    choice_id='thaumaturge-cantrip',
                    label='Thaumaturge cantrip',
                    spell_list_class_ids=('cleric',),
                    cantrip_count=1,
                    spell_selection_kind=SpellSelectionKind.CANTRIP,
                ),
            ),
        }
    if (class_id, feature_name, option_name) == ('druid', 'Primal Order', 'Magician'):
        return {
            'spell_choice_bundles': (
                ClassFeatureSpellChoiceBundle(
                    choice_id='magician-cantrip',
                    label='Magician cantrip',
                    spell_list_class_ids=('druid',),
                    cantrip_count=1,
                    spell_selection_kind=SpellSelectionKind.CANTRIP,
                ),
            ),
        }
    if (class_id, feature_name, option_name) == ('druid', 'Primal Order', 'Warden'):
        return {
            'armor_training_grants': ('medium',),
            'weapon_proficiency_grants': ('martial',),
        }
    if (class_id, feature_name, option_name) == ('warlock', 'Eldritch Invocation Options', 'Armor of Shadows'):
        return {
            'granted_spells': (
                ClassFeatureGrantedSpell(spell_id='mage-armor', selection_kind=SpellSelectionKind.INNATE),
            ),
        }
    if (class_id, feature_name, option_name) == ('warlock', 'Eldritch Invocation Options', 'Pact of the Chain'):
        return {
            'granted_spells': (
                ClassFeatureGrantedSpell(spell_id='find-familiar', selection_kind=SpellSelectionKind.INNATE),
            ),
        }
    if (class_id, feature_name, option_name) == ('warlock', 'Eldritch Invocation Options', 'Pact of the Tome'):
        return {
            'spell_choice_bundles': (
                ClassFeatureSpellChoiceBundle(
                    choice_id='pact-of-the-tome-cantrips',
                    label='Pact of the Tome cantrips',
                    spell_list_class_ids=all_class_ids,
                    cantrip_count=3,
                    spell_selection_kind=SpellSelectionKind.CANTRIP,
                ),
                ClassFeatureSpellChoiceBundle(
                    choice_id='pact-of-the-tome-rituals',
                    label='Pact of the Tome rituals',
                    spell_list_class_ids=all_class_ids,
                    spell_count=2,
                    spell_level=1,
                    spell_selection_kind=SpellSelectionKind.ALWAYS_PREPARED,
                ),
            ),
        }
    return {}



def _class_feature_records_for_class(
    raw_class: Mapping[str, object],
    class_doc: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    source = str(raw_class.get('source', '')).upper()
    class_names = frozenset({str(raw_class.get('name', '')).strip(), str(raw_class.get('ENG_name', '')).strip()}) - {''}
    return tuple(
        raw_feature
        for raw_feature in class_doc.get('classFeature', [])
        if isinstance(raw_feature, Mapping)
        and str(raw_feature.get('source', '')).upper() == source
        and str(raw_feature.get('classSource', '')).upper() == source
        and str(raw_feature.get('className', '')).strip() in class_names
    )


def _resolve_class_feature_record_flexible(
    raw_reference: object,
    *,
    class_features: Sequence[Mapping[str, object]],
    default_source: str,
    class_names: frozenset[str],
) -> Mapping[str, object]:
    if not isinstance(raw_reference, str):
        raise ContentLoadError(f'Unsupported class feature reference {raw_reference!r}.')
    parts = [part.strip() for part in raw_reference.split('|')]
    if len(parts) < 4:
        raise ContentLoadError(f'Unsupported class feature reference {raw_reference!r}.')
    feature_name = parts[0]
    class_name = parts[1] or next(iter(class_names), '')
    source = (parts[2] or default_source).upper()
    try:
        level = int(parts[3])
    except ValueError as exc:
        raise ContentLoadError(f'Unsupported class feature reference {raw_reference!r}.') from exc
    for raw_feature in class_features:
        if str(raw_feature.get('source', '')).upper() != source:
            continue
        if int(raw_feature.get('level', 0) or 0) != level:
            continue
        candidate_classes = {str(raw_feature.get('className', '')).strip(), str(raw_feature.get('ENG_className', '')).strip()} - {''}
        if class_name and candidate_classes and class_name not in candidate_classes:
            continue
        candidate_names = {str(raw_feature.get('name', '')).strip(), str(raw_feature.get('ENG_name', '')).strip(), _canonical_name(raw_feature)} - {''}
        if feature_name in candidate_names:
            return raw_feature
    raise ContentLoadError(f'Class feature reference {raw_reference!r} could not be resolved in mirror data.')


def _parse_class_feature_grants(
    *,
    raw_class: Mapping[str, object],
    class_doc: Mapping[str, object],
) -> tuple[ClassLevelFeatureGrant, ...]:
    class_features = _class_feature_records_for_class(raw_class, class_doc)
    source = str(raw_class.get('source', '')).upper()
    class_names = frozenset({str(raw_class.get('name', '')).strip(), str(raw_class.get('ENG_name', '')).strip()}) - {''}
    grants: list[ClassLevelFeatureGrant] = []
    seen: set[tuple[int, str, str | None, bool]] = set()
    raw_features = raw_class.get('classFeatures')
    if not isinstance(raw_features, Sequence) or isinstance(raw_features, (str, bytes)):
        return ()
    for raw_entry in raw_features:
        grants_subclass_choice = False
        raw_reference = raw_entry
        if isinstance(raw_entry, Mapping):
            raw_reference = raw_entry.get('classFeature')
            grants_subclass_choice = bool(raw_entry.get('gainSubclassFeature'))
        if raw_reference is None:
            continue
        resolved = _resolve_class_feature_record_flexible(raw_reference, class_features=class_features, default_source=source, class_names=class_names)
        level = int(resolved.get('level', 0) or 0)
        if level <= 0:
            continue
        feature_name = _canonical_name(resolved)
        key = (level, feature_name, str(raw_reference), grants_subclass_choice)
        if key in seen:
            continue
        seen.add(key)
        grants.append(
            ClassLevelFeatureGrant(
                level=level,
                feature_name=feature_name,
                feature_reference=(str(raw_reference) if isinstance(raw_reference, str) else None),
                grants_subclass_choice=grants_subclass_choice,
            )
        )
    return tuple(sorted(grants, key=lambda item: (item.level, item.feature_name)))


def _parse_multiclass_requirement_sets(raw_class: Mapping[str, object]) -> tuple[MulticlassRequirementSet, ...]:
    multiclassing = raw_class.get('multiclassing')
    if not isinstance(multiclassing, Mapping):
        return ()
    requirements = multiclassing.get('requirements')
    if not isinstance(requirements, Mapping):
        return ()

    def _convert_requirement_block(block: Mapping[str, object]) -> MulticlassRequirementSet | None:
        minimum_scores: dict[Ability, int] = {}
        for key, value in block.items():
            if not isinstance(value, int):
                return None
            if key.lower() not in {'str', 'dex', 'con', 'int', 'wis', 'cha'}:
                return None
            minimum_scores[_ability(key)] = int(value)
        if not minimum_scores:
            return None
        return MulticlassRequirementSet(minimum_scores=minimum_scores)

    if 'or' in requirements and isinstance(requirements.get('or'), Sequence) and not isinstance(requirements.get('or'), (str, bytes)):
        sets = [
            converted
            for converted in (_convert_requirement_block(block) for block in requirements['or'] if isinstance(block, Mapping))
            if converted is not None
        ]
        return tuple(sets)
    converted = _convert_requirement_block(requirements)
    return (converted,) if converted is not None else ()


def _parse_multiclass_proficiency_grant(
    raw_class: Mapping[str, object],
    *,
    skill_lookup: Mapping[str, str],
    skills: Mapping[str, SkillRecord],
    item_lookup: Mapping[str, str],
    tools: Mapping[str, ToolRecord],
) -> MulticlassProficiencyGrant | None:
    multiclassing = raw_class.get('multiclassing')
    if not isinstance(multiclassing, Mapping):
        return None
    proficiencies = multiclassing.get('proficienciesGained')
    if not isinstance(proficiencies, Mapping):
        return None
    fixed_skill_ids, skill_option_ids, skill_choice_count = _parse_skill_proficiency_data(
        proficiencies.get('skills'),
        skill_lookup=skill_lookup,
        skills=skills,
    )
    tool_proficiency_ids, _tool_option_ids, _tool_choice_count = _parse_tool_proficiency_data(
        proficiencies.get('tools'),
        item_lookup=item_lookup,
        tools=tools,
    )
    grant = MulticlassProficiencyGrant(
        armor_training=tuple(str(value) for value in proficiencies.get('armor', []) if isinstance(value, str)),
        weapon_proficiencies=tuple(str(value) for value in proficiencies.get('weapons', []) if isinstance(value, str)),
        skill_proficiency_ids=fixed_skill_ids,
        tool_proficiency_ids=tool_proficiency_ids,
        skill_option_ids=skill_option_ids,
        skill_choice_count=skill_choice_count,
    )
    if not any((grant.armor_training, grant.weapon_proficiencies, grant.skill_proficiency_ids, grant.tool_proficiency_ids, grant.skill_option_ids, (grant.skill_choice_count,))):
        return None
    return grant


def _parse_subclass_records(
    *,
    class_record_id: str,
    raw_class: Mapping[str, object],
    class_doc: Mapping[str, object],
    policy: SourcePolicy,
) -> tuple[SubclassRecord, ...]:
    raw_subclasses = class_doc.get('subclass')
    if not isinstance(raw_subclasses, Sequence) or isinstance(raw_subclasses, (str, bytes)):
        return ()
    class_name_candidates = {str(raw_class.get('name', '')).strip(), str(raw_class.get('ENG_name', '')).strip()} - {''}
    source = str(raw_class.get('source', '')).upper()
    records: list[SubclassRecord] = []
    for raw_subclass in raw_subclasses:
        if not isinstance(raw_subclass, Mapping):
            continue
        subclass_source = str(raw_subclass.get('source', '')).upper()
        edition = _edition_for_source(subclass_source)
        homebrew = _is_homebrew(subclass_source, raw_subclass)
        official = _is_official(subclass_source, raw_subclass)
        if not policy.allows_source(subclass_source, homebrew=homebrew, edition=edition, official=official):
            continue
        if str(raw_subclass.get('classSource', '')).upper() != source:
            continue
        subclass_class_name = str(raw_subclass.get('className', '')).strip()
        if subclass_class_name not in class_name_candidates:
            continue
        subclass_name = _canonical_name(raw_subclass)
        feature_grants: list[ClassLevelFeatureGrant] = []
        raw_features = raw_subclass.get('subclassFeatures')
        if isinstance(raw_features, Sequence) and not isinstance(raw_features, (str, bytes)):
            for raw_reference in raw_features:
                if not isinstance(raw_reference, str):
                    continue
                parts = [part.strip() for part in raw_reference.split('|')]
                if len(parts) < 6:
                    continue
                try:
                    level = int(parts[5])
                except ValueError:
                    continue
                feature_grants.append(ClassLevelFeatureGrant(level=level, feature_name=parts[0], feature_reference=raw_reference))
        records.append(
            SubclassRecord(
                record_id=f'{class_record_id}:{slugify(subclass_name)}',
                class_id=class_record_id,
                name=subclass_name,
                source=subclass_source,
                edition=edition,
                official=official,
                homebrew=homebrew,
                feature_grants=tuple(sorted(feature_grants, key=lambda item: (item.level, item.feature_name))),
            )
        )
    return tuple(sorted(records, key=lambda item: item.name))


def _parse_class_feature_choice_groups(
    *,
    class_record_id: str,
    raw_class: Mapping[str, object],
    class_doc: Mapping[str, object],
    optionalfeature_lookup: Mapping[tuple[str, str], Mapping[str, object]],
    all_class_ids: tuple[str, ...],
) -> tuple[ClassFeatureChoiceGroup, ...]:
    source = str(raw_class.get('source', '')).upper()
    class_names = frozenset({str(raw_class.get('name', '')).strip(), str(raw_class.get('ENG_name', '')).strip()})
    class_names -= {''}
    class_features = _class_feature_records_for_class(raw_class, class_doc)
    groups: list[ClassFeatureChoiceGroup] = []
    for raw_feature in class_features:
        feature_name = _canonical_name(raw_feature)
        feature_level = int(raw_feature.get('level', 0) or 0)
        option_blocks = tuple(_iter_options_blocks(raw_feature.get('entries')))
        for block_index, raw_block in enumerate(option_blocks, start=1):
            raw_entries = raw_block.get('entries')
            if not isinstance(raw_entries, Sequence) or isinstance(raw_entries, (str, bytes)):
                raise ContentLoadError(f'Class feature {feature_name} has an invalid options block in mirror data.')
            option_records: list[ClassFeatureChoiceOption] = []
            for raw_entry in raw_entries:
                if not isinstance(raw_entry, Mapping):
                    raise ContentLoadError(f'Class feature {feature_name} has an unsupported option entry {raw_entry!r}.')
                entry_type = raw_entry.get('type')
                resolved_option: Mapping[str, object] | None = None
                if entry_type == 'refClassFeature':
                    resolved_option = _resolve_class_feature_record_flexible(raw_entry.get('classFeature'), class_features=class_features, default_source=source, class_names=class_names)
                elif entry_type == 'refOptionalfeature':
                    option_name, option_source = _optionalfeature_ref_parts(raw_entry.get('optionalfeature'))
                    resolved_option = optionalfeature_lookup.get((option_name, option_source))
                    if resolved_option is None:
                        raise ContentLoadError(f'Optional feature reference {raw_entry.get("optionalfeature")!r} could not be resolved in mirror data.')
                    if not _optionalfeature_available_at_creation(resolved_option, class_names=class_names, level=feature_level):
                        continue
                else:
                    raise ContentLoadError(f'Class feature {feature_name} has unsupported option entry type {entry_type!r}.')
                option_name = _canonical_name(resolved_option)
                metadata = _class_feature_choice_option_metadata(
                    class_id=class_record_id,
                    feature_name=feature_name,
                    option_name=option_name,
                    all_class_ids=all_class_ids,
                )
                option_records.append(
                    ClassFeatureChoiceOption(
                        option_id=slugify(option_name),
                        label=option_name,
                        detail=feature_name,
                        armor_training_grants=tuple(metadata.get('armor_training_grants', ())),
                        weapon_proficiency_grants=tuple(metadata.get('weapon_proficiency_grants', ())),
                        spell_choice_bundles=tuple(metadata.get('spell_choice_bundles', ())),
                        granted_spells=tuple(metadata.get('granted_spells', ())),
                    )
                )
            if not option_records:
                continue
            count = int(raw_block.get('count', 1) or 1)
            if feature_level <= 1:
                choice_id = f"class:{class_record_id}:feature:{slugify(feature_name)}"
            else:
                choice_id = f"class:{class_record_id}:feature:{slugify(feature_name)}:level-{feature_level}"
            if len(option_blocks) > 1:
                choice_id = f"{choice_id}:{block_index}"
            groups.append(
                ClassFeatureChoiceGroup(
                    choice_id=choice_id,
                    label=feature_name,
                    prompt=f"Choose {count} option(s) for {feature_name}.",
                    options=tuple(option_records),
                    constraint=SelectionConstraint(required_count=count),
                    level=feature_level,
                    source_feature_name=feature_name,
                )
            )
    return tuple(groups)


def _parse_spell_class_ids(
    raw_spell: Mapping[str, object],
    *,
    spell_lookup_doc: Mapping[str, object],
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> tuple[str, ...]:
    source = str(raw_spell.get('source', '')).upper()
    lookup_bucket = spell_lookup_doc.get(source.lower())
    if not isinstance(lookup_bucket, Mapping):
        return ()
    raw_name = raw_spell.get('name')
    raw_english_name = raw_spell.get('ENG_name')
    entry = None
    if isinstance(raw_name, str):
        entry = lookup_bucket.get(raw_name)
    if entry is None and isinstance(raw_english_name, str):
        entry = lookup_bucket.get(raw_english_name)
    if not isinstance(entry, Mapping):
        return ()
    raw_class_section = entry.get('class')
    if not isinstance(raw_class_section, Mapping):
        return ()
    source_classes = raw_class_section.get(source)
    if not isinstance(source_classes, Mapping):
        return ()
    class_ids: list[str] = []
    for class_name in source_classes:
        class_ids.append(_resolve_record_id(str(class_name), lookup=class_lookup, records=classes, record_kind='class'))
    return tuple(dict.fromkeys(class_ids))


def _build_spell_catalog(
    mirror_base_url: str,
    fetch_json: DocumentFetcher,
    *,
    policy: SourcePolicy,
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> dict[str, CreationSpellRecord]:
    spells_doc = fetch_json(urljoin(mirror_base_url, 'data/spells/spells-xphb.json'))
    spell_lookup_doc = fetch_json(urljoin(mirror_base_url, 'data/generated/gendata-spell-source-lookup.json'))
    spells: dict[str, CreationSpellRecord] = {}
    existing_ids: set[str] = set()
    for raw_spell in spells_doc.get('spell', []):
        if not isinstance(raw_spell, Mapping):
            continue
        source = str(raw_spell.get('source', '')).upper()
        edition = _edition_for_source(source)
        homebrew = _is_homebrew(source, raw_spell)
        official = _is_official(source, raw_spell)
        if not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
            continue
        raw_level = raw_spell.get('level')
        if not isinstance(raw_level, int):
            raise ContentLoadError(f"Spell {_canonical_name(raw_spell)} is missing a numeric level in mirror data.")
        name = _canonical_name(raw_spell)
        record_id = _record_id_for_name_source(name, source, existing_ids)
        existing_ids.add(record_id)
        spells[record_id] = CreationSpellRecord(
            record_id=record_id,
            name=name,
            source=source,
            edition=edition,
            official=official,
            homebrew=homebrew,
            level=raw_level,
            school=str(raw_spell.get('school', '')),
            class_ids=_parse_spell_class_ids(
                raw_spell,
                spell_lookup_doc=spell_lookup_doc,
                class_lookup=class_lookup,
                classes=classes,
            ),
        )
    return spells


def _parse_spell_choice_class_id(
    raw_value: object,
    *,
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> str:
    if not isinstance(raw_value, str):
        raise ContentLoadError(f'Unsupported spell choice reference: {raw_value!r}')
    match = re.search(r'class=([^|]+)', raw_value)
    if not match:
        raise ContentLoadError(f'Unsupported spell choice reference: {raw_value!r}')
    return _resolve_record_id(match.group(1), lookup=class_lookup, records=classes, record_kind='class')


def _parse_magic_initiate_bundles(
    raw_feat: Mapping[str, object],
    *,
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> tuple[FeatSpellChoiceBundle, ...]:
    if _canonical_name(raw_feat) != 'Magic Initiate':
        return ()
    raw_additional_spells = raw_feat.get('additionalSpells')
    if not isinstance(raw_additional_spells, Sequence) or isinstance(raw_additional_spells, (str, bytes)):
        raise ContentLoadError('Magic Initiate is missing additional spell metadata in mirror data.')
    class_ids: list[str] = []
    ability_options: tuple[Ability, ...] = ()
    cantrip_count: int | None = None
    spell_count: int | None = None
    spell_level: int | None = None
    for option in raw_additional_spells:
        if not isinstance(option, Mapping):
            continue
        raw_ability = option.get('ability')
        if isinstance(raw_ability, Mapping):
            choose = raw_ability.get('choose')
            if isinstance(choose, Sequence) and not isinstance(choose, (str, bytes)):
                option_abilities = tuple(_ability(str(value)) for value in choose)
                if not ability_options:
                    ability_options = option_abilities
                elif ability_options != option_abilities:
                    raise ContentLoadError('Magic Initiate ability options do not match across spell-list options.')
        raw_known = option.get('known')
        if isinstance(raw_known, Mapping):
            raw_known_any = raw_known.get('_')
            if isinstance(raw_known_any, Sequence) and raw_known_any:
                first_known = raw_known_any[0]
                if isinstance(first_known, Mapping):
                    raw_choose = first_known.get('choose')
                    class_ids.append(_parse_spell_choice_class_id(raw_choose, class_lookup=class_lookup, classes=classes))
                    count = first_known.get('count', 1)
                    if cantrip_count is None:
                        cantrip_count = int(count or 1)
                    elif cantrip_count != int(count or 1):
                        raise ContentLoadError('Magic Initiate cantrip counts do not match across spell-list options.')
        raw_innate = option.get('innate')
        if isinstance(raw_innate, Mapping):
            raw_any = raw_innate.get('_')
            if isinstance(raw_any, Mapping):
                raw_daily = raw_any.get('daily')
                if isinstance(raw_daily, Mapping):
                    for raw_level, entries in raw_daily.items():
                        if not isinstance(entries, Sequence) or not entries:
                            continue
                        first_entry = entries[0]
                        if not isinstance(first_entry, Mapping):
                            continue
                        class_id = _parse_spell_choice_class_id(first_entry.get('choose'), class_lookup=class_lookup, classes=classes)
                        if class_id not in class_ids:
                            class_ids.append(class_id)
                        if spell_level is None:
                            spell_level = int(raw_level)
                        elif spell_level != int(raw_level):
                            raise ContentLoadError('Magic Initiate spell levels do not match across spell-list options.')
                        if spell_count is None:
                            spell_count = len(entries)
                        elif spell_count != len(entries):
                            raise ContentLoadError('Magic Initiate spell counts do not match across spell-list options.')
    if not class_ids or not ability_options or cantrip_count is None or spell_count is None or spell_level is None:
        raise ContentLoadError('Magic Initiate creation choices could not be normalized from mirror data.')
    return (
        FeatSpellChoiceBundle(
            choice_id='magic-initiate-spellcasting',
            label='Magic Initiate spellcasting',
            spell_list_class_ids=tuple(dict.fromkeys(class_ids)),
            spellcasting_ability_options=ability_options,
            cantrip_count=cantrip_count,
            spell_count=spell_count,
            spell_level=spell_level,
            spell_selection_kind=SpellSelectionKind.INNATE,
        ),
    )


def _parse_feat_proficiency_choice_groups(
    raw_feat: Mapping[str, object],
    *,
    skills: Mapping[str, SkillRecord],
    tools: Mapping[str, ToolRecord],
    item_lookup: Mapping[str, str],
) -> tuple[ProficiencyChoiceGroup, ...]:
    groups: list[ProficiencyChoiceGroup] = []
    raw_skill_tool_language = raw_feat.get('skillToolLanguageProficiencies')
    if isinstance(raw_skill_tool_language, Sequence) and not isinstance(raw_skill_tool_language, (str, bytes)):
        for entry in raw_skill_tool_language:
            if not isinstance(entry, Mapping):
                continue
            raw_choose = entry.get('choose')
            if not isinstance(raw_choose, Sequence) or not raw_choose:
                continue
            first_choose = raw_choose[0]
            if not isinstance(first_choose, Mapping):
                continue
            raw_from = first_choose.get('from')
            if not isinstance(raw_from, Sequence) or isinstance(raw_from, (str, bytes)):
                continue
            count = int(first_choose.get('count', 1) or 1)
            option_ids: list[str] = []
            allowed_categories: list[ProficiencyCategory] = []
            for token in raw_from:
                lowered = str(token).lower()
                if '\u6280\u80fd' in lowered or 'skill' in lowered:
                    option_ids.extend(skills.keys())
                    allowed_categories.append(ProficiencyCategory.SKILL)
                elif '\u5de5\u5177' in lowered or 'tool' in lowered:
                    option_ids.extend(tools.keys())
                    allowed_categories.append(ProficiencyCategory.TOOL)
                else:
                    raise ContentLoadError(f'Unsupported proficiency token in feat data: {token!r}')
            groups.append(
                ProficiencyChoiceGroup(
                    choice_id=f"{slugify(_canonical_name(raw_feat))}-skill-or-tool",
                    label=f"{_canonical_name(raw_feat)} proficiencies",
                    category=CreationChoiceCategory.SKILL_OR_TOOL,
                    allowed_categories=tuple(dict.fromkeys(allowed_categories)),
                    option_ids=tuple(dict.fromkeys(option_ids)),
                    count=count,
                )
            )
    raw_tool_proficiencies = raw_feat.get('toolProficiencies')
    if isinstance(raw_tool_proficiencies, Sequence) and not isinstance(raw_tool_proficiencies, (str, bytes)):
        fixed_ids, choice_option_ids, choice_count = _parse_tool_proficiency_data(
            raw_tool_proficiencies,
            item_lookup=item_lookup,
            tools=tools,
        )
        if choice_option_ids and choice_count > 0:
            groups.append(
                ProficiencyChoiceGroup(
                    choice_id=f"{slugify(_canonical_name(raw_feat))}-tools",
                    label=f"{_canonical_name(raw_feat)} tool choices",
                    category=CreationChoiceCategory.TOOL,
                    allowed_categories=(ProficiencyCategory.TOOL,),
                    option_ids=choice_option_ids,
                    count=choice_count,
                )
            )
    return tuple(groups)


def _build_creation_feat_record(
    raw_feat: Mapping[str, object],
    *,
    policy: SourcePolicy,
    source_metadata: Mapping[str, _SourceMetadata],
    existing_ids: set[str],
    skills: Mapping[str, SkillRecord],
    tools: Mapping[str, ToolRecord],
    item_lookup: Mapping[str, str],
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> FeatRecord | None:
    source = str(raw_feat.get('source', '')).upper()
    homebrew = _is_homebrew(source, raw_feat)
    official = _is_official(source, raw_feat)
    if homebrew and not policy.allow_homebrew:
        return None
    if not official:
        return None
    category = str(raw_feat.get('category', '')).upper()
    edition = _edition_for_source(source)
    metadata = source_metadata.get(source, _SourceMetadata(source=source, author='', group=''))
    if category == 'O':
        if not policy.allows_origin_feat_source(source, homebrew=homebrew, official=official, first_party=metadata.first_party):
            return None
    elif not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
        return None
    name = _canonical_name(raw_feat)
    record_id = _record_id_for_name_source(name, source, existing_ids)
    return FeatRecord(
        record_id=record_id,
        name=name,
        source=source,
        official=official,
        homebrew=homebrew,
        category=category,
        prerequisite=_extract_first_string(raw_feat.get('prerequisite')),
        selectable_for_custom_origin=(
            category == 'O'
            and policy.allows_origin_feat_source(
                source,
                homebrew=homebrew,
                official=official,
                first_party=metadata.first_party,
            )
        ),
        repeatable=bool(raw_feat.get('repeatable', False)),
        proficiency_choice_groups=_parse_feat_proficiency_choice_groups(
            raw_feat,
            skills=skills,
            tools=tools,
            item_lookup=item_lookup,
        ),
        spell_choice_bundles=_parse_magic_initiate_bundles(
            raw_feat,
            class_lookup=class_lookup,
            classes=classes,
        ),
    )


def _parse_feat_reference(reference: str) -> tuple[str, str, str | None]:
    name, source = _parse_item_ref(reference)
    variant: str | None = None
    for delimiter in ('\uff1b', ';'):
        if delimiter in name:
            base_name, variant = name.split(delimiter, 1)
            return base_name.strip(), source, variant.strip()
    return name.strip(), source, None


def _resolve_feat_option(
    reference: str,
    *,
    feat_lookup: Mapping[str, str],
    feats: Mapping[str, FeatRecord],
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> FeatGrantOption:
    feat_name, source, variant = _parse_feat_reference(reference)
    feat_id = _resolve_record_id(f'{feat_name}|{source}', lookup=feat_lookup, records=feats, record_kind='feat')
    feat = feats[feat_id]
    if variant is None:
        return FeatGrantOption(option_id=feat_id, feat_id=feat_id, label=feat.name)
    if feat.name != 'Magic Initiate':
        raise ContentLoadError(f"Unsupported feat variant reference {reference!r}; normalize this feat's subchoices first.")
    class_id = _resolve_record_id(variant, lookup=class_lookup, records=classes, record_kind='class')
    class_name = classes[class_id].name
    return FeatGrantOption(
        option_id=f'{feat_id}:{class_id}',
        feat_id=feat_id,
        label=f'{feat.name} ({class_name})',
        fixed_metadata=(('spell_list_class_id', class_id),),
    )


def _parse_origin_feat_options(
    record: Mapping[str, object],
    *,
    feats: Mapping[str, FeatRecord],
    feat_lookup: Mapping[str, str],
    class_lookup: Mapping[str, str],
    classes: Mapping[str, ClassRecord],
) -> tuple[FeatGrantOption, ...]:
    raw_feats = record.get('feats')
    options: list[FeatGrantOption] = []
    if isinstance(raw_feats, Sequence) and not isinstance(raw_feats, (str, bytes)):
        for feat_entry in raw_feats:
            if isinstance(feat_entry, str):
                options.append(_resolve_feat_option(feat_entry, feat_lookup=feat_lookup, feats=feats, class_lookup=class_lookup, classes=classes))
                continue
            if not isinstance(feat_entry, Mapping):
                continue
            any_from_category = feat_entry.get('anyFromCategory')
            if isinstance(any_from_category, Mapping):
                categories = any_from_category.get('category')
                category_values = [str(categories)] if isinstance(categories, str) else [str(value) for value in categories] if isinstance(categories, Sequence) and not isinstance(categories, (str, bytes)) else []
                if 'O' in {value.upper() for value in category_values}:
                    return ()
            for key, value in feat_entry.items():
                if isinstance(value, bool) and value:
                    options.append(_resolve_feat_option(str(key), feat_lookup=feat_lookup, feats=feats, class_lookup=class_lookup, classes=classes))
    origin_feat = record.get('originFeat')
    if isinstance(origin_feat, str):
        options.append(_resolve_feat_option(origin_feat, feat_lookup=feat_lookup, feats=feats, class_lookup=class_lookup, classes=classes))
    deduped: list[FeatGrantOption] = []
    seen_option_ids: set[str] = set()
    for option in options:
        if option.option_id in seen_option_ids:
            continue
        seen_option_ids.add(option.option_id)
        deduped.append(option)
    return tuple(deduped)

def load_catalog(
    base_url: str,
    policy: SourcePolicy,
    document_fetcher: DocumentFetcher | None = None,
) -> ContentCatalog:
    fetch_json = document_fetcher or _fetch_json_from_url
    mirror_base_url = _normalise_base_url(base_url)

    source_metadata = _load_source_metadata(mirror_base_url, fetch_json)
    items_base_doc = fetch_json(urljoin(mirror_base_url, 'data/items-base.json'))
    items_doc = fetch_json(urljoin(mirror_base_url, 'data/items.json'))
    skills_doc = fetch_json(urljoin(mirror_base_url, 'data/skills.json'))
    races_doc = fetch_json(urljoin(mirror_base_url, 'data/races.json'))
    backgrounds_doc = fetch_json(urljoin(mirror_base_url, 'data/backgrounds.json'))
    feats_doc = fetch_json(urljoin(mirror_base_url, 'data/feats.json'))
    optionalfeatures_doc = fetch_json(urljoin(mirror_base_url, 'data/optionalfeatures.json'))
    class_index_doc = fetch_json(urljoin(mirror_base_url, 'data/class/index.json'))

    items: dict[str, ItemRecord] = {}
    item_lookup: dict[str, str] = {}
    raw_item_records = _iter_item_records(items_base_doc) + _iter_item_records(items_doc)
    for raw_item in raw_item_records:
        record = _build_item_record(raw_item, policy)
        if record is None:
            continue
        items[record.record_id] = record
        _register_item_aliases(raw_item, record, item_lookup)
    for raw_item in raw_item_records:
        _register_item_reprint_aliases(raw_item, item_lookup=item_lookup, items=items)
    for raw_item in raw_item_records:
        record = _build_item_record(raw_item, policy)
        if record is None or record.record_id not in items:
            continue
        ammunition_ref = _parse_weapon_ammunition_type(raw_item)
        if ammunition_ref is None:
            continue
        try:
            ammunition_item_id = _resolve_item_id(ammunition_ref, item_lookup, items)
        except ContentLoadError as exc:
            raise ContentLoadError(f'Weapon ammunition reference {ammunition_ref!r} could not be resolved for item {record.record_id!r}.') from exc
        items[record.record_id] = replace(items[record.record_id], weapon_ammunition_type=ammunition_item_id)

    tools = _build_tool_catalog(items)
    skills, skill_lookup = _build_skill_catalog(skills_doc, policy)

    species: dict[str, SpeciesRecord] = {}
    for raw_species in races_doc.get('race', []):
        if not isinstance(raw_species, Mapping):
            continue
        source = str(raw_species.get('source', '')).upper()
        edition = _edition_for_source(source)
        homebrew = _is_homebrew(source, raw_species)
        official = _is_official(source, raw_species)
        if not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
            continue
        name = _canonical_name(raw_species)
        record_id = str(raw_species.get('id') or slugify(name))
        species[record_id] = SpeciesRecord(
            record_id=record_id,
            name=name,
            source=source,
            edition=edition,
            official=official,
            homebrew=homebrew,
            size_options=_parse_size_options(raw_species.get('size')),
            speed=_parse_speed(raw_species.get('speed')),
            traits=_extract_trait_names(raw_species),
            hit_point_bonus_per_level=int(raw_species.get('hitPointBonusPerLevel', 0) or 0),
            bonus_origin_feat_count=_parse_species_bonus_origin_feat_count(raw_species),
        )

    classes: dict[str, ClassRecord] = {}
    class_lookup: dict[str, str] = {}
    class_contexts: list[tuple[str, Mapping[str, object], Mapping[str, object]]] = []
    if not isinstance(class_index_doc, Mapping):
        raise ContentLoadError('Mirror class index is not a JSON object.')
    class_files = sorted({str(filename) for filename in class_index_doc.values() if isinstance(filename, str)})
    for class_filename in class_files:
        class_doc = fetch_json(urljoin(mirror_base_url, f'data/class/{class_filename}'))
        for raw_class in class_doc.get('class', []):
            if not isinstance(raw_class, Mapping):
                continue
            source = str(raw_class.get('source', '')).upper()
            edition = _edition_for_source(source)
            homebrew = _is_homebrew(source, raw_class)
            official = _is_official(source, raw_class)
            if not policy.allows_source(source, homebrew=homebrew, edition=edition, official=official):
                continue
            name = _canonical_name(raw_class)
            record_id = str(raw_class.get('id') or slugify(name))
            starting = raw_class.get('startingProficiencies')
            if not isinstance(starting, Mapping):
                raise ContentLoadError(f'Class {name} is missing starting proficiencies in mirror data.')
            skill_option_ids, skill_choice_count = _parse_class_skill_choice_ids(
                raw_class,
                skill_lookup=skill_lookup,
                skills=skills,
            )
            raw_tool_entries = starting.get('toolProficiencies', starting.get('tools', []))
            tool_proficiency_ids, class_tool_option_ids, class_tool_choice_count = _parse_tool_proficiency_data(
                raw_tool_entries,
                item_lookup=item_lookup,
                tools=tools,
            )
            hd = raw_class.get('hd')
            if not isinstance(hd, Mapping) or not isinstance(hd.get('faces'), int):
                raise ContentLoadError(f'Class {name} is missing hit-die data in mirror data.')
            classes[record_id] = ClassRecord(
                record_id=record_id,
                name=name,
                source=source,
                edition=edition,
                official=official,
                homebrew=homebrew,
                primary_abilities=_parse_primary_abilities(raw_class),
                hit_die=int(hd['faces']),
                saving_throw_proficiencies=tuple(_ability(str(value)) for value in raw_class.get('proficiency', [])),
                skill_choices=tuple(skills[skill_id].name for skill_id in skill_option_ids),
                skill_choice_count=skill_choice_count,
                armor_training=tuple(str(value) for value in starting.get('armor', []) if isinstance(value, str)),
                weapon_proficiencies=tuple(str(value) for value in starting.get('weapons', []) if isinstance(value, str)),
                tool_proficiencies=tuple(tools[tool_id].name for tool_id in tool_proficiency_ids),
                package_options=_build_packages(
                    owner_id=record_id,
                    owner_name=name,
                    source=source,
                    starting_equipment=raw_class.get('startingEquipment'),
                    items=items,
                    item_lookup=item_lookup,
                ),
                wealth_option=_parse_currency_roll(
                    raw_class.get('wealthRoll')
                    if 'wealthRoll' in raw_class
                    else raw_class.get('startingEquipment', {}).get('goldAlternative')
                    if isinstance(raw_class.get('startingEquipment'), Mapping)
                    else None
                ),
                spellcasting=_parse_class_spellcasting(raw_class),
                class_feature_grants=_parse_class_feature_grants(raw_class=raw_class, class_doc=class_doc),
                subclasses=_parse_subclass_records(class_record_id=record_id, raw_class=raw_class, class_doc=class_doc, policy=policy),
                multiclass_requirement_sets=_parse_multiclass_requirement_sets(raw_class),
                multiclass_proficiency_grant=_parse_multiclass_proficiency_grant(
                    raw_class,
                    skill_lookup=skill_lookup,
                    skills=skills,
                    item_lookup=item_lookup,
                    tools=tools,
                ),
                class_skill_option_ids=skill_option_ids,
                tool_proficiency_ids=tool_proficiency_ids,
                class_tool_option_ids=class_tool_option_ids,
                class_tool_choice_count=class_tool_choice_count,
            )
            class_contexts.append((record_id, raw_class, class_doc))
            _register_lookup_aliases(raw_class, record_id=record_id, source=source, lookup=class_lookup)

    optionalfeature_lookup = _build_optionalfeature_lookup(optionalfeatures_doc, policy=policy)
    all_class_ids = tuple(classes.keys())
    for record_id, raw_class, class_doc in class_contexts:
        classes[record_id] = replace(
            classes[record_id],
            class_feature_choice_groups=_parse_class_feature_choice_groups(
                class_record_id=record_id,
                raw_class=raw_class,
                class_doc=class_doc,
                optionalfeature_lookup=optionalfeature_lookup,
                all_class_ids=all_class_ids,
            ),
        )

    feats: dict[str, FeatRecord] = {}
    feat_lookup: dict[str, str] = {}
    existing_feat_ids: set[str] = set()
    for raw_feat in feats_doc.get('feat', []):
        if not isinstance(raw_feat, Mapping):
            continue
        record = _build_creation_feat_record(
            raw_feat,
            policy=policy,
            source_metadata=source_metadata,
            existing_ids=existing_feat_ids,
            skills=skills,
            tools=tools,
            item_lookup=item_lookup,
            class_lookup=class_lookup,
            classes=classes,
        )
        if record is None:
            continue
        existing_feat_ids.add(record.record_id)
        feats[record.record_id] = record
        _register_feat_aliases(raw_feat, record, feat_lookup)

    backgrounds: dict[str, BackgroundRecord] = {}
    existing_background_ids: set[str] = set()
    for raw_background in backgrounds_doc.get('background', []):
        if not isinstance(raw_background, Mapping):
            continue
        source = str(raw_background.get('source', '')).upper()
        edition = _edition_for_source(source)
        homebrew = _is_homebrew(source, raw_background)
        official = _is_official(source, raw_background)
        metadata = source_metadata.get(source, _SourceMetadata(source=source, author='', group=''))
        if not policy.allows_background_source(source, homebrew=homebrew, official=official, first_party=metadata.first_party):
            continue
        name = _canonical_name(raw_background)
        record_id = _record_id_for_name_source(name, source, existing_background_ids)
        existing_background_ids.add(record_id)
        allowed_asi_abilities, flexible_asi = _parse_background_ability_config(raw_background)
        try:
            skill_proficiency_ids, background_skill_option_ids, background_skill_choice_count = _parse_skill_proficiency_data(
                raw_background.get('skillProficiencies'),
                skill_lookup=skill_lookup,
                skills=skills,
            )
            tool_proficiency_ids, background_tool_option_ids, background_tool_choice_count = _parse_tool_proficiency_data(
                raw_background.get('toolProficiencies'),
                item_lookup=item_lookup,
                tools=tools,
            )
        except ContentLoadError:
            continue
        try:
            origin_feat_options = _parse_origin_feat_options(
                raw_background,
                feats=feats,
                feat_lookup=feat_lookup,
                class_lookup=class_lookup,
                classes=classes,
            )
        except ContentLoadError:
            continue
        backgrounds[record_id] = BackgroundRecord(
            record_id=record_id,
            name=name,
            source=source,
            edition=edition,
            official=official,
            homebrew=homebrew,
            allowed_asi_abilities=allowed_asi_abilities,
            flexible_asi=flexible_asi,
            origin_feat_options=origin_feat_options,
            skill_proficiencies=tuple(skills[skill_id].name for skill_id in skill_proficiency_ids),
            tool_proficiencies=tuple(tools[tool_id].name for tool_id in tool_proficiency_ids),
            package_options=_build_packages(
                owner_id=record_id,
                owner_name=name,
                source=source,
                starting_equipment=raw_background.get('startingEquipment'),
                items=items,
                item_lookup=item_lookup,
            ),
            gold_option_cp=_parse_gold_option_cp(raw_background),
            skill_proficiency_ids=skill_proficiency_ids,
            tool_proficiency_ids=tool_proficiency_ids,
            background_skill_option_ids=background_skill_option_ids,
            background_skill_choice_count=background_skill_choice_count,
            background_tool_option_ids=background_tool_option_ids,
            background_tool_choice_count=background_tool_choice_count,
        )

    spells = _build_spell_catalog(
        mirror_base_url,
        fetch_json,
        policy=policy,
        class_lookup=class_lookup,
        classes=classes,
    )

    if not species or not classes or not backgrounds:
        raise ContentLoadError(
            'The configured 5etools mirror did not return any official character-creation content for the active source policy.'
        )

    return ContentCatalog(
        species=species,
        classes=classes,
        backgrounds=backgrounds,
        feats=feats,
        items=items,
        skills=skills,
        tools=tools,
        spells=spells,
    )






