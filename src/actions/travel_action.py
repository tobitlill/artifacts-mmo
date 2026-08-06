import logging

from src.action import Action
from src.api_client import ArtifactsAPIError
from src.location import Location
from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TravelAction(Action):
    def __init__(self, location: Location):
        self.location = location
        self.name = "TravelAction"
        super().__init__(name=self.name)

    def execute(self, character: Character):
        logger.info(
            f"{character.name} travels to ({self.location.x}, {self.location.y})"
        )
        try:
            response = self.client.post(
                f"/my/{character.name}/action/move",
                {"x": self.location.x, "y": self.location.y},
            )
        except Exception as e:
            raise

        character.position = self.location
        self.apply_cooldown_from_payload(character, response)
        return response
