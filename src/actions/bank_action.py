import logging

from src.action import Action

logger = logging.getLogger(__name__)


class GetBankItemQuantity(Action):
    """The bank is account-wide, not per-character, and this is a plain
    data-bucket GET - no cooldown, no character state to update from the
    response. Returns the quantity of item_code currently in the bank."""

    def __init__(self, item_code: str):
        self.name = "GetBankItemQuantityAction"
        self.item_code: str = item_code

        super().__init__(name=self.name)

    async def execute(self, character=None) -> int:
        logger.debug(f"Checking bank for {self.item_code}")
        response = await self.client.get("/my/bank/items", params={"item_code": self.item_code})
        for item in response.get("data", []):
            if item.get("code") == self.item_code:
                return item.get("quantity", 0)
        return 0
