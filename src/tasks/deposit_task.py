from src.inventory import Inventory
from src.task import Task
from src.character import Character
from src.actions.deposit_action import DepositAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import INSUFFICIENT_QUANTITY, CONTENT_NOT_FOUND
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class DepositTask(Task):

    def __init__(
        self,
        all: bool = False,
        item_code: str = None,
        quantity: int = None,
        exclude: set[str] | None = None,
    ):
        super().__init__("DepositTask")
        self.all: bool = all
        self.item_code: str = item_code
        self.quantity: int = quantity
        self.exclude: set[str] = exclude or set()

    async def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        item_code, quantity = self._pick_item_to_deposit(character)
        if item_code is None:
            logger.info(f"No items to deposit for {character.name}")
            self.done = True
            return

        try:
            await DepositAction(item_code=item_code, quantity=quantity).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == INSUFFICIENT_QUANTITY:
                logger.info(f"{character.name} has no items to deposit")
                self.done = True
                return

            if e.status_code == CONTENT_NOT_FOUND:
                logger.info(f"{character.name} has no bank access")
                await character.refresh()
                self.done = True
                EVENT_LOG.record(character.name, "deposit failed: no bank access")
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, f"deposited {quantity}x {item_code}")

    def _pick_item_to_deposit(self, character: Character) -> tuple[str | None, int | None]:
        if not self.all:
            return self.item_code, self.quantity

        inventory: Inventory = character.inventory
        for slot in inventory.slots:
            if slot.get("quantity", 0) > 0 and slot.get("code") not in self.exclude:
                return slot.get("code"), slot.get("quantity")
        return None, None
