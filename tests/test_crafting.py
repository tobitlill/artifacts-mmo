from src.action import Action
from src.character import Character
from src.constants import WORKSHOP_LOCATIONS
from src.location import Location
from src.recipes import Recipe, resolve_recipe
from src.tasks.check_bank_stock_task import CheckBankStockTask
from src.tasks.craft_task import CraftTask

from conftest import FakeClient, run_async


def _char(client, name="A", level=8, alchemy_level=8, inventory=None, inventory_max_items=50):
    client.state[name]["level"] = level
    client.state[name]["alchemy_level"] = alchemy_level
    client.state[name]["inventory_max_items"] = inventory_max_items
    if inventory is not None:
        # Set on the fake server's ground truth, not the Character's local
        # cache directly - CraftAction's handler validates against this,
        # and refresh() below is what syncs it into the local cache.
        client.state[name]["inventory"] = inventory
    char = Character(name)
    run_async(char.refresh())
    return char


def test_resolve_recipe_parses_real_item_shape():
    client = FakeClient(["A"])
    Action.configure_client(client)

    recipe = run_async(resolve_recipe("small_health_potion"))

    assert recipe.item_code == "small_health_potion"
    assert recipe.skill == "alchemy"
    assert recipe.skill_level == 5
    assert recipe.materials == {"sunflower": 3}
    assert recipe.yield_quantity == 2


def test_resolve_recipe_raises_for_non_craftable_item():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.items["raw_rock"] = {"code": "raw_rock"}  # no craft field

    try:
        run_async(resolve_recipe("raw_rock"))
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_check_bank_stock_task_calls_back_with_quantity_and_costs_no_cooldown():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["small_health_potion"] = 42
    char = _char(client)

    results = []
    task = CheckBankStockTask("small_health_potion", results.append)
    run_async(task.tick(char))

    assert task.done is True
    assert results == [42]
    assert char.cooldown == 0


def test_craft_task_succeeds_and_updates_inventory():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, inventory=[{"code": "sunflower", "quantity": 30}])

    task = CraftTask("small_health_potion", 10)
    run_async(task.tick(char))

    assert task.done is True
    assert char.inventory.get_item_count("small_health_potion") == 20  # 10 batches x yield 2
    assert char.inventory.get_item_count("sunflower") == 0  # 10 batches x 3 consumed


def test_craft_task_handles_missing_materials():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)  # no sunflower in inventory

    task = CraftTask("small_health_potion", 10)
    run_async(task.tick(char))  # must not raise

    assert task.done is True


def test_craft_task_handles_insufficient_skill_level():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client, alchemy_level=1, inventory=[{"code": "sunflower", "quantity": 30}])

    task = CraftTask("small_health_potion", 10)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_item_count("small_health_potion") == 0


def test_craft_task_marks_inventory_full_on_497():
    client = FakeClient(["A"])
    Action.configure_client(client)
    # A recipe whose yield outnumbers what it consumes, so crafting it can
    # legitimately overflow a near-full inventory (small_health_potion's
    # 3-sunflower-for-2-potions recipe never would, since it shrinks the
    # total item count).
    client.items["bulk_test_item"] = {
        "code": "bulk_test_item",
        "craft": {"skill": "alchemy", "level": 1, "items": [{"code": "sunflower", "quantity": 1}], "quantity": 5},
    }
    char = _char(client, alchemy_level=1, inventory=[{"code": "sunflower", "quantity": 1}], inventory_max_items=3)

    task = CraftTask("bulk_test_item", 1)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0
    assert char.inventory.get_free_space() == 0


def test_workshop_locations_cover_the_alchemy_skill():
    assert "alchemy" in WORKSHOP_LOCATIONS
    assert isinstance(WORKSHOP_LOCATIONS["alchemy"], Location)
