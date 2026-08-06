import logging

from src.action import Action
from src.api_client import ArtifactsAPIError
from src.location import Location
from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DepositAction(Action):
    def __init__(self, item_code: str = None, quantity: int = 1):
        self.name = "DepositAction"
        self.item_code: str = item_code
        self.quantity: int = quantity

        super().__init__(name=self.name)

    def execute(self, character: Character):
        logger.info(f"{character.name} deposits {self.quantity}x {self.item_code}")
        try:
            response = self.client.post(
                f"/my/{character.name}/action/bank/deposit/item",
                [{"code": self.item_code, "quantity": self.quantity}],
            )
        except ArtifactsAPIError:
            raise

        self.apply_cooldown_from_payload(character, response)
        return response
