from src.task import Task
from src.character import Character
from src.actions.fight_action import FightAction
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import INVENTORY_FULL, CONTENT_NOT_FOUND
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


class FightTask(Task):

    def __init__(self, monster: str):
        super().__init__("FightTask")
        self.monster = monster

    async def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        try:
            await FightAction(self.monster).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == INVENTORY_FULL:
                # A single fight can drop several loot items at once - our
                # free-space check before the fight can pass and the fight
                # can still overflow capacity. The server's rejection is
                # the authoritative signal; trust it over our own count so
                # the goal is forced to the bank next tick instead of
                # retrying this same fight forever.
                logger.warning(f"{character.name}'s inventory is full - heading to bank")
                EVENT_LOG.record(character.name, "inventory full, heading to bank")
                await character.refresh()
                character.inventory.mark_full()
                self.done = True
                return
            if e.status_code == CONTENT_NOT_FOUND:
                # Losing a fight can send the character back to their
                # respawn point with HP reduced to near-zero - a whole
                # separate location/HP change our local state doesn't know
                # about yet. Re-sync from the API rather than retrying the
                # same fight forever; the goal will re-plan (heal/travel)
                # next tick from the now-current state.
                logger.warning(
                    f"{character.name} couldn't find {self.monster} here - resyncing state"
                )
                EVENT_LOG.record(character.name, f"lost track of {self.monster}, resyncing")
                await character.refresh()
                self.done = True
                return
            raise

        self.done = True
        EVENT_LOG.record(character.name, f"fought {self.monster}")
