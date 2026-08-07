import logging

from src.action import Action
from src.location import Location
from src.character import Character

logger = logging.getLogger(__name__)


class TravelAction(Action):
    def __init__(self, location: Location):
        self.location = location
        self.name = "TravelAction"
        super().__init__(name=self.name)

    async def execute(self, character: Character):
        logger.info(
            f"{character.name} travels to ({self.location.x}, {self.location.y})"
        )
        response = await self.client.post(
            f"/my/{character.name}/action/move",
            {"x": self.location.x, "y": self.location.y},
        )

        # Position/cooldown come from the response's own character data -
        # never assume the move landed where we asked it to.
        self.apply_response_to_character(character, response)
        return response
