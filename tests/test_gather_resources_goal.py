from src.action import Action
from src.character import Character
from src.constants import BANK_LOCATION
from src.goals.gather_ressources_goal import GatherResourcesGoal
from src.location import Location
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.craft_task import CraftTask
from src.tasks.deposit_task import DepositTask
from src.tasks.gather_task import GatherTask
from src.tasks.resolve_recipe_task import ResolveRecipeTask
from src.tasks.travel_task import TravelTask
from src.tasks.withdraw_material_task import WithdrawMaterialTask

from conftest import FakeClient, run_async

SUNFLOWER_LOCATION = Location(2, 2)
ALCHEMY_LOCATION = Location(2, 3)


def _char(client, name="A", level=8, alchemy_level=8, inventory_max_items=50):
    client.state[name]["level"] = level
    client.state[name]["alchemy_level"] = alchemy_level
    client.state[name]["inventory_max_items"] = inventory_max_items
    char = Character(name)
    run_async(char.refresh())
    return char


def _resolve(goal, char):
    """Every goal's first next_task() call is always a ResolveRecipeTask -
    tick it so the goal knows whether item_code needs crafting."""
    task = goal.next_task(char)
    assert isinstance(task, ResolveRecipeTask)
    run_async(task.tick(char))


# ---------------------------------------------------------------------------
# Recipe auto-detection
# ---------------------------------------------------------------------------


def test_first_task_is_always_a_recipe_lookup():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="sunflower", quantity=10, location=SUNFLOWER_LOCATION)

    task = goal.next_task(char)
    assert isinstance(task, ResolveRecipeTask)


def test_gives_up_when_no_recipe_and_no_location_given():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="sunflower", quantity=10)  # no location, no recipe

    _resolve(goal, char)
    task = goal.next_task(char)

    assert task is None
    assert goal.done is False  # gave up, not completed


def test_gives_up_when_recipe_found_but_no_material_locations_given():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="small_health_potion", quantity=10)  # no material_locations

    _resolve(goal, char)
    task = goal.next_task(char)

    assert task is None
    assert goal.done is False


def test_craft_location_defaults_to_the_recipes_workshop():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(
        item_code="small_health_potion",
        quantity=10,
        material_locations={"sunflower": SUNFLOWER_LOCATION},
    )

    _resolve(goal, char)
    goal.next_task(char)  # runs _prepare_craft_mode, which fills in craft_location

    assert goal.craft_location == ALCHEMY_LOCATION


# ---------------------------------------------------------------------------
# Plain gather mode (item has no recipe)
# ---------------------------------------------------------------------------


def test_gather_mode_travels_then_gathers():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="sunflower", quantity=10, location=SUNFLOWER_LOCATION)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # bank-stock check (0)
    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == SUNFLOWER_LOCATION

    char.position = SUNFLOWER_LOCATION
    task = goal.next_task(char)
    assert isinstance(task, GatherTask)


def test_gather_mode_deposits_when_inventory_gets_low_on_space():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "sunflower", "quantity": 48}], "inventory_max_items": 50}
    )
    char.position = BANK_LOCATION
    goal = GatherResourcesGoal(item_code="sunflower", quantity=1000, location=SUNFLOWER_LOCATION)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))
    task = goal.next_task(char)
    assert isinstance(task, DepositTask)


# ---------------------------------------------------------------------------
# The key behavior: inventory + bank combined completion
# ---------------------------------------------------------------------------


def test_completion_counts_inventory_plus_bank_not_just_one_of_them():
    """This is the fix for the old "never completes past one inventory
    load" limitation: depositing must not reset progress."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 7
    char = _char(client)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "sunflower", "quantity": 3}], "inventory_max_items": 50}
    )
    goal = GatherResourcesGoal(item_code="sunflower", quantity=10, location=SUNFLOWER_LOCATION)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # bank-stock check -> 7
    task = goal.next_task(char)

    assert task is None
    assert goal.done is True  # 3 (inventory) + 7 (bank) == 10


def test_not_yet_done_when_inventory_plus_bank_is_short():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 7
    char = _char(client)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "sunflower", "quantity": 1}], "inventory_max_items": 50}
    )
    goal = GatherResourcesGoal(item_code="sunflower", quantity=10, location=SUNFLOWER_LOCATION)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))
    task = goal.next_task(char)

    assert task is not None
    assert goal.done is False  # 1 + 7 == 8, still short of 10


def test_depositing_does_not_reset_progress():
    """A full gather -> deposit -> gather cycle must accumulate toward the
    target rather than restart from zero after each deposit."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="sunflower", quantity=15, location=SUNFLOWER_LOCATION)

    for _ in range(100):
        task = goal.next_task(char)
        if task is None:
            break
        run_async(task.tick(char))
        while not task.done:
            run_async(task.tick(char))
            if char.cooldown > 0:
                client.expire_cooldown("A")
                char.set_cooldown_until(None)

    assert goal.done is True
    total = char.inventory.get_item_count("sunflower") + client.bank.get("sunflower", 0)
    assert total >= 15


# ---------------------------------------------------------------------------
# Craft mode (item has a recipe)
# ---------------------------------------------------------------------------


def _make_craft_goal(**overrides):
    kwargs = dict(
        item_code="small_health_potion",
        quantity=20,
        material_locations={"sunflower": SUNFLOWER_LOCATION},
        cycle_batches=5,
    )
    kwargs.update(overrides)
    return GatherResourcesGoal(**kwargs)


def test_gives_up_when_skill_level_is_too_low():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, alchemy_level=1)
    goal = _make_craft_goal()

    _resolve(goal, char)
    task = goal.next_task(char)

    assert task is None
    assert goal.done is False  # gave up, not "successfully completed"
    assert goal.next_task(char) is None


def test_withdraws_material_from_bank_instead_of_gathering():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 1500
    char = _char(client)  # at (0, 0) - nowhere near sunflower or the bank
    goal = _make_craft_goal(cycle_batches=5)  # needs 15 sunflower this cycle

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # potion bank-stock check (0)

    # must travel to the bank before attempting a withdrawal - regression
    # test for the Udo/Rolf incident (WithdrawAction raised 598 because the
    # goal never checked position first)
    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, WithdrawMaterialTask)
    assert task.item_code == "sunflower"

    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("sunflower") == 15
    assert client.bank["sunflower"] == 1485
    assert not any(c[0] == "POST" and c[1] == "/my/A/action/gathering" for c in client.calls)


def test_falls_back_to_gathering_for_shortfall_after_one_bank_attempt():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 5  # not enough for the full 15-sunflower cycle target
    char = _char(client)
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))

    task = goal.next_task(char)  # travel to bank first
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, WithdrawMaterialTask)
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("sunflower") == 5

    if char.cooldown > 0:
        client.expire_cooldown("A")
        char.set_cooldown_until(None)

    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == SUNFLOWER_LOCATION


def test_acquiring_a_full_cycle_of_materials_does_not_trigger_a_premature_deposit():
    """Regression test for the Udo/Rolf oscillation bug: withdrawing/
    gathering a full cycle's worth of material can leave very little free
    space - that must not be mistaken for "ready to bank", or the goal
    loops depositing and withdrawing the same material forever without
    ever reaching craft."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 1000
    char = _char(client, inventory_max_items=20)
    goal = _make_craft_goal(quantity=1000)  # no cycle_batches cap - sized by capacity

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # potion bank-stock check (0)

    task = goal.next_task(char)  # CLEAR: already empty -> straight to ACQUIRE -> travel to bank
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, WithdrawMaterialTask)
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    # Inventory is now full (or close to it) of sunflower...
    assert char.inventory.get_free_space() <= goal.RESERVED_SPACE_FOR_OUTPUT

    # ...but the very next decision must move on to CRAFT, not loop back
    # to depositing/withdrawing the same material again.
    task = goal.next_task(char)
    assert goal._craft_stage == goal._STAGE_CRAFT
    assert isinstance(task, CheckBankStockTask)  # the pre-craft recheck, not a deposit


def test_acquire_targets_respect_inventory_capacity_and_remaining_need():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, inventory_max_items=20)
    goal = _make_craft_goal(quantity=1000)
    _resolve(goal, char)

    targets = goal._compute_acquire_targets(char, char.inventory)

    # usable_space = 20 - RESERVED_SPACE_FOR_OUTPUT(5) = 15; 3 sunflower/batch -> 5 batches
    assert targets == {"sunflower": 15}


def test_acquire_targets_capped_by_remaining_need_not_just_capacity():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, inventory_max_items=200)  # plenty of room
    # yield_quantity=2 per batch, so 6 remaining needs ceil(6/2)=3 batches
    goal = _make_craft_goal(quantity=6)
    _resolve(goal, char)

    targets = goal._compute_acquire_targets(char, char.inventory)

    assert targets == {"sunflower": 9}  # 3 sunflower/batch x 3 batches


def _advance_to_craft_stage(goal, char, materials: dict, client=None):
    """Test helper: skip past CLEAR/ACQUIRE to exercise the CRAFT stage
    directly, with the given materials already sitting in inventory. Pass
    `client` too when the test will actually tick a CraftTask/DepositTask
    to completion - the fake server checks its own state's inventory, not
    the character object, so both need to agree."""
    inventory = {
        "inventory": [{"code": code, "quantity": qty} for code, qty in materials.items()],
        "inventory_max_items": 50,
    }
    char.inventory.update_from_character_data(inventory)
    if client is not None:
        client.state[char.name]["inventory"] = inventory["inventory"]
        client.state[char.name]["inventory_max_items"] = 50
    goal._craft_stage = goal._STAGE_CRAFT


def test_rechecks_bank_stock_once_more_before_committing_to_a_craft():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.position = ALCHEMY_LOCATION
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial potion bank-stock check (0)
    _advance_to_craft_stage(goal, char, {"sunflower": 15})

    task = goal.next_task(char)
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, CraftTask)


def test_skips_crafting_if_fresh_recheck_shows_target_already_met():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.position = ALCHEMY_LOCATION
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial check: 0 potions, insufficient
    _advance_to_craft_stage(goal, char, {"sunflower": 15})

    client.bank["small_health_potion"] = 20  # someone else stocked it in the meantime

    task = goal.next_task(char)
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert task is None
    assert goal.done is True
    assert not any(c[0] == "POST" and c[1] == "/my/A/action/crafting" for c in client.calls)


def test_craft_mode_deposits_freshly_crafted_goods_even_with_room_to_spare():
    """Unlike plain gather mode, craft mode still deposits as soon as it's
    carrying any of the crafted item - so it actually reaches the bank for
    other characters to use, rather than only being deposited once
    inventory happens to run low."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, inventory_max_items=200)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "small_health_potion", "quantity": 4}], "inventory_max_items": 200}
    )
    char.position = ALCHEMY_LOCATION
    goal = _make_craft_goal()

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial bank-stock check (0)
    task = goal.next_task(char)

    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION


def test_full_craft_cycle_gather_craft_deposit_recheck():
    """cycle_batches=5 yields 10 potions per craft (5 batches x yield 2) -
    quantity is set high enough that a single craft can't satisfy it, so
    the goal must actually deposit and run a second cycle."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = _make_craft_goal(cycle_batches=5, quantity=25)

    seen_types = []
    for _ in range(200):
        task = goal.next_task(char)
        if task is None:
            break
        seen_types.append(type(task).__name__)
        run_async(task.tick(char))
        while not task.done:
            run_async(task.tick(char))
            if char.cooldown > 0:
                client.expire_cooldown("A")
                char.set_cooldown_until(None)

    assert goal.done is True
    total = char.inventory.get_item_count("small_health_potion") + client.bank.get("small_health_potion", 0)
    assert total >= 25
    assert "ResolveRecipeTask" in seen_types
    assert "CheckBankStockTask" in seen_types


# ---------------------------------------------------------------------------
# Leftover-material carryover (regression: Udo withdrawing ore right before
# going mining, because leftover scraps got deposited and then immediately
# re-withdrawn for no reason)
# ---------------------------------------------------------------------------


def test_clear_stage_skips_bank_trip_when_only_leftover_material_remains():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "sunflower", "quantity": 2}], "inventory_max_items": 50}
    )
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial potion bank-stock check (0)

    # Only leftover sunflower (a recipe material) sits in inventory - CLEAR
    # must not deposit it, it should move straight to ACQUIRE.
    task = goal.next_task(char)
    assert not isinstance(task, DepositTask)
    assert goal._craft_stage == goal._STAGE_ACQUIRE

    # and the 2 already held count directly toward this cycle's target
    assert goal._acquire_targets == {"sunflower": 15}
    assert char.inventory.get_item_count("sunflower") == 2  # untouched, not deposited


def test_leftover_material_reduces_amount_withdrawn_from_bank():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 1000
    char = _char(client)
    inventory_data = {"inventory": [{"code": "sunflower", "quantity": 2}], "inventory_max_items": 50}
    char.inventory.update_from_character_data(inventory_data)
    client.state["A"]["inventory"] = inventory_data["inventory"]
    client.state["A"]["inventory_max_items"] = 50
    goal = _make_craft_goal(cycle_batches=5)  # target: 15 sunflower this cycle

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial potion bank-stock check (0)

    task = goal.next_task(char)  # straight to ACQUIRE, no deposit of the leftover
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, WithdrawMaterialTask)
    assert task.item_code == "sunflower"
    assert task.requested_quantity == 13  # 15 target - 2 already held, not the full 15

    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("sunflower") == 15
    assert client.bank["sunflower"] == 987


def test_bank_stage_leaves_leftover_material_out_of_the_deposit():
    """After crafting, BANK must deposit the crafted result but leave any
    leftover material (e.g. gather yields that didn't divide evenly into a
    batch) in inventory rather than sweeping it into the bank too."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.position = ALCHEMY_LOCATION
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial potion bank-stock check (0)
    _advance_to_craft_stage(goal, char, {"sunflower": 17}, client=client)  # 2 left over after a 15-sunflower batch

    task = goal.next_task(char)  # pre-craft recheck
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)  # CraftTask consumes 15 of the 17 sunflower
    assert isinstance(task, CraftTask)
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("sunflower") == 2
    assert goal._craft_stage == goal._STAGE_BANK

    char.position = BANK_LOCATION
    task = goal.next_task(char)
    assert isinstance(task, DepositTask)
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("small_health_potion") == 0  # crafted result deposited
    assert char.inventory.get_item_count("sunflower") == 2  # leftover material kept


def test_leftover_material_carries_over_without_a_pointless_bank_round_trip():
    """End-to-end regression for the Udo scenario: leftover ore from
    gather-yield overshoot must never be deposited and then immediately
    re-withdrawn - once it's in inventory it should just count toward the
    next cycle's acquire target."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.position = ALCHEMY_LOCATION
    client.state["A"]["x"], client.state["A"]["y"] = ALCHEMY_LOCATION.x, ALCHEMY_LOCATION.y
    goal = _make_craft_goal(cycle_batches=5)

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))
    _advance_to_craft_stage(goal, char, {"sunflower": 17}, client=client)

    task = goal.next_task(char)
    run_async(task.tick(char))  # recheck
    task = goal.next_task(char)  # craft
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    char.position = BANK_LOCATION
    client.state["A"]["x"], client.state["A"]["y"] = BANK_LOCATION.x, BANK_LOCATION.y
    task = goal.next_task(char)  # deposit crafted result (sunflower excluded)
    run_async(task.tick(char))
    while not task.done:
        run_async(task.tick(char))
        if char.cooldown > 0:
            client.expire_cooldown("A")
            char.set_cooldown_until(None)

    assert char.inventory.get_item_count("sunflower") == 2

    # Next cycle: CLEAR must not send the character back to the bank just
    # because 2 leftover sunflower are sitting in inventory. Character is
    # still (correctly) at the bank from the deposit above, so ACQUIRE can
    # go straight to a withdrawal check with no extra deposit round trip.
    task = goal.next_task(char)
    assert isinstance(task, CheckBankStockTask)  # potion stock recheck, deposit reset it
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert not isinstance(task, DepositTask)
    assert isinstance(task, WithdrawMaterialTask)
    assert task.requested_quantity == 13  # 15 target - 2 leftover already held


# ---------------------------------------------------------------------------
# ACQUIRE vs. a genuinely full inventory (regression: Rolf stuck retrying
# the same gather forever - the server's actual yield doesn't always match
# our own free-space math, and ACQUIRE never checked for that)
# ---------------------------------------------------------------------------


def test_acquire_stops_gathering_once_inventory_actually_fills_up():
    """A 497 from GatherAction mid-ACQUIRE must stop that material's
    top-up (not retry the exact same gather forever) and let the cycle
    move on to CRAFT with whatever's already on hand."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, inventory_max_items=200)
    goal = _make_craft_goal(quantity=1000)  # sized by capacity - many batches needed

    _resolve(goal, char)
    run_async(goal.next_task(char).tick(char))  # initial potion bank-stock check (0)

    task = goal.next_task(char)  # ACQUIRE: untried yet -> travel to bank to check stock
    assert isinstance(task, TravelTask)
    run_async(task.tick(char))

    task = goal.next_task(char)  # bank is empty -> no-op, marks tried and done
    assert isinstance(task, WithdrawMaterialTask)
    run_async(task.tick(char))

    char.position = SUNFLOWER_LOCATION
    client.fail_next_action_with_497("A")
    task = goal.next_task(char)
    assert isinstance(task, GatherTask)
    run_async(task.tick(char))  # 497 - must not raise
    assert task.done is True
    assert char.inventory.get_free_space() == 0

    # ACQUIRE must not retry the same gather now that the server says
    # there's no room left - it should give up on the target and move on.
    task = goal.next_task(char)
    assert not isinstance(task, GatherTask)
    assert goal._craft_stage == goal._STAGE_CRAFT

    # ...and only 13 more are needed to hit the 15-sunflower cycle target.
    assert goal._acquire_targets == {"sunflower": 15}


# ---------------------------------------------------------------------------
# progress_text
# ---------------------------------------------------------------------------


def test_progress_text_is_none_before_recipe_is_resolved():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    goal = GatherResourcesGoal(item_code="sunflower", quantity=20, location=SUNFLOWER_LOCATION)

    assert goal.progress_text(char) is None


def test_progress_text_gather_mode():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 4
    char = _char(client)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "sunflower", "quantity": 3}], "inventory_max_items": 50}
    )
    goal = GatherResourcesGoal(item_code="sunflower", quantity=20, location=SUNFLOWER_LOCATION)

    _resolve(goal, char)
    assert goal.progress_text(char) == "3+?/20 sunflower"
    run_async(goal.next_task(char).tick(char))
    assert goal.progress_text(char) == "7/20 sunflower"
