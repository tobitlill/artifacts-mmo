import logging

from src.action import Action
from src.api_client import ArtifactsAPIError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FightAction(Action):
    def __init__(self, monster: str):
        self.monster = monster

    def execute(self, character):
        logger.info(f"{character.name} fights against {self.monster}")
        try:
            response = self.client.post(f"/my/{character.name}/action/fight", {})
        except ArtifactsAPIError:
            raise

        self.apply_cooldown_from_payload(character, response)
        return response