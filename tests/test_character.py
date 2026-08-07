from datetime import datetime, timedelta, timezone

from src.action import Action
from src.character import Character
from src.location import Location

from conftest import FakeClient, run_async


def test_cooldown_rounds_up_not_down():
    """A remaining cooldown of e.g. 0.99s must never read as 0 - that would
    let is_on_cooldown() greenlight an action the server still rejects."""
    char = Character("A")
    char.set_cooldown_until(datetime.now(timezone.utc) + timedelta(seconds=0.5))
    assert char.cooldown >= 1


def test_cooldown_is_zero_once_expired():
    char = Character("A")
    char.set_cooldown_until(datetime.now(timezone.utc) - timedelta(seconds=1))
    assert char.cooldown == 0
    assert char.cooldown_until is None


def test_cooldown_is_live_not_cached():
    char = Character("A")
    char.set_cooldown_seconds(1)
    first = char.cooldown
    assert first >= 1
    char.set_cooldown_until(None)
    assert char.cooldown == 0, "cooldown must recompute from cooldown_until every access"


def test_hp_percent_from_character_data():
    char = Character("A")
    char.apply_character_payload({"x": 0, "y": 0, "hp": 25, "max_hp": 100})
    assert char.hp_percent == 25.0


def test_hp_percent_defaults_to_100_with_no_data():
    char = Character("A")
    assert char.hp_percent == 100.0


def test_apply_character_payload_updates_position_inventory_and_cooldown():
    char = Character("A")
    expiration = (datetime.now(timezone.utc) + timedelta(seconds=5)).isoformat()
    char.apply_character_payload(
        {
            "x": 3,
            "y": 4,
            "hp": 80,
            "max_hp": 100,
            "cooldown_expiration": expiration,
            "inventory": [{"code": "wood", "quantity": 2}],
            "inventory_max_items": 10,
        }
    )
    assert char.position == Location(3, 4)
    assert char.cooldown >= 5
    assert char.inventory.get_item_count("wood") == 2
    assert char.inventory.get_free_space() == 8


def test_refresh_syncs_from_api_without_extra_calls():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")

    run_async(char.refresh())

    assert char.position == Location(0, 0)
    assert char.cooldown == 0
    assert [c[0:2] for c in client.calls] == [("GET", "/my/characters")]
