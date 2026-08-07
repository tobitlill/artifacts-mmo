from src.task import Task
from src.character import Character
from src.actions.bank_action import GetBankItemQuantity
from src.actions.withdraw_action import WithdrawAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class WithdrawMaterialTask(Task):
    """Withdraw up to `quantity` of item_code from the bank straight into
    inventory - capped by what's actually in the bank and by current free
    inventory space, so it never asks for more than fits or exists.

    Marks itself done whether or not the full requested quantity was
    available - the caller (e.g. GatherResourcesGoal, sourcing craft
    materials from a bank stockpile before gathering fresh) is expected
    to gather any remaining shortfall itself.
    """

    def __init__(self, item_code: str, quantity: int):
        super().__init__("WithdrawMaterialTask")
        self.item_code = item_code
        self.requested_quantity = quantity
        self._quantity_to_withdraw: int | None = None

    async def tick(self, character: Character):
        if self._quantity_to_withdraw is None:
            available = await GetBankItemQuantity(self.item_code).execute(character)
            free_space = character.get_inventory().get_free_space()
            quantity = min(available, self.requested_quantity, free_space)
            if quantity <= 0:
                logger.debug(f"No {self.item_code} available in the bank for {character.name} right now")
                self.done = True
                return
            self._quantity_to_withdraw = quantity

        if self.is_on_cooldown(character):
            return

        try:
            await WithdrawAction(self.item_code, self._quantity_to_withdraw).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == 497:
                logger.warning(f"{character.name}'s inventory is full - can't withdraw {self.item_code} right now")
                EVENT_LOG.record(character.name, "inventory full, skipping material withdrawal for now")
                character.inventory.mark_full()
                self.done = True
                return
            if e.status_code == 598:
                # Should be prevented by the caller checking position
                # before returning this task - but if our local position
                # is stale for any reason, resync rather than crash.
                logger.warning(f"{character.name} isn't at the bank after all - resyncing state")
                EVENT_LOG.record(character.name, "lost track of the bank, resyncing")
                await character.refresh()
                self.done = True
                return
            if e.status_code == 478:
                # Multiple characters share one bank and tick concurrently -
                # the availability check above can be stale by the time this
                # withdrawal actually posts (someone else got there first).
                # Give up on this material for now rather than retrying the
                # same now-unavailable quantity forever.
                logger.warning(
                    f"{character.name} couldn't withdraw {self.item_code} after all - "
                    f"bank stock changed since the check"
                )
                EVENT_LOG.record(character.name, f"bank ran out of {self.item_code} before withdrawal")
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, f"withdrew {self._quantity_to_withdraw}x {self.item_code} from bank")
