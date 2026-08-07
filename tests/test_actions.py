import pytest

from src.action import Action
from src.actions.fight_action import FightAction
from src.actions.rest_action import RestAction
from src.character import Character

from conftest import FakeClient, run_async


def test_action_without_configured_client_raises_instead_of_using_stale_state():
    with pytest.raises(RuntimeError):
        FightAction("chicken")


def test_fight_action_wires_up_client_and_name():
    """FightAction previously never called super().__init__(), so
    self.client didn't exist and any fight crashed with AttributeError."""
    Action.configure_client(FakeClient(["A"]))
    action = FightAction("chicken")
    assert action.client is not None
    assert action.name == "FightAction"


def test_fight_action_executes_and_updates_cooldown():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())

    run_async(FightAction("chicken").execute(char))
    assert char.cooldown >= 0
    assert ("POST", "/my/A/action/fight", {}) in client.calls


def test_rest_action_restores_hp_from_response():
    client = FakeClient(["A"])
    Action.configure_client(client)
    char = Character("A")
    run_async(char.refresh())
    char.data["hp"] = 10  # simulate damaged character

    run_async(RestAction().execute(char))
    assert char.hp == char.max_hp
