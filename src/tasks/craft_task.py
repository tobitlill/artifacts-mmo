from src.task import Task
from src.character import Character
from src.actions.craft_action import CraftAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import INVENTORY_FULL, INSUFFICIENT_QUANTITY, SKILL_LEVEL_TOO_LOW
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class CraftTask(Task):

    def __init__(self, item_code: str, quantity: int = 1):
        super().__init__("CraftTask")
        self.item_code = item_code
        self.quantity = quantity

    async def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        try:
            await CraftAction(self.item_code, self.quantity).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == INVENTORY_FULL:
                # Same overflow case as fighting/gathering: trust the
                # server's rejection over our own free-space count.
                logger.warning(f"{character.name}'s inventory is full - can't craft right now")
                EVENT_LOG.record(character.name, "inventory full, heading to bank")
                await character.refresh()
                character.inventory.mark_full()
                self.done = True
                return
            if e.status_code in (INSUFFICIENT_QUANTITY, SKILL_LEVEL_TOO_LOW):
                # 478: not enough materials on hand; 493: skill level too
                # low. Both mean "can't craft this right now" - the goal
                # will re-plan (gather more, or otherwise reassess) rather
                # than retrying the exact same failing craft forever.
                logger.warning(f"{character.name} can't craft {self.item_code} right now ({e.status_code})")
                EVENT_LOG.record(character.name, f"craft failed ({e.status_code}), reassessing")
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, f"crafted {self.quantity}x {self.item_code}")
