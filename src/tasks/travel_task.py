from src.task import Task
from src.character import Character
from src.actions.travel_action import TravelAction
from src.location import Location
from src.api_client import ArtifactsAPIError
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TravelTask(Task):

    def __init__(self, target_location: Location):
        super().__init__("TravelTask")
        self.target_location: Location = target_location

    def tick(self, character: Character):

        if self.is_on_cooldown(character):
            return

        try:
            TravelAction(self.target_location).execute(character)
        except ArtifactsAPIError as e:
            if e.status_code == 490:
                logger.info(
                    f"{character.name} is already at the target location ({self.target_location.x}, {self.target_location.y})"
                )
                self.done = True
                return
            raise e

        character.refresh()
        if character.position == self.target_location:
            logger.info(
                f"{character.name} has arrived at the target location ({self.target_location.x}, {self.target_location.y})"
            )
            character.position = self.target_location
            self.done = True
