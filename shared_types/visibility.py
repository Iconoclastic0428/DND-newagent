from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class LightLevel(str, Enum):
    BRIGHT = 'bright'
    DIM = 'dim'
    DARKNESS = 'darkness'


class ObscurementLevel(str, Enum):
    NONE = 'none'
    LIGHT = 'light'
    HEAVY = 'heavy'


class ObserverVisibilityState(str, Enum):
    VISIBLE = 'visible'
    UNSEEN = 'unseen'
    HIDDEN = 'hidden'


VisibilityState = ObserverVisibilityState


@dataclass(frozen=True)
class VisibilityAssessment:
    observer_id: str
    target_id: str
    visibility_state: ObserverVisibilityState
    can_see_target: bool
    knows_target_location: bool
    line_of_sight: bool
    line_of_effect: bool
    target_light_level: LightLevel
    target_obscurement: ObscurementLevel
    detail: str | None = None


VisibilityEvaluation = VisibilityAssessment


LightingLevel = LightLevel
