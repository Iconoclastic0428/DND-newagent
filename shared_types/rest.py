from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RestType(str, Enum):
    SHORT = 'short'
    LONG = 'long'


class RestStateStatus(str, Enum):
    NO_REST = 'no-rest'
    SHORT_REST_IN_PROGRESS = 'short-rest-in-progress'
    LONG_REST_IN_PROGRESS = 'long-rest-in-progress'
    SHORT_REST_COMPLETED = 'short-rest-completed'
    LONG_REST_COMPLETED = 'long-rest-completed'
    INTERRUPTED = 'interrupted'


class RestActivityType(str, Enum):
    QUIET = 'quiet'
    SLEEP = 'sleep'
    LIGHT_ACTIVITY = 'light-activity'
    EXERTION = 'exertion'


class RestInterruptionReason(str, Enum):
    INITIATIVE = 'initiative'
    NON_CANTRIP_SPELL = 'non-cantrip-spell'
    DAMAGE = 'damage'
    EXERTION = 'exertion'


class RestRecoveryMode(str, Enum):
    NONE = 'none'
    FIXED = 'fixed'
    FULL = 'full'


@dataclass(frozen=True)
class RestRecoveryRule:
    mode: RestRecoveryMode = RestRecoveryMode.NONE
    amount: int = 0


@dataclass(frozen=True)
class RestRecoverySpec:
    short_rest: RestRecoveryRule = field(default_factory=RestRecoveryRule)
    long_rest: RestRecoveryRule = field(default_factory=RestRecoveryRule)


@dataclass
class RuntimeResourcePoolState:
    resource_id: str
    label: str
    current: int
    maximum: int
    category: str = 'resource'
    detail: str = ''
    rest_recovery: RestRecoverySpec = field(default_factory=RestRecoverySpec)


@dataclass(frozen=True)
class RestState:
    rest_type: RestType | None = None
    status: RestStateStatus = RestStateStatus.NO_REST
    started_at_seconds: int | None = None
    accumulated_rest_seconds: int = 0
    required_rest_seconds: int = 0
    sleep_seconds: int = 0
    light_activity_seconds: int = 0
    exertion_seconds: int = 0
    interruption_count: int = 0
    last_interruption_reason: RestInterruptionReason | None = None
    short_rest_benefits_granted: bool = False
    hit_dice_window_open: bool = False
    last_completed_rest_type: RestType | None = None
    last_completed_at_seconds: int | None = None

    @property
    def in_progress(self) -> bool:
        return self.status in {
            RestStateStatus.SHORT_REST_IN_PROGRESS,
            RestStateStatus.LONG_REST_IN_PROGRESS,
        }

    @property
    def is_short_rest(self) -> bool:
        return self.rest_type == RestType.SHORT

    @property
    def is_long_rest(self) -> bool:
        return self.rest_type == RestType.LONG
