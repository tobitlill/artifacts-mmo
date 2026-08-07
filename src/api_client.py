#!/usr/bin/env python3

"""
Minimal Artifacts MMO API Client

Features:
- Bearer authentication
- JSON requests
- Retry handling
- Rate limit handling
- Per-character cooldown handling
- Generic endpoint access
- Fully async (aiohttp) so many characters can act concurrently instead of
  queuing behind each other's network round trips
"""

from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict

import aiohttp

logger = logging.getLogger(__name__)


class ArtifactsAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        data: Any = None,
    ):
        self.status_code = status_code
        self.message = message
        self.data = data

        super().__init__(f"[{status_code}] {message}")


class CharacterInCooldownError(Exception):
    def __init__(
        self,
        character_name: str,
        cooldown_seconds: int,
    ):
        self.character_name = character_name
        self.cooldown_seconds = cooldown_seconds

        super().__init__(
            f"Character {character_name} is on cooldown for {cooldown_seconds} seconds"
        )


class ArtifactsClient:

    BASE_URL = "https://api.artifactsmmo.com"

    def __init__(
        self,
        token: str,
        base_url: str | None = None,
        timeout: int = 30,
        max_retries: int = 5,
    ):
        self.base_url = base_url.rstrip("/") if base_url else self.BASE_URL

        self.timeout = timeout
        self.max_retries = max_retries
        self.token = token

        # Created lazily on first request so the aiohttp session is always
        # bound to the event loop that's actually running requests.
        self._session: aiohttp.ClientSession | None = None
        self._session_lock = asyncio.Lock()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "ArtifactsClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self.close()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is not None:
            return self._session

        async with self._session_lock:
            if self._session is None:
                self._session = aiohttp.ClientSession(
                    headers={
                        "Authorization": f"Bearer {self.token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                        "User-Agent": "artifacts-python-client/1.0",
                    },
                    timeout=aiohttp.ClientTimeout(total=self.timeout),
                )
        return self._session

    # ---------------------------------------------------------
    # Public HTTP methods
    # ---------------------------------------------------------

    async def get(
        self,
        path: str,
        params: Dict[str, Any] | None = None,
    ):
        return await self.request(
            "GET",
            path,
            params=params,
        )

    async def post(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return await self.request(
            "POST",
            path,
            json=json,
        )

    async def patch(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return await self.request(
            "PATCH",
            path,
            json=json,
        )

    async def delete(
        self,
        path: str,
        json: Dict[str, Any] | None = None,
    ):
        return await self.request(
            "DELETE",
            path,
            json=json,
        )

    # ---------------------------------------------------------
    # Core request handler
    # ---------------------------------------------------------

    async def request(
        self,
        method: str,
        path: str,
        **kwargs,
    ):
        logger.debug(f"{method} {path} with params {kwargs.get('params', {})}")

        session = await self._ensure_session()
        url = self.base_url + path
        retries = 0

        while True:

            async with session.request(method, url, **kwargs) as response:
                try:
                    data = await response.json(content_type=None)
                except Exception:
                    data = await response.text()

                # ---------------------------------------------
                # Success
                # ---------------------------------------------

                if response.ok:
                    return data

                # ---------------------------------------------
                # Rate limit / temporary errors
                # ---------------------------------------------

                if response.status in (
                    429,
                    500,
                    502,
                    503,
                    504,
                ):

                    if retries >= self.max_retries:
                        raise ArtifactsAPIError(
                            response.status,
                            "Maximum retries exceeded",
                            data,
                        )

                    delay = self._retry_delay(
                        response,
                        retries,
                    )

                    await asyncio.sleep(delay)

                    retries += 1
                    continue

                # ---------------------------------------------
                # Character in cooldown (code 499)
                # ---------------------------------------------

                if response.status == 499:
                    cooldown_seconds = self._extract_cooldown_seconds(data)
                    raise CharacterInCooldownError(
                        self._character_name_from_path(path),
                        cooldown_seconds if cooldown_seconds is not None else 0,
                    )

                # ---------------------------------------------
                # API errors
                # ---------------------------------------------

                message = (
                    data.get("error", {}).get("message")
                    if isinstance(data, dict)
                    else str(data)
                )

                raise ArtifactsAPIError(
                    response.status,
                    message,
                    data,
                )

    # ---------------------------------------------------------
    # Retry calculation
    # ---------------------------------------------------------

    def _extract_cooldown_seconds(self, payload: Any) -> int | None:
        if not isinstance(payload, dict):
            return None

        data = payload.get("data")
        cooldown = data.get("cooldown") if isinstance(data, dict) else None

        if isinstance(cooldown, dict):
            remaining_seconds = cooldown.get("remaining_seconds")
            if isinstance(remaining_seconds, (int, float)):
                return int(remaining_seconds)
            if isinstance(remaining_seconds, str):
                try:
                    return int(remaining_seconds)
                except ValueError:
                    pass

            expiration = cooldown.get("expiration")
            if isinstance(expiration, str):
                try:
                    expiration_dt = datetime.fromisoformat(expiration.replace("Z", "+00:00"))
                    now_dt = datetime.now(timezone.utc)
                    return max(0, int((expiration_dt - now_dt).total_seconds()))
                except ValueError:
                    pass

        # The 499 (cooldown) error body typically only carries {"error": {"message": ...}}
        # without a structured cooldown object; best-effort parse the remaining time out
        # of the message text so callers don't have to fall back to a refresh() every time.
        error = payload.get("error")
        message = error.get("message") if isinstance(error, dict) else None
        if isinstance(message, str):
            match = re.search(r"([\d.]+)\s*second", message, re.IGNORECASE)
            if match:
                try:
                    return int(float(match.group(1)))
                except ValueError:
                    return None

        return None

    @staticmethod
    def _character_name_from_path(path: str) -> str:
        match = re.match(r"^/my/([^/]+)/action/", path)
        return match.group(1) if match else "unknown"

    def _retry_delay(
        self,
        response,
        retry_number,
    ):

        retry_after = response.headers.get("Retry-After")

        if retry_after:
            return float(retry_after)

        # exponential backoff
        return min(
            2**retry_number,
            30,
        )
