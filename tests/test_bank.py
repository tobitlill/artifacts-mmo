from src.action import Action
from src.actions.bank_action import GetBankItemQuantity
from src.actions.equip_action import EquipAction
from src.actions.withdraw_action import WithdrawAction
from src.character import Character
from src.tasks.restock_utility_task import RestockUtilityTask

from conftest import FakeClient, run_async


def _tick_until_done(char, task, client, max_ticks=20):
    for _ in range(max_ticks):
        run_async(task.tick(char))
        if task.done:
            return True
        if char.cooldown > 0:
            client.expire_cooldown(char.name)
            char.set_cooldown_until(None)
    return False


def test_get_bank_item_quantity_returns_zero_when_absent():
    client = FakeClient(["A"])
    Action.configure_client(client)
    assert run_async(GetBankItemQuantity("small_health_potion").execute()) == 0


def test_get_bank_item_quantity_returns_real_amount():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["small_health_potion"] = 23
    assert run_async(GetBankItemQuantity("small_health_potion").execute()) == 23


def test_withdraw_action_moves_items_from_bank_to_inventory():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["small_health_potion"] = 50
    char = Character("A")
    run_async(char.refresh())

    run_async(WithdrawAction("small_health_potion", 30).execute(char))

    assert client.bank["small_health_potion"] == 20
    assert char.inventory.get_item_count("small_health_potion") == 30


def test_equip_action_sets_utility_slot():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    char.inventory.slots.append({"code": "small_health_potion", "quantity": 30})

    run_async(EquipAction("small_health_potion", "utility1", 30).execute(char))

    assert char.data["utility1_slot"] == "small_health_potion"
    assert char.data["utility1_slot_quantity"] == 30


def test_restock_task_noops_below_min_level():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["small_health_potion"] = 100
    char = Character("A")
    run_async(char.refresh())  # level defaults to 1 in FakeClient

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "GET" and c[1] == "/my/bank/items" for c in client.calls)


def test_restock_task_noops_when_bank_is_empty():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    char = Character("A")
    run_async(char.refresh())

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))

    assert task.done is True
    assert char.data.get("utility1_slot") != "small_health_potion"


def test_restock_task_noops_when_already_fully_stocked():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.state["A"]["utility1_slot"] = "small_health_potion"
    client.state["A"]["utility1_slot_quantity"] = 100
    client.bank["small_health_potion"] = 50
    char = Character("A")
    run_async(char.refresh())

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "POST" for c in client.calls), "already at cap - should not withdraw/equip"


def test_restock_task_withdraws_and_equips_capped_at_max_quantity():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.state["A"]["inventory_max_items"] = 150  # plenty of room, not the binding constraint here
    client.bank["small_health_potion"] = 250  # more than max_quantity
    char = Character("A")
    run_async(char.refresh())

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    assert _tick_until_done(char, task, client)

    assert char.data["utility1_slot"] == "small_health_potion"
    assert char.data["utility1_slot_quantity"] == 100
    assert client.bank["small_health_potion"] == 150


def test_restock_task_caps_withdrawal_at_available_inventory_space():
    """Regression test for the Hugo incident: arriving at the bank with the
    inventory nearly full of combat loot must not make the task try to
    withdraw more potions than actually fit."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.state["A"]["inventory_max_items"] = 112
    client.bank["small_health_potion"] = 100
    char = Character("A")
    run_async(char.refresh())
    # 110/112 used, like Hugo's real inventory - only 2 free
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "raw_chicken", "quantity": 110}], "inventory_max_items": 112}
    )

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    assert _tick_until_done(char, task, client)

    assert char.data["utility1_slot_quantity"] == 2, "should withdraw only what actually fits"


def test_restock_task_noops_when_no_inventory_space_at_all():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.bank["small_health_potion"] = 100
    char = Character("A")
    run_async(char.refresh())
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "raw_chicken", "quantity": 20}], "inventory_max_items": 20}
    )

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(call[0] == "POST" for call in client.calls), "zero free space - should not attempt withdraw"


def test_restock_task_recovers_from_497_instead_of_looping_forever():
    """Defense in depth: even if something still overflows despite the
    free-space cap (e.g. a race), the task must recover, not raise."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.bank["small_health_potion"] = 50
    char = Character("A")
    run_async(char.refresh())

    client.fail_next_action_with_497("A")

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0


def test_restock_task_recovers_from_478_instead_of_looping_forever():
    """Regression test for the Hugo incident: characters share one bank
    and tick concurrently, so the availability check can be stale by the
    time the withdraw actually posts (another character got there first).
    The task must give up on this visit, not retry the same now-gone
    quantity forever."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.bank["small_health_potion"] = 50
    char = Character("A")
    run_async(char.refresh())

    client.fail_next_action_with_478("A")

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.data.get("utility1_slot") != "small_health_potion"


def test_restock_task_withdraws_less_than_max_if_bank_has_less():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["level"] = 8
    client.bank["small_health_potion"] = 12
    char = Character("A")
    run_async(char.refresh())

    task = RestockUtilityTask("small_health_potion", "utility1", max_quantity=100, min_level=5)
    assert _tick_until_done(char, task, client)

    assert char.data["utility1_slot_quantity"] == 12
    assert client.bank["small_health_potion"] == 0
