from __future__ import annotations

from src.actions.character_action import GetCharacter
from src.inventory import Inventory
from src.location import Location
import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from src.goal import Goal

logger = logging.getLogger(__name__)


class Character:
    def __init__(
        self,
        name: str,
        goals: list[Goal] | None = None,
        fallback_goal_factory: Callable[[], Goal] | None = None,
    ):
        self.name = name
        self.goals = goals or []
        self.fallback_goal_factory = fallback_goal_factory
        self.position: Location = Location(0, 0)
        self._cooldown_until: datetime | None = None
        self.data: dict = {}
        self.inventory: Inventory = Inventory(self)

        self._consecutive_tick_failures = 0
        self._tick_backoff_until: datetime | None = None

    async def refresh(self) -> None:
        """Force a full re-sync from the API. Prefer letting actions update
        local state from their own responses; only call this for the
        initial sync or when local state is suspected to be stale."""
        logger.debug(f"Refreshing character {self.name}")
        data = await GetCharacter().execute(self)
        self.apply_character_payload(data)

    def apply_character_payload(self, data: dict) -> None:
        """Update local state from any character-shaped payload - either a
        full /my/characters record (refresh()) or the `character` object
        embedded in an action response - so we don't need an extra API
        call after every action just to learn our own new state."""
        if not data:
            return
        self.data = data
        self._update_position_from_data(data)
        self.set_cooldown_until(data.get("cooldown_expiration"))
        self.inventory.update_from_character_data(data)

    async def tick(self) -> None:
        self._advance_finished_goals()

        if not self.goals:
            if self.fallback_goal_factory is not None:
                logger.info(f"No goals left for {self.name}, assigning fallback goal")
                self.goals.append(self.fallback_goal_factory())
            else:
                logger.warning(f"No goal available for {self.name}")
                return

        logger.debug(f"Ticking goal {self.goals[0].name} for {self.name}")
        await self.goals[0].tick(self)

    def _advance_finished_goals(self) -> None:
        while self.goals and self.goals[0].done:
            finished = self.goals.pop(0)
            logger.info(f"Goal {finished.name} finished for {self.name}")

    def is_backing_off(self) -> bool:
        """True while skipping ticks after repeated failures (see
        record_tick_failure) - a permanently broken goal/task (bad
        item_code, an unhandled status code, ...) must not hammer the
        same doomed API call every second forever."""
        if self._tick_backoff_until is None:
            return False
        if self._tick_backoff_until <= datetime.now(timezone.utc):
            self._tick_backoff_until = None
            return False
        return True

    def record_tick_success(self) -> None:
        self._consecutive_tick_failures = 0
        self._tick_backoff_until = None

    def record_tick_failure(self) -> int:
        """Grows the backoff delay with each consecutive failure (capped
        at 60s) and returns it, so the caller can log/report it."""
        self._consecutive_tick_failures += 1
        delay = min(2**self._consecutive_tick_failures, 60)
        self._tick_backoff_until = datetime.now(timezone.utc) + timedelta(seconds=delay)
        return delay

    def set_cooldown_until(self, expiration: datetime | str | None) -> None:
        if expiration is None:
            self._cooldown_until = None
            return

        if isinstance(expiration, str):
            try:
                expiration = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
            except ValueError:
                logger.warning(f"Could not parse cooldown_expiration {expiration!r}")
                self._cooldown_until = None
                return

        self._cooldown_until = expiration

    def set_cooldown_seconds(self, duration_seconds: int) -> None:
        self.set_cooldown_until(datetime.now(timezone.utc) + timedelta(seconds=duration_seconds))

    @property
    def cooldown(self) -> int:
        """Seconds remaining on cooldown, computed live so it's always
        correct from anywhere - never a stale cached value."""
        if self._cooldown_until is None:
            return 0

        now_dt = datetime.now(timezone.utc)
        if self._cooldown_until <= now_dt:
            self._cooldown_until = None
            return 0

        # Round up, not down - a truncated 0.9s-remaining reading as "0"
        # would let is_on_cooldown() greenlight an action the server will
        # still reject.
        return max(0, math.ceil((self._cooldown_until - now_dt).total_seconds()))

    @property
    def cooldown_until(self) -> datetime | None:
        return self._cooldown_until

    @property
    def hp(self) -> int:
        return self.data.get("hp", 0)

    @property
    def max_hp(self) -> int:
        return self.data.get("max_hp", 0)

    @property
    def hp_percent(self) -> float:
        max_hp = self.max_hp
        if not max_hp:
            return 100.0
        return (self.hp / max_hp) * 100

    def _update_position_from_data(self, data: dict) -> None:
        x = data.get("x")
        y = data.get("y")
        if x is None or y is None:
            logger.warning(
                f"Character {self.name} is missing position data in refresh payload"
            )
            return
        self.position = Location(x, y)
