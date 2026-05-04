class CharacterCreationError(Exception):
    """Base error for deterministic character creation failures."""


class ValidationError(CharacterCreationError):
    """Raised when an intent is invalid for the current state or policy."""


class UnknownCommandError(CharacterCreationError):
    """Raised when a slash command cannot be parsed deterministically."""


class ContentLoadError(CharacterCreationError):
    """Raised when 5etools mirror content cannot satisfy the active policy."""


class EncounterError(Exception):
    """Base error for deterministic encounter runtime failures."""


class EncounterValidationError(EncounterError):
    """Raised when an encounter intent is invalid for the current state."""


class EncounterClarificationRequiredError(EncounterValidationError):
    """Raised when a deterministic command needs explicit user confirmation instead of a guess."""


class EncounterMovementPreviewError(EncounterClarificationRequiredError):
    """Raised when movement returns a typed preview or clarification instead of mutating state."""

    def __init__(self, preview) -> None:
        self.preview = preview
        super().__init__(preview.detail)


class EncounterPermissionError(EncounterError):
    """Raised when a controller attempts to act for an actor it does not own."""


class EncounterOwnershipError(EncounterError):
    """Raised when encounter actor-to-controller bindings are missing or invalid."""


class UnknownEncounterCommandError(EncounterError):
    """Raised when an encounter slash command cannot be parsed deterministically."""


class MonsterRuntimeError(Exception):
    """Base error for deterministic monster pipeline failures."""


class MonsterValidationError(MonsterRuntimeError):
    """Raised when a monster pipeline request is invalid for the current policy or catalog."""


class UnknownMonsterCommandError(MonsterRuntimeError):
    """Raised when a monster slash command cannot be parsed deterministically."""
