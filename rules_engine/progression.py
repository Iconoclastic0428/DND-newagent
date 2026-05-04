from __future__ import annotations

from dataclasses import replace

from shared_types.encounter_events import (
    LevelUpQueuedEvent,
    MilestoneAdvancementGrantedEvent,
    MilestoneCompletedEvent,
    ProgressionEligibilityUpdatedEvent,
    ProgressionProjectionUpdatedEvent,
    XPRewardAppliedEvent,
    XPRewardLoggedEvent,
)
from shared_types.errors import EncounterValidationError
from shared_types.progression import (
    ActorProgressState,
    CampaignProgressionState,
    MAX_CHARACTER_LEVEL,
    MilestoneCompletionState,
    MilestoneDistributionPolicy,
    MilestoneRecord,
    MilestoneRecipientAward,
    MilestoneSourceType,
    PendingLevelUpRecord,
    ProgressionMode,
    ProgressionPolicy,
    ProgressionRecipientScope,
    XPDistributionPolicy,
    XP_LEVEL_THRESHOLDS,
    XPRecipientAward,
    XPRewardRecord,
    XPRewardSourceType,
)
from shared_types.travel import unique_strings


class CampaignProgressionEngine:
    def initial_state(
        self,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        mode: ProgressionMode = ProgressionMode.XP,
        policy: ProgressionPolicy | None = None,
    ) -> CampaignProgressionState:
        state = CampaignProgressionState(mode=mode, policy=(policy or ProgressionPolicy()))
        return self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)

    def copy_state(self, state: CampaignProgressionState) -> CampaignProgressionState:
        return CampaignProgressionState(
            mode=state.mode,
            policy=state.policy,
            actor_progress=dict(state.actor_progress),
            xp_rewards=dict(state.xp_rewards),
            milestone_records=dict(state.milestone_records),
            pending_level_ups=dict(state.pending_level_ups),
            xp_dedupe=dict(state.xp_dedupe),
            milestone_dedupe=dict(state.milestone_dedupe),
        )

    def sync_actor_snapshots(self, state: CampaignProgressionState, *, actor_snapshots: tuple[tuple[str, str, int], ...]) -> CampaignProgressionState:
        updated = self.copy_state(state)
        snapshot_map = {actor_id: (label, level) for actor_id, label, level in actor_snapshots}
        for actor_id, actor_label, current_level in actor_snapshots:
            prior = updated.actor_progress.get(actor_id)
            xp_total = 0
            completed_milestone_ids: list[str] = []
            granted_milestone_advancements = 0
            last_reward_id = None
            last_milestone_id = None
            for reward, amount in self._xp_rewards_for_actor(updated, actor_id):
                xp_total += amount
                last_reward_id = reward.reward_id
            for record, steps in self._milestone_awards_for_actor(updated, actor_id):
                completed_milestone_ids.append(record.milestone_id)
                granted_milestone_advancements += steps
                last_milestone_id = record.milestone_id
            eligible_level = self._eligible_level_for_actor(updated, actor_id=actor_id, current_level=current_level, xp_total=xp_total, granted_milestone_advancements=granted_milestone_advancements)
            pending_ids = tuple(
                pending.pending_id
                for pending in sorted(updated.pending_level_ups.values(), key=lambda item: (item.actor_id, item.target_new_total_level, item.pending_id))
                if pending.actor_id == actor_id and not pending.applied and pending.source_mode == updated.mode
            )
            updated.actor_progress[actor_id] = ActorProgressState(
                actor_id=actor_id,
                actor_label=actor_label,
                current_level=current_level,
                xp_total=xp_total,
                completed_milestone_ids=tuple(completed_milestone_ids),
                granted_milestone_advancements=granted_milestone_advancements,
                eligible_level=eligible_level,
                next_level_xp_threshold=self._next_level_threshold(eligible_level if updated.mode == ProgressionMode.XP else current_level),
                pending_level_up_ids=pending_ids,
                last_reward_id=last_reward_id,
                last_milestone_id=last_milestone_id,
            )
        for actor_id, progress in list(updated.actor_progress.items()):
            if actor_id in snapshot_map:
                continue
            updated.actor_progress[actor_id] = replace(progress, pending_level_up_ids=tuple(
                pending.pending_id
                for pending in sorted(updated.pending_level_ups.values(), key=lambda item: (item.target_new_total_level, item.pending_id))
                if pending.actor_id == actor_id and not pending.applied and pending.source_mode == updated.mode
            ))
        return updated

    def set_mode(
        self,
        state: CampaignProgressionState,
        *,
        mode: ProgressionMode,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        timestamp_seconds: int,
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        updated = self.copy_state(state)
        updated.mode = mode
        updated = self.sync_actor_snapshots(updated, actor_snapshots=actor_snapshots)
        events = list(self._eligibility_events(updated))
        events.append(ProgressionProjectionUpdatedEvent(mode=updated.mode, pending_level_up_ids=tuple(sorted(updated.pending_level_ups))))
        return updated, tuple(events)

    def set_policy(
        self,
        state: CampaignProgressionState,
        *,
        policy: ProgressionPolicy,
        actor_snapshots: tuple[tuple[str, str, int], ...],
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        updated = self.copy_state(state)
        updated.policy = policy
        updated = self.sync_actor_snapshots(updated, actor_snapshots=actor_snapshots)
        events = list(self._eligibility_events(updated))
        events.append(ProgressionProjectionUpdatedEvent(mode=updated.mode, pending_level_up_ids=tuple(sorted(updated.pending_level_ups))))
        return updated, tuple(events)

    def log_xp_reward(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        campaign_id: str,
        session_id: str,
        scene_id: str | None,
        location_id: str | None,
        source_type: XPRewardSourceType,
        source_id: str,
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        amount: int,
        reason: str,
        timestamp_seconds: int,
        dedupe_key: str | None = None,
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        if amount <= 0:
            raise EncounterValidationError('XP award amount must be a positive integer.')
        if not recipient_actor_ids:
            raise EncounterValidationError('XP awards require at least one recipient actor.')
        updated = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        actor_map = {actor_id: actor_label for actor_id, actor_label, _level in actor_snapshots}
        self._validate_recipient_actor_ids(actor_map, recipient_actor_ids)
        resolved_dedupe = dedupe_key or self._default_xp_dedupe_key(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)
        existing_reward_id = updated.xp_dedupe.get(resolved_dedupe)
        if existing_reward_id is not None:
            return updated, ()
        awards = self._resolve_xp_awards(
            updated,
            actor_map=actor_map,
            recipient_scope=recipient_scope,
            recipient_actor_ids=recipient_actor_ids,
            amount=amount,
        )
        reward_id = self._xp_reward_id(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)
        record = XPRewardRecord(
            reward_id=reward_id,
            source_type=source_type,
            source_id=source_id,
            campaign_id=campaign_id,
            session_id=session_id,
            scene_id=scene_id,
            location_id=location_id,
            recipients=awards,
            recipient_scope=recipient_scope,
            configured_xp_amount=amount,
            award_reason=reason.strip() or source_id,
            timestamp_seconds=timestamp_seconds,
            dedupe_key=resolved_dedupe,
            applied=True,
        )
        updated = self.copy_state(updated)
        updated.xp_rewards[record.reward_id] = record
        updated.xp_dedupe[resolved_dedupe] = record.reward_id
        refreshed, follow_up_events = self._refresh_eligibility(updated, actor_snapshots=actor_snapshots, timestamp_seconds=timestamp_seconds)
        events: list[object] = [XPRewardLoggedEvent(record=record), XPRewardAppliedEvent(record=record), *follow_up_events]
        return refreshed, tuple(events)

    def complete_milestone(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        campaign_id: str,
        session_id: str,
        scene_id: str | None,
        location_id: str | None,
        source_type: MilestoneSourceType,
        source_id: str,
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        reason: str,
        timestamp_seconds: int,
        advancement_steps: int = 1,
        dedupe_key: str | None = None,
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        if advancement_steps <= 0:
            raise EncounterValidationError('Milestone advancement steps must be positive.')
        if not recipient_actor_ids:
            raise EncounterValidationError('Milestones require at least one recipient actor.')
        updated = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        actor_map = {actor_id: actor_label for actor_id, actor_label, _level in actor_snapshots}
        self._validate_recipient_actor_ids(actor_map, recipient_actor_ids)
        resolved_dedupe = dedupe_key or self._default_milestone_dedupe_key(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)
        existing_milestone_id = updated.milestone_dedupe.get(resolved_dedupe)
        if existing_milestone_id is not None:
            return updated, ()
        awards = self._resolve_milestone_awards(
            updated,
            actor_map=actor_map,
            recipient_scope=recipient_scope,
            recipient_actor_ids=recipient_actor_ids,
            advancement_steps=advancement_steps,
        )
        milestone_id = self._milestone_id(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)
        record = MilestoneRecord(
            milestone_id=milestone_id,
            source_type=source_type,
            source_id=source_id,
            campaign_id=campaign_id,
            session_id=session_id,
            scene_id=scene_id,
            location_id=location_id,
            recipients=awards,
            recipient_scope=recipient_scope,
            completion_state=MilestoneCompletionState.COMPLETED,
            advancement_granted=True,
            award_reason=reason.strip() or source_id,
            timestamp_seconds=timestamp_seconds,
            dedupe_key=resolved_dedupe,
        )
        updated = self.copy_state(updated)
        updated.milestone_records[record.milestone_id] = record
        updated.milestone_dedupe[resolved_dedupe] = record.milestone_id
        refreshed, follow_up_events = self._refresh_eligibility(updated, actor_snapshots=actor_snapshots, timestamp_seconds=timestamp_seconds)
        events: list[object] = [MilestoneCompletedEvent(record=record), MilestoneAdvancementGrantedEvent(record=record), *follow_up_events]
        return refreshed, tuple(events)

    def visible_projection_lines(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        dm_view: bool,
    ) -> tuple[str, ...]:
        synced = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        lines = [
            f'Mode {synced.mode.value}; XP policy {synced.policy.xp_distribution.value}; milestone policy {synced.policy.milestone_distribution.value}.',
        ]
        for actor_id, actor_label, current_level in actor_snapshots:
            progress = synced.actor_progress.get(actor_id)
            if progress is None:
                continue
            pending = [synced.pending_level_ups[pending_id].target_new_total_level for pending_id in progress.pending_level_up_ids if pending_id in synced.pending_level_ups]
            if synced.mode == ProgressionMode.XP:
                if not dm_view and not synced.policy.show_xp_to_players:
                    if pending:
                        lines.append(f'{actor_label}: pending level-up to {max(pending)}.')
                    continue
                next_threshold = progress.next_level_xp_threshold
                next_text = 'max level' if next_threshold is None else f'next at {next_threshold}'
                pending_text = f'; pending {", ".join(str(value) for value in pending)}' if pending else ''
                lines.append(f'{actor_label}: level {current_level}; XP {progress.xp_total}; {next_text}{pending_text}.')
                continue
            if not dm_view and not synced.policy.reveal_milestone_progress_to_players:
                if pending:
                    lines.append(f'{actor_label}: pending level-up to {max(pending)}.')
                continue
            pending_text = f'; pending {", ".join(str(value) for value in pending)}' if pending else ''
            lines.append(f'{actor_label}: level {current_level}; milestones granted {progress.granted_milestone_advancements}{pending_text}.')
        return tuple(lines)

    def dm_status_lines(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
    ) -> tuple[str, ...]:
        synced = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        lines: list[str] = [
            f'XP rewards logged: {len(synced.xp_rewards)}.',
            f'Milestones completed: {len(synced.milestone_records)}.',
        ]
        pending = sorted(
            (record for record in synced.pending_level_ups.values() if not record.applied and record.source_mode == synced.mode),
            key=lambda item: (item.actor_label, item.target_new_total_level, item.pending_id),
        )
        if pending:
            lines.append('Pending level-ups: ' + '; '.join(f'{record.actor_label} -> {record.target_new_total_level} ({record.source_mode.value})' for record in pending))
        recent_rewards = sorted(synced.xp_rewards.values(), key=lambda item: (item.timestamp_seconds, item.reward_id))[-3:]
        for reward in recent_rewards:
            recipient_summary = ', '.join(f'{award.actor_label}+{award.xp_amount}' for award in reward.recipients)
            lines.append(f'XP reward {reward.source_type.value}:{reward.source_id} -> {recipient_summary}.')
        recent_milestones = sorted(synced.milestone_records.values(), key=lambda item: (item.timestamp_seconds, item.milestone_id))[-3:]
        for record in recent_milestones:
            recipient_summary = ', '.join(f'{award.actor_label}+{award.advancement_steps}' for award in record.recipients)
            lines.append(f'Milestone {record.source_type.value}:{record.source_id} -> {recipient_summary}.')
        return tuple(lines)

    def writeback_lines(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
    ) -> tuple[str, ...]:
        synced = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        lines = list(self.visible_projection_lines(synced, actor_snapshots=actor_snapshots, dm_view=True))
        dm_lines = self.dm_status_lines(synced, actor_snapshots=actor_snapshots)
        return tuple(unique_strings(lines + list(dm_lines))[-10:])

    def _refresh_eligibility(
        self,
        state: CampaignProgressionState,
        *,
        actor_snapshots: tuple[tuple[str, str, int], ...],
        timestamp_seconds: int,
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        updated = self.sync_actor_snapshots(state, actor_snapshots=actor_snapshots)
        events: list[object] = []
        for actor_id, actor_label, current_level in actor_snapshots:
            progress = updated.actor_progress[actor_id]
            unapplied_pending_levels = sorted(
                record.target_new_total_level
                for record in updated.pending_level_ups.values()
                if record.actor_id == actor_id and not record.applied and record.source_mode == updated.mode
            )
            if unapplied_pending_levels and not updated.policy.allow_multiple_pending_level_ups:
                continue
            highest_accounted_level = max([current_level] + unapplied_pending_levels)
            eligible_level = progress.eligible_level
            if eligible_level <= highest_accounted_level:
                continue
            if updated.policy.allow_multiple_pending_level_ups:
                target_levels = range(highest_accounted_level + 1, eligible_level + 1)
            else:
                target_levels = (highest_accounted_level + 1,)
            if updated.mode == ProgressionMode.XP:
                threshold_refs = self._xp_threshold_reward_refs(updated, actor_id=actor_id)
                for target_level in target_levels:
                    pending = PendingLevelUpRecord(
                        pending_id=self._pending_id(updated.mode, actor_id=actor_id, target_level=target_level),
                        actor_id=actor_id,
                        actor_label=actor_label,
                        target_new_total_level=target_level,
                        source_mode=updated.mode,
                        source_reward_ids=threshold_refs.get(target_level, ()),
                        created_timestamp_seconds=timestamp_seconds,
                        blocked_by_unresolved_upgrade_choices=True,
                    )
                    updated.pending_level_ups[pending.pending_id] = pending
                    events.append(LevelUpQueuedEvent(record=pending))
            else:
                threshold_refs = self._milestone_threshold_refs(updated, actor_id=actor_id, current_level=current_level)
                for target_level in target_levels:
                    pending = PendingLevelUpRecord(
                        pending_id=self._pending_id(updated.mode, actor_id=actor_id, target_level=target_level),
                        actor_id=actor_id,
                        actor_label=actor_label,
                        target_new_total_level=target_level,
                        source_mode=updated.mode,
                        source_milestone_ids=threshold_refs.get(target_level, ()),
                        created_timestamp_seconds=timestamp_seconds,
                        blocked_by_unresolved_upgrade_choices=True,
                    )
                    updated.pending_level_ups[pending.pending_id] = pending
                    events.append(LevelUpQueuedEvent(record=pending))
        updated = self.sync_actor_snapshots(updated, actor_snapshots=actor_snapshots)
        events.extend(self._eligibility_events(updated))
        events.append(ProgressionProjectionUpdatedEvent(mode=updated.mode, pending_level_up_ids=tuple(sorted(updated.pending_level_ups))))
        return updated, tuple(events)

    def set_pending_level_up_blocked_state(
        self,
        state: CampaignProgressionState,
        *,
        pending_id: str,
        blocked: bool,
        actor_snapshots: tuple[tuple[str, str, int], ...],
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        if pending_id not in state.pending_level_ups:
            raise EncounterValidationError('Unknown pending level-up id.')
        updated = self.copy_state(state)
        updated.pending_level_ups[pending_id] = replace(updated.pending_level_ups[pending_id], blocked_by_unresolved_upgrade_choices=blocked)
        updated = self.sync_actor_snapshots(updated, actor_snapshots=actor_snapshots)
        events = list(self._eligibility_events(updated))
        events.append(ProgressionProjectionUpdatedEvent(mode=updated.mode, pending_level_up_ids=tuple(sorted(updated.pending_level_ups))))
        return updated, tuple(events)

    def mark_pending_level_up_applied(
        self,
        state: CampaignProgressionState,
        *,
        pending_id: str,
        actor_snapshots: tuple[tuple[str, str, int], ...],
    ) -> tuple[CampaignProgressionState, tuple[object, ...]]:
        if pending_id not in state.pending_level_ups:
            raise EncounterValidationError('Unknown pending level-up id.')
        pending = state.pending_level_ups[pending_id]
        if pending.applied:
            raise EncounterValidationError('Pending level-up already applied.')
        updated = self.copy_state(state)
        updated.pending_level_ups[pending_id] = replace(pending, applied=True, blocked_by_unresolved_upgrade_choices=False)
        updated = self.sync_actor_snapshots(updated, actor_snapshots=actor_snapshots)
        events = list(self._eligibility_events(updated))
        events.append(ProgressionProjectionUpdatedEvent(mode=updated.mode, pending_level_up_ids=tuple(sorted(updated.pending_level_ups))))
        return updated, tuple(events)

    def _eligibility_events(self, state: CampaignProgressionState) -> tuple[object, ...]:
        return tuple(
            ProgressionEligibilityUpdatedEvent(
                actor_id=progress.actor_id,
                actor_label=progress.actor_label,
                current_level=progress.current_level,
                eligible_level=progress.eligible_level,
                mode=state.mode,
                pending_level_up_ids=progress.pending_level_up_ids,
            )
            for progress in sorted(state.actor_progress.values(), key=lambda item: item.actor_id)
        )

    def _xp_rewards_for_actor(self, state: CampaignProgressionState, actor_id: str) -> list[tuple[XPRewardRecord, int]]:
        rewards: list[tuple[XPRewardRecord, int]] = []
        for record in sorted(state.xp_rewards.values(), key=lambda item: (item.timestamp_seconds, item.reward_id)):
            if not record.applied:
                continue
            amount = next((award.xp_amount for award in record.recipients if award.actor_id == actor_id), None)
            if amount is not None:
                rewards.append((record, amount))
        return rewards

    def _milestone_awards_for_actor(self, state: CampaignProgressionState, actor_id: str) -> list[tuple[MilestoneRecord, int]]:
        awards: list[tuple[MilestoneRecord, int]] = []
        for record in sorted(state.milestone_records.values(), key=lambda item: (item.timestamp_seconds, item.milestone_id)):
            if not record.advancement_granted:
                continue
            steps = next((award.advancement_steps for award in record.recipients if award.actor_id == actor_id), None)
            if steps is not None:
                awards.append((record, steps))
        return awards

    def _eligible_level_for_actor(
        self,
        state: CampaignProgressionState,
        *,
        actor_id: str,
        current_level: int,
        xp_total: int,
        granted_milestone_advancements: int,
    ) -> int:
        if state.mode == ProgressionMode.XP:
            return self._eligible_level_for_xp(xp_total)
        applied_milestone_steps = sum(
            1
            for record in state.pending_level_ups.values()
            if record.actor_id == actor_id and record.applied and record.source_mode == ProgressionMode.MILESTONE
        )
        effective_advancements = max(0, granted_milestone_advancements - applied_milestone_steps)
        return min(MAX_CHARACTER_LEVEL, current_level + effective_advancements)

    def _eligible_level_for_xp(self, xp_total: int) -> int:
        eligible_level = 1
        for level, threshold in sorted(XP_LEVEL_THRESHOLDS.items()):
            if xp_total >= threshold:
                eligible_level = level
        return eligible_level

    def _next_level_threshold(self, current_level: int) -> int | None:
        next_level = min(MAX_CHARACTER_LEVEL, current_level + 1)
        if current_level >= MAX_CHARACTER_LEVEL:
            return None
        return XP_LEVEL_THRESHOLDS[next_level]

    def _resolve_xp_awards(
        self,
        state: CampaignProgressionState,
        *,
        actor_map: dict[str, str],
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        amount: int,
    ) -> tuple[XPRecipientAward, ...]:
        recipients = tuple(sorted(recipient_actor_ids))
        policy = state.policy.xp_distribution
        if policy == XPDistributionPolicy.PARTY_WIDE:
            if recipient_scope != ProgressionRecipientScope.PARTY:
                raise EncounterValidationError('Party-wide XP policy requires `party` recipients.')
            return tuple(XPRecipientAward(actor_id=actor_id, actor_label=actor_map[actor_id], xp_amount=amount) for actor_id in recipients)
        if policy == XPDistributionPolicy.INDIVIDUAL:
            if recipient_scope == ProgressionRecipientScope.PARTY:
                raise EncounterValidationError('Individual XP policy requires `actor:` or `actors:` recipients.')
            return tuple(XPRecipientAward(actor_id=actor_id, actor_label=actor_map[actor_id], xp_amount=amount) for actor_id in recipients)
        share, remainder = divmod(amount, len(recipients))
        awards: list[XPRecipientAward] = []
        for index, actor_id in enumerate(recipients):
            awards.append(XPRecipientAward(actor_id=actor_id, actor_label=actor_map[actor_id], xp_amount=share + (1 if index < remainder else 0)))
        return tuple(awards)

    def _resolve_milestone_awards(
        self,
        state: CampaignProgressionState,
        *,
        actor_map: dict[str, str],
        recipient_scope: ProgressionRecipientScope,
        recipient_actor_ids: tuple[str, ...],
        advancement_steps: int,
    ) -> tuple[MilestoneRecipientAward, ...]:
        recipients = tuple(sorted(recipient_actor_ids))
        if state.policy.milestone_distribution == MilestoneDistributionPolicy.PARTY_WIDE and recipient_scope != ProgressionRecipientScope.PARTY:
            raise EncounterValidationError('Party-wide milestone policy requires `party` recipients.')
        return tuple(MilestoneRecipientAward(actor_id=actor_id, actor_label=actor_map[actor_id], advancement_steps=advancement_steps) for actor_id in recipients)

    def _xp_threshold_reward_refs(self, state: CampaignProgressionState, *, actor_id: str) -> dict[int, tuple[str, ...]]:
        refs: dict[int, tuple[str, ...]] = {}
        cumulative = 0
        reward_ids: list[str] = []
        next_target = 2
        for reward, amount in self._xp_rewards_for_actor(state, actor_id):
            cumulative += amount
            reward_ids.append(reward.reward_id)
            while next_target <= MAX_CHARACTER_LEVEL and cumulative >= XP_LEVEL_THRESHOLDS[next_target]:
                refs[next_target] = tuple(reward_ids)
                next_target += 1
        return refs

    def _milestone_threshold_refs(self, state: CampaignProgressionState, *, actor_id: str, current_level: int) -> dict[int, tuple[str, ...]]:
        refs: dict[int, tuple[str, ...]] = {}
        applied_steps = sum(
            1
            for record in state.pending_level_ups.values()
            if record.actor_id == actor_id and record.applied and record.source_mode == ProgressionMode.MILESTONE
        )
        unconsumed_step_index = 0
        granted_ids: list[str] = []
        target_level = current_level
        for record, steps in self._milestone_awards_for_actor(state, actor_id):
            for _ in range(steps):
                if unconsumed_step_index < applied_steps:
                    unconsumed_step_index += 1
                    continue
                if record.milestone_id not in granted_ids:
                    granted_ids.append(record.milestone_id)
                target_level = min(MAX_CHARACTER_LEVEL, target_level + 1)
                refs[target_level] = tuple(granted_ids)
        return refs

    def _validate_recipient_actor_ids(self, actor_map: dict[str, str], recipient_actor_ids: tuple[str, ...]) -> None:
        unknown = [actor_id for actor_id in recipient_actor_ids if actor_id not in actor_map]
        if unknown:
            raise EncounterValidationError(f'Unknown progression recipient actor ids: {", ".join(sorted(unknown))}.')

    def _xp_reward_id(self, *, source_type: XPRewardSourceType, source_id: str, recipient_scope: ProgressionRecipientScope, recipient_actor_ids: tuple[str, ...]) -> str:
        recipient_key = '-'.join(sorted(recipient_actor_ids))
        return f'xp:{source_type.value}:{source_id}:{recipient_scope.value}:{recipient_key}'

    def _milestone_id(self, *, source_type: MilestoneSourceType, source_id: str, recipient_scope: ProgressionRecipientScope, recipient_actor_ids: tuple[str, ...]) -> str:
        recipient_key = '-'.join(sorted(recipient_actor_ids))
        return f'milestone:{source_type.value}:{source_id}:{recipient_scope.value}:{recipient_key}'

    def _pending_id(self, mode: ProgressionMode, *, actor_id: str, target_level: int) -> str:
        return f'level-up:{mode.value}:{actor_id}:{target_level}'

    def _default_xp_dedupe_key(self, *, source_type: XPRewardSourceType, source_id: str, recipient_scope: ProgressionRecipientScope, recipient_actor_ids: tuple[str, ...]) -> str:
        return self._xp_reward_id(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)

    def _default_milestone_dedupe_key(self, *, source_type: MilestoneSourceType, source_id: str, recipient_scope: ProgressionRecipientScope, recipient_actor_ids: tuple[str, ...]) -> str:
        return self._milestone_id(source_type=source_type, source_id=source_id, recipient_scope=recipient_scope, recipient_actor_ids=recipient_actor_ids)
