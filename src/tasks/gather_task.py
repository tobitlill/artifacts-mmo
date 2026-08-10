from src.task import Task
from src.character import Character
from src.actions.gather_action import GatherAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import INVENTORY_FULL, CONTENT_NOT_FOUND
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class GatherTask(Task):

    def __init__(self):
        super().__init__("GatherTask")

    async def tick(self, character: Character):
        if self.is_on_cooldown(character):
            return

        try:
            await GatherAction().execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == INVENTORY_FULL:
                # Same overflow case as FightTask: a gather can drop more
                # than our free-space check accounted for. Trust the
                # server's rejection over our own count.
                logger.warning(f"{character.name}'s inventory is full - heading to bank")
                EVENT_LOG.record(character.name, "inventory full, heading to bank")
                await character.refresh()
                character.inventory.mark_full()
                self.done = True
                return
            if e.status_code == CONTENT_NOT_FOUND:
                # Same class of issue as FightTask's 598 handling: our local
                # position/state doesn't match reality anymore. Resync
                # instead of retrying the same failing gather forever.
                logger.warning(f"{character.name} couldn't find a resource here - resyncing state")
                EVENT_LOG.record(character.name, "lost track of resource, resyncing")
                await character.refresh()
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, "gathered resource")
