from __future__ import annotations

from shared_types.models import InspectionView, SourcePolicy, CreationSnapshot


def present_policy(policy: SourcePolicy) -> str:
    item_sources = ", ".join(sorted(policy.allowed_item_sources or policy.allowed_sources))
    return "\n".join(
        [
            f"Allowed rules sources: {', '.join(sorted(policy.allowed_sources))}",
            f"Ability generation mode: {policy.ability_generation_mode.value}",
            f"Homebrew allowed: {'yes' if policy.allow_homebrew else 'no'}",
            f"Class wealth allowed: {'yes' if policy.allow_class_wealth else 'no'}",
            f"Allowed item sources: {item_sources}",
        ]
    )


def present_snapshot(snapshot: CreationSnapshot) -> str:
    lines = list(snapshot.summary_lines)
    for label, choices in snapshot.available_choices.items():
        lines.append(f"{label}:")
        for choice in choices:
            lines.append(f"  - {choice.option_id}: {choice.label} [{choice.detail}]")
    return "\n".join(lines)


def present_inspection(view: InspectionView) -> str:
    return "\n".join([f"{view.kind.value}: {view.name} ({view.source})", *view.detail_lines])
