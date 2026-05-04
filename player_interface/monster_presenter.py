from __future__ import annotations

from shared_types.encounter_models import MonsterRecord, RuntimeActorState


def present_monster_list(records: tuple[MonsterRecord, ...]) -> str:
    lines = ["Monsters:"]
    for record in records:
        lines.append(f"- {record.record_id}: {record.name} [{record.source}] AC {record.armor_class}; HP {record.max_hit_points}; Speed {record.speed_ft}")
    return "\n".join(lines)


def present_monster_inspection(record: MonsterRecord) -> str:
    attacks = ", ".join(attack.name for attack in record.attacks) or "none"
    spells = ", ".join(option.option_id for option in record.spell_options) or "none"
    return "\n".join(
        (
            f"Monster: {record.name}",
            f"Id: {record.record_id}",
            f"Source: {record.source}",
            f"Type: {record.creature_type}",
            f"Size: {record.size}",
            f"AC: {record.armor_class}",
            f"HP: {record.max_hit_points} ({record.hit_point_formula})",
            f"Speed: {record.speed_ft}",
            f"Attacks: {attacks}",
            f"Spells: {spells}",
        )
    )


def present_runtime_actor(actor: RuntimeActorState) -> str:
    attacks = ", ".join(actor.attacks) or "none"
    spells = ", ".join(actor.spells) or "none"
    return "\n".join(
        (
            f"Actor: {actor.name}",
            f"Id: {actor.actor_id}",
            f"Side: {actor.side.value}",
            f"AC: {actor.armor_class}",
            f"HP: {actor.current_hit_points}/{actor.max_hit_points}",
            f"Position: ({actor.position.x},{actor.position.y})",
            f"Speed: {actor.speed_ft}",
            f"Initiative bonus: {actor.initiative_bonus}",
            f"Attacks: {attacks}",
            f"Spells: {spells}",
        )
    )
