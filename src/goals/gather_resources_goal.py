from __future__ import annotations

from dataclasses import dataclass, field
import logging

from src.goal import Goal
from src.character import Character
from src.constants import BANK_LOCATION, WORKSHOP_LOCATIONS
from src.inventory import Inventory
from src.location import Location
from src.recipes import Recipe
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.craft_task import CraftTask
from src.tasks.deposit_task import DepositTask
from src.tasks.gather_task import GatherTask
from src.tasks.resolve_recipe_task import ResolveRecipeTask
from src.tasks.travel_task import ensure_at
from src.tasks.withdraw_material_task import WithdrawMaterialTask
from src.goals.bank_errand import next_bank_task
from src.goals.deposit_errand import DepositErrand
from src.goals.tool_equip_helper import ToolEquipHelper

logger = logging.getLogger(__name__)

_UNRESOLVED = object()  # sentinel: "haven't looked up the recipe yet"

_STAGE_CLEAR = "clear"
_STAGE_ACQUIRE = "acquire"
_STAGE_CRAFT = "craft"
_STAGE_BANK = "bank"


@dataclass
class _CraftCycle:
    """One craft cycle's mutable state (CLEAR -> ACQUIRE -> CRAFT -> BANK) -
    grouped so a fresh cycle resets in one call instead of touching three
    separately-named flags by hand."""

    stage: str = _STAGE_CLEAR
    acquire_targets: dict[str, int] | None = None
    tried_bank_withdrawal: set[str] = field(default_factory=set)
    rechecked_before_craft: bool = False

    def start_acquiring(self) -> None:
        self.stage = _STAGE_ACQUIRE
        self.acquire_targets = None
        self.tried_bank_withdrawal = set()


class GatherResourcesGoal(Goal):
    """Ensure at least `quantity` of item_code exists, counting BOTH what
    the character currently carries and what's already in the bank - a
    deposit doesn't reset progress the way counting inventory alone would
    (that used to be this goal's documented limitation for any quantity
    bigger than one inventory load; counting the bank too fixes it).

    Two modes, auto-detected from the game's own item data on the first
    tick (via ResolveRecipeTask - no need to tell the goal which mode to
    use, or resolve anything yourself before constructing it):

    - item_code has no crafting recipe: it's gathered directly at
      `location` (mining, woodcutting, fishing, ... - anything that's
      just one gather action).
    - item_code has a crafting recipe: it's crafted instead, as an
      explicit four-stage cycle so materials and the crafted result are
      never confused with "ready to bank" mid-cycle (see the CLEAR/ACQUIRE/
      CRAFT/BANK stages below):

        1. CLEAR - deposit anything that isn't a recipe material (the
           crafted result from last cycle, or unrelated junk), so "how
           much fits" is computed against a clean baseline. Leftover
           material (e.g. a few units left over because gathering yields
           don't divide evenly into batches) is deliberately *not*
           deposited here - it stays in inventory and counts directly
           toward next cycle's need, rather than getting deposited and
           then immediately withdrawn again for no reason.
        2. ACQUIRE - top up each material to as much as fits (leaving a
           little headroom for the crafted result, and accounting for
           whatever's already carried over) or as much as still needed to
           reach `quantity`, whichever is smaller - from the bank first
           (see WithdrawMaterialTask - a stockpile someone already
           gathered gets used before anyone goes out gathering more),
           then gathered at material_locations for any shortfall.
        3. CRAFT - craft everything acquired in one go, at the recipe's
           workshop (craft_location, or looked up from WORKSHOP_LOCATIONS
           by the recipe's skill).
        4. BANK - deposit the crafted result (materials excluded again, in
           case nothing got crafted), then start over at CLEAR.

        goal = GatherResourcesGoal(
            item_code="small_health_potion",
            quantity=300,
            material_locations={"sunflower": Location(2, 2)},
        )

      Bank stock is rechecked once more right before committing to a
      craft (cheap - a cooldown-free data lookup) - stock may already
      have hit the target from someone else's deposit while materials
      were being gathered.

    Since the mode isn't known until that first lookup, whether you need
    to pass `location` or `material_locations` depends on what item_code
    turns out to be - pass whichever is actually relevant; if it turns out
    to need the other one, the goal logs an error and gives up rather than
    getting stuck.

    Trade-off worth knowing (crafting mode only): if a recipe needs
    multiple materials, ACQUIRE sizes them all off the same "batches that
    fit" number, so a lopsided recipe (one material much bulkier than the
    other) can under-use the inventory a bit. Not incorrect, just
    occasionally conservative; fine for the common single- or
    few-material low-tier recipes this was built for.
    """

    MIN_FREE_SPACE = 5
    RESERVED_SPACE_FOR_OUTPUT = 5

    _STAGE_CLEAR = _STAGE_CLEAR
    _STAGE_ACQUIRE = _STAGE_ACQUIRE
    _STAGE_CRAFT = _STAGE_CRAFT
    _STAGE_BANK = _STAGE_BANK

    def __init__(
        self,
        item_code: str,
        quantity: int,
        location: Location | None = None,
        material_locations: dict[str, Location] | None = None,
        craft_location: Location | None = None,
        cycle_batches: int | None = None,
        tool_item_code: str | None = None,
        tool_slot: str = "weapon",
        tool_min_level: int = 1,
    ):
        super().__init__(f"Gather {quantity} {item_code}")
        self.item_code = item_code
        self.quantity = quantity
        self.location = location
        self.material_locations = material_locations or {}
        self.craft_location = craft_location
        self.cycle_batches = cycle_batches  # optional cap on batches/cycle; None = as many as fit/needed

        self._tool = ToolEquipHelper(tool_item_code, tool_slot, tool_min_level) if tool_item_code else None
        self._deposit = DepositErrand(self.MIN_FREE_SPACE)
        self._gather_errands = [self._deposit, self._tool] if self._tool else [self._deposit]

        self.recipe: Recipe | None = _UNRESOLVED
        self._bank_stock: int | None = None
        self._gave_up = False

        self._craft = _CraftCycle()

    def next_task(self, character: Character):
        if self._gave_up:
            return None

        if self.recipe is _UNRESOLVED:
            return ResolveRecipeTask(self.item_code, self._set_recipe)

        if self.recipe is not None and not self._prepare_craft_mode(character):
            return None
        if self.recipe is None and self.location is None:
            logger.error(
                f"{self.item_code} has no crafting recipe and no gather location was given "
                f"for {character.name} - giving up on this goal"
            )
            self._gave_up = True
            return None

        if self._bank_stock is None:
            return CheckBankStockTask(self.item_code, self._set_bank_stock)

        inventory = character.inventory
        total_owned = inventory.get_item_count(self.item_code) + self._bank_stock
        if total_owned >= self.quantity:
            logger.info(
                f"{character.name} has {total_owned}x {self.item_code} (inventory + bank) - goal complete"
            )
            self.done = True
            return None

        if self.recipe is None:
            return self._next_gather_task(character, inventory)
        return self._next_craft_task(character, inventory)

    def _prepare_craft_mode(self, character: Character) -> bool:
        """Runs once the recipe is known to be real: checks the skill
        level requirement and fills in craft_location/validates
        material_locations - deferred to here since none of this was
        knowable before the recipe was resolved. Returns False (and gives
        up) if something's unworkable."""
        skill_level = character.data.get(f"{self.recipe.skill}_level", 0)
        if skill_level < self.recipe.skill_level:
            logger.error(
                f"{character.name}'s {self.recipe.skill} level ({skill_level}) is below the "
                f"{self.recipe.skill_level} required to craft {self.item_code} - giving up on this goal"
            )
            self._gave_up = True
            return False

        if self.craft_location is None:
            self.craft_location = WORKSHOP_LOCATIONS.get(self.recipe.skill)
        if self.craft_location is None:
            logger.error(
                f"no known workshop location for skill {self.recipe.skill!r} - giving up on this goal"
            )
            self._gave_up = True
            return False

        missing = set(self.recipe.materials) - set(self.material_locations)
        if missing:
            logger.error(
                f"no gather location given for materials {sorted(missing)} needed to craft "
                f"{self.item_code} - giving up on this goal"
            )
            self._gave_up = True
            return False

        return True

    def _next_gather_task(self, character: Character, inventory: Inventory):
        bank_task = next_bank_task(character, self._gather_errands)
        if bank_task is not None:
            if isinstance(bank_task, DepositTask):
                self._bank_stock = None  # stock is about to change - recheck next cycle
            return bank_task

        travel = ensure_at(character, self.location)
        if travel is not None:
            logger.info(f"Traveling to location ({self.location.x}, {self.location.y}) for {character.name}")
            return travel

        logger.info(f"{character.name} gathers {self.item_code} at location ({self.location.x}, {self.location.y})")
        return GatherTask()

    def _next_craft_task(self, character: Character, inventory: Inventory):
        if self._craft.stage == self._STAGE_CLEAR:
            return self._do_clear(character, inventory)
        if self._craft.stage == self._STAGE_ACQUIRE:
            task = self._do_acquire(character, inventory)
            if task is not None:
                return task
            # every material is at its target - move on to crafting
            self._craft.stage = self._STAGE_CRAFT
            self._craft.rechecked_before_craft = False
        if self._craft.stage == self._STAGE_CRAFT:
            return self._do_craft(character, inventory)
        return self._do_bank(character)

    def _do_clear(self, character: Character, inventory: Inventory):
        """Deposit anything that isn't a recipe material before starting a
        fresh acquire/craft cycle - materials themselves are deliberately
        left alone (see _do_bank) so leftover scraps from gather-yield
        granularity carry straight into next cycle's need instead of
        bouncing through the bank for no reason. If there's nothing but
        leftover material to deal with, skip the bank trip entirely."""
        if self._has_depositable_items(inventory):
            travel = ensure_at(character, BANK_LOCATION)
            if travel is not None:
                logger.info(f"Heading to bank to start a clean cycle for {character.name}")
                return travel
            logger.info(f"Depositing at bank for {character.name}")
            self._bank_stock = None
            return DepositTask(all=True, exclude=set(self.material_locations))

        self._craft.start_acquiring()
        return self._do_acquire(character, inventory)

    def _has_depositable_items(self, inventory: Inventory) -> bool:
        material_codes = set(self.material_locations)
        return any(
            slot.get("quantity", 0) > 0 and slot.get("code") not in material_codes
            for slot in inventory.slots
        )

    def _do_acquire(self, character: Character, inventory: Inventory):
        """Returns the next task needed to top up materials, or None once
        every material has reached this cycle's target (or the inventory
        has filled up before getting there - the server's actual gather
        yield doesn't always match our own free-space math exactly, so
        trust its rejection over retrying the same doomed gather forever)."""
        if self._craft.acquire_targets is None:
            self._craft.acquire_targets = self._compute_acquire_targets(character, inventory)

        for material_code, location in self.material_locations.items():
            have = inventory.get_item_count(material_code)
            target = self._craft.acquire_targets.get(material_code, 0)
            if have >= target:
                continue

            if inventory.get_free_space() <= 0:
                logger.warning(
                    f"{character.name}'s inventory filled up before reaching this cycle's "
                    f"{material_code} target - proceeding with what's on hand"
                )
                break

            if material_code not in self._craft.tried_bank_withdrawal:
                travel = ensure_at(character, BANK_LOCATION)
                if travel is not None:
                    logger.info(f"Heading to bank to check for {material_code} for {character.name}")
                    return travel
                self._craft.tried_bank_withdrawal.add(material_code)
                return WithdrawMaterialTask(material_code, target - have)

            if self._tool is not None:
                tool_task = next_bank_task(character, [self._tool])
                if tool_task is not None:
                    return tool_task
                # not needed, or the bank has none - gather without it

            travel = ensure_at(character, location)
            if travel is not None:
                logger.info(f"Gathering {material_code} for {character.name}")
                return travel
            return GatherTask()

        return None

    def _do_craft(self, character: Character, inventory: Inventory):
        if not self._craft.rechecked_before_craft:
            # One more fresh look before committing - stock may already
            # have hit the target from someone else's deposit while
            # materials were being gathered.
            self._craft.rechecked_before_craft = True
            self._bank_stock = None
            return CheckBankStockTask(self.item_code, self._set_bank_stock)

        batches = self._craftable_batches(inventory)
        if batches > 0:
            travel = ensure_at(character, self.craft_location)
            if travel is not None:
                return travel
            self._craft.stage = self._STAGE_BANK
            return CraftTask(self.item_code, batches)

        # Nothing craftable (shouldn't normally happen given ACQUIRE just
        # topped materials up) - bank whatever's here rather than getting
        # stuck, and start a fresh cycle.
        self._craft.stage = self._STAGE_BANK
        return self._do_bank(character)

    def _do_bank(self, character: Character):
        travel = ensure_at(character, BANK_LOCATION)
        if travel is not None:
            logger.info(f"Heading to bank to deposit the crafted result for {character.name}")
            return travel
        logger.info(f"Depositing at bank for {character.name}")
        self._bank_stock = None
        self._craft.stage = self._STAGE_CLEAR
        return DepositTask(all=True, exclude=set(self.material_locations))

    def _compute_acquire_targets(self, character: Character, inventory: Inventory) -> dict[str, int]:
        """How many of each material to acquire this cycle: as many
        batches as fit - leaving some headroom for the crafted result, and
        counting whatever material is already carried over from last
        cycle as space already "spent" rather than space we still need to
        find - capped at however many batches are actually still needed
        to reach `quantity`, and capped again by cycle_batches if the
        caller set an explicit limit."""
        material_qty_per_batch_total = sum(self.recipe.materials.values())
        already_held = sum(inventory.get_item_count(m) for m in self.recipe.materials)
        usable_space = max(
            inventory.get_free_space() + already_held - self.RESERVED_SPACE_FOR_OUTPUT, 0
        )
        max_batches_by_space = (
            usable_space // material_qty_per_batch_total if material_qty_per_batch_total else 0
        )

        total_owned = inventory.get_item_count(self.item_code) + (self._bank_stock or 0)
        remaining = max(self.quantity - total_owned, 1)
        batches_needed = -(-remaining // self.recipe.yield_quantity)  # ceil division

        batches = min(max_batches_by_space, batches_needed)
        if self.cycle_batches is not None:
            batches = min(batches, self.cycle_batches)
        batches = max(batches, 1)

        logger.debug(
            f"{character.name} will acquire {batches} batch(es) this cycle "
            f"(fits: {max_batches_by_space}, needed: {batches_needed})"
        )
        return {material_code: qty * batches for material_code, qty in self.recipe.materials.items()}

    def progress_text(self, character: Character) -> str | None:
        if self.recipe is _UNRESOLVED:
            return None
        inventory_count = character.inventory.get_item_count(self.item_code)
        if self._bank_stock is None:
            return f"{inventory_count}+?/{self.quantity} {self.item_code}"
        return f"{inventory_count + self._bank_stock}/{self.quantity} {self.item_code}"

    def _set_recipe(self, recipe: Recipe | None) -> None:
        self.recipe = recipe

    def _set_bank_stock(self, quantity: int) -> None:
        self._bank_stock = quantity

    def _craftable_batches(self, inventory: Inventory) -> int:
        if not self.recipe.materials:
            return 0
        return min(
            inventory.get_item_count(material_code) // quantity_per_batch
            for material_code, quantity_per_batch in self.recipe.materials.items()
        )
