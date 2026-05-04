from __future__ import annotations

from shared_types.conditions import ConditionType, parse_condition_type
from shared_types.encounter_models import (
    ActorSide,
    AttackKind,
    AttackProfile,
    CharacterPlacement,
    EncounterContentCatalog,
    MonsterPlacement,
    RuntimeActorState,
    RuntimeSpellState,
    ZeroHitPointsBehavior,
)
from shared_types.errors import ContentLoadError
from shared_types.models import ABILITY_ORDER, Ability, CharacterRecord, ContentCatalog, SpellSelectionKind
from shared_types.rest import RestRecoveryMode, RestRecoveryRule, RestRecoverySpec, RuntimeResourcePoolState

from rules_engine.encounter_math import ability_modifier
from rules_engine.starter_content import apply_player_passive_features, build_monster_capabilities, build_player_capabilities

from encounter_runtime.equipment import apply_default_equipped_slots, refresh_actor_equipment_state


_SKILL_ABILITY_MAP = {
    'Acrobatics': Ability.DEX,
    'Animal Handling': Ability.WIS,
    'Arcana': Ability.INT,
    'Athletics': Ability.STR,
    'Deception': Ability.CHA,
    'History': Ability.INT,
    'Insight': Ability.WIS,
    'Intimidation': Ability.CHA,
    'Investigation': Ability.INT,
    'Medicine': Ability.WIS,
    'Nature': Ability.INT,
    'Perception': Ability.WIS,
    'Performance': Ability.CHA,
    'Persuasion': Ability.CHA,
    'Religion': Ability.INT,
    'Sleight Of Hand': Ability.DEX,
    'Stealth': Ability.DEX,
    'Survival': Ability.WIS,
}

_SIZE_HEIGHT_FT = {
    'Tiny': 2,
    'Small': 5,
    'Medium': 5,
    'Large': 10,
    'Huge': 15,
    'Gargantuan': 20,
}


_LONG_REST_FULL_RECOVERY = RestRecoverySpec(
    long_rest=RestRecoveryRule(mode=RestRecoveryMode.FULL),
)


def _pc_armor_class(record: CharacterRecord) -> int:
    return 10 + record.ability_modifiers[Ability.DEX]


def _pc_unarmed_attack(record: CharacterRecord) -> AttackProfile:
    if record.class_id == 'monk':
        attack_ability = Ability.DEX if record.ability_modifiers[Ability.DEX] >= record.ability_modifiers[Ability.STR] else Ability.STR
        ability_mod = record.ability_modifiers[attack_ability]
        return AttackProfile(
            attack_id='unarmed-strike',
            name='Unarmed Strike',
            attack_kind=AttackKind.MELEE,
            to_hit_bonus=record.proficiency_bonus + ability_mod,
            reach_ft=5,
            range_ft=None,
            long_range_ft=None,
            damage_dice_count=1,
            damage_die_faces=6,
            damage_bonus=ability_mod,
            damage_type='bludgeoning',
        )
    strength_mod = record.ability_modifiers[Ability.STR]
    return AttackProfile(
        attack_id='unarmed-strike',
        name='Unarmed Strike',
        attack_kind=AttackKind.MELEE,
        to_hit_bonus=record.proficiency_bonus + strength_mod,
        reach_ft=5,
        range_ft=None,
        long_range_ft=None,
        damage_dice_count=0,
        damage_die_faces=0,
        damage_bonus=max(1, 1 + strength_mod),
        damage_type='bludgeoning',
    )


def _normalized_condition_immunities(raw_values: tuple[str, ...]) -> frozenset[ConditionType]:
    normalized: set[ConditionType] = set()
    for raw_value in raw_values:
        parsed = parse_condition_type(raw_value)
        if parsed is not None:
            normalized.add(parsed)
    return frozenset(normalized)


def _build_player_resource_pools(record: CharacterRecord, class_record) -> dict[str, RuntimeResourcePoolState]:
    resource_pools: dict[str, RuntimeResourcePoolState] = {}
    if class_record is not None and class_record.spellcasting is not None:
        progression = class_record.spellcasting.spell_slot_progression
        if progression and record.level > 0 and len(progression) >= record.level:
            slot_row = progression[record.level - 1]
            for slot_level, slot_count in enumerate(slot_row, start=1):
                if slot_count <= 0:
                    continue
                resource_id = f'spell-slot-{slot_level}'
                resource_pools[resource_id] = RuntimeResourcePoolState(
                    resource_id=resource_id,
                    label=f'Level {slot_level} Spell Slots',
                    current=slot_count,
                    maximum=slot_count,
                    category='spell-slot',
                    detail='Recovered on a long rest.',
                    rest_recovery=_LONG_REST_FULL_RECOVERY,
                )
    if record.class_id == 'paladin':
        pool_size = record.level * 5
        resource_pools['lay-on-hands'] = RuntimeResourcePoolState(
            resource_id='lay-on-hands',
            label='Lay on Hands Pool',
            current=pool_size,
            maximum=pool_size,
            category='class-feature',
            detail='Healing pool restored on a long rest.',
            rest_recovery=_LONG_REST_FULL_RECOVERY,
        )
    if record.class_id == 'ranger':
        resource_pools['favored-enemy-hunters-mark'] = RuntimeResourcePoolState(
            resource_id='favored-enemy-hunters-mark',
            label="Favored Enemy: Hunter's Mark",
            current=2,
            maximum=2,
            category='class-feature',
            detail="Free Hunter's Mark casts restored on a long rest.",
            rest_recovery=_LONG_REST_FULL_RECOVERY,
        )
    if record.class_id == 'wizard':
        resource_pools['arcane-recovery'] = RuntimeResourcePoolState(
            resource_id='arcane-recovery',
            label='Arcane Recovery',
            current=1,
            maximum=1,
            category='class-feature',
            detail='Once per long rest after a short rest, recover spell slots totaling 1 level.',
            rest_recovery=_LONG_REST_FULL_RECOVERY,
        )
    return resource_pools


def _finalize_actor_bases(actor: RuntimeActorState) -> None:
    actor.base_armor_class = actor.armor_class
    actor.base_initiative_bonus = actor.initiative_bonus
    actor.base_passive_perception = actor.passive_perception
    actor.base_ability_scores = dict(actor.ability_scores)
    actor.base_ability_modifiers = dict(actor.ability_modifiers)
    actor.base_saving_throw_bonuses = dict(actor.saving_throw_bonuses)
    actor.base_skill_bonuses = dict(actor.skill_bonuses)


def _build_player_spells(
    record: CharacterRecord,
    *,
    encounter_catalog: EncounterContentCatalog,
    resource_pools: dict[str, RuntimeResourcePoolState],
) -> dict[str, RuntimeSpellState]:
    spells: dict[str, RuntimeSpellState] = {}
    for selection in record.spell_selections:
        spell_record = encounter_catalog.spells.get(selection.spell_id)
        if spell_record is None:
            raise ContentLoadError(f"Spell {selection.spell_id!r} is missing from the encounter spell catalog.")
        remaining_uses = None
        max_uses = None
        resource_pool_id = None
        rest_recovery = RestRecoverySpec()
        if spell_record.level > 0:
            if selection.selection_kind == SpellSelectionKind.INNATE:
                remaining_uses = 1
                max_uses = 1
                rest_recovery = _LONG_REST_FULL_RECOVERY
            else:
                resource_pool_id = f'spell-slot-{spell_record.level}'
                if resource_pool_id not in resource_pools:
                    raise ContentLoadError(
                        f"Spell {selection.spell_id!r} requires resource pool {resource_pool_id!r}, but the compiled actor does not have it."
                    )
        spells[spell_record.record_id] = RuntimeSpellState(
            option_id=spell_record.record_id,
            name=spell_record.name,
            source=spell_record.source,
            action_cost=spell_record.action_cost,
            range_ft=spell_record.range_ft,
            remaining_uses=remaining_uses,
            level=spell_record.level,
            casting_time_seconds=spell_record.casting_time_seconds,
            perceptibility=spell_record.perceptibility,
            material_component_cost_cp=spell_record.material_component_cost_cp,
            material_component_consumed=spell_record.material_component_consumed,
            material_component_item_keywords=spell_record.material_component_item_keywords,
            material_component_focus_tags=spell_record.material_component_focus_tags,
            can_cast_as_ritual=spell_record.can_cast_as_ritual,
            ritual_additional_cast_seconds=spell_record.ritual_additional_cast_seconds,
            effect_type=spell_record.effect_type,
            max_uses=max_uses,
            concentration=spell_record.concentration,
            capability=spell_record.capability,
            runtime_support=spell_record.runtime_support,
            rest_recovery=rest_recovery,
            resource_pool_id=resource_pool_id,
        )
    return spells


def compile_player_actor(
    placement: CharacterPlacement,
    *,
    character_catalog: ContentCatalog,
    encounter_catalog: EncounterContentCatalog,
) -> RuntimeActorState:
    record = placement.record
    species = character_catalog.species.get(record.species_id)
    if species is None:
        raise ContentLoadError(f"Species {record.species_id!r} is not available for runtime compilation.")
    class_record = character_catalog.classes.get(record.class_id)
    spellcasting_ability = class_record.spellcasting.spellcasting_ability if class_record is not None and class_record.spellcasting is not None else None
    spell_save_dc = 8 + record.proficiency_bonus + record.ability_modifiers[spellcasting_ability] if spellcasting_ability is not None else None
    spell_attack_bonus = record.proficiency_bonus + record.ability_modifiers[spellcasting_ability] if spellcasting_ability is not None else None
    saving_throw_bonuses = {
        ability: record.ability_modifiers[ability] + (record.proficiency_bonus if ability in record.saving_throw_proficiencies else 0)
        for ability in ABILITY_ORDER
    }
    skill_bonuses = {}
    for skill in set(record.class_skill_proficiencies + record.background_skill_proficiencies):
        ability = _SKILL_ABILITY_MAP.get(skill.title(), Ability.INT)
        skill_bonuses[skill.title()] = record.proficiency_bonus + record.ability_modifiers[ability]
    attack = _pc_unarmed_attack(record)
    passive_perception = 10 + skill_bonuses.get('Perception', record.ability_modifiers[Ability.WIS])
    resource_pools = _build_player_resource_pools(record, class_record)
    actor = RuntimeActorState(
        actor_id=placement.actor_id,
        name=f'PC {record.record_id}',
        side=ActorSide.PLAYER,
        source_refs=record.source_refs,
        size=(species.size_options[0] if species.size_options else 'Medium'),
        alignment=None,
        creature_type='humanoid',
        armor_class=_pc_armor_class(record),
        max_hit_points=record.max_hit_points,
        current_hit_points=record.max_hit_points,
        position=placement.position,
        speed_ft=species.speed,
        climb_speed_ft=0,
        swim_speed_ft=0,
        fly_speed_ft=0,
        hover=False,
        occupied_height_ft=5,
        movement_spent_ft=0,
        dash_bonus_ft=0,
        remaining_movement_ft=species.speed,
        initiative_bonus=record.ability_modifiers[Ability.DEX],
        level=record.level,
        proficiency_bonus=record.proficiency_bonus,
        passive_perception=passive_perception,
        ability_scores=dict(record.ability_scores),
        ability_modifiers=dict(record.ability_modifiers),
        saving_throw_bonuses=saving_throw_bonuses,
        skill_bonuses=skill_bonuses,
        attacks={attack.attack_id: attack},
        spells=_build_player_spells(record, encounter_catalog=encounter_catalog, resource_pools=resource_pools),
        capabilities=build_player_capabilities(record, character_catalog.items),
        resource_pools=resource_pools,
        hit_die_faces=(class_record.hit_die if class_record is not None else 0),
        total_hit_dice=record.level,
        remaining_hit_dice=record.level,
        spellcasting_ability=spellcasting_ability,
        spell_save_dc=spell_save_dc,
        spell_attack_bonus=spell_attack_bonus,
        damage_immunities=frozenset(),
        damage_resistances=frozenset(),
        base_damage_resistances=frozenset(),
        condition_immunities=frozenset(),
        base_condition_immunities=frozenset(),
        carried_item_counts={item_id: quantity for item_id, quantity in record.inventory.items() if quantity > 0},
        condition_instances=(),
        character_record=record,
        zero_hit_points_behavior=ZeroHitPointsBehavior.DEATH_SAVES,
    )
    apply_default_equipped_slots(actor, character_catalog.items)
    refresh_actor_equipment_state(actor, character_catalog.items, unarmed_attack=attack)
    apply_player_passive_features(actor, record, character_catalog.items)
    _finalize_actor_bases(actor)
    return actor


def compile_monster_actor_from_record(
    monster,
    *,
    actor_id: str,
    position,
    monster_catalog: EncounterContentCatalog,
) -> RuntimeActorState:
    ability_modifiers = {ability: ability_modifier(score) for ability, score in monster.ability_scores.items()}
    saving_throw_bonuses = {ability: monster.save_bonuses.get(ability, ability_modifiers[ability]) for ability in ABILITY_ORDER}
    spells = {}
    for option in monster.spell_options:
        spell_record = monster_catalog.spells.get(option.spell_record_id)
        if spell_record is None or (spell_record.effect_type is None and spell_record.capability is None):
            continue
        spells[option.option_id] = RuntimeSpellState(
            option_id=option.option_id,
            name=spell_record.name,
            source=spell_record.source,
            level=spell_record.level,
            casting_time_seconds=spell_record.casting_time_seconds,
            perceptibility=spell_record.perceptibility,
            material_component_cost_cp=spell_record.material_component_cost_cp,
            material_component_consumed=spell_record.material_component_consumed,
            material_component_item_keywords=spell_record.material_component_item_keywords,
            material_component_focus_tags=spell_record.material_component_focus_tags,
            can_cast_as_ritual=spell_record.can_cast_as_ritual,
            ritual_additional_cast_seconds=spell_record.ritual_additional_cast_seconds,
            effect_type=spell_record.effect_type,
            action_cost=option.action_cost_override or spell_record.action_cost,
            range_ft=spell_record.range_ft,
            remaining_uses=option.uses_per_day,
            max_uses=option.uses_per_day,
            concentration=spell_record.concentration,
            capability=spell_record.capability,
            runtime_support=spell_record.runtime_support,
        )
    actor = RuntimeActorState(
        actor_id=actor_id,
        name=monster.name,
        side=ActorSide.MONSTER,
        source_refs=(monster.source,),
        size=monster.size,
        alignment=monster.alignment,
        creature_type=monster.creature_type,
        armor_class=monster.armor_class,
        max_hit_points=monster.max_hit_points,
        current_hit_points=monster.max_hit_points,
        position=position,
        speed_ft=monster.speed_ft,
        climb_speed_ft=monster.climb_speed_ft,
        swim_speed_ft=0,
        fly_speed_ft=0,
        hover=False,
        occupied_height_ft=_SIZE_HEIGHT_FT.get(monster.size, 5),
        movement_spent_ft=0,
        dash_bonus_ft=0,
        remaining_movement_ft=monster.speed_ft,
        initiative_bonus=ability_modifiers[Ability.DEX],
        level=0,
        proficiency_bonus=monster.proficiency_bonus,
        passive_perception=monster.passive_perception,
        ability_scores=dict(monster.ability_scores),
        ability_modifiers=ability_modifiers,
        saving_throw_bonuses=saving_throw_bonuses,
        skill_bonuses=dict(monster.skill_bonuses),
        attacks={attack.attack_id: attack for attack in monster.attacks},
        spells=spells,
        capabilities=build_monster_capabilities(monster),
        spellcasting_ability=monster.spellcasting_ability,
        spell_save_dc=monster.spell_save_dc,
        spell_attack_bonus=monster.spell_attack_bonus,
        damage_immunities=frozenset(monster.damage_immunities),
        damage_resistances=frozenset(monster.damage_resistances),
        base_damage_resistances=frozenset(monster.damage_resistances),
        condition_immunities=_normalized_condition_immunities(monster.condition_immunities),
        condition_instances=(),
        character_record=None,
        zero_hit_points_behavior=ZeroHitPointsBehavior.DIE,
    )
    _finalize_actor_bases(actor)
    return actor


def compile_monster_actor(
    placement: MonsterPlacement,
    *,
    monster_catalog: EncounterContentCatalog,
) -> RuntimeActorState:
    monster = monster_catalog.monsters.get(placement.monster_id)
    if monster is None:
        raise ContentLoadError(f"Monster {placement.monster_id!r} is not available under the active monster policy.")
    return compile_monster_actor_from_record(
        monster,
        actor_id=placement.actor_id,
        position=placement.position,
        monster_catalog=monster_catalog,
    )
