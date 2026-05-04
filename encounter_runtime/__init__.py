from .control import EncounterControlResult, EncounterControlRuntime
from .kernel import EncounterKernel


def build_default_encounter_runtime(*, base_url: str | None = None):
    from .service import build_default_encounter_runtime as _build_default_encounter_runtime

    return _build_default_encounter_runtime(base_url=base_url)


def __getattr__(name: str):
    if name == 'EncounterRuntimeServices':
        from .service import EncounterRuntimeServices

        return EncounterRuntimeServices
    raise AttributeError(name)
