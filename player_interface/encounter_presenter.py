from __future__ import annotations

from shared_types.encounter_control import ControllerEncounterView
from shared_types.encounter_models import EncounterSnapshot


def present_encounter_snapshot(snapshot: EncounterSnapshot | ControllerEncounterView) -> str:
    lines = list(snapshot.summary_lines)
    for label, choices in snapshot.available_choices.items():
        lines.append(f"{label}:")
        for choice in choices:
            lines.append(f"  - {choice.option_id}: {choice.label} [{choice.detail}]")
    return "\n".join(lines)
