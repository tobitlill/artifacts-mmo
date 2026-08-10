from src.task import Task
from src.character import Character
from src.actions.bank_action import GetBankItemQuantity
from src.actions.deposit_action import DepositAction
from src.actions.equip_action import EquipAction
from src.actions.unequip_action import UnequipAction
from src.actions.withdraw_action import WithdrawAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import INVENTORY_FULL, INSUFFICIENT_QUANTITY, CONTENT_NOT_FOUND
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)

_UNSET = object()  # sentinel: "haven't looked up what was equipped before yet"


class EquipToolTask(Task):
    """Make sure item_code is equipped in slot - swapping out whatever's
    there first (unequip, then deposit it) if it's something else - the
    same withdraw-then-equip shape as RestockUtilityTask, extended to
    handle an already-occupied, non-stackable slot (tools/weapons, always
    quantity 1, unlike RestockUtilityTask's stackable potions).

    Assumes it's only ticked while at the bank - same assumption
    RestockUtilityTask and WithdrawMaterialTask make; the calling goal is
    responsible for traveling there first.

    Safe to call whenever the right tool isn't equipped: no-ops (marks
    itself done without any API calls) if the character is below
    min_level or the bank has none of item_code, so gathering/fighting can
    proceed without the tool rather than getting stuck ("equip it if
    possible").
    """

    def __init__(self, item_code: str, slot: str = "weapon", min_level: int = 1):
        super().__init__("EquipToolTask")
        self.item_code: str = item_code
        self.slot: str = slot
        self.min_level: int = min_level

        self._old_code: str | None | object = _UNSET
        self._unequipped: bool = False
        self._deposited_old: bool = False
        self._bank_checked: bool = False
        self._withdrawn: bool = False

    async def tick(self, character: Character):
        if character.data.get("level", 0) < self.min_level:
            self.done = True
            return

        if character.data.get(f"{self.slot}_slot") == self.item_code:
            logger.debug(f"{character.name} already has {self.item_code} equipped in {self.slot}")
            self.done = True
            return

        if self._old_code is _UNSET:
            # Cached now, before unequipping clears it locally - this is
            # the only chance to learn what needs depositing afterward.
            self._old_code = character.data.get(f"{self.slot}_slot") or None

        if self.is_on_cooldown(character):
            return

        try:
            if self._old_code is not None and not self._unequipped:
                await UnequipAction(self.slot).execute(character)
                self._unequipped = True
                return

            if self._old_code is not None and not self._deposited_old:
                await DepositAction(item_code=self._old_code, quantity=1).execute(character)
                self._deposited_old = True
                return

            if not self._bank_checked:
                available = await GetBankItemQuantity(self.item_code).execute(character)
                if available <= 0:
                    logger.info(f"No {self.item_code} in the bank for {character.name}")
                    self.done = True
                    return

                # Withdrawing moves the tool bank -> inventory before it can
                # be equipped, so it needs inventory room too.
                if character.inventory.get_free_space() <= 0:
                    logger.info(f"No inventory space to withdraw {self.item_code} for {character.name} right now")
                    self.done = True
                    return
                self._bank_checked = True

            if not self._withdrawn:
                await WithdrawAction(self.item_code, 1).execute(character)
                self._withdrawn = True
                return

            await EquipAction(self.item_code, self.slot, 1).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == INVENTORY_FULL:
                logger.warning(f"{character.name}'s inventory is full - can't equip {self.item_code} right now")
                EVENT_LOG.record(character.name, "inventory full, skipping tool swap for now")
                character.inventory.mark_full()
                self.done = True
                return
            if e.status_code == INSUFFICIENT_QUANTITY:
                # Multiple characters share one bank and tick concurrently -
                # the availability check above can be stale by the time the
                # withdrawal actually posts. Skip the swap this visit rather
                # than retrying the same now-unavailable item forever.
                logger.warning(
                    f"{character.name} couldn't equip {self.item_code} after all - "
                    f"bank stock changed since the check"
                )
                EVENT_LOG.record(character.name, f"bank ran out of {self.item_code} before tool swap")
                self.done = True
                return
            if e.status_code == CONTENT_NOT_FOUND:
                logger.warning(f"{character.name} isn't at the bank after all - resyncing state")
                EVENT_LOG.record(character.name, "lost track of the bank, resyncing")
                await character.refresh()
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, f"equipped {self.item_code} in {self.slot}")
