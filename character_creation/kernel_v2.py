from __future__ import annotations

from dataclasses import dataclass

from shared_types.errors import ValidationError
from shared_types.events import (
    AbilitiesAssignedEvent,
    AbilityArrayChosenEvent,
    BackgroundAsiAppliedEvent,
    BackgroundChosenEvent,
    BackgroundEquipmentChosenEvent,
    ClassChosenEvent,
    ClassEquipmentChosenEvent,
    ClassSkillsChosenEvent,
    CreationChoiceResolvedEvent,
    CreationConfirmedEvent,
    CreationStartedEvent,
    ItemPurchasedEvent,
    PointBuyScoresSetEvent,
    RolledAbilityScoresGeneratedEvent,
    SpeciesChosenEvent,
)
from shared_types.intents import (
    AssignAbilityScoresIntent,
    BeginCreationIntent,
    BuyItemIntent,
    ChooseAbilityArrayIntent,
    ChooseBackgroundAsiIntent,
    ChooseBackgroundIntent,
    ChooseBackgroundEquipmentIntent,
    ChooseClassIntent,
    ChooseClassEquipmentIntent,
    ChooseClassSkillsIntent,
    ChooseOriginFeatIntent,
    ChooseSpeciesIntent,
    ConfirmCharacterIntent,
    CreationIntent,
    GenerateRolledAbilitiesIntent,
    ResolveCreationChoiceIntent,
    SetPointBuyScoresIntent,
)
from shared_types.models import (
    ABILITY_ORDER,
    Ability,
    AbilityGenerationMode,
    AbilityMethod,
    CharacterFeatGrant,
    CharacterProficiencySelection,
    CharacterRecord,
    CharacterClassLevel,
    FeatGrantOption,
    CharacterSpellSelection,
    ChoiceGroup,
    ChoiceOption,
    ChoiceResolutionStatus,
    ChoiceSource,
    ChoiceSourceKind,
    ChoiceView,
    ContentCatalog,
    ContentKind,
    CreationChoiceCategory,
    CreationPhase,
    CreationSnapshot,
    CreationState,
    EquipmentSelectionMode,
    InspectionView,
    ItemGrant,
    PendingChoice,
    ProficiencyCategory,
    ResolvedCreationChoice,
    SelectionConstraint,
    SourcePolicy,
    SpellSelectionKind,
    cp_to_display,
)

from rules_engine.ability_generation import (
    arrays_match_multiset,
    higher_total_methods,
    roll_dice,
    roll_six_ability_scores,
    validate_point_buy_scores,
)
from rules_engine.rng import seeded_random


def ability_modifier(score: int) -> int:
    return (score - 10) // 2


def _add_items(inventory: dict[str, int], grants: tuple[ItemGrant, ...]) -> None:
    for grant in grants:
        inventory[grant.item_id] = inventory.get(grant.item_id, 0) + grant.quantity


@dataclass(frozen=True)
class _OriginFeatSlot:
    choice_id: str
    label: str
    source: ChoiceSource
    options: tuple[object, ...]
    fixed_option: object | None = None


@dataclass(frozen=True)
class _SelectedFeatGrant:
    slot_id: str
    source: ChoiceSource
    feat_option: object


class CharacterCreationKernel:
    def __init__(self, catalog: ContentCatalog, policy: SourcePolicy, seed: str) -> None:
        self.catalog = catalog
        self.policy = policy
        self.seed = seed

    def new_state(self) -> CreationState:
        return CreationState()

    def phase(self, state: CreationState) -> CreationPhase:
        if state.character_record is not None:
            return CreationPhase.COMPLETE
        if not state.started:
            return CreationPhase.NOT_STARTED
        if state.species_id is None:
            return CreationPhase.CHOOSE_SPECIES
        if state.class_id is None:
            return CreationPhase.CHOOSE_CLASS
        class_record = self.catalog.classes[state.class_id]
        if len(state.class_skill_ids) != class_record.skill_choice_count:
            return CreationPhase.CHOOSE_CLASS_SKILLS
        if state.background_id is None:
            return CreationPhase.CHOOSE_BACKGROUND
        if self._next_pending_creation_choice(state) is not None:
            return CreationPhase.CHOOSE_CREATION_CHOICES
        if state.ability_draft.chosen_scores() is None:
            if (
                self.policy.ability_generation_mode
                == AbilityGenerationMode.COMPARE_ROLL_AND_POINT_BUY_HIGHER_TOTAL
                and state.ability_draft.rolled_scores is not None
                and state.ability_draft.point_buy_scores is not None
                and state.ability_draft.chosen_method is None
            ):
                return CreationPhase.CHOOSE_ABILITY_ARRAY
            return CreationPhase.GENERATE_ABILITIES
        if not state.assigned_abilities:
            return CreationPhase.ASSIGN_ABILITIES
        if state.background_asi_option_id is None:
            return CreationPhase.CHOOSE_BACKGROUND_ASI
        background = self.catalog.backgrounds[state.background_id]
        if state.background_equipment_mode is None and (background.package_options or background.gold_option_cp is not None):
            return CreationPhase.CHOOSE_BACKGROUND_EQUIPMENT
        if state.class_equipment_mode is None:
            return CreationPhase.CHOOSE_CLASS_EQUIPMENT
        return CreationPhase.REVIEW

    def snapshot(self, state: CreationState) -> CreationSnapshot:
        pending_choice = self._next_pending_creation_choice(state)
        lines = [
            f"Phase: {self.phase(state).value}",
            f"Species: {state.species_id or 'pending'}",
            f"Class: {self.catalog.classes[state.class_id].name if state.class_id else 'pending'}",
            f"Class skills: {', '.join(self._skill_names(state.class_skill_ids)) or 'pending'}",
            f"Background: {self.catalog.backgrounds[state.background_id].name if state.background_id else 'pending'}",
            f"Ability method: {state.ability_draft.chosen_method.value if state.ability_draft.chosen_method else 'pending'}",
            f"Rolled array: {self._array_display(state.ability_draft.rolled_scores) if state.ability_draft.rolled_scores else 'pending'}",
            f"Roll breakdown: {self._roll_breakdown_display(state.ability_draft.roll_breakdown) if state.ability_draft.roll_breakdown else 'pending'}",
            f"Point-buy array: {self._array_display(state.ability_draft.point_buy_scores) if state.ability_draft.point_buy_scores else 'pending'}",
            f"Origin feats: {self._origin_feats_display(state)}",
            f"Assigned abilities: {self._abilities_display(state.assigned_abilities) if state.assigned_abilities else 'pending'}",
            f"Final abilities: {self._abilities_display(state.final_ability_scores()) if state.final_ability_scores() else 'pending'}",
            f"Coins: {cp_to_display(state.currency_cp)}",
            f"Inventory entries: {len(state.inventory)}",
        ]
        if pending_choice is not None:
            lines.append(f"Pending creation choice: {pending_choice.group.prompt}")
            lines.append(self._choice_count_instruction(pending_choice.group.constraint.required_count))
            lines.append(f"Command: /create choose choice {pending_choice.group.choice_id} <option-id ...>")
        phase = self.phase(state)
        if phase == CreationPhase.CHOOSE_CLASS_SKILLS and state.class_id is not None:
            class_record = self.catalog.classes[state.class_id]
            lines.append(f"Class skill choices: {self._choice_count_instruction(class_record.skill_choice_count)}")
            lines.append("Command: /create choose class-skills <skill-id ...>")
        if phase == CreationPhase.ASSIGN_ABILITIES:
            assignment_hint = self._ability_assignment_command_hint(state)
            if assignment_hint is not None:
                lines.append(f"Ability order: {self._ability_order_display()}")
                lines.append(f"Command: {assignment_hint}")
        if phase == CreationPhase.REVIEW:
            lines.append("Command: /create confirm")
        return CreationSnapshot(
            phase=phase,
            summary_lines=tuple(lines),
            available_choices=self.available_choices(state),
        )

    def _abilities_display(self, scores: dict[Ability, int]) -> str:
        return ", ".join(f"{ability.value} {scores[ability]}" for ability in ABILITY_ORDER if ability in scores)

    def _array_display(self, scores: tuple[int, ...] | None) -> str:
        if not scores:
            return "pending"
        return ", ".join(str(score) for score in scores)

    def _ability_order_display(self) -> str:
        return " ".join(ability.value for ability in ABILITY_ORDER)

    def _ability_assignment_command_hint(self, state: CreationState) -> str | None:
        chosen_scores = state.ability_draft.chosen_scores()
        if not chosen_scores:
            return None
        return "/create ability assign " + " ".join(str(score) for score in chosen_scores)

    def _choice_count_instruction(self, required_count: int) -> str:
        return f"Choose exactly {required_count} option(s)."

    def _roll_breakdown_display(self, breakdown: tuple[tuple[int, int, int, int], ...] | None) -> str:
        if not breakdown:
            return "pending"
        return "; ".join(
            f"[{', '.join(str(value) for value in roll)}] -> {sum(sorted(roll, reverse=True)[:3])}" for roll in breakdown
        )

    def _skill_name(self, skill_id: str) -> str:
        return self.catalog.skills[skill_id].name if skill_id in self.catalog.skills else skill_id

    def _skill_names(self, skill_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self._skill_name(skill_id) for skill_id in skill_ids)

    def _tool_name(self, tool_id: str) -> str:
        return self.catalog.tools[tool_id].name if tool_id in self.catalog.tools else tool_id

    def _tool_names(self, tool_ids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(self._tool_name(tool_id) for tool_id in tool_ids)

    def _spell_name(self, spell_id: str) -> str:
        return self.catalog.spells[spell_id].name if spell_id in self.catalog.spells else spell_id

    def _background_origin_feat_detail(self, background_id: str) -> str:
        background = self.catalog.backgrounds[background_id]
        if not background.origin_feat_options:
            return "choose custom origin feat"
        if len(background.origin_feat_options) == 1:
            return background.origin_feat_options[0].label
        return f"choose 1 of {len(background.origin_feat_options)} origin feats"

    def _build_custom_origin_feat_options(self) -> tuple[FeatGrantOption, ...]:
        return tuple(
            FeatGrantOption(
                option_id=feat.record_id,
                feat_id=feat.record_id,
                label=feat.name,
            )
            for feat in self.catalog.feats.values()
            if feat.selectable_for_custom_origin
        )

    def _origin_feat_slots(self, state: CreationState) -> tuple[_OriginFeatSlot, ...]:
        if state.species_id is None or state.background_id is None:
            return ()
        slots: list[_OriginFeatSlot] = []
        background = self.catalog.backgrounds[state.background_id]
        if not background.origin_feat_options:
            slots.append(
                _OriginFeatSlot(
                    choice_id=f"background:{background.record_id}:origin-feat",
                    label=f"{background.name} custom origin feat",
                    source=ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name),
                    options=self._build_custom_origin_feat_options(),
                )
            )
        elif len(background.origin_feat_options) == 1:
            slots.append(
                _OriginFeatSlot(
                    choice_id=f"background:{background.record_id}:origin-feat",
                    label=f"{background.name} origin feat",
                    source=ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name),
                    options=background.origin_feat_options,
                    fixed_option=background.origin_feat_options[0],
                )
            )
        else:
            slots.append(
                _OriginFeatSlot(
                    choice_id=f"background:{background.record_id}:origin-feat",
                    label=f"{background.name} origin feat",
                    source=ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name),
                    options=background.origin_feat_options,
                )
            )
        species = self.catalog.species[state.species_id]
        custom_options = self._build_custom_origin_feat_options()
        for index in range(species.bonus_origin_feat_count):
            slots.append(
                _OriginFeatSlot(
                    choice_id=f"species:{species.record_id}:origin-feat-{index + 1}",
                    label=f"{species.name} bonus origin feat {index + 1}",
                    source=ChoiceSource(ChoiceSourceKind.SPECIES, species.record_id, species.name),
                    options=custom_options,
                )
            )
        return tuple(slots)

    def _find_origin_feat_option(self, slot: _OriginFeatSlot, option_id: str):
        for option in slot.options:
            if option.option_id == option_id:
                return option
        raise ValidationError(f"Unknown origin feat option {option_id!r}.")

    def _selected_feat_option(self, slot: _OriginFeatSlot, state: CreationState):
        if slot.fixed_option is not None:
            return slot.fixed_option
        resolved = state.resolved_creation_choices.get(slot.choice_id)
        if not resolved:
            return None
        return self._find_origin_feat_option(slot, resolved[0])

    def _selected_feat_grants(self, state: CreationState) -> tuple[_SelectedFeatGrant, ...]:
        grants: list[_SelectedFeatGrant] = []
        for slot in self._origin_feat_slots(state):
            selected_option = self._selected_feat_option(slot, state)
            if selected_option is None:
                break
            grants.append(_SelectedFeatGrant(slot_id=slot.choice_id, source=slot.source, feat_option=selected_option))
        return tuple(grants)

    def _origin_feat_names(self, state: CreationState) -> tuple[str, ...]:
        names: list[str] = []
        for grant in self._selected_feat_grants(state):
            feat = self.catalog.feats[grant.feat_option.feat_id]
            names.append(feat.name)
        return tuple(names)

    def _origin_feats_display(self, state: CreationState) -> str:
        names = self._origin_feat_names(state)
        if names:
            return ", ".join(names)
        if state.background_id is None:
            return "pending"
        pending_slots = len(self._origin_feat_slots(state))
        if pending_slots > 0:
            return f"pending {pending_slots} selection(s)"
        return "pending"

    def _current_skill_ids(self, state: CreationState) -> tuple[str, ...]:
        skill_ids: list[str] = list(state.class_skill_ids)
        if state.background_id is not None:
            background = self.catalog.backgrounds[state.background_id]
            skill_ids.extend(background.skill_proficiency_ids)
            choice_id = f"background:{background.record_id}:skills"
            skill_ids.extend(state.resolved_creation_choices.get(choice_id, ()))
        for grant in self._selected_feat_grants(state):
            feat = self.catalog.feats[grant.feat_option.feat_id]
            for group in feat.proficiency_choice_groups:
                if ProficiencyCategory.SKILL not in group.allowed_categories:
                    continue
                choice_id = f"{grant.slot_id}:{group.choice_id}"
                for option_id in state.resolved_creation_choices.get(choice_id, ()): 
                    if option_id in self.catalog.skills:
                        skill_ids.append(option_id)
        return tuple(dict.fromkeys(skill_ids))

    def _current_tool_ids(self, state: CreationState) -> tuple[str, ...]:
        tool_ids: list[str] = []
        if state.class_id is not None:
            class_record = self.catalog.classes[state.class_id]
            tool_ids.extend(class_record.tool_proficiency_ids)
            choice_id = f"class:{class_record.record_id}:tools"
            tool_ids.extend(state.resolved_creation_choices.get(choice_id, ()))
        if state.background_id is not None:
            background = self.catalog.backgrounds[state.background_id]
            tool_ids.extend(background.tool_proficiency_ids)
            choice_id = f"background:{background.record_id}:tools"
            tool_ids.extend(state.resolved_creation_choices.get(choice_id, ()))
        for grant in self._selected_feat_grants(state):
            feat = self.catalog.feats[grant.feat_option.feat_id]
            for group in feat.proficiency_choice_groups:
                if ProficiencyCategory.TOOL not in group.allowed_categories:
                    continue
                choice_id = f"{grant.slot_id}:{group.choice_id}"
                for option_id in state.resolved_creation_choices.get(choice_id, ()): 
                    if option_id in self.catalog.tools:
                        tool_ids.append(option_id)
        return tuple(dict.fromkeys(tool_ids))

    def _selected_spell_ids(self, state: CreationState) -> frozenset[str]:
        return frozenset(
            option_id
            for option_ids in state.resolved_creation_choices.values()
            for option_id in option_ids
            if option_id in self.catalog.spells
        )

    def _spell_choice_options(
        self,
        *,
        level: int,
        class_id: str | None = None,
        class_ids: tuple[str, ...] = (),
        exclude_spell_ids: frozenset[str] = frozenset(),
    ) -> tuple[ChoiceOption, ...]:
        eligible_class_ids = tuple(dict.fromkeys(class_ids or ((class_id,) if class_id is not None else ())))
        spells = [
            spell
            for spell in self.catalog.spells.values()
            if spell.level == level
            and spell.record_id not in exclude_spell_ids
            and any(eligible_class_id in spell.class_ids for eligible_class_id in eligible_class_ids)
        ]
        spells.sort(key=lambda record: record.name)
        return tuple(
            ChoiceOption(
                option_id=spell.record_id,
                label=spell.name,
                detail=f"Level {spell.level} spell",
            )
            for spell in spells
        )

    def _class_feature_pending_choices(self, state: CreationState) -> tuple[PendingChoice, ...]:
        if state.class_id is None:
            return ()
        class_record = self.catalog.classes[state.class_id]
        source = ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name)
        return tuple(
            PendingChoice(
                group=ChoiceGroup(
                    choice_id=group.choice_id,
                    label=group.label,
                    prompt=group.prompt,
                    options=tuple(ChoiceOption(option_id=option.option_id, label=option.label, detail=option.detail) for option in group.options),
                    constraint=group.constraint,
                ),
                source=source,
                category=CreationChoiceCategory.CLASS_FEATURE,
                resolution_status=ChoiceResolutionStatus.RESOLVED if group.choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
            )
            for group in class_record.class_feature_choice_groups
            if group.level == 1
        )

    def _selected_class_feature_options(self, state: CreationState):
        if state.class_id is None:
            return ()
        class_record = self.catalog.classes[state.class_id]
        selected = []
        for group in class_record.class_feature_choice_groups:
            if group.level != 1:
                continue
            selected_option_ids = state.resolved_creation_choices.get(group.choice_id, ())
            if not selected_option_ids:
                continue
            for option_id in selected_option_ids:
                option = next((candidate for candidate in group.options if candidate.option_id == option_id), None)
                if option is not None:
                    selected.append((group, option))
        return tuple(selected)

    def _class_feature_bundle_next_choice(self, state: CreationState, group, option) -> PendingChoice | None:
        if state.class_id is None:
            return None
        class_record = self.catalog.classes[state.class_id]
        source = ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name)
        for bundle in option.spell_choice_bundles:
            choice_id = f"{group.choice_id}:{bundle.choice_id}"
            if choice_id in state.resolved_creation_choices:
                continue
            if bundle.cantrip_count > 0:
                return PendingChoice(
                    group=ChoiceGroup(
                        choice_id=choice_id,
                        label=bundle.label,
                        prompt=f"Choose {bundle.cantrip_count} cantrip(s) for {option.label}.",
                        options=self._spell_choice_options(level=0, class_ids=bundle.spell_list_class_ids, exclude_spell_ids=self._selected_spell_ids(state)),
                        constraint=SelectionConstraint(required_count=bundle.cantrip_count),
                    ),
                    source=source,
                    category=CreationChoiceCategory.CANTRIP,
                    resolution_status=ChoiceResolutionStatus.PENDING,
                )
            if bundle.spell_count > 0:
                return PendingChoice(
                    group=ChoiceGroup(
                        choice_id=choice_id,
                        label=bundle.label,
                        prompt=f"Choose {bundle.spell_count} level-{bundle.spell_level} spell(s) for {option.label}.",
                        options=self._spell_choice_options(level=bundle.spell_level, class_ids=bundle.spell_list_class_ids, exclude_spell_ids=self._selected_spell_ids(state)),
                        constraint=SelectionConstraint(required_count=bundle.spell_count),
                    ),
                    source=source,
                    category=CreationChoiceCategory.SPELL if bundle.spell_level > 0 else CreationChoiceCategory.CANTRIP,
                    resolution_status=ChoiceResolutionStatus.PENDING,
                )
        return None

    def _background_skill_choice(self, state: CreationState) -> PendingChoice | None:
        if state.background_id is None:
            return None
        background = self.catalog.backgrounds[state.background_id]
        if background.background_skill_choice_count <= 0:
            return None
        taken = set(self._current_skill_ids(state)) - set(state.resolved_creation_choices.get(f"background:{background.record_id}:skills", ()))
        options = tuple(
            ChoiceOption(option_id=skill_id, label=self.catalog.skills[skill_id].name, detail="background skill option")
            for skill_id in background.background_skill_option_ids
            if skill_id not in taken
        )
        choice_id = f"background:{background.record_id}:skills"
        choice = PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=f"{background.name} skills",
                prompt=f"Choose {background.background_skill_choice_count} background skill(s).",
                options=options,
                constraint=SelectionConstraint(required_count=background.background_skill_choice_count),
            ),
            source=ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name),
            category=CreationChoiceCategory.BACKGROUND_SKILL,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )
        return choice

    def _background_tool_choice(self, state: CreationState) -> PendingChoice | None:
        if state.background_id is None:
            return None
        background = self.catalog.backgrounds[state.background_id]
        if background.background_tool_choice_count <= 0:
            return None
        taken = set(self._current_tool_ids(state)) - set(state.resolved_creation_choices.get(f"background:{background.record_id}:tools", ()))
        options = tuple(
            ChoiceOption(option_id=tool_id, label=self.catalog.tools[tool_id].name, detail="background tool option")
            for tool_id in background.background_tool_option_ids
            if tool_id not in taken
        )
        choice_id = f"background:{background.record_id}:tools"
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=f"{background.name} tools",
                prompt=f"Choose {background.background_tool_choice_count} background tool(s).",
                options=options,
                constraint=SelectionConstraint(required_count=background.background_tool_choice_count),
            ),
            source=ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name),
            category=CreationChoiceCategory.TOOL,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _class_tool_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id is None:
            return None
        class_record = self.catalog.classes[state.class_id]
        if class_record.class_tool_choice_count <= 0:
            return None
        taken = set(self._current_tool_ids(state)) - set(state.resolved_creation_choices.get(f"class:{class_record.record_id}:tools", ()))
        options = tuple(
            ChoiceOption(option_id=tool_id, label=self.catalog.tools[tool_id].name, detail="class tool option")
            for tool_id in class_record.class_tool_option_ids
            if tool_id not in taken
        )
        choice_id = f"class:{class_record.record_id}:tools"
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=f"{class_record.name} tools",
                prompt=f"Choose {class_record.class_tool_choice_count} class tool(s).",
                options=options,
                constraint=SelectionConstraint(required_count=class_record.class_tool_choice_count),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name),
            category=CreationChoiceCategory.TOOL,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _class_cantrip_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id is None:
            return None
        class_record = self.catalog.classes[state.class_id]
        if class_record.spellcasting is None or class_record.spellcasting.cantrip_choice_count <= 0:
            return None
        choice_id = f"class:{class_record.record_id}:cantrips"
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=f"{class_record.name} cantrips",
                prompt=f"Choose {class_record.spellcasting.cantrip_choice_count} cantrip(s).",
                options=self._spell_choice_options(class_id=class_record.record_id, level=0),
                constraint=SelectionConstraint(required_count=class_record.spellcasting.cantrip_choice_count),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name),
            category=CreationChoiceCategory.CANTRIP,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _class_spell_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id is None:
            return None
        class_record = self.catalog.classes[state.class_id]
        if class_record.spellcasting is None or class_record.spellcasting.spell_choice_count <= 0:
            return None
        choice_id = f"class:{class_record.record_id}:spells"
        detail = class_record.spellcasting.spell_selection_kind.value
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=f"{class_record.name} level 1 spells",
                prompt=f"Choose {class_record.spellcasting.spell_choice_count} level-1 spell(s).",
                options=tuple(
                    ChoiceOption(option_id=option.option_id, label=option.label, detail=f"{detail} spell")
                    for option in self._spell_choice_options(class_id=class_record.record_id, level=1)
                ),
                constraint=SelectionConstraint(required_count=class_record.spellcasting.spell_choice_count),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name),
            category=CreationChoiceCategory.SPELL,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _origin_feat_slot_choice(self, slot: _OriginFeatSlot, state: CreationState) -> PendingChoice | None:
        if slot.fixed_option is not None:
            return None
        taken_feat_ids = {grant.feat_option.feat_id for grant in self._selected_feat_grants(state) if grant.slot_id != slot.choice_id}
        options = []
        for option in slot.options:
            feat = self.catalog.feats[option.feat_id]
            if option.feat_id in taken_feat_ids and not feat.repeatable:
                continue
            options.append(ChoiceOption(option_id=option.option_id, label=option.label, detail=feat.source))
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=slot.choice_id,
                label=slot.label,
                prompt=f"Choose {slot.label}.",
                options=tuple(options),
                constraint=SelectionConstraint(required_count=1),
            ),
            source=slot.source,
            category=CreationChoiceCategory.ORIGIN_FEAT,
            resolution_status=ChoiceResolutionStatus.RESOLVED if slot.choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _feat_proficiency_choice(self, state: CreationState, grant: _SelectedFeatGrant, group) -> PendingChoice | None:
        choice_id = f"{grant.slot_id}:{group.choice_id}"
        current_skills = set(self._current_skill_ids(state)) - set(state.resolved_creation_choices.get(choice_id, ()))
        current_tools = set(self._current_tool_ids(state)) - set(state.resolved_creation_choices.get(choice_id, ()))
        options = []
        for option_id in group.option_ids:
            if option_id in self.catalog.skills:
                if option_id in current_skills:
                    continue
                options.append(ChoiceOption(option_id=option_id, label=self.catalog.skills[option_id].name, detail="skill"))
            elif option_id in self.catalog.tools:
                if option_id in current_tools:
                    continue
                options.append(ChoiceOption(option_id=option_id, label=self.catalog.tools[option_id].name, detail="tool"))
        feat = self.catalog.feats[grant.feat_option.feat_id]
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label=group.label,
                prompt=f"Choose {group.count} option(s) for {feat.name}.",
                options=tuple(options),
                constraint=SelectionConstraint(required_count=group.count),
            ),
            source=ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name),
            category=group.category,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _feat_bundle_selected_class_id(self, state: CreationState, grant: _SelectedFeatGrant, bundle) -> str | None:
        metadata = dict(grant.feat_option.fixed_metadata)
        if 'spell_list_class_id' in metadata:
            return metadata['spell_list_class_id']
        choice_id = f"{grant.slot_id}:{bundle.choice_id}:spell-list"
        selected = state.resolved_creation_choices.get(choice_id)
        if not selected:
            return None
        return selected[0]

    def _feat_spellcasting_ability(self, state: CreationState, grant: _SelectedFeatGrant, bundle) -> Ability | None:
        choice_id = f"{grant.slot_id}:{bundle.choice_id}:ability"
        selected = state.resolved_creation_choices.get(choice_id)
        if not selected:
            return None
        return Ability(selected[0])

    def _feat_bundle_next_choice(self, state: CreationState, grant: _SelectedFeatGrant, bundle) -> PendingChoice | None:
        feat = self.catalog.feats[grant.feat_option.feat_id]
        source = ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name)
        metadata = dict(grant.feat_option.fixed_metadata)
        if 'spell_list_class_id' not in metadata:
            choice_id = f"{grant.slot_id}:{bundle.choice_id}:spell-list"
            if choice_id not in state.resolved_creation_choices:
                options = tuple(
                    ChoiceOption(option_id=class_id, label=self.catalog.classes[class_id].name, detail="spell list")
                    for class_id in bundle.spell_list_class_ids
                )
                return PendingChoice(
                    group=ChoiceGroup(choice_id=choice_id, label=f"{feat.name} spell list", prompt=f"Choose the {feat.name} spell list.", options=options, constraint=SelectionConstraint(required_count=1)),
                    source=source,
                    category=CreationChoiceCategory.SPELL_LIST,
                    resolution_status=ChoiceResolutionStatus.PENDING,
                )
        selected_class_id = self._feat_bundle_selected_class_id(state, grant, bundle)
        if selected_class_id is None:
            return None
        ability_choice_id = f"{grant.slot_id}:{bundle.choice_id}:ability"
        if ability_choice_id not in state.resolved_creation_choices:
            options = tuple(ChoiceOption(option_id=ability.value, label=ability.value, detail="spellcasting ability") for ability in bundle.spellcasting_ability_options)
            return PendingChoice(
                group=ChoiceGroup(choice_id=ability_choice_id, label=f"{feat.name} spellcasting ability", prompt=f"Choose the spellcasting ability for {feat.name}.", options=options, constraint=SelectionConstraint(required_count=1)),
                source=source,
                category=CreationChoiceCategory.SPELLCASTING_ABILITY,
                resolution_status=ChoiceResolutionStatus.PENDING,
            )
        cantrip_choice_id = f"{grant.slot_id}:{bundle.choice_id}:cantrips"
        if cantrip_choice_id not in state.resolved_creation_choices:
            return PendingChoice(
                group=ChoiceGroup(choice_id=cantrip_choice_id, label=f"{feat.name} cantrips", prompt=f"Choose {bundle.cantrip_count} cantrip(s) for {feat.name}.", options=self._spell_choice_options(class_id=selected_class_id, level=0), constraint=SelectionConstraint(required_count=bundle.cantrip_count)),
                source=source,
                category=CreationChoiceCategory.CANTRIP,
                resolution_status=ChoiceResolutionStatus.PENDING,
            )
        spell_choice_id = f"{grant.slot_id}:{bundle.choice_id}:spell"
        if spell_choice_id not in state.resolved_creation_choices:
            return PendingChoice(
                group=ChoiceGroup(choice_id=spell_choice_id, label=f"{feat.name} spell", prompt=f"Choose {bundle.spell_count} level-{bundle.spell_level} spell(s) for {feat.name}.", options=self._spell_choice_options(class_id=selected_class_id, level=bundle.spell_level), constraint=SelectionConstraint(required_count=bundle.spell_count)),
                source=source,
                category=CreationChoiceCategory.SPELL,
                resolution_status=ChoiceResolutionStatus.PENDING,
            )
        return None

    def _fighter_fighting_style_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id != 'fighter':
            return None
        choice_id = 'class:fighter:fighting-style'
        style_options = tuple(
            ChoiceOption(option_id=feat.record_id, label=feat.name, detail='fighting style feat')
            for feat in sorted(self.catalog.feats.values(), key=lambda record: record.name)
            if feat.category == 'FS'
        )
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label='Fighting Style',
                prompt='Choose a fighting style.',
                options=style_options,
                constraint=SelectionConstraint(required_count=1),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, 'fighter', 'Fighter'),
            category=CreationChoiceCategory.CLASS_FEATURE,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _rogue_expertise_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id != 'rogue' or state.background_id is None:
            return None
        choice_id = 'class:rogue:expertise'
        options: list[ChoiceOption] = []
        for skill_id in self._current_skill_ids(state):
            options.append(ChoiceOption(option_id=skill_id, label=self._skill_name(skill_id), detail='skill expertise'))
        for tool_id in self._current_tool_ids(state):
            if tool_id == 'thieves-tools':
                options.append(ChoiceOption(option_id=tool_id, label=self._tool_name(tool_id), detail='tool expertise'))
        unique_options = tuple(dict.fromkeys((option.option_id, option.label, option.detail) for option in options))
        rendered_options = tuple(ChoiceOption(option_id=option_id, label=label, detail=detail) for option_id, label, detail in unique_options)
        if not rendered_options:
            return None
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label='Expertise',
                prompt="Choose 2 expertise options from your proficient skills, or choose 1 skill and thieves' tools.",
                options=rendered_options,
                constraint=SelectionConstraint(required_count=2),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, 'rogue', 'Rogue'),
            category=CreationChoiceCategory.SKILL_OR_TOOL,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _weapon_mastery_choice(self, state: CreationState) -> PendingChoice | None:
        if state.class_id is None:
            return None
        mastery_counts = {'barbarian': 2, 'fighter': 3, 'paladin': 2, 'ranger': 2, 'rogue': 2}
        count = mastery_counts.get(state.class_id)
        if count is None:
            return None
        choice_id = f'class:{state.class_id}:weapon-mastery'
        options: list[ChoiceOption] = []
        for item in sorted(self.catalog.items.values(), key=lambda record: record.name):
            if item.weapon_category is None:
                continue
            if state.class_id == 'rogue':
                is_simple = item.weapon_category == 'simple'
                is_eligible_martial = item.weapon_category == 'martial' and any(prop in {'light', 'finesse'} for prop in item.weapon_properties)
                if not (is_simple or is_eligible_martial):
                    continue
            options.append(ChoiceOption(option_id=item.record_id, label=item.name, detail='weapon mastery'))
        return PendingChoice(
            group=ChoiceGroup(
                choice_id=choice_id,
                label='Weapon Mastery',
                prompt=f'Choose {count} weapon mastery option(s).',
                options=tuple(options),
                constraint=SelectionConstraint(required_count=count),
            ),
            source=ChoiceSource(ChoiceSourceKind.CLASS, state.class_id, self.catalog.classes[state.class_id].name),
            category=CreationChoiceCategory.CLASS_FEATURE,
            resolution_status=ChoiceResolutionStatus.RESOLVED if choice_id in state.resolved_creation_choices else ChoiceResolutionStatus.PENDING,
        )

    def _next_pending_creation_choice(self, state: CreationState) -> PendingChoice | None:
        for builder in (self._background_skill_choice, self._background_tool_choice, self._class_tool_choice):
            choice = builder(state)
            if choice is not None and choice.resolution_status == ChoiceResolutionStatus.PENDING:
                return choice
        for choice in self._class_feature_pending_choices(state):
            if choice.resolution_status == ChoiceResolutionStatus.PENDING:
                return choice
        for builder in (self._fighter_fighting_style_choice, self._rogue_expertise_choice, self._weapon_mastery_choice, self._class_cantrip_choice, self._class_spell_choice):
            choice = builder(state)
            if choice is not None and choice.resolution_status == ChoiceResolutionStatus.PENDING:
                return choice
        for group, option in self._selected_class_feature_options(state):
            choice = self._class_feature_bundle_next_choice(state, group, option)
            if choice is not None:
                return choice
        for slot in self._origin_feat_slots(state):
            slot_choice = self._origin_feat_slot_choice(slot, state)
            if slot_choice is not None and slot_choice.resolution_status == ChoiceResolutionStatus.PENDING:
                return slot_choice
            selected_option = self._selected_feat_option(slot, state)
            if selected_option is None:
                return None
            feat = self.catalog.feats[selected_option.feat_id]
            grant = _SelectedFeatGrant(slot_id=slot.choice_id, source=slot.source, feat_option=selected_option)
            for group in feat.proficiency_choice_groups:
                choice = self._feat_proficiency_choice(state, grant, group)
                if choice is not None and choice.resolution_status == ChoiceResolutionStatus.PENDING:
                    return choice
            for bundle in feat.spell_choice_bundles:
                choice = self._feat_bundle_next_choice(state, grant, bundle)
                if choice is not None:
                    return choice
        return None

    def available_choices(self, state: CreationState) -> dict[str, tuple[ChoiceView, ...]]:
        phase = self.phase(state)
        choices: dict[str, tuple[ChoiceView, ...]] = {}
        if phase == CreationPhase.CHOOSE_SPECIES:
            choices['species'] = tuple(ChoiceView(option_id=record.record_id, label=record.name, detail=f"{record.source}; Speed {record.speed}") for record in self.catalog.species.values())
        elif phase == CreationPhase.CHOOSE_CLASS:
            choices['class'] = tuple(ChoiceView(option_id=record.record_id, label=record.name, detail=f"{record.source}; d{record.hit_die} hit die") for record in self.catalog.classes.values())
        elif phase == CreationPhase.CHOOSE_CLASS_SKILLS:
            class_record = self.catalog.classes[state.class_id]
            detail = f"{self._choice_count_instruction(class_record.skill_choice_count)} Command: /create choose class-skills <skill-id ...>"
            choices['class-skills'] = tuple(ChoiceView(option_id=skill_id, label=self.catalog.skills[skill_id].name, detail=detail) for skill_id in class_record.class_skill_option_ids)
        elif phase == CreationPhase.CHOOSE_BACKGROUND:
            choices['background'] = tuple(ChoiceView(option_id=record.record_id, label=record.name, detail=f"{record.source}; feat {self._background_origin_feat_detail(record.record_id)}") for record in self.catalog.backgrounds.values())
        elif phase == CreationPhase.CHOOSE_CREATION_CHOICES:
            pending_choice = self._next_pending_creation_choice(state)
            if pending_choice is not None:
                choices[f"choice:{pending_choice.group.choice_id}"] = tuple(
                    ChoiceView(
                        option_id=option.option_id,
                        label=option.label,
                        detail=f"{self._choice_count_instruction(pending_choice.group.constraint.required_count)} {option.detail}".strip(),
                    )
                    for option in pending_choice.group.options
                )
        elif phase == CreationPhase.GENERATE_ABILITIES:
            methods = []
            if self.policy.ability_generation_mode in {AbilityGenerationMode.ROLL_ONLY, AbilityGenerationMode.ROLL_OR_POINT_BUY, AbilityGenerationMode.COMPARE_ROLL_AND_POINT_BUY_HIGHER_TOTAL}:
                methods.append(ChoiceView(option_id='roll', label='4d6 keep highest 3', detail='repeat six times'))
            if self.policy.ability_generation_mode in {AbilityGenerationMode.POINT_BUY_ONLY, AbilityGenerationMode.ROLL_OR_POINT_BUY, AbilityGenerationMode.COMPARE_ROLL_AND_POINT_BUY_HIGHER_TOTAL}:
                methods.append(ChoiceView(option_id='point-buy', label='27 point buy', detail='submit six purchased scores'))
            choices['ability-method'] = tuple(methods)
        elif phase == CreationPhase.CHOOSE_ABILITY_ARRAY:
            rolled = state.ability_draft.rolled_scores or ()
            point_buy = state.ability_draft.point_buy_scores or ()
            choices['ability-array'] = tuple(ChoiceView(option_id=method.value, label=method.value, detail=f"{sum(rolled if method == AbilityMethod.ROLLED else point_buy)} total") for method in higher_total_methods(rolled, point_buy))
        elif phase == CreationPhase.ASSIGN_ABILITIES:
            assignment_hint = self._ability_assignment_command_hint(state)
            if assignment_hint is not None:
                scores = assignment_hint.removeprefix('/create ability assign ')
                choices['ability-assignment'] = (
                    ChoiceView(
                        option_id=scores,
                        label='Assign generated scores',
                        detail=f"Enter scores in {self._ability_order_display()} order; edit the command if you want a different assignment.",
                    ),
                )
        elif phase == CreationPhase.CHOOSE_BACKGROUND_ASI:
            background = self.catalog.backgrounds[state.background_id]
            choices['background-asi'] = tuple(ChoiceView(option_id=option.option_id, label=option.label, detail='background ASI option') for option in background.ability_increase_options())
        elif phase == CreationPhase.CHOOSE_BACKGROUND_EQUIPMENT:
            background = self.catalog.backgrounds[state.background_id]
            base = [ChoiceView(option_id=package.package_id, label=package.label, detail=f"{len(package.item_grants)} item grants, {cp_to_display(package.currency_cp)}") for package in background.package_options]
            choices['background-equipment'] = tuple(base)
            if background.gold_option_cp is not None:
                choices['background-equipment'] = choices['background-equipment'] + (ChoiceView(option_id=EquipmentSelectionMode.GOLD.value, label=cp_to_display(background.gold_option_cp), detail='take background gold'),)
        elif phase == CreationPhase.CHOOSE_CLASS_EQUIPMENT:
            class_record = self.catalog.classes[state.class_id]
            base = [ChoiceView(option_id=package.package_id, label=package.label, detail=f"{len(package.item_grants)} item grants, {cp_to_display(package.currency_cp)}") for package in class_record.package_options]
            choices['class-equipment'] = tuple(base)
            if self.policy.allow_class_wealth and class_record.wealth_option is not None:
                choices['class-equipment'] = choices['class-equipment'] + (ChoiceView(option_id=EquipmentSelectionMode.WEALTH.value, label=class_record.wealth_option.label, detail='roll deterministic class wealth'),)
        elif phase == CreationPhase.REVIEW:
            choices['items'] = tuple(ChoiceView(option_id=item.record_id, label=item.name, detail=f"{cp_to_display(item.cost_cp)}") for item in self.catalog.items.values() if item.cost_cp > 0)
            choices['confirm'] = (
                ChoiceView(option_id='confirm', label='Confirm character', detail='Finish item choices and create the character record.'),
            )
        elif phase == CreationPhase.COMPLETE:
            choices['items'] = tuple(ChoiceView(option_id=item.record_id, label=item.name, detail=f"{cp_to_display(item.cost_cp)}") for item in self.catalog.items.values() if item.cost_cp > 0)
        return choices

    def inspect(self, kind: ContentKind, record_id: str) -> InspectionView:
        if kind == ContentKind.SPECIES:
            record = self.catalog.species[record_id]
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Size options: {', '.join(record.size_options)}", f"Speed: {record.speed}", f"Traits: {', '.join(record.traits)}"))
        if kind == ContentKind.CLASS:
            record = self.catalog.classes[record_id]
            wealth_line = record.wealth_option.label if record.wealth_option is not None else 'none'
            feature_choice_line = '; '.join(f"{group.label}: {', '.join(option.label for option in group.options)}" for group in record.class_feature_choice_groups) or 'none'
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Primary abilities: {', '.join(ability.value for ability in record.primary_abilities) or 'none'}", f"Saving throws: {', '.join(ability.value for ability in record.saving_throw_proficiencies)}", f"Skill choices: choose {record.skill_choice_count} from {', '.join(self._skill_name(skill_id) for skill_id in record.class_skill_option_ids)}", f"Level-1 class choices: {feature_choice_line}", f"Wealth option: {wealth_line}"))
        if kind == ContentKind.BACKGROUND:
            record = self.catalog.backgrounds[record_id]
            asi_detail = 'any ability +2, another +1, or +1 to three abilities' if record.flexible_asi else ', '.join(ability.value for ability in record.allowed_asi_abilities)
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"ASI abilities: {asi_detail}", f"Origin feat: {self._background_origin_feat_detail(record.record_id)}", f"Skills: {', '.join(record.skill_proficiencies) or 'none'}", f"Background skill choices: {record.background_skill_choice_count}", f"Tools: {', '.join(record.tool_proficiencies) or 'none'}"))
        if kind == ContentKind.FEAT:
            record = self.catalog.feats[record_id]
            prerequisite = record.prerequisite or 'none'
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Category: {record.category}", f"Prerequisite: {prerequisite}", f"Selectable as custom origin feat: {'yes' if record.selectable_for_custom_origin else 'no'}"))
        if kind == ContentKind.SKILL:
            record = self.catalog.skills[record_id]
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Ability: {record.ability.value}",))
        if kind == ContentKind.TOOL:
            record = self.catalog.tools[record_id]
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Category: {record.category}",))
        if kind == ContentKind.SPELL:
            record = self.catalog.spells[record_id]
            class_names = ', '.join(self.catalog.classes[class_id].name for class_id in record.class_ids)
            return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Level: {record.level}", f"Classes: {class_names or 'none'}"))
        record = self.catalog.items[record_id]
        return InspectionView(kind=kind, record_id=record.record_id, name=record.name, source=record.source, detail_lines=(f"Cost: {cp_to_display(record.cost_cp)}", f"Tags: {', '.join(record.tags) or 'none'}"))

    def dispatch(self, state: CreationState, intent: CreationIntent) -> CreationState:
        events = self._resolve_intent(state, intent)
        for event in events:
            self._apply_event(state, event)
        return state

    def _validate_choice_resolution(self, pending_choice: PendingChoice, option_ids: tuple[str, ...]) -> tuple[str, ...]:
        unique_option_ids = tuple(dict.fromkeys(option_ids))
        if len(unique_option_ids) != len(option_ids):
            raise ValidationError('Creation choices cannot contain duplicate selections.')
        if len(unique_option_ids) != pending_choice.group.constraint.required_count:
            raise ValidationError(f"Choose exactly {pending_choice.group.constraint.required_count} option(s) for {pending_choice.group.label}.")
        legal_option_ids = {option.option_id for option in pending_choice.group.options}
        for option_id in unique_option_ids:
            if option_id not in legal_option_ids:
                raise ValidationError(f"{option_id} is not a legal option for {pending_choice.group.label}.")
        return unique_option_ids

    def _resolve_intent(self, state: CreationState, intent: CreationIntent) -> list[object]:
        if isinstance(intent, BeginCreationIntent):
            if state.started:
                raise ValidationError('Creation has already started.')
            return [CreationStartedEvent()]
        if isinstance(intent, ChooseSpeciesIntent):
            if self.phase(state) != CreationPhase.CHOOSE_SPECIES:
                raise ValidationError('Species can only be chosen at the species step.')
            if intent.species_id not in self.catalog.species:
                raise ValidationError('Species is not available under the current DM policy.')
            return [SpeciesChosenEvent(species_id=intent.species_id)]
        if isinstance(intent, ChooseClassIntent):
            if self.phase(state) != CreationPhase.CHOOSE_CLASS:
                raise ValidationError('Class can only be chosen at the class step.')
            if intent.class_id not in self.catalog.classes:
                raise ValidationError('Class is not available under the current DM policy.')
            return [ClassChosenEvent(class_id=intent.class_id)]
        if isinstance(intent, ChooseClassSkillsIntent):
            if self.phase(state) != CreationPhase.CHOOSE_CLASS_SKILLS:
                raise ValidationError('Class skills can only be chosen after selecting a class.')
            class_record = self.catalog.classes[state.class_id]
            normalized_skills: list[str] = []
            for requested in intent.skill_ids:
                if requested in class_record.class_skill_option_ids:
                    normalized_skills.append(requested)
                    continue
                matching_id = next((skill_id for skill_id in class_record.class_skill_option_ids if self.catalog.skills[skill_id].name == requested), None)
                if matching_id is None:
                    raise ValidationError(f"{requested} is not a legal class skill for {class_record.name}.")
                normalized_skills.append(matching_id)
            unique_skills = tuple(dict.fromkeys(normalized_skills))
            if len(unique_skills) != class_record.skill_choice_count:
                raise ValidationError(f"Choose exactly {class_record.skill_choice_count} class skills.")
            return [ClassSkillsChosenEvent(skill_ids=unique_skills)]
        if isinstance(intent, ChooseBackgroundIntent):
            if self.phase(state) != CreationPhase.CHOOSE_BACKGROUND:
                raise ValidationError('Background can only be chosen at the background step.')
            if intent.background_id not in self.catalog.backgrounds:
                raise ValidationError('Background is not available under the current DM policy.')
            return [BackgroundChosenEvent(background_id=intent.background_id)]
        if isinstance(intent, ResolveCreationChoiceIntent):
            if self.phase(state) != CreationPhase.CHOOSE_CREATION_CHOICES:
                raise ValidationError('Creation choices are not available at this step.')
            pending_choice = self._next_pending_creation_choice(state)
            if pending_choice is None:
                raise ValidationError('There are no pending creation choices.')
            if intent.choice_id != pending_choice.group.choice_id:
                raise ValidationError(f"Resolve the current pending choice {pending_choice.group.choice_id} before selecting another creation choice.")
            return [CreationChoiceResolvedEvent(choice_id=intent.choice_id, option_ids=self._validate_choice_resolution(pending_choice, intent.option_ids))]
        if isinstance(intent, ChooseOriginFeatIntent):
            pending_choice = self._next_pending_creation_choice(state)
            if pending_choice is None or pending_choice.category != CreationChoiceCategory.ORIGIN_FEAT:
                raise ValidationError('Origin feat choice is not the current pending creation choice.')
            return [CreationChoiceResolvedEvent(choice_id=pending_choice.group.choice_id, option_ids=self._validate_choice_resolution(pending_choice, (intent.feat_id,)))]
        if isinstance(intent, GenerateRolledAbilitiesIntent):
            if self.phase(state) != CreationPhase.GENERATE_ABILITIES:
                raise ValidationError('Rolled scores are not available at this step.')
            if self.policy.ability_generation_mode == AbilityGenerationMode.POINT_BUY_ONLY:
                raise ValidationError('DM policy only allows point buy.')
            rng = seeded_random(self.seed, state.random_counter)
            scores, breakdown = roll_six_ability_scores(rng)
            events = [RolledAbilityScoresGeneratedEvent(scores=scores, roll_breakdown=breakdown, random_counter_used=state.random_counter)]
            if self.policy.ability_generation_mode in {AbilityGenerationMode.ROLL_ONLY, AbilityGenerationMode.ROLL_OR_POINT_BUY}:
                events.append(AbilityArrayChosenEvent(method=AbilityMethod.ROLLED))
            return events
        if isinstance(intent, SetPointBuyScoresIntent):
            if self.phase(state) != CreationPhase.GENERATE_ABILITIES:
                raise ValidationError('Point buy is not available at this step.')
            if self.policy.ability_generation_mode == AbilityGenerationMode.ROLL_ONLY:
                raise ValidationError('DM policy only allows rolling.')
            total_cost = validate_point_buy_scores(intent.scores)
            events = [PointBuyScoresSetEvent(scores=intent.scores, total_cost=total_cost)]
            if self.policy.ability_generation_mode in {AbilityGenerationMode.POINT_BUY_ONLY, AbilityGenerationMode.ROLL_OR_POINT_BUY}:
                events.append(AbilityArrayChosenEvent(method=AbilityMethod.POINT_BUY))
            return events
        if isinstance(intent, ChooseAbilityArrayIntent):
            if self.phase(state) != CreationPhase.CHOOSE_ABILITY_ARRAY:
                raise ValidationError('Ability array choice is not available at this step.')
            rolled_scores = state.ability_draft.rolled_scores
            point_buy_scores = state.ability_draft.point_buy_scores
            if rolled_scores is None or point_buy_scores is None:
                raise ValidationError('Both rolled and point-buy arrays must exist before choosing.')
            if intent.method not in higher_total_methods(rolled_scores, point_buy_scores):
                raise ValidationError('DM policy only allows choosing the higher total array.')
            return [AbilityArrayChosenEvent(method=intent.method)]
        if isinstance(intent, AssignAbilityScoresIntent):
            if self.phase(state) != CreationPhase.ASSIGN_ABILITIES:
                raise ValidationError('Ability assignment is not available at this step.')
            chosen_scores = state.ability_draft.chosen_scores()
            if chosen_scores is None:
                raise ValidationError('No ability array has been selected yet.')
            provided = tuple(intent.assignments[ability] for ability in ABILITY_ORDER)
            if not arrays_match_multiset(chosen_scores, provided):
                raise ValidationError('Assigned ability scores must use exactly the generated scores.')
            return [AbilitiesAssignedEvent(assignments=dict(intent.assignments))]
        if isinstance(intent, ChooseBackgroundAsiIntent):
            if self.phase(state) != CreationPhase.CHOOSE_BACKGROUND_ASI:
                raise ValidationError('Background ASI choice is not available at this step.')
            background = self.catalog.backgrounds[state.background_id]
            option = next((option for option in background.ability_increase_options() if option.option_id == intent.option_id), None)
            if option is None:
                raise ValidationError('That ASI option is not legal for the selected background.')
            final_scores = dict(state.assigned_abilities)
            for ability, bonus in option.bonuses.items():
                if final_scores[ability] + bonus > 20:
                    raise ValidationError('Background ASI cannot raise an ability above 20.')
            return [BackgroundAsiAppliedEvent(option_id=option.option_id, bonuses=dict(option.bonuses))]
        if isinstance(intent, ChooseBackgroundEquipmentIntent):
            if self.phase(state) != CreationPhase.CHOOSE_BACKGROUND_EQUIPMENT:
                raise ValidationError('Background equipment choice is not available at this step.')
            background = self.catalog.backgrounds[state.background_id]
            if intent.mode == EquipmentSelectionMode.GOLD:
                if background.gold_option_cp is None:
                    raise ValidationError('The selected background does not expose a mirror-backed gold option.')
                return [BackgroundEquipmentChosenEvent(mode=intent.mode, package_id=None, item_grants=(), currency_cp_delta=background.gold_option_cp)]
            if intent.mode != EquipmentSelectionMode.PACKAGE:
                raise ValidationError('Background equipment must be a package or gold.')
            package = next((package for package in background.package_options if package.package_id == intent.package_id), None)
            if package is None:
                raise ValidationError('Unknown background equipment package.')
            return [BackgroundEquipmentChosenEvent(mode=intent.mode, package_id=package.package_id, item_grants=package.item_grants, currency_cp_delta=package.currency_cp)]
        if isinstance(intent, ChooseClassEquipmentIntent):
            if self.phase(state) != CreationPhase.CHOOSE_CLASS_EQUIPMENT:
                raise ValidationError('Class equipment choice is not available at this step.')
            class_record = self.catalog.classes[state.class_id]
            if intent.mode == EquipmentSelectionMode.WEALTH:
                if not self.policy.allow_class_wealth:
                    raise ValidationError('DM policy does not allow class wealth.')
                if class_record.wealth_option is None:
                    raise ValidationError('The selected class does not expose a mirror-backed wealth option.')
                rng = seeded_random(self.seed, state.random_counter)
                total_roll, roll_breakdown = roll_dice(rng, die_count=class_record.wealth_option.die_count, die_faces=class_record.wealth_option.die_faces)
                return [ClassEquipmentChosenEvent(mode=intent.mode, package_id=None, item_grants=(), currency_cp_delta=total_roll * class_record.wealth_option.multiplier_cp, random_counter_used=state.random_counter, roll_breakdown=roll_breakdown)]
            if intent.mode != EquipmentSelectionMode.PACKAGE:
                raise ValidationError('Class equipment must be a package or wealth.')
            package = next((package for package in class_record.package_options if package.package_id == intent.package_id), None)
            if package is None:
                raise ValidationError('Unknown class equipment package.')
            return [ClassEquipmentChosenEvent(mode=intent.mode, package_id=package.package_id, item_grants=package.item_grants, currency_cp_delta=package.currency_cp)]
        if isinstance(intent, BuyItemIntent):
            if self.phase(state) not in {CreationPhase.REVIEW, CreationPhase.COMPLETE}:
                raise ValidationError('Item purchases are only available after both equipment choices are locked.')
            if intent.item_id not in self.catalog.items:
                raise ValidationError('Item is not available under the current DM policy.')
            if intent.quantity <= 0:
                raise ValidationError('Purchase quantity must be positive.')
            item = self.catalog.items[intent.item_id]
            total_cost = item.cost_cp * intent.quantity
            if total_cost > state.currency_cp:
                raise ValidationError('Not enough gold to complete that purchase.')
            return [ItemPurchasedEvent(item_id=intent.item_id, quantity=intent.quantity, total_cost_cp=total_cost)]
        if isinstance(intent, ConfirmCharacterIntent):
            if self.phase(state) != CreationPhase.REVIEW:
                raise ValidationError('Character confirmation is only available after all required choices are complete.')
            return [CreationConfirmedEvent(record=self._build_character_record(state))]
        raise ValidationError(f'Unsupported intent: {intent!r}')

    def _apply_event(self, state: CreationState, event: object) -> None:
        state.event_log.append(event)
        if isinstance(event, CreationStartedEvent):
            state.started = True
        elif isinstance(event, SpeciesChosenEvent):
            state.species_id = event.species_id
        elif isinstance(event, ClassChosenEvent):
            state.class_id = event.class_id
            state.class_skill_ids = ()
        elif isinstance(event, ClassSkillsChosenEvent):
            state.class_skill_ids = event.skill_ids
        elif isinstance(event, BackgroundChosenEvent):
            state.background_id = event.background_id
        elif isinstance(event, CreationChoiceResolvedEvent):
            state.resolved_creation_choices[event.choice_id] = event.option_ids
        elif isinstance(event, RolledAbilityScoresGeneratedEvent):
            state.ability_draft.rolled_scores = event.scores
            state.ability_draft.roll_breakdown = event.roll_breakdown
            state.random_counter = event.random_counter_used + 1
        elif isinstance(event, PointBuyScoresSetEvent):
            state.ability_draft.point_buy_scores = event.scores
        elif isinstance(event, AbilityArrayChosenEvent):
            state.ability_draft.chosen_method = event.method
        elif isinstance(event, AbilitiesAssignedEvent):
            state.assigned_abilities = event.assignments
        elif isinstance(event, BackgroundAsiAppliedEvent):
            state.background_asi_option_id = event.option_id
            state.background_asi_bonuses = event.bonuses
        elif isinstance(event, BackgroundEquipmentChosenEvent):
            state.background_equipment_mode = event.mode
            state.background_package_id = event.package_id
            state.currency_cp += event.currency_cp_delta
            _add_items(state.inventory, event.item_grants)
        elif isinstance(event, ClassEquipmentChosenEvent):
            state.class_equipment_mode = event.mode
            state.class_package_id = event.package_id
            state.currency_cp += event.currency_cp_delta
            _add_items(state.inventory, event.item_grants)
            if event.random_counter_used is not None:
                state.random_counter = event.random_counter_used + 1
        elif isinstance(event, ItemPurchasedEvent):
            state.currency_cp -= event.total_cost_cp
            state.inventory[event.item_id] = state.inventory.get(event.item_id, 0) + event.quantity
        elif isinstance(event, CreationConfirmedEvent):
            state.character_record = event.record

    def _build_choice_resolution_record(self, state: CreationState, pending_choice: PendingChoice) -> ResolvedCreationChoice | None:
        selected_option_ids = state.resolved_creation_choices.get(pending_choice.group.choice_id)
        if not selected_option_ids:
            return None
        option_labels: list[str] = []
        for option_id in selected_option_ids:
            matched = next((option.label for option in pending_choice.group.options if option.option_id == option_id), None)
            option_labels.append(matched or option_id)
        return ResolvedCreationChoice(choice_id=pending_choice.group.choice_id, category=pending_choice.category, source=pending_choice.source, selected_option_ids=selected_option_ids, selected_option_labels=tuple(option_labels))

    def _resolved_creation_choice_records(self, state: CreationState) -> tuple[ResolvedCreationChoice, ...]:
        choices: list[ResolvedCreationChoice] = []
        existing_choice_ids: set[str] = set()
        for builder in (self._background_skill_choice, self._background_tool_choice, self._class_tool_choice):
            choice = builder(state)
            if choice is not None:
                record = self._build_choice_resolution_record(state, choice)
                if record is not None:
                    choices.append(record)
                    existing_choice_ids.add(record.choice_id)
        for choice in self._class_feature_pending_choices(state):
            record = self._build_choice_resolution_record(state, choice)
            if record is not None and record.choice_id not in existing_choice_ids:
                choices.append(record)
                existing_choice_ids.add(record.choice_id)
        for builder in (self._fighter_fighting_style_choice, self._rogue_expertise_choice, self._weapon_mastery_choice, self._class_cantrip_choice, self._class_spell_choice):
            choice = builder(state)
            if choice is not None:
                record = self._build_choice_resolution_record(state, choice)
                if record is not None and record.choice_id not in existing_choice_ids:
                    choices.append(record)
                    existing_choice_ids.add(record.choice_id)
        if state.class_id is not None:
            class_record = self.catalog.classes[state.class_id]
            class_source = ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name)
            for group, option in self._selected_class_feature_options(state):
                for bundle in option.spell_choice_bundles:
                    choice_id = f"{group.choice_id}:{bundle.choice_id}"
                    if choice_id not in state.resolved_creation_choices:
                        continue
                    if bundle.cantrip_count > 0:
                        choice = PendingChoice(
                            group=ChoiceGroup(choice_id=choice_id, label=bundle.label, prompt='', options=self._spell_choice_options(level=0, class_ids=bundle.spell_list_class_ids), constraint=SelectionConstraint(required_count=bundle.cantrip_count)),
                            source=class_source,
                            category=CreationChoiceCategory.CANTRIP,
                            resolution_status=ChoiceResolutionStatus.RESOLVED,
                        )
                    else:
                        choice = PendingChoice(
                            group=ChoiceGroup(choice_id=choice_id, label=bundle.label, prompt='', options=self._spell_choice_options(level=bundle.spell_level, class_ids=bundle.spell_list_class_ids), constraint=SelectionConstraint(required_count=bundle.spell_count)),
                            source=class_source,
                            category=CreationChoiceCategory.SPELL,
                            resolution_status=ChoiceResolutionStatus.RESOLVED,
                        )
                    record = self._build_choice_resolution_record(state, choice)
                    if record is not None and record.choice_id not in existing_choice_ids:
                        choices.append(record)
                        existing_choice_ids.add(record.choice_id)
        for slot in self._origin_feat_slots(state):
            slot_choice = self._origin_feat_slot_choice(slot, state)
            if slot_choice is not None:
                record = self._build_choice_resolution_record(state, slot_choice)
                if record is not None and record.choice_id not in existing_choice_ids:
                    choices.append(record)
                    existing_choice_ids.add(record.choice_id)
            selected_option = self._selected_feat_option(slot, state)
            if selected_option is None:
                continue
            feat = self.catalog.feats[selected_option.feat_id]
            grant = _SelectedFeatGrant(slot_id=slot.choice_id, source=slot.source, feat_option=selected_option)
            for group in feat.proficiency_choice_groups:
                choice = self._feat_proficiency_choice(state, grant, group)
                if choice is not None:
                    record = self._build_choice_resolution_record(state, choice)
                    if record is not None and record.choice_id not in existing_choice_ids:
                        choices.append(record)
                        existing_choice_ids.add(record.choice_id)
            for bundle in feat.spell_choice_bundles:
                for suffix in ('spell-list', 'ability', 'cantrips', 'spell'):
                    choice = self._feat_bundle_next_choice(state, grant, bundle)
                    if choice is None:
                        choice_id = f"{grant.slot_id}:{bundle.choice_id}:{suffix}"
                        if choice_id not in state.resolved_creation_choices:
                            continue
                        if suffix == 'spell-list':
                            choice = PendingChoice(group=ChoiceGroup(choice_id=choice_id, label=f"{feat.name} spell list", prompt='', options=tuple(ChoiceOption(option_id=class_id, label=self.catalog.classes[class_id].name, detail='spell list') for class_id in bundle.spell_list_class_ids), constraint=SelectionConstraint(required_count=1)), source=ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name), category=CreationChoiceCategory.SPELL_LIST, resolution_status=ChoiceResolutionStatus.RESOLVED)
                        elif suffix == 'ability':
                            choice = PendingChoice(group=ChoiceGroup(choice_id=choice_id, label=f"{feat.name} spellcasting ability", prompt='', options=tuple(ChoiceOption(option_id=ability.value, label=ability.value, detail='spellcasting ability') for ability in bundle.spellcasting_ability_options), constraint=SelectionConstraint(required_count=1)), source=ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name), category=CreationChoiceCategory.SPELLCASTING_ABILITY, resolution_status=ChoiceResolutionStatus.RESOLVED)
                        elif suffix == 'cantrips':
                            selected_class_id = self._feat_bundle_selected_class_id(state, grant, bundle)
                            if selected_class_id is None:
                                continue
                            choice = PendingChoice(group=ChoiceGroup(choice_id=choice_id, label=f"{feat.name} cantrips", prompt='', options=self._spell_choice_options(class_id=selected_class_id, level=0), constraint=SelectionConstraint(required_count=bundle.cantrip_count)), source=ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name), category=CreationChoiceCategory.CANTRIP, resolution_status=ChoiceResolutionStatus.RESOLVED)
                        else:
                            selected_class_id = self._feat_bundle_selected_class_id(state, grant, bundle)
                            if selected_class_id is None:
                                continue
                            choice = PendingChoice(group=ChoiceGroup(choice_id=choice_id, label=f"{feat.name} spell", prompt='', options=self._spell_choice_options(class_id=selected_class_id, level=bundle.spell_level), constraint=SelectionConstraint(required_count=bundle.spell_count)), source=ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name), category=CreationChoiceCategory.SPELL, resolution_status=ChoiceResolutionStatus.RESOLVED)
                    record = self._build_choice_resolution_record(state, choice)
                    if record is not None and record.choice_id not in existing_choice_ids:
                        choices.append(record)
                        existing_choice_ids.add(record.choice_id)
        return tuple(choices)

    def _build_character_record(self, state: CreationState) -> CharacterRecord:
        if self._next_pending_creation_choice(state) is not None:
            raise ValidationError('Character record cannot be built before all creation-time choices are resolved.')
        if state.species_id is None or state.class_id is None or state.background_id is None:
            raise ValidationError('Character record cannot be built before species, class, and background are chosen.')
        if state.ability_draft.chosen_method is None or state.ability_draft.chosen_scores() is None:
            raise ValidationError('Character record cannot be built before an ability array is selected.')
        final_scores = state.final_ability_scores()
        class_record = self.catalog.classes[state.class_id]
        background = self.catalog.backgrounds[state.background_id]
        species = self.catalog.species[state.species_id]
        selected_class_feature_options = self._selected_class_feature_options(state)
        class_feature_armor_grants = tuple(
            grant
            for _, option in selected_class_feature_options
            for grant in option.armor_training_grants
        )
        class_feature_weapon_grants = tuple(
            grant
            for _, option in selected_class_feature_options
            for grant in option.weapon_proficiency_grants
        )
        class_armor_training = tuple(dict.fromkeys(class_record.armor_training + class_feature_armor_grants))
        class_weapon_proficiencies = tuple(dict.fromkeys(class_record.weapon_proficiencies + class_feature_weapon_grants))
        con_modifier = ability_modifier(final_scores[Ability.CON])
        max_hp = class_record.hit_die + con_modifier + species.hit_point_bonus_per_level

        class_skill_names = self._skill_names(state.class_skill_ids)
        background_skill_ids = background.skill_proficiency_ids + state.resolved_creation_choices.get(f"background:{background.record_id}:skills", ())
        background_skill_names = self._skill_names(background_skill_ids)
        tool_ids = class_record.tool_proficiency_ids + state.resolved_creation_choices.get(f"class:{class_record.record_id}:tools", ()) + background.tool_proficiency_ids + state.resolved_creation_choices.get(f"background:{background.record_id}:tools", ())
        tool_names = self._tool_names(tuple(dict.fromkeys(tool_ids)))

        proficiency_selections: list[CharacterProficiencySelection] = []
        class_source = ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name)
        background_source = ChoiceSource(ChoiceSourceKind.BACKGROUND, background.record_id, background.name)
        for skill_id in state.class_skill_ids:
            proficiency_selections.append(CharacterProficiencySelection(record_id=skill_id, name=self._skill_name(skill_id), category=ProficiencyCategory.SKILL, source=class_source))
        for skill_id in background_skill_ids:
            proficiency_selections.append(CharacterProficiencySelection(record_id=skill_id, name=self._skill_name(skill_id), category=ProficiencyCategory.SKILL, source=background_source))
        for tool_id in class_record.tool_proficiency_ids + state.resolved_creation_choices.get(f"class:{class_record.record_id}:tools", ()):
            proficiency_selections.append(CharacterProficiencySelection(record_id=tool_id, name=self._tool_name(tool_id), category=ProficiencyCategory.TOOL, source=class_source))
        for tool_id in background.tool_proficiency_ids + state.resolved_creation_choices.get(f"background:{background.record_id}:tools", ()):
            proficiency_selections.append(CharacterProficiencySelection(record_id=tool_id, name=self._tool_name(tool_id), category=ProficiencyCategory.TOOL, source=background_source))

        feat_grants: list[CharacterFeatGrant] = []
        spell_selections: list[CharacterSpellSelection] = []
        class_spellcasting_ability = class_record.spellcasting.spellcasting_ability if class_record.spellcasting is not None else None
        if class_record.spellcasting is not None:
            for spell_id in state.resolved_creation_choices.get(f"class:{class_record.record_id}:cantrips", ()):
                spell = self.catalog.spells[spell_id]
                spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=SpellSelectionKind.CANTRIP, source=class_source, spellcasting_ability=class_record.spellcasting.spellcasting_ability, spell_list_class_id=class_record.record_id))
            for spell_id in state.resolved_creation_choices.get(f"class:{class_record.record_id}:spells", ()):
                spell = self.catalog.spells[spell_id]
                spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=class_record.spellcasting.spell_selection_kind, source=class_source, spellcasting_ability=class_record.spellcasting.spellcasting_ability, spell_list_class_id=class_record.record_id))
        for group, option in selected_class_feature_options:
            for bundle in option.spell_choice_bundles:
                choice_id = f"{group.choice_id}:{bundle.choice_id}"
                selection_kind = SpellSelectionKind.CANTRIP if bundle.cantrip_count > 0 else bundle.spell_selection_kind
                for spell_id in state.resolved_creation_choices.get(choice_id, ()): 
                    spell = self.catalog.spells[spell_id]
                    spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=selection_kind, source=class_source, spellcasting_ability=class_spellcasting_ability, spell_list_class_id=class_record.record_id))
            for granted_spell in option.granted_spells:
                if granted_spell.spell_id not in self.catalog.spells:
                    raise ValidationError(f"Granted class feature spell {granted_spell.spell_id!r} is not available in the creation catalog.")
                spell = self.catalog.spells[granted_spell.spell_id]
                spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=granted_spell.selection_kind, source=class_source, spellcasting_ability=class_spellcasting_ability, spell_list_class_id=class_record.record_id))
        if class_record.record_id == 'ranger' and 'hunter-s-mark' in self.catalog.spells and not any(selection.spell_id == 'hunter-s-mark' and selection.source.source_kind == ChoiceSourceKind.CLASS for selection in spell_selections):
            spell = self.catalog.spells['hunter-s-mark']
            spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=SpellSelectionKind.ALWAYS_PREPARED, source=class_source, spellcasting_ability=class_spellcasting_ability, spell_list_class_id=class_record.record_id))

        for grant in self._selected_feat_grants(state):
            feat = self.catalog.feats[grant.feat_option.feat_id]
            feat_source = ChoiceSource(ChoiceSourceKind.FEAT, feat.record_id, feat.name)
            feat_grants.append(CharacterFeatGrant(feat_id=feat.record_id, feat_name=feat.name, source=grant.source, fixed_metadata=grant.feat_option.fixed_metadata))
            for group in feat.proficiency_choice_groups:
                choice_id = f"{grant.slot_id}:{group.choice_id}"
                for option_id in state.resolved_creation_choices.get(choice_id, ()): 
                    if option_id in self.catalog.skills:
                        proficiency_selections.append(CharacterProficiencySelection(record_id=option_id, name=self._skill_name(option_id), category=ProficiencyCategory.SKILL, source=feat_source))
                    elif option_id in self.catalog.tools:
                        proficiency_selections.append(CharacterProficiencySelection(record_id=option_id, name=self._tool_name(option_id), category=ProficiencyCategory.TOOL, source=feat_source))
            for bundle in feat.spell_choice_bundles:
                selected_class_id = self._feat_bundle_selected_class_id(state, grant, bundle)
                selected_ability = self._feat_spellcasting_ability(state, grant, bundle)
                if selected_class_id is None or selected_ability is None:
                    continue
                for spell_id in state.resolved_creation_choices.get(f"{grant.slot_id}:{bundle.choice_id}:cantrips", ()):
                    spell = self.catalog.spells[spell_id]
                    spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=SpellSelectionKind.CANTRIP, source=feat_source, spellcasting_ability=selected_ability, spell_list_class_id=selected_class_id))
                for spell_id in state.resolved_creation_choices.get(f"{grant.slot_id}:{bundle.choice_id}:spell", ()):
                    spell = self.catalog.spells[spell_id]
                    spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=bundle.spell_selection_kind, source=feat_source, spellcasting_ability=selected_ability, spell_list_class_id=selected_class_id))

        level_one_class_feature_names_by_class = {
            'barbarian': ('Rage', 'Unarmored Defense', 'Weapon Mastery'),
            'bard': ('Bardic Inspiration', 'Spellcasting'),
            'cleric': ('Spellcasting', 'Divine Order'),
            'druid': ('Druidic', 'Primal Order', 'Spellcasting'),
            'fighter': ('Fighting Style', 'Second Wind', 'Weapon Mastery'),
            'monk': ('Martial Arts', 'Unarmored Defense'),
            'paladin': ('Lay on Hands', 'Spellcasting', 'Weapon Mastery'),
            'ranger': ('Spellcasting', 'Favored Enemy', 'Weapon Mastery'),
            'rogue': ('Expertise', 'Sneak Attack', "Thieves' Cant", 'Weapon Mastery'),
            'sorcerer': ('Spellcasting', 'Innate Sorcery'),
            'warlock': ('Eldritch Invocations', 'Pact Magic', 'Eldritch Invocation Options'),
            'wizard': ('Spellcasting', 'Ritual Adept', 'Arcane Recovery'),
        }
        expertise_choice_ids = state.resolved_creation_choices.get('class:rogue:expertise', ())
        expertise_skill_ids = tuple(option_id for option_id in expertise_choice_ids if option_id in self.catalog.skills)
        expertise_tool_ids = tuple(option_id for option_id in expertise_choice_ids if option_id in self.catalog.tools)
        fighting_style_names = tuple(
            self.catalog.feats[option_id].name if option_id in self.catalog.feats else option_id
            for option_id in state.resolved_creation_choices.get('class:fighter:fighting-style', ())
        )
        weapon_mastery_item_ids = tuple(state.resolved_creation_choices.get(f'class:{class_record.record_id}:weapon-mastery', ()))
        class_feature_traits = [f"{group.label}: {option.label}" for group, option in selected_class_feature_options]
        class_feature_names = tuple(dict.fromkeys(level_one_class_feature_names_by_class.get(class_record.record_id, ()) + tuple(option.label for _, option in selected_class_feature_options)))
        all_traits = tuple(dict.fromkeys(list(species.traits) + [f"Class: {class_record.name}", f"Background: {background.name}"] + list(level_one_class_feature_names_by_class.get(class_record.record_id, ())) + class_feature_traits))
        return CharacterRecord(
            record_id='level-1-character',
            level=1,
            species_id=species.record_id,
            class_id=class_record.record_id,
            background_id=background.record_id,
            source_refs=(species.source, class_record.source, background.source),
            ability_scores=final_scores,
            ability_modifiers={ability: ability_modifier(score) for ability, score in final_scores.items()},
            base_ability_array=state.ability_draft.chosen_scores() or (),
            chosen_ability_method=state.ability_draft.chosen_method,
            max_hit_points=max_hp,
            proficiency_bonus=2,
            saving_throw_proficiencies=class_record.saving_throw_proficiencies,
            class_skill_proficiencies=class_skill_names,
            background_skill_proficiencies=background_skill_names,
            tool_proficiencies=tool_names,
            armor_training=class_armor_training,
            weapon_proficiencies=class_weapon_proficiencies,
            traits=all_traits,
            origin_feats=self._origin_feat_names(state),
            inventory=dict(state.inventory),
            currency_cp=state.currency_cp,
            proficiency_selections=tuple(proficiency_selections),
            spell_selections=tuple(spell_selections),
            feat_grants=tuple(feat_grants),
            resolved_creation_choices=self._resolved_creation_choice_records(state),
            class_levels=(CharacterClassLevel(class_id=class_record.record_id, level=1),),
            expertise_skill_ids=expertise_skill_ids,
            expertise_tool_ids=expertise_tool_ids,
            fighting_style_names=fighting_style_names,
            weapon_mastery_item_ids=weapon_mastery_item_ids,
            class_feature_names=class_feature_names,
        )
