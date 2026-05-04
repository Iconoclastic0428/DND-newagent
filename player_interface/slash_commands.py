from __future__ import annotations

from shared_types.errors import UnknownCommandError
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
    GenerateRolledAbilitiesIntent,
    ResolveCreationChoiceIntent,
    SetPointBuyScoresIntent,
)
from shared_types.models import ABILITY_ORDER, AbilityMethod, ContentKind, EquipmentSelectionMode

from .presenter import present_inspection, present_policy, present_snapshot


class SlashCommandInterface:
    def __init__(self, kernel) -> None:
        self.kernel = kernel

    def execute(self, state, command: str) -> tuple[object, str]:
        tokens = command.strip().split()
        if len(tokens) < 2 or tokens[0] != "/create":
            raise UnknownCommandError("Character creation commands must start with /create.")

        if tokens[1] == "begin":
            state = self.kernel.dispatch(state, BeginCreationIntent())
            return state, present_snapshot(self.kernel.snapshot(state))

        if tokens[1] == "policy" and tokens[2:] == ["show"]:
            return state, present_policy(self.kernel.policy)

        if tokens[1] == "inspect" and len(tokens) == 4:
            kind = ContentKind(tokens[2])
            return state, present_inspection(self.kernel.inspect(kind, tokens[3]))

        if tokens[1] == "choose" and len(tokens) >= 4:
            subject = tokens[2]
            if subject == "species" and len(tokens) == 4:
                state = self.kernel.dispatch(state, ChooseSpeciesIntent(species_id=tokens[3]))
                return state, present_snapshot(self.kernel.snapshot(state))
            if subject == "class" and len(tokens) == 4:
                state = self.kernel.dispatch(state, ChooseClassIntent(class_id=tokens[3]))
                return state, present_snapshot(self.kernel.snapshot(state))
            if subject == "class-skills" and len(tokens) >= 4:
                state = self.kernel.dispatch(state, ChooseClassSkillsIntent(skill_ids=tuple(tokens[3:])))
                return state, present_snapshot(self.kernel.snapshot(state))
            if subject == "background" and len(tokens) == 4:
                state = self.kernel.dispatch(state, ChooseBackgroundIntent(background_id=tokens[3]))
                return state, present_snapshot(self.kernel.snapshot(state))
            if subject == "origin-feat" and len(tokens) == 4:
                state = self.kernel.dispatch(state, ChooseOriginFeatIntent(feat_id=tokens[3]))
                return state, present_snapshot(self.kernel.snapshot(state))
            if subject == "choice" and len(tokens) >= 5:
                state = self.kernel.dispatch(
                    state,
                    ResolveCreationChoiceIntent(choice_id=tokens[3], option_ids=tuple(tokens[4:])),
                )
                return state, present_snapshot(self.kernel.snapshot(state))
            raise UnknownCommandError("Unknown /create choose command.")

        if tokens[1] == "ability" and len(tokens) >= 3:
            if tokens[2] == "generate":
                if tokens[3:] == ["roll"]:
                    state = self.kernel.dispatch(state, GenerateRolledAbilitiesIntent())
                    return state, present_snapshot(self.kernel.snapshot(state))
                if tokens[3] == "point-buy" and len(tokens) == 10:
                    scores = tuple(int(value) for value in tokens[4:])
                    state = self.kernel.dispatch(state, SetPointBuyScoresIntent(scores=scores))
                    return state, present_snapshot(self.kernel.snapshot(state))
                raise UnknownCommandError("Use /create ability generate roll or /create ability generate point-buy <6 scores>.")
            if tokens[2] == "choose" and len(tokens) == 4:
                state = self.kernel.dispatch(state, ChooseAbilityArrayIntent(method=AbilityMethod(tokens[3])))
                return state, present_snapshot(self.kernel.snapshot(state))
            if tokens[2] == "assign" and len(tokens) == 9:
                scores = [int(value) for value in tokens[3:]]
                assignments = {ability: score for ability, score in zip(ABILITY_ORDER, scores, strict=True)}
                state = self.kernel.dispatch(state, AssignAbilityScoresIntent(assignments=assignments))
                return state, present_snapshot(self.kernel.snapshot(state))
            raise UnknownCommandError("Unknown /create ability command.")

        if tokens[1] == "background-asi" and tokens[2:] and tokens[2] == "choose" and len(tokens) == 4:
            state = self.kernel.dispatch(state, ChooseBackgroundAsiIntent(option_id=tokens[3]))
            return state, present_snapshot(self.kernel.snapshot(state))

        if tokens[1] == "equipment" and len(tokens) >= 4:
            if tokens[2] == "background":
                if tokens[3] == "gold":
                    state = self.kernel.dispatch(state, ChooseBackgroundEquipmentIntent(mode=EquipmentSelectionMode.GOLD))
                    return state, present_snapshot(self.kernel.snapshot(state))
                if tokens[3] == "package" and len(tokens) == 5:
                    state = self.kernel.dispatch(
                        state,
                        ChooseBackgroundEquipmentIntent(mode=EquipmentSelectionMode.PACKAGE, package_id=tokens[4]),
                    )
                    return state, present_snapshot(self.kernel.snapshot(state))
            if tokens[2] == "class":
                if tokens[3] == "wealth":
                    state = self.kernel.dispatch(state, ChooseClassEquipmentIntent(mode=EquipmentSelectionMode.WEALTH))
                    return state, present_snapshot(self.kernel.snapshot(state))
                if tokens[3] == "package" and len(tokens) == 5:
                    state = self.kernel.dispatch(
                        state,
                        ChooseClassEquipmentIntent(mode=EquipmentSelectionMode.PACKAGE, package_id=tokens[4]),
                    )
                    return state, present_snapshot(self.kernel.snapshot(state))
            if tokens[2] == "buy" and len(tokens) == 5:
                state = self.kernel.dispatch(state, BuyItemIntent(item_id=tokens[3], quantity=int(tokens[4])))
                return state, present_snapshot(self.kernel.snapshot(state))
            raise UnknownCommandError("Unknown /create equipment command.")

        if tokens[1] == "summary":
            return state, present_snapshot(self.kernel.snapshot(state))

        if tokens[1] == "confirm":
            state = self.kernel.dispatch(state, ConfirmCharacterIntent())
            return state, present_snapshot(self.kernel.snapshot(state))

        raise UnknownCommandError("Unknown /create command.")
