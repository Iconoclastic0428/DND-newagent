from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import replace

from shared_types.equipment import ArmorCategory, EquipmentSlot
from shared_types.encounter_models import ActiveEffectState, AttackKind, AttackProfile, AttackUsageKind, RuntimeActorState
from shared_types.models import Ability, ItemRecord


_SIMPLE_WEAPON_MARKERS = ('simple', '??')
_MARTIAL_WEAPON_MARKERS = ('martial', '??')
_FINESSE_OR_LIGHT_MARKERS = ('finesse', 'light', '??', '??')

_ARMOR_DON_TIME_SECONDS = {
    ArmorCategory.LIGHT: 60,
    ArmorCategory.MEDIUM: 300,
    ArmorCategory.HEAVY: 600,
}

_ARMOR_DOFF_TIME_SECONDS = {
    ArmorCategory.LIGHT: 60,
    ArmorCategory.MEDIUM: 60,
    ArmorCategory.HEAVY: 300,
}


def default_unarmed_attack(actor: RuntimeActorState) -> AttackProfile:
    strength_mod = actor.ability_modifiers.get(Ability.STR, 0)
    return AttackProfile(
        attack_id='unarmed-strike',
        name='Unarmed Strike',
        attack_kind=AttackKind.MELEE,
        to_hit_bonus=actor.proficiency_bonus + strength_mod,
        reach_ft=5,
        range_ft=None,
        long_range_ft=None,
        damage_dice_count=0,
        damage_die_faces=0,
        damage_bonus=max(1, 1 + strength_mod),
        damage_type='bludgeoning',
    )


def item_is_weapon(item: ItemRecord | None) -> bool:
    return bool(item and 'weapon' in item.tags and item.weapon_damage_dice_count and item.weapon_damage_die_faces and item.weapon_damage_type)



def item_is_shield(item: ItemRecord | None) -> bool:
    return bool(item and item.armor_category == ArmorCategory.SHIELD)



def item_is_armor(item: ItemRecord | None) -> bool:
    return bool(item and item.armor_category in {ArmorCategory.LIGHT, ArmorCategory.MEDIUM, ArmorCategory.HEAVY})



def armor_don_time_seconds(item: ItemRecord) -> int:
    if item.armor_category not in _ARMOR_DON_TIME_SECONDS:
        raise ValueError(f'Item {item.record_id!r} is not timed armor.')
    if item.armor_don_time_seconds is not None:
        return item.armor_don_time_seconds
    return _ARMOR_DON_TIME_SECONDS[item.armor_category]



def armor_doff_time_seconds(item: ItemRecord) -> int:
    if item.armor_category not in _ARMOR_DOFF_TIME_SECONDS:
        raise ValueError(f'Item {item.record_id!r} is not timed armor.')
    if item.armor_doff_time_seconds is not None:
        return item.armor_doff_time_seconds
    return _ARMOR_DOFF_TIME_SECONDS[item.armor_category]



def _normalize_slot_state_from_legacy(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> None:
    if actor.equipped_armor_item_id is None and actor.worn_armor_item_id is not None:
        actor.equipped_armor_item_id = actor.worn_armor_item_id
    if actor.main_hand_item_id is None and actor.off_hand_item_id is None:
        held_items = list(actor.held_item_ids)
        if held_items:
            actor.main_hand_item_id = held_items.pop(0)
        if actor.worn_shield_item_id is not None:
            actor.off_hand_item_id = actor.worn_shield_item_id
        elif held_items:
            actor.off_hand_item_id = held_items.pop(0)
    elif actor.off_hand_item_id is None and actor.worn_shield_item_id is not None:
        actor.off_hand_item_id = actor.worn_shield_item_id

    main_item = item_catalog.get(actor.main_hand_item_id) if actor.main_hand_item_id is not None else None
    if item_is_shield(main_item):
        if actor.off_hand_item_id is None:
            actor.off_hand_item_id = actor.main_hand_item_id
        actor.main_hand_item_id = None



def _sync_legacy_equipment_state(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> None:
    _normalize_slot_state_from_legacy(actor, item_catalog)
    hand_items: list[str] = []
    main_item = item_catalog.get(actor.main_hand_item_id) if actor.main_hand_item_id is not None else None
    off_item = item_catalog.get(actor.off_hand_item_id) if actor.off_hand_item_id is not None else None
    if actor.main_hand_item_id is not None and not item_is_shield(main_item):
        hand_items.append(actor.main_hand_item_id)
    if actor.off_hand_item_id is not None and not item_is_shield(off_item):
        hand_items.append(actor.off_hand_item_id)
    actor.held_item_ids = tuple(hand_items)
    actor.worn_armor_item_id = actor.equipped_armor_item_id
    actor.worn_shield_item_id = actor.off_hand_item_id if item_is_shield(off_item) else None



def hand_slot_item_ids(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> tuple[str, ...]:
    _sync_legacy_equipment_state(actor, item_catalog)
    return tuple(item_id for item_id in (actor.main_hand_item_id, actor.off_hand_item_id) if item_id is not None)



def held_count(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord] | None = None) -> int:
    if item_catalog is None:
        return sum(1 for held_item_id in actor.held_item_ids if held_item_id == item_id)
    return sum(1 for hand_item_id in hand_slot_item_ids(actor, item_catalog) if hand_item_id == item_id)



def equipped_count(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord] | None = None) -> int:
    if item_catalog is None:
        return held_count(actor, item_id) + (1 if actor.worn_armor_item_id == item_id else 0) + (1 if actor.worn_shield_item_id == item_id else 0)
    return held_count(actor, item_id, item_catalog) + (1 if actor.equipped_armor_item_id == item_id else 0)



def carried_quantity(actor: RuntimeActorState, item_id: str) -> int:
    return actor.carried_item_counts.get(item_id, 0)


def item_weight_lb(item: ItemRecord | None) -> float:
    if item is None or item.weight_lb is None:
        return 0.0
    return max(0.0, float(item.weight_lb))


def carried_item_weight_lb(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> float:
    return sum(item_weight_lb(item_catalog.get(item_id)) * quantity for item_id, quantity in actor.carried_item_counts.items() if quantity > 0)


def supported_actor_weight_lb(state, actor_id: str, item_catalog: dict[str, ItemRecord]) -> float:
    actor = state.actors.get(actor_id)
    if actor is None:
        return 0.0
    total = float(getattr(actor, 'body_weight_lb', 0.0) or 0.0) + carried_item_weight_lb(actor, item_catalog)
    for rider in state.actors.values():
        if rider.mounted_on_actor_id == actor_id:
            total += supported_actor_weight_lb(state, rider.actor_id, item_catalog)
    return total



def stowed_quantity(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord] | None = None) -> int:
    return max(0, carried_quantity(actor, item_id) - equipped_count(actor, item_id, item_catalog))



def is_item_held(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord] | None = None) -> bool:
    if item_catalog is None:
        return held_count(actor, item_id) > 0
    return held_count(actor, item_id, item_catalog) > 0



def required_hand_count(item: ItemRecord | None) -> int:
    if item is None:
        return 1
    if item_is_shield(item):
        return 1
    if item_is_weapon(item) and 'two-handed' in item.weapon_properties:
        return 2
    return 1



def hands_used(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> int:
    _sync_legacy_equipment_state(actor, item_catalog)
    total = 0
    main_item = item_catalog.get(actor.main_hand_item_id) if actor.main_hand_item_id is not None else None
    off_item = item_catalog.get(actor.off_hand_item_id) if actor.off_hand_item_id is not None else None
    if main_item is not None:
        total += required_hand_count(main_item)
    if off_item is not None:
        total += 1 if item_is_shield(off_item) else required_hand_count(off_item)
    return total



def free_hands(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> int:
    return max(0, 2 - hands_used(actor, item_catalog))



def can_hold_item(actor: RuntimeActorState, item: ItemRecord | None, item_catalog: dict[str, ItemRecord]) -> bool:
    if item is None:
        return False
    required = required_hand_count(item)
    if required >= 2:
        return actor.main_hand_item_id is None and actor.off_hand_item_id is None
    if actor.main_hand_item_id is None or actor.off_hand_item_id is None:
        return True
    return False



def hand_slot_for_item(actor: RuntimeActorState, item_id: str) -> EquipmentSlot | None:
    if actor.main_hand_item_id == item_id:
        return EquipmentSlot.MAIN_HAND
    if actor.off_hand_item_id == item_id:
        return EquipmentSlot.OFF_HAND
    return None



def first_available_hand_slot(actor: RuntimeActorState, item: ItemRecord | None, item_catalog: dict[str, ItemRecord]) -> EquipmentSlot | None:
    if item is None:
        return None
    if item_is_shield(item):
        return EquipmentSlot.OFF_HAND if actor.off_hand_item_id is None else None
    if required_hand_count(item) >= 2:
        if actor.main_hand_item_id is None and actor.off_hand_item_id is None:
            return EquipmentSlot.MAIN_HAND
        return None
    if actor.main_hand_item_id is None:
        return EquipmentSlot.MAIN_HAND
    if actor.off_hand_item_id is None:
        return EquipmentSlot.OFF_HAND
    return None



def clear_equipped_slot(actor: RuntimeActorState, slot: EquipmentSlot) -> None:
    if slot == EquipmentSlot.MAIN_HAND:
        actor.main_hand_item_id = None
        return
    if slot == EquipmentSlot.OFF_HAND:
        actor.off_hand_item_id = None
        return
    if slot == EquipmentSlot.ARMOR:
        actor.equipped_armor_item_id = None
        return
    raise ValueError(f'Unsupported equipment slot: {slot.value}.')



def equip_item_to_slot(actor: RuntimeActorState, item_id: str, *, slot: EquipmentSlot, item_catalog: dict[str, ItemRecord]) -> None:
    _normalize_slot_state_from_legacy(actor, item_catalog)
    item = item_catalog.get(item_id)
    if item is None:
        raise ValueError(f'Unknown equipment item: {item_id!r}.')
    if slot == EquipmentSlot.ARMOR:
        actor.equipped_armor_item_id = item_id
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    if slot == EquipmentSlot.MAIN_HAND:
        actor.main_hand_item_id = item_id
        if required_hand_count(item) >= 2:
            actor.off_hand_item_id = None
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    if slot == EquipmentSlot.OFF_HAND:
        actor.off_hand_item_id = item_id
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    raise ValueError(f'Unsupported equipment slot: {slot.value}.')



def append_held_item(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord]) -> None:
    _normalize_slot_state_from_legacy(actor, item_catalog)
    if actor.main_hand_item_id == item_id or actor.off_hand_item_id == item_id:
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    item = item_catalog.get(item_id)
    slot = first_available_hand_slot(actor, item, item_catalog)
    if slot is None:
        raise ValueError(f'No free hand slot available for {item_id!r}.')
    equip_item_to_slot(actor, item_id, slot=slot, item_catalog=item_catalog)



def remove_held_item(actor: RuntimeActorState, item_id: str, item_catalog: dict[str, ItemRecord]) -> None:
    _normalize_slot_state_from_legacy(actor, item_catalog)
    slot = hand_slot_for_item(actor, item_id)
    if slot is None:
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    clear_equipped_slot(actor, slot)
    removed = False
    next_held_items: list[str] = []
    for held_item_id in actor.held_item_ids:
        if not removed and held_item_id == item_id:
            removed = True
            continue
        next_held_items.append(held_item_id)
    actor.held_item_ids = tuple(next_held_items)
    if actor.worn_shield_item_id == item_id:
        actor.worn_shield_item_id = None
    _sync_legacy_equipment_state(actor, item_catalog)



def clear_equipped_items(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> None:
    actor.main_hand_item_id = None
    actor.off_hand_item_id = None
    actor.equipped_armor_item_id = None
    actor.held_item_ids = ()
    actor.worn_armor_item_id = None
    actor.worn_shield_item_id = None
    _sync_legacy_equipment_state(actor, item_catalog)



def add_carried_item(actor: RuntimeActorState, item_id: str, quantity: int = 1) -> None:
    actor.carried_item_counts[item_id] = actor.carried_item_counts.get(item_id, 0) + quantity



def remove_carried_item(actor: RuntimeActorState, item_id: str, quantity: int = 1) -> None:
    remaining = actor.carried_item_counts.get(item_id, 0) - quantity
    if remaining > 0:
        actor.carried_item_counts[item_id] = remaining
    else:
        actor.carried_item_counts.pop(item_id, None)



def actor_is_proficient_with_weapon(actor: RuntimeActorState, item: ItemRecord) -> bool:
    record = actor.character_record
    if record is None:
        return True
    proficiencies = tuple(str(value).strip().lower() for value in record.weapon_proficiencies)
    if item.record_id.lower() in proficiencies or item.name.strip().lower() in proficiencies:
        return True
    if item.weapon_category == 'simple' and any(any(marker in prof for marker in _SIMPLE_WEAPON_MARKERS) for prof in proficiencies):
        return True
    if item.weapon_category == 'martial' and any(any(marker in prof for marker in _MARTIAL_WEAPON_MARKERS) for prof in proficiencies):
        return True
    if item.weapon_category == 'martial' and any(any(marker in prof for marker in _FINESSE_OR_LIGHT_MARKERS) for prof in proficiencies):
        return any(prop in item.weapon_properties for prop in ('finesse', 'light'))
    return False



def actor_is_trained_with_armor(actor: RuntimeActorState, item: ItemRecord) -> bool:
    record = actor.character_record
    if record is None:
        return True
    if item_is_shield(item):
        return any(str(value).strip().lower() == 'shield' for value in record.armor_training)
    if item.armor_category is None:
        return False
    return any(str(value).strip().lower() == item.armor_category.value for value in record.armor_training)



def compute_equipped_armor_class(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord], *, active_effects: Mapping[str, ActiveEffectState] | None = None) -> int:
    _sync_legacy_equipment_state(actor, item_catalog)
    dex_mod = actor.ability_modifiers.get(Ability.DEX, 0)
    base_armor_class = 10 + dex_mod
    record = actor.character_record
    if actor.equipped_armor_item_id is None and record is not None and record.class_id == 'barbarian':
        base_armor_class = max(base_armor_class, 10 + dex_mod + actor.ability_modifiers.get(Ability.CON, 0))
    if actor.equipped_armor_item_id is None and record is not None and record.class_id == 'monk':
        base_armor_class = max(base_armor_class, 10 + dex_mod + actor.ability_modifiers.get(Ability.WIS, 0))
    if actor.equipped_armor_item_id is not None:
        armor = item_catalog.get(actor.equipped_armor_item_id)
        if armor is not None and armor.armor_base_ac is not None:
            base_armor_class = armor.armor_base_ac
            if armor.armor_category == ArmorCategory.LIGHT:
                base_armor_class += dex_mod
            elif armor.armor_category == ArmorCategory.MEDIUM:
                dex_cap = armor.armor_dex_cap if armor.armor_dex_cap is not None else dex_mod
                base_armor_class += min(dex_mod, dex_cap)
    if active_effects:
        for effect in active_effects.values():
            if actor.actor_id not in effect.target_actor_ids:
                continue
            if effect.definition.armor_class_base_override is None:
                continue
            override_value = effect.definition.armor_class_base_override
            if effect.definition.armor_class_base_add_dex_modifier:
                override_value += dex_mod
            base_armor_class = max(base_armor_class, override_value)
    off_hand_item = item_catalog.get(actor.off_hand_item_id) if actor.off_hand_item_id is not None else None
    if off_hand_item is not None and item_is_shield(off_hand_item):
        if off_hand_item.shield_ac_bonus is not None and actor_is_trained_with_armor(actor, off_hand_item):
            base_armor_class += off_hand_item.shield_ac_bonus
    return base_armor_class



def _weapon_display_name(item: ItemRecord, suffix: str | None = None) -> str:
    return item.name if not suffix else f'{item.name} ({suffix})'



def _weapon_attack_profile(
    actor: RuntimeActorState,
    *,
    item: ItemRecord,
    attack_id: str,
    name: str,
    attack_kind: AttackKind,
    usage_kind: AttackUsageKind,
    attack_ability: Ability,
    damage_ability: Ability,
    damage_dice_count: int,
    damage_die_faces: int,
    required_hand_count_value: int,
    attack_ability_override: Ability | None = None,
    damage_ability_override: Ability | None = None,
    damage_dice_count_override: int | None = None,
    damage_die_faces_override: int | None = None,
    damage_type_override: str | None = None,
    attack_bonus_flat: int = 0,
    damage_bonus_flat: int = 0,
) -> AttackProfile:
    effective_attack_ability = attack_ability_override or attack_ability
    effective_damage_ability = damage_ability_override or damage_ability
    effective_dice_count = damage_dice_count_override if damage_dice_count_override is not None else damage_dice_count
    effective_die_faces = damage_die_faces_override if damage_die_faces_override is not None else damage_die_faces
    proficiency_bonus = actor.proficiency_bonus if actor_is_proficient_with_weapon(actor, item) else 0
    attack_bonus = actor.ability_modifiers.get(effective_attack_ability, 0) + proficiency_bonus + attack_bonus_flat
    damage_bonus = actor.ability_modifiers.get(effective_damage_ability, 0) + damage_bonus_flat
    reach_ft = 5 if attack_kind != AttackKind.RANGED else None
    range_ft = item.weapon_range_ft if attack_kind != AttackKind.MELEE else None
    long_range_ft = item.weapon_long_range_ft if attack_kind != AttackKind.MELEE else None
    return AttackProfile(
        attack_id=attack_id,
        name=name,
        attack_kind=attack_kind,
        to_hit_bonus=attack_bonus,
        reach_ft=reach_ft,
        range_ft=range_ft,
        long_range_ft=long_range_ft,
        damage_dice_count=effective_dice_count,
        damage_die_faces=effective_die_faces,
        damage_bonus=damage_bonus,
        damage_type=(damage_type_override or item.weapon_damage_type or 'bludgeoning'),
        is_finesse=('finesse' in item.weapon_properties),
        source_item_id=item.record_id,
        attack_usage_kind=usage_kind,
        ammunition_item_id=item.weapon_ammunition_type,
        required_hand_count=required_hand_count_value,
        loading=('loading' in item.weapon_properties),
    )



def _item_enchantment_effect(
    actor: RuntimeActorState,
    item: ItemRecord,
    active_effects: Mapping[str, ActiveEffectState] | None,
):
    if not active_effects:
        return None
    matches = [
        effect
        for effect in active_effects.values()
        if actor.actor_id in effect.target_actor_ids and effect.definition.enchanted_item_id == item.record_id
    ]
    return matches[-1] if matches else None



def _item_attack_profiles(
    actor: RuntimeActorState,
    item: ItemRecord,
    *,
    active_effects: Mapping[str, ActiveEffectState] | None = None,
) -> tuple[AttackProfile, ...]:
    if not item_is_weapon(item):
        return ()
    attacks: list[AttackProfile] = []
    finesse = 'finesse' in item.weapon_properties
    thrown = 'thrown' in item.weapon_properties and item.weapon_range_ft is not None
    versatile = item.weapon_versatile_damage_dice_count is not None and item.weapon_versatile_damage_die_faces is not None and 'versatile' in item.weapon_properties
    enchantment = _item_enchantment_effect(actor, item, active_effects)

    def _weapon_overrides() -> dict[str, object]:
        if enchantment is None:
            return {}
        return {
            'attack_ability_override': enchantment.definition.enchanted_attack_ability,
            'damage_ability_override': enchantment.definition.enchanted_damage_ability,
            'damage_dice_count_override': enchantment.definition.enchanted_damage_dice_count,
            'damage_die_faces_override': enchantment.definition.enchanted_damage_die_faces,
            'damage_type_override': enchantment.definition.enchanted_damage_type_override,
            'attack_bonus_flat': enchantment.definition.enchanted_attack_bonus,
            'damage_bonus_flat': enchantment.definition.enchanted_damage_bonus,
        }

    if item.weapon_kind == 'melee':
        attacks.append(
            _weapon_attack_profile(
                actor,
                item=item,
                attack_id=f'{item.record_id}-melee-str',
                name=_weapon_display_name(item, 'Melee STR'),
                attack_kind=AttackKind.MELEE,
                usage_kind=AttackUsageKind.WEAPON_MELEE,
                attack_ability=Ability.STR,
                damage_ability=Ability.STR,
                damage_dice_count=(item.weapon_damage_dice_count or 1),
                damage_die_faces=(item.weapon_damage_die_faces or 4),
                required_hand_count_value=(2 if 'two-handed' in item.weapon_properties else 1),
                **_weapon_overrides(),
            )
        )
        if finesse:
            attacks.append(
                _weapon_attack_profile(
                    actor,
                    item=item,
                    attack_id=f'{item.record_id}-melee-dex',
                    name=_weapon_display_name(item, 'Melee DEX'),
                    attack_kind=AttackKind.MELEE,
                    usage_kind=AttackUsageKind.WEAPON_MELEE,
                    attack_ability=Ability.DEX,
                    damage_ability=Ability.DEX,
                    damage_dice_count=(item.weapon_damage_dice_count or 1),
                    damage_die_faces=(item.weapon_damage_die_faces or 4),
                    required_hand_count_value=(2 if 'two-handed' in item.weapon_properties else 1),
                    **_weapon_overrides(),
                )
            )
        if versatile:
            attacks.append(
                _weapon_attack_profile(
                    actor,
                    item=item,
                    attack_id=f'{item.record_id}-versatile-str',
                    name=_weapon_display_name(item, 'Versatile STR'),
                    attack_kind=AttackKind.MELEE,
                    usage_kind=AttackUsageKind.WEAPON_MELEE,
                    attack_ability=Ability.STR,
                    damage_ability=Ability.STR,
                    damage_dice_count=(item.weapon_versatile_damage_dice_count or item.weapon_damage_dice_count or 1),
                    damage_die_faces=(item.weapon_versatile_damage_die_faces or item.weapon_damage_die_faces or 4),
                    required_hand_count_value=2,
                    **_weapon_overrides(),
                )
            )
            if finesse:
                attacks.append(
                    _weapon_attack_profile(
                        actor,
                        item=item,
                        attack_id=f'{item.record_id}-versatile-dex',
                        name=_weapon_display_name(item, 'Versatile DEX'),
                        attack_kind=AttackKind.MELEE,
                        usage_kind=AttackUsageKind.WEAPON_MELEE,
                        attack_ability=Ability.DEX,
                        damage_ability=Ability.DEX,
                        damage_dice_count=(item.weapon_versatile_damage_dice_count or item.weapon_damage_dice_count or 1),
                        damage_die_faces=(item.weapon_versatile_damage_die_faces or item.weapon_damage_die_faces or 4),
                        required_hand_count_value=2,
                        **_weapon_overrides(),
                    )
                )
        if thrown:
            attacks.append(
                _weapon_attack_profile(
                    actor,
                    item=item,
                    attack_id=f'{item.record_id}-thrown-str',
                    name=_weapon_display_name(item, 'Thrown STR'),
                    attack_kind=AttackKind.RANGED,
                    usage_kind=AttackUsageKind.THROWN_WEAPON,
                    attack_ability=Ability.STR,
                    damage_ability=Ability.STR,
                    damage_dice_count=(item.weapon_damage_dice_count or 1),
                    damage_die_faces=(item.weapon_damage_die_faces or 4),
                    required_hand_count_value=1,
                    **_weapon_overrides(),
                )
            )
            if finesse:
                attacks.append(
                    _weapon_attack_profile(
                        actor,
                        item=item,
                        attack_id=f'{item.record_id}-thrown-dex',
                        name=_weapon_display_name(item, 'Thrown DEX'),
                        attack_kind=AttackKind.RANGED,
                        usage_kind=AttackUsageKind.THROWN_WEAPON,
                        attack_ability=Ability.DEX,
                        damage_ability=Ability.DEX,
                        damage_dice_count=(item.weapon_damage_dice_count or 1),
                        damage_die_faces=(item.weapon_damage_die_faces or 4),
                        required_hand_count_value=1,
                        **_weapon_overrides(),
                    )
                )
        return tuple(attacks)
    if item.weapon_kind == 'ranged':
        attacks.append(
            _weapon_attack_profile(
                actor,
                item=item,
                attack_id=f'{item.record_id}-ranged',
                name=item.name,
                attack_kind=AttackKind.RANGED,
                usage_kind=AttackUsageKind.WEAPON_RANGED,
                attack_ability=Ability.DEX,
                damage_ability=Ability.DEX,
                damage_dice_count=(item.weapon_damage_dice_count or 1),
                damage_die_faces=(item.weapon_damage_die_faces or 4),
                required_hand_count_value=(2 if 'two-handed' in item.weapon_properties else 1),
                **_weapon_overrides(),
            )
        )
        return tuple(attacks)
    return ()




def item_attack_profiles(
    actor: RuntimeActorState,
    item: ItemRecord,
    *,
    active_effects: Mapping[str, ActiveEffectState] | None = None,
) -> tuple[AttackProfile, ...]:
    return _item_attack_profiles(actor, item, active_effects=active_effects)



def build_player_attack_profiles(
    actor: RuntimeActorState,
    item_catalog: dict[str, ItemRecord],
    *,
    unarmed_attack: AttackProfile,
    active_effects: Mapping[str, ActiveEffectState] | None = None,
) -> dict[str, AttackProfile]:
    attacks: dict[str, AttackProfile] = {unarmed_attack.attack_id: unarmed_attack}
    for item_id, quantity in sorted(actor.carried_item_counts.items()):
        if quantity <= 0:
            continue
        item = item_catalog.get(item_id)
        if not item_is_weapon(item):
            continue
        for attack in _item_attack_profiles(actor, item, active_effects=active_effects):
            attacks[attack.attack_id] = attack
    return attacks



def apply_default_equipped_slots(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord]) -> None:
    _normalize_slot_state_from_legacy(actor, item_catalog)
    if actor.main_hand_item_id is not None or actor.off_hand_item_id is not None or actor.equipped_armor_item_id is not None:
        _sync_legacy_equipment_state(actor, item_catalog)
        return
    first_weapon: str | None = None
    shield_item_id: str | None = None
    armor_item_id: str | None = None
    for item_id, quantity in actor.carried_item_counts.items():
        if quantity <= 0:
            continue
        item = item_catalog.get(item_id)
        if item is None:
            continue
        if armor_item_id is None and item_is_armor(item):
            armor_item_id = item_id
            continue
        if shield_item_id is None and item_is_shield(item):
            shield_item_id = item_id
            continue
        if first_weapon is None and item_is_weapon(item):
            first_weapon = item_id
    if armor_item_id is not None:
        actor.equipped_armor_item_id = armor_item_id
    if first_weapon is not None:
        actor.main_hand_item_id = first_weapon
    main_item = item_catalog.get(actor.main_hand_item_id) if actor.main_hand_item_id is not None else None
    if shield_item_id is not None and main_item is not None and required_hand_count(main_item) <= 1:
        actor.off_hand_item_id = shield_item_id
    elif actor.main_hand_item_id is None and shield_item_id is not None:
        actor.off_hand_item_id = shield_item_id
    _sync_legacy_equipment_state(actor, item_catalog)



def refresh_actor_equipment_state(
    actor: RuntimeActorState,
    item_catalog: dict[str, ItemRecord],
    *,
    unarmed_attack: AttackProfile | None = None,
    active_effects: Mapping[str, ActiveEffectState] | None = None,
) -> None:
    _sync_legacy_equipment_state(actor, item_catalog)
    resolved_unarmed_attack = unarmed_attack or actor.attacks.get('unarmed-strike') or default_unarmed_attack(actor)
    actor.attacks = build_player_attack_profiles(actor, item_catalog, unarmed_attack=resolved_unarmed_attack, active_effects=active_effects)
    actor.armor_class = compute_equipped_armor_class(actor, item_catalog, active_effects=active_effects)



def derived_stowed_counts(actor: RuntimeActorState, item_catalog: dict[str, ItemRecord] | None = None) -> dict[str, int]:
    counts = Counter(actor.carried_item_counts)
    if item_catalog is None:
        for held_item_id in actor.held_item_ids:
            if held_item_id in counts:
                counts[held_item_id] -= 1
                if counts[held_item_id] <= 0:
                    counts.pop(held_item_id, None)
        for worn_item_id in (actor.worn_armor_item_id, actor.worn_shield_item_id):
            if worn_item_id and worn_item_id in counts:
                counts[worn_item_id] -= 1
                if counts[worn_item_id] <= 0:
                    counts.pop(worn_item_id, None)
        return dict(counts)
    _sync_legacy_equipment_state(actor, item_catalog)
    for equipped_item_id in hand_slot_item_ids(actor, item_catalog):
        if equipped_item_id in counts:
            counts[equipped_item_id] -= 1
            if counts[equipped_item_id] <= 0:
                counts.pop(equipped_item_id, None)
    if actor.equipped_armor_item_id is not None and actor.equipped_armor_item_id in counts:
        counts[actor.equipped_armor_item_id] -= 1
        if counts[actor.equipped_armor_item_id] <= 0:
            counts.pop(actor.equipped_armor_item_id, None)
    return dict(counts)
