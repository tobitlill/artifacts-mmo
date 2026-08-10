import logging

from src.action import Action
from src.character import Character

logger = logging.getLogger(__name__)


class UnequipAction(Action):
    def __init__(self, slot: str, quantity: int = 1):
        self.name = "UnequipAction"
        self.slot: str = slot
        self.quantity: int = quantity

        super().__init__(name=self.name)

    async def execute(self, character: Character):
        logger.info(f"{character.name} unequips {self.quantity}x from {self.slot}")
        response = await self.client.post(
            f"/my/{character.name}/action/unequip",
            [{"slot": self.slot, "quantity": self.quantity}],
        )

        self.apply_response_to_character(character, response)
        return response
