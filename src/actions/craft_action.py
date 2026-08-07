import logging

from src.action import Action

logger = logging.getLogger(__name__)


class CraftAction(Action):
    def __init__(self, item_code: str, quantity: int = 1):
        self.name = "CraftAction"
        self.item_code: str = item_code
        self.quantity: int = quantity

        super().__init__(name=self.name)

    async def execute(self, character):
        logger.info(f"{character.name} crafts {self.quantity}x {self.item_code}")
        response = await self.client.post(
            f"/my/{character.name}/action/crafting",
            {"code": self.item_code, "quantity": self.quantity},
        )

        self.apply_response_to_character(character, response)
        return response
