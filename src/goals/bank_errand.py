from __future__ import annotations

from abc import ABC, abstractmethod

from src.character import Character
from src.constants import BANK_LOCATION
from src.task import Task
from src.tasks.travel_task import TravelTask


class BankErrand(ABC):
    """Something a goal may need to do at the bank (deposit loot, restock a
    consumable, swap a tool, ...), checked fresh on every next_task() call.
    Lets a goal register a plain ordered list of errands instead of hand-
    computing a boolean per errand and hand-ordering if-statements around
    them - adding a new kind of bank errand becomes "write one more small
    class", not "touch every goal's next_task()".
    """

    @abstractmethod
    def is_needed(self, character: Character) -> bool:
        """Cheap, local, side-effect-free check - safe to call every tick."""

    def precheck(self, character: Character) -> Task | bool | None:
        """Only called while away from the bank, for an errand whose
        is_needed() is True. Three possible outcomes:
        - a Task: run this now (e.g. a cooldown-free bank-stock lookup).
        - None: nothing to check - this errand is ready to travel for.
        - False: the check determined this errand isn't worth a trip
          after all (e.g. the bank has none of it) - skip it this round.
        Default (no precheck needed): None.
        """
        return None

    @abstractmethod
    def act(self, character: Character) -> Task:
        """The task to run once at the bank. Only called when is_needed()
        is True and character.position == BANK_LOCATION."""


def next_bank_task(character: Character, errands: list[BankErrand]) -> Task | None:
    """Drives an ordered list of bank errands: earlier errands take
    priority (e.g. depositing loot before restocking, so the restock has
    room to withdraw into). Returns None if nothing is currently needed -
    the caller should fall through to its normal (non-bank) task."""
    active = [errand for errand in errands if errand.is_needed(character)]
    if not active:
        return None

    if character.position != BANK_LOCATION:
        for errand in active:
            result = errand.precheck(character)
            if isinstance(result, Task):
                return result
            if result is None:
                # This errand alone already justifies the trip - no need
                # to spend a precheck call on any lower-priority errand.
                return TravelTask(BANK_LOCATION)
            # result is False: ruled out on its own - check the next one.
        return None

    return active[0].act(character)
