from src.action import Action
from src.character import Character
from src.location import Location
from src.tasks.deposit_task import DepositTask
from src.tasks.fight_task import FightTask
from src.tasks.gather_task import GatherTask
from src.tasks.travel_task import TravelTask

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


def test_travel_task_updates_position_from_response_not_optimistically():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    task = TravelTask(Location(2, 2))
    assert _tick_until_done(char, task, client)
    assert char.position == Location(2, 2)


def test_travel_task_already_there_marks_done_via_490():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())  # already at (0, 0)

    task = TravelTask(Location(0, 0))
    run_async(task.tick(char))

    assert task.done is True
    assert char.position == Location(0, 0)


def test_gather_task_updates_inventory_from_response():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    task = GatherTask()
    assert _tick_until_done(char, task, client)
    assert char.inventory.get_item_count("sunflower") == 10


def test_gather_task_recovers_from_server_side_cooldown_rejection():
    """Simulates the local cooldown clock being stale: server still says
    499 even though our local check passed. Must not crash the task."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    # Pre-arm the fake server with an active cooldown the character doesn't
    # know about locally.
    client.state["A"]["cooldown_expiration"] = None
    from datetime import datetime, timedelta, timezone
    client.state["A"]["cooldown_expiration"] = (
        datetime.now(timezone.utc) + timedelta(seconds=2)
    ).isoformat()

    task = GatherTask()
    run_async(task.tick(char))  # should catch CharacterInCooldownError, not raise

    assert task.done is False
    assert char.cooldown > 0, "character should have adopted the server's cooldown"


def test_fight_task_resyncs_on_598_instead_of_looping_forever():
    """Regression test for the Hugo incident: losing a fight can relocate
    the character (respawn point) and drop HP to near-zero server-side
    without our local state knowing yet. The next fight attempt then fails
    with 598 (monster not on this tile) - the task must resync from the API
    and mark itself done, not raise and get retried against stale state
    forever."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    # Simulate the real post-loss server state: relocated, HP near zero.
    client.state["A"]["x"] = 0
    client.state["A"]["y"] = 0
    client.state["A"]["hp"] = 1
    client.fail_next_action_with_598("A")

    task = FightTask("chicken")
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.position == Location(0, 0), "resync should have picked up the real position"
    assert char.hp == 1, "resync should have picked up the real HP"


def test_gather_task_resyncs_on_598_instead_of_looping_forever():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    client.state["A"]["x"] = 3
    client.state["A"]["y"] = 3
    client.fail_next_action_with_598("A")

    task = GatherTask()
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.position == Location(3, 3)


def test_fight_task_marks_inventory_full_on_497_instead_of_looping_forever():
    """Regression test: a fight can drop multiple loot items at once, so
    free space can look sufficient right up until a single fight's combined
    loot doesn't fit. The server rejects with 497 - the task must trust
    that over its own quantity-sum and force get_free_space() to 0 so the
    goal is routed to the bank next tick, not retried against the same
    'still looks like enough room' snapshot forever."""
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "raw_chicken", "quantity": 6}], "inventory_max_items": 10}
    )
    assert char.inventory.get_free_space() == 4  # "looks fine" by our own count

    client.fail_next_action_with_497("A")

    task = FightTask("chicken")
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0, "server's rejection must override our own count"


def test_gather_task_marks_inventory_full_on_497_instead_of_looping_forever():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    client.fail_next_action_with_497("A")

    task = GatherTask()
    run_async(task.tick(char))  # must not raise

    assert task.done is True
    assert char.inventory.get_free_space() == 0


def test_inventory_full_override_clears_on_next_authoritative_update():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    char.inventory.mark_full()
    assert char.inventory.get_free_space() == 0

    char.inventory.update_from_character_data({"inventory": [], "inventory_max_items": 20})
    assert char.inventory.get_free_space() == 20


def test_deposit_task_all_picks_first_nonempty_stack():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    char.inventory.update_from_character_data(
        {"inventory": [{"code": "wood", "quantity": 3}], "inventory_max_items": 20}
    )

    task = DepositTask(all=True)
    assert _tick_until_done(char, task, client)
    assert char.inventory.get_item_count("wood") == 0


def test_deposit_task_all_with_empty_inventory_marks_done_without_calling_api():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    task = DepositTask(all=True)
    run_async(task.tick(char))

    assert task.done is True
    assert not any(call[0] == "POST" for call in client.calls)
