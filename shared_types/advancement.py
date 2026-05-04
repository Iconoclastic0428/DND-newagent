from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .models import ChoiceGroup, ChoiceResolutionStatus
from .progression import ProgressionMode


class AdvancementValidationStatus(str, Enum):
    PENDING_CLASS_SELECTION = 'pending-class-selection'
    BLOCKED_BY_PENDING_CHOICES = 'blocked-by-pending-choices'
    READY_TO_COMMIT = 'ready-to-commit'
    INVALID = 'invalid'


class AdvancementCommitStatus(str, Enum):
    OPEN = 'open'
    COMMITTED = 'committed'
    FAILED = 'failed'
    CANCELED = 'canceled'


class AdvancementHitPointMode(str, Enum):
    FIXED = 'fixed'
    ROLLED = 'rolled'


class AdvancementChoiceCategory(str, Enum):
    CLASS_SELECTION = 'class-selection'
    SUBCLASS = 'subclass'
    CANTRIP = 'cantrip'
    SPELL = 'spell'
    CLASS_FEATURE = 'class-feature'
    EXPERTISE = 'expertise'
    FIGHTING_STYLE = 'fighting-style'
    WEAPON_MASTERY = 'weapon-mastery'
    FEAT = 'feat'
    ABILITY_SCORE = 'ability-score'


class AdvancementChoiceSourceKind(str, Enum):
    CLASS_LEVEL = 'class-level'
    SUBCLASS_LEVEL = 'subclass-level'
    MULTICLASS = 'multiclass'
    FEATURE = 'feature'


@dataclass(frozen=True)
class AdvancementPolicy:
    hit_point_mode: AdvancementHitPointMode = AdvancementHitPointMode.FIXED
    allow_multiclass: bool = False
    allow_apply_in_combat: bool = False
    allow_apply_with_pending_resolution: bool = False


@dataclass(frozen=True)
class AdvancementChoiceSource:
    source_kind: AdvancementChoiceSourceKind
    class_id: str
    class_name: str
    class_level: int
    feature_name: str | None = None
    detail: str = ''


@dataclass(frozen=True)
class PendingAdvancementChoice:
    group: ChoiceGroup
    source: AdvancementChoiceSource
    category: AdvancementChoiceCategory
    resolution_status: ChoiceResolutionStatus
    blocks_finalization: bool = True
    metadata: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ResolvedAdvancementChoice:
    choice_id: str
    category: AdvancementChoiceCategory
    source: AdvancementChoiceSource
    selected_option_ids: tuple[str, ...]
    selected_option_labels: tuple[str, ...]


@dataclass(frozen=True)
class ClassLevelAllocation:
    class_id: str
    class_name: str
    new_class_level: int
    is_multiclass: bool = False


@dataclass(frozen=True)
class HitPointGainRecord:
    target_total_level: int
    class_id: str
    die_faces: int
    rolled_value: int | None
    constitution_modifier: int
    species_bonus: int
    total_gained: int


@dataclass(frozen=True)
class AdvancementTransaction:
    transaction_id: str
    actor_id: str
    actor_label: str
    source_pending_level_up_id: str
    source_mode: ProgressionMode
    current_total_level: int
    target_total_level: int
    chosen_class_id: str | None = None
    chosen_class_level: int | None = None
    validation_status: AdvancementValidationStatus = AdvancementValidationStatus.PENDING_CLASS_SELECTION
    commit_status: AdvancementCommitStatus = AdvancementCommitStatus.OPEN
    generated_feature_names: tuple[str, ...] = ()
    pending_choices: tuple[PendingAdvancementChoice, ...] = ()
    resolved_choices: tuple[ResolvedAdvancementChoice, ...] = ()
    hp_gain: HitPointGainRecord | None = None
    created_timestamp_seconds: int = 0
    error_text: str = ''


@dataclass
class AdvancementRuntimeState:
    policy: AdvancementPolicy = field(default_factory=AdvancementPolicy)
    transactions: dict[str, AdvancementTransaction] = field(default_factory=dict)
    actor_transaction_ids: dict[str, str] = field(default_factory=dict)
    random_counter: int = 0
