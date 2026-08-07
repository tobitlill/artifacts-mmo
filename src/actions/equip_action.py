import logging

from src.action import Action
from src.character import Character

logger = logging.getLogger(__name__)


class EquipAction(Action):
    def __init__(self, item_code: str, slot: str, quantity: int = 1):
        self.name = "EquipAction"
        self.item_code: str = item_code
        self.slot: str = slot
        self.quantity: int = quantity

        super().__init__(name=self.name)

    async def execute(self, character: Character):
        logger.info(f"{character.name} equips {self.quantity}x {self.item_code} to {self.slot}")
        response = await self.client.post(
            f"/my/{character.name}/action/equip",
            [{"code": self.item_code, "slot": self.slot, "quantity": self.quantity}],
        )

        self.apply_response_to_character(character, response)
        return response
