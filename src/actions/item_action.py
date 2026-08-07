import logging

from src.action import Action

logger = logging.getLogger(__name__)


class GetItemDetails(Action):
    """Static game data (recipe, level requirements, ...) - no cooldown,
    no character state to update from the response."""

    def __init__(self, item_code: str):
        self.name = "GetItemDetailsAction"
        self.item_code: str = item_code

        super().__init__(name=self.name)

    async def execute(self, character=None) -> dict:
        logger.debug(f"Looking up item details for {self.item_code}")
        response = await self.client.get(f"/items/{self.item_code}")
        return response.get("data", {})
