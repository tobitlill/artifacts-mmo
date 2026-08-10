from __future__ import annotations

from src.character import Character
from src.goals.bank_errand import BankErrand
from src.task import Task
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.equip_tool_task import EquipToolTask


class ToolEquipHelper(BankErrand):
    """Make sure the right tool/weapon is equipped before gathering or
    fighting - a BankErrand that checks the bank's stock (a cooldown-free,
    account-wide lookup) before committing to a trip, then hands back the
    EquipToolTask that does the swap once at the bank.

    Gives up gracefully (precheck() returns False) if the bank turns out
    to have none of it: the caller proceeds without the tool rather than
    getting stuck circling back to the bank forever.
    """

    def __init__(self, item_code: str, slot: str = "weapon", min_level: int = 1):
        self.item_code = item_code
        self.slot = slot
        self.min_level = min_level
        self._bank_stock: int | None = None

    def is_equipped(self, character: Character) -> bool:
        return character.data.get(f"{self.slot}_slot") == self.item_code

    def is_needed(self, character: Character) -> bool:
        if character.data.get("level", 0) < self.min_level:
            return False  # couldn't equip it anyway - no point banking for this
        return not self.is_equipped(character)

    def precheck(self, character: Character) -> Task | bool | None:
        if self._bank_stock is None:
            return CheckBankStockTask(self.item_code, self._set_bank_stock)
        stock = self._bank_stock
        self._bank_stock = None  # single-use - re-verify fresh next time
        return None if stock > 0 else False

    def act(self, character: Character) -> Task:
        return EquipToolTask(self.item_code, self.slot, self.min_level)

    def _set_bank_stock(self, quantity: int) -> None:
        self._bank_stock = quantity
