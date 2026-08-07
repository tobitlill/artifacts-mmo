import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from src.action import Action
from src.api_client import ArtifactsAPIError, CharacterInCooldownError


def run_async(coro):
    """Tests stay plain `def test_...()` (no extra pytest-asyncio dependency
    needed); this just drives the coroutine to completion."""
    return asyncio.run(coro)


class FakeClient:
    """Stands in for ArtifactsClient: same get()/post() surface, no network.
    Mimics just enough of the real API's behaviour (cooldown rejection,
    already-on-map, response shape) to exercise the Task/Goal/Character/Game
    layers end-to-end."""

    def __init__(self, names):
        self.state = {
            n: {
                "x": 0,
                "y": 0,
                "hp": 100,
                "max_hp": 100,
                "level": 1,
                "inventory": [],
                "inventory_max_items": 20,
                "cooldown_expiration": None,
                "utility1_slot": "",
                "utility1_slot_quantity": 0,
                "utility2_slot": "",
                "utility2_slot_quantity": 0,
                "_sunflowers": 0,
            }
            for n in names
        }
        self.bank: dict[str, int] = {}
        self.calls = []
        self.items: dict[str, dict] = {
            "small_health_potion": {
                "code": "small_health_potion",
                "craft": {
                    "skill": "alchemy",
                    "level": 5,
                    "items": [{"code": "sunflower", "quantity": 3}],
                    "quantity": 2,
                },
            },
        }

    def _char_payload(self, name):
        s = self.state[name]
        return {"name": name, **s}

    async def get(self, path, params=None):
        self.calls.append(("GET", path))
        if path == "/my/characters":
            return {"data": [self._char_payload(n) for n in self.state]}
        if path == "/my/bank/items":
            item_code = (params or {}).get("item_code")
            quantity = self.bank.get(item_code, 0)
            items = [{"code": item_code, "quantity": quantity}] if quantity > 0 else []
            return {"data": items}
        if path.startswith("/items/"):
            code = path.split("/")[-1]
            # Anything not explicitly registered as craftable defaults to
            # a plain raw-resource item (no "craft" field) - matches most
            # test item codes (sunflower, wood, ...) without needing each
            # one pre-registered individually.
            item = self.items.get(code, {"code": code})
            return {"data": item}
        raise AssertionError(f"unexpected GET {path}")

    async def post(self, path, json=None):
        self.calls.append(("POST", path, json))
        name = path.split("/")[2]
        s = self.state[name]

        cd = s.get("cooldown_expiration")
        if cd and datetime.fromisoformat(cd) > datetime.now(timezone.utc):
            raise CharacterInCooldownError(name, 3)

        if path.endswith("/action/move"):
            if s["x"] == json["x"] and s["y"] == json["y"]:
                raise ArtifactsAPIError(490, "already there", {"error": {"message": "already there"}})
            s["x"], s["y"] = json["x"], json["y"]
            return self._resp(name)

        if path.endswith("/action/gathering"):
            self._maybe_fail(s)
            s["_sunflowers"] += 10
            s["inventory"] = [{"code": "sunflower", "quantity": s["_sunflowers"]}]
            return self._resp(name)

        if path.endswith("/action/bank/deposit/item"):
            code, quantity = json[0]["code"], json[0]["quantity"]
            self.bank[code] = self.bank.get(code, 0) + quantity
            for slot in s["inventory"]:
                if slot["code"] == code:
                    slot["quantity"] -= quantity
            s["inventory"] = [slot for slot in s["inventory"] if slot.get("quantity", 0) > 0]
            return self._resp(name)

        if path.endswith("/action/bank/withdraw/item"):
            self._maybe_fail(s)
            code, quantity = json[0]["code"], json[0]["quantity"]
            self.bank[code] = self.bank.get(code, 0) - quantity
            existing = next((slot for slot in s["inventory"] if slot["code"] == code), None)
            if existing:
                existing["quantity"] += quantity
            else:
                s["inventory"].append({"code": code, "quantity": quantity})
            return self._resp(name)

        if path.endswith("/action/equip"):
            self._maybe_fail(s)
            item = json[0]
            code, slot, quantity = item["code"], item["slot"], item.get("quantity", 1)
            s["inventory"] = [i for i in s["inventory"] if i["code"] != code]
            s[f"{slot}_slot"] = code
            s[f"{slot}_slot_quantity"] = quantity
            return self._resp(name)

        if path.endswith("/action/fight"):
            self._maybe_fail(s)
            return self._resp(name)

        if path.endswith("/action/rest"):
            s["hp"] = s["max_hp"]
            return self._resp(name)

        if path.endswith("/action/crafting"):
            self._maybe_fail(s)
            self._craft(s, json["code"], json.get("quantity", 1))
            return self._resp(name)

        raise AssertionError(f"unexpected POST {path}")

    def _craft(self, s, code, quantity):
        item = self.items[code]
        craft = item["craft"]

        skill_level = s.get(f"{craft['skill']}_level", 0)
        if skill_level < craft["level"]:
            raise ArtifactsAPIError(493, "skill level too low", {"error": {"message": "skill level too low"}})

        for material in craft["items"]:
            have = sum(slot["quantity"] for slot in s["inventory"] if slot["code"] == material["code"])
            if have < material["quantity"] * quantity:
                raise ArtifactsAPIError(478, "missing item", {"error": {"message": "missing item"}})

        produced = craft["quantity"] * quantity
        consumed_total = sum(material["quantity"] * quantity for material in craft["items"])
        current_total = sum(slot["quantity"] for slot in s["inventory"])
        if current_total - consumed_total + produced > s["inventory_max_items"]:
            raise ArtifactsAPIError(497, "inventory full", {"error": {"message": "inventory full"}})

        for material in craft["items"]:
            remove_qty = material["quantity"] * quantity
            for slot in s["inventory"]:
                if slot["code"] == material["code"]:
                    slot["quantity"] -= remove_qty
        s["inventory"] = [slot for slot in s["inventory"] if slot.get("quantity", 0) > 0]

        existing = next((slot for slot in s["inventory"] if slot["code"] == code), None)
        if existing:
            existing["quantity"] += produced
        else:
            s["inventory"].append({"code": code, "quantity": produced})

    def _resp(self, name, seconds=0):
        s = self.state[name]
        expiration = (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat()
        s["cooldown_expiration"] = expiration
        return {
            "data": {
                "character": self._char_payload(name),
                "cooldown": {"expiration": expiration, "remaining_seconds": seconds},
            }
        }

    def _maybe_fail(self, s):
        pending = s.pop("_fail_next_with", None)
        if pending is not None:
            status_code, message = pending
            raise ArtifactsAPIError(status_code, message, {"error": {"message": message}})

    def fail_next_action_with_598(self, name):
        """Simulates the world having moved on without us - e.g. a fight
        loss that relocated the character server-side before our local
        state caught up. The next fight/gather POST for this character
        raises 598 exactly once."""
        self.state[name]["_fail_next_with"] = (598, "Monster not found on this map.")

    def fail_next_action_with_497(self, name):
        """Simulates a fight/gather whose combined loot doesn't fit even
        though free space looked sufficient beforehand. The next
        fight/gather POST for this character raises 497 exactly once."""
        self.state[name]["_fail_next_with"] = (497, "The character's inventory is full.")

    def fail_next_action_with_478(self, name):
        """Simulates a bank stock race: another character (this is a
        multi-character bot sharing one bank) withdrew the item between our
        availability check and this withdrawal actually posting. The next
        withdraw POST for this character raises 478 exactly once."""
        self.state[name]["_fail_next_with"] = (478, "Missing item or insufficient quantity in this item.")

    def expire_cooldown(self, name):
        """Force both the fake server's and (via the real Character object,
        separately) the local cooldown clock to have already passed -
        avoids tests needing real sleeps."""
        self.state[name]["cooldown_expiration"] = (
            datetime.now(timezone.utc) - timedelta(seconds=1)
        ).isoformat()


@pytest.fixture(autouse=True)
def reset_action_client():
    """Action.client is process-global (by design - one shared client);
    make sure one test's FakeClient never leaks into the next."""
    yield
    Action.client = None


@pytest.fixture(autouse=True)
def reset_event_log():
    """EVENT_LOG is a process-global ring buffer for the dashboard; clear it
    between tests so assertions never see events from a previous test."""
    from src.event_log import EVENT_LOG

    yield
    EVENT_LOG.clear()
