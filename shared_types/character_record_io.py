from __future__ import annotations

from dataclasses import fields, is_dataclass
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping

from shared_types.models import (
    Ability,
    AbilityMethod,
    CharacterClassLevel,
    CharacterFeatGrant,
    CharacterProficiencySelection,
    CharacterRecord,
    CharacterSpellSelection,
    CharacterSubclassSelection,
    ChoiceSource,
    ChoiceSourceKind,
    CreationChoiceCategory,
    ProficiencyCategory,
    ResolvedAdvancementChoiceRecord,
    ResolvedCreationChoice,
    SpellSelectionKind,
)

CHARACTER_RECORD_SCHEMA_VERSION = 1


def save_character_party(path: str | Path, records_by_controller: Mapping[str, CharacterRecord]) -> None:
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        'schema_version': CHARACTER_RECORD_SCHEMA_VERSION,
        'records': [
            {
                'controller_id': controller_id,
                'record': character_record_to_dict(record),
            }
            for controller_id, record in sorted(records_by_controller.items())
        ],
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding='utf-8')


def load_character_party(path: str | Path) -> dict[str, CharacterRecord]:
    input_path = Path(path)
    try:
        payload = json.loads(input_path.read_text(encoding='utf-8'))
    except OSError as exc:
        raise ValueError(f'Failed to read character party file {input_path}: {exc}') from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f'Character party file {input_path} is not valid JSON: {exc}') from exc
    if not isinstance(payload, Mapping):
        raise ValueError('Character party file must contain a JSON object.')
    schema_version = payload.get('schema_version')
    if schema_version != CHARACTER_RECORD_SCHEMA_VERSION:
        raise ValueError(f'Unsupported character party schema version {schema_version!r}.')
    raw_records = payload.get('records')
    if not isinstance(raw_records, list):
        raise ValueError('Character party file must contain a records list.')
    records: dict[str, CharacterRecord] = {}
    for index, raw_entry in enumerate(raw_records):
        if not isinstance(raw_entry, Mapping):
            raise ValueError(f'Character party record {index} must be an object.')
        controller_id = raw_entry.get('controller_id')
        if not isinstance(controller_id, str) or not controller_id:
            raise ValueError(f'Character party record {index} is missing controller_id.')
        if controller_id in records:
            raise ValueError(f'Character party file contains duplicate controller id {controller_id!r}.')
        raw_record = raw_entry.get('record')
        if not isinstance(raw_record, Mapping):
            raise ValueError(f'Character party record {controller_id!r} is missing a record object.')
        records[controller_id] = character_record_from_dict(raw_record)
    return records


def character_record_to_dict(record: CharacterRecord) -> dict[str, Any]:
    return _to_jsonable(record)


def character_record_from_dict(data: Mapping[str, Any]) -> CharacterRecord:
    return CharacterRecord(
        record_id=_required_str(data, 'record_id'),
        level=_required_int(data, 'level'),
        species_id=_required_str(data, 'species_id'),
        class_id=_required_str(data, 'class_id'),
        background_id=_required_str(data, 'background_id'),
        source_refs=_str_tuple(data.get('source_refs', ())),
        ability_scores=_ability_int_dict(data.get('ability_scores', {})),
        ability_modifiers=_ability_int_dict(data.get('ability_modifiers', {})),
        base_ability_array=_int_tuple(data.get('base_ability_array', ())),
        chosen_ability_method=AbilityMethod(_required_str(data, 'chosen_ability_method')),
        max_hit_points=_required_int(data, 'max_hit_points'),
        proficiency_bonus=_required_int(data, 'proficiency_bonus'),
        saving_throw_proficiencies=_enum_tuple(data.get('saving_throw_proficiencies', ()), Ability),
        class_skill_proficiencies=_str_tuple(data.get('class_skill_proficiencies', ())),
        background_skill_proficiencies=_str_tuple(data.get('background_skill_proficiencies', ())),
        tool_proficiencies=_str_tuple(data.get('tool_proficiencies', ())),
        armor_training=_str_tuple(data.get('armor_training', ())),
        weapon_proficiencies=_str_tuple(data.get('weapon_proficiencies', ())),
        traits=_str_tuple(data.get('traits', ())),
        origin_feats=_str_tuple(data.get('origin_feats', ())),
        inventory={str(key): int(value) for key, value in _mapping(data.get('inventory', {})).items()},
        currency_cp=_required_int(data, 'currency_cp'),
        proficiency_selections=tuple(_proficiency_selection_from_dict(item) for item in _list(data.get('proficiency_selections', ()))),
        spell_selections=tuple(_spell_selection_from_dict(item) for item in _list(data.get('spell_selections', ()))),
        feat_grants=tuple(_feat_grant_from_dict(item) for item in _list(data.get('feat_grants', ()))),
        resolved_creation_choices=tuple(_resolved_creation_choice_from_dict(item) for item in _list(data.get('resolved_creation_choices', ()))),
        class_levels=tuple(_class_level_from_dict(item) for item in _list(data.get('class_levels', ()))),
        subclass_selections=tuple(_subclass_selection_from_dict(item) for item in _list(data.get('subclass_selections', ()))),
        resolved_advancement_choices=tuple(_advancement_choice_from_dict(item) for item in _list(data.get('resolved_advancement_choices', ()))),
        expertise_skill_ids=_str_tuple(data.get('expertise_skill_ids', ())),
        expertise_tool_ids=_str_tuple(data.get('expertise_tool_ids', ())),
        fighting_style_names=_str_tuple(data.get('fighting_style_names', ())),
        weapon_mastery_item_ids=_str_tuple(data.get('weapon_mastery_item_ids', ())),
        class_feature_names=_str_tuple(data.get('class_feature_names', ())),
    )


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return {field.name: _to_jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key.value if isinstance(key, Enum) else key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_to_jsonable(item) for item in value]
    return value


def _choice_source_from_dict(data: Mapping[str, Any]) -> ChoiceSource:
    return ChoiceSource(
        source_kind=ChoiceSourceKind(_required_str(data, 'source_kind')),
        source_id=_required_str(data, 'source_id'),
        source_name=_required_str(data, 'source_name'),
    )


def _proficiency_selection_from_dict(data: Any) -> CharacterProficiencySelection:
    raw = _mapping(data)
    return CharacterProficiencySelection(
        record_id=_required_str(raw, 'record_id'),
        name=_required_str(raw, 'name'),
        category=ProficiencyCategory(_required_str(raw, 'category')),
        source=_choice_source_from_dict(_mapping(raw.get('source'))),
    )


def _spell_selection_from_dict(data: Any) -> CharacterSpellSelection:
    raw = _mapping(data)
    spellcasting_ability = raw.get('spellcasting_ability')
    return CharacterSpellSelection(
        spell_id=_required_str(raw, 'spell_id'),
        spell_name=_required_str(raw, 'spell_name'),
        spell_level=_required_int(raw, 'spell_level'),
        selection_kind=SpellSelectionKind(_required_str(raw, 'selection_kind')),
        source=_choice_source_from_dict(_mapping(raw.get('source'))),
        spellcasting_ability=Ability(spellcasting_ability) if spellcasting_ability is not None else None,
        spell_list_class_id=raw.get('spell_list_class_id') if raw.get('spell_list_class_id') is not None else None,
    )


def _feat_grant_from_dict(data: Any) -> CharacterFeatGrant:
    raw = _mapping(data)
    return CharacterFeatGrant(
        feat_id=_required_str(raw, 'feat_id'),
        feat_name=_required_str(raw, 'feat_name'),
        source=_choice_source_from_dict(_mapping(raw.get('source'))),
        fixed_metadata=_pair_tuple(raw.get('fixed_metadata', ())),
    )


def _resolved_creation_choice_from_dict(data: Any) -> ResolvedCreationChoice:
    raw = _mapping(data)
    return ResolvedCreationChoice(
        choice_id=_required_str(raw, 'choice_id'),
        category=CreationChoiceCategory(_required_str(raw, 'category')),
        source=_choice_source_from_dict(_mapping(raw.get('source'))),
        selected_option_ids=_str_tuple(raw.get('selected_option_ids', ())),
        selected_option_labels=_str_tuple(raw.get('selected_option_labels', ())),
    )


def _class_level_from_dict(data: Any) -> CharacterClassLevel:
    raw = _mapping(data)
    return CharacterClassLevel(class_id=_required_str(raw, 'class_id'), level=_required_int(raw, 'level'))


def _subclass_selection_from_dict(data: Any) -> CharacterSubclassSelection:
    raw = _mapping(data)
    return CharacterSubclassSelection(
        class_id=_required_str(raw, 'class_id'),
        subclass_id=_required_str(raw, 'subclass_id'),
        subclass_name=_required_str(raw, 'subclass_name'),
    )


def _advancement_choice_from_dict(data: Any) -> ResolvedAdvancementChoiceRecord:
    raw = _mapping(data)
    return ResolvedAdvancementChoiceRecord(
        choice_id=_required_str(raw, 'choice_id'),
        category=_required_str(raw, 'category'),
        selected_option_ids=_str_tuple(raw.get('selected_option_ids', ())),
        selected_option_labels=_str_tuple(raw.get('selected_option_labels', ())),
    )


def _required_str(data: Mapping[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str):
        raise ValueError(f'Character record field {key!r} must be a string.')
    return value


def _required_int(data: Mapping[str, Any], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int):
        raise ValueError(f'Character record field {key!r} must be an integer.')
    return value


def _mapping(value: Any) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError('Expected a JSON object while loading a character record.')
    return value


def _list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    raise ValueError('Expected a JSON list while loading a character record.')


def _str_tuple(value: Any) -> tuple[str, ...]:
    return tuple(str(item) for item in _list(value))


def _int_tuple(value: Any) -> tuple[int, ...]:
    return tuple(int(item) for item in _list(value))


def _enum_tuple(value: Any, enum_type) -> tuple[Any, ...]:
    return tuple(enum_type(item) for item in _list(value))


def _ability_int_dict(value: Any) -> dict[Ability, int]:
    return {Ability(key): int(item) for key, item in _mapping(value).items()}


def _pair_tuple(value: Any) -> tuple[tuple[str, str], ...]:
    pairs: list[tuple[str, str]] = []
    for item in _list(value):
        if not isinstance(item, (list, tuple)) or len(item) != 2:
            raise ValueError('Expected metadata entries to be two-item lists.')
        pairs.append((str(item[0]), str(item[1])))
    return tuple(pairs)
