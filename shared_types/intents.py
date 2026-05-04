from __future__ import annotations

from dataclasses import dataclass

from .models import Ability, AbilityMethod, EquipmentSelectionMode


class CreationIntent:
    """Marker base type for typed intents."""


@dataclass(frozen=True)
class BeginCreationIntent(CreationIntent):
    pass


@dataclass(frozen=True)
class ChooseSpeciesIntent(CreationIntent):
    species_id: str


@dataclass(frozen=True)
class ChooseClassIntent(CreationIntent):
    class_id: str


@dataclass(frozen=True)
class ChooseClassSkillsIntent(CreationIntent):
    skill_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChooseBackgroundIntent(CreationIntent):
    background_id: str


@dataclass(frozen=True)
class GenerateRolledAbilitiesIntent(CreationIntent):
    pass


@dataclass(frozen=True)
class SetPointBuyScoresIntent(CreationIntent):
    scores: tuple[int, ...]


@dataclass(frozen=True)
class ChooseAbilityArrayIntent(CreationIntent):
    method: AbilityMethod


@dataclass(frozen=True)
class AssignAbilityScoresIntent(CreationIntent):
    assignments: dict[Ability, int]


@dataclass(frozen=True)
class ChooseBackgroundAsiIntent(CreationIntent):
    option_id: str


@dataclass(frozen=True)
class ChooseOriginFeatIntent(CreationIntent):
    feat_id: str


@dataclass(frozen=True)
class ResolveCreationChoiceIntent(CreationIntent):
    choice_id: str
    option_ids: tuple[str, ...]


@dataclass(frozen=True)
class ChooseBackgroundEquipmentIntent(CreationIntent):
    mode: EquipmentSelectionMode
    package_id: str | None = None


@dataclass(frozen=True)
class ChooseClassEquipmentIntent(CreationIntent):
    mode: EquipmentSelectionMode
    package_id: str | None = None


@dataclass(frozen=True)
class BuyItemIntent(CreationIntent):
    item_id: str
    quantity: int


@dataclass(frozen=True)
class ConfirmCharacterIntent(CreationIntent):
    pass
