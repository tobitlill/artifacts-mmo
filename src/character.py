from __future__ import annotations

from src.actions.character_action import GetCharacter
from src.inventory import Inventory
from src.location import Location
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.goal import Goal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class Character:
    def __init__(self, name: str, goals: list[Goal] | None = None):
        self.name = name
        self.goals = goals or []
        self.position: Location = Location(0, 0)
        self.cooldown: int = 0
        self.cooldown_until: datetime | None = None
        self.data: dict = {}
        self.inventory: Inventory = Inventory(self)

    def refresh(self):
        logger.debug(f"Refreshing character {self.name}")
        data = GetCharacter().execute(self)
        self.data = data

        self._update_position_from_data(data)
        self._update_cooldown_from_data(data)
        self.inventory.update_inventory()

    def tick(self):
        if len(self.goals) > 0:
            logger.debug(f"Ticking goal {self.goals[0].name} for {self.name}")
            self.goals[0].tick(self)
        else:
            logger.warning(f"No goal available for {self.name}")
            return

    def get_inventory(self) -> Inventory:
        self.inventory.update_inventory()
        return self.inventory

    def set_cooldown(self, duration_seconds: int) -> None:
        now_dt = datetime.now(timezone.utc)
        self.cooldown_until = now_dt + timedelta(seconds=duration_seconds)
        self.cooldown = duration_seconds

    def _update_position_from_data(self, data: dict) -> None:
        x = data.get("x")
        y = data.get("y")
        if x is None or y is None:
            logger.warning(
                f"Character {self.name} is missing position data in refresh payload"
            )
            return
        self.position = Location(x, y)

    def _update_cooldown_from_data(self, data: dict) -> None:
        expiration = data.get("cooldown_expiration")
        if not expiration:
            self.cooldown = 0
            self.cooldown_until = None
            return

        try:
            expiration_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
            now_dt = datetime.now(timezone.utc)
            self.cooldown_until = expiration_dt
            self.cooldown = max(0, int((expiration_dt - now_dt).total_seconds()))
        except ValueError:
            logger.warning(f"Could not parse cooldown_expiration {expiration!r}")
            self.cooldown_until = None
            self.cooldown = 0

    def get_cooldown(self) -> int:
        if self.cooldown_until is None:
            return self.cooldown

        now_dt = datetime.now(timezone.utc)
        if self.cooldown_until <= now_dt:
            self.cooldown = 0
            self.cooldown_until = None
            return 0

        self.cooldown = max(0, int((self.cooldown_until - now_dt).total_seconds()))
        return self.cooldown
