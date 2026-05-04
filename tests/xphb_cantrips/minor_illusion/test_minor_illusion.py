from __future__ import annotations

import unittest

from session_server.bootstrap import build_default_encounter_session
from shared_types.capabilities import IllusionInteractionKind, IllusionModality, IllusionTemplateId
from shared_types.encounter_models import IllusionObserverStatus
from shared_types.encounter_intents import ResolveIllusionInteractionIntent
from shared_types.encounter_models import RuntimeSpellState
from tests.test_encounter_kernel import LOCAL_MIRROR_BASE_URL


class MinorIllusionCantripTests(unittest.TestCase):
    def _build_session(self):
        session = build_default_encounter_session(base_url=LOCAL_MIRROR_BASE_URL)
        spell_record = next(record for record in session.runtime_services.encounter_catalog.spells.values() if record.name == 'Minor Illusion' and record.source == 'XPHB')
        session.state.actors['player-1'].spells['minor-illusion'] = RuntimeSpellState(
            option_id='minor-illusion',
            name=spell_record.name,
            source=spell_record.source,
            action_cost=spell_record.action_cost,
            range_ft=spell_record.range_ft,
            remaining_uses=None,
            level=spell_record.level,
            casting_time_seconds=spell_record.casting_time_seconds,
            perceptibility=spell_record.perceptibility,
            can_cast_as_ritual=spell_record.can_cast_as_ritual,
            ritual_additional_cast_seconds=spell_record.ritual_additional_cast_seconds,
            effect_type=spell_record.effect_type,
            max_uses=None,
            concentration=spell_record.concentration,
            capability=spell_record.capability,
            runtime_support=spell_record.runtime_support,
        )
        return session

    def test_minor_illusion_visual_door_can_be_studied_and_pierced(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        session.state, _ = session.command_interface.execute(
            session.state,
            f'/cast player-1 minor-illusion {player.position.x} {player.position.y} --template minor_visual_door --label Door --description Painted door',
        )
        illusion_id = next(iter(session.state.illusions))
        illusion = session.state.illusions[illusion_id]
        self.assertEqual(illusion.definition.template_id, IllusionTemplateId.MINOR_VISUAL_DOOR)
        self.assertEqual(illusion.definition.modality, IllusionModality.VISUAL)
        session.command_interface.kernel.dispatch(
            session.state,
            ResolveIllusionInteractionIntent(actor_id='player-1', illusion_id=illusion_id, interaction_kind=IllusionInteractionKind.STUDY_SUCCESS),
        )
        self.assertEqual(session.state.illusions[illusion_id].observer_states['player-1'].status, IllusionObserverStatus.PIERCED)

    def test_minor_illusion_can_create_a_sound_source(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        session.state, _ = session.command_interface.execute(
            session.state,
            f'/cast player-1 minor-illusion {player.position.x} {player.position.y} --template minor_sound_source --label Whisper --description Whispering behind the wagon',
        )
        illusion = next(iter(session.state.illusions.values()))
        self.assertEqual(illusion.definition.template_id, IllusionTemplateId.MINOR_SOUND_SOURCE)
        self.assertEqual(illusion.definition.modality, IllusionModality.AUDITORY)

    def test_minor_illusion_recast_replaces_previous_illusion(self) -> None:
        session = self._build_session()
        player = session.state.actors['player-1']
        session.state, _ = session.command_interface.execute(
            session.state,
            f'/cast player-1 minor-illusion {player.position.x} {player.position.y} --template minor_visual_object --label Crate --description Wooden crate',
        )
        session.state, _ = session.command_interface.execute(
            session.state,
            f'/cast player-1 minor-illusion {player.position.x + 1} {player.position.y} --template minor_visual_sign_or_sigil --label Sigil --description Blue sigil',
        )
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Minor Illusion'), 1)
        self.assertEqual(len(session.state.illusions), 1)
        illusion = next(iter(session.state.illusions.values()))
        self.assertEqual(illusion.definition.display_name, 'Sigil')


if __name__ == '__main__':
    unittest.main()
