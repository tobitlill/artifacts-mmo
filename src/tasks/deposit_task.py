from src.inventory import Inventory
from src.task import Task
from src.character import Character
from src.actions.deposit_action import DepositAction
from src.location import Location
from src.api_client import ArtifactsAPIError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DepositTask(Task):

    def __init__(self, all: bool = False, item_code: str = None, quantity: int = None):
        super().__init__("DepositTask")
        self.all: bool = all
        self.item_code: str = item_code
        self.quantity: int = quantity

    def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        inventory: Inventory = character.get_inventory()
        slots = inventory.slots
        item_code = None
        quantity = None
        for slot in slots:
            if slot.get("quantity", 0) > 0:
                item_code = slot.get("code")
                quantity = slot.get("quantity")
                break
            
        if not self.all:
            item_code = self.item_code
            quantity = self.quantity

        if item_code is None:
            logger.info(f"No items to deposit for {character.name}")
            self.done = True
            return
        
        try:
            DepositAction(item_code=item_code, quantity=quantity).execute(character)
        except ArtifactsAPIError as e:
            if e.status_code == 478:
                logger.info(f"{character.name} has no items to deposit")
                self.done = True
                return

            if e.status_code == 598:
                logger.info(f"{character.name} has no bank access")
                self.done = True
                return
            raise e
