from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SpellRuntimeSupportMode(str, Enum):
    DETERMINISTIC_CAPABILITY = 'deterministic-capability'
    STORY_ADJUDICATED = 'story-adjudicated'


@dataclass(frozen=True)
class SpellRuntimeSupportProfile:
    support_mode: SpellRuntimeSupportMode
    content_id: str
    implementation_path: str
    support_summary: str = ''


@dataclass(frozen=True)
class SpellPerceptibilityProfile:
    has_verbal_component: bool = False
    has_somatic_component: bool = False
    has_material_component: bool = False
    material_is_costly_or_consumed: bool = False
    material_description: str | None = None
    casting_visual_manifestation: bool = False
    casting_auditory_manifestation: bool = False
    effect_visible: bool = False
    effect_audible: bool = False
    componentless_casting: bool = False


@dataclass(frozen=True)
class SpellParameter:
    key: str
    value: str
