from src.action import Action
from src.character import Character
from src.constants import BANK_LOCATION
from src.goals.endless_fighting_goal import EndlessFightGoal
from src.location import Location
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.deposit_task import DepositTask
from src.tasks.equip_tool_task import EquipToolTask
from src.tasks.fight_task import FightTask
from src.tasks.heal_task import HealTask
from src.tasks.restock_utility_task import RestockUtilityTask
from src.tasks.travel_task import TravelTask

from conftest import FakeClient, run_async


def _char(client, name="A", level=8, potion_quantity=50):
    """Defaults to a character with potions already equipped, so tests
    that aren't specifically about the potion-restock trigger keep
    exercising plain fight/heal/deposit behavior instead of tripping the
    new "out of potions" bank detour."""
    client.state[name]["level"] = level
    if potion_quantity > 0:
        client.state[name]["utility1_slot"] = "small_health_potion"
        client.state[name]["utility1_slot_quantity"] = potion_quantity
    char = Character(name)
    run_async(char.refresh())
    return char


def test_heals_when_hp_below_50_percent():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.data["hp"] = 40  # 40% of 100

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)

    assert isinstance(task, HealTask)


def test_travels_then_fights_when_healthy_and_not_at_location():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == Location(5, 5)

    char.position = Location(5, 5)
    task = goal.next_task(char)
    assert isinstance(task, FightTask)
    assert task.monster == "chicken"


def test_goal_never_completes():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    char.position = Location(5, 5)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    for _ in range(10):
        assert goal.next_task(char) is not None
    assert goal.done is False


def test_bank_routine_deposits_first_then_restocks():
    """Deposit must happen before restocking - withdrawing potions needs
    inventory room too, and the character usually arrives at the bank with
    the inventory nearly full of combat loot (see the Hugo incident)."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8, potion_quantity=0)  # out of potions too, needs both
    client.bank["small_health_potion"] = 100
    # force low free space so the bank routine triggers
    char.inventory.slots = [{"code": "chicken_feather", "quantity": 20}]
    char.inventory.max_items = 20

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))

    # not at bank yet -> travel there
    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION

    char.position = BANK_LOCATION

    # at bank, inventory still low on space -> deposit first
    task = goal.next_task(char)
    assert isinstance(task, DepositTask)

    # simulate the deposit freeing up space
    char.inventory.slots = []

    # now that there's room, first visit -> restock potions
    task = goal.next_task(char)
    assert isinstance(task, RestockUtilityTask)
    assert task.item_code == "small_health_potion"
    assert task.min_level == 5

    # simulate the restock task completing
    task.done = True

    # same visit, already restocked -> head back out to fight
    task = goal.next_task(char)
    assert isinstance(task, FightTask) or isinstance(task, TravelTask)


def test_recovers_from_fight_loss_relocation_instead_of_looping_forever():
    """End-to-end regression test for the Hugo incident: a fight loss
    relocates the character and drops HP server-side; the next fight
    attempt fails with 598. The goal must recover - resync, heal, travel
    back - rather than the bot retrying the same failing fight forever."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    char.position = Location(5, 5)  # standing at the fight location already

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)
    assert isinstance(task, FightTask)

    # Simulate the loss: server relocated the character and cut HP, before
    # our local state learns about it.
    client.state["A"]["x"] = 0
    client.state["A"]["y"] = 0
    client.state["A"]["hp"] = 1
    client.fail_next_action_with_598("A")

    run_async(task.tick(char))  # must not raise
    assert task.done is True
    assert char.position == Location(0, 0)
    assert char.hp == 1

    # Goal must now notice the critical HP and heal rather than fight again.
    next_task = goal.next_task(char)
    assert isinstance(next_task, HealTask)


def test_recovers_from_loot_overflow_instead_of_looping_forever():
    """End-to-end regression test for the Hugo '106/110 but inventory full'
    incident: free space looks sufficient by our own quantity-sum, a fight
    still overflows capacity (497), and the goal must route to the bank on
    the very next decision instead of fighting again against the same
    stale-looking free-space count."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    char.position = Location(5, 5)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "raw_chicken", "quantity": 100}], "inventory_max_items": 110}
    )
    assert char.inventory.get_free_space() == 10  # looks safely above the trigger

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)
    assert isinstance(task, FightTask)

    client.fail_next_action_with_497("A")
    run_async(task.tick(char))  # must not raise
    assert task.done is True

    next_task = goal.next_task(char)
    assert isinstance(next_task, TravelTask)
    assert next_task.target_location == BANK_LOCATION


def test_running_out_of_potions_triggers_a_bank_trip_even_with_free_inventory_space():
    """Regression test for the tib0t incident: a character who's simply
    burned through their equipped potions (inventory otherwise nowhere
    near full) must still be routed to the bank to restock - not left to
    keep fighting unprotected until a bad fight nearly kills them."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8, potion_quantity=0)
    client.bank["small_health_potion"] = 100
    char.position = Location(5, 5)  # already at the fight spot, healthy, room to spare

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)

    # checks the bank's potion stock first (no travel needed for that)
    # before deciding it's worth the trip
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION


def test_skips_the_bank_trip_entirely_when_it_has_no_potions():
    """The whole point of the pre-check: don't walk to the bank only to
    find it empty too - just keep fighting instead."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8, potion_quantity=0)
    # client.bank has no small_health_potion at all
    char.position = Location(5, 5)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, FightTask)
    assert not any(c[0] == "POST" and c[1].endswith("/action/move") for c in client.calls)


def test_full_potion_slot_does_not_trigger_a_bank_trip():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8, potion_quantity=50)
    char.position = Location(5, 5)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)

    assert isinstance(task, FightTask)


def test_out_of_potions_leads_to_a_restock_task_once_at_the_bank():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8, potion_quantity=0)
    client.bank["small_health_potion"] = 100
    char.position = BANK_LOCATION

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)

    assert isinstance(task, RestockUtilityTask)
    assert task.item_code == "small_health_potion"


def test_missing_weapon_checks_bank_stock_then_travels():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    client.bank["wooden_sword"] = 5
    char.position = Location(5, 5)  # already at the fight spot, healthy, room to spare

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5), tool_item_code="wooden_sword")
    task = goal.next_task(char)

    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, TravelTask)
    assert task.target_location == BANK_LOCATION


def test_skips_the_bank_trip_for_a_weapon_the_bank_does_not_have():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    # client.bank has no wooden_sword at all
    char.position = Location(5, 5)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5), tool_item_code="wooden_sword")
    task = goal.next_task(char)
    assert isinstance(task, CheckBankStockTask)
    run_async(task.tick(char))

    task = goal.next_task(char)
    assert isinstance(task, FightTask)


def test_equips_weapon_once_at_the_bank():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    client.bank["wooden_sword"] = 5
    char.position = BANK_LOCATION

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5), tool_item_code="wooden_sword")
    task = goal.next_task(char)

    assert isinstance(task, EquipToolTask)
    assert task.item_code == "wooden_sword"


def test_deposit_runs_before_weapon_swap_when_both_are_needed():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=8)
    client.bank["wooden_sword"] = 5
    char.inventory.slots = [{"code": "chicken_feather", "quantity": 20}]
    char.inventory.max_items = 20
    char.position = BANK_LOCATION

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5), tool_item_code="wooden_sword")
    task = goal.next_task(char)
    assert isinstance(task, DepositTask)


def test_already_wielding_the_right_weapon_skips_the_swap_entirely():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["weapon_slot"] = "wooden_sword"
    client.state["A"]["weapon_slot_quantity"] = 1
    char = _char(client, level=8)
    char.position = Location(5, 5)

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5), tool_item_code="wooden_sword")
    task = goal.next_task(char)

    assert isinstance(task, FightTask)


def test_below_potion_min_level_never_triggers_a_potion_bank_trip():
    """A character who couldn't equip the potion anyway shouldn't be sent
    to the bank for it - the goal pre-filters by level itself now, rather
    than relying solely on RestockUtilityTask's own no-op (still covered
    separately in test_bank.py)."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, level=1, potion_quantity=0)
    client.bank["small_health_potion"] = 100

    goal = EndlessFightGoal(monster="chicken", location=Location(5, 5))
    task = goal.next_task(char)

    assert isinstance(task, TravelTask)
    assert task.target_location == Location(5, 5)
    assert not any(c[0] == "GET" and c[1] == "/my/bank/items" for c in client.calls)
