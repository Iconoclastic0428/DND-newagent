from __future__ import annotations

from dataclasses import replace

from shared_types.advancement import (
    AdvancementChoiceCategory,
    AdvancementChoiceSource,
    AdvancementChoiceSourceKind,
    AdvancementCommitStatus,
    AdvancementRuntimeState,
    AdvancementTransaction,
    AdvancementValidationStatus,
    ClassLevelAllocation,
    HitPointGainRecord,
    PendingAdvancementChoice,
    ResolvedAdvancementChoice,
)
from shared_types.encounter_events import (
    AdvancementChoiceGeneratedEvent,
    AdvancementChoiceResolvedEvent,
    AdvancementClassChosenEvent,
    AdvancementCommitSucceededEvent,
    AdvancementTransactionStartedEvent,
    AdvancementValidatedEvent,
    CharacterLevelIncreasedEvent,
    ClassLevelIncreasedEvent,
    FeatureUnlockedEvent,
    HitPointsIncreasedEvent,
    ProficiencyBonusUpdatedEvent,
)
from shared_types.errors import EncounterValidationError
from shared_types.models import (
    Ability,
    CharacterClassLevel,
    CharacterRecord,
    CharacterSpellSelection,
    CharacterSubclassSelection,
    ChoiceGroup,
    ChoiceOption,
    ChoiceResolutionStatus,
    ChoiceSource,
    ChoiceSourceKind,
    ClassFeatureChoiceGroup,
    ClassRecord,
    ContentCatalog,
    ResolvedAdvancementChoiceRecord,
    SelectionConstraint,
    SpellSelectionKind,
    class_level_for,
    has_subclass_selection,
    normalized_class_levels,
    total_character_level,
)
from shared_types.progression import PendingLevelUpRecord

from rules_engine.rng import seeded_random


class CharacterAdvancementEngine:
    def copy_state(self, state: AdvancementRuntimeState) -> AdvancementRuntimeState:
        return AdvancementRuntimeState(
            policy=state.policy,
            transactions=dict(state.transactions),
            actor_transaction_ids=dict(state.actor_transaction_ids),
            random_counter=state.random_counter,
        )

    def start_transaction(
        self,
        state: AdvancementRuntimeState,
        *,
        actor_id: str,
        actor_label: str,
        record: CharacterRecord,
        pending_record: PendingLevelUpRecord,
        timestamp_seconds: int,
        catalog: ContentCatalog,
    ) -> tuple[AdvancementRuntimeState, AdvancementTransaction, tuple[object, ...]]:
        if actor_id in state.actor_transaction_ids:
            raise EncounterValidationError('This actor already has an open advancement transaction.')
        current_total_level = total_character_level(record)
        if pending_record.actor_id != actor_id:
            raise EncounterValidationError('The pending level-up does not belong to this actor.')
        if pending_record.applied:
            raise EncounterValidationError('That pending level-up has already been applied.')
        if pending_record.target_new_total_level != current_total_level + 1:
            raise EncounterValidationError('Only the next pending level-up can be applied.')
        updated = self.copy_state(state)
        transaction = AdvancementTransaction(
            transaction_id=f'advancement:{actor_id}:{pending_record.pending_id}',
            actor_id=actor_id,
            actor_label=actor_label,
            source_pending_level_up_id=pending_record.pending_id,
            source_mode=pending_record.source_mode,
            current_total_level=current_total_level,
            target_total_level=pending_record.target_new_total_level,
            created_timestamp_seconds=timestamp_seconds,
        )
        updated.transactions[transaction.transaction_id] = transaction
        updated.actor_transaction_ids[actor_id] = transaction.transaction_id
        events: list[object] = [AdvancementTransactionStartedEvent(transaction=transaction)]
        legal_allocations = self._legal_class_allocations(record=record, catalog=catalog, state=updated)
        if len(legal_allocations) == 1:
            updated, transaction, choose_events = self.choose_class(
                updated,
                transaction_id=transaction.transaction_id,
                chosen_class_id=legal_allocations[0].class_id,
                record=record,
                catalog=catalog,
            )
            events.extend(choose_events)
        return updated, transaction, tuple(events)

    def cancel_transaction(self, state: AdvancementRuntimeState, *, actor_id: str) -> AdvancementRuntimeState:
        transaction = self._require_actor_transaction(state, actor_id)
        updated = self.copy_state(state)
        updated.transactions.pop(transaction.transaction_id, None)
        updated.actor_transaction_ids.pop(actor_id, None)
        return updated

    def choose_class(
        self,
        state: AdvancementRuntimeState,
        *,
        transaction_id: str,
        chosen_class_id: str,
        record: CharacterRecord,
        catalog: ContentCatalog,
    ) -> tuple[AdvancementRuntimeState, AdvancementTransaction, tuple[object, ...]]:
        transaction = self._require_transaction(state, transaction_id)
        if chosen_class_id not in catalog.classes:
            raise EncounterValidationError('Unknown class selection for advancement.')
        class_record = catalog.classes[chosen_class_id]
        current_class_level = class_level_for(record, chosen_class_id)
        is_multiclass = current_class_level == 0
        if is_multiclass and not state.policy.allow_multiclass:
            raise EncounterValidationError('Multiclass advancement is disabled by the active advancement policy.')
        if is_multiclass:
            self._validate_multiclass_prerequisites(record=record, class_record=class_record)
        target_class_level = current_class_level + 1
        source = AdvancementChoiceSource(
            source_kind=(AdvancementChoiceSourceKind.MULTICLASS if is_multiclass else AdvancementChoiceSourceKind.CLASS_LEVEL),
            class_id=class_record.record_id,
            class_name=class_record.name,
            class_level=target_class_level,
        )
        pending_choices, generated_feature_names = self._generate_pending_choices(
            transaction_id=transaction.transaction_id,
            record=record,
            class_record=class_record,
            target_class_level=target_class_level,
            catalog=catalog,
            source=source,
        )
        validation_status = AdvancementValidationStatus.READY_TO_COMMIT if not pending_choices else AdvancementValidationStatus.BLOCKED_BY_PENDING_CHOICES
        updated_transaction = replace(
            transaction,
            chosen_class_id=class_record.record_id,
            chosen_class_level=target_class_level,
            pending_choices=pending_choices,
            resolved_choices=(),
            generated_feature_names=generated_feature_names,
            validation_status=validation_status,
            commit_status=AdvancementCommitStatus.OPEN,
            error_text='',
        )
        updated = self.copy_state(state)
        updated.transactions[transaction_id] = updated_transaction
        events: list[object] = [
            AdvancementClassChosenEvent(
                transaction_id=transaction_id,
                actor_id=transaction.actor_id,
                class_id=class_record.record_id,
                target_class_level=target_class_level,
            ),
            AdvancementValidatedEvent(
                transaction_id=transaction_id,
                actor_id=transaction.actor_id,
                status=validation_status,
                generated_feature_names=generated_feature_names,
            ),
        ]
        events.extend(
            AdvancementChoiceGeneratedEvent(transaction_id=transaction_id, actor_id=transaction.actor_id, choice=choice)
            for choice in pending_choices
        )
        return updated, updated_transaction, tuple(events)

    def resolve_choice(
        self,
        state: AdvancementRuntimeState,
        *,
        actor_id: str,
        choice_id: str,
        option_ids: tuple[str, ...],
    ) -> tuple[AdvancementRuntimeState, AdvancementTransaction, tuple[object, ...]]:
        transaction = self._require_actor_transaction(state, actor_id)
        pending_choice = next((choice for choice in transaction.pending_choices if choice.group.choice_id == choice_id), None)
        if pending_choice is None:
            raise EncounterValidationError('That advancement choice is not pending for this actor.')
        unique_option_ids = tuple(dict.fromkeys(option_ids))
        if len(unique_option_ids) != len(option_ids):
            raise EncounterValidationError('Advancement choices cannot contain duplicate selections.')
        if len(unique_option_ids) != pending_choice.group.constraint.required_count:
            raise EncounterValidationError(f'Choose exactly {pending_choice.group.constraint.required_count} option(s) for {pending_choice.group.label}.')
        legal_option_ids = {option.option_id for option in pending_choice.group.options}
        for option_id in unique_option_ids:
            if option_id not in legal_option_ids:
                raise EncounterValidationError(f'{option_id} is not a legal option for {pending_choice.group.label}.')
        selected_labels = tuple(next(option.label for option in pending_choice.group.options if option.option_id == option_id) for option_id in unique_option_ids)
        resolved_choice = ResolvedAdvancementChoice(
            choice_id=choice_id,
            category=pending_choice.category,
            source=pending_choice.source,
            selected_option_ids=unique_option_ids,
            selected_option_labels=selected_labels,
        )
        resolved_map = {choice.choice_id: choice for choice in transaction.resolved_choices}
        resolved_map[choice_id] = resolved_choice
        updated_pending_choices = tuple(
            replace(choice, resolution_status=(ChoiceResolutionStatus.RESOLVED if choice.group.choice_id in resolved_map else ChoiceResolutionStatus.PENDING))
            for choice in transaction.pending_choices
        )
        unresolved = [choice for choice in updated_pending_choices if choice.blocks_finalization and choice.resolution_status != ChoiceResolutionStatus.RESOLVED]
        updated_transaction = replace(
            transaction,
            pending_choices=updated_pending_choices,
            resolved_choices=tuple(resolved_map[choice.group.choice_id] for choice in updated_pending_choices if choice.group.choice_id in resolved_map),
            validation_status=(AdvancementValidationStatus.READY_TO_COMMIT if not unresolved else AdvancementValidationStatus.BLOCKED_BY_PENDING_CHOICES),
        )
        updated = self.copy_state(state)
        updated.transactions[transaction.transaction_id] = updated_transaction
        return updated, updated_transaction, (
            AdvancementChoiceResolvedEvent(transaction_id=transaction.transaction_id, actor_id=actor_id, choice=resolved_choice),
            AdvancementValidatedEvent(transaction_id=transaction.transaction_id, actor_id=actor_id, status=updated_transaction.validation_status, generated_feature_names=updated_transaction.generated_feature_names),
        )
    def commit_transaction(
        self,
        state: AdvancementRuntimeState,
        *,
        actor_id: str,
        record: CharacterRecord,
        species_hit_point_bonus_per_level: int,
        catalog: ContentCatalog,
        random_counter: int,
        seed: str,
    ) -> tuple[AdvancementRuntimeState, CharacterRecord, AdvancementTransaction, tuple[object, ...], int]:
        transaction = self._require_actor_transaction(state, actor_id)
        if transaction.chosen_class_id is None or transaction.chosen_class_level is None:
            raise EncounterValidationError('Choose a class to advance before applying the level-up.')
        unresolved = [choice for choice in transaction.pending_choices if choice.blocks_finalization and choice.resolution_status != ChoiceResolutionStatus.RESOLVED]
        if unresolved:
            raise EncounterValidationError('Resolve all mandatory advancement choices before applying the level-up.')
        class_record = catalog.classes[transaction.chosen_class_id]
        current_class_level = class_level_for(record, class_record.record_id)
        hp_gain, next_random_counter = self._build_hit_point_gain(
            constitution_modifier=record.ability_modifiers.get(Ability.CON, 0),
            class_record=class_record,
            target_total_level=transaction.target_total_level,
            species_hit_point_bonus_per_level=species_hit_point_bonus_per_level,
            random_counter=random_counter,
            seed=seed,
            rolled=(state.policy.hit_point_mode.value == 'rolled'),
        )
        committed_record = self._build_committed_record(
            record=record,
            class_record=class_record,
            target_class_level=transaction.chosen_class_level,
            target_total_level=transaction.target_total_level,
            hp_gain=hp_gain,
            transaction=transaction,
            catalog=catalog,
        )
        committed_transaction = replace(transaction, hp_gain=hp_gain, commit_status=AdvancementCommitStatus.COMMITTED, validation_status=AdvancementValidationStatus.READY_TO_COMMIT)
        updated = self.copy_state(state)
        updated.transactions.pop(transaction.transaction_id, None)
        updated.actor_transaction_ids.pop(actor_id, None)
        events: list[object] = [
            AdvancementCommitSucceededEvent(transaction=committed_transaction),
            CharacterLevelIncreasedEvent(actor_id=actor_id, previous_level=record.level, new_level=committed_record.level),
            ClassLevelIncreasedEvent(actor_id=actor_id, class_id=class_record.record_id, previous_class_level=current_class_level, new_class_level=transaction.chosen_class_level),
            HitPointsIncreasedEvent(actor_id=actor_id, previous_max_hit_points=record.max_hit_points, new_max_hit_points=committed_record.max_hit_points, gained_hit_points=hp_gain.total_gained),
            ProficiencyBonusUpdatedEvent(actor_id=actor_id, previous_proficiency_bonus=record.proficiency_bonus, new_proficiency_bonus=committed_record.proficiency_bonus),
        ]
        for feature_name in committed_transaction.generated_feature_names:
            events.append(FeatureUnlockedEvent(actor_id=actor_id, feature_name=feature_name))
        return updated, committed_record, committed_transaction, tuple(events), next_random_counter

    def actor_summary_lines(self, state: AdvancementRuntimeState, *, actor_id: str) -> tuple[str, ...]:
        transaction_id = state.actor_transaction_ids.get(actor_id)
        if transaction_id is None:
            return ()
        transaction = state.transactions.get(transaction_id)
        if transaction is None:
            return ()
        lines = [f'Pending advancement transaction to level {transaction.target_total_level} from {transaction.source_mode.value}.']
        if transaction.chosen_class_id is None:
            lines.append('Choose a class with /levelup class <actor-id> <class-id>.')
            return tuple(lines)
        lines.append(f'Chosen class: {transaction.chosen_class_id} -> class level {transaction.chosen_class_level}.')
        if transaction.generated_feature_names:
            lines.append('Feature unlocks: ' + '; '.join(transaction.generated_feature_names))
        unresolved = [choice for choice in transaction.pending_choices if choice.resolution_status != ChoiceResolutionStatus.RESOLVED]
        if unresolved:
            lines.append('Pending advancement choices:')
            for choice in unresolved:
                lines.append(f'  - {choice.group.choice_id}: {choice.group.prompt}')
        else:
            lines.append('Advancement is ready to commit with /levelup apply <actor-id>.')
        return tuple(lines)

    def available_choice_views(self, state: AdvancementRuntimeState, *, actor_id: str) -> dict[str, tuple[ChoiceOption, ...]]:
        transaction_id = state.actor_transaction_ids.get(actor_id)
        if transaction_id is None:
            return {}
        transaction = state.transactions.get(transaction_id)
        if transaction is None:
            return {}
        return {choice.group.choice_id: choice.group.options for choice in transaction.pending_choices if choice.resolution_status != ChoiceResolutionStatus.RESOLVED}

    def _build_committed_record(
        self,
        *,
        record: CharacterRecord,
        class_record: ClassRecord,
        target_class_level: int,
        target_total_level: int,
        hp_gain: HitPointGainRecord,
        transaction: AdvancementTransaction,
        catalog: ContentCatalog,
    ) -> CharacterRecord:
        updated_class_levels = []
        replaced_existing = False
        for allocation in normalized_class_levels(record):
            if allocation.class_id == class_record.record_id:
                updated_class_levels.append(CharacterClassLevel(class_id=allocation.class_id, level=target_class_level))
                replaced_existing = True
            else:
                updated_class_levels.append(allocation)
        if not replaced_existing:
            updated_class_levels.append(CharacterClassLevel(class_id=class_record.record_id, level=target_class_level))
        updated_class_levels.sort(key=lambda item: item.class_id)

        subclass_selections = list(record.subclass_selections)
        subclass_choice = next((choice for choice in transaction.resolved_choices if choice.category == AdvancementChoiceCategory.SUBCLASS), None)
        if subclass_choice is not None:
            subclass_record = next((subclass for subclass in class_record.subclasses if subclass.record_id == subclass_choice.selected_option_ids[0]), None)
            if subclass_record is None:
                raise EncounterValidationError('Resolved subclass selection is not legal for the chosen class.')
            subclass_selections = [selection for selection in subclass_selections if selection.class_id != class_record.record_id]
            subclass_selections.append(CharacterSubclassSelection(class_id=class_record.record_id, subclass_id=subclass_record.record_id, subclass_name=subclass_record.name))
        subclass_selection = next((selection for selection in subclass_selections if selection.class_id == class_record.record_id), None)

        class_feature_names = list(record.class_feature_names)
        for feature_name in transaction.generated_feature_names:
            if feature_name not in class_feature_names:
                class_feature_names.append(feature_name)
        if subclass_selection is not None and subclass_selection.subclass_name not in class_feature_names:
            class_feature_names.append(subclass_selection.subclass_name)
        for resolved_choice in transaction.resolved_choices:
            if resolved_choice.category == AdvancementChoiceCategory.SUBCLASS:
                continue
            for label in resolved_choice.selected_option_labels:
                if label not in class_feature_names:
                    class_feature_names.append(label)

        traits = list(record.traits)
        for feature_name in transaction.generated_feature_names:
            if feature_name not in traits:
                traits.append(feature_name)
        if subclass_selection is not None:
            subclass_trait = f'Subclass: {subclass_selection.subclass_name}'
            if subclass_trait not in traits:
                traits.append(subclass_trait)
        spell_selections = list(record.spell_selections)
        class_source = ChoiceSource(ChoiceSourceKind.CLASS, class_record.record_id, class_record.name)
        for resolved_choice in transaction.resolved_choices:
            if resolved_choice.category not in {AdvancementChoiceCategory.CANTRIP, AdvancementChoiceCategory.SPELL}:
                continue
            selection_kind = SpellSelectionKind.CANTRIP if resolved_choice.category == AdvancementChoiceCategory.CANTRIP else class_record.spellcasting.spell_selection_kind
            for spell_id in resolved_choice.selected_option_ids:
                spell = catalog.spells[spell_id]
                spell_selections.append(CharacterSpellSelection(spell_id=spell.record_id, spell_name=spell.name, spell_level=spell.level, selection_kind=selection_kind, source=class_source, spellcasting_ability=(class_record.spellcasting.spellcasting_ability if class_record.spellcasting is not None else None), spell_list_class_id=class_record.record_id))

        expertise_skill_ids = list(record.expertise_skill_ids)
        expertise_tool_ids = list(record.expertise_tool_ids)
        fighting_style_names = list(record.fighting_style_names)
        weapon_mastery_item_ids = list(record.weapon_mastery_item_ids)
        for resolved_choice in transaction.resolved_choices:
            if resolved_choice.category == AdvancementChoiceCategory.EXPERTISE:
                for option_id in resolved_choice.selected_option_ids:
                    if option_id in catalog.skills and option_id not in expertise_skill_ids:
                        expertise_skill_ids.append(option_id)
                    elif option_id in catalog.tools and option_id not in expertise_tool_ids:
                        expertise_tool_ids.append(option_id)
            elif resolved_choice.category == AdvancementChoiceCategory.FIGHTING_STYLE:
                for label in resolved_choice.selected_option_labels:
                    if label not in fighting_style_names:
                        fighting_style_names.append(label)
            elif resolved_choice.category == AdvancementChoiceCategory.WEAPON_MASTERY:
                for option_id in resolved_choice.selected_option_ids:
                    if option_id not in weapon_mastery_item_ids:
                        weapon_mastery_item_ids.append(option_id)

        resolved_advancement_choices = list(record.resolved_advancement_choices)
        for resolved_choice in transaction.resolved_choices:
            resolved_advancement_choices.append(ResolvedAdvancementChoiceRecord(choice_id=resolved_choice.choice_id, category=resolved_choice.category.value, selected_option_ids=resolved_choice.selected_option_ids, selected_option_labels=resolved_choice.selected_option_labels))

        return replace(
            record,
            level=target_total_level,
            class_levels=tuple(updated_class_levels),
            subclass_selections=tuple(sorted(subclass_selections, key=lambda item: item.class_id)),
            resolved_advancement_choices=tuple(resolved_advancement_choices),
            max_hit_points=record.max_hit_points + hp_gain.total_gained,
            proficiency_bonus=self._proficiency_bonus_for_level(target_total_level),
            spell_selections=tuple(spell_selections),
            traits=tuple(traits),
            expertise_skill_ids=tuple(expertise_skill_ids),
            expertise_tool_ids=tuple(expertise_tool_ids),
            fighting_style_names=tuple(fighting_style_names),
            weapon_mastery_item_ids=tuple(weapon_mastery_item_ids),
            class_feature_names=tuple(class_feature_names),
        )

    def _generate_pending_choices(
        self,
        *,
        transaction_id: str,
        record: CharacterRecord,
        class_record: ClassRecord,
        target_class_level: int,
        catalog: ContentCatalog,
        source: AdvancementChoiceSource,
    ) -> tuple[tuple[PendingAdvancementChoice, ...], tuple[str, ...]]:
        generated_feature_names: list[str] = []
        pending_choices: list[PendingAdvancementChoice] = []
        for grant in class_record.class_feature_grants:
            if grant.level != target_class_level:
                continue
            if grant.feature_name not in generated_feature_names:
                generated_feature_names.append(grant.feature_name)
            if grant.grants_subclass_choice and not has_subclass_selection(record, class_record.record_id):
                options = tuple(ChoiceOption(option_id=subclass.record_id, label=subclass.name, detail=f'{class_record.name} subclass') for subclass in class_record.subclasses)
                if options:
                    pending_choices.append(PendingAdvancementChoice(group=ChoiceGroup(choice_id=f'{transaction_id}:subclass:{class_record.record_id}:{target_class_level}', label=f'{class_record.name} subclass', prompt=f'Choose a subclass for {class_record.name}.', options=options, constraint=SelectionConstraint(required_count=1)), source=source, category=AdvancementChoiceCategory.SUBCLASS, resolution_status=ChoiceResolutionStatus.PENDING))
        pending_choices.extend(self._pending_class_feature_choices(transaction_id=transaction_id, class_record=class_record, target_class_level=target_class_level, source=source))
        pending_choices.extend(self._pending_spell_choices(transaction_id=transaction_id, record=record, class_record=class_record, target_class_level=target_class_level, catalog=catalog, source=source))
        pending_choices.extend(self._manual_level_choices(transaction_id=transaction_id, record=record, class_record=class_record, target_class_level=target_class_level, catalog=catalog, source=source))
        return tuple(pending_choices), tuple(generated_feature_names)

    def _pending_class_feature_choices(self, *, transaction_id: str, class_record: ClassRecord, target_class_level: int, source: AdvancementChoiceSource) -> list[PendingAdvancementChoice]:
        choices: list[PendingAdvancementChoice] = []
        for group in class_record.class_feature_choice_groups:
            if group.level != target_class_level:
                continue
            choices.append(PendingAdvancementChoice(group=ChoiceGroup(choice_id=f'{transaction_id}:{group.choice_id}', label=group.label, prompt=group.prompt, options=tuple(ChoiceOption(option_id=option.option_id, label=option.label, detail=option.detail) for option in group.options), constraint=group.constraint), source=source, category=self._choice_category_for_group(group), resolution_status=ChoiceResolutionStatus.PENDING))
        return choices

    def _pending_spell_choices(self, *, transaction_id: str, record: CharacterRecord, class_record: ClassRecord, target_class_level: int, catalog: ContentCatalog, source: AdvancementChoiceSource) -> list[PendingAdvancementChoice]:
        if class_record.spellcasting is None:
            return []
        spellcasting = class_record.spellcasting
        current_class_level = class_level_for(record, class_record.record_id)
        choices: list[PendingAdvancementChoice] = []
        current_cantrip_total = self._progression_value(spellcasting.cantrip_choice_progression, current_class_level, default=spellcasting.cantrip_choice_count)
        target_cantrip_total = self._progression_value(spellcasting.cantrip_choice_progression, target_class_level, default=spellcasting.cantrip_choice_count)
        cantrip_delta = max(0, target_cantrip_total - current_cantrip_total)
        if cantrip_delta > 0:
            existing_spell_ids = {selection.spell_id for selection in record.spell_selections}
            cantrip_options = tuple(ChoiceOption(option_id=spell.record_id, label=spell.name, detail='cantrip') for spell in sorted(catalog.spells.values(), key=lambda item: item.name) if spell.level == 0 and spell.record_id not in existing_spell_ids and class_record.record_id in spell.class_ids)
            choices.append(PendingAdvancementChoice(group=ChoiceGroup(choice_id=f'{transaction_id}:class:{class_record.record_id}:cantrips:{target_class_level}', label=f'{class_record.name} cantrips', prompt=f'Choose {cantrip_delta} cantrip(s) for {class_record.name}.', options=cantrip_options, constraint=SelectionConstraint(required_count=cantrip_delta)), source=source, category=AdvancementChoiceCategory.CANTRIP, resolution_status=ChoiceResolutionStatus.PENDING))
        if spellcasting.spell_selection_kind == SpellSelectionKind.KNOWN:
            current_spell_total = self._progression_value(spellcasting.spell_choice_progression, current_class_level, default=spellcasting.spell_choice_count)
            target_spell_total = self._progression_value(spellcasting.spell_choice_progression, target_class_level, default=spellcasting.spell_choice_count)
            spell_delta = max(0, target_spell_total - current_spell_total)
            if spell_delta > 0:
                max_spell_level = self._highest_spell_level_available(class_record=class_record, class_level=target_class_level)
                existing_spell_ids = {selection.spell_id for selection in record.spell_selections if selection.source.source_kind == ChoiceSourceKind.CLASS and selection.source.source_id == class_record.record_id}
                spell_options = tuple(ChoiceOption(option_id=spell.record_id, label=spell.name, detail=f'level {spell.level} spell') for spell in sorted(catalog.spells.values(), key=lambda item: (item.level, item.name)) if 0 < spell.level <= max_spell_level and spell.record_id not in existing_spell_ids and class_record.record_id in spell.class_ids)
                choices.append(PendingAdvancementChoice(group=ChoiceGroup(choice_id=f'{transaction_id}:class:{class_record.record_id}:spells:{target_class_level}', label=f'{class_record.name} spells', prompt=f'Choose {spell_delta} spell(s) for {class_record.name}.', options=spell_options, constraint=SelectionConstraint(required_count=spell_delta)), source=source, category=AdvancementChoiceCategory.SPELL, resolution_status=ChoiceResolutionStatus.PENDING))
        return choices
    def _manual_level_choices(self, *, transaction_id: str, record: CharacterRecord, class_record: ClassRecord, target_class_level: int, catalog: ContentCatalog, source: AdvancementChoiceSource) -> list[PendingAdvancementChoice]:
        choices: list[PendingAdvancementChoice] = []
        if class_record.record_id == 'rogue' and target_class_level in {1, 6}:
            options: list[ChoiceOption] = []
            seen: set[str] = set()
            for selection in record.proficiency_selections:
                if selection.record_id in catalog.skills and selection.record_id not in record.expertise_skill_ids and selection.record_id not in seen:
                    options.append(ChoiceOption(option_id=selection.record_id, label=selection.name, detail='skill expertise'))
                    seen.add(selection.record_id)
                elif selection.record_id in catalog.tools and selection.record_id not in record.expertise_tool_ids and selection.record_id not in seen:
                    options.append(ChoiceOption(option_id=selection.record_id, label=selection.name, detail='tool expertise'))
                    seen.add(selection.record_id)
            if options:
                choices.append(PendingAdvancementChoice(group=ChoiceGroup(choice_id=f'{transaction_id}:rogue:expertise:{target_class_level}', label='Expertise', prompt='Choose 2 expertise options from your proficient skills or tools.', options=tuple(options), constraint=SelectionConstraint(required_count=min(2, len(options)))), source=source, category=AdvancementChoiceCategory.EXPERTISE, resolution_status=ChoiceResolutionStatus.PENDING))
        return choices

    def _choice_category_for_group(self, group: ClassFeatureChoiceGroup) -> AdvancementChoiceCategory:
        label = group.label.lower()
        if 'fighting style' in label:
            return AdvancementChoiceCategory.FIGHTING_STYLE
        if 'expertise' in label:
            return AdvancementChoiceCategory.EXPERTISE
        if 'weapon mastery' in label:
            return AdvancementChoiceCategory.WEAPON_MASTERY
        return AdvancementChoiceCategory.CLASS_FEATURE

    def _legal_class_allocations(self, *, record: CharacterRecord, catalog: ContentCatalog, state: AdvancementRuntimeState) -> tuple[ClassLevelAllocation, ...]:
        current_class = catalog.classes[record.class_id]
        allocations = [ClassLevelAllocation(class_id=current_class.record_id, class_name=current_class.name, new_class_level=class_level_for(record, current_class.record_id) + 1, is_multiclass=False)]
        if not state.policy.allow_multiclass:
            return tuple(allocations)
        for class_id, class_record in sorted(catalog.classes.items()):
            if class_id == record.class_id:
                continue
            if not class_record.multiclass_requirement_sets:
                continue
            if not self._meets_requirement_set(record=record, requirement_sets=class_record.multiclass_requirement_sets):
                continue
            allocations.append(ClassLevelAllocation(class_id=class_id, class_name=class_record.name, new_class_level=class_level_for(record, class_id) + 1, is_multiclass=True))
        return tuple(allocations)

    def _validate_multiclass_prerequisites(self, *, record: CharacterRecord, class_record: ClassRecord) -> None:
        if not class_record.multiclass_requirement_sets:
            raise EncounterValidationError(f'{class_record.name} does not expose normalized multiclass prerequisites in the current catalog.')
        if not self._meets_requirement_set(record=record, requirement_sets=class_record.multiclass_requirement_sets):
            raise EncounterValidationError(f'{record.record_id} does not meet the multiclass prerequisites for {class_record.name}.')

    def _meets_requirement_set(self, *, record: CharacterRecord, requirement_sets) -> bool:
        return any(all(record.ability_scores.get(ability, 0) >= minimum for ability, minimum in requirement.minimum_scores.items()) for requirement in requirement_sets)

    def _progression_value(self, progression: tuple[int, ...], class_level: int, *, default: int) -> int:
        if class_level <= 0:
            return 0
        if progression and len(progression) >= class_level:
            return progression[class_level - 1]
        return default if class_level == 1 else 0

    def _highest_spell_level_available(self, *, class_record: ClassRecord, class_level: int) -> int:
        spellcasting = class_record.spellcasting
        if spellcasting is None or class_level <= 0 or len(spellcasting.spell_slot_progression) < class_level:
            return 1
        highest = 1
        for index, slot_count in enumerate(spellcasting.spell_slot_progression[class_level - 1], start=1):
            if slot_count > 0:
                highest = index
        return highest

    def _build_hit_point_gain(self, *, constitution_modifier: int, class_record: ClassRecord, target_total_level: int, species_hit_point_bonus_per_level: int, random_counter: int, seed: str, rolled: bool) -> tuple[HitPointGainRecord, int]:
        rolled_value = None
        if rolled:
            rolled_value = seeded_random(seed, random_counter).randint(1, class_record.hit_die)
            base_gain = rolled_value
            next_random_counter = random_counter + 1
        else:
            base_gain = (class_record.hit_die // 2) + 1
            next_random_counter = random_counter
        total_gained = max(1, base_gain + constitution_modifier + species_hit_point_bonus_per_level)
        return HitPointGainRecord(target_total_level=target_total_level, class_id=class_record.record_id, die_faces=class_record.hit_die, rolled_value=rolled_value, constitution_modifier=constitution_modifier, species_bonus=species_hit_point_bonus_per_level, total_gained=total_gained), next_random_counter

    def _require_actor_transaction(self, state: AdvancementRuntimeState, actor_id: str) -> AdvancementTransaction:
        transaction_id = state.actor_transaction_ids.get(actor_id)
        if transaction_id is None:
            raise EncounterValidationError('This actor does not have an open advancement transaction.')
        return self._require_transaction(state, transaction_id)

    def _require_transaction(self, state: AdvancementRuntimeState, transaction_id: str) -> AdvancementTransaction:
        transaction = state.transactions.get(transaction_id)
        if transaction is None:
            raise EncounterValidationError('Unknown advancement transaction.')
        return transaction

    def _proficiency_bonus_for_level(self, level: int) -> int:
        return 2 + max(0, (level - 1) // 4)
