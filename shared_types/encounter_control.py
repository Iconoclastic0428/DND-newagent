from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .encounter_models import EncounterPhase
from .models import ChoiceView
from .session_projection import ControllerEncounterProjection


class ControllerRole(str, Enum):
    DM = 'dm'
    PLAYER = 'player'


@dataclass(frozen=True)
class ControllerBinding:
    controller_id: str
    role: ControllerRole
    label: str


@dataclass(frozen=True)
class PromptRecipient:
    controller_id: str
    role: ControllerRole
    label: str
    actor_ids: tuple[str, ...]


@dataclass(frozen=True)
class PromptOption:
    option_id: str
    label: str
    detail: str
    actor_id: str | None = None


@dataclass(frozen=True)
class ControllerPrompt:
    prompt_id: str
    prompt_kind: str
    prompt: str
    recipients: tuple[PromptRecipient, ...]
    options: tuple[PromptOption, ...]
    trigger_id: str | None = None
    trigger_type: str | None = None


@dataclass(frozen=True)
class ControllerEncounterView:
    controller_id: str
    role: ControllerRole
    phase: EncounterPhase
    summary_lines: tuple[str, ...]
    available_choices: dict[str, tuple[ChoiceView, ...]]
    projection: ControllerEncounterProjection | None = None
