from __future__ import annotations

from shared_types.encounter_intents import ContinueTimingIntent
from tests.xphb_cantrips.support import EncounterCantripTestCase


class EncounterLevel1SpellTestCase(EncounterCantripTestCase):
    def apply_spell_events(
        self,
        session,
        *,
        actor_id: str = 'player-1',
        spell_id: str,
        target_id: str | None = None,
        point=None,
        parameters: dict[str, str] | None = None,
    ) -> list[object]:
        actor = session.state.actors[actor_id]
        spell = actor.spells[spell_id]
        events = session.command_interface.kernel.effect_executor.execute_spell(
            session.state,
            actor=actor,
            spell=spell,
            target_id=target_id,
            point=point,
            parameters=parameters,
        )
        for event in events:
            session.state.event_log.append(event)
            session.command_interface.kernel._apply_event(session.state, event)
        return events

    def advance_existing_turn(self, session, actor_id: str) -> None:
        guard = 0
        while session.state.active_actor_id != actor_id:
            guard += 1
            if guard > 40:
                raise AssertionError(f'Could not advance to actor {actor_id}.')
            session.state, _ = session.command_interface.execute(session.state, f'/endturn {session.state.active_actor_id}')

    def resolve_pending_timing(self, session, *, actor_id: str) -> None:
        guard = 0
        while session.state.pending_timing_queue is not None:
            guard += 1
            if guard > 20:
                raise AssertionError('Could not resolve the pending timing queue.')
            session.state = session.command_interface.kernel.dispatch(
                session.state,
                ContinueTimingIntent(actor_id=actor_id),
            )

    def end_turn_and_resolve(self, session, actor_id: str) -> None:
        session.state, _ = session.command_interface.execute(session.state, f'/endturn {actor_id}')
        self.resolve_pending_timing(session, actor_id=actor_id)
