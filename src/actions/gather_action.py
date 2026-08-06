import logging

from src.action import Action
from src.api_client import ArtifactsAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GatherAction(Action):
    def __init__(self):
        self.name = "GatherAction"
        super().__init__(name=self.name)

    def execute(self, character):
        logger.info(f"{character.name} gathers resource")
        try:
            response = self.client.post(f"/my/{character.name}/action/gathering", {})
        except ArtifactsAPIError:
            raise

        self.apply_cooldown_from_payload(character, response)
        return response