from __future__ import annotations

import logging

from src.goal import Goal
from src.character import Character
from src.constants import BANK_LOCATION
from src.location import Location
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.deposit_task import DepositTask
from src.tasks.fight_task import FightTask
from src.tasks.heal_task import HealTask
from src.tasks.restock_utility_task import RestockUtilityTask
from src.tasks.travel_task import TravelTask

logger = logging.getLogger(__name__)


class EndlessFightGoal(Goal):
    """Fight a specific monster forever (to level it up), resting when HP
    drops too low and periodically banking loot - never marks itself done
    (next_task() never returns None), so it doubles as a good fallback goal.

    A utility potion like small_health_potion heals automatically *during*
    a fight once equipped - the game does that server-side, we never call
    anything for it mid-fight. That only works while the equipped slot
    still holds some, though: if it runs dry, that safety net is gone and
    a single fight (which can resolve several rounds in one action) can
    crash HP before our between-fights HEAL_BELOW_HP_PERCENT check ever
    gets a chance to react. So running out of potions triggers its own
    bank trip, independent of whether there's loot to deposit - not just
    a side effect of an inventory-full trip.

    At the bank, deposit runs before restock if both are needed:
    withdrawing potions needs inventory room too, and the character
    usually arrives with the inventory at least partly full of combat
    loot - restocking first would just fail with "inventory full" (497)
    instead of depositing.

    The bank's potion stock is account-wide and not location-bound (it's
    a plain data lookup, no cooldown), so when potions are the *only*
    reason to consider a bank trip, it's checked before traveling there -
    no point making the round trip just to find the bank empty too.
    """

    HEAL_BELOW_HP_PERCENT = 60
    INVENTORY_FREE_SPACE_TRIGGER = 5

    def __init__(
        self,
        monster: str,
        location: Location,
        potion_item_code: str = "small_health_potion",
        potion_slot: str = "utility1",
        potion_min_level: int = 5,
        max_potions: int = 100,
    ):
        super().__init__("Endless Fighting")
        self.monster = monster
        self.location = location
        self.potion_item_code = potion_item_code
        self.potion_slot = potion_slot
        self.potion_min_level = potion_min_level
        self.max_potions = max_potions
        self._restocked_this_visit = False
        self._bank_potion_stock: int | None = None

    def next_task(self, character: Character):
        if character.hp_percent < self.HEAL_BELOW_HP_PERCENT:
            return HealTask()

        inventory = character.get_inventory()
        needs_deposit = inventory.get_free_space() < self.INVENTORY_FREE_SPACE_TRIGGER
        needs_potions = self._out_of_potions(character)

        if needs_potions and not needs_deposit and character.position != BANK_LOCATION:
            # Potions are the only reason to consider a trip right now -
            # check the bank's stock first (no travel needed for that)
            # instead of walking all the way there just to find it empty.
            if self._bank_potion_stock is None:
                return CheckBankStockTask(self.potion_item_code, self._set_bank_potion_stock)
            if self._bank_potion_stock <= 0:
                logger.debug(
                    f"No {self.potion_item_code} in the bank for {character.name} - skipping the trip"
                )
                needs_potions = False
            self._bank_potion_stock = None  # single-use - re-verify fresh next time

        if needs_deposit or needs_potions:
            if character.position != BANK_LOCATION:
                logger.info(
                    f"Heading to bank for {character.name} "
                    f"(deposit={needs_deposit}, need potions={needs_potions})"
                )
                return TravelTask(BANK_LOCATION)

            if needs_deposit:
                logger.info(f"Depositing loot at bank for {character.name}")
                return DepositTask(all=True)

            if needs_potions and not self._restocked_this_visit:
                self._restocked_this_visit = True
                return RestockUtilityTask(
                    item_code=self.potion_item_code,
                    slot=self.potion_slot,
                    max_quantity=self.max_potions,
                    min_level=self.potion_min_level,
                )

        # leaving the bank (or never went) - re-arm for the next visit
        self._restocked_this_visit = False

        if character.position != self.location:
            return TravelTask(self.location)

        return FightTask(self.monster)

    def _set_bank_potion_stock(self, quantity: int) -> None:
        self._bank_potion_stock = quantity

    def _out_of_potions(self, character: Character) -> bool:
        if character.data.get("level", 0) < self.potion_min_level:
            return False  # couldn't equip them anyway - no point banking for this

        if character.data.get(f"{self.potion_slot}_slot") != self.potion_item_code:
            return True  # not equipped at all

        return character.data.get(f"{self.potion_slot}_slot_quantity", 0) <= 0
