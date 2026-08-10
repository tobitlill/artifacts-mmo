from __future__ import annotations

from src.goal import Goal
from src.character import Character
from src.goals.bank_errand import next_bank_task
from src.goals.deposit_errand import DepositErrand
from src.goals.potion_errand import PotionErrand
from src.goals.tool_equip_helper import ToolEquipHelper
from src.location import Location
from src.tasks.fight_task import FightTask
from src.tasks.heal_task import HealTask
from src.tasks.travel_task import ensure_at


class EndlessFightGoal(Goal):
    """Fight a specific monster forever (to level it up), resting when HP
    drops too low and periodically running bank errands (depositing loot,
    restocking a potion, swapping a weapon) - never marks itself done
    (next_task() never returns None), so it doubles as a good fallback goal.

    A utility potion like small_health_potion heals automatically *during*
    a fight once equipped - the game does that server-side, we never call
    anything for it mid-fight. That only works while the equipped slot
    still holds some, though: if it runs dry, that safety net is gone and
    a single fight (which can resolve several rounds in one action) can
    crash HP before our between-fights HEAL_BELOW_HP_PERCENT check ever
    gets a chance to react - see PotionErrand.

    Bank errands (deposit/tool/potion) are handled by next_bank_task() in
    priority order: deposit first (frees the most space, and withdrawing
    a tool/potion needs room too), then tool, then potion - see
    src/goals/bank_errand.py for how a new errand type would plug in.
    """

    HEAL_BELOW_HP_PERCENT = 60
    INVENTORY_FREE_SPACE_TRIGGER = 5

    def __init__(
        self,
        monster: str,
        location: Location,
        potion_item_code: str = "small_health_potion",
        potion_slot: str = "utility1",
        potion_min_level: int = 5,
        max_potions: int = 100,
        tool_item_code: str | None = None,
        tool_slot: str = "weapon",
        tool_min_level: int = 1,
    ):
        super().__init__("Endless Fighting")
        self.monster = monster
        self.location = location

        self._tool = ToolEquipHelper(tool_item_code, tool_slot, tool_min_level) if tool_item_code else None
        self._potions = PotionErrand(potion_item_code, potion_slot, max_potions, potion_min_level)
        self._deposit = DepositErrand(self.INVENTORY_FREE_SPACE_TRIGGER)

    def next_task(self, character: Character):
        if character.hp_percent < self.HEAL_BELOW_HP_PERCENT:
            return HealTask()

        errands = [self._deposit, self._tool, self._potions] if self._tool else [self._deposit, self._potions]
        bank_task = next_bank_task(character, errands)
        if bank_task is not None:
            return bank_task

        travel = ensure_at(character, self.location)
        if travel is not None:
            return travel

        return FightTask(self.monster)
