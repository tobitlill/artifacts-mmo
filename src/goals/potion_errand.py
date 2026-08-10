from __future__ import annotations

from src.character import Character
from src.constants import BANK_LOCATION
from src.goals.bank_errand import BankErrand
from src.task import Task
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.restock_utility_task import RestockUtilityTask


class PotionErrand(BankErrand):
    """Restock a utility potion once the equipped slot runs dry - a
    BankErrand wrapping RestockUtilityTask, with the same bank-stock
    precheck as ToolEquipHelper (checked before traveling, since the
    bank's stock is a cooldown-free, account-wide lookup).

    Only attempts one restock per bank visit: if it comes back short (the
    bank ran out mid-withdrawal, a shared-bank race) rather than actually
    clearing is_needed(), retrying it every tick would spin at the bank
    forever - _given_up_this_visit gives up until the character leaves
    and comes back.
    """

    def __init__(self, item_code: str, slot: str, max_quantity: int, min_level: int):
        self.item_code = item_code
        self.slot = slot
        self.max_quantity = max_quantity
        self.min_level = min_level
        self._bank_stock: int | None = None
        self._given_up_this_visit = False

    def is_needed(self, character: Character) -> bool:
        if character.position != BANK_LOCATION:
            self._given_up_this_visit = False
        if self._given_up_this_visit:
            return False
        if character.data.get("level", 0) < self.min_level:
            return False  # couldn't equip it anyway - no point banking for this
        if character.data.get(f"{self.slot}_slot") != self.item_code:
            return True  # not equipped at all
        return character.data.get(f"{self.slot}_slot_quantity", 0) <= 0

    def precheck(self, character: Character) -> Task | bool | None:
        if self._bank_stock is None:
            return CheckBankStockTask(self.item_code, self._set_bank_stock)
        stock = self._bank_stock
        self._bank_stock = None  # single-use - re-verify fresh next time
        return None if stock > 0 else False

    def act(self, character: Character) -> Task:
        self._given_up_this_visit = True
        return RestockUtilityTask(
            item_code=self.item_code,
            slot=self.slot,
            max_quantity=self.max_quantity,
            min_level=self.min_level,
        )

    def _set_bank_stock(self, quantity: int) -> None:
        self._bank_stock = quantity
