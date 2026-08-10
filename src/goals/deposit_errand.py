from __future__ import annotations

from src.character import Character
from src.goals.bank_errand import BankErrand
from src.task import Task
from src.tasks.deposit_task import DepositTask


class DepositErrand(BankErrand):
    """Deposit loot once free inventory space drops below a trigger.
    Unconditionally worth a trip when needed - no bank-stock precheck."""

    def __init__(self, free_space_trigger: int, exclude: set[str] | None = None):
        self.free_space_trigger = free_space_trigger
        self.exclude = exclude

    def is_needed(self, character: Character) -> bool:
        return character.inventory.get_free_space() < self.free_space_trigger

    def act(self, character: Character) -> Task:
        return DepositTask(all=True, exclude=self.exclude)
