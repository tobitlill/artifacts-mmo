from __future__ import annotations

from typing import Callable

from src.task import Task
from src.character import Character
from src.actions.bank_action import GetBankItemQuantity


class CheckBankStockTask(Task):
    """A pure data lookup (no cooldown, no character mutation) that hands
    its result to a callback instead of storing it anywhere itself - lets
    a Goal's otherwise-synchronous next_task() incorporate live bank state
    (e.g. GatherResourcesGoal's completion check) without next_task()
    itself needing to be async."""

    def __init__(self, item_code: str, on_result: Callable[[int], None]):
        super().__init__("CheckBankStockTask")
        self.item_code = item_code
        self.on_result = on_result

    async def tick(self, character: Character):
        quantity = await GetBankItemQuantity(self.item_code).execute(character)
        self.on_result(quantity)
        self.done = True
