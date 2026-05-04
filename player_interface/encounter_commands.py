from __future__ import annotations

from shared_types.battlefield import MovementIntentMode
from shared_types.encounter_intents import (
    AttackIntent,
    AdvanceTimeIntent,
    CastSpellIntent,
    ChooseReactionIntent,
    ReadyIntent,
    EndTurnIntent,
    EquipItemIntent,
    DismountActorIntent,
    MountActorIntent,
    ObjectInteractionIntent,
    ShareFamiliarSensesIntent,
    ResumeRestIntent,
    SpendHitPointDieIntent,
    StartLongRestIntent,
    StartShortRestIntent,
    GrappleIntent,
    MoveActorIntent,
    ShoveIntent,
    StandFromProneIntent,
    StartEncounterIntent,
    TakeCombatActionIntent,
    UseCapabilityIntent,
    UseImprovisedWeaponIntent,
)
from shared_types.encounter_models import CombatActionType, ReadyResponseKind, ReadyTriggerKind, ShoveOutcome
from shared_types.equipment import AttackInteractionSpec, AttackInteractionTiming, EnvironmentObjectAction, EquipmentSlot, ObjectInteractionCostMode, ObjectInteractionKind
from shared_types.rest import RestActivityType
from shared_types.spellcasting import SpellParameter
from shared_types.errors import UnknownEncounterCommandError

from .encounter_presenter import present_encounter_snapshot


class EncounterSlashCommandInterface:
    def __init__(self, kernel) -> None:
        self.kernel = kernel

    def _parse_int(self, token: str) -> int:
        try:
            return int(token)
        except ValueError as exc:
            raise UnknownEncounterCommandError(f'Expected an integer token, got {token!r}.') from exc

    def _parse_shove_outcome(self, token: str) -> ShoveOutcome:
        try:
            return ShoveOutcome(token)
        except ValueError as exc:
            raise UnknownEncounterCommandError(f'Unknown shove outcome: {token!r}.') from exc

    def _parse_rest_activity(self, token: str) -> RestActivityType:
        normalized = token.strip().lower()
        mapping = {
            'quiet': RestActivityType.QUIET,
            'sleep': RestActivityType.SLEEP,
            'light': RestActivityType.LIGHT_ACTIVITY,
            'light-activity': RestActivityType.LIGHT_ACTIVITY,
            'exert': RestActivityType.EXERTION,
            'exertion': RestActivityType.EXERTION,
        }
        activity = mapping.get(normalized)
        if activity is None:
            raise UnknownEncounterCommandError(f'Unknown rest activity: {token!r}.')
        return activity

    def _parse_object_interaction_kind(self, token: str) -> ObjectInteractionKind:
        mapping = {
            'draw': ObjectInteractionKind.DRAW,
            'stow': ObjectInteractionKind.STOW,
            'drop': ObjectInteractionKind.DROP,
            'pickup': ObjectInteractionKind.PICK_UP,
            'pick-up': ObjectInteractionKind.PICK_UP,
            'transfer': ObjectInteractionKind.TRANSFER,
            'don-shield': ObjectInteractionKind.DON_SHIELD,
            'doff-shield': ObjectInteractionKind.DOFF_SHIELD,
            'don-armor': ObjectInteractionKind.DON_ARMOR,
            'doff-armor': ObjectInteractionKind.DOFF_ARMOR,
        }
        try:
            return mapping[token.strip().lower()]
        except KeyError as exc:
            raise UnknownEncounterCommandError(f'Unknown object interaction kind: {token!r}.') from exc

    def _parse_environment_object_action(self, token: str) -> EnvironmentObjectAction:
        mapping = {
            'open': EnvironmentObjectAction.OPEN,
            'close': EnvironmentObjectAction.CLOSE,
            'toggle': EnvironmentObjectAction.TOGGLE,
            'activate': EnvironmentObjectAction.ACTIVATE,
            'deactivate': EnvironmentObjectAction.DEACTIVATE,
        }
        try:
            return mapping[token.strip().lower()]
        except KeyError as exc:
            raise UnknownEncounterCommandError(f'Unknown environment-object action: {token!r}.') from exc

    def _parse_equipment_slot(self, token: str) -> EquipmentSlot:
        mapping = {
            'main-hand': EquipmentSlot.MAIN_HAND,
            'mainhand': EquipmentSlot.MAIN_HAND,
            'off-hand': EquipmentSlot.OFF_HAND,
            'offhand': EquipmentSlot.OFF_HAND,
            'armor': EquipmentSlot.ARMOR,
        }
        try:
            return mapping[token.strip().lower()]
        except KeyError as exc:
            raise UnknownEncounterCommandError(f'Unknown equipment slot: {token!r}.') from exc

    def _parse_attack_interaction_spec(self, token: str, *, timing: AttackInteractionTiming) -> AttackInteractionSpec:
        if ':' not in token:
            raise UnknownEncounterCommandError('Attack interaction specs must look like `draw:item-id`, `stow:item-id`, `drop:item-id`, or `pickup:ground-item-id`.')
        verb, value = token.split(':', 1)
        kind = self._parse_object_interaction_kind(verb)
        if kind == ObjectInteractionKind.PICK_UP:
            return AttackInteractionSpec(timing=timing, interaction_kind=kind, ground_item_id=value)
        return AttackInteractionSpec(timing=timing, interaction_kind=kind, item_id=value)

    def _parse_object_interaction_command(self, tokens: list[str], *, cost_mode: ObjectInteractionCostMode):
        if len(tokens) < 3:
            raise UnknownEncounterCommandError('Object interaction requires at least an actor id and an interaction verb.')
        actor_id = tokens[1]
        third = tokens[2].strip().lower()
        if third in {'open', 'close', 'toggle', 'activate', 'deactivate'}:
            if len(tokens) != 4:
                raise UnknownEncounterCommandError('Environment object interaction requires `/<interact|utilize> <actor-id> <open|close|toggle|activate|deactivate> <object-id>`.')
            return ObjectInteractionIntent(actor_id=actor_id, interaction_kind=ObjectInteractionKind.USE_ENVIRONMENT_OBJECT, cost_mode=cost_mode, object_id=tokens[3], object_action=self._parse_environment_object_action(tokens[2]))
        kind = self._parse_object_interaction_kind(tokens[2])
        if kind in {ObjectInteractionKind.DOFF_SHIELD, ObjectInteractionKind.DOFF_ARMOR}:
            item_id = tokens[3] if len(tokens) == 4 else None
            if len(tokens) not in {3, 4}:
                raise UnknownEncounterCommandError('Doff interactions accept at most one optional item id.')
            return ObjectInteractionIntent(actor_id=actor_id, interaction_kind=kind, cost_mode=cost_mode, item_id=item_id)
        if kind == ObjectInteractionKind.TRANSFER:
            if len(tokens) != 5:
                raise UnknownEncounterCommandError('Transfer requires `/<interact|utilize> <actor-id> transfer <source-actor-id> <item-id>`.')
            return ObjectInteractionIntent(actor_id=actor_id, interaction_kind=kind, cost_mode=cost_mode, item_id=tokens[4], source_actor_id=tokens[3])
        if len(tokens) != 4:
            raise UnknownEncounterCommandError('Item object interactions require `/<interact|utilize> <actor-id> <verb> <item-id|ground-item-id>`.')
        if kind == ObjectInteractionKind.PICK_UP:
            return ObjectInteractionIntent(actor_id=actor_id, interaction_kind=kind, cost_mode=cost_mode, ground_item_id=tokens[3])
        return ObjectInteractionIntent(actor_id=actor_id, interaction_kind=kind, cost_mode=cost_mode, item_id=tokens[3])

    def _parse_improvised_attack_command(self, tokens: list[str]) -> UseImprovisedWeaponIntent:
        if len(tokens) < 4:
            raise UnknownEncounterCommandError('Improvised attacks require `/improvise <actor-id> <target-id> <item:item-id|object:object-id> [--thrown] [--damage type] [--equivalent weapon-id]`.')
        actor_id = tokens[1]
        target_id = tokens[2]
        source_token = tokens[3]
        item_id = None
        object_id = None
        if ':' not in source_token:
            raise UnknownEncounterCommandError('Improvised attack source must be tagged like `item:torch` or `object:door-bar`.')
        source_kind, source_value = source_token.split(':', 1)
        if source_kind == 'item':
            item_id = source_value
        elif source_kind == 'object':
            object_id = source_value
        else:
            raise UnknownEncounterCommandError('Improvised attack source must begin with `item:` or `object:`.')
        thrown = False
        damage_type = 'bludgeoning'
        equivalent_weapon_item_id = None
        index = 4
        while index < len(tokens):
            token = tokens[index]
            if token == '--thrown':
                thrown = True
                index += 1
                continue
            if token == '--damage' and index + 1 < len(tokens):
                damage_type = tokens[index + 1]
                index += 2
                continue
            if token == '--equivalent' and index + 1 < len(tokens):
                equivalent_weapon_item_id = tokens[index + 1]
                index += 2
                continue
            raise UnknownEncounterCommandError(f'Unknown improvised attack token: {token!r}.')
        return UseImprovisedWeaponIntent(actor_id=actor_id, target_id=target_id, item_id=item_id, object_id=object_id, thrown=thrown, equivalent_weapon_item_id=equivalent_weapon_item_id, damage_type=damage_type)

    def _parse_move_command(self, tokens: list[str]) -> MoveActorIntent:
        if len(tokens) not in {4, 5, 6}:
            raise UnknownEncounterCommandError('Move requires `/move <actor-id> <x> <y> [z] [--allow-elevation|--allow-climb|--allow-fly]`.')
        actor_id = tokens[1]
        x = self._parse_int(tokens[2])
        y = self._parse_int(tokens[3])
        z: int | None = None
        mode = MovementIntentMode.SAME_PLANE
        extras = tokens[4:]
        for token in extras:
            if token == '--allow-elevation':
                mode = MovementIntentMode.ALLOW_ELEVATION
            elif token == '--allow-climb':
                mode = MovementIntentMode.ALLOW_CLIMB
            elif token == '--allow-fly':
                mode = MovementIntentMode.ALLOW_FLY
            else:
                if z is not None:
                    raise UnknownEncounterCommandError('Move accepts at most one explicit z coordinate.')
                z = self._parse_int(token)
        return MoveActorIntent(actor_id=actor_id, x=x, y=y, z=z, movement_intent_mode=mode)

    def _parse_ready_command(self, tokens: list[str]) -> ReadyIntent:
        if len(tokens) < 5:
            raise UnknownEncounterCommandError('Ready requires `/ready <attack|move|cast|feature> <actor-id> <trigger-actor-id> ...`.')
        mode = tokens[1].strip().lower()
        actor_id = tokens[2]
        trigger_actor_id = tokens[3]
        if mode == 'attack':
            if len(tokens) != 5:
                raise UnknownEncounterCommandError('Readied attacks require `/ready attack <actor-id> <trigger-actor-id> <attack-id>`.')
            return ReadyIntent(
                actor_id=actor_id,
                trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW,
                trigger_actor_id=trigger_actor_id,
                response_kind=ReadyResponseKind.ATTACK,
                attack_id=tokens[4],
            )
        if mode in {'cast', 'spell'}:
            if len(tokens) != 5:
                raise UnknownEncounterCommandError('Readied spells require `/ready cast <actor-id> <trigger-actor-id> <spell-id>`.')
            return ReadyIntent(
                actor_id=actor_id,
                trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW,
                trigger_actor_id=trigger_actor_id,
                response_kind=ReadyResponseKind.SPELL,
                spell_id=tokens[4],
            )
        if mode in {'feature', 'capability'}:
            if len(tokens) != 5:
                raise UnknownEncounterCommandError('Readied capabilities require `/ready feature <actor-id> <trigger-actor-id> <capability-id>`.')
            return ReadyIntent(
                actor_id=actor_id,
                trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW,
                trigger_actor_id=trigger_actor_id,
                response_kind=ReadyResponseKind.CAPABILITY,
                capability_id=tokens[4],
            )
        if mode == 'move':
            if len(tokens) < 6:
                raise UnknownEncounterCommandError('Readied movement requires `/ready move <actor-id> <trigger-actor-id> <x> <y> [z] [--allow-elevation|--allow-climb|--allow-fly]`.')
            x = self._parse_int(tokens[4])
            y = self._parse_int(tokens[5])
            z: int | None = None
            movement_intent_mode = MovementIntentMode.SAME_PLANE
            for token in tokens[6:]:
                if token == '--allow-elevation':
                    movement_intent_mode = MovementIntentMode.ALLOW_ELEVATION
                    continue
                if token == '--allow-climb':
                    movement_intent_mode = MovementIntentMode.ALLOW_CLIMB
                    continue
                if token == '--allow-fly':
                    movement_intent_mode = MovementIntentMode.ALLOW_FLY
                    continue
                if z is not None:
                    raise UnknownEncounterCommandError('Readied movement accepts at most one explicit z coordinate.')
                z = self._parse_int(token)
            return ReadyIntent(
                actor_id=actor_id,
                trigger_kind=ReadyTriggerKind.TARGET_IN_RESPONSE_WINDOW,
                trigger_actor_id=trigger_actor_id,
                response_kind=ReadyResponseKind.MOVE,
                x=x,
                y=y,
                z=z,
                movement_intent_mode=movement_intent_mode,
            )
        raise UnknownEncounterCommandError(f'Unknown ready mode: {mode!r}.')

    def _parse_capability_command(self, tokens: list[str], *, command_name: str) -> UseCapabilityIntent:
        if len(tokens) < 3:
            raise UnknownEncounterCommandError(f'{command_name} requires `/{command_name} <actor-id> <capability-id> [target-id|x y [z]] [--key value ...]`.')
        actor_id = tokens[1]
        capability_id = tokens[2]
        positional: list[str] = []
        parameters: list[SpellParameter] = []
        index = 3
        while index < len(tokens):
            token = tokens[index]
            if token.startswith('--'):
                key = token[2:]
                if not key:
                    raise UnknownEncounterCommandError(f'{command_name} parameter keys cannot be empty.')
                index += 1
                values: list[str] = []
                while index < len(tokens) and not tokens[index].startswith('--'):
                    values.append(tokens[index])
                    index += 1
                if not values:
                    raise UnknownEncounterCommandError(f'{command_name} parameter --{key} requires a value.')
                parameters.append(SpellParameter(key=key, value=' '.join(values)))
                continue
            positional.append(token)
            index += 1
        if not positional:
            return UseCapabilityIntent(actor_id=actor_id, capability_id=capability_id, parameters=tuple(parameters))
        if len(positional) == 1:
            return UseCapabilityIntent(actor_id=actor_id, capability_id=capability_id, target_id=positional[0], parameters=tuple(parameters))
        if len(positional) in {2, 3}:
            return UseCapabilityIntent(
                actor_id=actor_id,
                capability_id=capability_id,
                x=self._parse_int(positional[0]),
                y=self._parse_int(positional[1]),
                z=(self._parse_int(positional[2]) if len(positional) == 3 else None),
                parameters=tuple(parameters),
            )
        raise UnknownEncounterCommandError(f'{command_name} requires `/{command_name} <actor-id> <capability-id> [target-id|x y [z]] [--key value ...]`.')

    def _parse_cast_command(self, tokens: list[str]) -> CastSpellIntent:
        if len(tokens) < 3:
            raise UnknownEncounterCommandError('Cast requires `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.')
        actor_id = tokens[1]
        spell_id = tokens[2]
        ritual_cast = False
        positional: list[str] = []
        parameters: list[SpellParameter] = []
        index = 3
        while index < len(tokens):
            token = tokens[index]
            if token == '--ritual':
                ritual_cast = True
                index += 1
                continue
            if token.startswith('--'):
                key = token[2:]
                if not key:
                    raise UnknownEncounterCommandError('Spell parameter keys cannot be empty.')
                index += 1
                values: list[str] = []
                while index < len(tokens) and not tokens[index].startswith('--'):
                    values.append(tokens[index])
                    index += 1
                if not values:
                    raise UnknownEncounterCommandError(f'Spell parameter --{key} requires a value.')
                parameters.append(SpellParameter(key=key, value=' '.join(values)))
                continue
            positional.append(token)
            index += 1
        if not positional:
            return CastSpellIntent(actor_id=actor_id, spell_id=spell_id, ritual_cast=ritual_cast, parameters=tuple(parameters))
        if len(positional) == 1:
            return CastSpellIntent(actor_id=actor_id, spell_id=spell_id, target_id=positional[0], ritual_cast=ritual_cast, parameters=tuple(parameters))
        if len(positional) in {2, 3}:
            return CastSpellIntent(
                actor_id=actor_id,
                spell_id=spell_id,
                x=self._parse_int(positional[0]),
                y=self._parse_int(positional[1]),
                z=(self._parse_int(positional[2]) if len(positional) == 3 else None),
                ritual_cast=ritual_cast,
                parameters=tuple(parameters),
            )
        raise UnknownEncounterCommandError('Cast requires `/cast <actor-id> <spell-id> [target-id|x y [z]] [--ritual] [--key value ...]`.')

    def parse_command(self, command: str):
        tokens = command.strip().split()
        if not tokens:
            raise UnknownEncounterCommandError('Encounter commands cannot be empty.')

        if tokens[:2] == ['/encounter', 'start']:
            return StartEncounterIntent()
        if tokens[:2] == ['/encounter', 'summary']:
            return None
        if tokens[0] == '/initiative':
            return None
        if tokens[0] == '/move':
            return self._parse_move_command(tokens)
        if tokens[0] == '/mount' and len(tokens) == 3:
            return MountActorIntent(actor_id=tokens[1], mount_actor_id=tokens[2])
        if tokens[0] == '/dismount' and len(tokens) == 2:
            return DismountActorIntent(actor_id=tokens[1])
        if tokens[0] == '/sense' and len(tokens) == 3:
            familiar_actor_id = None if tokens[2].strip().lower() in {'off', 'end', 'stop', 'none'} else tokens[2]
            return ShareFamiliarSensesIntent(actor_id=tokens[1], familiar_actor_id=familiar_actor_id)
        if tokens[0] == '/climb' and len(tokens) in {4, 5}:
            z = self._parse_int(tokens[4]) if len(tokens) == 5 else None
            return MoveActorIntent(actor_id=tokens[1], x=self._parse_int(tokens[2]), y=self._parse_int(tokens[3]), z=z, movement_intent_mode=MovementIntentMode.ALLOW_CLIMB)
        if tokens[0] == '/fly' and len(tokens) == 5:
            return MoveActorIntent(actor_id=tokens[1], x=self._parse_int(tokens[2]), y=self._parse_int(tokens[3]), z=self._parse_int(tokens[4]), movement_intent_mode=MovementIntentMode.ALLOW_FLY)
        if tokens[0] == '/stand' and len(tokens) == 2:
            return StandFromProneIntent(actor_id=tokens[1])
        if tokens[0] == '/attack' and len(tokens) >= 4:
            actor_id = tokens[1]
            attack_id = tokens[2]
            target_id = tokens[3]
            attack_interaction = None
            index = 4
            while index < len(tokens):
                token = tokens[index]
                if token == '--before' and index + 1 < len(tokens):
                    if attack_interaction is not None:
                        raise UnknownEncounterCommandError('Attack accepts at most one before/after interaction in this slice.')
                    attack_interaction = self._parse_attack_interaction_spec(tokens[index + 1], timing=AttackInteractionTiming.BEFORE)
                    index += 2
                    continue
                if token == '--after' and index + 1 < len(tokens):
                    if attack_interaction is not None:
                        raise UnknownEncounterCommandError('Attack accepts at most one before/after interaction in this slice.')
                    attack_interaction = self._parse_attack_interaction_spec(tokens[index + 1], timing=AttackInteractionTiming.AFTER)
                    index += 2
                    continue
                raise UnknownEncounterCommandError(f'Unknown /attack token: {token!r}.')
            return AttackIntent(actor_id=actor_id, attack_id=attack_id, target_id=target_id, attack_interaction=attack_interaction)
        if tokens[0] == '/cast':
            return self._parse_cast_command(tokens)
        if tokens[0] == '/feature':
            return self._parse_capability_command(tokens, command_name='feature')
        if tokens[0] == '/use':
            return self._parse_capability_command(tokens, command_name='use')
        if tokens[0] == '/dash' and len(tokens) in {2, 3}:
            resource_mode = 'action'
            if len(tokens) == 3:
                if tokens[2] != '--bonus':
                    raise UnknownEncounterCommandError("Dash accepts at most the optional token --bonus.")
                resource_mode = 'bonus'
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.DASH, resource_mode=resource_mode)
        if tokens[0] == '/disengage' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.DISENGAGE)
        if tokens[0] == '/dodge' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.DODGE)
        if tokens[0] == '/help' and len(tokens) == 3:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.HELP, target_id=tokens[2])
        if tokens[0] == '/hide' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.HIDE)
        if tokens[0] == '/ready':
            return self._parse_ready_command(tokens)
        if tokens[0] == '/search' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.SEARCH)
        if tokens[0] == '/study' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.STUDY)
        if tokens[0] == '/interact':
            return self._parse_object_interaction_command(tokens, cost_mode=ObjectInteractionCostMode.FREE)
        if tokens[0] == '/equip' and len(tokens) == 4:
            return EquipItemIntent(actor_id=tokens[1], item_id=tokens[2], slot=self._parse_equipment_slot(tokens[3]))
        if tokens[0] == '/utilize' and len(tokens) == 2:
            return TakeCombatActionIntent(actor_id=tokens[1], action_type=CombatActionType.UTILIZE)
        if tokens[0] == '/utilize' and len(tokens) >= 3:
            return self._parse_object_interaction_command(tokens, cost_mode=ObjectInteractionCostMode.UTILIZE)
        if tokens[0] == '/grapple' and len(tokens) == 3:
            return GrappleIntent(actor_id=tokens[1], target_id=tokens[2])
        if tokens[0] == '/shove' and len(tokens) == 4:
            return ShoveIntent(actor_id=tokens[1], target_id=tokens[2], outcome=self._parse_shove_outcome(tokens[3]))
        if tokens[0] == '/improvise':
            return self._parse_improvised_attack_command(tokens)
        if tokens[0] == '/react' and len(tokens) == 3:
            return ChooseReactionIntent(actor_id=tokens[1], option_id=tokens[2])
        if tokens[0] == '/endturn' and len(tokens) == 2:
            return EndTurnIntent(actor_id=tokens[1])
        if tokens[0] == '/shortrest' and len(tokens) == 2:
            return StartShortRestIntent(actor_id=tokens[1])
        if tokens[0] == '/longrest' and len(tokens) == 2:
            return StartLongRestIntent(actor_id=tokens[1])
        if tokens[:2] == ['/rest', 'resume'] and len(tokens) == 3:
            return ResumeRestIntent(actor_id=tokens[2])
        if tokens[0] == '/hitdie' and len(tokens) in {2, 3}:
            return SpendHitPointDieIntent(actor_id=tokens[1], count=(self._parse_int(tokens[2]) if len(tokens) == 3 else 1))
        if tokens[:2] == ['/time', 'advance'] and len(tokens) in {3, 4}:
            activity = RestActivityType.LIGHT_ACTIVITY
            if len(tokens) == 4:
                activity = self._parse_rest_activity(tokens[3])
            return AdvanceTimeIntent(minutes=self._parse_int(tokens[2]), activity_type=activity)
        if tokens[0] == '/time' and len(tokens) == 3:
            return AdvanceTimeIntent(minutes=self._parse_int(tokens[2]), activity_type=self._parse_rest_activity(tokens[1]))
        if tokens[:2] == ['/turn', 'end'] and len(tokens) == 3:
            return EndTurnIntent(actor_id=tokens[2])
        if tokens[:2] == ['/action', 'dash'] and len(tokens) == 3:
            return TakeCombatActionIntent(actor_id=tokens[2], action_type=CombatActionType.DASH, resource_mode='action')
        if tokens[:2] == ['/action', 'dodge'] and len(tokens) == 3:
            return TakeCombatActionIntent(actor_id=tokens[2], action_type=CombatActionType.DODGE)
        raise UnknownEncounterCommandError('Unknown encounter command.')

    def render(self, state) -> str:
        return present_encounter_snapshot(self.kernel.snapshot(state))

    def execute(self, state, command: str):
        intent = self.parse_command(command)
        if intent is not None:
            state = self.kernel.dispatch(state, intent)
        return state, self.render(state)
