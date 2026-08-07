from __future__ import annotations
import logging

from src.actions.character_action import GetCharacter
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character

logger = logging.getLogger(__name__)


class Inventory:
    def __init__(self, character: Character):
        self.character: Character = character
        self.slots: list[dict] = []
        self.max_items: int = 0
        self._forced_full: bool = False

    async def update_inventory(self) -> None:
        """Force a full re-fetch. Prefer update_from_character_data(), which
        is fed by every action response - this should only be needed for the
        initial sync or a suspected-stale recovery."""
        logger.debug(f"Updating inventory for character {self.character.name}")
        character_data = await GetCharacter().execute(character=self.character)
        self.update_from_character_data(character_data)

    def update_from_character_data(self, data: dict) -> None:
        self.slots = data.get("inventory", [])
        self.max_items = data.get("inventory_max_items", 0)
        # Any authoritative update supersedes the forced-full override below.
        self._forced_full = False

    def mark_full(self) -> None:
        """A gather/fight can drop more combined loot than we had free
        space for even when our own quantity-sum looked safe beforehand -
        the server then rejects the whole action with 497. That tells us
        definitively there's no room, which our own count might still
        disagree with (e.g. free space was 6, but that one fight's combined
        loot needed 8). Trust the server over our heuristic until the next
        authoritative update (deposit/refresh) corrects it."""
        self._forced_full = True

    def get_item_count(self, item_code: str) -> int:
        item_count = 0
        for slot in self.slots:
            if slot.get("code") == item_code:
                item_count += slot.get("quantity", 0)
        return item_count

    def get_free_space(self) -> int:
        if self._forced_full:
            return 0
        item_count = sum(slot.get("quantity", 0) for slot in self.slots)
        return self.max_items - item_count
