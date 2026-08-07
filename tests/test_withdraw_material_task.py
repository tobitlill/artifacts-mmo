from src.action import Action
from src.character import Character
from src.tasks.withdraw_material_task import WithdrawMaterialTask

from conftest import FakeClient, run_async


def _char(client, name="A", inventory_max_items=50):
    client.state[name]["inventory_max_items"] = inventory_max_items
    char = Character(name)
    run_async(char.refresh())
    return char


def _tick_until_done(char, task, client, max_ticks=20):
    for _ in range(max_ticks):
        run_async(task.tick(char))
        if task.done:
            return True
        if char.cooldown > 0:
            client.expire_cooldown(char.name)
            char.set_cooldown_until(None)
    return False


def test_withdraws_requested_quantity_when_available():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 100
    char = _char(client)

    task = WithdrawMaterialTask("sunflower", 30)
    assert _tick_until_done(char, task, client)

    assert char.inventory.get_item_count("sunflower") == 30
    assert client.bank["sunflower"] == 70


def test_caps_at_bank_availability():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 5
    char = _char(client)

    task = WithdrawMaterialTask("sunflower", 30)
    assert _tick_until_done(char, task, client)

    assert char.inventory.get_item_count("sunflower") == 5
    assert client.bank.get("sunflower", 0) == 0


def test_caps_at_free_inventory_space():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 100
    char = _char(client, inventory_max_items=10)

    task = WithdrawMaterialTask("sunflower", 30)
    assert _tick_until_done(char, task, client)

    assert char.inventory.get_item_count("sunflower") == 10
    assert client.bank["sunflower"] == 90


def test_noops_when_bank_has_none():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)

    task = WithdrawMaterialTask("sunflower", 30)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "POST" for c in client.calls)


def test_recovers_from_497_instead_of_looping_forever():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 50
    char = _char(client)
    client.fail_next_action_with_497("A")

    task = WithdrawMaterialTask("sunflower", 30)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0


def test_recovers_from_478_instead_of_looping_forever():
    """Regression: characters share one bank and tick concurrently, so the
    availability check can be stale by the time the withdraw actually
    posts (another character got there first). Must give up on this
    material for now, not retry the same now-gone quantity forever."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 50
    char = _char(client)
    client.fail_next_action_with_478("A")

    task = WithdrawMaterialTask("sunflower", 30)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_item_count("sunflower") == 0


def test_recovers_from_598_instead_of_crashing():
    """Defense in depth: the caller (GatherResourcesGoal) is responsible
    for making sure the character is at the bank before returning this
    task - but if that's ever wrong (stale position), it must resync
    rather than let the exception escape uncaught."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["sunflower"] = 50
    char = _char(client)
    client.fail_next_action_with_598("A")

    task = WithdrawMaterialTask("sunflower", 30)
    run_async(task.tick(char))  # must not raise

    assert task.done is True
