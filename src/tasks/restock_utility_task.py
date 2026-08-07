from src.task import Task
from src.character import Character
from src.actions.bank_action import GetBankItemQuantity
from src.actions.equip_action import EquipAction
from src.actions.withdraw_action import WithdrawAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class RestockUtilityTask(Task):
    """Top up a utility slot from the bank: withdraw up to max_quantity of
    item_code (capped by what's actually in the bank) and equip it.

    Safe to call on every bank visit - it no-ops (marks itself done without
    any API calls) if the character is below min_level, the bank has none
    of the item, or the slot already holds max_quantity of it.

    Spans multiple ticks because the bank check doesn't cost a cooldown but
    the withdraw and equip actions each do - they can't both fire in the
    same tick.
    """

    def __init__(self, item_code: str, slot: str, max_quantity: int = 100, min_level: int = 1):
        super().__init__("RestockUtilityTask")
        self.item_code: str = item_code
        self.slot: str = slot
        self.max_quantity: int = max_quantity
        self.min_level: int = min_level
        self._quantity_to_withdraw: int | None = None
        self._withdrawn: bool = False

    async def tick(self, character: Character):
        if character.data.get("level", 0) < self.min_level:
            self.done = True
            return

        if self._already_stocked(character):
            logger.debug(f"{character.name} already has {self.max_quantity}x {self.item_code} in {self.slot}")
            self.done = True
            return

        if self._quantity_to_withdraw is None:
            available = await GetBankItemQuantity(self.item_code).execute(character)
            if available <= 0:
                logger.info(f"No {self.item_code} in the bank for {character.name}")
                self.done = True
                return

            # Withdrawing moves items bank -> inventory before they can be
            # equipped, so it needs inventory room too - never ask for more
            # than actually fits, even if the caller expected the inventory
            # to already be empty by this point.
            free_space = character.get_inventory().get_free_space()
            quantity = min(available, self.max_quantity, free_space)
            if quantity <= 0:
                logger.info(f"No inventory space to withdraw {self.item_code} for {character.name} right now")
                self.done = True
                return
            self._quantity_to_withdraw = quantity

        if self.is_on_cooldown(character):
            return

        try:
            if not self._withdrawn:
                await WithdrawAction(self.item_code, self._quantity_to_withdraw).execute(character)
                self._withdrawn = True
                return

            await EquipAction(self.item_code, self.slot, self._quantity_to_withdraw).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == 497:
                logger.warning(f"{character.name}'s inventory is full - can't restock {self.item_code} right now")
                EVENT_LOG.record(character.name, "inventory full, skipping potion restock for now")
                character.inventory.mark_full()
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(
            character.name, f"equipped {self._quantity_to_withdraw}x {self.item_code} in {self.slot}"
        )

    def _already_stocked(self, character: Character) -> bool:
        for slot_name in ("utility1", "utility2"):
            if character.data.get(f"{slot_name}_slot") != self.item_code:
                continue
            if character.data.get(f"{slot_name}_slot_quantity", 0) >= self.max_quantity:
                return True
        return False
