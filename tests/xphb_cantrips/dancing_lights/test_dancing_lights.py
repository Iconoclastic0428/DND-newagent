from __future__ import annotations

import unittest

from shared_types.encounter_models import GridPosition
from shared_types.errors import EncounterValidationError
from tests.xphb_cantrips.support import EncounterCantripTestCase


class DancingLightsCantripTests(EncounterCantripTestCase):
    def test_cast_creates_clustered_dim_light_illusion(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Dancing Lights')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 dancing-lights 1 1 --form lights')
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Dancing Lights'), 1)
        self.assertEqual(len(session.state.persistent_areas), 1)
        area = next(iter(session.state.persistent_areas.values()))
        self.assertEqual(area.origin, GridPosition(1, 1, 0))
        self.assertEqual(len(area.origins), 4)
        illusion = next(iter(session.state.illusions.values()))
        self.assertIn('cluster of four torch-sized lights', illusion.definition.display_description.lower())

    def test_move_repositions_existing_lights_and_can_change_form(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Dancing Lights')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 dancing-lights 1 1 --form lights')
        session.state, _ = session.command_interface.execute(session.state, '/cast player-1 dancing-lights 2 1 --mode move --form humanoid')
        self.assertEqual(sum(1 for effect in session.state.active_effects.values() if effect.name == 'Dancing Lights'), 1)
        area = next(iter(session.state.persistent_areas.values()))
        self.assertEqual(area.origin, GridPosition(2, 1, 0))
        self.assertEqual(len(area.origins), 1)
        illusion = next(iter(session.state.illusions.values()))
        self.assertIn('humanoid', illusion.definition.display_description.lower())

    def test_move_requires_existing_lights(self) -> None:
        session = self.build_default_session()
        self.grant_spell(session, 'Dancing Lights')
        with self.assertRaisesRegex(EncounterValidationError, 'already active'):
            session.command_interface.execute(session.state, '/cast player-1 dancing-lights 2 1 --mode move --form lights')


if __name__ == '__main__':
    unittest.main()
