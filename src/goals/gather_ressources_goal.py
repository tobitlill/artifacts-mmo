from __future__ import annotations

from src.goal import Goal
from src.character import Character
from src.location import Location
from src.tasks.travel_task import TravelTask
from src.tasks.gather_task import GatherTask
from src.tasks.deposit_task import DepositTask
import logging

from src.task import Task

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GatherResourcesGoal(Goal):

    def __init__(
        self, location: Location, item_code: str, quantity: int = 100
    ) -> Task | None:
        super().__init__(f"Gather {quantity} {item_code}")
        self.location: Location = location
        self.item_code: str = item_code
        self.quantity: int = quantity

    def next_task(self, character: Character):
        inventory = character.get_inventory()

        # are we done?
        if inventory.get_item_count(self.item_code) >= self.quantity:
            logger.info(f"Goal completed for {character.name}")
            self.done = True
            return None

        # do we have enough space in the inventory?
        if inventory.get_free_space() < 100:
            if character.position == Location(4, 1):
                logger.info(f"Depositing items at bank for {character.name}")
                return DepositTask(all=True)
            else:
                logger.info(
                    f"Inventory is full for {character.name}, traveling to bank"
                )
                return TravelTask(Location(4, 1))

        # do we need to travel to the location?
        if character.position == self.location:
            # we are at the location, gather resources
            logger.info(
                f"{character.name} gathers {self.item_code} at location ({self.location.x}, {self.location.y})"
            )
            return GatherTask()
        else:
            # we are not at the location, travel there
            logger.info(
                f"Traveling to location ({self.location.x}, {self.location.y}) for {character.name}"
            )
            return TravelTask(self.location)
