import logging

from src.action import Action
from src.character import Character

logger = logging.getLogger(__name__)


class WithdrawAction(Action):
    def __init__(self, item_code: str, quantity: int = 1):
        self.name = "WithdrawAction"
        self.item_code: str = item_code
        self.quantity: int = quantity

        super().__init__(name=self.name)

    async def execute(self, character: Character):
        logger.info(f"{character.name} withdraws {self.quantity}x {self.item_code} from the bank")
        response = await self.client.post(
            f"/my/{character.name}/action/bank/withdraw/item",
            [{"code": self.item_code, "quantity": self.quantity}],
        )

        self.apply_response_to_character(character, response)
        return response
