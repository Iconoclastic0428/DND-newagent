from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .battlefield import CoverLevel

if TYPE_CHECKING:
    from .encounter_models import GridPosition


class ArmorCategory(str, Enum):
    LIGHT = 'light'
    MEDIUM = 'medium'
    HEAVY = 'heavy'
    SHIELD = 'shield'


class ObjectInteractionKind(str, Enum):
    DRAW = 'draw'
    STOW = 'stow'
    DROP = 'drop'
    PICK_UP = 'pick-up'
    TRANSFER = 'transfer'
    DON_SHIELD = 'don-shield'
    DOFF_SHIELD = 'doff-shield'
    DON_ARMOR = 'don-armor'
    DOFF_ARMOR = 'doff-armor'
    LOAD_AMMUNITION = 'load-ammunition'
    USE_ENVIRONMENT_OBJECT = 'use-environment-object'


class ObjectInteractionCostMode(str, Enum):
    FREE = 'free'
    UTILIZE = 'utilize'
    ATTACK = 'attack'


class EquipmentSlot(str, Enum):
    MAIN_HAND = 'main-hand'
    OFF_HAND = 'off-hand'
    ARMOR = 'armor'


class AttackInteractionTiming(str, Enum):
    BEFORE = 'before'
    AFTER = 'after'


class EnvironmentObjectAction(str, Enum):
    OPEN = 'open'
    CLOSE = 'close'
    TOGGLE = 'toggle'
    ACTIVATE = 'activate'
    DEACTIVATE = 'deactivate'


class AmmunitionRecoveryPolicy(str, Enum):
    EXPENDED_NOT_RECOVERABLE = 'expended-not-recoverable'


@dataclass(frozen=True)
class AttackInteractionSpec:
    timing: AttackInteractionTiming
    interaction_kind: ObjectInteractionKind
    item_id: str | None = None
    ground_item_id: str | None = None


@dataclass
class GroundItemState:
    ground_item_id: str
    item_id: str
    quantity: int
    position: 'GridPosition'
    improvised_damage_type: str | None = None
    equivalent_weapon_item_id: str | None = None


@dataclass
class EnvironmentObjectState:
    object_id: str
    feature_id: str
    label: str
    allowed_actions: tuple[EnvironmentObjectAction, ...]
    position_cells: tuple['GridPosition', ...]
    open_state: bool | None = None
    closed_traversable: bool = False
    open_traversable: bool = True
    closed_occupiable: bool = False
    open_occupiable: bool = True
    closed_blocks_los: bool = False
    open_blocks_los: bool = False
    closed_blocks_loe: bool = False
    open_blocks_loe: bool = False
    closed_cover_provided: CoverLevel = CoverLevel.NONE
    open_cover_provided: CoverLevel = CoverLevel.NONE
    tags: tuple[str, ...] = ()
