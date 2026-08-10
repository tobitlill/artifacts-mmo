from src.task import Task
from src.character import Character
from src.actions.travel_action import TravelAction
from src.location import Location
from src.api_client import ArtifactsAPIError, CharacterInCooldownError
from src.artifacts_status_codes import ALREADY_THERE
from src.event_log import EVENT_LOG
import logging

logger = logging.getLogger(__name__)


def ensure_at(character: Character, location: Location) -> Task | None:
    """A TravelTask if character isn't at location yet, else None - lets a
    goal write `task = ensure_at(character, X)\n if task: return task`
    instead of repeating the position-check-then-travel branch by hand."""
    if character.position != location:
        return TravelTask(location)
    return None


class TravelTask(Task):

    def __init__(self, target_location: Location):
        super().__init__("TravelTask")
        self.target_location: Location = target_location

    async def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        try:
            await TravelAction(self.target_location).execute(character)
        except CharacterInCooldownError as e:
            await self.apply_cooldown_error(character, e)
            return
        except ArtifactsAPIError as e:
            if e.status_code == ALREADY_THERE:
                logger.info(
                    f"{character.name} is already at the target location ({self.target_location.x}, {self.target_location.y})"
                )
                character.position = self.target_location
                self.done = True
                EVENT_LOG.record(character.name, f"already at ({self.target_location.x}, {self.target_location.y})")
                return
            raise

        if character.position == self.target_location:
            logger.info(
                f"{character.name} has arrived at the target location ({self.target_location.x}, {self.target_location.y})"
            )
            self.done = True
            EVENT_LOG.record(character.name, f"arrived at ({self.target_location.x}, {self.target_location.y})")
        else:
            logger.warning(
                f"{character.name} expected to reach ({self.target_location.x}, {self.target_location.y}) "
                f"but is at ({character.position.x}, {character.position.y})"
            )
