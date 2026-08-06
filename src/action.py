from __future__ import annotations

import os
import logging
from abc import ABC
from datetime import datetime, timezone
from dotenv import load_dotenv
from src.api_client import ArtifactsClient, ArtifactsAPIError, CharacterInCooldownError
from src.location import Location
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.character import Character

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
client = ArtifactsClient(token=os.getenv("API_TOKEN"))


class Action(ABC):
    def __init__(self, name: str = ""):
        self.name: str = name
        self.client = client

    def execute(self, character: Character, **kwargs):
        pass

    def apply_cooldown_from_payload(self, character: Character, payload: object) -> None:
        duration_seconds = self._extract_cooldown_seconds(payload)
        if duration_seconds is None:
            return

        if hasattr(character, "set_cooldown"):
            character.set_cooldown(duration_seconds)
            logger.info(f"{character.name} marked on local cooldown for {duration_seconds} seconds")

    def _extract_cooldown_seconds(self, payload: object) -> int | None:
        if isinstance(payload, CharacterInCooldownError):
            return payload.cooldown_seconds

        if isinstance(payload, ArtifactsAPIError):
            payload = payload.data

        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        cooldown = None
        if isinstance(data, dict):
            cooldown = data.get("cooldown")
        if cooldown is None:
            cooldown = payload.get("cooldown")
        if not isinstance(cooldown, dict):
            return None

        expiration = cooldown.get("expiration")
        if expiration:
            try:
                expiration_dt = datetime.fromisoformat(str(expiration).replace("Z", "+00:00"))
                now_dt = datetime.now(timezone.utc)
                return max(0, int((expiration_dt - now_dt).total_seconds()))
            except ValueError:
                pass

        for key in ("remaining_seconds", "total_seconds"):
            value = cooldown.get(key)
            if isinstance(value, (int, float)):
                return int(value)
            if isinstance(value, str):
                try:
                    return int(value)
                except ValueError:
                    continue

        return None

