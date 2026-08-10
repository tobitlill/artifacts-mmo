from src.action import Action
from src.character import Character
from src.tasks.equip_tool_task import EquipToolTask

from conftest import FakeClient, run_async


def _char(client, name="A", level=1, inventory_max_items=20):
    client.state[name]["level"] = level
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


def test_noops_below_min_level():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 50
    char = _char(client, level=1)

    task = EquipToolTask("wooden_axe", "weapon", min_level=5)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "GET" and c[1] == "/my/bank/items" for c in client.calls)


def test_noops_when_already_equipped():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["weapon_slot"] = "wooden_axe"
    client.state["A"]["weapon_slot_quantity"] = 1
    char = _char(client)

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "POST" for c in client.calls)
    assert not any(c[0] == "GET" and c[1] == "/my/bank/items" for c in client.calls)


def test_noops_when_bank_has_none():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = _char(client)
    # client.bank has no wooden_axe at all

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "POST" for c in client.calls)


def test_noops_when_no_inventory_space():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 50
    char = _char(client, inventory_max_items=5)
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "raw_chicken", "quantity": 5}], "inventory_max_items": 5}
    )

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))

    assert task.done is True
    assert not any(c[0] == "POST" for c in client.calls)


def test_withdraws_and_equips_when_nothing_equipped_yet():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 5
    char = _char(client)

    task = EquipToolTask("wooden_axe", "weapon")
    assert _tick_until_done(char, task, client)

    assert char.data["weapon_slot"] == "wooden_axe"
    assert char.data["weapon_slot_quantity"] == 1
    assert client.bank["wooden_axe"] == 4


def test_swaps_out_the_old_tool_and_deposits_it():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.state["A"]["weapon_slot"] = "wooden_stick"
    client.state["A"]["weapon_slot_quantity"] = 1
    client.bank["wooden_axe"] = 5
    char = _char(client)

    task = EquipToolTask("wooden_axe", "weapon")
    assert _tick_until_done(char, task, client)

    assert char.data["weapon_slot"] == "wooden_axe"
    assert char.data["weapon_slot_quantity"] == 1
    assert client.bank["wooden_axe"] == 4
    assert client.bank["wooden_stick"] == 1, "the old tool must end up back in the bank"
    assert char.inventory.get_item_count("wooden_stick") == 0


def test_recovers_from_497_during_withdraw_instead_of_looping_forever():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 50
    char = _char(client)
    client.fail_next_action_with_497("A")

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0


def test_recovers_from_478_during_withdraw_instead_of_looping_forever():
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 50
    char = _char(client)
    client.fail_next_action_with_478("A")

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.data.get("weapon_slot") != "wooden_axe"


def test_recovers_from_598_during_withdraw_instead_of_crashing():
    """Defense in depth: the caller (a Goal) is responsible for making
    sure the character is at the bank before returning this task - but if
    that's ever wrong (stale position), it must resync rather than let
    the exception escape uncaught."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    client.bank["wooden_axe"] = 50
    char = _char(client)
    client.fail_next_action_with_598("A")

    task = EquipToolTask("wooden_axe", "weapon")
    run_async(task.tick(char))  # must not raise

    assert task.done is True
